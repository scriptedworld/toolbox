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
import shutil
import subprocess  # nosec B404
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


def script_argv(path: Path | str, *args: str) -> list[str]:
    """The command that runs a checker or adapter as its own process.

    Under coverage when the parent is. These scripts are spawned, not called,
    because the shebang, the imports, and where `main()` writes its envelope
    are all part of the contract and an in-process call proves none of them. A
    spawned process is invisible to the parent's coverage, though, so without
    this every script tested only this way reported 0% with a full suite behind
    it: `adapters/go/coverage.py` measured 0 of 96 lines, and
    `adapters/common/bolt-result.py` 0 of 65.

    That is worse than a gap, because the number was going to be gated. A
    per-file threshold reading those figures would have failed two well-tested
    adapters and pressed whoever fixed it to rewrite good subprocess tests as
    weaker in-process ones to move a number that was measuring the wrong thing.

    `--parallel-mode` makes each child write its own data file, and the jig's
    `tests` task runs `coverage combine` before reporting, which folds them back
    together. Detection is `"coverage" in sys.modules`, so a bare `pytest` run
    spawns the plain interpreter and needs nothing installed.

    The path is `Path | str` because a caller that has already built its whole
    argument list spreads it in as `script_argv(*argv)`, and the first element of
    a `list[str]` is a `str`.
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


def run_flag_adapter(adapter, tmp_path, evidence_name, evidence, *args, exitcode="0"):
    """Invoke a flag-contract adapter as bolt does and read the envelope it wrote.

    The coverage adapters take `--evidence`, `--work-dir` and `--exitcode` and
    write `output.yaml` into the work directory, where the stdin-contract
    adapters the `adapter` fixture serves read a record and print an envelope.
    This is that second shape, and it is here rather than in each test file
    because it was written out twice, identically, and pylint's R0801 was right
    about it.

    As a subprocess, because an in-process call cannot catch a broken shebang, a
    missing import, or a `main()` that writes somewhere other than where it was
    told. The envelope's location is part of the contract.

    `evidence` may be `bytes`, which is how a document declaring an encoding
    other than UTF-8 has to be written, or `None` to name no evidence at all.

    `exitcode=None` names a status file that was never written, which is the
    case where the adapter cannot tell whether the suite passed. It has to be
    named-but-absent rather than omitted, because omitting the flag is a
    different case: bolt always passes it.
    """
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    status = tmp_path / "exitcode"
    if exitcode is not None:
        status.write_text(exitcode, encoding="utf-8")

    argv = [str(adapter), "--work-dir", str(work)]
    if evidence is not None:
        path = tmp_path / evidence_name
        if isinstance(evidence, bytes):
            path.write_bytes(evidence)
        else:
            path.write_text(evidence, encoding="utf-8")
        argv += ["--evidence", str(path)]
    argv += ["--exitcode", str(status), *args]

    subprocess.run(script_argv(*argv), check=True, capture_output=True)  # nosec B603
    return yaml.safe_load((work / "output.yaml").read_text(encoding="utf-8"))


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


def git(tree: Path, *args: str) -> str:
    """git in the tree, with an identity and without the machine's hooks or signing.

    The two voice checks read real repositories, so their tests build real ones.
    """
    found = shutil.which("git")
    assert found is not None
    identity = ("-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false")
    return subprocess.run([found, "-C", str(tree), *identity, *args], capture_output=True, text=True, check=True).stdout.strip()  # nosec B603


def repository(tmp_path: Path, files: dict[str, str]) -> Path:
    """A repository with the files named, committed once."""
    tree = tmp_path / "repo"
    tree.mkdir(parents=True)
    for name, text in files.items():
        (tree / name).parent.mkdir(parents=True, exist_ok=True)
        (tree / name).write_text(text, encoding="utf-8")
    git(tree, "init", "-q")
    git(tree, "add", "-A")
    git(tree, "commit", "-q", "-m", "start")
    return tree
