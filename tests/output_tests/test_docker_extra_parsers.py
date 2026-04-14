"""Tests for docker compose, docker ps/images, and docker logs parsers."""

from tokkit_output.parsers.docker_compose import DockerComposeParser
from tokkit_output.parsers.docker_ps import DockerPsParser
from tokkit_output.parsers.docker_logs import DockerLogsParser
from tests.output_tests.fixtures import docker_extra_output as fx


# ===========================================================================
# TestDockerComposeDetect
# ===========================================================================

class TestDockerComposeDetect:
    def setup_method(self):
        self.parser = DockerComposeParser()

    def test_detects_compose_ps_table(self):
        assert self.parser.detect(fx.COMPOSE_PS) >= 0.7

    def test_detects_compose_ps_unhealthy(self):
        assert self.parser.detect(fx.COMPOSE_PS_WITH_UNHEALTHY) >= 0.7

    def test_detects_compose_logs(self):
        assert self.parser.detect(fx.COMPOSE_LOGS) >= 0.7

    def test_rejects_plain_text(self):
        assert self.parser.detect("hello world\nsome random text\nno docker here\n") < 0.5

    def test_rejects_docker_ps(self):
        # docker ps has CONTAINER ID header, not compose
        assert self.parser.detect(fx.DOCKER_PS) < 0.5


# ===========================================================================
# TestDockerComposeParsePsHealthy
# ===========================================================================

class TestDockerComposeParsePsHealthy:
    def setup_method(self):
        self.parser = DockerComposeParser()

    def test_all_healthy_summary(self):
        result = self.parser.parse(fx.COMPOSE_PS)
        assert result.tool == "docker-compose"
        assert "all healthy" in result.summary
        assert "5 services" in result.summary

    def test_healthy_services_elided(self):
        result = self.parser.parse(fx.COMPOSE_PS)
        # All services are healthy, so no rows should be shown
        assert result.rows == []

    def test_schema_is_correct(self):
        result = self.parser.parse(fx.COMPOSE_PS)
        assert result.schema == ["service", "status", "ports"]

    def test_unhealthy_services_shown(self):
        result = self.parser.parse(fx.COMPOSE_PS_WITH_UNHEALTHY)
        statuses = [r[1] for r in result.rows]
        # Restarting and Exited must appear
        assert any("Restarting" in s for s in statuses)
        assert any("Exited" in s for s in statuses)

    def test_healthy_services_elided_in_mixed(self):
        result = self.parser.parse(fx.COMPOSE_PS_WITH_UNHEALTHY)
        statuses = [r[1] for r in result.rows]
        # Up/healthy services should not appear in rows
        assert not any(s.startswith("Up") and "Exited" not in s and "Restarting" not in s for s in statuses if not any(bad in s for bad in ["Restarting", "Exited", "Dead"]))

    def test_unhealthy_summary_counts(self):
        result = self.parser.parse(fx.COMPOSE_PS_WITH_UNHEALTHY)
        # 5 services total: 3 healthy, 2 unhealthy
        assert "5 services" in result.summary
        assert "3 healthy" in result.summary
        assert "2 unhealthy" in result.summary

    def test_verbose_shows_all_services(self):
        result = self.parser.parse(fx.COMPOSE_PS, verbose=True)
        # All 5 services should appear
        assert len(result.rows) == 5

    def test_verbose_shows_all_mixed(self):
        result = self.parser.parse(fx.COMPOSE_PS_WITH_UNHEALTHY, verbose=True)
        assert len(result.rows) == 5


# ===========================================================================
# TestDockerComposeParseLogs
# ===========================================================================

class TestDockerComposeParseLogs:
    def setup_method(self):
        self.parser = DockerComposeParser()

    def test_schema_is_correct(self):
        result = self.parser.parse(fx.COMPOSE_LOGS)
        assert result.schema == ["service", "line"]

    def test_summary_format(self):
        result = self.parser.parse(fx.COMPOSE_LOGS)
        assert "services" in result.summary
        assert "log lines" in result.summary

    def test_three_services_in_summary(self):
        result = self.parser.parse(fx.COMPOSE_LOGS)
        assert "3 services" in result.summary

    def test_error_preserved(self):
        result = self.parser.parse(fx.COMPOSE_LOGS)
        all_lines = [r[1] for r in result.rows]
        assert any("ERROR" in ln for ln in all_lines)

    def test_compressed_fewer_rows_than_raw_lines(self):
        result = self.parser.parse(fx.COMPOSE_LOGS)
        raw_lines = [ln for ln in fx.COMPOSE_LOGS.splitlines() if ln.strip()]
        assert len(result.rows) < len(raw_lines)

    def test_gap_markers_present(self):
        result = self.parser.parse(fx.COMPOSE_LOGS)
        all_lines = [r[1] for r in result.rows]
        assert any("skipped" in ln for ln in all_lines)

    def test_service_names_in_rows(self):
        result = self.parser.parse(fx.COMPOSE_LOGS)
        services = {r[0] for r in result.rows if not r[1].startswith("...")}
        assert "web-1" in services
        assert "api-1" in services
        assert "worker-1" in services

    def test_verbose_shows_all(self):
        result = self.parser.parse(fx.COMPOSE_LOGS, verbose=True)
        all_lines = [r[1] for r in result.rows]
        assert not any("skipped" in ln for ln in all_lines)
        raw_lines = [ln for ln in fx.COMPOSE_LOGS.splitlines() if ln.strip()]
        assert len(result.rows) == len(raw_lines)

    def test_error_neighborhood_preserved(self):
        result = self.parser.parse(fx.COMPOSE_LOGS)
        all_lines = [r[1] for r in result.rows]
        # The line before ERROR in api-1 should be present
        assert any("POST /api/orders" in ln for ln in all_lines)
        # The line after ERROR should be present (retry queue)
        assert any("Queuing email" in ln or "retry" in ln.lower() for ln in all_lines)


# ===========================================================================
# TestDockerPsDetect
# ===========================================================================

class TestDockerPsDetect:
    def setup_method(self):
        self.parser = DockerPsParser()

    def test_detects_docker_ps(self):
        assert self.parser.detect(fx.DOCKER_PS) >= 0.85

    def test_detects_docker_images(self):
        assert self.parser.detect(fx.DOCKER_IMAGES) >= 0.8

    def test_rejects_plain_text(self):
        assert self.parser.detect("hello world\nsome random text\n") < 0.5

    def test_rejects_compose_logs(self):
        assert self.parser.detect(fx.COMPOSE_LOGS) < 0.5


# ===========================================================================
# TestDockerPsParse
# ===========================================================================

class TestDockerPsParse:
    def setup_method(self):
        self.parser = DockerPsParser()

    def test_schema_is_correct(self):
        result = self.parser.parse(fx.DOCKER_PS)
        assert result.schema == ["name", "image", "status", "ports"]

    def test_summary_counts(self):
        result = self.parser.parse(fx.DOCKER_PS)
        assert "5 containers" in result.summary
        assert "3 running" in result.summary
        assert "2 stopped" in result.summary

    def test_stopped_containers_elided(self):
        result = self.parser.parse(fx.DOCKER_PS)
        # Default mode: only running containers shown
        statuses = [r[2] for r in result.rows]
        assert not any("Exited" in s for s in statuses)

    def test_running_containers_shown(self):
        result = self.parser.parse(fx.DOCKER_PS)
        statuses = [r[2] for r in result.rows]
        assert all(s.startswith("Up") for s in statuses)
        assert len(result.rows) == 3

    def test_verbose_shows_all(self):
        result = self.parser.parse(fx.DOCKER_PS, verbose=True)
        assert len(result.rows) == 5

    def test_images_parse(self):
        result = self.parser.parse(fx.DOCKER_IMAGES)
        assert result.schema == ["repository", "tag", "size", "created"]
        assert "7 images" in result.summary
        assert len(result.rows) == 7

    def test_images_rows_content(self):
        result = self.parser.parse(fx.DOCKER_IMAGES)
        repos = [r[0] for r in result.rows]
        assert "myapp-web" in repos
        assert "postgres" in repos
        assert "redis" in repos

    def test_images_tags(self):
        result = self.parser.parse(fx.DOCKER_IMAGES)
        tags = [r[1] for r in result.rows]
        assert "latest" in tags
        assert "v2.1.0" in tags
        assert "7-alpine" in tags


# ===========================================================================
# TestDockerLogsDetect
# ===========================================================================

class TestDockerLogsDetect:
    def setup_method(self):
        self.parser = DockerLogsParser()

    def test_detects_timestamp_logs(self):
        assert self.parser.detect(fx.DOCKER_LOGS_SIMPLE) >= 0.7

    def test_rejects_plain_text(self):
        assert self.parser.detect("hello world\nsome random text\nno timestamps\n") < 0.5

    def test_rejects_compose_ps(self):
        assert self.parser.detect(fx.COMPOSE_PS) < 0.5


# ===========================================================================
# TestDockerLogsParse
# ===========================================================================

class TestDockerLogsParse:
    def setup_method(self):
        self.parser = DockerLogsParser()

    def test_schema_is_correct(self):
        result = self.parser.parse(fx.DOCKER_LOGS_SIMPLE)
        assert result.schema == ["line"]

    def test_summary_format(self):
        result = self.parser.parse(fx.DOCKER_LOGS_SIMPLE)
        assert "log lines" in result.summary
        assert "2 errors" in result.summary

    def test_compressed_fewer_rows_than_raw(self):
        result = self.parser.parse(fx.DOCKER_LOGS_SIMPLE)
        raw_lines = [ln for ln in fx.DOCKER_LOGS_SIMPLE.splitlines() if ln.strip()]
        assert len(result.rows) < len(raw_lines)

    def test_error_lines_preserved(self):
        result = self.parser.parse(fx.DOCKER_LOGS_SIMPLE)
        all_lines = [r[0] for r in result.rows]
        errors = [ln for ln in all_lines if "ERROR" in ln]
        assert len(errors) == 2

    def test_head_lines_present(self):
        result = self.parser.parse(fx.DOCKER_LOGS_SIMPLE)
        all_lines = [r[0] for r in result.rows]
        # First log line should appear in head
        assert any("Starting myapp-api" in ln for ln in all_lines)

    def test_tail_lines_present(self):
        result = self.parser.parse(fx.DOCKER_LOGS_SIMPLE)
        all_lines = [r[0] for r in result.rows]
        # Last log line should appear in tail
        assert any("Shutdown complete" in ln for ln in all_lines)

    def test_gap_markers_present(self):
        result = self.parser.parse(fx.DOCKER_LOGS_SIMPLE)
        all_lines = [r[0] for r in result.rows]
        assert any("skipped" in ln for ln in all_lines)

    def test_error_neighborhood_preserved(self):
        result = self.parser.parse(fx.DOCKER_LOGS_SIMPLE)
        all_lines = [r[0] for r in result.rows]
        # Lines around first ERROR (payment gateway)
        assert any("Retrying payment gateway" in ln for ln in all_lines)
        # Lines around second ERROR (SMTP)
        assert any("Queuing email for retry" in ln for ln in all_lines)

    def test_verbose_shows_all(self):
        result = self.parser.parse(fx.DOCKER_LOGS_SIMPLE, verbose=True)
        all_lines = [r[0] for r in result.rows]
        assert not any("skipped" in ln for ln in all_lines)
        raw_lines = [ln for ln in fx.DOCKER_LOGS_SIMPLE.splitlines() if ln.strip()]
        assert len(result.rows) == len(raw_lines)

    def test_short_input_shows_all(self):
        short_logs = "\n".join([
            f"2026-04-13T10:00:0{i}.000Z INFO  Line {i}" for i in range(10)
        ])
        result = self.parser.parse(short_logs)
        assert len(result.rows) == 10
        all_lines = [r[0] for r in result.rows]
        assert not any("skipped" in ln for ln in all_lines)
