"""Per-page agent loop for handbook pages (overview, install, data model, API).

Investigators read the repository with file tools and record typed facts with ``FILE:LINE: quote``
evidence; every fact is verified by a program as it is recorded. A writer turns verified facts into
prose while lists/tables are rendered by the program; deterministic checks (including the
repository's own handbook gates) and an independent auditor drive a bounded rework loop. A page that
still fails is reported as failed and is not shipped.
"""

from repo_wiki.agent_loop.checklists import PAGE_TYPES, PAGES

__all__ = ["PAGES", "PAGE_TYPES"]
