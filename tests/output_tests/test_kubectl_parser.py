"""Tests for kubectl output parser."""

from tokkit_output.parsers.kubectl import KubectlParser
from tests.output_tests.fixtures import k8s_output as fx


class TestKubectlDetect:
    def setup_method(self):
        self.parser = KubectlParser()

    def test_detects_get_pods(self):
        assert self.parser.detect(fx.GET_PODS) >= 0.8

    def test_detects_describe(self):
        assert self.parser.detect(fx.DESCRIBE_POD) >= 0.7

    def test_detects_services(self):
        assert self.parser.detect(fx.GET_SERVICES) >= 0.7

    def test_rejects_non_k8s(self):
        assert self.parser.detect("hello world\nsome random text\nno kubectl here\n") < 0.6


class TestKubectlParsePods:
    def setup_method(self):
        self.parser = KubectlParser()

    def test_elides_healthy_pods(self):
        result = self.parser.parse(fx.GET_PODS)
        # Only unhealthy rows should be shown
        statuses = [r[2] for r in result.rows]
        assert "CrashLoopBackOff" in statuses
        # Running pods should not appear in rows
        assert not any(s == "Running" for s in statuses)
        # Summary should mention healthy count
        assert "healthy" in result.summary

    def test_elides_completed_pods(self):
        result = self.parser.parse(fx.GET_PODS)
        statuses = [r[2] for r in result.rows]
        assert "Completed" not in statuses

    def test_summary_counts(self):
        result = self.parser.parse(fx.GET_PODS)
        # 13 pods total
        assert "13 pods" in result.summary
        # 11 healthy (CrashLoopBackOff + Completed excluded)
        assert "11 healthy" in result.summary
        # 1 unhealthy
        assert "1 unhealthy" in result.summary

    def test_all_healthy_summary_only(self):
        result = self.parser.parse(fx.GET_PODS_ALL_HEALTHY)
        # No unhealthy rows
        assert result.rows == []
        assert "healthy" in result.summary
        assert "3 pods" in result.summary

    def test_verbose_shows_all(self):
        result = self.parser.parse(fx.GET_PODS, verbose=True)
        # All 13 rows should be present
        assert len(result.rows) >= 10

    def test_services_parsed(self):
        result = self.parser.parse(fx.GET_SERVICES)
        # Services table: all 3 rows present
        assert len(result.rows) >= 3

    def test_schema_from_header(self):
        result = self.parser.parse(fx.GET_PODS)
        # Schema should include lowercased column names
        assert "name" in result.schema
        assert "status" in result.schema

    def test_services_schema(self):
        result = self.parser.parse(fx.GET_SERVICES)
        assert "name" in result.schema
        assert "type" in result.schema


class TestKubectlParseDescribe:
    def setup_method(self):
        self.parser = KubectlParser()

    def test_describe_extracts_key_sections(self):
        result = self.parser.parse(fx.DESCRIBE_POD)
        assert result.tool == "kubectl"
        assert result.schema == ["section", "key", "value"]
        # CrashLoopBackOff should appear somewhere in values
        values = [r[2] for r in result.rows]
        assert any("CrashLoopBackOff" in v for v in values)

    def test_describe_excludes_last_applied_configuration(self):
        result = self.parser.parse(fx.DESCRIBE_POD)
        # Long annotation blob should be excluded
        values = [r[2] for r in result.rows]
        assert not any("last-applied-configuration" in v for v in values)
        # The JSON blob itself should not appear
        assert not any("apiVersion" in v for v in values)

    def test_describe_verbose_includes_annotations(self):
        result = self.parser.parse(fx.DESCRIBE_POD, verbose=True)
        keys = [r[1] for r in result.rows]
        assert "Annotations" in keys

    def test_describe_summary_has_name(self):
        result = self.parser.parse(fx.DESCRIBE_POD)
        assert "payment-svc-9e8f7a6b5-crash" in result.summary

    def test_describe_has_events(self):
        result = self.parser.parse(fx.DESCRIBE_POD)
        sections = [r[0] for r in result.rows]
        assert any("event" in s.lower() for s in sections)


class TestKubectlParseLogs:
    def setup_method(self):
        self.parser = KubectlParser()

    def test_logs_head_tail_with_errors(self):
        result = self.parser.parse(fx.LOGS_WITH_ERRORS)
        assert result.tool == "kubectl"
        assert result.schema == ["line"]

        all_lines = [r[0] for r in result.rows]

        # ERROR lines must be preserved
        assert any("ERROR" in ln for ln in all_lines)

        # First log line (startup) should be in head
        assert any("Starting" in ln for ln in all_lines)

        # Last log line (shutdown) should be in tail
        assert any("Shutdown complete" in ln or "shutdown" in ln.lower() for ln in all_lines)

        # Output should be compressed — fewer lines than total
        assert len(result.rows) < 72

    def test_logs_summary_format(self):
        result = self.parser.parse(fx.LOGS_WITH_ERRORS)
        assert "log lines" in result.summary
        assert "2 errors" in result.summary

    def test_logs_gap_markers(self):
        result = self.parser.parse(fx.LOGS_WITH_ERRORS)
        all_lines = [r[0] for r in result.rows]
        # There should be at least one gap marker
        assert any("skipped" in ln for ln in all_lines)

    def test_logs_verbose_shows_all(self):
        result = self.parser.parse(fx.LOGS_WITH_ERRORS, verbose=True)
        # All lines present, no gap markers
        all_lines = [r[0] for r in result.rows]
        assert not any("skipped" in ln for ln in all_lines)
        # Total line count matches fixture
        total_fixture_lines = len([ln for ln in fx.LOGS_WITH_ERRORS.splitlines() if ln.strip()])
        assert len(result.rows) == total_fixture_lines

    def test_logs_error_neighborhood_preserved(self):
        result = self.parser.parse(fx.LOGS_WITH_ERRORS)
        all_lines = [r[0] for r in result.rows]
        # Lines immediately after the first ERROR should be present
        assert any("Queuing payment for retry" in ln for ln in all_lines)
        # Lines immediately before the second ERROR should be present
        assert any("Validating payment payload" in ln for ln in all_lines)
