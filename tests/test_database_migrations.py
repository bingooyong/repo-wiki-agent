"""Tests for database migration and table extractor (Task 26.2)."""

from __future__ import annotations

from pathlib import Path

from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.scanner.database_migrations import (
    DatabaseMigrationExtractor,
    MigrationFile,
    SchemaEvolution,
    TableColumn,
    TableSchema,
    enrich_snapshot_with_db_schemas,
    write_schema_contracts,
)
from repo_wiki.scanner.repository_scanner import RepositoryScanner


class TestDatabaseMigrationExtractor:
    """Tests for DatabaseMigrationExtractor."""

    def test_extract_simple_create_table(self, tmp_path: Path) -> None:
        """Test extraction of a simple CREATE TABLE statement."""
        # Create a migration file
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir(parents=True)
        (migrations_dir / "001_initial.sql").write_text(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username VARCHAR(50) NOT NULL UNIQUE,
                email VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """.strip(),
            encoding="utf-8",
        )

        extractor = DatabaseMigrationExtractor(tmp_path)
        schema_evolution = extractor.extract()

        assert len(schema_evolution.tables) == 1
        table = schema_evolution.tables[0]
        assert table.name == "users"
        assert len(table.columns) == 4

        # Check column details
        col_names = {col.name for col in table.columns}
        assert col_names == {"id", "username", "email", "created_at"}

        # Check primary key
        assert table.primary_key_columns == ["id"]

        # Check nullable constraints
        username_col = next(col for col in table.columns if col.name == "username")
        assert not username_col.is_nullable
        assert username_col.is_unique

    def test_extract_multiple_tables(self, tmp_path: Path) -> None:
        """Test extraction of multiple tables from a single file."""
        (tmp_path / "schema.sql").write_text(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                name VARCHAR(100) NOT NULL
            );

            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                title VARCHAR(200) NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            """.strip(),
            encoding="utf-8",
        )

        extractor = DatabaseMigrationExtractor(tmp_path)
        schema_evolution = extractor.extract()

        assert len(schema_evolution.tables) == 2
        table_names = {t.name for t in schema_evolution.tables}
        assert table_names == {"users", "posts"}

        # Check foreign key on posts
        posts_table = next(t for t in schema_evolution.tables if t.name == "posts")
        user_id_col = next(col for col in posts_table.columns if col.name == "user_id")
        assert user_id_col.foreign_key == ("user_id", "users", "id")

    def test_extract_alembic_migration(self, tmp_path: Path) -> None:
        """Test extraction of Alembic migration metadata."""
        alembic_dir = tmp_path / "alembic" / "versions"
        alembic_dir.mkdir(parents=True)

        (alembic_dir / "001_initial.py").write_text(
            '''
            """initial schema

            Revision ID: 001
            Revises:
            Create Date: 2024-01-01 12:00:00.000000

            """
            from alembic import op
            import sqlalchemy as sa

            revision = '001'
            down_revision = None
            up_revision = '002'

            def upgrade():
                op.create_table(
                    'users',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('username', sa.String(length=50), nullable=False),
                    sa.PrimaryKeyConstraint('id')
                )

            def downgrade():
                op.drop_table('users')
            ''',
            encoding="utf-8",
        )

        extractor = DatabaseMigrationExtractor(tmp_path)
        schema_evolution = extractor.extract()

        # Should find migration file (migration metadata)
        # Note: Python-based SQLAlchemy migrations don't contain SQL CREATE TABLE
        # statements, so tables list will be empty. The migration metadata
        # (version, down_revision, up_revision) is still extracted.
        assert len(schema_evolution.migrations) >= 1
        migration = schema_evolution.migrations[0]
        assert migration.version == "001"
        assert migration.down_revision is None
        assert migration.up_revision == "002"

    def test_extract_table_with_indexes(self, tmp_path: Path) -> None:
        """Test extraction of CREATE INDEX statements."""
        (tmp_path / "schema.sql").write_text(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                email VARCHAR(255) NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_unique ON users(email);
            """.strip(),
            encoding="utf-8",
        )

        extractor = DatabaseMigrationExtractor(tmp_path)
        schema_evolution = extractor.extract()

        # Should have migration info with indexes
        migrations_with_indexes = [m for m in schema_evolution.migrations if m.indexes_created]
        assert len(migrations_with_indexes) >= 1

    def test_canonical_model_name_guessing(self, tmp_path: Path) -> None:
        """Test that canonical model names are guessed from table names."""
        (tmp_path / "schema.sql").write_text(
            """
            CREATE TABLE IF NOT EXISTS user_profiles (
                id INTEGER PRIMARY KEY,
                bio TEXT
            );

            CREATE TABLE IF NOT EXISTS dm_sales_facts (
                id INTEGER PRIMARY KEY
            );
            """.strip(),
            encoding="utf-8",
        )

        extractor = DatabaseMigrationExtractor(tmp_path)
        schema_evolution = extractor.extract()

        # Check model name guessing
        user_profiles = next(t for t in schema_evolution.tables if t.name == "user_profiles")
        assert user_profiles.canonical_model_name == "UserProfiles"

        dm_sales = next(t for t in schema_evolution.tables if t.name == "dm_sales_facts")
        assert dm_sales.canonical_model_name == "SalesFacts"

    def test_file_line_citations(self, tmp_path: Path) -> None:
        """Test that file and line citations are preserved."""
        (tmp_path / "schema.sql").write_text(
            """
            -- Line 2
            -- Line 3
            CREATE TABLE IF NOT EXISTS users (  -- Line 5
                id INTEGER PRIMARY KEY  -- Line 6
            );  -- Line 7
            """.strip(),
            encoding="utf-8",
        )

        extractor = DatabaseMigrationExtractor(tmp_path)
        schema_evolution = extractor.extract()

        assert len(schema_evolution.tables) == 1
        table = schema_evolution.tables[0]
        assert table.file_path == "schema.sql"
        assert table.line_start > 0
        assert table.line_end >= table.line_start

    def test_find_migration_files_by_pattern(self, tmp_path: Path) -> None:
        """Test that migration files are found by pattern."""
        # Create files with migration-related names
        migrations_dir = tmp_path / "db" / "migrations"
        migrations_dir.mkdir(parents=True)
        (migrations_dir / "001.sql").write_text(
            "CREATE TABLE users (id INTEGER PRIMARY KEY);",
            encoding="utf-8",
        )
        alembic_dir = tmp_path / "alembic" / "versions"
        alembic_dir.mkdir(parents=True)
        (alembic_dir / "002.py").write_text(
            "# migration file",
            encoding="utf-8",
        )
        src_dir = tmp_path / "src"
        src_dir.mkdir(parents=True)
        (src_dir / "schema.py").write_text(
            "# not a migration",
            encoding="utf-8",
        )

        extractor = DatabaseMigrationExtractor(tmp_path)
        migration_files = extractor._find_migration_files()

        # Should find SQL and alembic files but not schema.py
        paths = [str(p) for p, _ in migration_files]
        assert any("001.sql" in p for p in paths)
        assert any("002.py" in p for p in paths)
        assert not any("schema.py" in p for p in paths)

    def test_empty_repository(self, tmp_path: Path) -> None:
        """Test extraction from repository with no migration files."""
        src_dir = tmp_path / "src"
        src_dir.mkdir(parents=True)
        (src_dir / "main.py").write_text("print('hello')", encoding="utf-8")

        extractor = DatabaseMigrationExtractor(tmp_path)
        schema_evolution = extractor.extract()

        assert len(schema_evolution.tables) == 0
        assert len(schema_evolution.migrations) == 0


class TestWriteSchemaContracts:
    """Tests for write_schema_contracts function."""

    def test_write_table_schemas(self, tmp_path: Path) -> None:
        """Test writing table schemas to YAML."""
        schema_evolution = SchemaEvolution(
            tables=[
                TableSchema(
                    name="users",
                    columns=[
                        TableColumn(
                            name="id",
                            data_type="INTEGER",
                            is_nullable=False,
                            is_primary_key=True,
                        ),
                        TableColumn(
                            name="email",
                            data_type="VARCHAR(255)",
                            is_nullable=False,
                        ),
                    ],
                    primary_key_columns=["id"],
                    file_path="migrations/001.sql",
                    line_start=2,
                    line_end=5,
                )
            ]
        )

        paths = write_schema_contracts(tmp_path, schema_evolution)

        assert "table-schemas.yaml" in paths
        schema_file = tmp_path / "ai" / "source-of-truth" / "table-schemas.yaml"
        assert schema_file.exists()

        # Read and verify content
        import yaml

        with open(schema_file) as f:
            data = yaml.safe_load(f)

        assert len(data["tables"]) == 1
        assert data["tables"][0]["name"] == "users"
        assert len(data["tables"][0]["columns"]) == 2

    def test_write_migrations(self, tmp_path: Path) -> None:
        """Test writing migration metadata to YAML."""
        schema_evolution = SchemaEvolution(
            migrations=[
                MigrationFile(
                    path="alembic/versions/001.py",
                    version="001",
                    tables_created=["users"],
                    tables_altered=[],
                    tables_dropped=[],
                    indexes_created=["idx_users_email"],
                )
            ]
        )

        paths = write_schema_contracts(tmp_path, schema_evolution)

        assert "migrations.yaml" in paths
        migrations_file = tmp_path / "ai" / "source-of-truth" / "migrations.yaml"
        assert migrations_file.exists()

        import yaml

        with open(migrations_file) as f:
            data = yaml.safe_load(f)

        assert len(data["migrations"]) == 1
        assert data["migrations"][0]["version"] == "001"

    def test_write_table_model_links(self, tmp_path: Path) -> None:
        """Test writing table-to-model links to YAML."""
        schema_evolution = SchemaEvolution(table_to_model_links={"users": "User", "posts": "Post"})

        paths = write_schema_contracts(tmp_path, schema_evolution)

        assert "table-model-links.yaml" in paths
        links_file = tmp_path / "ai" / "source-of-truth" / "table-model-links.yaml"
        assert links_file.exists()

        import yaml

        with open(links_file) as f:
            data = yaml.safe_load(f)

        assert len(data["links"]) == 2


class TestIntegration:
    """Integration tests for database migration extraction."""

    def test_extract_and_enrich_snapshot(self, tmp_path: Path) -> None:
        """Test extraction and snapshot enrichment."""
        # Create a migration file
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir(parents=True)
        (migrations_dir / "001.sql").write_text(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username VARCHAR(50) NOT NULL
            );
            """.strip(),
            encoding="utf-8",
        )

        # Create a source file with a data model
        src_dir = tmp_path / "src"
        src_dir.mkdir(parents=True)
        (src_dir / "models.py").write_text(
            """
            class User:
                pass
            """.strip(),
            encoding="utf-8",
        )

        # Run scanner
        cfg = RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})
        scanner = RepositoryScanner(cfg)
        snapshot = scanner.scan()

        # Extract database schemas
        extractor = DatabaseMigrationExtractor(tmp_path)
        schema_evolution = extractor.extract()

        # Enrich snapshot
        enriched = enrich_snapshot_with_db_schemas(snapshot, schema_evolution)

        # Should have extracted the table
        assert len(schema_evolution.tables) == 1
        assert schema_evolution.tables[0].name == "users"
