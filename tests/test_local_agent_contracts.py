from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from repo_wiki.cli import app
from repo_wiki.local_agent import build_graph_contract, build_search_contract

runner = CliRunner()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _release_root(root: Path) -> Path:
    return root / ".repo-agent-eval" / "repowiki" / "zh"


def _write_ready_release(root: Path, *, commit: str | None = None, status: str = "READY") -> Path:
    rel = _release_root(root)
    (rel / "content" / "guide").mkdir(parents=True, exist_ok=True)
    (rel / "content" / "guide" / "search.md").write_text(
        "# Search Guide\n\nSearch uses READY content and cites source lines.\n"
        "<cite>repo_wiki/cli.py:40-65 (search command)</cite>\n"
        "<cite>/tmp/unsafe.py:1-2</cite>\n"
        "<cite>../secret.py:3-4</cite>\n"
        "token=sk-abcdefghijklmnop should not leak.\n",
        encoding="utf-8",
    )
    _write_json(
        rel / "meta" / "page-registry.json",
        {
            "schema_version": "repo_agent.page_registry/1.0",
            "generated_at": "2026-07-15T00:00:00Z",
            "pages": [
                {
                    "page_id": "search-guide",
                    "relative_path": "guide/search.md",
                    "category": "guide",
                    "page_type": "markdown",
                    "title": "Search Guide",
                }
            ],
        },
    )
    _write_json(
        rel / "meta" / "evidence-index.json",
        {
            "schema_version": "repo_agent.evidence_index/1.0",
            "generated_at": "2026-07-15T00:00:00Z",
            "spans": [
                {
                    "span_id": "span-1",
                    "page_relative_path": "guide/search.md",
                    "source_path": "repo_wiki/local_agent/contracts.py",
                    "start_line": 10,
                    "end_line": 20,
                }
            ],
        },
    )
    _write_json(
        rel / "meta" / "service-registry.json",
        {
            "schema_version": "repo_agent.service_registry/1.0",
            "generated_at": "2026-07-15T00:00:00Z",
            "services": [
                {
                    "service_id": "repo_wiki.local_agent",
                    "display_name": "Local Agent",
                    "runtime_family": "python",
                    "dependencies": ["repo_wiki.cli"],
                    "api_key": "sk-should-not-appear",
                },
                {
                    "service_id": "repo_wiki.cli",
                    "display_name": "CLI",
                    "runtime_family": "python",
                },
            ],
        },
    )
    _write_json(
        rel / "meta" / "repowiki-metadata.json",
        {
            "knowledge_relations": [
                {"from": "repo_wiki.cli", "to": "repo_wiki.local_agent", "type": "uses"}
            ]
        },
    )
    _write_json(
        rel / "manifest.json",
        {
            "release_status": status,
            "readiness": status,
            "release_id": "release-run-1",
            "source_run_id": "run-1",
            "published_at": "2026-07-15T00:00:00Z",
            "generated_at": "2026-07-14T00:00:00Z",
            "content_root": "content",
            "meta_root": "meta",
            "target_git_commit": commit,
            "metadata": {"repository_identity": {"name": "sample", "display_name": "Sample"}},
        },
    )
    return rel


def _write_release_meta(
    rel: Path,
    *,
    release_id: str = "release-run-1",
    source_run_id: str = "run-1",
    published_at: str = "2026-07-15T01:00:00Z",
    target_git_commit: str | None = None,
    release_status: str = "READY",
) -> None:
    _write_json(
        rel / "meta" / "release.json",
        {
            "schema_version": "repo_agent.meta_release/1.0",
            "release_status": release_status,
            "release_id": release_id,
            "source_run_id": source_run_id,
            "published_at": published_at,
            "target_git_commit": target_git_commit,
            "manifest_path": ".repo-agent-eval/repowiki/zh/manifest.json",
        },
    )


def _snapshot_tree(root: Path) -> dict[str, tuple[str, str]]:
    snapshot: dict[str, tuple[str, str]] = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        stat = path.lstat()
        if path.is_symlink():
            snapshot[rel] = ("symlink", os.readlink(path))
        elif path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            snapshot[rel] = ("file", f"{stat.st_mode}:{stat.st_size}:{digest}")
        elif path.is_dir():
            snapshot[rel] = ("dir", f"{stat.st_mode}")
        else:
            snapshot[rel] = ("other", f"{stat.st_mode}")
    return snapshot


def _assert_no_absolute_paths(payload: Any, root: Path) -> None:
    root_text = str(root)
    if isinstance(payload, dict):
        for value in payload.values():
            _assert_no_absolute_paths(value, root)
    elif isinstance(payload, list):
        for value in payload:
            _assert_no_absolute_paths(value, root)
    elif isinstance(payload, str):
        assert root_text not in payload
        assert not payload.startswith("/")


def _init_git(root: Path) -> str:
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "a@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "A"], cwd=root, check=True)
    (root / "tracked.txt").write_text("one\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=root, check=True)
    subprocess.run(
        ["git", "commit", "-m", "init"], cwd=root, check=True, capture_output=True, text=True
    )
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()


def test_search_success_citations_ranges_and_ready_provenance(tmp_path: Path) -> None:
    head = _init_git(tmp_path)
    _write_ready_release(tmp_path, commit=head)

    payload, exit_code = build_search_contract(tmp_path, query="READY source lines", top_k=5)

    assert exit_code == 0
    assert payload["schema_version"] == "repo_agent.search/1.0"
    assert payload["status"] == "ok"
    assert payload["release"]["source_run_id"] == "run-1"
    assert payload["freshness"]["status"] == "fresh"
    assert payload["query"] == "READY source lines"
    assert payload["top_k"] == 5
    assert payload["diagnostics"]["readonly"] is True
    result = payload["results"][0]
    assert result["page_path"] == "guide/search.md"
    assert result["file_path"] == "repo_wiki/local_agent/contracts.py"
    assert result["line_start"] == 10
    assert result["start_line"] == 10
    assert result["line_range"] == {"start": 10, "end": 20}
    assert result["citations"][0]["source"] == "repo_wiki/local_agent/contracts.py"
    all_sources = {c["source"] for c in result["citations"]}
    assert "/tmp/unsafe.py" not in all_sources
    assert "../secret.py" not in all_sources
    assert "sk-abcdefghijklmnop" not in result["excerpt"]


def test_search_missing_nonready_and_malformed_are_structured_json(tmp_path: Path) -> None:
    missing, missing_code = build_search_contract(tmp_path, query="x")
    assert missing_code == 1
    assert missing["status"] == "error"
    assert missing["error"]["code"] == "release_missing"
    assert missing["results"] == []

    _write_ready_release(tmp_path, status="DRAFT")
    nonready, nonready_code = build_search_contract(tmp_path, query="x")
    assert nonready_code == 1
    assert nonready["error"]["code"] == "release_not_ready"

    manifest = _release_root(tmp_path) / "manifest.json"
    manifest.write_text("{not-json", encoding="utf-8")
    malformed, malformed_code = build_search_contract(tmp_path, query="x")
    assert malformed_code == 1
    assert malformed["error"]["code"] == "manifest_malformed"


def test_freshness_stale_and_unknown(tmp_path: Path) -> None:
    head = _init_git(tmp_path)
    _write_ready_release(tmp_path, commit="0" * 40)
    stale, _ = build_search_contract(tmp_path, query="Search")
    assert stale["freshness"]["head"] == head
    assert stale["freshness"]["status"] == "stale"

    no_git = tmp_path / "nogit"
    no_git.mkdir()
    _write_ready_release(no_git, commit="0" * 40)
    unknown, _ = build_search_contract(no_git, query="Search")
    assert unknown["freshness"]["status"] == "unknown"


def test_graph_deterministic_and_secret_scrubbed(tmp_path: Path) -> None:
    _write_ready_release(tmp_path)

    first, code = build_graph_contract(tmp_path, module="repo_wiki.local_agent")
    second, code2 = build_graph_contract(tmp_path, module="repo_wiki.local_agent")

    assert code == code2 == 0
    assert first == second
    assert first["schema_version"] == "repo_agent.graph/1.0"
    assert first["found"] is True
    assert first["node"]["id"] == "repo_wiki.local_agent"
    assert "api_key" not in first["node"]
    assert first["edges"] == sorted(first["edges"], key=lambda e: (e["from"], e["to"], e["type"]))

    missing, _ = build_graph_contract(tmp_path, module="missing")
    assert missing["found"] is False
    assert missing["suggestions"] == sorted(missing["suggestions"])


def test_cli_error_stdout_json_nonzero_no_traceback(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["search", "anything"])

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "error"
    assert "Traceback" not in result.stdout
    assert "Traceback" not in result.stderr


def test_no_mutation_and_no_unready_run_consumption(tmp_path: Path) -> None:
    unready = tmp_path / ".repo-agent-eval" / "runs" / "newer" / "repowiki" / "zh"
    _write_json(unready / "manifest.json", {"release_status": "READY", "content_root": "content"})
    before = sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*"))

    payload, code = build_search_contract(tmp_path, query="newer")

    after = sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*"))
    assert code == 1
    assert payload["error"]["code"] == "release_missing"
    assert before == after


def test_search_required_sidecars_missing_or_malformed_are_structured(tmp_path: Path) -> None:
    rel = _write_ready_release(tmp_path)
    (rel / "meta" / "page-registry.json").unlink()

    missing, missing_code = build_search_contract(tmp_path, query="Search")

    assert missing_code == 1
    assert missing["status"] == "error"
    assert missing["error"]["code"] == "search_sidecar_missing"
    assert missing["results"] == []

    rel = _write_ready_release(tmp_path)
    (rel / "meta" / "evidence-index.json").write_text("{not-json", encoding="utf-8")

    malformed, malformed_code = build_search_contract(tmp_path, query="Search")

    assert malformed_code == 1
    assert malformed["status"] == "error"
    assert malformed["error"]["code"] == "search_sidecar_malformed"
    assert malformed["results"] == []


def test_search_accepts_compatible_sidecar_versions_and_unknown_fields(tmp_path: Path) -> None:
    rel = _write_ready_release(tmp_path)
    registry = json.loads((rel / "meta" / "page-registry.json").read_text(encoding="utf-8"))
    registry["schema_version"] = "repo_agent.page_registry/1.7"
    registry["unknown_future_field"] = {"ok": True}
    registry["pages"][0]["aliases"] = ["ready search", "contracts"]
    _write_json(rel / "meta" / "page-registry.json", registry)
    evidence = json.loads((rel / "meta" / "evidence-index.json").read_text(encoding="utf-8"))
    evidence["schema_version"] = "repo_agent.evidence_index/1.7"
    evidence["spans"][0]["extra"] = "ignored"
    _write_json(rel / "meta" / "evidence-index.json", evidence)

    payload, code = build_search_contract(tmp_path, query="READY")

    assert code == 0
    assert payload["results"][0]["aliases"] == ["ready search", "contracts"]


def test_search_rejects_incompatible_sidecar_major_with_structured_error(tmp_path: Path) -> None:
    rel = _write_ready_release(tmp_path)
    registry = json.loads((rel / "meta" / "page-registry.json").read_text(encoding="utf-8"))
    registry["schema_version"] = "repo_agent.page_registry/2.0"
    _write_json(rel / "meta" / "page-registry.json", registry)

    payload, code = build_search_contract(tmp_path, query="READY")

    assert code == 1
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "search_sidecar_malformed"
    assert "schema_version major must be 1" in payload["error"]["message"]
    assert payload["results"] == []


def test_release_meta_accepts_compatible_minor_and_rejects_incompatible_major(
    tmp_path: Path,
) -> None:
    rel = _write_ready_release(tmp_path)
    _write_release_meta(rel)
    meta_path = rel / "meta" / "release.json"
    release_meta = json.loads(meta_path.read_text(encoding="utf-8"))
    release_meta["schema_version"] = "repo_agent.meta_release/1.7"
    _write_json(meta_path, release_meta)

    accepted, accepted_code = build_search_contract(tmp_path, query="READY")

    assert accepted_code == 0
    assert accepted["status"] == "ok"

    release_meta["schema_version"] = "repo_agent.meta_release/2.0"
    _write_json(meta_path, release_meta)

    rejected, rejected_code = build_search_contract(tmp_path, query="READY")

    assert rejected_code == 1
    assert rejected["status"] == "error"
    assert rejected["error"]["code"] == "release_meta_invalid"
    assert "schema_version major must be 1" in rejected["error"]["message"]
    assert rejected["results"] == []


def test_output_has_workspace_relative_paths_and_dot_repo_root(tmp_path: Path) -> None:
    _write_ready_release(tmp_path)

    search_payload, search_code = build_search_contract(tmp_path, query="READY")
    graph_payload, graph_code = build_graph_contract(tmp_path, module="repo_wiki.local_agent")

    assert search_code == graph_code == 0
    assert search_payload["repo"]["root"] == "."
    assert graph_payload["repo"]["root"] == "."
    _assert_no_absolute_paths(search_payload, tmp_path)
    _assert_no_absolute_paths(graph_payload, tmp_path)


def test_release_meta_is_preferred_for_provenance_and_freshness(tmp_path: Path) -> None:
    head = _init_git(tmp_path)
    rel = _write_ready_release(tmp_path, commit=None)
    manifest = json.loads((rel / "manifest.json").read_text(encoding="utf-8"))
    manifest.pop("release_id")
    manifest.pop("source_run_id")
    manifest.pop("target_git_commit")
    _write_json(rel / "manifest.json", manifest)
    _write_release_meta(
        rel,
        release_id="release-meta-1",
        source_run_id="run-meta-1",
        published_at="2026-07-15T02:00:00Z",
        target_git_commit=head,
    )

    payload, code = build_search_contract(tmp_path, query="READY")

    assert code == 0
    assert payload["release"]["release_id"] == "release-meta-1"
    assert payload["release"]["source_run_id"] == "run-meta-1"
    assert payload["release"]["published_at"] == "2026-07-15T02:00:00Z"
    assert payload["freshness"]["status"] == "fresh"
    assert payload["freshness"]["release_commit"] == head


def test_release_meta_malformed_and_inconsistent_are_structured(tmp_path: Path) -> None:
    rel = _write_ready_release(tmp_path)
    (rel / "meta" / "release.json").write_text("{not-json", encoding="utf-8")

    malformed, malformed_code = build_search_contract(tmp_path, query="READY")

    assert malformed_code == 1
    assert malformed["error"]["code"] == "release_meta_malformed"
    assert malformed["results"] == []

    rel = _write_ready_release(tmp_path)
    _write_release_meta(rel, release_id="different-release")

    inconsistent, inconsistent_code = build_search_contract(tmp_path, query="READY")

    assert inconsistent_code == 1
    assert inconsistent["error"]["code"] == "release_meta_invalid"
    assert "does not match manifest" in inconsistent["error"]["message"]

    rel = _write_ready_release(tmp_path)
    _write_release_meta(rel, release_status="NOT_READY")

    not_ready, not_ready_code = build_search_contract(tmp_path, query="READY")

    assert not_ready_code == 1
    assert not_ready["error"]["code"] == "release_meta_invalid"


def test_registry_pages_without_safe_content_or_citations_are_not_synthetic(tmp_path: Path) -> None:
    rel = _write_ready_release(tmp_path)
    (rel / "content" / "guide" / "no-cites.md").write_text(
        "# No Cites\n\nneedle text with only unsafe evidence.\n", encoding="utf-8"
    )
    registry = json.loads((rel / "meta" / "page-registry.json").read_text(encoding="utf-8"))
    registry["pages"].extend(
        [
            {
                "page_id": "missing",
                "relative_path": "guide/missing.md",
                "category": "guide",
                "page_type": "markdown",
                "title": "Missing Needle",
            },
            {
                "page_id": "no-cites",
                "relative_path": "guide/no-cites.md",
                "category": "guide",
                "page_type": "markdown",
                "title": "No Cites",
            },
        ]
    )
    _write_json(rel / "meta" / "page-registry.json", registry)
    evidence = json.loads((rel / "meta" / "evidence-index.json").read_text(encoding="utf-8"))
    evidence["spans"].append(
        {
            "span_id": "unsafe",
            "page_relative_path": "guide/no-cites.md",
            "source_path": str(tmp_path / "absolute.py"),
            "start_line": 1,
            "end_line": 2,
        }
    )
    _write_json(rel / "meta" / "evidence-index.json", evidence)

    payload, code = build_search_contract(tmp_path, query="needle")

    assert code == 0
    assert payload["results"] == []


def test_search_rejects_symlink_component_escape(tmp_path: Path) -> None:
    rel = _write_ready_release(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "escape.md").write_text(
        "# Escape\n\nsymlink needle <cite>repo_wiki/cli.py:1-2</cite>\n", encoding="utf-8"
    )
    link = rel / "content" / "linked"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlinks unsupported: {exc}")
    registry = json.loads((rel / "meta" / "page-registry.json").read_text(encoding="utf-8"))
    registry["pages"].append(
        {
            "page_id": "escape",
            "relative_path": "linked/escape.md",
            "category": "guide",
            "page_type": "markdown",
            "title": "Escape",
        }
    )
    _write_json(rel / "meta" / "page-registry.json", registry)
    evidence = json.loads((rel / "meta" / "evidence-index.json").read_text(encoding="utf-8"))
    evidence["spans"].append(
        {
            "span_id": "escape",
            "page_relative_path": "linked/escape.md",
            "source_path": "repo_wiki/cli.py",
            "start_line": 1,
            "end_line": 2,
        }
    )
    _write_json(rel / "meta" / "evidence-index.json", evidence)

    payload, code = build_search_contract(tmp_path, query="symlink needle")

    assert code == 0
    assert all(result["page_path"] != "linked/escape.md" for result in payload["results"])


def test_default_content_root_symlink_outside_fails_closed_and_does_not_mutate(
    tmp_path: Path,
) -> None:
    rel = _write_ready_release(tmp_path)
    outside = tmp_path / "outside-content"
    outside.mkdir()
    (outside / "search.md").write_text(
        "# Outside\n\nleaked needle <cite>repo_wiki/cli.py:1-2</cite>\n", encoding="utf-8"
    )
    shutil.rmtree(rel / "content")
    try:
        (rel / "content").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlinks unsupported: {exc}")
    before = _snapshot_tree(tmp_path)

    search_payload, search_code = build_search_contract(tmp_path, query="leaked needle")
    graph_payload, graph_code = build_graph_contract(tmp_path, module="repo_wiki.local_agent")

    assert search_code == graph_code == 1
    assert search_payload["status"] == graph_payload["status"] == "error"
    assert (
        search_payload["error"]["code"] == graph_payload["error"]["code"] == "release_path_invalid"
    )
    assert "symlink" in search_payload["error"]["message"]
    assert search_payload["results"] == []
    assert graph_payload["node"] is None
    assert graph_payload["edges"] == []
    assert _snapshot_tree(tmp_path) == before


def test_default_meta_root_symlink_outside_fails_closed_and_does_not_mutate(tmp_path: Path) -> None:
    rel = _write_ready_release(tmp_path)
    outside = tmp_path / "outside-meta"
    outside.mkdir()
    _write_json(
        outside / "service-registry.json",
        {
            "schema_version": "repo_agent.service_registry/1.0",
            "generated_at": "2026-07-15T00:00:00Z",
            "services": [{"service_id": "outside.secret"}],
        },
    )
    shutil.rmtree(rel / "meta")
    try:
        (rel / "meta").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlinks unsupported: {exc}")
    before = _snapshot_tree(tmp_path)

    search_payload, search_code = build_search_contract(tmp_path, query="Search")
    graph_payload, graph_code = build_graph_contract(tmp_path, module="outside.secret")

    assert search_code == graph_code == 1
    assert (
        search_payload["error"]["code"] == graph_payload["error"]["code"] == "release_path_invalid"
    )
    assert "symlink" in graph_payload["error"]["message"]
    assert search_payload["results"] == []
    assert graph_payload["found"] is False
    assert graph_payload["node"] is None
    assert graph_payload["edges"] == []
    assert _snapshot_tree(tmp_path) == before


def test_graph_rejects_incompatible_service_registry_major_even_with_metadata_fallback(
    tmp_path: Path,
) -> None:
    rel = _write_ready_release(tmp_path)
    registry = json.loads((rel / "meta" / "service-registry.json").read_text(encoding="utf-8"))
    registry["schema_version"] = "repo_agent.service_registry/2.0"
    _write_json(rel / "meta" / "service-registry.json", registry)

    payload, code = build_graph_contract(tmp_path, module="repo_wiki.local_agent")

    assert code == 1
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "graph_metadata_invalid"
    assert payload["found"] is False
    assert payload["node"] is None
    assert payload["edges"] == []
    assert "schema_version major must be 1" in ";".join(
        payload["diagnostics"]["graph_source_errors"]
    )


def test_graph_no_usable_metadata_is_nonzero_and_does_not_use_page_registry(tmp_path: Path) -> None:
    rel = _write_ready_release(tmp_path)
    (rel / "meta" / "service-registry.json").unlink()
    (rel / "meta" / "repowiki-metadata.json").unlink()

    payload, code = build_graph_contract(tmp_path, module="search")

    assert code == 1
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "graph_metadata_unavailable"
    assert payload["found"] is False
    assert payload["suggestions"] == []
    assert payload["node"] is None
    assert payload["edges"] == []


def test_search_and_graph_leave_filesystem_unchanged(tmp_path: Path) -> None:
    _write_ready_release(tmp_path)
    before = _snapshot_tree(tmp_path)

    search_payload, search_code = build_search_contract(tmp_path, query="READY")
    graph_payload, graph_code = build_graph_contract(tmp_path, module="repo_wiki.local_agent")

    assert search_code == graph_code == 0
    assert search_payload["status"] == graph_payload["status"] == "ok"
    assert _snapshot_tree(tmp_path) == before
