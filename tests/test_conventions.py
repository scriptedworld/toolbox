"""Tests for the repository's own conventions, where a checker cannot be the one asking.

These hold toolbox to rules it states about itself rather than to rules it
enforces elsewhere. `bin/test-traceability.py` can tell that a requirement has
no test; it cannot tell that a fixture was captured rather than composed.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from conftest import ROOT, script_argv

FIXTURES = ROOT / "tests" / "fixtures"

# `# gofmt (go1.26.6 linux/amd64), captured 2026-08-20 from ...` — a tool, a
# version, and an ISO date. Not anchored at the end: several fixtures say what
# was run and on what after the date, which is worth having and is not the part
# being held to a shape.
PROVENANCE = re.compile(r"^#\s*\S+.*\d+\.\d+.*captured \d{4}-\d{2}-\d{2}")


# COVERS: NFR-4 | property
def test_every_fixture_records_the_tool_version_and_the_date():
    """A fixture composed by hand tests whoever composed it.

    The rule is only worth having if something asks, because the failure is
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

    Asserted on the command rather than on a coverage figure, because a figure
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
    nothing installed to run — which is NFR-1's constraint, and would be broken
    by making the coverage invocation unconditional.
    """
    argv = script_argv(Path("x.py"))
    assert argv[0] == sys.executable
    assert ("-m" in argv) == ("coverage" in sys.modules)
