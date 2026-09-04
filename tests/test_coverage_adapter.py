"""Tests for `adapters/go/coverage.py`.

It landed at `0cfd449` with no tests at all, which is also why its `main()`
grew to 88 lines against the jig's own `--length 60` without anything saying so.
Written 2026-08-29 while fixing that.

IT SPEAKS THE FLAG CONTRACT, NOT THE STDIN ONE. `gofmt.py` reads an execution
record on stdin and is what the `adapter` fixture serves; this one is handed
`--evidence`, `--work-dir` and `--exitcode` and writes `output.yaml` into the
work directory. So these drive it directly rather than through that fixture.

WHAT IT ANSWERS FOR IS WIDER THAN COVERAGE. It is attached to the task that RUNS
the tests, because that is the task whose work directory holds the profile, so a
suite that failed while leaving a profile behind must not report as a pass with
a number beside it.
"""

from __future__ import annotations

import subprocess  # nosec B404

import yaml
from conftest import ROOT, script_argv

ADAPTER = ROOT / "adapters" / "go" / "coverage.py"

# Two files, one partly covered and one not at all, plus a fully covered third.
# Written as a Go profile because that is what the adapter parses: a mode line,
# then `file:startLine.col,endLine.col statements count` per block.
PROFILE = (
    "mode: atomic\n"
    "github.com/x/p/a.go:10.20,12.3 2 5\n"
    "github.com/x/p/a.go:14.2,15.3 1 0\n"
    "github.com/x/p/b.go:1.1,2.2 4 0\n"
    "github.com/x/p/c.go:1.1,2.2 3 3\n"
)


# Every file fully covered. The mixed profile above cannot demonstrate a pass at
# any positive minimum, because `b.go` is at zero.
COVERED = "mode: atomic\ngithub.com/x/p/a.go:1.1,2.2 2 1\ngithub.com/x/p/c.go:1.1,2.2 3 3\n"


def run(tmp_path, *args, profile: str | None = PROFILE, exitcode="0"):
    """Invoke the adapter as bolt does and read the envelope it wrote.

    AS A SUBPROCESS, because an in-process call cannot catch a broken shebang,
    a missing import, or a `main()` that writes somewhere other than where it
    was told. The envelope's location is part of the contract.
    """
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    status = tmp_path / "exitcode"
    status.write_text(exitcode, encoding="utf-8")

    argv = script_argv(ADAPTER, "--work-dir", str(work))
    if profile is not None:
        prof = tmp_path / "cover.out"
        prof.write_text(profile, encoding="utf-8")
        argv += ["--evidence", str(prof)]
    argv += ["--exitcode", str(status), *args]

    subprocess.run(argv, check=True, capture_output=True)  # nosec B603
    return yaml.safe_load((work / "output.yaml").read_text(encoding="utf-8"))


# COVERS: FR-3.4 | positive
def test_a_file_below_the_minimum_becomes_one_reason(tmp_path):
    """Per file, so a well-covered file cannot carry an uncovered one."""
    envelope = run(tmp_path, "--min", "80")
    assert envelope["success"] is False
    below = [r["file"] for r in envelope["reasons"]]
    assert below == ["a.go", "b.go"]
    assert "c.go" not in below


# COVERS: FR-3.5 | positive
def test_every_file_above_the_minimum_passes(tmp_path):
    """A pass carries no reasons and still reports what it measured."""
    envelope = run(tmp_path, "--min", "80", profile=COVERED)
    assert envelope["success"] is True
    assert "reasons" not in envelope
    assert envelope["metadata"]["statistics"]["files"] == 2
    assert envelope["metadata"]["statistics"]["below_minimum"] == 0


# COVERS: FR-3.4 | property
def test_the_statistic_counts_files_and_not_reasons(tmp_path):
    """`below_minimum` is counted before a test failure joins the list.

    Otherwise a failing suite would silently add one to the number of files
    under the minimum, and the statistic would stop meaning what it says.
    """
    envelope = run(tmp_path, "--min", "80", exitcode="1")
    assert envelope["metadata"]["statistics"]["below_minimum"] == 2
    assert len(envelope["reasons"]) == 3


# COVERS: FR-3.6 | negative
def test_a_failing_suite_fails_even_where_coverage_is_met(tmp_path):
    """The profile exists and the suite failed, so the run has not passed.

    This adapter is attached to the task that runs the tests, so answering only
    about coverage would report a pass for a suite that did not.
    """
    envelope = run(tmp_path, "--min", "80", profile=COVERED, exitcode="1")
    assert envelope["success"] is False
    assert envelope["metadata"]["statistics"]["below_minimum"] == 0
    assert envelope["reasons"][0]["kind"] != "coverage-below-minimum"


# COVERS: FR-3.6 | negative
def test_declaring_no_evidence_fails_rather_than_passing(tmp_path):
    """Measuring nothing is not measuring zero problems."""
    envelope = run(tmp_path, profile=None)
    assert envelope["success"] is False
    assert envelope["reasons"][0]["kind"] == "evidence-missing"


# COVERS: FR-3.4 | edge
def test_an_excluded_file_is_not_judged_and_not_counted(tmp_path):
    """Exclusion drops the file from the verdict and from the totals."""
    envelope = run(tmp_path, "--min", "80", "--exclude", r"^b\.go$")
    assert [r["file"] for r in envelope["reasons"]] == ["a.go"]


# COVERS: FR-3.4 | regression
def test_two_profiles_merge_by_taking_the_higher_count(tmp_path):
    """The entry point is measured in a second run and counted with the first.

    A block executed by the binary but not by any test must end up covered, so
    merging takes the higher count per block rather than the last one seen.
    That is what lets hard rule 5 be satisfied by measuring rather than
    excluding.
    """
    work = tmp_path / "work"
    work.mkdir()
    status = tmp_path / "exitcode"
    status.write_text("0", encoding="utf-8")

    first = tmp_path / "cover-test.out"
    first.write_text("mode: atomic\ngithub.com/x/p/m.go:1.1,2.2 4 0\n", "utf-8")
    second = tmp_path / "cover-entry.out"
    second.write_text("mode: atomic\ngithub.com/x/p/m.go:1.1,2.2 4 1\n", "utf-8")

    subprocess.run(  # nosec B603
        script_argv(
            ADAPTER,
            "--work-dir",
            str(work),
            "--evidence",
            str(first),
            "--evidence",
            str(second),
            "--exitcode",
            str(status),
            "--min",
            "80",
        ),
        check=True,
        capture_output=True,
    )
    envelope = yaml.safe_load((work / "output.yaml").read_text(encoding="utf-8"))
    assert envelope["success"] is True, envelope
    assert envelope["metadata"]["statistics"]["total_percent"] == 100.0
