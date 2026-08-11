from __future__ import annotations

import json

from repo_wiki.verifier.blind_review_matrix import (
    BLIND_REVIEW_MATRIX_SCHEMA_VERSION,
    DIMENSIONS,
    blind_review_matrix_report,
    blind_review_matrix_to_json,
    evaluate_blind_review_matrix,
    load_blind_review_matrix,
)


def _hash(seed: str) -> str:
    return (seed * 64)[:64]


def _matrix(*, classes: int = 5, repo_agent_score: float = 4.0, qoder_score: float = 3.0) -> dict:
    candidates = [
        {
            "candidate_id": "cand-a",
            "system": "repo-agent",
            "artifact_hash": _hash("a"),
            "provenance_hash": _hash("b"),
        },
        {
            "candidate_id": "cand-b",
            "system": "qoder",
            "artifact_hash": _hash("c"),
            "provenance_hash": _hash("d"),
        },
    ]
    records = []
    repo_classes = [
        "python-cli",
        "typescript-extension",
        "monorepo-service",
        "docs-heavy",
        "polyglot-runtime",
    ][:classes]
    for repo_class in repo_classes:
        records.append(
            {
                "repo_class": repo_class,
                "candidate_id": "cand-a",
                "case_id": f"{repo_class}-a",
                "scores": {dimension: repo_agent_score for dimension in DIMENSIONS},
                "critical_false_facts": 0,
            }
        )
        records.append(
            {
                "repo_class": repo_class,
                "candidate_id": "cand-b",
                "case_id": f"{repo_class}-b",
                "scores": {dimension: qoder_score for dimension in DIMENSIONS},
                "critical_false_facts": 0,
            }
        )
    return {
        "schema_version": BLIND_REVIEW_MATRIX_SCHEMA_VERSION,
        "reviewer_identity_hash": _hash("e"),
        "candidates": candidates,
        "records": records,
    }


def test_four_classes_fail_representative_class_gate() -> None:
    evaluation = evaluate_blind_review_matrix(load_blind_review_matrix(_matrix(classes=4)))

    assert evaluation.status == "FAIL"
    assert any(f.code == "BLIND_REVIEW_CLASS_COVERAGE_LOW" for f in evaluation.failures)


def test_five_classes_pass_only_when_all_repo_agent_medians_meet_qoder() -> None:
    passing = evaluate_blind_review_matrix(load_blind_review_matrix(_matrix()))
    assert passing.status == "PASS"
    assert passing.medians["repo-agent"]["accuracy"] == 4.0
    assert passing.medians["qoder"]["accuracy"] == 3.0
    assert passing.class_medians["python-cli"]["repo-agent"]["accuracy"] == 4.0

    failing_payload = _matrix(repo_agent_score=2.0, qoder_score=3.0)
    failing = evaluate_blind_review_matrix(load_blind_review_matrix(failing_payload))
    assert failing.status == "FAIL"
    assert any(f.code == "BLIND_REVIEW_MEDIAN_BELOW_QODER" for f in failing.failures)


def test_per_class_median_gate_blocks_global_aggregate_bypass() -> None:
    payload = _matrix()
    for record in payload["records"]:
        is_last_class = record["repo_class"] == "polyglot-runtime"
        is_repo_agent = record["candidate_id"] == "cand-a"
        record["scores"] = {
            dimension: 1.0
            if is_last_class and is_repo_agent
            else 3.0
            if is_last_class
            else 5.0
            if is_repo_agent
            else 4.0
            for dimension in DIMENSIONS
        }

    evaluation = evaluate_blind_review_matrix(load_blind_review_matrix(payload))

    assert evaluation.status == "FAIL"
    assert evaluation.medians["repo-agent"]["accuracy"] == 5.0
    assert evaluation.medians["qoder"]["accuracy"] == 4.0
    assert any(f.code == "BLIND_REVIEW_CLASS_MEDIAN_BELOW_QODER" for f in evaluation.failures)


def test_five_repo_agent_classes_plus_one_qoder_class_fails_pairing_gate() -> None:
    payload = _matrix()
    payload["records"] = [
        record
        for record in payload["records"]
        if record["candidate_id"] == "cand-a" or record["repo_class"] == "python-cli"
    ]

    evaluation = evaluate_blind_review_matrix(load_blind_review_matrix(payload))

    assert evaluation.status == "FAIL"
    codes = {f.code for f in evaluation.failures}
    assert "BLIND_REVIEW_CLASS_COUNTERPART_MISSING" in codes
    assert "BLIND_REVIEW_CLASS_SYSTEM_INCOMPLETE" in codes


def test_any_critical_false_fact_fails() -> None:
    payload = _matrix()
    payload["records"][0]["critical_false_facts"] = 1

    evaluation = evaluate_blind_review_matrix(load_blind_review_matrix(payload))

    assert evaluation.status == "FAIL"
    assert any(f.code == "BLIND_REVIEW_CRITICAL_FALSE_FACTS_PRESENT" for f in evaluation.failures)


def test_unblinded_source_label_leak_fails() -> None:
    payload = _matrix()
    payload["records"][0]["source"] = "repo-agent"
    payload["records"][1]["reviewer_notes"] = "Qoder output was shorter"

    evaluation = evaluate_blind_review_matrix(load_blind_review_matrix(payload))

    assert evaluation.status == "FAIL"
    assert any(f.code == "BLIND_REVIEW_UNBLINDED_SCORING_RECORD" for f in evaluation.failures)


def test_duplicate_class_hash_and_provenance_gaps_fail() -> None:
    payload = _matrix()
    payload["records"].append(dict(payload["records"][0], case_id="duplicate"))
    payload["candidates"][0]["provenance_hash"] = ""

    evaluation = evaluate_blind_review_matrix(load_blind_review_matrix(payload))

    codes = {f.code for f in evaluation.failures}
    assert "BLIND_REVIEW_DUPLICATE_CLASS_HASH" in codes
    assert "BLIND_REVIEW_DUPLICATE_PAIR_IDENTITY" in codes
    assert "BLIND_REVIEW_PROVENANCE_GAP" in codes


def test_cross_rubric_or_revision_mismatch_fails() -> None:
    payload = _matrix()
    payload["records"][0]["rubric_id"] = "g005-rubric"
    payload["records"][1]["rubric_id"] = "other-rubric"
    payload["records"][2]["revision_id"] = "round-2"
    payload["records"][3]["revision_id"] = "round-1"

    evaluation = evaluate_blind_review_matrix(load_blind_review_matrix(payload))

    assert evaluation.status == "FAIL"
    assert any(f.code == "BLIND_REVIEW_RUBRIC_REVISION_MISMATCH" for f in evaluation.failures)


def test_deterministic_json_roundtrip(tmp_path) -> None:
    payload = _matrix()
    matrix = load_blind_review_matrix(payload)
    first_json = blind_review_matrix_to_json(matrix)
    second_json = blind_review_matrix_to_json(load_blind_review_matrix(first_json))
    assert first_json == second_json

    evaluation = evaluate_blind_review_matrix(load_blind_review_matrix(json.loads(second_json)))
    report_path = tmp_path / "blind-review-matrix-v3.json"
    first_report = blind_review_matrix_report(evaluation, path=report_path)
    second_report = blind_review_matrix_report(evaluation)

    assert report_path.read_text(encoding="utf-8").strip() == first_report
    assert first_report == second_report
    assert json.loads(first_report)["status"] == "PASS"
