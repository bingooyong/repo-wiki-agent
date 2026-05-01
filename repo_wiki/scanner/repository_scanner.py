from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path

from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.core.contracts import (
    DataModel,
    Endpoint,
    Module,
    RepositoryInfo,
    RepositorySnapshot,
    RepositoryStats,
)
from repo_wiki.core.security import (
    SecurityWarning,
    is_binary_bytes,
    is_binary_path,
    sanitize_text,
    should_scan,
)

try:
    from pathspec import PathSpec
except ImportError:  # pragma: no cover
    PathSpec = None


_CODE_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".java", ".kt"}
_MODEL_FILE_HINTS = ("model", "schema", "entity", "dto", "migration", "alembic")
_MODULE_ROOT_HINTS = {"src", "app", "apps", "services", "modules", "internal", "cmd"}
_HTTP_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD")

# Domain classification signals
_DOMAIN_SIGNALS: dict[str, tuple[frozenset[str], float]] = {
    # Core platform domains
    "core-platform": (
        frozenset({"repo_wiki", "core", "shared", "common", "base", "foundation"}),
        0.8,
    ),
    # AI/ML services
    "ai-services": (
        frozenset({"ai", "ml", "model", "embedding", "vector", "indexer", "retrieval", "graph"}),
        0.9,
    ),
    # API and HTTP handling
    "api-gateway": (
        frozenset({"api", "gateway", "router", "endpoint", "route", "handler"}),
        0.7,
    ),
    # Data pipeline and processing
    "data-pipeline": (
        frozenset({"pipeline", "worker", "queue", "task", "job", "batch", "stream"}),
        0.7,
    ),
    # Frontend/UI
    "frontend": (
        frozenset({"ui", "web", "client", "view", "component", "pages", "static"}),
        0.7,
    ),
    # Storage and persistence
    "persistence": (
        frozenset({"db", "storage", "migration", "repository", "dal", "dao"}),
        0.7,
    ),
    # Tooling and scripts
    "tooling": (
        frozenset({"scripts", "tools", "cli", "cmd", "bin", "script"}),
        0.9,
    ),
    # Testing
    "testing": (
        frozenset({"test", "spec", "mock", "fixture", "e2e", "integration"}),
        0.9,
    ),
    # Operations/DevOps
    "operations": (
        frozenset({"deploy", "ops", "monitoring", "logging", "config", "ci", "cd"}),
        0.6,
    ),
}

_SERVICE_FAMILY_SIGNALS: dict[str, tuple[frozenset[str], float]] = {
    "python-backend": (frozenset({"python", ".py", "pyproject", "poetry", "requirements"}), 0.8),
    "typescript-frontend": (frozenset({".ts", ".tsx", ".jsx", "package.json", "tsconfig"}), 0.8),
    "golang-service": (frozenset({".go", "go.mod", "go.sum"}), 0.9),
    "jvm-service": (frozenset({".java", ".kt", "pom.xml", "build.gradle"}), 0.8),
}

_RUNTIME_ROLE_SIGNALS: dict[str, tuple[frozenset[str], float]] = {
    "api-server": (frozenset({"router", "endpoint", "handler", "get", "post", "put", "delete", "patch"}), 0.7),
    "worker": (frozenset({"worker", "job", "task", "queue", "background", "async"}), 0.7),
    "data-pipeline": (frozenset({"pipeline", "stream", "batch", "etl", "transform"}), 0.7),
    "data-store": (frozenset({"db", "storage", "cache", "repository", "dal", "dao"}), 0.7),
    "tooling": (frozenset({"script", "cli", "cmd", "bin", "main"}), 0.8),
    "test-harness": (frozenset({"test", "spec", "fixture", "mock", "assert"}), 0.8),
}


@dataclass
class ScannedFile:
    path: Path
    text: str


class RepositoryScanner:
    def __init__(self, config: RepoWikiConfig) -> None:
        self.config = config
        self.root = Path(config.project.root).resolve()
        self._gitignore = self._load_gitignore()
        self.last_security_warnings: list[SecurityWarning] = []

    def scan(self) -> RepositorySnapshot:
        scanned_files, stats = self._collect_files()
        commands = self._extract_commands(scanned_files)
        repository = self._build_repository_info(scanned_files, commands)

        modules = self._discover_modules(scanned_files)
        endpoints = self._extract_endpoints(scanned_files, modules)
        data_models = self._extract_data_models(scanned_files, modules)
        self._ensure_modules_cover_entities(modules, endpoints, data_models)
        self._enrich_modules(modules, endpoints, data_models, scanned_files)
        self._enrich_endpoints(endpoints, modules, scanned_files)

        stats.module_count = len(modules)
        stats.endpoint_count = len(endpoints)
        stats.data_model_count = len(data_models)

        return RepositorySnapshot(
            repository=repository,
            modules=sorted(modules.values(), key=lambda m: m.path),
            endpoints=sorted(endpoints, key=lambda e: (e.module, e.path, e.method)),
            data_models=sorted(data_models, key=lambda m: (m.module, m.name)),
            commands=commands,
            stats=stats,
        )

    def _collect_files(self) -> tuple[list[ScannedFile], RepositoryStats]:
        scanned: list[ScannedFile] = []
        skipped = 0
        total = 0
        max_bytes = self.config.security.max_file_size_kb * 1024
        for dirpath, dirnames, filenames in os.walk(self.root, followlinks=self.config.scan.follow_symlinks):
            current_dir = Path(dirpath)
            try:
                current_rel = current_dir.relative_to(self.root)
            except ValueError:
                continue

            dirnames[:] = [
                dirname
                for dirname in sorted(dirnames)
                if not self._is_directory_pruned(current_rel / dirname)
            ]

            for filename in sorted(filenames):
                path = current_dir / filename
                if not path.is_file():
                    continue
                total += 1
                rel = path.relative_to(self.root)
                if self._is_gitignored(rel):
                    skipped += 1
                    continue
                if self._is_config_excluded(rel):
                    skipped += 1
                    continue
                if not should_scan(path, self.config, root=self.root):
                    skipped += 1
                    continue
                if path.stat().st_size > max_bytes:
                    skipped += 1
                    continue
                if self.config.security.skip_binary_files and is_binary_path(path):
                    skipped += 1
                    continue
                raw = path.read_bytes()
                if self.config.security.skip_binary_files and is_binary_bytes(raw):
                    skipped += 1
                    continue
                text = raw.decode("utf-8", errors="ignore")
                sanitized, warnings = sanitize_text(text, path=rel.as_posix())
                self.last_security_warnings.extend(warnings)
                scanned.append(ScannedFile(path=rel, text=sanitized))
                if len(scanned) >= self.config.scan.max_file_count:
                    stats = RepositoryStats(total_files=total, scanned_files=len(scanned), skipped_files=skipped)
                    return scanned, stats
        stats = RepositoryStats(total_files=total, scanned_files=len(scanned), skipped_files=skipped)
        return scanned, stats

    def _is_directory_pruned(self, rel_path: Path) -> bool:
        rel = rel_path.as_posix()
        if rel in {"", "."}:
            return False

        generated_dirs = {
            ".qoder",
            ".repo-agent-eval",
            ".repo-wiki",
            ".git",
            "node_modules",
            "target",
            "build",
            "dist",
            ".venv",
            ".artifact-venv",
            ".m2-temp",
            ".pytest_cache",
            ".ruff_cache",
            ".playwright-mcp",
            "playwright-report",
            "test-results",
            "result",
            "output",
            "logs",
            "log",
            "venv",
        }
        if any(part in generated_dirs for part in rel_path.parts):
            return True
        for directory in set(self.config.scan.exclude_dirs) | set(self.config.security.deny_dirs) | generated_dirs:
            normalized = directory.strip("/")
            if normalized and normalized in rel_path.parts:
                return True
            if rel == normalized or rel.startswith(f"{normalized}/"):
                return True

        for pattern in self.config.project.exclude:
            normalized = pattern.strip("/")
            if normalized.endswith("/**"):
                prefix = normalized[:-3]
                if rel == prefix or rel.startswith(f"{prefix}/"):
                    return True
            if fnmatch(rel, normalized):
                return True
        return False

    def _load_gitignore(self):
        if PathSpec is None:
            return None
        gitignore_path = self.root / ".gitignore"
        if not gitignore_path.exists():
            return None
        patterns = gitignore_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        return PathSpec.from_lines("gitwildmatch", patterns)

    def _is_gitignored(self, rel_path: Path) -> bool:
        if self._gitignore is None:
            return False
        return self._gitignore.match_file(rel_path.as_posix())

    def _is_config_excluded(self, rel_path: Path) -> bool:
        rel = rel_path.as_posix()
        for exclude_dir in self.config.scan.exclude_dirs:
            normalized = exclude_dir.strip("/")
            if rel == normalized or rel.startswith(f"{normalized}/"):
                return True
        return any(fnmatch(rel, pattern) for pattern in self.config.project.exclude)

    def _build_repository_info(
        self,
        scanned_files: list[ScannedFile],
        commands: dict[str, str],
    ) -> RepositoryInfo:
        name = self.config.project.name
        if name == "auto":
            name = self.root.name
        language = self._detect_language(scanned_files)
        framework = self._detect_framework(scanned_files)
        package_manager = self._detect_package_manager()
        entry_points = self._detect_entry_points(scanned_files, commands)
        key_directories = sorted(
            {
                path.parts[0]
                for path in (f.path for f in scanned_files)
                if len(path.parts) > 1 and not path.parts[0].startswith(".")
            }
        )
        return RepositoryInfo(
            name=name,
            root_path=str(self.root),
            language=language,
            framework=framework,
            package_manager=package_manager,
            entry_points=entry_points,
            key_directories=key_directories,
        )

    def _detect_language(self, files: list[ScannedFile]) -> str:
        counters = {"python": 0, "typescript": 0, "javascript": 0, "go": 0}
        for file in files:
            suffix = file.path.suffix.lower()
            if suffix == ".py":
                counters["python"] += 1
            elif suffix in {".ts", ".tsx"}:
                counters["typescript"] += 1
            elif suffix in {".js", ".jsx"}:
                counters["javascript"] += 1
            elif suffix == ".go":
                counters["go"] += 1
        language, count = max(counters.items(), key=lambda item: item[1])
        return language if count > 0 else "unknown"

    def _detect_framework(self, files: list[ScannedFile]) -> str:
        content = "\n".join(f.text for f in files if f.path.name in {"package.json", "pyproject.toml", "requirements.txt", "go.mod"})
        framework_signals = {
            "nestjs": ("@nestjs",),
            "express": ("express",),
            "fastify": ("fastify",),
            "fastapi": ("fastapi",),
            "flask": ("flask",),
            "gin": ("gin-gonic/gin",),
            "fiber": ("gofiber/fiber",),
        }
        for framework, hints in framework_signals.items():
            if any(hint in content.lower() for hint in hints):
                return framework
        return "unknown"

    def _detect_package_manager(self) -> str:
        checks = {
            "pnpm": "pnpm-lock.yaml",
            "yarn": "yarn.lock",
            "npm": "package-lock.json",
            "poetry": "poetry.lock",
            "pip": "requirements.txt",
            "go": "go.sum",
        }
        for manager, marker in checks.items():
            if (self.root / marker).exists():
                return manager
        return "unknown"

    def _extract_commands(self, files: list[ScannedFile]) -> dict[str, str]:
        commands = {key: "" for key in ("start", "build", "test", "lint")}
        package_json = next((f for f in files if f.path.name == "package.json"), None)
        if package_json:
            try:
                data = json.loads(package_json.text)
                scripts = data.get("scripts", {})
                for key in commands:
                    if key in scripts:
                        commands[key] = f"npm run {key}"
            except json.JSONDecodeError:
                pass

        makefile = next((f for f in files if f.path.name.lower() == "makefile"), None)
        if makefile:
            for line in makefile.text.splitlines():
                stripped = line.strip()
                for key in commands:
                    if stripped.startswith(f"{key}:") and not commands[key]:
                        commands[key] = f"make {key}"

        language = self._detect_language(files)
        fallback = {
            "python": {"start": "python -m app", "test": "pytest -q", "lint": "ruff check ."},
            "typescript": {"start": "npm run start", "build": "npm run build", "test": "npm run test", "lint": "npm run lint"},
            "javascript": {"start": "npm run start", "build": "npm run build", "test": "npm run test", "lint": "npm run lint"},
            "go": {"start": "go run ./cmd/...", "build": "go build ./...", "test": "go test ./...", "lint": "golangci-lint run"},
        }.get(language, {})
        for key, value in fallback.items():
            if not commands[key]:
                commands[key] = value
        return commands

    def _detect_entry_points(self, files: list[ScannedFile], commands: dict[str, str]) -> list[str]:
        entries: set[str] = set()
        if commands.get("start"):
            entries.add(commands["start"])
        for file in files:
            if file.path.name in {"main.py", "app.py", "server.py", "main.go"}:
                entries.add(file.path.as_posix())
            if len(file.path.parts) >= 3 and file.path.parts[0] == "cmd" and file.path.name == "main.go":
                entries.add(file.path.parent.as_posix())
        return sorted(entries)

    def _discover_modules(self, files: list[ScannedFile]) -> dict[str, Module]:
        modules: dict[str, Module] = {}
        for file in files:
            if file.path.suffix.lower() not in _CODE_SUFFIXES:
                continue
            module_path = self._choose_module_path(file.path)
            if module_path not in modules:
                name = module_path.split("/")[-1] if module_path != "." else self.root.name
                modules[module_path] = Module(
                    name=name,
                    path=module_path,
                    responsibility="",
                    exports=[],
                    depends_on=[],
                    depended_by=[],
                    interfaces=[],
                    data_models=[],
                    owner="unknown",
                    doc_path=f"docs/modules/{module_path.replace('/', '-')}.md" if module_path != "." else "docs/modules/root.md",
                )

            export_names = self._extract_exports(file)
            if export_names:
                existing = set(modules[module_path].exports)
                modules[module_path].exports = sorted(existing | set(export_names))
        return modules

    def _choose_module_path(self, rel_path: Path) -> str:
        parts = rel_path.parts
        if not parts:
            return "."
        if parts[0] in _MODULE_ROOT_HINTS and len(parts) > 1:
            return Path(parts[0], parts[1]).as_posix()
        return parts[0]

    def _extract_exports(self, file: ScannedFile) -> list[str]:
        suffix = file.path.suffix.lower()
        exports: set[str] = set()
        if suffix == ".py":
            exports.update(re.findall(r"^\s*def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", file.text, re.MULTILINE))
            exports.update(re.findall(r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)\s*[:(]", file.text, re.MULTILINE))
        elif suffix in {".ts", ".tsx", ".js", ".jsx"}:
            exports.update(re.findall(r"\bexport\s+(?:class|function|const|let|var|type|interface)\s+([A-Za-z_][A-Za-z0-9_]*)", file.text))
        elif suffix == ".go":
            exports.update(re.findall(r"^\s*func\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", file.text, re.MULTILINE))
        elif suffix in {".java", ".kt"}:
            exports.update(re.findall(r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)", file.text))
            exports.update(re.findall(r"\binterface\s+([A-Za-z_][A-Za-z0-9_]*)", file.text))
        return sorted(exports)

    def _extract_endpoints(self, files: list[ScannedFile], modules: dict[str, Module]) -> list[Endpoint]:
        endpoints: list[Endpoint] = []
        for file in files:
            suffix = file.path.suffix.lower()
            if suffix not in _CODE_SUFFIXES:
                continue
            module_path = self._choose_module_path(file.path)
            module_name = modules[module_path].name
            text = file.text

            for method, path_expr, handler in re.findall(
                r"\b(?:router|app|server|r)\.(get|post|put|patch|delete|options|head)\(\s*[\"']([^\"']+)[\"']\s*,\s*([A-Za-z_][A-Za-z0-9_]*)",
                text,
                re.IGNORECASE,
            ):
                endpoints.append(
                    Endpoint(
                        method=method.upper(),
                        path=path_expr,
                        module=module_name,
                        handler=handler,
                        file_path=file.path.as_posix(),
                    )
                )

            for decorator, path_expr in re.findall(r"@(Get|Post|Put|Patch|Delete|Options|Head)\(\s*[\"']?([^\"')]+)[\"']?\)", text):
                endpoints.append(
                    Endpoint(
                        method=decorator.upper(),
                        path=path_expr,
                        module=module_name,
                        handler=self._guess_handler(text),
                        file_path=file.path.as_posix(),
                    )
                )

            for method, path_expr in re.findall(r"@(?:app|router|bp)\.(get|post|put|patch|delete|options|head)\(\s*[\"']([^\"']+)[\"']", text, re.IGNORECASE):
                endpoints.append(
                    Endpoint(
                        method=method.upper(),
                        path=path_expr,
                        module=module_name,
                        handler=self._guess_handler(text),
                        file_path=file.path.as_posix(),
                    )
                )

            for path_expr, handler in re.findall(r"http\.HandleFunc\(\s*[\"']([^\"']+)[\"']\s*,\s*([A-Za-z_][A-Za-z0-9_]*)", text):
                endpoints.append(
                    Endpoint(
                        method="GET",
                        path=path_expr,
                        module=module_name,
                        handler=handler,
                        file_path=file.path.as_posix(),
                    )
                )

            for method, path_expr, handler in re.findall(
                r"\b(?:r|router|app)\.(GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD)\(\s*[\"']([^\"']+)[\"']\s*,\s*([A-Za-z_][A-Za-z0-9_]*)",
                text,
            ):
                endpoints.append(
                    Endpoint(
                        method=method.upper(),
                        path=path_expr,
                        module=module_name,
                        handler=handler,
                        file_path=file.path.as_posix(),
                    )
                )

            # Flask-style @app.route("/path", methods=["GET"])
            for path_expr, methods in re.findall(
                r"@app\.route\s*\(\s*[\"']([^\"']+)[\"']\s*,\s*methods\s*=\s*\[([^\]]+)\]\s*\)",
                text,
                re.IGNORECASE,
            ):
                for method in re.findall(r"['\"](\w+)['\"]", methods):
                    if method.upper() in _HTTP_METHODS:
                        endpoints.append(
                            Endpoint(
                                method=method.upper(),
                                path=path_expr,
                                module=module_name,
                                handler=self._guess_handler(text),
                                file_path=file.path.as_posix(),
                            )
                        )

            # Flask-style @app.route("/path") without methods (default GET)
            for path_expr in re.findall(
                r"@app\.route\s*\(\s*[\"']([^\"']+)[\"']\s*\)",
                text,
            ):
                endpoints.append(
                    Endpoint(
                        method="GET",
                        path=path_expr,
                        module=module_name,
                        handler=self._guess_handler(text),
                        file_path=file.path.as_posix(),
                    )
                )

        dedup: dict[tuple[str, str, str, str], Endpoint] = {}
        for endpoint in endpoints:
            if endpoint.method in _HTTP_METHODS:
                key = (endpoint.method, endpoint.path, endpoint.module, endpoint.file_path)
                dedup[key] = endpoint
        return list(dedup.values())

    def _guess_handler(self, text: str) -> str:
        match = re.search(r"def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", text)
        if match:
            return match.group(1)
        match = re.search(r"function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", text)
        if match:
            return match.group(1)
        return "handler"

    def _extract_data_models(self, files: list[ScannedFile], modules: dict[str, Module]) -> list[DataModel]:
        models: list[DataModel] = []
        for file in files:
            suffix = file.path.suffix.lower()
            module_path = self._choose_module_path(file.path)
            if modules and module_path in modules:
                module_name = modules[module_path].name
            else:
                module_name = file.path.parts[0] if file.path.parts else self.root.name
            path_str = file.path.as_posix()
            lower_path = path_str.lower()
            if suffix == ".py":
                for name, base in re.findall(r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)\(([^)]+)\)\s*:", file.text, re.MULTILINE):
                    if any(key in base for key in ("BaseModel", "Model", "SQLModel")) or any(h in lower_path for h in _MODEL_FILE_HINTS):
                        models.append(DataModel(name=name, type="python_class", module=module_name, file_path=path_str))
            elif suffix in {".ts", ".tsx", ".js", ".jsx"}:
                for name in re.findall(
                    r"\b(?:interface|type|class)\s+([A-Za-z_][A-Za-z0-9_]*(?:DTO|Schema|Model|Entity)?)",
                    file.text,
                ):
                    if (
                        name.lower().endswith(("dto", "schema", "model", "entity"))
                        or any(h in lower_path for h in _MODEL_FILE_HINTS)
                    ):
                        models.append(DataModel(name=name, type="ts_definition", module=module_name, file_path=path_str))
            elif suffix == ".go":
                for name in re.findall(r"^\s*type\s+([A-Za-z_][A-Za-z0-9_]*)\s+struct\b", file.text, re.MULTILINE):
                    if any(h in lower_path for h in _MODEL_FILE_HINTS):
                        models.append(DataModel(name=name, type="go_struct", module=module_name, file_path=path_str))
            elif suffix in {".java", ".kt"}:
                for name in re.findall(r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)", file.text):
                    if any(h in lower_path for h in _MODEL_FILE_HINTS) or name.lower().endswith(("dto", "entity", "model")):
                        models.append(DataModel(name=name, type="jvm_class", module=module_name, file_path=path_str))

            if "migration" in lower_path or "alembic" in lower_path:
                for table in re.findall(r"(?i)create\s+table\s+(?:if\s+not\s+exists\s+)?([A-Za-z_][A-Za-z0-9_]*)", file.text):
                    models.append(DataModel(name=table, type="migration_table", module=module_name, file_path=path_str))

        dedup: dict[tuple[str, str, str], DataModel] = {}
        for model in models:
            dedup[(model.name, model.module, model.file_path)] = model
        return list(dedup.values())

    def _ensure_modules_cover_entities(
        self,
        modules: dict[str, Module],
        endpoints: list[Endpoint],
        data_models: list[DataModel],
    ) -> None:
        by_name = {module.name: module for module in modules.values()}
        referenced = {endpoint.module for endpoint in endpoints} | {model.module for model in data_models}
        for module_name in sorted(x for x in referenced if x and x not in by_name):
            path = module_name
            modules[path] = Module(
                name=module_name,
                path=path,
                responsibility="",
                exports=[],
                depends_on=[],
                depended_by=[],
                interfaces=[],
                data_models=[],
                owner="unknown",
                doc_path=f"docs/modules/{module_name.replace('/', '-')}.md",
            )

    def _extract_dependencies(self, files: list[ScannedFile], modules: dict[str, Module]) -> dict[str, set[str]]:
        deps: dict[str, set[str]] = {module.path: set() for module in modules.values()}
        known_paths = list(modules.keys())
        for file in files:
            module_path = self._choose_module_path(file.path)
            if module_path not in deps:
                continue
            text = file.text
            candidates = set(re.findall(r"^\s*from\s+([A-Za-z0-9_./]+)\s+import\b", text, re.MULTILINE))
            candidates.update(re.findall(r"^\s*import\s+([A-Za-z0-9_./]+)", text, re.MULTILINE))
            candidates.update(re.findall(r"from\s+[\"']([^\"']+)[\"']", text))
            candidates.update(re.findall(r"import\s+[\"']([^\"']+)[\"']", text))
            candidates.update(re.findall(r"^\s*import\s+[\"']([^\"']+)[\"']", text, re.MULTILINE))
            for candidate in candidates:
                normalized = candidate.strip("./").replace(".", "/")
                for known in known_paths:
                    if known == module_path:
                        continue
                    if normalized.startswith(known) or known.endswith(normalized):
                        deps[module_path].add(modules[known].name)
        return deps

    def _extract_codeowners(self) -> list[tuple[str, str]]:
        codeowners_path = self.root / "CODEOWNERS"
        if not codeowners_path.exists():
            return []
        mappings: list[tuple[str, str]] = []
        for line in codeowners_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            parts = stripped.split()
            if len(parts) >= 2:
                path_pattern = parts[0].lstrip("/")
                owner = parts[1]
                mappings.append((path_pattern, owner))
        return mappings

    def _owner_for_module(self, module_path: str, mappings: list[tuple[str, str]]) -> str:
        for pattern, owner in mappings:
            normalized_pattern = pattern.rstrip("*").rstrip("/")
            if not normalized_pattern:
                continue
            if module_path.startswith(normalized_pattern):
                return owner
        return "unknown"

    def _responsibility_for_module(
        self,
        module: Module,
        endpoints: list[Endpoint],
        data_models: list[DataModel],
    ) -> str:
        endpoint_paths = [e.path for e in endpoints if e.module == module.name][:2]
        model_names = [m.name for m in data_models if m.module == module.name][:2]
        signals: list[str] = []
        if endpoint_paths:
            signals.append("API routes " + ", ".join(endpoint_paths))
        if model_names:
            signals.append("models " + ", ".join(model_names))
        if module.exports:
            signals.append("exports " + ", ".join(module.exports[:2]))
        if not signals:
            signals.append(f"core logic under {module.path}")
        return f"Handles {signals[0]}."

    def _enrich_modules(
        self,
        modules: dict[str, Module],
        endpoints: list[Endpoint],
        data_models: list[DataModel],
        files: list[ScannedFile],
    ) -> None:
        deps_map = self._extract_dependencies(files, modules)
        reverse_map: dict[str, set[str]] = {m.name: set() for m in modules.values()}
        for path, module in modules.items():
            module.depends_on = sorted(deps_map.get(path, set()))
            for dep in module.depends_on:
                reverse_map.setdefault(dep, set()).add(module.name)
            module.interfaces = sorted(
                {f"{endpoint.method} {endpoint.path}" for endpoint in endpoints if endpoint.module == module.name}
            )
            module.data_models = sorted({model.name for model in data_models if model.module == module.name})

        for module in modules.values():
            module.depended_by = sorted(reverse_map.get(module.name, set()))

        owners = self._extract_codeowners()
        for path, module in modules.items():
            module.owner = self._owner_for_module(path, owners)
            module.responsibility = self._responsibility_for_module(module, endpoints, data_models)

        # Classify modules into business domains
        self._classify_module_domains(list(modules.values()), files)

    def _classify_module_domains(self, modules: list[Module], files: list[ScannedFile]) -> None:
        """Classify each module into business domain, service family, and runtime role.

        This method uses deterministic heuristics based on module path, exports,
        interfaces, data models, and file content signals. When signals are weak,
        it falls back to stable default classifications.

        The classification is additive - it does NOT overwrite existing module
        attributes, only adds domain classification metadata.
        """
        # Build file content index for modules
        module_files: dict[str, list[str]] = {}
        module_extensions: dict[str, list[str]] = {}
        for f in files:
            module_path = self._choose_module_path(f.path)
            if module_path not in module_files:
                module_files[module_path] = []
                module_extensions[module_path] = []
            module_files[module_path].append(f.text)
            # Track file extensions for language detection
            ext = f.path.suffix.lower()
            if ext:
                module_extensions[module_path].append(ext)

        for module in modules:
            # Gather all signals for this module
            path_lower = module.path.lower()
            exports_lower = " ".join(e.lower() for e in module.exports)
            interfaces_lower = " ".join(i.lower() for i in module.interfaces)
            data_models_lower = " ".join(d.lower() for d in module.data_models)
            file_contents = " ".join(module_files.get(module.path, []))[:5000]  # Limit content size
            extensions = " ".join(module_extensions.get(module.path, []))

            # Combine all signals
            all_signals = f"{path_lower} {exports_lower} {interfaces_lower} {data_models_lower} {file_contents} {extensions}"

            # Classify domain
            domain, domain_confidence, domain_reason = self._score_classification(
                all_signals, _DOMAIN_SIGNALS, "path and content"
            )
            module.domain = domain
            module.domain_confidence = domain_confidence
            module.domain_classification_reason = domain_reason

            # Classify service family based on language/framework
            service_family, sf_confidence, sf_reason = self._score_service_family(
                all_signals, module.path, module.exports
            )
            module.service_family = service_family

            # Classify runtime role
            runtime_role, rr_confidence, rr_reason = self._score_runtime_role(
                all_signals, module.interfaces, module.data_models
            )
            module.runtime_role = runtime_role

    def _score_classification(
        self, signals: str, classification_map: dict[str, tuple[frozenset[str], float]], context: str
    ) -> tuple[str, float, str]:
        """Score and return the best classification match with confidence and reason."""
        best_match = "unknown"
        best_score = 0.0
        best_reason = "No signals found, using fallback."

        for classification, (keywords, base_confidence) in classification_map.items():
            score = sum(1 for keyword in keywords if keyword.lower() in signals.lower())
            if score > 0:
                adjusted_score = min(score * base_confidence, 1.0)
                if adjusted_score > best_score:
                    best_score = adjusted_score
                    best_match = classification
                    matched_keywords = [k for k in keywords if k.lower() in signals.lower()]
                    best_reason = f"Matched {len(matched_keywords)} keywords ({', '.join(matched_keywords[:3])}) with confidence {adjusted_score:.2f}"

        if best_score == 0.0:
            # Fallback to unknown with low confidence
            return "unknown", 0.1, "No classification signals found, using fallback."

        return best_match, best_score, best_reason

    def _score_service_family(
        self, signals: str, module_path: str, exports: list[str]
    ) -> tuple[str, float, str]:
        """Classify service family based on language and framework signals."""
        # Check path hints first
        path_lower = module_path.lower()
        signals_lower = signals.lower()

        # Python detection - check for .py files or path hints
        if "python" in path_lower or ".py" in signals_lower:
            matched = [k for k in _SERVICE_FAMILY_SIGNALS["python-backend"][0] if k.lower() in signals_lower]
            if matched:
                return "python-backend", 0.8, f"Python signals: {', '.join(matched[:2])}"
            # Even if no keywords matched, .py is a strong signal
            if ".py" in signals_lower:
                return "python-backend", 0.7, "Python file extension detected"
        # TypeScript detection
        elif ".ts" in signals_lower or ".tsx" in signals_lower or "typescript" in path_lower:
            matched = [k for k in _SERVICE_FAMILY_SIGNALS["typescript-frontend"][0] if k.lower() in signals_lower]
            if matched:
                return "typescript-frontend", 0.8, f"TypeScript signals: {', '.join(matched[:2])}"
            if ".ts" in signals_lower or ".tsx" in signals_lower:
                return "typescript-frontend", 0.7, "TypeScript file extension detected"
        # Go detection
        elif ".go" in signals_lower or "golang" in path_lower:
            return "golang-service", 0.9, "Go source files detected"
        # JVM detection
        elif ".java" in signals_lower or ".kt" in signals_lower:
            return "jvm-service", 0.8, "JVM source files detected"

        # Default based on first keyword match in signals
        for family, (keywords, confidence) in _SERVICE_FAMILY_SIGNALS.items():
            if any(k.lower() in signals_lower for k in keywords):
                return family, confidence, f"Language hint matched {family}"

        return "unknown", 0.1, "No language signals found, using fallback."

    def _score_runtime_role(
        self, signals: str, interfaces: list[str], data_models: list[str]
    ) -> tuple[str, float, str]:
        """Classify runtime role based on interfaces and data models."""
        interfaces_text = " ".join(interfaces).lower()
        models_text = " ".join(data_models).lower()

        # Check interface patterns
        for role, (keywords, base_confidence) in _RUNTIME_ROLE_SIGNALS.items():
            matches = [k for k in keywords if k.lower() in interfaces_text or k.lower() in models_text or k.lower() in signals.lower()]
            if matches:
                return role, base_confidence, f"Role signals: {', '.join(matches[:2])}"

        # Fallback based on data models presence
        if data_models:
            return "data-store", 0.5, "Module has data models, classified as data-store"
        elif interfaces:
            return "api-server", 0.5, "Module has interfaces, classified as api-server"

        return "tooling", 0.3, "No clear role signals, defaulting to tooling"

    def _enrich_endpoints(
        self,
        endpoints: list[Endpoint],
        modules: dict[str, Module],
        files: list[ScannedFile],
    ) -> None:
        """Enrich endpoints with service_family, domain, runtime_role, auth, and line citations.

        Phase 25 - Task 25.1: Extract controller/router/handler locations across
        Java, Python, and TypeScript fixtures. Infer service ownership, auth sources,
        request/response models, and error handling references. Preserve handler
        file/line citations for later pages.
        """
        module_lookup = {m.name: m for m in modules.values()}

        # Build file content index for line number lookups
        file_contents: dict[str, str] = {}
        for f in files:
            file_contents[f.path.as_posix()] = f.text

        for endpoint in endpoints:
            # Attach module-level metadata
            module = module_lookup.get(endpoint.module)
            if module:
                endpoint.service_family = module.service_family
                endpoint.domain = module.domain
                endpoint.runtime_role = module.runtime_role

            # Detect auth type
            endpoint.auth_type = self._detect_endpoint_auth_type(endpoint, module)
            endpoint.auth_required = endpoint.auth_type != "none"

            # Detect request body
            endpoint.request_body = endpoint.method in ("POST", "PUT", "PATCH") and not self._is_webhook_path(endpoint.path)

            # Set common error codes
            endpoint.error_codes = [400, 401, 403, 404, 500]

            # Extract line number for handler citation
            line_number = self._find_handler_line(endpoint, file_contents.get(endpoint.file_path, ""))
            endpoint.line_number = line_number
            endpoint.line_end = line_number + 10  # Approximate span

    def _is_webhook_path(self, path: str) -> bool:
        """Check if path looks like a webhook."""
        webhook_patterns = ["webhook", "callback", "hook", "/trigger", "/event"]
        path_lower = path.lower()
        return any(pattern in path_lower for pattern in webhook_patterns)

    def _detect_endpoint_auth_type(self, endpoint: Endpoint, module: Module | None) -> str:
        """Detect authentication type for an endpoint."""
        module_name = endpoint.module or ""
        path_lower = endpoint.path.lower()

        # Test modules don't require auth
        if module_name == "tests" or "test" in module_name.lower():
            return "none"

        # Check for auth-related path segments
        auth_paths = ["auth", "login", "signin", "token", "jwt", "oauth"]
        if any(ap in path_lower for ap in auth_paths):
            return "bearer"

        # Check for health/status paths (public, no auth needed)
        if any(x in path_lower for x in ("health", "status", "metrics", "monitoring", "ready")):
            return "none"

        # Webhook paths use signature verification, not bearer tokens
        if self._is_webhook_path(endpoint.path):
            return "none"

        # Check module domain
        if module and module.domain in ("frontend", "operations", "testing"):
            return "none"

        # Check runtime role (only if not already matched above)
        if module and module.runtime_role == "api-server":
            return "bearer"

        return "bearer"  # Default for unknown

    def _find_handler_line(self, endpoint: Endpoint, file_content: str) -> int:
        """Find the line number where the handler function is defined."""
        if not file_content:
            return 0

        handler = endpoint.handler
        if not handler or handler == "unknown":
            return 0

        # Search for function definition
        patterns = [
            rf"^def\s+{re.escape(handler)}\s*\(",
            rf"^async\s+def\s+{re.escape(handler)}\s*\(",
            rf"^function\s+{re.escape(handler)}\s*\(",
            rf"^export\s+function\s+{re.escape(handler)}\s*\(",
            rf"^export\s+const\s+{re.escape(handler)}\s*=",
            rf"^\s*func\s+{re.escape(handler)}\s*\(",
            rf"^\s*fun\s+{re.escape(handler)}\s*\(",
        ]

        lines = file_content.splitlines()
        for i, line in enumerate(lines, start=1):
            for pattern in patterns:
                if re.match(pattern, line.strip()):
                    return i

        return 0
