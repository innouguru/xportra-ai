"""Production runtime dependency declaration — regression tests.

Guards the Render startup failure `uvicorn: command not found`:
the Render start command invokes the `uvicorn` console script, so
Uvicorn must stay a declared runtime dependency in
`pyproject.toml` with a range-pinned constraint consistent with the
project dependency policy (explicit lower + upper bounds, CD-10–CD-13).

Stdlib only (`tomllib`, `importlib.metadata`): no new test
dependencies, no network, no installs.
"""

import importlib.metadata as metadata
import pathlib
import re
import tomllib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]

_START_COMMAND_EXECUTABLE = "uvicorn"

_REQUIREMENT_NAME = re.compile(r"^\s*([A-Za-z0-9_.\-]+)")


def runtime_dependencies():
    with open(ROOT / "pyproject.toml", "rb") as handle:
        return list(tomllib.load(handle)["project"]["dependencies"])


def requirement_name(requirement):
    match = _REQUIREMENT_NAME.match(requirement)
    if match is None:
        raise AssertionError(
            f"unparseable dependency declaration: {requirement!r}")
    return match.group(1).lower().replace("_", "-")


class ProductionRuntimeDependencyTests(unittest.TestCase):
    def test_uvicorn_declared_as_runtime_dependency(self):
        names = [requirement_name(req)
                 for req in runtime_dependencies()]
        self.assertIn(_START_COMMAND_EXECUTABLE, names)

    def test_uvicorn_constraint_is_range_pinned(self):
        matches = [
            req for req in runtime_dependencies()
            if requirement_name(req) == _START_COMMAND_EXECUTABLE
        ]
        self.assertEqual(len(matches), 1)
        # Policy: explicit lower bound plus an upper bound, exactly
        # like every other runtime dependency in the section.
        self.assertIn(">=", matches[0])
        self.assertIn(",<", matches[0])

    def test_no_duplicate_runtime_dependencies(self):
        names = [requirement_name(req)
                 for req in runtime_dependencies()]
        self.assertEqual(len(names), len(set(names)))

    def test_installed_uvicorn_exposes_console_script(self):
        # The deployed failure mode is a missing executable, not a
        # missing import: pin that the installed distribution ships
        # the console script the Render start command invokes.
        scripts = {
            entry_point.name
            for entry_point in metadata.distribution(
                _START_COMMAND_EXECUTABLE).entry_points
            if entry_point.group == "console_scripts"
        }
        self.assertIn(_START_COMMAND_EXECUTABLE, scripts)


if __name__ == "__main__":
    unittest.main()
