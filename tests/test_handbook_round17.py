"""Round 17: no prose/code deletion, derived roles, best-attempt keep, no hard-coded literals."""

from __future__ import annotations

from pathlib import Path

import pytest

from repo_wiki.evidence.citation_renderer import strip_empty_cite_parens
from repo_wiki.generator.adjacent_cites import (
    cite_readme_supporting_line,
    find_alembic_revision_rel,
    realign_route_registration_cites,
)
from repo_wiki.generator.composer import build_composer_input, create_composer
from repo_wiki.generator.composer_cache import COMPOSER_GENERATOR_VERSION
from repo_wiki.generator.process_roles import (
    derive_process_role_facts,
    derive_repo_process_names,
    unknown_process_mentions,
)
from repo_wiki.llm.models import ChatResponse
from repo_wiki.planner.schema import WikiTaxonomyCategory
from repo_wiki.verifier.handbook import (
    EVIDENCE_META_REJECTION,
    handbook_reader_hygiene_offenders,
    handbook_unknown_process_offenders,
)
from tests.test_handbook_round10 import _fastapi_repo, _page, _service
from tests.test_handbook_round14 import _context
from tests.test_handbook_round15 import _auth_page
from tests.test_handbook_round16 import _pad, _write_probe_mains
from tests.test_llm_compose_retry import SequenceLLMProvider

_FORBIDDEN_LITERALS = (
    "ccagent",
    "ccprobe-control",
    "probe-agent",
    "apiauth",
    "X-Probe-Api-Token",
    "probe_exporter",
    "app/core/settings",
    "ProbeBlackbox",
    "articles_common",
    "拨测",
    "conduit",
    "realworld",
    "fdf8821871d7",
    "not actively maintained",
    "不再积极维护",
    "1900",
    "rwdb",
    "pgdb",
    "probe-network",
    "mysql-data",
    "mysql-db",
    "ProbeEndpoint",
    "BizTreeNode",
    "APIAuth",
    "README sample, not in code",
    "commentaries",
    "followers_to_followings",
    "articles_to_tags",
    "mark_article_as_favorite",
    "remove_article_from_favorites",
    "follow_for_user",
    "unsubscribe_from_user",
    "/api/articles/{slug}/favorite",
    "/api/profiles/{username}/follow",
    "create_updated_at_trigger",
    "control url",
    "blackbox-exporter",
    "authenticationdep",
    "get_username_from_token",
    "/api/tags",
    "profiles.py",
    "7 张业务表",
)
_FORBIDDEN_PATH_JOINS = (
    r"""["']cmd["']\s*,\s*["']ccagent["']""",
    r"""["']cmd["']\s*/\s*["']ccagent["']""",
    r"""["']cmd["']\s*,\s*["']ccprobe-control["']""",
    r"""["']cmd["']\s*/\s*["']ccprobe-control["']""",
    r"""["']cmd["']\s*,\s*["']probe-agent["']""",
    r"""["']cmd["']\s*/\s*["']probe-agent["']""",
    r"""Path\(\s*["']cmd["']\s*\)\s*/\s*["']ccagent["']""",
    r"""Path\(\s*["']cmd["']\s*\)\s*/\s*["']ccprobe-control["']""",
    r"""Path\(\s*["']cmd["']\s*\)\s*/\s*["']probe-agent["']""",
    r"""os\.path\.join\(\s*["']cmd["']\s*,\s*["']ccagent["']""",
    r"""os\.path\.join\(\s*["']cmd["']\s*,\s*["']ccprobe-control["']""",
    r"""os\.path\.join\(\s*["']cmd["']\s*,\s*["']probe-agent["']""",
)


def test_empty_cite_parens_keep_code_calls() -> None:
    text = (
        "注入 `Depends(get_current_user_authorizer())` 与 `Depends(f())`，"
        "并在围栏中保留时间戳。\n"
        "```go\nnow := time.Now()\npool.close()\n```\n"
        "完整的 Web 管理界面（）。\n"
    )
    cleaned = strip_empty_cite_parens(text)
    assert "Depends(get_current_user_authorizer())" in cleaned
    assert "Depends(f())" in cleaned
    assert "time.Now()" in cleaned
    assert "pool.close()" in cleaned
    assert "（）" not in cleaned


def test_unknown_process_does_not_delete_identity(tmp_path: Path) -> None:
    _write_probe_mains(tmp_path)
    (tmp_path / "README.md").write_text("# probe_exporter\n\n平台。\n", encoding="utf-8")
    (tmp_path / "go.mod").write_text("module github.com/x/probe_exporter\n", encoding="utf-8")
    allowed = derive_repo_process_names(tmp_path)
    assert "probe_exporter" in allowed
    text = "probe_exporter 是面向企业级的服务探针平台，支持**双模式探测**。\n"
    assert unknown_process_mentions(text, allowed) == []


def test_unknown_process_skips_types_and_databases(tmp_path: Path) -> None:
    root = _fastapi_repo(tmp_path)
    content = tmp_path / "zh" / "content"
    content.mkdir(parents=True)
    (content / "认证问题.md").write_text(
        "# 认证问题\n\n`UsersRepository` 负责读用户。"
        "PostgreSQL 是主数据库。Controller 作为请求入口。"
        "`ApplyAuth` 在 README 示例里出现。\n",
        encoding="utf-8",
    )
    offenders = handbook_unknown_process_offenders(content, root)
    flat = [name for names in offenders.values() for name in names]
    assert "UsersRepository" not in flat
    assert "PostgreSQL" not in flat
    assert "Controller" not in flat
    assert "ApplyAuth" not in flat
    (content / "部署问题.md").write_text(
        "# 部署问题\n\nASGI 服务由 uvicorn 拉起。Postgres 服务提供主库。\n",
        encoding="utf-8",
    )
    more = handbook_unknown_process_offenders(content, root)
    flat = [name for names in more.values() for name in names]
    assert "ASGI" not in flat
    assert "Postgres" not in flat


def test_example_binary_is_not_main_entry(tmp_path: Path) -> None:
    _write_probe_mains(tmp_path)
    example = tmp_path / "cmd" / "custom-probe"
    example.mkdir(parents=True)
    (example / "README.md").write_text("# Custom Probe 示例工具\n\n学习用。\n", encoding="utf-8")
    (example / "main.go").write_text(
        "package main\nfunc main() {\n"
        '    mux.HandleFunc("/probe", h)\n    http.ListenAndServe(":8080", mux)\n}\n',
        encoding="utf-8",
    )
    (tmp_path / "cmd" / "ccagent" / "main.go").write_text(
        "package main\nfunc main() {\n"
        "    ccagent.NewController(config).Run()\n"
        '    mux.HandleFunc("/healthz", h)\n    mux.HandleFunc("/api/v1/x", h)\n}\n',
        encoding="utf-8",
    )
    facts = derive_process_role_facts(tmp_path)
    assert "custom-probe" in facts
    assert "示例" in facts
    assert facts.count("主 REST/Web") == 1
    assert "ccagent" in facts and "REST/Web" in facts
    assert "不是被" not in facts
    assert "拨测" not in facts


def test_best_structured_attempt_is_kept(tmp_path: Path) -> None:
    (tmp_path / "auth.go").write_text("package api\nfunc Apply() {}\n", encoding="utf-8")
    good = _pad(
        "# 认证授权API\n\n## 简介\n\n"
        "令牌解析发生在请求进入控制器之前。"
        "完整说明令牌解析与控制器注册。<cite>auth.go:1-2</cite>\n"
        "## 核心组件\n\n控制器把凭证接入请求生命周期。\n",
        minimum=1100,
    )
    bad = "# 认证授权API\n\n没有结构。\n"
    provider = SequenceLLMProvider(
        [
            ChatResponse(content=good, model="mock"),
            ChatResponse(content=good, model="mock"),
            ChatResponse(content=bad, model="mock"),
        ]
    )
    composer = create_composer(provider=provider)
    composer.workspace_root = tmp_path
    output = None

    async def _run() -> None:
        nonlocal output
        output = await composer.compose_page(
            build_composer_input(_auth_page(), None, _context(tmp_path))
        )

    import asyncio

    asyncio.run(_run())
    assert output is not None
    assert output.rejected is False
    assert "## 简介" in output.markdown
    assert "<cite>" in output.markdown
    assert "没有结构" not in output.markdown


def test_meta_optional_de_is_flagged(tmp_path: Path) -> None:
    content = tmp_path / "zh" / "content"
    content.mkdir(parents=True)
    (content / "认证授权API.md").write_text(
        _pad("# 认证授权API\n\n## 简介\n\n当前可见的源码证据只覆盖令牌解析。\n"),
        encoding="utf-8",
    )
    offenders = handbook_reader_hygiene_offenders(content, tmp_path)
    assert offenders.get("evidence_meta_talk")


def test_role_section_gated_on_derived_facts(tmp_path: Path) -> None:
    root = _fastapi_repo(tmp_path)
    page = _page(
        "module-relationships",
        "模块关系",
        WikiTaxonomyCategory.ARCHITECTURE_DESIGN,
        "架构设计/模块关系.md",
    )
    markdown = _pad("# 模块关系\n\n## 简介\n\nFastAPI 路由与仓储协作。\n")
    out = _service(root)._enforce_qoder_page_contract(page, markdown, None, add_mermaid=False)
    assert "角色说明" not in out
    assert "进程角色见整体架构概览" not in out


def test_identity_does_not_truncate_readme_mid_word() -> None:
    from repo_wiki.planner.identity import _parse_readme_identity

    title, description = _parse_readme_identity(
        "**NOTE**: This repository is not actively maintained because this example "
        "is quite complete and does its primary goal - passing Conduit testsuite.\n\n"
        "More modern and relevant examples can be found in other repositories with "
        "``fastapi`` tag on GitHub.\n\n"
        "Conduit is a RealWorld example API for users, articles, comments, and tags.\n"
    )
    assert description
    assert "in oth" not in description
    assert "other repositories" not in description
    assert "NOTE" not in description
    assert "Conduit" in description


def test_prompt_echo_flags_readme_sample_english(tmp_path: Path) -> None:
    from repo_wiki.verifier.handbook import (
        contains_generator_meta,
        handbook_reader_hygiene_offenders,
    )

    content = tmp_path / "content"
    content.mkdir()
    (content / "身份认证.md").write_text(
        "# 身份认证\n\nApplyAuth 是 README sample, not in code。\n",
        encoding="utf-8",
    )
    assert contains_generator_meta("README sample, not in code")
    offenders = handbook_reader_hygiene_offenders(content, tmp_path)
    assert offenders.get("instruction_voice")


def test_readme_note_is_found_by_structure(tmp_path: Path) -> None:
    (tmp_path / "README.rst").write_text(
        ".. image:: logo.png\n\n----------\n\n"
        "**NOTE**: This repository is complete.\n\nQuickstart\n----------\n",
        encoding="utf-8",
    )
    cite = cite_readme_supporting_line(tmp_path, "README.rst", "产品身份不再积极维护")
    assert cite == "<cite>README.rst:5-5</cite>"


def test_alembic_revision_is_discovered(tmp_path: Path) -> None:
    versions = tmp_path / "app" / "db" / "migrations" / "versions"
    versions.mkdir(parents=True)
    (versions / "aaaa_small.py").write_text("def upgrade():\n    pass\n", encoding="utf-8")
    (versions / "bbbb_main.py").write_text(
        "def upgrade():\n    op.create_table('a')\n    op.create_table('b')\n",
        encoding="utf-8",
    )
    assert find_alembic_revision_rel(tmp_path).endswith("bbbb_main.py")


def test_route_cite_realigns_to_registration(tmp_path: Path) -> None:
    (tmp_path / "controller.go").write_text(
        "\n" * 54
        + 'mux.HandleFunc("/probe/result/list", list)\n'
        + "\n" * 80
        + 'path := "/probe/result/list"\n',
        encoding="utf-8",
    )
    markdown = "查询 `/probe/result/list` <cite>controller.go:136-136</cite>\n"
    out = realign_route_registration_cites(markdown, tmp_path)
    assert "<cite>controller.go:55-55</cite>" in out


def test_unknown_process_ignores_volume_and_generic_server_names() -> None:
    text = (
        "命名卷 `ha-agent-a1-data`、`ha-agent-*-data` 只是持久化锚点。"
        '说明优先于通用包名 slug 或 "api-server" 这类泛称。'
        "UsersRepository 负责读用户。PostgreSQL 是主数据库。\n"
    )
    assert unknown_process_mentions(text, {"probe-agent"}) == []
    assert unknown_process_mentions("见 cmd/probe-control/main.go。\n", {"ccprobe-control"}) == []


def test_code_integrity_matches_raw_replies_by_any_path(tmp_path: Path) -> None:
    from repo_wiki.verifier.handbook import handbook_code_integrity_offenders

    content = tmp_path / "zh" / "content"
    content.mkdir(parents=True)
    (content / "开发指南").mkdir()
    (content / "开发指南" / "数据库迁移.md").write_text(
        "# 迁移\n\n调用 `FastAPI()` 与 `pool.close()`。\n",
        encoding="utf-8",
    )
    raw_dir = tmp_path / "zh" / "meta" / "raw-replies" / "docs" / "pages" / "development"
    raw_dir.mkdir(parents=True)
    (raw_dir / "database-migration.md").write_text(
        "调用 `FastAPI()` 与 `pool.close()`。\n",
        encoding="utf-8",
    )
    (tmp_path / "app.py").write_text("print('ok')\n", encoding="utf-8")
    offenders = handbook_code_integrity_offenders(content, tmp_path)
    flat = [unit for units in offenders.values() for unit in units]
    assert "FastAPI()" not in flat
    assert "pool.close()" not in flat
    (content / "部署.md").write_text(
        "# 部署\n\n调用 `FastAPI()`。\n\n```bash\nmake install\n```\n",
        encoding="utf-8",
    )
    more = handbook_code_integrity_offenders(content, tmp_path)
    flat = [unit for units in more.values() for unit in units]
    assert not any(unit.startswith("empty-span") for unit in flat)


def test_readme_header_range_cite_is_rewritten(tmp_path: Path) -> None:
    from repo_wiki.generator.adjacent_cites import rewrite_fastapi_intro_cites

    (tmp_path / "README.rst").write_text(
        "Logo\n====\n\n**NOTE**: This repository is complete.\n\nQuickstart\n----------\n",
        encoding="utf-8",
    )
    page = _page(
        "development-guide",
        "开发指南",
        WikiTaxonomyCategory.DEVELOPMENT_GUIDE,
        "开发指南/开发指南.md",
    )
    markdown = (
        "工厂保持接口稳定 <cite>README.rst:28-28</cite>"
        "<cite>app/api/dependencies/authentication.py:21-34</cite>。"
        "同时请注意仓库已停止主动维护。<cite>README.rst:1-10</cite>\n"
    )
    out = rewrite_fastapi_intro_cites(markdown, page, tmp_path)
    assert "README.rst:1-10" not in out
    assert "README.rst:4-4" in out
    assert "authentication.py:21-34" in out


def _sample_repo_literals() -> tuple[str, ...]:
    import os
    import re

    extra: list[str] = []
    raw = os.environ.get("REPO_WIKI_SAMPLE_REPOS", "")
    roots = [Path(item) for item in raw.split(":") if item]
    roots.extend(
        path
        for path in (
            Path("/tmp/sample-repos"),
            Path("/tmp/eval-probe"),
            Path("/tmp/eval-fastapi"),
        )
        if path.is_dir()
    )
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {
                ".go",
                ".py",
                ".sql",
                ".yml",
                ".yaml",
            }:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            extra.extend(
                re.findall(r"\b(?:ccagent|ccprobe-control|probe-agent)\b", text, flags=re.I)
            )
            extra.extend(re.findall(r"create_table\(\s*[\"']([a-z][a-z0-9_]+)[\"']", text))
            extra.extend(
                re.findall(
                    r"^\s{2}([A-Za-z][A-Za-z0-9_-]*(?:-[A-Za-z0-9_]+)+):\s*$",
                    text,
                    flags=re.M,
                )
            )
            extra.extend(
                re.findall(
                    r"\b(mark_article\w+|remove_article\w+|follow_for_user|"
                    r"unsubscribe_from_user|articles_to_tags|followers_to_followings)\b",
                    text,
                )
            )
    return tuple(
        sorted({item.lower() for item in extra if len(item) >= 8 and ("_" in item or "-" in item)})
    )


def test_no_repo_specific_literals_in_audited_source() -> None:
    import re

    repo = Path(__file__).resolve().parents[1]
    tokens = {item.lower() for item in _FORBIDDEN_LITERALS}
    tokens.update(_sample_repo_literals())
    hits: list[str] = []
    for path in sorted((repo / "repo_wiki").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(repo).as_posix()
        lowered = text.lower()
        for token in tokens:
            if not token:
                continue
            if re.search(rf"(?<![A-Za-z0-9_]){re.escape(token)}(?![A-Za-z0-9_])", lowered):
                hits.append(f"{rel}:{token}")
        for pattern in _FORBIDDEN_PATH_JOINS:
            if re.search(pattern, text, flags=re.I):
                hits.append(f"{rel}:path-join:{pattern}")
    assert hits == []


def test_generator_version_is_r17() -> None:
    assert COMPOSER_GENERATOR_VERSION.startswith("handbook-r24-")


def test_hedged_current_evidence_is_meta_talk() -> None:
    from repo_wiki.verifier.handbook import contains_evidence_meta_talk

    assert contains_evidence_meta_talk("当前可见的源码证据只覆盖令牌解析。")
    assert contains_evidence_meta_talk("本页限定在提供的证据范围内描述迁移。")
    assert contains_evidence_meta_talk("其余状态码在当前证据之外，不再推断。")
    assert contains_evidence_meta_talk("当前证据集中在迁移 revision 的 upgrade。")
    assert contains_evidence_meta_talk("额外模块不在源码证据范围内，应避免凭空假设。")


def test_fallback_stub_detector_ignores_short_llm() -> None:
    from repo_wiki.verifier.handbook import handbook_page_is_fallback_stub

    llm = "# 数据库迁移\n\n## 环境搭建\n\n连接池在启动期注入。\n"
    stub = (
        "# 数据库迁移\n\n## 这是什么\n\n"
        "「数据库迁移」面向接手仓库的人，用来定位这个主题在仓库里的实现。\n"
        "## 可核对的文件\n"
    )
    assert handbook_page_is_fallback_stub(llm) is False
    assert handbook_page_is_fallback_stub(stub) is True


def test_short_migration_page_appends_alembic_facts(tmp_path: Path) -> None:
    root = _fastapi_repo(tmp_path)
    page = _page(
        "database-migration",
        "数据库迁移",
        WikiTaxonomyCategory.DEVELOPMENT_GUIDE,
        "开发指南/数据库迁移.md",
    )
    markdown = (
        "# 数据库迁移\n\n## 环境搭建\n\n"
        "连接池在启动期注入，关闭时释放。<cite>app/db/events.py:20-25</cite>\n"
    )
    out = _service(root)._enforce_qoder_page_contract(page, markdown, None, add_mermaid=False)
    assert "README.rst:1-10" not in out
    assert "op.create_table" in out
    assert "users" in out


@pytest.mark.asyncio
async def test_meta_still_rejects_after_retries(tmp_path: Path) -> None:
    meta = _pad("# 认证授权API\n\n## 简介\n\n当前可见的源码证据只覆盖 Bearer。\n")
    provider = SequenceLLMProvider([ChatResponse(content=meta, model="mock") for _ in range(3)])
    composer = create_composer(provider=provider)
    composer.workspace_root = tmp_path
    output = await composer.compose_page(
        build_composer_input(_auth_page(), None, _context(tmp_path))
    )
    assert provider.call_count == 3
    assert output.rejected is True
    assert output.rejection_reason == EVIDENCE_META_REJECTION
