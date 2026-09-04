"""Tests for `adapters/go/gofmt.py`, and the worked example for the rest.

`gofmt -l` lists unformatted files on stdout and exits 0 either way, so its exit
status answers "did gofmt run" and never "is this formatted". The adapter is
what turns that into a verdict, which makes the exit code irrelevant here and
the envelope everything.
"""

from __future__ import annotations

import subprocess  # nosec B404

import yaml
from conftest import ROOT, fixture_text, load, script_argv

gofmt = load("adapters/go/gofmt.py")


def record(stdout: str = "", stderr: str = "", exitcode: int = 0) -> dict[str, object]:
    """An execution record shaped the way bolt writes one."""
    return {"captures": {"stdout": stdout, "stderr": stderr, "exitcode": exitcode}}


# COVERS: FR-3.5 | positive
def test_a_clean_tree_succeeds(adapter):
    """gofmt printing nothing is the pass, and the envelope carries no reasons."""
    envelope = adapter(gofmt, record(fixture_text("gofmt/clean.txt")))
    assert envelope["success"] is True
    assert "reasons" not in envelope


# COVERS: FR-3.2, FR-3.4 | positive
def test_each_unformatted_file_becomes_one_reason(adapter):
    """Captured output from a real run: two files, two reasons, in order."""
    envelope = adapter(gofmt, record(fixture_text("gofmt/unformatted.txt")))
    assert envelope["success"] is False
    assert [reason["file"] for reason in envelope["reasons"]] == [
        "internal/cli/cli.go",
        "main.go",
    ]


# COVERS: FR-3.4 | property
def test_a_reason_names_its_checker_and_how_to_fix_it(adapter):
    """A reason nobody can act on is a reason nobody acts on."""
    envelope = adapter(gofmt, record(fixture_text("gofmt/unformatted.txt")))
    first = envelope["reasons"][0]
    assert first["checker"] == "format"
    assert "not gofmt-clean" in first["message"]
    assert first["fix"].startswith("gofmt -w ")


# COVERS: FR-3.4 | edge
def test_a_leading_dot_slash_is_stripped_from_the_file(adapter):
    """gofmt echoes the path it was given; the reason names the file, not the walk."""
    envelope = adapter(gofmt, record("./cmd/bolt/main.go\n"))
    assert envelope["reasons"][0]["file"] == "cmd/bolt/main.go"


# COVERS: FR-3.1 | edge
def test_an_empty_record_succeeds_rather_than_raising(adapter):
    """A record with no captures at all is the shape bolt writes for a task that
    produced no output, and it must not be read as a finding."""
    envelope = adapter(gofmt, {})
    assert envelope["success"] is True


# COVERS: NFR-3 | positive
def test_the_adapter_runs_as_a_script():
    """In-process tests cannot catch a broken shebang or a missing import."""
    result = subprocess.run(  # nosec B603
        script_argv(ROOT / "adapters" / "go" / "gofmt.py"),
        input=yaml.safe_dump(record("main.go\n")),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert yaml.safe_load(result.stdout)["success"] is False
