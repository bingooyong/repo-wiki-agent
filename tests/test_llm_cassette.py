"""Record/replay raw LLM replies for offline generate (Round 12 Part A)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.generator.composer import ComposerContext, LLMPageComposer, build_composer_input
from repo_wiki.llm.config import LLMProviderConfig
from repo_wiki.llm.models import ChatMessage, ChatRequest, NonRetryableError
from repo_wiki.llm.providers import create_mock_provider
from repo_wiki.orchestration.eval_layout import EvalOutputProfile
from repo_wiki.orchestration.service import RepoWikiService
from repo_wiki.planner.schema import (
    GenerationMode,
    SourceRequirement,
    WikiPagePlan,
    WikiTaxonomyCategory,
)
from tests.handbook_pad import pad_handbook_markdown

RAW_REPLY = "<think>internal scratch, must not reach the page</think>\n" + pad_handbook_markdown(
    "# Sample Page\n\nRecorded raw model text for cassette replay.\n"
)


def _sample_page() -> WikiPagePlan:
    return WikiPagePlan(
        page_id="sample-page",
        title="Sample Page",
        category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
        output_path="docs/sample.md",
        source_requirements=SourceRequirement(modules=["auth"], endpoints=["GET /users"]),
        generation_mode=GenerationMode.LLM_ASSISTED,
    )


def _sample_context() -> ComposerContext:
    return ComposerContext(
        repository_name="test-repo",
        primary_language="python",
        framework="fastapi",
        repository_root=".",
    )


def _jsonl_rows(path: Path) -> list[dict]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _write_cassette(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_record_appends_jsonl_per_call_llm_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cassette_dir = tmp_path / "cassettes"
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setenv("REPO_WIKI_LLM_CASSETTE_DIR", str(cassette_dir))
    provider = create_mock_provider(response_content=RAW_REPLY)
    composer = LLMPageComposer(llm_provider=provider, llm_config=LLMProviderConfig(provider="mock"))
    output = asyncio.run(
        composer.compose_page(build_composer_input(_sample_page(), None, _sample_context()))
    )
    assert output.rejected is False
    rows = []
    for jsonl in cassette_dir.glob("*.jsonl"):
        rows.extend(_jsonl_rows(jsonl))
    assert len(rows) >= 1
    row = rows[0]
    assert row["page_id"] == "sample-page"
    assert row["attempt"] == 0
    assert row["input_hash"]
    assert row["prompt_hash"]
    assert row["generator_version"]
    assert row["model"]
    assert isinstance(row["messages"], list)
    assert row["messages"][0]["role"] == "system"
    assert row["raw_reply"] == RAW_REPLY
    assert "usage" in row
    assert "<think>" in row["raw_reply"]
    assert "<think>" not in output.markdown


def test_record_never_writes_api_keys_or_auth_headers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cassette_dir = tmp_path / "cassettes"
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setenv("REPO_WIKI_LLM_CASSETTE_DIR", str(cassette_dir))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret-cassette-key-1234567890abcd")
    provider = create_mock_provider(response_content=pad_handbook_markdown("# Page\n\nsafe"))
    composer = LLMPageComposer(llm_provider=provider, llm_config=LLMProviderConfig(provider="mock"))
    asyncio.run(
        composer.compose_page(build_composer_input(_sample_page(), None, _sample_context()))
    )
    blob = "".join(p.read_text(encoding="utf-8") for p in cassette_dir.glob("*.jsonl"))
    assert "sk-secret-cassette-key-1234567890abcd" not in blob
    assert "Authorization" not in blob
    for row in _jsonl_rows(next(cassette_dir.glob("*.jsonl"))):
        assert "extra_headers" not in row
        assert "headers" not in row
        assert "authorization" not in json.dumps(row).lower()


@pytest.mark.asyncio
async def test_cassette_provider_serves_by_page_id_and_attempt(tmp_path: Path) -> None:
    from repo_wiki.llm.cassette import CassetteLLMProvider, set_cassette_call_context

    jsonl = tmp_path / "llm-cassette.jsonl"
    _write_cassette(
        jsonl,
        [
            {
                "page_id": "overview",
                "attempt": 0,
                "prompt_hash": "aaa",
                "raw_reply": "first-attempt-overview",
                "model": "cassette-model",
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
            {
                "page_id": "overview",
                "attempt": 1,
                "prompt_hash": "bbb",
                "raw_reply": "second-attempt-overview",
                "model": "cassette-model",
            },
        ],
    )
    provider = CassetteLLMProvider.from_dir(tmp_path)
    set_cassette_call_context(page_id="overview", attempt=0, prompt_hash="aaa")
    first = await provider.chat(
        ChatRequest(messages=[ChatMessage(role="user", content="x")], model="cassette-model")
    )
    assert first.content == "first-attempt-overview"
    set_cassette_call_context(page_id="overview", attempt=1, prompt_hash="bbb")
    second = await provider.chat(
        ChatRequest(messages=[ChatMessage(role="user", content="x")], model="cassette-model")
    )
    assert second.content == "second-attempt-overview"


@pytest.mark.asyncio
async def test_cassette_provider_prompt_hash_mismatch_falls_back_to_page_id(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    from repo_wiki.llm.cassette import CassetteLLMProvider, set_cassette_call_context

    _write_cassette(
        tmp_path / "llm-cassette.jsonl",
        [
            {
                "page_id": "overview",
                "attempt": 0,
                "prompt_hash": "old-hash",
                "raw_reply": "fallback-body",
                "model": "cassette-model",
            }
        ],
    )
    provider = CassetteLLMProvider.from_dir(tmp_path)
    set_cassette_call_context(page_id="overview", attempt=0, prompt_hash="new-hash")
    with caplog.at_level("WARNING"):
        response = await provider.chat(
            ChatRequest(messages=[ChatMessage(role="user", content="x")], model="cassette-model")
        )
    assert response.content == "fallback-body"
    assert provider.prompt_mismatches
    assert provider.prompt_mismatches[0]["page_id"] == "overview"
    assert "cassette_prompt_mismatch" in caplog.text or "prompt" in caplog.text.lower()


@pytest.mark.asyncio
async def test_cassette_provider_unknown_page_fails_loudly(tmp_path: Path) -> None:
    from repo_wiki.llm.cassette import CassetteLLMProvider, set_cassette_call_context

    _write_cassette(tmp_path / "llm-cassette.jsonl", [])
    provider = CassetteLLMProvider.from_dir(tmp_path)
    set_cassette_call_context(page_id="missing-page", attempt=0, prompt_hash="x")
    with pytest.raises(NonRetryableError):
        await provider.chat(
            ChatRequest(messages=[ChatMessage(role="user", content="x")], model="cassette-model")
        )


def test_cassette_provider_resolves_without_api_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from repo_wiki.llm.qoder_like_provider import resolve_qoder_like_llm

    monkeypatch.setenv("LLM_PROVIDER", "cassette")
    monkeypatch.setenv("REPO_WIKI_LLM_CASSETTE_DIR", str(tmp_path))
    monkeypatch.delenv("REPO_WIKI_FORCE_MOCK_LLM", raising=False)
    for name in ("OPENAI_API_KEY", "MINIMAX_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    provider, cfg, summary = resolve_qoder_like_llm(
        llm_config_dict={"provider": "cassette", "model": "cassette", "api_key_env": "UNUSED_KEY"},
        force_mock_llm_config=False,
    )
    assert cfg.provider == "cassette"
    assert getattr(provider, "name", None) == "cassette"
    assert summary["mode"] == "cassette"
    assert summary["mock_reason"] is None


def test_full_generate_offline_from_synthetic_cassette(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A recorded cassette drives a second generate; cleanup runs on raw model text."""
    from repo_wiki.llm.cassette import load_cassette_rows

    repo_root = tmp_path / "target"
    repo_root.mkdir()
    (repo_root / "src").mkdir()
    (repo_root / "src" / "app.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n\n@app.get('/health')\ndef health():\n    return {'ok': True}\n",
        encoding="utf-8",
    )
    (repo_root / "README.md").write_text(
        "# Sample Service\n\nA small test service.\n", encoding="utf-8"
    )

    cassette_dir = tmp_path / "cassettes"
    cassette_dir.mkdir()
    monkeypatch.setenv("REPO_WIKI_LLM_CASSETTE_DIR", str(cassette_dir))
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setenv("REPO_WIKI_FORCE_MOCK_LLM", "1")

    def _cfg(force_mock: bool) -> RepoWikiConfig:
        return RepoWikiConfig.model_validate(
            {
                "project": {
                    "name": "sample",
                    "root": str(repo_root),
                    "include": ["**/*"],
                    "exclude": [".repo-agent-eval/**", ".qoder/**", ".repo-wiki/**"],
                },
                "llm": {
                    "force_mock_llm": force_mock,
                    "provider": "cassette" if not force_mock else "mock",
                },
            }
        )

    profile = EvalOutputProfile(
        name="qoder-like",
        root=str(repo_root / ".repo-agent-eval"),
        create_subdirs=True,
        content_subdir="content",
    )
    RepoWikiService(_cfg(True)).generate(eval_profile=profile, run_id="record-run")
    rows = load_cassette_rows(cassette_dir)
    assert rows, "recording generate must write raw LLM cassette lines"
    assert all(row.get("raw_reply") for row in rows)
    assert all("extra_headers" not in row and "authorization" not in row for row in rows)

    poisoned = []
    for row in rows:
        copy = dict(row)
        copy["raw_reply"] = "<think>scratch-must-not-land</think>\n" + str(row["raw_reply"])
        poisoned.append(copy)
    replay_dir = tmp_path / "replay-cassettes"
    _write_cassette(replay_dir / "llm-cassette.jsonl", poisoned)

    monkeypatch.setenv("REPO_WIKI_LLM_CASSETTE_DIR", str(replay_dir))
    monkeypatch.setenv("LLM_PROVIDER", "cassette")
    monkeypatch.delenv("REPO_WIKI_FORCE_MOCK_LLM", raising=False)
    result = RepoWikiService(_cfg(False)).generate(eval_profile=profile, run_id="replay-run")
    assert result["generate"]["llm"]["effective_provider"] == "cassette"
    assert result["generate"]["llm"]["mode"] == "cassette"
    content_dir = repo_root / ".repo-agent-eval" / "replay-run" / "content"
    pages = list(content_dir.rglob("*.md")) if content_dir.exists() else []
    blob = "\n".join(p.read_text(encoding="utf-8") for p in pages)
    assert "<think>" not in blob
    assert "scratch-must-not-land" not in blob
    dropped = result["generate"]["llm"].get("dropped_page_ids") or []
    assert pages or dropped
