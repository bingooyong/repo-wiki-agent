"""Round 18: restored gates, code-safe rewrites, derived roles, no filler."""

from __future__ import annotations

from pathlib import Path

from repo_wiki.generator.code_safe import (
    empty_inline_spans,
    map_outside_code,
)
from repo_wiki.generator.deterministic_sections import (
    attach_missing_route_cites,
    rewrite_route_cites_from_endpoints,
)
from repo_wiki.generator.process_roles import derive_process_role_facts
from repo_wiki.planner.schema import WikiTaxonomyCategory
from repo_wiki.verifier.handbook import (
    handbook_code_integrity_offenders,
    handbook_doc_code_mismatches,
    has_unclosed_fence,
)
from tests.test_handbook_round10 import _fastapi_repo, _page, _service
from tests.test_handbook_round16 import _pad, _write_probe_mains


def test_code_safe_map_does_not_touch_spans_or_fences() -> None:
    text = (
        "安装 `make install` 之后检查 `http://localhost:8080/health`。\n"
        "```bash\ncurl http://localhost:8080/health\n```\n"
        "路由 `GET /probe/result/list` 仍保持原样。\n"
    )

    def _mutate(prose: str) -> str:
        return prose.replace("8080", "1900").replace("make install", "make boom")

    out = map_outside_code(text, _mutate)
    assert "`make install`" in out
    assert "`http://localhost:8080/health`" in out
    assert "```bash\ncurl http://localhost:8080/health\n```" in out
    assert "1900" not in out


def test_route_cite_injection_stays_outside_spans(tmp_path: Path) -> None:
    (tmp_path / "controller.go").write_text(
        'mux.HandleFunc("/probe/result/list", list)\n', encoding="utf-8"
    )
    endpoints = [
        {
            "method": "GET",
            "path": "/probe/result/list",
            "file_path": "controller.go",
            "line_number": 1,
        }
    ]
    text = "查询 `GET /probe/result/list` 返回最近结果。\n"
    out = map_outside_code(
        text, lambda body: rewrite_route_cites_from_endpoints(body, endpoints, tmp_path)
    )
    assert "`GET /probe/result/list`" in out
    assert "<cite>" not in out.split("`GET /probe/result/list`")[0][-20:]
    assert "<cite>controller.go:1-1</cite>" not in "`GET /probe/result/list`"
    attached = map_outside_code(text, lambda body: attach_missing_route_cites(body, endpoints))
    assert "`GET /probe/result/list`" in attached


def test_unclosed_fence_and_empty_span_are_integrity_violations(tmp_path: Path) -> None:
    content = tmp_path / "zh" / "content"
    content.mkdir(parents=True)
    (content / "身份认证.md").write_text(
        "# 身份认证\n\n```go\nfunc Apply() {}\n``<cite>README.md:319-330</cite>CustomAuth`\n",
        encoding="utf-8",
    )
    (content / "API开发指南.md").write_text(
        "# API\n\n- `` 与 `` 被清空。\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("# x\n", encoding="utf-8")
    raw = tmp_path / "zh" / "meta" / "raw-replies"
    raw.mkdir(parents=True)
    (raw / "auth.md").write_text("func Apply() {}\n", encoding="utf-8")
    offenders = handbook_code_integrity_offenders(content, tmp_path)
    flat = [item for items in offenders.values() for item in items]
    assert any("unclosed-fence" in item for item in flat)
    assert empty_inline_spans((content / "API开发指南.md").read_text(encoding="utf-8"))
    assert has_unclosed_fence((content / "身份认证.md").read_text(encoding="utf-8"))


def test_doc_only_readme_methods_are_mismatches(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "# Auth\n\n```go\nfunc (h *Handler) ApplyAuth() {}\ntype CustomAuth struct{}\n```\n",
        encoding="utf-8",
    )
    (tmp_path / "auth.go").write_text(
        "package auth\nfunc (a Authenticator) Apply() {}\n", encoding="utf-8"
    )
    content = tmp_path / "zh" / "content"
    content.mkdir(parents=True)
    (content / "身份认证.md").write_text(
        "# 身份认证\n\n接口合同是 `ApplyAuth` 与 `CustomAuth`。真实方法是 `Apply`。\n",
        encoding="utf-8",
    )
    found = handbook_doc_code_mismatches(content, tmp_path)
    flat = [name for names in found.values() for name in names]
    assert "ApplyAuth" in flat
    assert "CustomAuth" in flat
    assert "Apply" not in flat


def test_probe_roles_rank_http_entry_even_with_grpc(tmp_path: Path) -> None:
    _write_probe_mains(tmp_path)
    (tmp_path / "controller.go").write_text(
        "package ccagent\nfunc (c *Controller) Run() {\n"
        '    mux.HandleFunc("/health", h)\n    mux.HandleFunc("/probe", h)\n'
        '    mux.HandleFunc("/tag", h)\n    http.ListenAndServe(":1900", mux)\n}\n',
        encoding="utf-8",
    )
    (tmp_path / "cmd" / "ccagent" / "main.go").write_text(
        'package main\nimport "ccagent"\nfunc main() {\n'
        "    ccagent.NewController(config).Run()\n}\n",
        encoding="utf-8",
    )
    (tmp_path / "cmd" / "probe-agent" / "main.go").write_text(
        "package main\nfunc main() {\n"
        "    // data-plane execution pool\n"
        "    grpc.Dial(control)\n}\n",
        encoding="utf-8",
    )
    (tmp_path / "cmd" / "ccprobe-control" / "main.go").write_text(
        "package main\nfunc main() {\n    control.NewTunnelHub()\n    grpc.ListenAndServe()\n}\n",
        encoding="utf-8",
    )
    example = tmp_path / "cmd" / "custom-probe"
    example.mkdir(parents=True)
    (example / "README.md").write_text("# Custom Probe 示例工具\n", encoding="utf-8")
    (example / "main.go").write_text(
        "package main\nfunc main() {\n"
        '    mux.HandleFunc("/probe", h)\n    http.ListenAndServe(":8080", mux)\n}\n',
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text(
        "# demo\n\nRun `./bin/ccagent` then curl :1900/health\n", encoding="utf-8"
    )
    facts = derive_process_role_facts(tmp_path)
    assert "ccagent" in facts and "REST/Web" in facts
    assert "probe-agent" in facts and "数据面" in facts
    assert "custom-probe" in facts and "示例" in facts
    assert "不承担面向前端" not in facts
    assert facts.count("主 REST/Web") == 1


def test_fastapi_has_no_derived_go_roles(tmp_path: Path) -> None:
    root = _fastapi_repo(tmp_path)
    assert derive_process_role_facts(root) == ""
    page = _page(
        "architecture-overview",
        "整体架构概览",
        WikiTaxonomyCategory.ARCHITECTURE_DESIGN,
        "架构设计/整体架构概览.md",
    )
    out = _service(root)._enforce_qoder_page_contract(
        page,
        _pad("# 整体架构概览\n\n## 简介\n\nFastAPI 路由与仓储协作。\n"),
        None,
        add_mermaid=False,
    )
    assert "ccagent" not in out
    assert "probe-agent" not in out
    assert "ccprobe-control" not in out


def test_health_port_is_not_rewritten(tmp_path: Path) -> None:
    root = tmp_path
    (root / "cmd" / "svc").mkdir(parents=True)
    (root / "cmd" / "svc" / "main.go").write_text(
        'package main\nfunc main() { http.ListenAndServe(":1900", nil) }\n',
        encoding="utf-8",
    )
    (root / "config.go").write_text('Listen: ":1900"\n', encoding="utf-8")
    page = _page(
        "health-check", "健康检查", WikiTaxonomyCategory.DEPLOYMENT_OPERATIONS, "健康检查.md"
    )
    markdown = _pad("# 健康检查\n\n探测 `http://localhost:8080/health`。\n")
    out = _service(root)._enforce_qoder_page_contract(page, markdown, None, add_mermaid=False)
    assert "`http://localhost:8080/health`" in out
    assert "localhost:1900" not in out


def test_no_architecture_filler_sentences(tmp_path: Path) -> None:
    _write_probe_mains(tmp_path)
    (tmp_path / "internal" / "agent").mkdir(parents=True)
    (tmp_path / "internal" / "agent" / "pool.go").write_text("package agent\n", encoding="utf-8")
    page = _page(
        "architecture-overview",
        "整体架构概览",
        WikiTaxonomyCategory.ARCHITECTURE_DESIGN,
        "架构设计/整体架构概览.md",
    )
    markdown = _pad("# 整体架构概览\n\n## 简介\n\n模块按 cmd 与 internal 拆分。\n")
    out = _service(tmp_path)._enforce_qoder_page_contract(page, markdown, None, add_mermaid=False)
    assert "是仓库中的实现包" not in out
