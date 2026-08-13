"""Engine imports must not depend on scanner/orchestration package init."""


def test_generation_engine_imports_without_circular_import() -> None:
    from repo_wiki.generator.engine import APIAggregator, GenerationEngine

    assert GenerationEngine is not None
    assert APIAggregator is not None
