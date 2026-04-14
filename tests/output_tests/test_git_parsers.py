"""Tests for git output parsers."""

from tokkit_output.parsers.git_diff import GitDiffParser
from tokkit_output.parsers.git_status import GitStatusParser
from tokkit_output.parsers.git_log import GitLogParser
from tokkit_output.parsers.git_show import GitShowParser
from tokkit_output.parsers.git_blame import GitBlameParser
from tokkit_output.parsers.git_branch import GitBranchParser
from tokkit_output.parsers.git_stash import GitStashParser
from tests.output_tests.fixtures import git_output as fx


class TestGitDiffDetect:
    def setup_method(self):
        self.parser = GitDiffParser()

    def test_detects_diff(self):
        assert self.parser.detect(fx.DIFF_SIMPLE) >= 0.8

    def test_detects_diff_with_lockfile(self):
        assert self.parser.detect(fx.DIFF_WITH_LOCKFILE) >= 0.8

    def test_detects_stat(self):
        assert self.parser.detect(fx.DIFF_STAT) >= 0.7

    def test_rejects_non_diff(self):
        assert self.parser.detect("hello world\nsome random text\nno diff here\n") < 0.6

    def test_rejects_empty(self):
        assert self.parser.detect("") < 0.6


class TestGitDiffParse:
    def setup_method(self):
        self.parser = GitDiffParser()

    def test_simple_diff_has_rows(self):
        result = self.parser.parse(fx.DIFF_SIMPLE)
        assert result.tool == "git-diff"
        assert result.schema == ["file", "lines_changed", "content"]
        assert len(result.rows) > 0

    def test_strips_index_lines(self):
        result = self.parser.parse(fx.DIFF_SIMPLE)
        for row in result.rows:
            content = row[2]
            assert "index 1234567" not in content
            assert not any(
                line.startswith("index ") for line in content.splitlines()
            )

    def test_lockfile_elided(self):
        result = self.parser.parse(fx.DIFF_WITH_LOCKFILE)
        lock_rows = [r for r in result.rows if "package-lock.json" in r[0]]
        assert len(lock_rows) == 1
        assert "lockfile changed" in lock_rows[0][2]
        assert "pkg-50" not in lock_rows[0][2]

    def test_large_hunk_truncated(self):
        result = self.parser.parse(fx.DIFF_LARGE_HUNK)
        assert len(result.rows) > 0
        content = result.rows[0][2]
        assert "truncated" in content
        assert "added line 55" not in content

    def test_stat_output_parsed(self):
        result = self.parser.parse(fx.DIFF_STAT)
        assert "4 files" in result.summary or "files changed" in result.summary or "4" in result.summary

    def test_multiple_files_parsed(self):
        result = self.parser.parse(fx.DIFF_MULTIPLE_FILES)
        files = [r[0] for r in result.rows]
        assert len(set(files)) >= 2

    def test_summary_has_file_count(self):
        result = self.parser.parse(fx.DIFF_SIMPLE)
        assert result.summary != ""
        assert result.summary != "no changes"


# ---------------------------------------------------------------------------
# git status
# ---------------------------------------------------------------------------


class TestGitStatusDetect:
    def setup_method(self):
        self.parser = GitStatusParser()

    def test_detects_clean(self):
        assert self.parser.detect(fx.STATUS_CLEAN) >= 0.5

    def test_detects_dirty_long(self):
        assert self.parser.detect(fx.STATUS_DIRTY) >= 0.8

    def test_detects_short_format(self):
        assert self.parser.detect(fx.STATUS_SHORT) >= 0.5

    def test_rejects_non_status(self):
        assert self.parser.detect("hello world\nsome random text\n") < 0.4

    def test_rejects_empty(self):
        assert self.parser.detect("") < 0.4


class TestGitStatusParse:
    def setup_method(self):
        self.parser = GitStatusParser()

    def test_clean_repo_no_rows(self):
        result = self.parser.parse(fx.STATUS_CLEAN)
        assert result.tool == "git-status"
        assert result.schema == ["file", "status", "staged"]
        assert result.rows == []
        assert "clean" in result.summary.lower()

    def test_dirty_long_has_rows(self):
        result = self.parser.parse(fx.STATUS_DIRTY)
        assert len(result.rows) > 0
        files = [r[0] for r in result.rows]
        assert any("src/auth.py" in f for f in files)

    def test_dirty_long_staged_flag(self):
        result = self.parser.parse(fx.STATUS_DIRTY)
        staged = {r[0]: r[2] for r in result.rows}
        assert staged.get("src/auth.py") == "true"
        assert staged.get("src/models/user.py") == "false"

    def test_short_format_parsed(self):
        result = self.parser.parse(fx.STATUS_SHORT)
        assert len(result.rows) >= 4
        files = [r[0] for r in result.rows]
        assert any("src/auth.py" in f for f in files)

    def test_short_format_untracked(self):
        result = self.parser.parse(fx.STATUS_SHORT)
        untracked = [r for r in result.rows if r[1] == "untracked"]
        assert len(untracked) >= 1

    def test_summary_format(self):
        result = self.parser.parse(fx.STATUS_DIRTY)
        assert "Files:" in result.summary

    def test_large_status_groups_dirs(self):
        result = self.parser.parse(fx.STATUS_LARGE)
        # Some directories with >8 files should be collapsed
        grouped = [r for r in result.rows if r[0].endswith("/")]
        assert len(grouped) >= 1

    def test_no_hint_lines_in_rows(self):
        result = self.parser.parse(fx.STATUS_DIRTY)
        for row in result.rows:
            assert not row[0].startswith('(use "git')


# ---------------------------------------------------------------------------
# git log
# ---------------------------------------------------------------------------


class TestGitLogDetect:
    def setup_method(self):
        self.parser = GitLogParser()

    def test_detects_verbose(self):
        assert self.parser.detect(fx.LOG_VERBOSE) >= 0.6

    def test_detects_oneline(self):
        assert self.parser.detect(fx.LOG_ONELINE) >= 0.5

    def test_rejects_non_log(self):
        assert self.parser.detect("hello world\nsome random text\n") < 0.4

    def test_rejects_empty(self):
        assert self.parser.detect("") < 0.4


class TestGitLogParse:
    def setup_method(self):
        self.parser = GitLogParser()

    def test_oneline_rows(self):
        result = self.parser.parse(fx.LOG_ONELINE_SHORT)
        assert result.tool == "git-log"
        assert result.schema == ["hash", "message"]
        assert len(result.rows) == 3

    def test_oneline_hash_len(self):
        result = self.parser.parse(fx.LOG_ONELINE_SHORT)
        for row in result.rows:
            assert len(row[0]) <= 8

    def test_oneline_message_content(self):
        result = self.parser.parse(fx.LOG_ONELINE_SHORT)
        messages = [r[1] for r in result.rows]
        assert any("token refresh" in m for m in messages)

    def test_verbose_extracts_subject(self):
        result = self.parser.parse(fx.LOG_VERBOSE)
        assert len(result.rows) == 3
        messages = [r[1] for r in result.rows]
        assert any("token refresh" in m for m in messages)

    def test_verbose_drops_metadata(self):
        result = self.parser.parse(fx.LOG_VERBOSE)
        for row in result.rows:
            assert not row[1].startswith("Author:")
            assert not row[1].startswith("Date:")

    def test_cap_at_limit(self):
        result = self.parser.parse(fx.LOG_ONELINE, limit=10)
        assert len(result.rows) == 10

    def test_summary_showing_of(self):
        result = self.parser.parse(fx.LOG_ONELINE, limit=10)
        assert "showing 10 of 12" in result.summary

    def test_summary_exact(self):
        result = self.parser.parse(fx.LOG_ONELINE_SHORT)
        assert "3" in result.summary
        assert "showing" not in result.summary


# ---------------------------------------------------------------------------
# git show
# ---------------------------------------------------------------------------


class TestGitShowDetect:
    def setup_method(self):
        self.parser = GitShowParser()

    def test_detects_show(self):
        assert self.parser.detect(fx.SHOW_COMMIT) > 0.6

    def test_commit_only_low_score(self):
        # Verbose log without diff should score low
        assert self.parser.detect(fx.LOG_VERBOSE) <= 0.5

    def test_diff_only_low_score(self):
        from tests.output_tests.fixtures.git_output import DIFF_SIMPLE
        assert self.parser.detect(DIFF_SIMPLE) <= 0.5

    def test_rejects_empty(self):
        assert self.parser.detect("") == 0.0


class TestGitShowParse:
    def setup_method(self):
        self.parser = GitShowParser()

    def test_has_schema(self):
        result = self.parser.parse(fx.SHOW_COMMIT)
        assert result.tool == "git-show"
        assert result.schema == ["file", "lines_changed", "content"]

    def test_summary_has_hash_and_message(self):
        result = self.parser.parse(fx.SHOW_COMMIT)
        assert "a1b2c3d" in result.summary
        assert "token refresh" in result.summary

    def test_diff_rows_parsed(self):
        result = self.parser.parse(fx.SHOW_COMMIT)
        assert len(result.rows) >= 1
        files = [r[0] for r in result.rows]
        assert any("auth.py" in f for f in files)

    def test_summary_has_file_count(self):
        result = self.parser.parse(fx.SHOW_COMMIT)
        assert "file" in result.summary


# ---------------------------------------------------------------------------
# git blame
# ---------------------------------------------------------------------------


class TestGitBlameDetect:
    def setup_method(self):
        self.parser = GitBlameParser()

    def test_detects_blame(self):
        assert self.parser.detect(fx.BLAME_OUTPUT) >= 0.9

    def test_rejects_non_blame(self):
        assert self.parser.detect("hello world\nsome random text\n") < 0.4

    def test_rejects_empty(self):
        assert self.parser.detect("") == 0.0


class TestGitBlameParse:
    def setup_method(self):
        self.parser = GitBlameParser()

    def test_schema(self):
        result = self.parser.parse(fx.BLAME_OUTPUT)
        assert result.tool == "git-blame"
        assert result.schema == ["lines", "hash", "author"]

    def test_collapses_consecutive_ranges(self):
        result = self.parser.parse(fx.BLAME_OUTPUT)
        # Lines 1-2 are same author+hash, should be collapsed
        lines_col = [r[0] for r in result.rows]
        assert any("-" in l for l in lines_col)

    def test_authors_identified(self):
        result = self.parser.parse(fx.BLAME_OUTPUT)
        authors = {r[2] for r in result.rows}
        assert "Alice Johnson" in authors
        assert "Bob Smith" in authors

    def test_summary_format(self):
        result = self.parser.parse(fx.BLAME_OUTPUT)
        assert "lines" in result.summary
        assert "authors" in result.summary
        assert "ranges" in result.summary

    def test_12_total_lines(self):
        result = self.parser.parse(fx.BLAME_OUTPUT)
        assert "12 lines" in result.summary


# ---------------------------------------------------------------------------
# git branch
# ---------------------------------------------------------------------------


class TestGitBranchDetect:
    def setup_method(self):
        self.parser = GitBranchParser()

    def test_detects_branch(self):
        assert self.parser.detect(fx.BRANCH_OUTPUT) >= 0.85

    def test_detects_verbose(self):
        assert self.parser.detect(fx.BRANCH_VERBOSE) >= 0.85

    def test_rejects_non_branch(self):
        assert self.parser.detect("hello world\nsome text\n") < 0.4

    def test_rejects_empty(self):
        assert self.parser.detect("") == 0.0


class TestGitBranchParse:
    def setup_method(self):
        self.parser = GitBranchParser()

    def test_schema(self):
        result = self.parser.parse(fx.BRANCH_OUTPUT)
        assert result.tool == "git-branch"
        assert result.schema == ["branch", "current", "info"]

    def test_marks_current(self):
        result = self.parser.parse(fx.BRANCH_OUTPUT)
        current = [r for r in result.rows if r[1] == "true"]
        assert len(current) == 1
        assert current[0][0] == "main"

    def test_all_branches_present(self):
        result = self.parser.parse(fx.BRANCH_OUTPUT)
        names = [r[0] for r in result.rows]
        assert "main" in names

    def test_summary_branch_count(self):
        result = self.parser.parse(fx.BRANCH_OUTPUT)
        assert "8" in result.summary or "branch" in result.summary

    def test_summary_current(self):
        result = self.parser.parse(fx.BRANCH_OUTPUT)
        assert "main" in result.summary


# ---------------------------------------------------------------------------
# git stash
# ---------------------------------------------------------------------------


class TestGitStashDetect:
    def setup_method(self):
        self.parser = GitStashParser()

    def test_detects_stash(self):
        assert self.parser.detect(fx.STASH_LIST) >= 0.9

    def test_rejects_non_stash(self):
        assert self.parser.detect("hello world\nsome text\n") < 0.4

    def test_rejects_empty(self):
        assert self.parser.detect("") == 0.0


class TestGitStashParse:
    def setup_method(self):
        self.parser = GitStashParser()

    def test_schema(self):
        result = self.parser.parse(fx.STASH_LIST)
        assert result.tool == "git-stash"
        assert result.schema == ["index", "branch", "message"]

    def test_rows_parsed(self):
        result = self.parser.parse(fx.STASH_LIST)
        assert len(result.rows) == 3

    def test_index_extracted(self):
        result = self.parser.parse(fx.STASH_LIST)
        indices = [r[0] for r in result.rows]
        assert "0" in indices
        assert "1" in indices
        assert "2" in indices

    def test_branch_extracted(self):
        result = self.parser.parse(fx.STASH_LIST)
        branches = [r[1] for r in result.rows]
        assert "feat/auth-improvements" in branches
        assert "main" in branches

    def test_message_extracted(self):
        result = self.parser.parse(fx.STASH_LIST)
        messages = [r[2] for r in result.rows]
        assert any("token refresh" in m for m in messages)

    def test_summary_count(self):
        result = self.parser.parse(fx.STASH_LIST)
        assert "3" in result.summary
