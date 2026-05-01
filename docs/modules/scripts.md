# Module: scripts

Path: `scripts`  
Owner: `unknown`

## Responsibility
Handles exports AcceptanceEvidence, BaselineComparatorConfig.

## Exports
- `AcceptanceEvidence`
- `BaselineComparatorConfig`
- `BenchmarkMatrix`
- `BenchmarkResult`
- `ComparisonDimension`
- `ConfidenceScorer`
- `DeltaType`
- `DiagnosticMessage`
- `DimensionResult`
- `EvidenceField`
- `FixtureIngestion`
- `FixtureIntegrity`
- `FixtureIntegrityChecker`
- `FixtureManifest`
- `FixtureMetadata`
- `FixtureSchemaValidator`
- `FixtureStatus`
- `FreshnessValidator`
- `GapItem`
- `GapReport`
- `GapSeverity`
- `GovernanceDB`
- `GovernanceDashboard`
- `GovernanceMetric`
- `IngestionError`
- `Language`
- `PathNormalizer`
- `QoderBaselineComparator`
- `ReadinessCriteria`
- `ReadinessReport`
- `RepositoryClassifier`
- `RepositoryComplexity`
- `RepositoryMetadata`
- `RepositorySize`
- `ScoreBand`
- `ScoreDriftAnalysis`
- `ScoreDriftDetector`
- `ThresholdProfile`
- `ThresholdProfileGenerator`
- `TrendAnalyzer`
- `TrendData`
- `WeightedScore`
- `__init__`
- `_analyze_api_aggregation`
- `_analyze_data_model_aggregation`
- `_analyze_prose_density`
- `_build_dimension_weights`
- `_calculate_weighted_scores`
- `_compare_aggregation_quality`
- `_compare_directory_hierarchy`
- `_compare_heading_coverage`
- `_compare_navigation_completeness`
- `_compare_prose_density`
- `_compare_section_coverage`
- `_extract_headings`
- `_get_docs_structure`
- `_get_unique_profiles`
- `_load_metadata`
- `_validate_metadata`
- `_validate_required_files`
- `_validate_sections`
- `add_repository`
- `analyze`
- `analyze_drift`
- `analyze_trend`
- `calculate_slope`
- `calculate_volatility`
- `classify`
- `classify_by_complexity`
- `classify_by_language`
- `classify_by_size`
- `close`
- `compare_all`
- `compute_age_days`
- `compute_confidence_score`
- `compute_content_hash`
- `compute_integrity`
- `compute_structure_hash`
- `connect`
- `create_fixture_metadata`
- `export_human_readable`
- `export_machine_readable`
- `from_yaml`
- `from_yaml_config`
- `generate_readiness_report`
- `get_confidence_level`
- `get_default_dimension_weights`
- `get_delta_type`
- `get_freshness_score`
- `get_freshness_status`
- `get_profile`
- `get_quality_dims`
- `get_release_gate_decision`
- `get_score_band`
- `get_structural_dims`
- `import_from_benchmark_matrix`
- `ingest`
- `init_schema`
- `insert_metric`
- `is_accepted`
- `is_usable`
- `is_valid`
- `main`
- `normalize`
- `produce_diagnostic_report`
- `query_latest`
- `query_trends`
- `run_command`
- `suggest_normalization`
- `to_dict`
- `to_markdown`
- `validate`
- `validate_required_evidence`

## Depends On
- `repo_wiki`

## Depended By
- `extensions`
- `tests`

## Interfaces
- none

## Data Models
- none

## Context Strategy
- Strategy: `A`
- Token budget: `1200`
- Notes: Small module summary from direct metadata and a compact chunk set.

### Graph Neighbors
- none

### Retrieval Chunks
- `run_command` `scripts/pilot_acceptance.py`
- `scripts` `scripts/pilot_acceptance.py`
- `main` `scripts/pilot_acceptance.py`
