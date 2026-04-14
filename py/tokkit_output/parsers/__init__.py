"""Parser registry."""

from tokkit_output.base import BaseParser

_REGISTRY: list[BaseParser] = []
_HINT_MAP: dict[str, BaseParser] = {}


def register(parser: BaseParser) -> None:
    """Register a parser in the global registry."""
    _REGISTRY.append(parser)
    for hint in parser.hint_values:
        _HINT_MAP[hint.lower()] = parser


def get_by_hint(hint: str) -> BaseParser | None:
    """Look up parser by hint string."""
    return _HINT_MAP.get(hint.lower())


def all_parsers() -> list[BaseParser]:
    """Return all registered parsers."""
    return list(_REGISTRY)


from tokkit_output.parsers.pytest_p import PytestParser
from tokkit_output.parsers.unittest_p import UnittestParser

register(PytestParser())
register(UnittestParser())

from tokkit_output.parsers.ruff import RuffParser
from tokkit_output.parsers.mypy import MypyParser
from tokkit_output.parsers.pyright import PyrightParser
from tokkit_output.parsers.pip import PipParser
from tokkit_output.parsers.traceback_p import TracebackParser

register(RuffParser())
register(MypyParser())
register(PyrightParser())
register(PipParser())
register(TracebackParser())

from tokkit_output.parsers.jest import JestParser
from tokkit_output.parsers.vitest import VitestParser
from tokkit_output.parsers.mocha import MochaParser
from tokkit_output.parsers.tsc import TscParser
from tokkit_output.parsers.eslint import EslintParser
from tokkit_output.parsers.webpack import WebpackParser
from tokkit_output.parsers.vite import ViteParser
from tokkit_output.parsers.npm import NpmParser

register(JestParser())
register(VitestParser())
register(MochaParser())
register(TscParser())
register(EslintParser())
register(WebpackParser())
register(ViteParser())
register(NpmParser())

from tokkit_output.parsers.cargo_test import CargoTestParser
from tokkit_output.parsers.cargo_build import CargoBuildParser
from tokkit_output.parsers.cargo_clippy import CargoClippyParser
from tokkit_output.parsers.docker import DockerParser

register(CargoTestParser())
register(CargoBuildParser())
register(CargoClippyParser())
register(DockerParser())

# --- Git parsers ---
from tokkit_output.parsers.git_diff import GitDiffParser
from tokkit_output.parsers.git_status import GitStatusParser
from tokkit_output.parsers.git_log import GitLogParser
from tokkit_output.parsers.git_show import GitShowParser
from tokkit_output.parsers.git_blame import GitBlameParser
from tokkit_output.parsers.git_branch import GitBranchParser
from tokkit_output.parsers.git_stash import GitStashParser

register(GitDiffParser())
register(GitStatusParser())
register(GitLogParser())
register(GitShowParser())
register(GitBlameParser())
register(GitBranchParser())
register(GitStashParser())

# --- Kubernetes ---
from tokkit_output.parsers.kubectl import KubectlParser

register(KubectlParser())

# --- Docker (compose, ps/images, logs) ---
from tokkit_output.parsers.docker_compose import DockerComposeParser
from tokkit_output.parsers.docker_ps import DockerPsParser
from tokkit_output.parsers.docker_logs import DockerLogsParser

register(DockerComposeParser())
register(DockerPsParser())
register(DockerLogsParser())

# --- Shell tools ---
from tokkit_output.parsers.package_list import PackageListParser
from tokkit_output.parsers.file_listing import FileListingParser
from tokkit_output.parsers.search_results import SearchResultsParser
from tokkit_output.parsers.gh_cli import GhCliParser
from tokkit_output.parsers.env_redact import EnvRedactParser

register(PackageListParser())
register(FileListingParser())
register(SearchResultsParser())
register(GhCliParser())
register(EnvRedactParser())
