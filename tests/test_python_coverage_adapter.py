"""Tests for `adapters/python/coverage.py`.

IT SPEAKS THE FLAG CONTRACT, NOT THE STDIN ONE, exactly as the Go and Rust
coverage adapters do: it is handed `--evidence`, `--work-dir` and `--exitcode`
and writes `output.yaml` into the work directory.

WHAT IT ANSWERS FOR IS WIDER THAN COVERAGE. It is attached to the task that RUNS
the tests, so a suite that failed while leaving a report behind must not report
as a pass with a number beside it.

ENCODING IS A REAL CASE HERE AND NOT A HYPOTHETICAL. This adapter is the only
one of the three parsing XML, so it is the only one where the document declares
its own encoding and the parser is obliged to honour it. A filename is the whole
identity of a reason, so a filename decoded wrongly is a reason pointing at a
file nobody has.
"""

from __future__ import annotations

import subprocess

import yaml
from conftest import ROOT, script_argv

ADAPTER = ROOT / "adapters" / "python" / "coverage.py"


def document(classes: str, declaration: str = '<?xml version="1.0" ?>') -> str:
    """A Cobertura report around the class elements given."""
    return (
        f"{declaration}\n"
        '<coverage version="7.10.0" branch-rate="0.5" line-rate="0.6">\n'
        '  <packages><package name="p"><classes>\n'
        f"{classes}"
        "  </classes></package></packages>\n"
        "</coverage>\n"
    )


def klass(filename: str, lines: str) -> str:
    return f'    <class filename="{filename}" name="x">\n      <lines>\n{lines}      </lines>\n    </class>\n'


def line(number: int, hits: int, condition: str | None = None) -> str:
    if condition is None:
        return f'        <line number="{number}" hits="{hits}"/>\n'
    return f'        <line number="{number}" hits="{hits}" branch="true" condition-coverage="{condition}"/>\n'


# a.py: 2 of 3 lines, 1 of 2 branches. b.py: nothing. c.py: everything.
REPORT = document(
    klass("a.py", line(1, 5) + line(2, 1) + line(3, 0, "50% (1/2)"))
    + klass("b.py", line(1, 0) + line(2, 0))
    + klass("c.py", line(1, 4) + line(2, 1, "100% (2/2)"))
)

COVERED = document(klass("a.py", line(1, 5) + line(2, 1, "100% (2/2)")) + klass("c.py", line(1, 4)))


def run(tmp_path, *args, report=REPORT, exitcode="0", raw: bytes | None = None):
    """Invoke the adapter as bolt does and read the envelope it wrote.

    AS A SUBPROCESS, because an in-process call cannot catch a broken shebang, a
    missing import, or a `main()` that writes somewhere other than where it was
    told. `raw` writes bytes rather than text, which is how a document declaring
    an encoding other than UTF-8 has to be produced.
    """
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    status = tmp_path / "exitcode"
    status.write_text(exitcode, encoding="utf-8")

    argv = [str(ADAPTER), "--work-dir", str(work)]
    if raw is not None:
        path = tmp_path / "coverage.xml"
        path.write_bytes(raw)
        argv += ["--evidence", str(path)]
    elif report is not None:
        path = tmp_path / "coverage.xml"
        path.write_text(report, encoding="utf-8")
        argv += ["--evidence", str(path)]
    argv += ["--exitcode", str(status), *args]

    subprocess.run(script_argv(*argv), check=True, capture_output=True)
    return yaml.safe_load((work / "output.yaml").read_text(encoding="utf-8"))


def reasons_of(envelope, kind):
    return [r for r in envelope.get("reasons", []) if r["kind"] == kind]


# ---- lines -------------------------------------------------------------------


# COVERS: FR-3.4 | positive
def test_a_file_below_the_minimum_becomes_one_reason(tmp_path):
    """Per file, so a well-covered file cannot carry an uncovered one."""
    envelope = run(tmp_path, "--min", "80", "--min-branch", "0")
    below = reasons_of(envelope, "coverage-below-minimum")
    assert {r["file"] for r in below} == {"a.py", "b.py"}
    assert envelope["success"] is False


# COVERS: FR-3.4 | edge
def test_the_aggregate_never_rescues_a_file(tmp_path):
    """b.py is at 0% while the tree is well above it, and the file is judged."""
    envelope = run(tmp_path, "--min", "40", "--min-branch", "0")
    assert [r["file"] for r in reasons_of(envelope, "coverage-below-minimum")] == ["b.py"]
    assert envelope["metadata"]["statistics"]["total_percent"] > 40


# COVERS: FR-3.4 | positive
def test_a_reason_carries_the_counts_it_judged(tmp_path):
    envelope = run(tmp_path, "--min", "80", "--min-branch", "0")
    a = next(r for r in reasons_of(envelope, "coverage-below-minimum") if r["file"] == "a.py")
    assert (a["covered"], a["lines"], a["percent"]) == (2, 3, 66.7)


# COVERS: FR-3.4 | edge
def test_line_rate_is_not_believed_over_the_counted_lines(tmp_path):
    """The document declares line-rate 0.6. Counting gives 4 covered of 7, which
    is 57.1%, and the counted figure is the one reported."""
    envelope = run(tmp_path, "--min", "40", "--min-branch", "0")
    assert envelope["metadata"]["statistics"]["total_percent"] == 57.1


# ---- branches ----------------------------------------------------------------


# COVERS: FR-3.4 | positive
def test_a_file_below_the_branch_minimum_is_its_own_reason_kind(tmp_path):
    envelope = run(tmp_path, "--min", "0", "--min-branch", "80")
    below = reasons_of(envelope, "branch-coverage-below-minimum")
    assert [r["file"] for r in below] == ["a.py"]
    assert (below[0]["covered"], below[0]["branches"]) == (1, 2)


# COVERS: FR-3.4 | edge
def test_a_file_with_no_branch_data_is_not_judged_on_branches(tmp_path):
    """b.py declares no condition-coverage, so it has no branch question."""
    envelope = run(tmp_path, "--min", "0", "--min-branch", "100")
    assert "b.py" not in {r["file"] for r in reasons_of(envelope, "branch-coverage-below-minimum")}


# COVERS: FR-3.7 | edge
def test_a_report_without_branch_data_says_so_rather_than_reading_as_missed(tmp_path):
    """coverage.py writes no condition-coverage unless it ran in branch mode.
    That must read as unmeasured, not as every branch missed."""
    report = document(klass("a.py", line(1, 1) + line(2, 1)))
    envelope = run(tmp_path, "--min", "0", "--min-branch", "100", report=report)
    assert envelope["metadata"]["statistics"]["branch_measured"] is False
    assert envelope["success"] is True, "an unmeasured branch is not a failed one"


# COVERS: FR-3.7 | positive
def test_branch_measured_is_true_when_conditions_are_present(tmp_path):
    envelope = run(tmp_path, "--min", "0", "--min-branch", "0")
    assert envelope["metadata"]["statistics"]["branch_measured"] is True


# COVERS: FR-3.4 | edge
def test_a_malformed_condition_is_skipped_rather_than_guessed(tmp_path):
    """Without a parseable pair there is no count, and inventing one would put a
    number nobody measured into a gate."""
    report = document(klass("a.py", line(1, 1, "not a fraction")))
    envelope = run(tmp_path, "--min", "0", "--min-branch", "100", report=report)
    assert envelope["metadata"]["statistics"]["branch_measured"] is False


# ---- merging -----------------------------------------------------------------


# COVERS: FR-3.4 | edge
def test_one_filename_in_two_packages_merges_on_the_higher_count(tmp_path):
    """A filename can appear in more than one package; a line is covered if any
    entry reached it, and summing would count its hits twice."""
    report = document(klass("a.py", line(1, 0)) + klass("a.py", line(1, 3)))
    envelope = run(tmp_path, "--min", "100", "--min-branch", "0", report=report)
    assert envelope["success"] is True, envelope


# COVERS: FR-3.4 | edge
def test_a_branch_merges_on_the_higher_covered_count(tmp_path):
    report = document(klass("a.py", line(1, 1, "0% (0/2)")) + klass("a.py", line(1, 1, "100% (2/2)")))
    envelope = run(tmp_path, "--min", "0", "--min-branch", "100", report=report)
    assert envelope["success"] is True, envelope


# ---- the test run it answers for ---------------------------------------------


# COVERS: FR-3.6 | negative
def test_a_failed_suite_is_a_failure_even_with_a_clean_report(tmp_path):
    envelope = run(tmp_path, "--min", "0", "--min-branch", "0", report=COVERED, exitcode="1")
    assert envelope["success"] is False
    assert reasons_of(envelope, "tests-failed")


# COVERS: FR-3.6 | negative
def test_no_evidence_is_a_failure_rather_than_an_empty_pass(tmp_path):
    envelope = run(tmp_path, report=None)
    assert envelope["success"] is False
    assert reasons_of(envelope, "evidence-missing")


# ---- statistics and the shape of a pass --------------------------------------


# COVERS: FR-3.7 | positive
def test_statistics_are_emitted_on_a_pass(tmp_path):
    envelope = run(tmp_path, "--min", "0", "--min-branch", "0", report=COVERED)
    stats = envelope["metadata"]["statistics"]
    assert envelope["success"] is True
    assert stats["total_percent"] == 100.0
    assert stats["below_minimum"] == 0
    assert stats["branch_below_minimum"] == 0


# COVERS: FR-3.5 | positive
def test_a_pass_omits_the_reasons_block_rather_than_emitting_it_empty(tmp_path):
    envelope = run(tmp_path, "--min", "0", "--min-branch", "0", report=COVERED)
    assert "reasons" not in envelope


# COVERS: FR-3.4 | edge
def test_an_exclusion_removes_a_file_from_both_judgements(tmp_path):
    envelope = run(
        tmp_path,
        "--min",
        "80",
        "--min-branch",
        "80",
        "--exclude",
        r"^a\.py$",
        "--exclude",
        r"^b\.py$",
    )
    assert envelope["success"] is True, envelope


# ---- encoding ----------------------------------------------------------------


# COVERS: FR-3.4 | edge
def test_a_non_ascii_filename_survives_into_the_reason(tmp_path):
    """A filename is a reason's whole identity. Latin-1-range, CJK and an
    astral-plane character together, because each is a different width in UTF-8
    and a byte-oriented read would corrupt them differently."""
    report = document(klass("café.py", line(1, 0)) + klass("設定.py", line(1, 0)) + klass("emoji\U0001f600.py", line(1, 0)))
    envelope = run(tmp_path, "--min", "80", "--min-branch", "0", report=report)
    assert {r["file"] for r in reasons_of(envelope, "coverage-below-minimum")} == {
        "café.py",
        "設定.py",
        "emoji\U0001f600.py",
    }


# COVERS: FR-3.4 | edge
def test_a_non_ascii_filename_round_trips_through_the_envelope(tmp_path):
    """The envelope is YAML bolt reads back, so the escaping has to survive a
    load rather than merely be written without raising."""
    report = document(klass("café.py", line(1, 0)))
    envelope = run(tmp_path, "--min", "80", "--min-branch", "0", report=report)
    assert reasons_of(envelope, "coverage-below-minimum")[0]["file"] == "café.py"


# COVERS: FR-3.4 | edge
def test_a_declared_latin1_document_is_decoded_by_its_declaration(tmp_path):
    """XML carries its own encoding and the parser is obliged to honour it.
    Reading these bytes as UTF-8 would fail outright; reading them as UTF-8 with
    errors ignored would silently produce a different filename."""
    report = document(
        klass("café.py", line(1, 0)),
        declaration='<?xml version="1.0" encoding="ISO-8859-1" ?>',
    )
    envelope = run(tmp_path, "--min", "80", "--min-branch", "0", raw=report.encode("iso-8859-1"))
    assert reasons_of(envelope, "coverage-below-minimum")[0]["file"] == "café.py"


# COVERS: FR-3.4 | edge
def test_a_utf8_document_with_a_byte_order_mark_parses(tmp_path):
    """A BOM ahead of the declaration is legal and a parser that treated it as
    content would fail on the first character of the document."""
    report = document(klass("café.py", line(1, 0)))
    envelope = run(
        tmp_path,
        "--min",
        "80",
        "--min-branch",
        "0",
        raw=b"\xef\xbb\xbf" + report.encode("utf-8"),
    )
    assert reasons_of(envelope, "coverage-below-minimum")[0]["file"] == "café.py"


# COVERS: FR-3.4 | edge
def test_a_class_without_a_filename_is_skipped(tmp_path):
    """Nothing can be said about a file with no name, and attributing its lines
    to a neighbour would move coverage between files."""
    report = document('    <class name="x"><lines>\n' + line(1, 0) + "    </lines></class>\n" + klass("a.py", line(1, 0)))
    envelope = run(tmp_path, "--min", "80", "--min-branch", "0", report=report)
    assert [r["file"] for r in reasons_of(envelope, "coverage-below-minimum")] == ["a.py"]
