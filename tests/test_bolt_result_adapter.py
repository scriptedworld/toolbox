"""Tests for `adapters/common/bolt-result.py`, which is the whole of composition.

Bolt retired nested jigs, so a jig composing another writes a command task whose
command is `bolt` and names this adapter. Without it the task gets the generic
exit-code adapter, and bolt exits 0 whenever it carried a run out, so the
composed task passes however badly the child failed.

MEASURED 2026-08-29 on a real composed run, one failing child judged twice:

    composed                   success=False, carrying the child's reason
    composed-without-adapter   success=True

That is the defect these tests exist to keep closed.
"""

from __future__ import annotations

import subprocess  # nosec B404

import yaml
from conftest import ROOT, script_argv

ADAPTER = ROOT / "adapters" / "common" / "bolt-result.py"


def run(tmp_path, stdout_text=None):
    """Invoke the adapter as bolt does and read the envelope it wrote.

    As a subprocess, because the envelope's location is part of the contract and
    an in-process call cannot catch a broken shebang or a `main()` writing
    somewhere other than where it was told.
    """
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    argv = script_argv(ADAPTER, "--work-dir", str(work))
    if stdout_text is not None:
        captured = tmp_path / "stdout"
        captured.write_text(stdout_text, encoding="utf-8")
        argv += ["--stdout", str(captured)]
    subprocess.run(argv, check=True, capture_output=True)  # nosec B603
    return yaml.safe_load((work / "output.yaml").read_text(encoding="utf-8"))


def child(tmp_path, document) -> str:
    """Write a child result and return the stdout a child bolt run would print."""
    result = tmp_path / "child-result.yaml"
    result.write_text(yaml.safe_dump(document), encoding="utf-8")
    return f"{result}\n"


# COVERS: FR-3.4 | positive
def test_a_failing_childs_own_reasons_come_up(tmp_path):
    """A path going down is what this replaces.

    A parent whose only reason is "the child failed" sends a reader down a level
    for every failure, when the child's list is already structured and already
    says which task and why.
    """
    envelope = run(
        tmp_path,
        child(
            tmp_path,
            {
                "success": False,
                "reasons": [
                    {"kind": "nonzero-exit", "message": "analyse exited 24"},
                    {"kind": "nonzero-exit", "message": "tests exited 1"},
                ],
            },
        ),
    )
    assert envelope["success"] is False
    assert [r["message"] for r in envelope["reasons"]] == [
        "analyse exited 24",
        "tests exited 1",
    ]
    assert all("child" in r for r in envelope["reasons"])


# COVERS: FR-3.5 | positive
def test_a_passing_child_passes_and_says_nothing(tmp_path):
    """An adapter omits an optional block instead of emitting it empty."""
    envelope = run(tmp_path, child(tmp_path, {"success": True}))
    assert envelope["success"] is True
    assert "reasons" not in envelope


# COVERS: FR-3.6 | regression
def test_the_result_path_is_the_last_line_not_the_first(tmp_path):
    """The Go build prints a transcript first and the path last.

    FR-10.3a says bolt prints the path to the result it wrote, and the Rust
    build prints that alone. Reading the first line got a task name from the Go
    build still on PATH, and reported a missing result over a child that had
    written one. The last line satisfies both.
    """
    path = child(
        tmp_path,
        {"success": False, "reasons": [{"kind": "nonzero-exit", "message": "no"}]},
    ).strip()
    transcript = f"always-fails-0\n\nfailed: 1 execution(s)\n{path}\n"
    envelope = run(tmp_path, transcript)
    assert envelope["success"] is False
    assert envelope["reasons"][0]["message"] == "no"


# COVERS: FR-3.6 | negative
def test_an_empty_stdout_is_a_child_that_wrote_nothing(tmp_path):
    """Died before writing a result, which is not the same as writing a bad one.

    The two have different causes and different fixes, which is the distinction
    bolt itself draws between an adapter that wrote nothing and one that wrote
    something invalid.
    """
    envelope = run(tmp_path, "")
    assert envelope["success"] is False
    assert envelope["reasons"][0]["kind"] == "child-wrote-nothing"


# COVERS: FR-3.6 | negative
def test_a_named_result_that_is_not_there_fails(tmp_path):
    """Naming a result and not writing one is its own failure."""
    envelope = run(tmp_path, f"{tmp_path / 'absent.yaml'}\n")
    assert envelope["success"] is False
    assert envelope["reasons"][0]["kind"] == "child-result-missing"


# COVERS: FR-3.6 | negative
def test_a_result_that_does_not_validate_is_refused(tmp_path):
    """Reading `success` off a document that does not validate would let a
    truncated write read as a pass."""
    broken = tmp_path / "broken.yaml"
    broken.write_text("success: yes please\n", encoding="utf-8")
    envelope = run(tmp_path, f"{broken}\n")
    assert envelope["success"] is False
    assert envelope["reasons"][0]["kind"] == "child-result-invalid"


# COVERS: FR-3.6 | edge
def test_a_failure_claiming_no_reasons_is_refused_as_invalid(tmp_path):
    """The schema makes a silent failure impossible, so this is not a fold.

    `success: false` alone, and with `reasons: []`, both fail validation. So a
    validated failure always carries at least one reason and the adapter needs
    no fallback for the empty case. Written as a test rather than trusted,
    because it is the guarantee that lets a branch be absent.
    """
    envelope = run(tmp_path, child(tmp_path, {"success": False}))
    assert envelope["success"] is False
    assert envelope["reasons"][0]["kind"] == "child-result-invalid"


# COVERS: FR-3.6 | edge
def test_an_empty_reasons_list_is_refused_too(tmp_path):
    """The other spelling of a silent failure, and the schema refuses it as well."""
    envelope = run(tmp_path, child(tmp_path, {"success": False, "reasons": []}))
    assert envelope["success"] is False
    assert envelope["reasons"][0]["kind"] == "child-result-invalid"
