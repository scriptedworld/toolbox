"""Load the scripts under test, and give tests one way to call each contract.

Nothing in `bin/` or `adapters/` is importable by name: neither directory is a
package, and a hyphen is not valid in a Python identifier, so
`bin/test-traceability.py` can only be reached by path.

The two fixtures below are the two contracts in
`docs/PATTERNS/testing-checkers-and-adapters.md`. A checker is
`argv` plus a directory, and its exit code is the verdict. An adapter is `argv`
plus a record on stdin, and its envelope is the verdict.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from types import ModuleType

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent


def load(relative: str) -> ModuleType:
    """Import a checker or adapter from its path within this repository."""
    path = ROOT / relative
    # Namespaced, because `bin/test-traceability.py` would otherwise register
    # itself as `test_traceability` and collide with the test file of that
    # name, which pytest reports as an import file mismatch rather than as a
    # collision.
    name = "under_test." + path.stem.replace("-", "_")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def script_argv(path: Path, *args: str) -> list[str]:
    """The command that runs a checker or adapter as its own process.

    UNDER COVERAGE WHEN THE PARENT IS. These scripts are spawned rather than
    called, because the shebang, the imports, and where `main()` writes its
    envelope are all part of the contract and an in-process call proves none of
    them. A spawned process is invisible to the parent's coverage, though, so
    until 2026-09-04 every script tested only this way reported 0% with a full
    suite behind it: `adapters/go/coverage.py` measured 0 of 96 lines, and
    `adapters/common/bolt-result.py` 0 of 65.

    That is worse than a gap, because the number was going to be gated. A
    per-file threshold reading those figures would have failed two well-tested
    adapters and pressed whoever fixed it to rewrite good subprocess tests as
    weaker in-process ones to move a number that was measuring the wrong thing.

    `--parallel-mode` makes each child write its own data file, and the jig's
    `tests` task runs `coverage combine` before reporting, which folds them back
    together. Detection is `"coverage" in sys.modules`, so a bare `pytest` run
    spawns the plain interpreter and needs nothing installed.
    """
    if "coverage" in sys.modules:
        return [
            sys.executable,
            "-m",
            "coverage",
            "run",
            "--parallel-mode",
            str(path),
            *args,
        ]
    return [sys.executable, str(path), *args]


@pytest.fixture
def checker(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[ModuleType, Sequence[str], Path], tuple[int, str]]:
    """Run a checker's `main()` in a directory, returning its exit code and output."""

    def run(module: ModuleType, argv: Sequence[str], cwd: Path) -> tuple[int, str]:
        monkeypatch.chdir(cwd)
        monkeypatch.setattr(sys, "argv", [str(module.__file__), *argv])
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            code = module.main()
        return code, captured.getvalue()

    return run


@pytest.fixture
def adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[..., dict[str, object]]:
    """Feed a record to an adapter's `main()` and return the envelope it writes."""

    def run(
        module: ModuleType,
        record: dict[str, object],
        argv: Sequence[str] = (),
    ) -> dict[str, object]:
        monkeypatch.setattr(sys, "argv", [str(module.__file__), *argv])
        monkeypatch.setattr(sys, "stdin", io.StringIO(yaml.safe_dump(record)))
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            module.main()
        loaded = yaml.safe_load(captured.getvalue())
        return loaded if isinstance(loaded, dict) else {}

    return run


def fixture_text(relative: str) -> str:
    """Read captured tool output, dropping the provenance comment on line one."""
    lines = (Path(__file__).parent / "fixtures" / relative).read_text(encoding="utf-8").splitlines(keepends=True)
    return "".join(lines[1:]) if lines and lines[0].startswith("#") else "".join(lines)
