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
