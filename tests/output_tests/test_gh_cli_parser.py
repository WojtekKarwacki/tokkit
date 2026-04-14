"""Tests for GitHub CLI output parser."""

from tokkit_output.parsers.gh_cli import GhCliParser
from tests.output_tests.fixtures import gh_output as fx


# ---------------------------------------------------------------------------
# GhCliParser — detect
# ---------------------------------------------------------------------------

class TestGhCliDetect:
    def setup_method(self):
        self.parser = GhCliParser()

    def test_detects_pr_list(self):
        assert self.parser.detect(fx.GH_PR_LIST) >= 0.8

    def test_detects_issue_list(self):
        assert self.parser.detect(fx.GH_ISSUE_LIST) >= 0.8

    def test_detects_run_list(self):
        assert self.parser.detect(fx.GH_RUN_LIST) >= 0.8

    def test_rejects_non_gh(self):
        assert self.parser.detect("hello world\nsome random text\nno gh here\n") < 0.5

    def test_rejects_empty(self):
        assert self.parser.detect("") < 0.5


# ---------------------------------------------------------------------------
# GhCliParser — PR list parse
# ---------------------------------------------------------------------------

class TestGhCliParsePrList:
    def setup_method(self):
        self.parser = GhCliParser()

    def test_tool_name(self):
        result = self.parser.parse(fx.GH_PR_LIST)
        assert result.tool == "gh-cli"

    def test_schema(self):
        result = self.parser.parse(fx.GH_PR_LIST)
        assert "number" in result.schema
        assert "title" in result.schema
        assert "status" in result.schema

    def test_row_count(self):
        result = self.parser.parse(fx.GH_PR_LIST)
        assert len(result.rows) == 5

    def test_pr_numbers(self):
        result = self.parser.parse(fx.GH_PR_LIST)
        numbers = [r[0] for r in result.rows]
        assert "47" in numbers
        assert "45" in numbers
        assert "38" in numbers

    def test_pr_titles_present(self):
        result = self.parser.parse(fx.GH_PR_LIST)
        titles = [r[1] for r in result.rows]
        assert any("auth token" in t for t in titles)

    def test_summary_mentions_pull_requests(self):
        result = self.parser.parse(fx.GH_PR_LIST)
        assert "pull requests" in result.summary or "12" in result.summary


# ---------------------------------------------------------------------------
# GhCliParser — issue list parse
# ---------------------------------------------------------------------------

class TestGhCliParseIssueList:
    def setup_method(self):
        self.parser = GhCliParser()

    def test_schema(self):
        result = self.parser.parse(fx.GH_ISSUE_LIST)
        assert "number" in result.schema
        assert "title" in result.schema
        assert "status" in result.schema

    def test_row_count(self):
        result = self.parser.parse(fx.GH_ISSUE_LIST)
        assert len(result.rows) == 5

    def test_issue_numbers(self):
        result = self.parser.parse(fx.GH_ISSUE_LIST)
        numbers = [r[0] for r in result.rows]
        assert "102" in numbers
        assert "87" in numbers

    def test_summary_mentions_issues(self):
        result = self.parser.parse(fx.GH_ISSUE_LIST)
        assert "issue" in result.summary or "23" in result.summary


# ---------------------------------------------------------------------------
# GhCliParser — run list parse
# ---------------------------------------------------------------------------

class TestGhCliParseRunList:
    def setup_method(self):
        self.parser = GhCliParser()

    def test_schema(self):
        result = self.parser.parse(fx.GH_RUN_LIST)
        assert result.schema == ["status", "name", "branch", "elapsed"]

    def test_row_count(self):
        result = self.parser.parse(fx.GH_RUN_LIST)
        assert len(result.rows) == 5

    def test_statuses_present(self):
        result = self.parser.parse(fx.GH_RUN_LIST)
        statuses = [r[0] for r in result.rows]
        assert "completed" in statuses
        assert "failed" in statuses
        assert "in_progress" in statuses

    def test_branch_present(self):
        result = self.parser.parse(fx.GH_RUN_LIST)
        branches = [r[2] for r in result.rows]
        assert "main" in branches
        assert "feat/auth-fix" in branches

    def test_elapsed_present(self):
        result = self.parser.parse(fx.GH_RUN_LIST)
        elapsed = [r[3] for r in result.rows]
        assert any("m" in e for e in elapsed if e)

    def test_summary_mentions_runs(self):
        result = self.parser.parse(fx.GH_RUN_LIST)
        assert "run" in result.summary
