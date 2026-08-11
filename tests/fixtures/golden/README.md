# Golden CI fixtures (Task 29.4)

This directory holds **checked-in, tiny source trees** used by `repo_wiki.test.golden_fixtures` and
`tests/test_golden_fixtures.py`. They provide language surface area (Python, Java, TypeScript, SQL)
without network or API keys.

- `sample_repo/` — minimal multi-language layout referenced from mock wiki `<cite>` lines and planner tests.

Mock LLM outputs for generated wiki pages live in `repo_wiki/test/golden_fixtures.py` (`build_strict_qoder_mock_pages`).
