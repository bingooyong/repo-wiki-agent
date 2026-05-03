"""Tests for generation state machine."""

from repo_wiki.orchestration.generation_state import (
    GenerationRun,
    GenerationStateMachine,
    PageGenerationState,
    PageState,
    RunState,
)


class TestGenerationStateMachine:
    """Tests for GenerationStateMachine."""

    def test_create_run(self, tmp_path):
        """Test creating a new generation run."""
        sm = GenerationStateMachine(tmp_path / "test.db")
        run = sm.create_run(profile="default", total_pages=10)

        assert run.run_id.startswith("gen-")
        assert run.state == RunState.PENDING
        assert run.total_pages == 10
        assert run.profile == "default"

    def test_start_run(self, tmp_path):
        """Test starting a pending run."""
        sm = GenerationStateMachine(tmp_path / "test.db")
        run = sm.create_run()
        started = sm.start_run(run.run_id)

        assert started is not None
        assert started.state == RunState.RUNNING
        assert started.started_at is not None

    def test_complete_run(self, tmp_path):
        """Test completing a run."""
        sm = GenerationStateMachine(tmp_path / "test.db")
        run = sm.create_run()

        # Add some pages
        sm.add_page(run.run_id, "00-overview", "overview", "docs/00-overview.md")
        sm.add_page(run.run_id, "01-architecture", "overview", "docs/01-architecture.md")

        # Start and complete first page
        sm.start_page(run.run_id, "00-overview")
        sm.complete_page(run.run_id, "00-overview")

        # Complete the run
        sm.complete_run(run.run_id)
        final = sm.get_run(run.run_id)

        assert final.state == RunState.COMPLETED
        assert final.completed_pages == 1

    def test_run_becomes_retryable_when_retryable_pages_exist(self, tmp_path):
        """Run should be marked retryable if any page is retryable."""
        sm = GenerationStateMachine(tmp_path / "test.db")
        run = sm.create_run()
        sm.add_page(run.run_id, "00-overview", "overview", "docs/00-overview.md")

        sm.start_page(run.run_id, "00-overview")
        sm.fail_page(run.run_id, "00-overview", "Transient error", retryable=True)
        sm.complete_run(run.run_id)

        final = sm.get_run(run.run_id)
        assert final is not None
        assert final.state == RunState.RETRYABLE

    def test_cancel_run(self, tmp_path):
        """Test cancelling a run."""
        sm = GenerationStateMachine(tmp_path / "test.db")
        run = sm.create_run()

        # Add a pending page
        sm.add_page(run.run_id, "00-overview", "overview", "docs/00-overview.md")

        # Cancel the run
        sm.cancel_run(run.run_id)
        final = sm.get_run(run.run_id)

        assert final.state == RunState.CANCELLED

        # Page should be skipped
        page = sm.get_page_state(run.run_id, "00-overview")
        assert page.state == PageState.SKIPPED

    def test_page_state_transitions(self, tmp_path):
        """Test page state transitions."""
        sm = GenerationStateMachine(tmp_path / "test.db")
        run = sm.create_run()
        sm.add_page(run.run_id, "00-overview", "overview", "docs/00-overview.md")

        # Initial state
        page = sm.get_page_state(run.run_id, "00-overview")
        assert page.state == PageState.PENDING
        assert page.attempts == 0

        # Start page
        sm.start_page(run.run_id, "00-overview")
        page = sm.get_page_state(run.run_id, "00-overview")
        assert page.state == PageState.RUNNING
        assert page.attempts == 0  # start_page doesn't increment attempts

        # Fail and retry (increments attempts)
        sm.fail_page(run.run_id, "00-overview", "Transient error")
        page = sm.get_page_state(run.run_id, "00-overview")
        assert page.state == PageState.RETRYABLE
        assert page.attempts == 1

        # Start again
        sm.start_page(run.run_id, "00-overview")
        page = sm.get_page_state(run.run_id, "00-overview")
        assert page.state == PageState.RUNNING
        assert page.attempts == 1

        # Complete page
        sm.complete_page(run.run_id, "00-overview")
        page = sm.get_page_state(run.run_id, "00-overview")
        assert page.state == PageState.COMPLETED
        assert page.attempts == 1

    def test_fail_page(self, tmp_path):
        """Test failing a page."""
        sm = GenerationStateMachine(tmp_path / "test.db")
        run = sm.create_run()
        sm.add_page(run.run_id, "00-overview", "overview", "docs/00-overview.md")

        # Fail the page
        sm.fail_page(run.run_id, "00-overview", "Test error")
        page = sm.get_page_state(run.run_id, "00-overview")
        assert page.state == PageState.RETRYABLE
        assert page.error_message == "Test error"

        # Exhaust retries (default max_attempts is 3)
        for i in range(2):
            sm.start_page(run.run_id, "00-overview")
            sm.fail_page(run.run_id, "00-overview", f"Test error {i + 1}")

        page = sm.get_page_state(run.run_id, "00-overview")
        assert page.state == PageState.FAILED
        assert page.attempts == 3

    def test_skip_page(self, tmp_path):
        """Test skipping a page."""
        sm = GenerationStateMachine(tmp_path / "test.db")
        run = sm.create_run()
        sm.add_page(run.run_id, "00-overview", "overview", "docs/00-overview.md")

        sm.skip_page(run.run_id, "00-overview", "Not needed")
        page = sm.get_page_state(run.run_id, "00-overview")
        assert page.state == PageState.SKIPPED

    def test_get_pending_pages(self, tmp_path):
        """Test getting pending pages."""
        sm = GenerationStateMachine(tmp_path / "test.db")
        run = sm.create_run()

        sm.add_page(run.run_id, "00-overview", "overview", "docs/00-overview.md")
        sm.add_page(run.run_id, "01-architecture", "overview", "docs/01-architecture.md")

        pending = sm.get_pending_pages(run.run_id)
        assert len(pending) == 2

        # Start one page
        sm.start_page(run.run_id, "00-overview")
        pending = sm.get_pending_pages(run.run_id)
        assert len(pending) == 1

    def test_is_run_complete(self, tmp_path):
        """Test checking if run is complete."""
        sm = GenerationStateMachine(tmp_path / "test.db")
        run = sm.create_run()
        sm.add_page(run.run_id, "00-overview", "overview", "docs/00-overview.md")
        sm.add_page(run.run_id, "01-architecture", "overview", "docs/01-architecture.md")

        assert not sm.is_run_complete(run.run_id)

        # Complete one page
        sm.start_page(run.run_id, "00-overview")
        sm.complete_page(run.run_id, "00-overview")
        assert not sm.is_run_complete(run.run_id)

        # Skip the other
        sm.skip_page(run.run_id, "01-architecture")
        assert sm.is_run_complete(run.run_id)

    def test_get_pages_needing_regeneration(self, tmp_path):
        """Test detecting pages with changed input."""
        sm = GenerationStateMachine(tmp_path / "test.db")
        run = sm.create_run()

        # Original hash
        sm.add_page(
            run.run_id, "00-overview", "overview", "docs/00-overview.md", input_hash="abc123"
        )

        # Mark as completed
        sm.start_page(run.run_id, "00-overview")
        sm.complete_page(run.run_id, "00-overview")

        # Check with same hash - no regeneration needed
        needs = sm.get_pages_needing_regeneration(run.run_id, {"00-overview": "abc123"})
        assert len(needs) == 0

        # Check with different hash - needs regeneration
        needs = sm.get_pages_needing_regeneration(run.run_id, {"00-overview": "xyz789"})
        assert len(needs) == 1
        assert needs[0].doc_slug == "00-overview"

    def test_resume_run_does_not_regenerate_completed_pages(self, tmp_path):
        """Resuming should only keep pending/retryable pages in queue."""
        sm = GenerationStateMachine(tmp_path / "test.db")
        run = sm.create_run()

        sm.add_page(run.run_id, "00-overview", "overview", "docs/00-overview.md")
        sm.add_page(run.run_id, "01-architecture", "overview", "docs/01-architecture.md")
        sm.add_page(run.run_id, "03-module-map", "overview", "docs/03-module-map.md")

        sm.start_run(run.run_id)
        sm.start_page(run.run_id, "00-overview")
        sm.complete_page(run.run_id, "00-overview")
        sm.start_page(run.run_id, "01-architecture")
        # Simulate interruption while this page is running.
        resumed = sm.resume_run(run.run_id)

        assert resumed is not None
        assert resumed.state == RunState.RUNNING
        completed = sm.get_page_state(run.run_id, "00-overview")
        assert completed is not None
        assert completed.state == PageState.COMPLETED

        pending = sm.get_pending_pages(run.run_id)
        pending_slugs = {p.doc_slug for p in pending}
        assert "00-overview" not in pending_slugs
        assert "01-architecture" in pending_slugs
        assert "03-module-map" in pending_slugs

    def test_list_runs(self, tmp_path):
        """Test listing runs."""
        sm = GenerationStateMachine(tmp_path / "test.db")

        # Create multiple runs
        run1 = sm.create_run(profile="default")
        run2 = sm.create_run(profile="ci")
        run3 = sm.create_run(profile="qoder-like")

        runs = sm.list_runs()
        assert len(runs) == 3

        # Filter by state
        pending = sm.list_runs(state=RunState.PENDING)
        assert len(pending) == 3

        # Start one run
        sm.start_run(run1.run_id)
        pending = sm.list_runs(state=RunState.PENDING)
        assert len(pending) == 2

        running = sm.list_runs(state=RunState.RUNNING)
        assert len(running) == 1


class TestGenerationRun:
    """Tests for GenerationRun dataclass."""

    def test_run_creation(self):
        """Test creating a GenerationRun."""
        from repo_wiki.orchestration.generation_state import RunState

        run = GenerationRun(
            run_id="gen-test123",
            state=RunState.PENDING,
            created_at="2024-01-01T00:00:00Z",
            total_pages=5,
        )

        assert run.run_id == "gen-test123"
        assert run.state == RunState.PENDING
        assert run.total_pages == 5


class TestPageGenerationState:
    """Tests for PageGenerationState dataclass."""

    def test_page_state_creation(self):
        """Test creating a PageGenerationState."""
        from repo_wiki.orchestration.generation_state import PageState

        page = PageGenerationState(
            run_id="gen-test123",
            doc_slug="00-overview",
            doc_type="overview",
            doc_path="docs/00-overview.md",
            state=PageState.PENDING,
        )

        assert page.run_id == "gen-test123"
        assert page.doc_slug == "00-overview"
        assert page.state == PageState.PENDING
        assert page.attempts == 0
        assert page.max_attempts == 3


class TestCreateGenerationStateMachine:
    """Tests for create_generation_state_machine factory."""

    def test_create_state_machine(self, tmp_path):
        """Test creating state machine with factory."""
        db_path = tmp_path / ".repo-wiki" / "index" / "generation_state.sqlite3"
        sm = GenerationStateMachine(db_path)

        run = sm.create_run()
        assert run is not None
        assert db_path.exists()
