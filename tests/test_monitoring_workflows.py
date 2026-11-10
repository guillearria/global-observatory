"""Static guardrails for the event topology and non-blocking publisher preflight."""
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_staleness_only_follows_pages_on_main_and_retains_daily_manual_runs():
    workflow = (ROOT / ".github/workflows/staleness.yml").read_text()
    trigger = workflow.split("  workflow_run:\n", 1)[1].split("permissions:", 1)[0]
    assert "workflows: [pages]" in trigger
    assert "branches: [main]" in trigger
    assert "types: [completed]" in trigger
    assert "notify" not in trigger and "staleness" not in trigger
    assert 'cron: "0 13 * * *"' in workflow
    assert "workflow_dispatch: {}" in workflow
    assert "permissions:\n  contents: read\njobs:" in workflow
    assert "github.event_name != 'workflow_run' ||" in workflow
    assert "github.event.workflow_run.conclusion == 'success' &&" in workflow
    assert "github.event.workflow_run.head_repository.full_name == github.repository" in workflow
    assert "ref: ${{ github.event.workflow_run.head_sha || github.sha }}" in workflow
    assert "run: python3 scripts/check_freshness.py --live" in workflow
    assert "--report-only" not in workflow


def test_publisher_checks_actual_merged_tree_without_blocking_valid_updates():
    workflow = (ROOT / ".github/workflows/publish.yml").read_text()
    merge = workflow.index('git merge --no-edit "$sha"')
    validation = workflow.index("python scripts/validate_data.py", merge)
    preflight = workflow.index("python scripts/check_freshness.py --report-only", merge)
    push = workflow.index("git push origin publish:main", merge)
    assert merge < validation < preflight < push
    command = workflow[preflight:].splitlines()[0]
    assert '|| echo "::warning::Freshness preflight could not complete' in command
    assert "gh workflow run pages.yml --ref main" in workflow
    assert "gh workflow run validate.yml --ref main" in workflow


def test_daily_refresh_plans_before_next_run_without_restamping_sources():
    command = (ROOT / ".claude/commands/refresh-events.md").read_text()
    assert "--report-only --review-window-hours 24" in command
    assert "Account for every queued record" in command
    assert "Only a successful source read" in command
    assert "preserve its retrieval date" in command
