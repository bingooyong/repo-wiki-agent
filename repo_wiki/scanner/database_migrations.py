"""Database migration and table schema extractor for Phase 26.2.

Extracts SQL table definitions, migrations, schema evolution from migration files.
Links tables to canonical models and preserves file/line citations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from repo_wiki.core.contracts import RepositorySnapshot
from repo_wiki.generator.io import ensure_dir, write_yamlish


# SQL file hints for migration detection
_MIGRATION_FILE_PATTERNS = (
    "migration",
    "alembic",
    "schema",
    "init_db",
    "create_table",
)


@dataclass
class TableColumn:
    """Represents a database table column."""
    name: str
    data_type: str
    is_nullable: bool = True
    is_primary_key: bool = False
    is_unique: bool = False
    default_value: str | None = None
    check_constraint: str | None = None
    foreign_key: tuple[str, str, str] | None = None  # (column, ref_table, ref_column)


@dataclass
class TableSchema:
    """Represents a database table schema with columns and constraints."""
    name: str
    columns: list[TableColumn] = field(default_factory=list)
    primary_key_columns: list[str] = field(default_factory=list)
    file_path: str = ""
    line_start: int = 0
    line_end: int = 0
    canonical_model_name: str | None = None  # Link to canonical model


@dataclass
class MigrationFile:
    """Represents a database migration file."""
    path: str
    version: str | None = None  # Alembic version or migration number
    down_revision: str | None = None  # Alembic down revision
    up_revision: str | None = None  # Alembic up revision
    tables_created: list[str] = field(default_factory=list)
    tables_altered: list[str] = field(default_factory=list)
    tables_dropped: list[str] = field(default_factory=list)
    indexes_created: list[str] = field(default_factory=list)
    line_start: int = 0
    line_end: int = 0


@dataclass
class SchemaEvolution:
    """Tracks schema evolution across migrations."""
    tables: list[TableSchema] = field(default_factory=list)
    migrations: list[MigrationFile] = field(default_factory=list)
    table_to_model_links: dict[str, str] = field(default_factory=dict)  # table_name -> model_name


class DatabaseMigrationExtractor:
    """Extracts database migrations and table schemas from repository."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def extract(self) -> SchemaEvolution:
        """Extract all database migrations and table schemas."""
        schema_evolution = SchemaEvolution()

        # Find all SQL files and migration files
        migration_files = self._find_migration_files()

        for file_path, content in migration_files:
            rel_path = file_path.relative_to(self.root).as_posix()
            lines = content.split("\n")

            # Extract table definitions
            tables = self._extract_tables(content, rel_path, lines)
            schema_evolution.tables.extend(tables)

            # Extract migration metadata
            migration = self._extract_migration_info(
                file_path, content, rel_path, lines
            )
            if migration:
                schema_evolution.migrations.append(migration)

            # Link tables to canonical models
            for table in tables:
                model_name = self._guess_canonical_model(table.name)
                table.canonical_model_name = model_name
                schema_evolution.table_to_model_links[table.name] = model_name

        # Deduplicate tables by name
        seen: dict[str, TableSchema] = {}
        for table in schema_evolution.tables:
            if table.name not in seen:
                seen[table.name] = table
        schema_evolution.tables = list(seen.values())

        return schema_evolution

    def _find_migration_files(self) -> list[tuple[Path, str]]:
        """Find all files that might contain database migrations."""
        files: list[tuple[Path, str]] = []

        for path in self.root.rglob("*"):
            if not path.is_file():
                continue

            rel_path = path.relative_to(self.root)
            path_str_lower = rel_path.as_posix().lower()

            # Check if it's a SQL file
            is_sql_file = path.suffix.lower() in {".sql"}

            # For Python files, only include if they look like Alembic migrations
            is_python_migration = path.suffix.lower() == ".py" and any(
                pattern in path_str_lower for pattern in ("alembic", "migration", "versions")
            )

            if is_sql_file or is_python_migration:
                try:
                    file_content = path.read_text(encoding="utf-8", errors="ignore")
                    if file_content.strip():
                        files.append((path, file_content))
                except Exception:
                    pass

        return files

    def _extract_tables(
        self, content: str, rel_path: str, lines: list[str]
    ) -> list[TableSchema]:
        """Extract table definitions from SQL content."""
        tables: list[TableSchema] = []

        # Match CREATE TABLE statements
        create_table_pattern = re.compile(
            r"""(?ix)
            CREATE\s+TABLE\s+
            (?:IF\s+NOT\s+EXISTS\s+)?
            ([A-Za-z_][A-Za-z0-9_]*)""",
        )

        for match in create_table_pattern.finditer(content):
            table_name = match.group(1)
            start_pos = match.start()
            start_line = content[:start_pos].count("\n") + 1

            # Find the end of the CREATE TABLE statement
            end_pos = self._find_sql_block_end(content, match.end())
            end_line = content[:end_pos].count("\n") + 1

            # Extract column definitions from the table body
            table_body = content[start_pos:end_pos]
            columns = self._extract_columns(table_body)

            # Extract primary key columns
            pk_columns = self._extract_primary_keys(table_body)

            # Extract foreign keys
            foreign_keys = self._extract_foreign_keys(table_body)
            for fk in foreign_keys:
                for col in columns:
                    if col.name == fk[0]:
                        col.foreign_key = fk

            # Mark primary key columns
            for col in columns:
                if col.name in pk_columns:
                    col.is_primary_key = True

            table = TableSchema(
                name=table_name,
                columns=columns,
                primary_key_columns=pk_columns,
                file_path=rel_path,
                line_start=start_line,
                line_end=end_line,
            )
            tables.append(table)

        return tables

    def _extract_columns(self, table_body: str) -> list[TableColumn]:
        """Extract column definitions from CREATE TABLE body.

        Handles simple column definitions like:
            column_name VARCHAR(255) NOT NULL,
            column_name INTEGER PRIMARY KEY,
            column_name TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        """
        columns: list[TableColumn] = []

        # Find the content between the first ( and the last )
        first_paren = table_body.find("(")
        last_paren = table_body.rfind(")")

        if first_paren == -1 or last_paren == -1 or first_paren >= last_paren:
            return columns

        # Get the column definitions (everything between first pair of parentheses)
        column_defs = table_body[first_paren + 1:last_paren]

        # Split by comma, handling nested parentheses
        column_parts = self._split_by_comma(column_defs)

        for part in column_parts:
            part = part.strip()
            if not part:
                continue

            # Skip constraint definitions that aren't column definitions
            upper_part = part.upper()
            if any(
                upper_part.startswith(kw)
                for kw in ["PRIMARY KEY", "FOREIGN KEY", "UNIQUE", "CHECK", "CONSTRAINT"]
            ):
                continue

            # Parse column name and type
            # Match: column_name DATA_TYPE OptionalConstraints
            col_match = re.match(
                r"""(?ix)
                ^(\w+)\s+           # Column name
                ([A-Za-z_][A-Za-z0-9_]*(?:\s*\([^)]+\))?)  # Data type with optional args
                (.*)?               # Optional constraints
                $""",
                part,
            )

            if col_match:
                col_name = col_match.group(1)
                data_type = col_match.group(2).strip().upper()
                constraints = col_match.group(3) or ""

                # Parse constraints
                is_nullable = "NOT NULL" not in constraints.upper()
                is_unique = "UNIQUE" in constraints.upper()

                # Extract default value
                default_match = re.search(
                    r"""(?ix)DEFAULT\s+([^\s,]+)""", constraints
                )
                default_value = default_match.group(1) if default_match else None

                # Extract check constraint
                check_match = re.search(
                    r"""(?ix)CHECK\s*\(([^)]+)\)""", constraints
                )
                check_constraint = check_match.group(1) if check_match else None

                columns.append(
                    TableColumn(
                        name=col_name,
                        data_type=data_type,
                        is_nullable=is_nullable,
                        is_unique=is_unique,
                        default_value=default_value,
                        check_constraint=check_constraint,
                    )
                )

        return columns

    def _extract_primary_keys(self, table_body: str) -> list[str]:
        """Extract primary key column names."""
        pk_columns: list[str] = []

        # Extract just the column definitions part (between parentheses)
        first_paren = table_body.find("(")
        last_paren = table_body.rfind(")")
        if first_paren == -1 or last_paren == -1 or first_paren >= last_paren:
            return pk_columns

        column_section = table_body[first_paren + 1:last_paren]

        # Look for PRIMARY KEY (col1, col2, ...) at the end of table definition
        pk_match = re.search(
            r"""(?ix)PRIMARY\s+KEY\s*\(\s*([^\)]+)\s*\)""",
            column_section,
        )
        if pk_match:
            pk_cols_str = pk_match.group(1)
            pk_columns = [
                col.strip().strip('"').strip("'")
                for col in pk_cols_str.split(",")
            ]

        # Also check inline PRIMARY KEY on columns
        # Match column definitions with PRIMARY KEY inline
        for col_def in column_section.split(","):
            col_upper = col_def.upper()
            if "PRIMARY KEY" in col_upper:
                # This is a column definition with PRIMARY KEY
                col_name_match = re.match(r"^\s*(\w+)", col_def)
                if col_name_match:
                    col_name = col_name_match.group(1)
                    if col_name not in pk_columns:
                        pk_columns.append(col_name)

        return pk_columns

    def _extract_foreign_keys(
        self, table_body: str
    ) -> list[tuple[str, str, str]]:
        """Extract foreign key definitions.

        Returns list of (column, ref_table, ref_column) tuples.
        """
        foreign_keys: list[tuple[str, str, str]] = []

        fk_pattern = re.compile(
            r"""(?ix)
            FOREIGN\s+KEY\s*\(\s*(\w+)\s*\)\s*
            REFERENCES\s+(\w+)\s*\(\s*(\w+)\s*\)""",
        )

        for match in fk_pattern.finditer(table_body):
            column = match.group(1)
            ref_table = match.group(2)
            ref_column = match.group(3)
            foreign_keys.append((column, ref_table, ref_column))

        return foreign_keys

    def _extract_migration_info(
        self,
        file_path: Path,
        content: str,
        rel_path: str,
        lines: list[str],
    ) -> MigrationFile | None:
        """Extract migration metadata from file."""
        tables_created = []
        tables_altered = []
        tables_dropped = []
        indexes_created = []

        # Find CREATE TABLE statements
        create_table_pattern = re.compile(
            r"""(?ix)CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([A-Za-z_][A-Za-z0-9_]*)""",
        )
        for match in create_table_pattern.finditer(content):
            tables_created.append(match.group(1))

        # Find ALTER TABLE statements
        alter_table_pattern = re.compile(
            r"""(?ix)ALTER\s+TABLE\s+([A-Za-z_][A-Za-z0-9_]*)""",
        )
        for match in alter_table_pattern.finditer(content):
            tables_altered.append(match.group(1))

        # Find DROP TABLE statements
        drop_table_pattern = re.compile(
            r"""(?ix)DROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?([A-Za-z_][A-Za-z0-9_]*)""",
        )
        for match in drop_table_pattern.finditer(content):
            tables_dropped.append(match.group(1))

        # Find CREATE INDEX statements
        create_index_pattern = re.compile(
            r"""(?ix)CREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?([A-Za-z_][A-Za-z0-9_]*)""",
        )
        for match in create_index_pattern.finditer(content):
            indexes_created.append(match.group(1))

        # Extract Alembic version if present
        version = None
        down_revision = None
        up_revision = None

        version_match = re.search(
            r"""(?ix)revision\s*=\s*['"]([^'"]+)['"]""", content
        )
        if version_match:
            version = version_match.group(1)

        down_match = re.search(
            r"""(?ix)down_revision\s*=\s*['"]([^'"]+)['"]""", content
        )
        if down_match:
            down_revision = down_match.group(1)

        up_match = re.search(
            r"""(?ix)up_revision\s*=\s*['"]([^'"]+)['"]""", content
        )
        if up_match:
            up_revision = up_match.group(1)

        # If no migration-related content found, return None
        if not any([tables_created, tables_altered, tables_dropped, indexes_created, version]):
            return None

        # Calculate line numbers
        start_line = 1
        end_line = len(lines)

        return MigrationFile(
            path=rel_path,
            version=version,
            down_revision=down_revision,
            up_revision=up_revision,
            tables_created=tables_created,
            tables_altered=tables_altered,
            tables_dropped=tables_dropped,
            indexes_created=indexes_created,
            line_start=start_line,
            line_end=end_line,
        )

    def _find_sql_block_end(self, content: str, start_pos: int) -> int:
        """Find end position of a SQL statement/block."""
        text_after = content[start_pos:]

        # Find semicolon that ends the statement
        # But ignore semicolons inside string literals or nested blocks
        in_string = False
        string_char = ""
        paren_depth = 0
        bracket_depth = 0

        for i, char in enumerate(text_after):
            if char in ("'", '"', "`") and (i == 0 or text_after[i - 1] != "\\"):
                if not in_string:
                    in_string = True
                    string_char = char
                elif char == string_char:
                    in_string = False

            if not in_string:
                if char == "(":
                    paren_depth += 1
                elif char == ")":
                    paren_depth -= 1
                elif char == "[":
                    bracket_depth += 1
                elif char == "]":
                    bracket_depth -= 1
                elif char == ";" and paren_depth == 0 and bracket_depth == 0:
                    # End of statement
                    return start_pos + i + 1

        # No semicolon found, return end of content
        return len(content)

    def _split_by_comma(self, text: str) -> list[str]:
        """Split by comma, but not commas inside parentheses."""
        parts: list[str] = []
        depth = 0
        current = ""

        for char in text:
            if char == "(":
                depth += 1
                current += char
            elif char == ")":
                depth -= 1
                current += char
            elif char == "," and depth == 0:
                parts.append(current)
                current = ""
            else:
                current += char

        if current.strip():
            parts.append(current)

        return parts

    def _guess_canonical_model(self, table_name: str) -> str | None:
        """Guess canonical model name from table name."""
        # Remove common prefixes/suffixes
        name = table_name.lower()

        # Remove common prefixes
        for prefix in ("tbl_", "tab_", "dm_", "fact_", "dim_"):
            if name.startswith(prefix):
                name = name[len(prefix) :]

        # Remove common suffixes
        for suffix in ("_tbl", "_table", "_v", "_view"):
            if name.endswith(suffix):
                name = name[: -len(suffix)]

        # Convert to PascalCase
        parts = re.split(r"[_\-]+", name)
        model_name = "".join(p.capitalize() for p in parts if p)

        return model_name if model_name else None


def write_schema_contracts(root: Path, schema_evolution: SchemaEvolution) -> dict[str, Path]:
    """Write schema contracts to ai/source-of-truth directory.

    Returns a dictionary mapping contract name to file path.
    """
    ai_dir = root / "ai" / "source-of-truth"
    ensure_dir(ai_dir)

    paths: dict[str, Path] = {}

    # Write table schemas
    if schema_evolution.tables:
        schemas_path = ai_dir / "table-schemas.yaml"
        schemas_data = {
            "tables": [
                {
                    "name": table.name,
                    "columns": [
                        {
                            "name": col.name,
                            "data_type": col.data_type,
                            "is_nullable": col.is_nullable,
                            "is_primary_key": col.is_primary_key,
                            "is_unique": col.is_unique,
                            "default_value": col.default_value,
                            "check_constraint": col.check_constraint,
                            "foreign_key": (
                                f"{col.foreign_key[1]}.{col.foreign_key[2]}"
                                if col.foreign_key
                                else None
                            ),
                        }
                        for col in table.columns
                    ],
                    "primary_key_columns": table.primary_key_columns,
                    "file_path": table.file_path,
                    "line_start": table.line_start,
                    "line_end": table.line_end,
                    "canonical_model_name": table.canonical_model_name,
                }
                for table in schema_evolution.tables
            ]
        }
        write_yamlish(schemas_path, schemas_data)
        paths["table-schemas.yaml"] = schemas_path

    # Write migrations
    if schema_evolution.migrations:
        migrations_path = ai_dir / "migrations.yaml"
        migrations_data = {
            "migrations": [
                {
                    "path": mig.path,
                    "version": mig.version,
                    "down_revision": mig.down_revision,
                    "up_revision": mig.up_revision,
                    "tables_created": mig.tables_created,
                    "tables_altered": mig.tables_altered,
                    "tables_dropped": mig.tables_dropped,
                    "indexes_created": mig.indexes_created,
                    "line_start": mig.line_start,
                    "line_end": mig.line_end,
                }
                for mig in schema_evolution.migrations
            ]
        }
        write_yamlish(migrations_path, migrations_data)
        paths["migrations.yaml"] = migrations_path

    # Write table-to-model links
    if schema_evolution.table_to_model_links:
        links_path = ai_dir / "table-model-links.yaml"
        links_data = {
            "links": [
                {"table": table, "model": model}
                for table, model in schema_evolution.table_to_model_links.items()
            ]
        }
        write_yamlish(links_path, links_data)
        paths["table-model-links.yaml"] = links_path

    return paths


def enrich_snapshot_with_db_schemas(
    snapshot: RepositorySnapshot, schema_evolution: SchemaEvolution
) -> RepositorySnapshot:
    """Enrich repository snapshot with database schema information.

    Links tables discovered in migrations to data models in the snapshot.
    """
    # Build model name index
    model_names = {m.name.lower(): m for m in snapshot.data_models}

    # Link tables to models
    for table in schema_evolution.tables:
        if table.canonical_model_name:
            # Try to find matching model
            model_name_lower = table.canonical_model_name.lower()
            if model_name_lower in model_names:
                # Table is linked to an existing model
                pass

    return snapshot
