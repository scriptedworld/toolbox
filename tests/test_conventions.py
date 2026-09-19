"""Tests for the repository's own conventions, where a checker cannot be the one asking.

These hold toolbox to rules it states about itself, not to rules it enforces
elsewhere. `bin/test-traceability.py` can tell that a requirement has
no test; it cannot tell that a fixture was captured rather than composed.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml
from conftest import ROOT, script_argv

FIXTURES = ROOT / "tests" / "fixtures"

# `# gofmt (go1.26.6 linux/amd64), captured 2026-08-20 from ...`: a tool, a
# version, and an ISO date. Not anchored at the end: several fixtures say what
# was run and on what after the date, which is useful and is not the part being
# held to a shape.
PROVENANCE = re.compile(r"^#\s*\S+.*\d+\.\d+.*captured \d{4}-\d{2}-\d{2}")


# COVERS: NFR-4 | property
def test_every_fixture_records_the_tool_version_and_the_date():
    """A fixture composed by hand tests whoever composed it.

    The rule only holds if something asks, because the failure is
    silent: a hand-written fixture passes for as long as nobody compares it with
    what the tool actually prints.
    """
    fixtures = sorted(FIXTURES.rglob("*.txt"))
    assert fixtures, "the fixture set is empty, so this test would pass vacuously"
    for path in fixtures:
        first = path.read_text(encoding="utf-8").splitlines()[0]
        assert PROVENANCE.match(first), f"{path.relative_to(ROOT)} opens with {first!r}, which names no tool version and no capture date"


# COVERS: NFR-2 | property
def test_a_spawned_script_is_measured_when_the_parent_is_under_coverage():
    """The guarantee that replaced 'tests must run in-process'.

    Asserted on the command and not on a coverage figure, because a figure
    would need a second coverage run inside this one. What can go wrong here is
    the routing: `script_argv` returning a plain interpreter invocation while the
    parent is measured is exactly the silent 0% this requirement is about.
    """
    argv = script_argv(ROOT / "adapters" / "go" / "gofmt.py", "--flag")

    if "coverage" in sys.modules:
        assert argv[:5] == [sys.executable, "-m", "coverage", "run", "--parallel-mode"], argv
        assert argv[-2:] == [str(ROOT / "adapters" / "go" / "gofmt.py"), "--flag"]
    else:
        assert argv == [sys.executable, str(ROOT / "adapters" / "go" / "gofmt.py"), "--flag"]


# COVERS: NFR-2 | edge
def test_the_routing_is_decided_by_the_parent_and_not_by_a_flag():
    """`coverage` in `sys.modules` is the whole condition.

    A bare `pytest` run must spawn the plain interpreter, so the suite needs
    nothing installed to run. That is NFR-1's constraint, and making the
    coverage invocation unconditional would break it.
    """
    argv = script_argv(Path("x.py"))
    assert argv[0] == sys.executable
    assert ("-m" in argv) == ("coverage" in sys.modules)


# ---- the two contracts, held from outside -----------------------------------


CHECKERS = sorted(path for path in (ROOT / "bin").glob("*.py"))
ADAPTERS = sorted(path for path in (ROOT / "adapters").rglob("*.py") if path.name != "__init__.py")

# A clock, a network call, or a source of entropy in an adapter. `subprocess` is
# here too: an adapter that shells out is reading something it was not handed.
IMPURE = ("time", "datetime", "socket", "http", "urllib", "requests", "subprocess", "random", "secrets", "shutil", "tempfile")

# What a test may spawn. Every other tool a jig names has to be absent for the
# suite to run inside the image anvil builds to hold them.
SPAWNABLE = ("sys.executable", "found", "GIT", "claude")


def source(path: Path) -> str:
    """One file's text."""
    return path.read_text(encoding="utf-8")


# COVERS: FR-2.1 | property
def test_every_checker_exits_with_its_verdict_and_needs_no_adapter():
    """A checker's exit code is the verdict, which is why no task here names one for a checker."""
    assert CHECKERS, "no checkers found, so the contract is untested"
    for path in CHECKERS:
        text = source(path)
        assert "def main(" in text, f"{path.name} has no main()"
        assert "sys.exit(main(" in text, f"{path.name} does not exit with what main() returns"

    for jig in sorted(one for one in ROOT.glob("bolt.*.yaml") if not one.name.endswith(".definitions.yaml")):
        document = yaml.safe_load(jig.read_text(encoding="utf-8"))
        for task in document.get("tasks") or []:
            runs_checker = any(f"bin/{path.name}" in (task.get("command") or "") for path in CHECKERS)
            assert not (runs_checker and task.get("adapter")), f"{jig.name}:{task['name']} runs a checker and names an adapter"


# COVERS: FR-3.8 | property
def test_no_adapter_reads_a_clock_a_network_or_anything_it_was_not_handed():
    """An adapter takes a record or the evidence it is named, and writes its envelope.

    Held by import: a module that cannot reach the network or the clock cannot
    depend on either, which is what makes a fixture enough to test it on a
    machine without the tool installed.
    """
    assert ADAPTERS, "no adapters found, so the contract is untested"
    for path in ADAPTERS:
        for line in source(path).splitlines():
            words = line.split()
            if words[:1] == ["import"] or words[:1] == ["from"]:
                module = words[1].split(".")[0]
                assert module not in IMPURE, f"{path.relative_to(ROOT)} imports {module}"


# COVERS: NFR-1 | property
def test_the_suite_spawns_only_the_interpreter_and_git():
    """No test runs a tool a jig names, so the suite runs where none of them are installed."""
    calls = 0
    for path in sorted((ROOT / "tests").glob("*.py")):
        for number, line in enumerate(source(path).splitlines(), 1):
            # A fixture writes source for a checker to read, and its escaped
            # newline is what tells such a line from a call this suite makes.
            if "\\n" in line:
                continue
            for hit in re.finditer(r"subprocess\.run\(\s*\[?([A-Za-z_.]+)", line):
                calls += 1
                first = hit.group(1)
                assert first in SPAWNABLE or first.startswith(("script_argv", "argv")), f"{path.name}:{number} spawns {first}"
    assert calls, "no spawning test found, so the constraint is untested"
