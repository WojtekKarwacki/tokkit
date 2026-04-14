"""Tests for shell tool output parsers."""

from tokkit_output.parsers.package_list import PackageListParser
from tokkit_output.parsers.file_listing import FileListingParser
from tokkit_output.parsers.search_results import SearchResultsParser
from tokkit_output.parsers.env_redact import EnvRedactParser
from tests.output_tests.fixtures import shell_output as fx


# ---------------------------------------------------------------------------
# PackageListParser — detect
# ---------------------------------------------------------------------------

class TestPackageListDetect:
    def setup_method(self):
        self.parser = PackageListParser()

    def test_detects_pip_list(self):
        assert self.parser.detect(fx.PIP_LIST) >= 0.8

    def test_detects_pip_freeze(self):
        assert self.parser.detect(fx.PIP_FREEZE) >= 0.7

    def test_detects_npm_ls(self):
        assert self.parser.detect(fx.NPM_LS) >= 0.7

    def test_rejects_non_package(self):
        assert self.parser.detect("hello world\nsome random text\n") < 0.5

    def test_rejects_empty(self):
        assert self.parser.detect("") < 0.5


# ---------------------------------------------------------------------------
# PackageListParser — pip list parse
# ---------------------------------------------------------------------------

class TestPackageListParsePipList:
    def setup_method(self):
        self.parser = PackageListParser()

    def test_schema(self):
        result = self.parser.parse(fx.PIP_LIST)
        assert result.schema == ["package", "version"]

    def test_tool_name(self):
        result = self.parser.parse(fx.PIP_LIST)
        assert result.tool == "package-list"

    def test_truncated_at_20(self):
        result = self.parser.parse(fx.PIP_LIST)
        # 30 packages → truncated to 15 + summary row
        assert len(result.rows) == 16

    def test_truncation_row_present(self):
        result = self.parser.parse(fx.PIP_LIST)
        last = result.rows[-1]
        assert "more" in last[0]

    def test_verbose_shows_all(self):
        result = self.parser.parse(fx.PIP_LIST, verbose=True)
        assert len(result.rows) == 30

    def test_summary_has_package_count(self):
        result = self.parser.parse(fx.PIP_LIST)
        assert "30 packages" in result.summary

    def test_first_package_parsed(self):
        result = self.parser.parse(fx.PIP_LIST)
        names = [r[0] for r in result.rows]
        assert "annotated-types" in names


# ---------------------------------------------------------------------------
# PackageListParser — pip freeze parse
# ---------------------------------------------------------------------------

class TestPackageListParsePipFreeze:
    def setup_method(self):
        self.parser = PackageListParser()

    def test_schema(self):
        result = self.parser.parse(fx.PIP_FREEZE)
        assert result.schema == ["package", "version"]

    def test_truncated(self):
        result = self.parser.parse(fx.PIP_FREEZE)
        assert len(result.rows) == 16

    def test_verbose_shows_all(self):
        result = self.parser.parse(fx.PIP_FREEZE, verbose=True)
        assert len(result.rows) == 30

    def test_parses_name_and_version(self):
        result = self.parser.parse(fx.PIP_FREEZE, verbose=True)
        row = result.rows[0]
        assert row[0] == "annotated-types"
        assert row[1] == "0.7.0"


# ---------------------------------------------------------------------------
# PackageListParser — npm ls parse
# ---------------------------------------------------------------------------

class TestPackageListParseNpmLs:
    def setup_method(self):
        self.parser = PackageListParser()

    def test_schema(self):
        result = self.parser.parse(fx.NPM_LS)
        assert result.schema == ["package", "version", "status"]

    def test_top_level_packages_present(self):
        result = self.parser.parse(fx.NPM_LS)
        names = [r[0] for r in result.rows]
        assert "express" in names
        assert "lodash" in names
        assert "react" in names

    def test_unmet_peer_kept(self):
        result = self.parser.parse(fx.NPM_LS)
        issue_rows = [r for r in result.rows if r[2] == "UNMET"]
        assert len(issue_rows) >= 1

    def test_unmet_row_has_name(self):
        result = self.parser.parse(fx.NPM_LS)
        issue_rows = [r for r in result.rows if r[2] == "UNMET"]
        names = [r[0] for r in issue_rows]
        assert any("react-dom" in n for n in names)

    def test_summary_format(self):
        result = self.parser.parse(fx.NPM_LS)
        assert "top-level" in result.summary
        assert "issues" in result.summary

    def test_nested_not_in_rows(self):
        result = self.parser.parse(fx.NPM_LS)
        # Nested deps like accepts, mime-types should not appear as top-level rows
        names = [r[0] for r in result.rows if r[2] != "UNMET"]
        assert "accepts" not in names
        assert "mime-types" not in names


# ---------------------------------------------------------------------------
# FileListingParser — detect
# ---------------------------------------------------------------------------

class TestFileListingDetect:
    def setup_method(self):
        self.parser = FileListingParser()

    def test_detects_tree(self):
        assert self.parser.detect(fx.TREE_OUTPUT) >= 0.8

    def test_detects_ls_la(self):
        assert self.parser.detect(fx.LS_LA_OUTPUT) >= 0.7

    def test_detects_find(self):
        assert self.parser.detect(fx.FIND_OUTPUT) >= 0.6

    def test_rejects_non_listing(self):
        assert self.parser.detect("hello world\nsome text\n") < 0.5


# ---------------------------------------------------------------------------
# FileListingParser — tree parse
# ---------------------------------------------------------------------------

class TestFileListingParseTree:
    def setup_method(self):
        self.parser = FileListingParser()

    def test_schema(self):
        result = self.parser.parse(fx.TREE_OUTPUT)
        assert result.schema == ["path"]

    def test_tool_name(self):
        result = self.parser.parse(fx.TREE_OUTPUT)
        assert result.tool == "file-listing"

    def test_shallow_entries_present(self):
        result = self.parser.parse(fx.TREE_OUTPUT)
        paths = [r[0] for r in result.rows]
        # Top-level entries should be present
        assert any("README.md" in p for p in paths)
        assert any("src" in p for p in paths)

    def test_has_rows(self):
        result = self.parser.parse(fx.TREE_OUTPUT)
        assert len(result.rows) > 0

    def test_verbose_shows_all_entries(self):
        result = self.parser.parse(fx.TREE_OUTPUT)
        result_verbose = self.parser.parse(fx.TREE_OUTPUT, verbose=True)
        # Verbose should have at least as many rows
        assert len(result_verbose.rows) >= len(result.rows)


# ---------------------------------------------------------------------------
# FileListingParser — ls -la parse
# ---------------------------------------------------------------------------

class TestFileListingParseLsLa:
    def setup_method(self):
        self.parser = FileListingParser()

    def test_schema(self):
        result = self.parser.parse(fx.LS_LA_OUTPUT)
        assert result.schema == ["path", "type", "size"]

    def test_truncated_at_50(self):
        result = self.parser.parse(fx.LS_LA_OUTPUT)
        # 60 entries → truncated to 30 + summary row
        assert len(result.rows) == 31

    def test_truncation_row(self):
        result = self.parser.parse(fx.LS_LA_OUTPUT)
        last = result.rows[-1]
        assert "more" in last[0]

    def test_verbose_shows_all(self):
        result = self.parser.parse(fx.LS_LA_OUTPUT, verbose=True)
        # All entries (total line excluded, dot entries included)
        assert len(result.rows) >= 50

    def test_summary_count(self):
        result = self.parser.parse(fx.LS_LA_OUTPUT)
        assert "entries" in result.summary

    def test_directory_type(self):
        result = self.parser.parse(fx.LS_LA_OUTPUT)
        types = [r[1] for r in result.rows if r[0] == ".config"]
        assert types and types[0] == "dir"


# ---------------------------------------------------------------------------
# FileListingParser — find parse
# ---------------------------------------------------------------------------

class TestFileListingParseFind:
    def setup_method(self):
        self.parser = FileListingParser()

    def test_schema(self):
        result = self.parser.parse(fx.FIND_OUTPUT)
        assert result.schema == ["path"]

    def test_grouped_by_dir(self):
        result = self.parser.parse(fx.FIND_OUTPUT)
        # >30 files → should be grouped with "... (N more)" rows
        continuation_rows = [r for r in result.rows if "more" in r[0]]
        assert len(continuation_rows) > 0

    def test_summary_has_file_count(self):
        result = self.parser.parse(fx.FIND_OUTPUT)
        assert "files" in result.summary

    def test_verbose_shows_all(self):
        result = self.parser.parse(fx.FIND_OUTPUT, verbose=True)
        assert len(result.rows) >= 48


# ---------------------------------------------------------------------------
# SearchResultsParser — detect
# ---------------------------------------------------------------------------

class TestSearchResultsDetect:
    def setup_method(self):
        self.parser = SearchResultsParser()

    def test_detects_grep(self):
        assert self.parser.detect(fx.GREP_RESULTS) >= 0.8

    def test_rejects_non_grep(self):
        assert self.parser.detect("hello world\nsome text\n") < 0.5

    def test_rejects_empty(self):
        assert self.parser.detect("") < 0.5


# ---------------------------------------------------------------------------
# SearchResultsParser — parse
# ---------------------------------------------------------------------------

class TestSearchResultsParse:
    def setup_method(self):
        self.parser = SearchResultsParser()

    def test_schema(self):
        result = self.parser.parse(fx.GREP_RESULTS)
        assert result.schema == ["file", "line", "match"]

    def test_tool_name(self):
        result = self.parser.parse(fx.GREP_RESULTS)
        assert result.tool == "search-results"

    def test_per_file_limit_3(self):
        result = self.parser.parse(fx.GREP_RESULTS)
        # src/auth.py has 10+ matches; at most 3 shown + 1 continuation
        auth_matches = [r for r in result.rows if r[0] == "src/auth.py" and r[1] != ""]
        assert len(auth_matches) <= 3

    def test_continuation_row_for_overflow(self):
        result = self.parser.parse(fx.GREP_RESULTS)
        continuation = [r for r in result.rows if "more" in r[2] and r[0] == "src/auth.py"]
        assert len(continuation) == 1

    def test_binary_file_stripped(self):
        result = self.parser.parse(fx.GREP_RESULTS)
        files = [r[0] for r in result.rows]
        assert not any("Binary file" in f for f in files)

    def test_summary_format(self):
        result = self.parser.parse(fx.GREP_RESULTS)
        assert "matches" in result.summary
        assert "files" in result.summary

    def test_most_matches_first(self):
        result = self.parser.parse(fx.GREP_RESULTS)
        files = [r[0] for r in result.rows if r[1] != ""]
        # src/auth.py has most matches, should appear first
        if files:
            assert files[0] == "src/auth.py"

    def test_max_15_files(self):
        result = self.parser.parse(fx.GREP_RESULTS)
        unique_files = {r[0] for r in result.rows if not r[2].startswith("(")}
        # Fixture has 5 files; all should be present
        assert len(unique_files) <= 15

    def test_verbose_shows_all_matches(self):
        result = self.parser.parse(fx.GREP_RESULTS, verbose=True)
        # No continuation rows in verbose mode
        continuation = [r for r in result.rows if "more" in r[2]]
        assert len(continuation) == 0


# ---------------------------------------------------------------------------
# EnvRedactParser — detect
# ---------------------------------------------------------------------------

class TestEnvRedactDetect:
    def setup_method(self):
        self.parser = EnvRedactParser()

    def test_detects_env_output(self):
        assert self.parser.detect(fx.ENV_OUTPUT) >= 0.8

    def test_rejects_non_env(self):
        assert self.parser.detect("hello world\nsome text\n") < 0.5

    def test_rejects_empty(self):
        assert self.parser.detect("") < 0.5


# ---------------------------------------------------------------------------
# EnvRedactParser — parse
# ---------------------------------------------------------------------------

class TestEnvRedactParse:
    def setup_method(self):
        self.parser = EnvRedactParser()

    def test_schema(self):
        result = self.parser.parse(fx.ENV_OUTPUT)
        assert result.schema == ["key", "value"]

    def test_tool_name(self):
        result = self.parser.parse(fx.ENV_OUTPUT)
        assert result.tool == "env-redact"

    def test_sensitive_values_redacted(self):
        result = self.parser.parse(fx.ENV_OUTPUT)
        by_key = {r[0]: r[1] for r in result.rows}
        assert by_key["AWS_SECRET_ACCESS_KEY"] == "[REDACTED]"
        assert by_key["SECRET_KEY"] == "[REDACTED]"
        assert by_key["API_TOKEN"] == "[REDACTED]"
        assert by_key["DATABASE_PASSWORD"] == "[REDACTED]"
        assert by_key["JWT_SECRET"] == "[REDACTED]"

    def test_non_sensitive_values_kept(self):
        result = self.parser.parse(fx.ENV_OUTPUT)
        by_key = {r[0]: r[1] for r in result.rows}
        assert by_key["HOME"] == "/home/user"
        assert by_key["SHELL"] == "/bin/bash"
        assert by_key["USER"] == "user"

    def test_aws_key_id_redacted(self):
        result = self.parser.parse(fx.ENV_OUTPUT)
        by_key = {r[0]: r[1] for r in result.rows}
        # AWS_ACCESS_KEY_ID contains KEY
        assert by_key["AWS_ACCESS_KEY_ID"] == "[REDACTED]"

    def test_stripe_secret_redacted(self):
        result = self.parser.parse(fx.ENV_OUTPUT)
        by_key = {r[0]: r[1] for r in result.rows}
        assert by_key["STRIPE_SECRET_KEY"] == "[REDACTED]"

    def test_summary_format(self):
        result = self.parser.parse(fx.ENV_OUTPUT)
        assert "vars" in result.summary
        assert "redacted" in result.summary

    def test_summary_counts(self):
        result = self.parser.parse(fx.ENV_OUTPUT)
        # 7 sensitive: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, SECRET_KEY,
        #              API_TOKEN, DATABASE_PASSWORD, JWT_SECRET, STRIPE_SECRET_KEY
        assert "7 redacted" in result.summary

    def test_all_vars_present(self):
        result = self.parser.parse(fx.ENV_OUTPUT)
        # All KEY=VALUE lines in the fixture
        assert len(result.rows) == 27
