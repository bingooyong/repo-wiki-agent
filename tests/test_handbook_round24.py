"""Round 24: exact route cross-check, invented endpoints, stubs, CommonMark render."""

from __future__ import annotations

import re
from pathlib import Path

from repo_wiki.generator.composer_cache import COMPOSER_GENERATOR_VERSION
from repo_wiki.generator.deterministic_sections import (
    build_install_section,
    build_verify_section,
    dedupe_identical_fences,
    strip_dangling_colon_leads,
)
from repo_wiki.orchestration.content_layout_writer import ContentLayoutWriter
from repo_wiki.orchestration.eval_layout import EvalOutputProfile
from repo_wiki.planner.identity import resolve_repository_identity
from repo_wiki.verifier.handbook import (
    MIN_HANDBOOK_BODY_CHARS,
    classify_shell_command,
    collect_repo_install_commands,
    collect_repo_run_commands,
    core_page_stub_offenders,
    dangling_colon_lead_ins,
    discover_model_classes,
    extract_readme_shell_commands,
    handbook_page_body_len,
    install_page_render_errors,
)
from repo_wiki.verifier.handbook_routes import (
    ROUTE_COMPLETENESS_MIN,
    extract_handbook_http_paths,
    extract_source_http_paths,
    handbook_route_crosscheck_mismatches,
    route_completeness_ratio,
    source_extraction_is_unsupported,
    upgrade_handbook_route_paths,
)
from repo_wiki.verifier.qoder_strict_verifier import QoderLikeVerifierService
from repo_wiki.verifier.source_facts import handbook_source_fact_offenders


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def test_1_prefix_declared_in_other_file() -> None:
    files = [
        (
            "boot/app.py",
            "from lamps.routes import lantern\n"
            "application = FastAPI()\n"
            "STEM = '/harbor'\n"
            "application.include_router(lantern, prefix=STEM)\n",
        ),
        (
            "lamps/routes.py",
            "router = APIRouter(prefix='/beacons')\n"
            "@router.get('/flash')\n"
            "def flash():\n    return {}\n",
        ),
    ]
    source = extract_source_http_paths(files)
    assert source == {("GET", "/harbor/beacons/flash")}
    assert ("GET", "/beacons/flash") not in source
    assert ("GET", "/flash") not in source


def test_1_two_level_nest_and_mount() -> None:
    files = [
        (
            "main.py",
            "from outer import router as outer\n"
            "app = FastAPI()\n"
            "app.include_router(outer, prefix='/v2')\n",
        ),
        (
            "outer.py",
            "from inner import router as inner\n"
            "router = APIRouter(prefix='/ops')\n"
            "router.include_router(inner, prefix='/lamps')\n",
        ),
        (
            "inner.py",
            "router = APIRouter()\n@router.post('/ignite')\ndef ignite():\n    return {}\n",
        ),
    ]
    source = extract_source_http_paths(files)
    assert source == {("POST", "/v2/ops/lamps/ignite")}


def test_1_class_resource_and_chained_builder() -> None:
    files = [
        (
            "rest.py",
            "api.add_resource(WickView, '/wicks', '/wicks/<wid>')\n"
            "url('/candles/<cid>', CandleView.as_view('candle'))\n",
        ),
        (
            "chain.js",
            "const router = Router();\nrouter.route('/sparks/:sid').get(show).post(make);\n",
        ),
    ]
    source = extract_source_http_paths(files)
    assert ("ANY", "/wicks") in source
    assert ("ANY", "/wicks/:wid") in source
    assert ("ANY", "/candles/:cid") in source
    assert ("GET", "/sparks/:sid") in source
    assert ("POST", "/sparks/:sid") in source


def test_1_verbless_table_and_method_match() -> None:
    files = [("app.py", "app = FastAPI()\n@app.delete('/ashes')\ndef ashes():\n    return {}\n")]
    table = "# API\n\n| 路径 |\n| --- |\n| `/ashes` |\n"
    found = extract_handbook_http_paths(table, api_page=True)
    assert ("ANY", "/ashes") in found
    assert handbook_route_crosscheck_mismatches(table, files, api_page=True) == []
    wrong_verb = "# API\n\nGET `/ashes`\n"
    assert handbook_route_crosscheck_mismatches(wrong_verb, files) == ["GET /ashes"]


def test_1_unsupported_never_passes() -> None:
    files = [
        ("needs.txt", "Depends on FastAPI for the HTTP surface.\n"),
        ("glue.py", "class Wick(Resource):\n    pass\nApi.attach('/wicks', Wick)\n"),
    ]
    assert extract_source_http_paths(files) == set()
    assert source_extraction_is_unsupported(files)
    assert route_completeness_ratio("# API\n", files) == 0.0


def test_2_invented_endpoints_fail() -> None:
    files = [("app.py", "app = FastAPI()\n@app.get('/real-spark')\ndef spark():\n    return {}\n")]
    invented = "# API\n\nGET `/users` 与 POST `/login`。\n"
    bad = handbook_route_crosscheck_mismatches(invented, files, api_page=True)
    assert any("/users" in item or "/login" in item for item in bad)
    assert ROUTE_COMPLETENESS_MIN == 0.5
    assert route_completeness_ratio(invented, files) == 0.0


def test_2_curl_and_upgrade_unique_suffix() -> None:
    files = [
        ("app.py", "app = FastAPI()\n@app.get('/harbor/wicks')\ndef wicks():\n    return {}\n")
    ]
    curl = "# API\n\n```\ncurl -X GET http://127.0.0.1:9/harbor/wicks\n```\n"
    assert handbook_route_crosscheck_mismatches(curl, files, api_page=True) == []
    upgraded = upgrade_handbook_route_paths("# API\n\nGET `/wicks`\n", files)
    assert "/harbor/wicks" in upgraded


def test_3_core_stub_is_reported(tmp_path: Path) -> None:
    content = tmp_path / "pages"
    _write(content / "数据模型.md", "# 数据模型\n\nevidence missing\n")
    _write(content / "附录清单.md", "# 附录\n\n" + ("清单项。" * 40) + "\n")
    stubs = core_page_stub_offenders(content)
    assert any("数据模型" in key or "data" in key for key in stubs)
    assert handbook_page_body_len("# 数据模型\n\nevidence missing\n") < MIN_HANDBOOK_BODY_CHARS


def test_4_commonmark_fence_with_trailing_cite_is_unclosed() -> None:
    broken = (
        "## 安装步骤\n\n1. `git clone x`\n\n```bash\ngit clone x\n``` <cite>README.md:1-1</cite>\n"
    )
    errors = install_page_render_errors(broken)
    assert any("unclosed" in item or "unbalanced" in item or "cite" in item for item in errors)
    closed = (
        "## 安装步骤\n\n1. `git clone x`\n\n```bash\ngit clone x\n```\n<cite>README.md:1-1</cite>\n"
    )
    assert install_page_render_errors(closed) == []


def test_4_quickstart_and_dangling_lead_in() -> None:
    dangling = "先执行克隆：\n\n## 下一步\n"
    assert dangling_colon_lead_ins(dangling)
    cleaned = strip_dangling_colon_leads("先执行克隆：\n\n## 下一步\n")
    assert dangling_colon_lead_ins(cleaned) == []
    duped = "再用这条：\n\n```bash\ngit clone x\n```\n\n再用这条：\n\n```bash\ngit clone x\n```\n"
    after = strip_dangling_colon_leads(dedupe_identical_fences(duped))
    assert after.count("```") == 2
    assert dangling_colon_lead_ins(after) == []


def test_4_no_command_cap_and_placeholders_kept(tmp_path: Path) -> None:
    fences = "\n".join(f"```bash\nmake wick-{index}\n```" for index in range(1, 16))
    _write(
        tmp_path / "README.md",
        f"# Wick\n\n```bash\ngit clone https://example.invalid/wick.git\n```\n{fences}\n"
        "```bash\nuvicorn wick.main:app --host 0.0.0.0 --port 9\n```\n"
        "```bash\nexport TOKEN=<WICK_TOKEN>\n```\n"
        "```bash\ndocker compose down\n```\n"
        "```bash\npytest -q\n```\n",
    )
    install = collect_repo_install_commands(tmp_path)
    run = collect_repo_run_commands(tmp_path)
    assert any("wick-14" in item or "wick-15" in item for item in install + run)
    assert any("uvicorn" in item for item in run)
    assert any(
        "<WICK_TOKEN>" in item
        for item in extract_readme_shell_commands(
            (tmp_path / "README.md").read_text(encoding="utf-8")
        )
    )
    assert classify_shell_command("docker compose down") == "destructive"
    assert classify_shell_command("pytest -q") == "test"
    section = build_install_section(tmp_path)
    assert "compose down" not in section
    assert "pytest" not in section
    verify = build_verify_section(tmp_path)
    assert "uvicorn" in verify or any("uvicorn" in item for item in run)


def test_5_identity_skips_changelog_and_desc(tmp_path: Path) -> None:
    _write(
        tmp_path / "README.md",
        """
# Wick Lantern

desc: slug leftover for the catalog

## Changelog

- v9.9 ships a rewrite

Wick Lantern keeps coastal lamps lit overnight.
""",
    )
    identity = resolve_repository_identity(tmp_path)
    assert identity.display_name == "Wick Lantern"
    assert "slug leftover" not in (identity.description or "")
    assert "v9.9" not in (identity.description or "")
    assert "keeps coastal lamps" in (identity.description or "")


def test_6_odm_name_comes_from_registration(tmp_path: Path) -> None:
    _write(
        tmp_path / "store" / "nodes.js",
        """
const WidgetDoc = new mongoose.Schema({
  title: String,
});
mongoose.model('LanternNode', WidgetDoc);
""",
    )
    tables = {name for name, _rel in discover_model_classes(tmp_path)}
    assert "LanternNode" in tables
    assert "WidgetDoc" not in tables


def test_6_placeholder_model_table_fails(tmp_path: Path) -> None:
    from repo_wiki.verifier.handbook import model_definition_cite_offenders

    _write(tmp_path / "store" / "wick.py", "class Wick:\n    __tablename__ = 'wicks'\n")
    page = "# 数据模型\n\n| 字段 | 说明 |\n| --- | --- |\n| name | declared in source |\n"
    assert model_definition_cite_offenders(page, tmp_path)


def test_10_dotted_module_is_not_a_directory(tmp_path: Path) -> None:
    versions = tmp_path / "db" / "migrations"
    versions.mkdir(parents=True)
    _write(tmp_path / "db" / "migrations" / "env.py", "target_metadata = None\n")
    _write(tmp_path / "store" / "models.py", "class Wick:\n    __tablename__ = 'wicks'\n")
    content = tmp_path / "pages"
    _write(content / "数据库迁移.md", "模型在 `store.models`。\n")
    found = handbook_source_fact_offenders(content, tmp_path)
    flat = [item for hits in found.values() for item in hits]
    assert not any(item.startswith("orm:") and "store.models" in item for item in flat)
    _write(content / "数据库迁移.md", "模型在 `missing.models.wick`。\n")
    found = handbook_source_fact_offenders(content, tmp_path)
    flat = [item for hits in found.values() for item in hits]
    assert any(item.startswith("orm:") for item in flat)


def test_9_stale_pages_are_unlinked(tmp_path: Path) -> None:
    profile = EvalOutputProfile(
        name="qoder-like",
        root=str(tmp_path / ".repo-agent-eval"),
        create_subdirs=True,
        content_subdir="content",
    )
    writer = ContentLayoutWriter(profile, "r24")
    writer.write_markdown_pages([("docs/pages/overview.md", "# 旧页\n")])
    leftover = next(writer.content_dir.rglob("*.md"))
    writer.write_markdown_pages([("docs/pages/install.md", "# 新页\n")])
    remaining = [path.name for path in writer.content_dir.rglob("*.md")]
    assert leftover.name not in remaining or leftover.read_text(encoding="utf-8").startswith("# 新")
    assert any(
        "新" in path.read_text(encoding="utf-8") for path in writer.content_dir.rglob("*.md")
    )


def test_11_thresholds_and_version_stay_tight() -> None:
    assert ROUTE_COMPLETENESS_MIN == 0.5
    assert MIN_HANDBOOK_BODY_CHARS == 800
    assert COMPOSER_GENERATOR_VERSION.startswith("handbook-r24-")
    assert re.fullmatch(r"handbook-r24-\d{8}", COMPOSER_GENERATOR_VERSION)


def test_12_command_page_gate_is_not_title_only() -> None:
    page = "# 快速开始指南\n\n1. `git clone x`\n\n```bash\ngit clone x\n``` <cite>README.md:1-1</cite>\n"
    assert install_page_render_errors(page)
    verifier = QoderLikeVerifierService
    assert hasattr(verifier, "_check_handbook_install_fence")
