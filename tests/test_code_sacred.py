"""Phase A: code spans/fences stay byte-identical to the raw model reply."""

from __future__ import annotations

import os
from pathlib import Path

from repo_wiki.evidence.citation_renderer import normalize_citation_markup
from repo_wiki.generator.code_safe import sacred_code_offenders
from repo_wiki.generator.deterministic_sections import (
    apply_deterministic_rewrites,
    expand_truncated_build_commands,
)
from repo_wiki.planner.schema import WikiTaxonomyCategory
from repo_wiki.verifier.api_claim_inventory import drop_uninventoried_api_claims
from repo_wiki.verifier.handbook import handbook_code_integrity_offenders
from tests.test_handbook_round10 import _go_context, _page, _render, _service


def test_25s_route_spans_are_not_emptied(tmp_path: Path) -> None:
    raw = (
        "# API开发指南\n\n"
        "创建用 `POST /create`，列表用 `GET /list`，"
        "详情 `GET /get/:id`，更新 `PUT /update/:id`。\n"
    )
    page = _page(
        "api-dev-guide",
        "API开发指南",
        WikiTaxonomyCategory.DEVELOPMENT_GUIDE,
        "开发指南/API开发指南.md",
    )
    out = _render(_service(tmp_path), page, raw, _go_context(tmp_path), add_mermaid=False)
    assert "`POST /create`" in out
    assert "`GET /list`" in out
    assert "`GET /get/:id`" in out
    assert "`PUT /update/:id`" in out
    assert "``" not in out.replace("```", "")


def test_25s_agent_api_wildcard_spans_stay(tmp_path: Path) -> None:
    raw = (
        "# Agent代理API\n\n"
        "接口在 `ANY /probe/...`、`ANY /tag/...`、`GET /api/v1/agent/...` 下暴露。\n"
    )
    page = _page(
        "agent-api",
        "Agent代理API",
        WikiTaxonomyCategory.API_REFERENCE,
        "API参考/Agent代理API.md",
    )
    out = _render(_service(tmp_path), page, raw, _go_context(tmp_path), add_mermaid=False)
    assert "`ANY /probe/...`" in out
    assert "`ANY /tag/...`" in out
    assert "`GET /api/v1/agent/...`" in out


def test_25s_go_build_span_is_not_expanded(tmp_path: Path) -> None:
    raw = "# IDE配置\n\n构建入口沿用 `go build -o bin/... cmd/.../main.go` 的写法。\n"
    page = _page(
        "ide-configuration",
        "IDE配置",
        WikiTaxonomyCategory.DEVELOPMENT_GUIDE,
        "开发指南/IDE配置.md",
    )
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text(
        "run: go build -o bin/ccagent ./cmd/ccagent\n",
        encoding="utf-8",
    )
    out = _render(_service(tmp_path), page, raw, _go_context(tmp_path), add_mermaid=False)
    assert "`go build -o bin/... cmd/.../main.go`" in out
    assert " && " not in out
    assert expand_truncated_build_commands(raw, tmp_path) == raw


def test_25s_adjacent_spans_do_not_merge_with_cite(tmp_path: Path) -> None:
    raw = (
        "# 系统组件\n\n"
        "见 `deploy/mtls/README.md` 与 `db/migrations/`。"
        "入口在 `README.md` 与 `cmd/probe-agent`。\n"
    )
    page = _page(
        "system-components",
        "系统组件",
        WikiTaxonomyCategory.ARCHITECTURE_DESIGN,
        "架构设计/系统组件.md",
    )
    out = _render(_service(tmp_path), page, raw, _go_context(tmp_path), add_mermaid=False)
    assert "`deploy/mtls/README.md`" in out
    assert "`db/migrations/`" in out
    assert "<cite>" not in "`deploy/mtls/README.md`"
    assert "README.md<cite>" not in out
    assert "db/migrations/" in out


def test_25s_cite_to_code_converter_is_gone() -> None:
    text = "见 `articles_common.py` 与 `DESIGN.md:49-54`。"
    out = normalize_citation_markup(text)
    assert "`articles_common.py`" in out
    assert "`DESIGN.md:49-54`" in out
    assert "``articles_common.py``" not in out
    assert sacred_code_offenders(out, text) == []


def test_25s_fastapi_truncated_readme_span_stays() -> None:
    raw = "More modern examples can be found in oth `README.rst` 仓库说明。"
    out = normalize_citation_markup(raw)
    assert "`README.rst`" in out
    assert "in oth``" not in out
    assert sacred_code_offenders(out, raw) == []


def test_drop_uninventoried_does_not_empty_spans() -> None:
    text = "创建 `POST /create` 与散文 POST /wrong_path/asd 。\n"
    out = drop_uninventoried_api_claims(text, {("POST", "/api/items")})
    assert "`POST /create`" in out
    assert "POST /wrong_path/asd" not in out


def test_sacred_code_offenders_detect_empty_and_rewrite() -> None:
    raw = "用 `POST /create` 再 `go build -o bin/... cmd/.../main.go`。"
    mutated = "用 `` 再 `go build -o bin/x ./cmd/x && go build -o bin/y ./cmd/y`。"
    offenders = sacred_code_offenders(mutated, raw)
    assert any(item == "``" for item in offenders)
    assert any("go build" in item for item in offenders)


def test_integrity_flags_sacred_mutation(tmp_path: Path) -> None:
    content = tmp_path / "content"
    raw_dir = tmp_path / "meta" / "raw-replies"
    content.mkdir()
    raw_dir.mkdir(parents=True)
    (content / "page.md").write_text("# API\n\n见 `` 与 `` 。\n", encoding="utf-8")
    (raw_dir / "page.md").write_text(
        "# API\n\n见 `POST /create` 与 `GET /list`。\n", encoding="utf-8"
    )
    (tmp_path / "main.go").write_text("package main\n", encoding="utf-8")
    found = handbook_code_integrity_offenders(content, tmp_path)
    assert found


def test_apply_deterministic_rewrites_keep_raw_spans(tmp_path: Path) -> None:
    raw = "# 架构\n\n`POST /create` 与 `go build -o bin/... cmd/.../main.go`。\n"
    out = apply_deterministic_rewrites(raw, tmp_path, title="系统组件", page_id="system-components")
    assert sacred_code_offenders(out, raw) == []


def test_cassette_property_all_waves_when_present() -> None:
    """Every 25m–25s cassette copy keeps code units under outside-code rewrites."""
    import json

    from repo_wiki.generator.code_safe import empty_inline_spans, map_outside_code

    root = Path(os.environ.get("REPO_WIKI_CASSETTE_MATRIX_DIR", "/tmp/cassettes-copy"))
    if not root.is_dir():
        return
    waves = ("25m", "25n", "25o", "25p", "25q", "25r", "25s")
    folders: list[Path] = []
    for repo in ("probe", "fastapi"):
        for wave in waves:
            for name in (f"{repo}-{wave}-raw-cassette", f"{repo}-{wave}"):
                folder = root / name
                if folder.is_dir():
                    folders.append(folder)
                    break
    if not folders:
        return
    assert len(folders) == 14, f"expected 14 cassette copies, found {len(folders)}"
    checked = 0
    for folder in folders:
        jsonls = list(folder.rglob("*.jsonl"))
        assert jsonls, f"missing jsonl in {folder}"
        for jsonl in jsonls:
            for line in jsonl.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                record = json.loads(line)
                raw = str(record.get("raw_reply") or "")
                if not raw.strip():
                    continue
                assert map_outside_code(raw, lambda text: text) == raw
                smashed = map_outside_code(raw, lambda text: "\u3000".join(text.split(" ")))
                assert sacred_code_offenders(smashed, raw) == []
                assert empty_inline_spans(smashed) == empty_inline_spans(raw)
                checked += 1
    assert checked >= 14
