"""Blind review matrix v3 gate for repo-agent versus Qoder comparisons.

The contract is intentionally additive and independent from existing release wiring.
It evaluates blinded scoring records against an explicit candidate manifest so the
review data can remain source-blind while the gate can still compute medians for
repo-agent and Qoder after collection.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median
from typing import Any

BLIND_REVIEW_MATRIX_SCHEMA_VERSION = "blind-review-matrix-v3"
MIN_REPRESENTATIVE_REPO_CLASSES = 5
DIMENSIONS = ("accuracy", "coverage", "navigation", "readability", "actionability")
SYSTEM_REPO_AGENT = "repo-agent"
SYSTEM_QODER = "qoder"
SYSTEMS = (SYSTEM_REPO_AGENT, SYSTEM_QODER)

_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_SOURCE_LABEL_RE = re.compile(r"repo[-_ ]?agent|qoder|baseline|target", re.IGNORECASE)
_SCORING_SOURCE_KEYS = {
    "source",
    "source_label",
    "system",
    "tool",
    "vendor",
    "generator",
    "artifact_hash",
    "provenance",
    "provenance_hash",
}
_ALLOWED_SCORE_KEYS = {
    "repo_class",
    "candidate_id",
    "scores",
    "critical_false_facts",
    "case_id",
    "pair_id",
    "rubric_id",
    "revision_id",
    "reviewer_notes",
}


@dataclass(frozen=True)
class BlindReviewCandidate:
    """A blinded candidate and its unblinding metadata kept outside score rows."""

    candidate_id: str
    system: str
    artifact_hash: str
    provenance_hash: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BlindReviewCandidate:
        return cls(
            candidate_id=str(data.get("candidate_id", "")),
            system=str(data.get("system", "")),
            artifact_hash=str(data.get("artifact_hash", "")),
            provenance_hash=str(data.get("provenance_hash", "")),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "artifact_hash": self.artifact_hash,
            "candidate_id": self.candidate_id,
            "provenance_hash": self.provenance_hash,
            "system": self.system,
        }


@dataclass(frozen=True)
class BlindReviewScore:
    """One source-blind score row for a representative repository class."""

    repo_class: str
    candidate_id: str
    scores: dict[str, float]
    critical_false_facts: int = 0
    case_id: str = ""
    pair_id: str = ""
    rubric_id: str = ""
    revision_id: str = ""
    reviewer_notes: str = ""
    raw_keys: frozenset[str] = field(default_factory=frozenset, repr=False, compare=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BlindReviewScore:
        raw_scores = data.get("scores", {})
        if not isinstance(raw_scores, dict):
            raw_scores = {}
        return cls(
            repo_class=str(data.get("repo_class", "")),
            candidate_id=str(data.get("candidate_id", "")),
            scores={str(k): float(v) for k, v in raw_scores.items() if isinstance(v, int | float)},
            critical_false_facts=int(data.get("critical_false_facts", 0) or 0),
            case_id=str(data.get("case_id", "")),
            pair_id=str(data.get("pair_id", "")),
            rubric_id=str(data.get("rubric_id", "")),
            revision_id=str(data.get("revision_id", "")),
            reviewer_notes=str(data.get("reviewer_notes", "")),
            raw_keys=frozenset(str(k) for k in data.keys()),
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "candidate_id": self.candidate_id,
            "critical_false_facts": self.critical_false_facts,
            "repo_class": self.repo_class,
            "scores": {d: self.scores[d] for d in DIMENSIONS if d in self.scores},
        }
        if self.case_id:
            data["case_id"] = self.case_id
        if self.pair_id:
            data["pair_id"] = self.pair_id
        if self.rubric_id:
            data["rubric_id"] = self.rubric_id
        if self.revision_id:
            data["revision_id"] = self.revision_id
        if self.reviewer_notes:
            data["reviewer_notes"] = self.reviewer_notes
        return data


@dataclass(frozen=True)
class BlindReviewMatrix:
    """Loaded blind review matrix v3 document."""

    reviewer_identity_hash: str
    candidates: list[BlindReviewCandidate]
    records: list[BlindReviewScore]
    schema_version: str = BLIND_REVIEW_MATRIX_SCHEMA_VERSION

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BlindReviewMatrix:
        raw_candidates = data.get("candidates", [])
        raw_records = data.get("records", data.get("scores", []))
        if not isinstance(raw_candidates, list):
            raw_candidates = []
        if not isinstance(raw_records, list):
            raw_records = []
        return cls(
            schema_version=str(data.get("schema_version", BLIND_REVIEW_MATRIX_SCHEMA_VERSION)),
            reviewer_identity_hash=str(data.get("reviewer_identity_hash", "")),
            candidates=[
                BlindReviewCandidate.from_dict(c) for c in raw_candidates if isinstance(c, dict)
            ],
            records=[BlindReviewScore.from_dict(r) for r in raw_records if isinstance(r, dict)],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidates": [
                c.to_dict() for c in sorted(self.candidates, key=lambda c: c.candidate_id)
            ],
            "records": [
                r.to_dict()
                for r in sorted(
                    self.records,
                    key=lambda r: (r.repo_class, r.pair_id, r.candidate_id, r.case_id),
                )
            ],
            "reviewer_identity_hash": self.reviewer_identity_hash,
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True)
class BlindReviewFailure:
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "details": self.details, "message": self.message}


@dataclass(frozen=True)
class BlindReviewEvaluation:
    """Machine-gated v3 evaluation result."""

    status: str
    medians: dict[str, dict[str, float | None]]
    class_medians: dict[str, dict[str, dict[str, float | None]]]
    class_count: int
    critical_false_facts: int
    failures: list[BlindReviewFailure]
    schema_version: str = BLIND_REVIEW_MATRIX_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "class_count": self.class_count,
            "critical_false_facts": self.critical_false_facts,
            "class_medians": self.class_medians,
            "dimensions": list(DIMENSIONS),
            "failures": [f.to_dict() for f in self.failures],
            "medians": self.medians,
            "schema_version": self.schema_version,
            "status": self.status,
            "thresholds": {
                "every_repo_agent_median_gte_qoder": True,
                "min_representative_repo_classes": MIN_REPRESENTATIVE_REPO_CLASSES,
                "zero_critical_false_facts": True,
            },
        }


def load_blind_review_matrix(source: Path | str | dict[str, Any]) -> BlindReviewMatrix:
    """Load a blind review matrix from a path, JSON string, or already-decoded dict."""
    if isinstance(source, dict):
        data = source
    else:
        if isinstance(source, str) and source.lstrip().startswith(("{", "[")):
            data = json.loads(source)
        else:
            text_or_path = Path(source) if not isinstance(source, Path) else source
            if text_or_path.exists():
                data = json.loads(text_or_path.read_text(encoding="utf-8"))
            else:
                data = json.loads(str(source))
    if not isinstance(data, dict):
        raise ValueError("Blind review matrix JSON must be an object")
    return BlindReviewMatrix.from_dict(data)


def evaluate_blind_review_matrix(
    matrix: BlindReviewMatrix | dict[str, Any],
) -> BlindReviewEvaluation:
    """Evaluate the v3 blind review matrix as a hard release gate."""
    if isinstance(matrix, dict):
        matrix = BlindReviewMatrix.from_dict(matrix)

    failures: list[BlindReviewFailure] = []
    candidates_by_id = {c.candidate_id: c for c in matrix.candidates}
    repo_classes = sorted({r.repo_class for r in matrix.records if r.repo_class})

    _validate_schema(matrix, failures)
    _validate_candidates(matrix, failures)
    _validate_blinded_records(matrix, failures)

    if len(repo_classes) < MIN_REPRESENTATIVE_REPO_CLASSES:
        failures.append(
            BlindReviewFailure(
                "BLIND_REVIEW_CLASS_COVERAGE_LOW",
                "Blind review matrix must include at least five distinct representative repo classes",
                {"actual": len(repo_classes), "threshold": MIN_REPRESENTATIVE_REPO_CLASSES},
            )
        )

    missing_candidates = sorted(
        {r.candidate_id for r in matrix.records if r.candidate_id not in candidates_by_id}
    )
    if missing_candidates:
        failures.append(
            BlindReviewFailure(
                "BLIND_REVIEW_CANDIDATE_UNKNOWN",
                "Scoring records reference candidates missing from the candidate manifest",
                {"candidate_ids": missing_candidates},
            )
        )

    _validate_duplicate_class_hash(matrix, candidates_by_id, failures)
    _validate_class_pairs(matrix, candidates_by_id, failures)
    critical_false_facts = sum(max(0, r.critical_false_facts) for r in matrix.records)
    if critical_false_facts:
        failures.append(
            BlindReviewFailure(
                "BLIND_REVIEW_CRITICAL_FALSE_FACTS_PRESENT",
                "Blind review matrix requires zero critical false facts",
                {"actual": critical_false_facts, "threshold": 0},
            )
        )

    medians = _compute_medians(matrix.records, candidates_by_id)
    class_medians = _compute_class_medians(matrix.records, candidates_by_id)
    failures.extend(_median_failures(medians))
    failures.extend(_class_median_failures(class_medians))

    return BlindReviewEvaluation(
        status="PASS" if not failures else "FAIL",
        medians=medians,
        class_medians=class_medians,
        class_count=len(repo_classes),
        critical_false_facts=critical_false_facts,
        failures=failures,
    )


def blind_review_matrix_report(
    evaluation: BlindReviewEvaluation | dict[str, Any],
    *,
    path: Path | None = None,
    indent: int | None = 2,
) -> str:
    """Serialize an evaluation report deterministically as JSON."""
    data = evaluation.to_dict() if isinstance(evaluation, BlindReviewEvaluation) else evaluation
    text = json.dumps(data, ensure_ascii=False, indent=indent, sort_keys=True)
    if path is not None:
        path.write_text(text + "\n", encoding="utf-8")
    return text


def blind_review_matrix_to_json(matrix: BlindReviewMatrix, *, indent: int | None = 2) -> str:
    """Serialize a loaded matrix deterministically for artifact roundtrips."""
    return json.dumps(matrix.to_dict(), ensure_ascii=False, indent=indent, sort_keys=True)


def _validate_schema(matrix: BlindReviewMatrix, failures: list[BlindReviewFailure]) -> None:
    if matrix.schema_version != BLIND_REVIEW_MATRIX_SCHEMA_VERSION:
        failures.append(
            BlindReviewFailure(
                "BLIND_REVIEW_SCHEMA_VERSION_INVALID",
                "Blind review matrix schema version is not v3",
                {"actual": matrix.schema_version, "expected": BLIND_REVIEW_MATRIX_SCHEMA_VERSION},
            )
        )
    if not _is_sha256(matrix.reviewer_identity_hash):
        failures.append(
            BlindReviewFailure(
                "BLIND_REVIEW_REVIEWER_HASH_INVALID",
                "Reviewer identity must be represented by a SHA-256 hash",
                {"field": "reviewer_identity_hash"},
            )
        )


def _validate_candidates(matrix: BlindReviewMatrix, failures: list[BlindReviewFailure]) -> None:
    ids: set[str] = set()
    artifact_hashes: set[str] = set()
    systems_present: set[str] = set()
    duplicate_ids: list[str] = []
    duplicate_hashes: list[str] = []
    provenance_gaps: list[str] = []
    invalid_systems: list[str] = []
    unblinded_ids: list[str] = []

    for candidate in matrix.candidates:
        if candidate.candidate_id in ids:
            duplicate_ids.append(candidate.candidate_id)
        ids.add(candidate.candidate_id)
        if candidate.artifact_hash in artifact_hashes:
            duplicate_hashes.append(candidate.artifact_hash)
        artifact_hashes.add(candidate.artifact_hash)
        if _SOURCE_LABEL_RE.search(candidate.candidate_id):
            unblinded_ids.append(candidate.candidate_id)
        if candidate.system not in SYSTEMS:
            invalid_systems.append(candidate.candidate_id)
        else:
            systems_present.add(candidate.system)
        if not _is_sha256(candidate.artifact_hash) or not _is_sha256(candidate.provenance_hash):
            provenance_gaps.append(candidate.candidate_id)

    if duplicate_ids:
        failures.append(
            BlindReviewFailure(
                "BLIND_REVIEW_DUPLICATE_CANDIDATE_ID",
                "Candidate manifest contains duplicate blinded candidate IDs",
                {"candidate_ids": sorted(set(duplicate_ids))},
            )
        )
    if duplicate_hashes:
        failures.append(
            BlindReviewFailure(
                "BLIND_REVIEW_DUPLICATE_ARTIFACT_HASH",
                "Candidate manifest contains duplicate artifact hashes",
                {"artifact_hashes": sorted(set(duplicate_hashes))},
            )
        )
    if unblinded_ids:
        failures.append(
            BlindReviewFailure(
                "BLIND_REVIEW_UNBLINDED_CANDIDATE_ID",
                "Candidate IDs must be blinded and must not contain source labels",
                {"candidate_ids": sorted(set(unblinded_ids))},
            )
        )
    if invalid_systems:
        failures.append(
            BlindReviewFailure(
                "BLIND_REVIEW_CANDIDATE_SYSTEM_INVALID",
                "Candidate manifest must map each candidate to repo-agent or qoder",
                {"candidate_ids": sorted(set(invalid_systems)), "allowed": list(SYSTEMS)},
            )
        )
    if provenance_gaps:
        failures.append(
            BlindReviewFailure(
                "BLIND_REVIEW_PROVENANCE_GAP",
                "Candidates must include artifact and provenance SHA-256 hashes",
                {"candidate_ids": sorted(set(provenance_gaps))},
            )
        )
    missing_systems = [s for s in SYSTEMS if s not in systems_present]
    if missing_systems:
        failures.append(
            BlindReviewFailure(
                "BLIND_REVIEW_SYSTEM_COVERAGE_INCOMPLETE",
                "Candidate manifest must include repo-agent and Qoder candidates",
                {"missing_systems": missing_systems},
            )
        )


def _validate_blinded_records(
    matrix: BlindReviewMatrix, failures: list[BlindReviewFailure]
) -> None:
    leaks: list[dict[str, Any]] = []
    invalid_scores: list[dict[str, Any]] = []
    for idx, record in enumerate(matrix.records):
        extra_keys = sorted(
            (record.raw_keys - _ALLOWED_SCORE_KEYS) | (record.raw_keys & _SCORING_SOURCE_KEYS)
        )
        if (
            extra_keys
            or _SOURCE_LABEL_RE.search(record.candidate_id)
            or _SOURCE_LABEL_RE.search(record.reviewer_notes)
        ):
            leaks.append({"index": idx, "keys": extra_keys, "candidate_id": record.candidate_id})
        missing_dimensions = [d for d in DIMENSIONS if d not in record.scores]
        out_of_range = [
            d for d, value in record.scores.items() if d in DIMENSIONS and not 0 <= value <= 5
        ]
        if missing_dimensions or out_of_range or not record.repo_class or not record.candidate_id:
            invalid_scores.append(
                {
                    "index": idx,
                    "missing_dimensions": missing_dimensions,
                    "out_of_range": out_of_range,
                }
            )
    if leaks:
        failures.append(
            BlindReviewFailure(
                "BLIND_REVIEW_UNBLINDED_SCORING_RECORD",
                "Scoring records must not contain source labels, source keys, or artifact provenance",
                {"records": leaks},
            )
        )
    if invalid_scores:
        failures.append(
            BlindReviewFailure(
                "BLIND_REVIEW_SCORE_RECORD_INVALID",
                "Scoring records must include all dimensions with scores from 0 to 5",
                {"records": invalid_scores},
            )
        )


def _validate_duplicate_class_hash(
    matrix: BlindReviewMatrix,
    candidates_by_id: dict[str, BlindReviewCandidate],
    failures: list[BlindReviewFailure],
) -> None:
    seen: set[tuple[str, str]] = set()
    duplicates: list[dict[str, str]] = []
    for record in matrix.records:
        candidate = candidates_by_id.get(record.candidate_id)
        if candidate is None:
            continue
        key = (record.repo_class, candidate.artifact_hash)
        if key in seen:
            duplicates.append(
                {"artifact_hash": candidate.artifact_hash, "repo_class": record.repo_class}
            )
        seen.add(key)
    if duplicates:
        failures.append(
            BlindReviewFailure(
                "BLIND_REVIEW_DUPLICATE_CLASS_HASH",
                "Each representative class/artifact hash pair may be scored only once",
                {"duplicates": duplicates},
            )
        )


def _validate_class_pairs(
    matrix: BlindReviewMatrix,
    candidates_by_id: dict[str, BlindReviewCandidate],
    failures: list[BlindReviewFailure],
) -> None:
    records_by_pair: dict[tuple[str, str], list[BlindReviewScore]] = {}
    duplicate_systems: list[dict[str, str]] = []
    for record in matrix.records:
        candidate = candidates_by_id.get(record.candidate_id)
        if candidate is None or candidate.system not in SYSTEMS or not record.repo_class:
            continue
        pair_key = (record.repo_class, _pair_id(record))
        pair_records = records_by_pair.setdefault(pair_key, [])
        if any(candidates_by_id[r.candidate_id].system == candidate.system for r in pair_records):
            duplicate_systems.append(
                {
                    "pair_id": pair_key[1],
                    "repo_class": record.repo_class,
                    "system": candidate.system,
                }
            )
        pair_records.append(record)

    class_systems: dict[str, set[str]] = {}
    missing_counterparts: list[dict[str, Any]] = []
    rubric_revision_mismatches: list[dict[str, Any]] = []
    for (repo_class, pair_id), pair_records in sorted(records_by_pair.items()):
        systems = {candidates_by_id[r.candidate_id].system for r in pair_records}
        class_systems.setdefault(repo_class, set()).update(systems)
        missing_systems = [system for system in SYSTEMS if system not in systems]
        if missing_systems:
            missing_counterparts.append(
                {
                    "missing_systems": missing_systems,
                    "pair_id": pair_id,
                    "present_systems": sorted(systems),
                    "repo_class": repo_class,
                }
            )

        rubric_values = _field_values(pair_records, "rubric_id")
        revision_values = _field_values(pair_records, "revision_id")
        if len(rubric_values) > 1 or len(revision_values) > 1:
            rubric_revision_mismatches.append(
                {
                    "pair_id": pair_id,
                    "repo_class": repo_class,
                    "revision_ids": sorted(revision_values),
                    "rubric_ids": sorted(rubric_values),
                }
            )

    one_system_classes = [
        {
            "missing_systems": [system for system in SYSTEMS if system not in systems],
            "present_systems": sorted(systems),
            "repo_class": repo_class,
        }
        for repo_class, systems in sorted(class_systems.items())
        if systems != set(SYSTEMS)
    ]

    if missing_counterparts:
        failures.append(
            BlindReviewFailure(
                "BLIND_REVIEW_CLASS_COUNTERPART_MISSING",
                "Each class pair must contain both repo-agent and Qoder scoring records",
                {"pairs": missing_counterparts},
            )
        )
    if duplicate_systems:
        failures.append(
            BlindReviewFailure(
                "BLIND_REVIEW_DUPLICATE_PAIR_IDENTITY",
                "Each repo class/pair/system identity may be scored only once",
                {"duplicates": duplicate_systems},
            )
        )
    if rubric_revision_mismatches:
        failures.append(
            BlindReviewFailure(
                "BLIND_REVIEW_RUBRIC_REVISION_MISMATCH",
                "Paired records must use the same rubric and revision identifiers",
                {"pairs": rubric_revision_mismatches},
            )
        )
    if one_system_classes:
        failures.append(
            BlindReviewFailure(
                "BLIND_REVIEW_CLASS_SYSTEM_INCOMPLETE",
                "Every representative repo class must include both repo-agent and Qoder systems",
                {"classes": one_system_classes},
            )
        )


def _pair_id(record: BlindReviewScore) -> str:
    return record.pair_id or record.repo_class


def _field_values(records: list[BlindReviewScore], field_name: str) -> set[str]:
    values = {str(getattr(record, field_name)) for record in records}
    non_empty = {value for value in values if value}
    return values if non_empty else set()


def _compute_medians(
    records: list[BlindReviewScore],
    candidates_by_id: dict[str, BlindReviewCandidate],
) -> dict[str, dict[str, float | None]]:
    values: dict[str, dict[str, list[float]]] = {
        system: {dimension: [] for dimension in DIMENSIONS} for system in SYSTEMS
    }
    for record in records:
        candidate = candidates_by_id.get(record.candidate_id)
        if candidate is None or candidate.system not in SYSTEMS:
            continue
        for dimension in DIMENSIONS:
            value = record.scores.get(dimension)
            if value is not None:
                values[candidate.system][dimension].append(value)

    result: dict[str, dict[str, float | None]] = {system: {} for system in SYSTEMS}
    for system in SYSTEMS:
        for dimension in DIMENSIONS:
            samples = values[system][dimension]
            result[system][dimension] = float(median(samples)) if samples else None
    return result


def _compute_class_medians(
    records: list[BlindReviewScore],
    candidates_by_id: dict[str, BlindReviewCandidate],
) -> dict[str, dict[str, dict[str, float | None]]]:
    records_by_class: dict[str, list[BlindReviewScore]] = {}
    for record in records:
        if record.repo_class:
            records_by_class.setdefault(record.repo_class, []).append(record)
    return {
        repo_class: _compute_medians(class_records, candidates_by_id)
        for repo_class, class_records in sorted(records_by_class.items())
    }


def _median_failures(medians: dict[str, dict[str, float | None]]) -> list[BlindReviewFailure]:
    failures: list[BlindReviewFailure] = []
    gaps: list[dict[str, float | str | None]] = []
    for dimension in DIMENSIONS:
        repo_agent = medians[SYSTEM_REPO_AGENT][dimension]
        qoder = medians[SYSTEM_QODER][dimension]
        if repo_agent is None or qoder is None or repo_agent < qoder:
            gaps.append(
                {
                    "dimension": dimension,
                    SYSTEM_REPO_AGENT: repo_agent,
                    SYSTEM_QODER: qoder,
                }
            )
    if gaps:
        failures.append(
            BlindReviewFailure(
                "BLIND_REVIEW_MEDIAN_BELOW_QODER",
                "Every repo-agent median must be greater than or equal to the Qoder median",
                {"gaps": gaps},
            )
        )
    return failures


def _class_median_failures(
    class_medians: dict[str, dict[str, dict[str, float | None]]],
) -> list[BlindReviewFailure]:
    failures: list[BlindReviewFailure] = []
    gaps: list[dict[str, float | str | None]] = []
    for repo_class, medians in class_medians.items():
        for dimension in DIMENSIONS:
            repo_agent = medians[SYSTEM_REPO_AGENT][dimension]
            qoder = medians[SYSTEM_QODER][dimension]
            if repo_agent is None or qoder is None or repo_agent < qoder:
                gaps.append(
                    {
                        "dimension": dimension,
                        "repo_class": repo_class,
                        SYSTEM_REPO_AGENT: repo_agent,
                        SYSTEM_QODER: qoder,
                    }
                )
    if gaps:
        failures.append(
            BlindReviewFailure(
                "BLIND_REVIEW_CLASS_MEDIAN_BELOW_QODER",
                "Repo-agent must meet or exceed Qoder for every dimension in every representative class",
                {"gaps": gaps},
            )
        )
    return failures


def _is_sha256(value: str) -> bool:
    return bool(_HASH_RE.fullmatch(value))
