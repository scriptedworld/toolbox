"""Tests for `adapters/rust/coverage.py`.

IT SPEAKS THE FLAG CONTRACT, NOT THE STDIN ONE, exactly as `adapters/go/coverage.py`
does: it is handed `--evidence`, `--work-dir` and `--exitcode` and writes
`output.yaml` into the work directory, so these drive it directly rather than
through the `adapter` fixture.

WHAT IT ANSWERS FOR IS WIDER THAN COVERAGE. It is attached to the task that RUNS
the tests, because that is the task whose work directory holds the profile, so a
suite that failed while leaving a profile behind must not report as a pass with
a number beside it.

BRANCHES ARE READ BUT NOT GATED, AND THE CASES BELOW ARE WHY THAT IS SAFE. The
lcov format carries `BRDA` records and the adapter reads them, but cargo-llvm-cov
emits none on a stable toolchain: its `--branch` flag is unstable and needs
nightly. So these cases feed BRDA records the real producer does not currently
write, which is deliberate — the parsing has to be correct and pinned before the
toolchain makes it reachable, and `branch_measured` has to say plainly that
nothing was measured rather than let a threshold pass on a zero denominator.
"""

from __future__ import annotations

from conftest import ROOT, run_flag_adapter

ADAPTER = ROOT / "adapters" / "rust" / "coverage.py"

# a.rs: 2 of 3 lines, 1 of 2 branches. b.rs: nothing at all. c.rs: everything.
# `-` is lcov's spelling for a branch that was never taken.
PROFILE = (
    "SF:/repo/src/a.rs\n"
    "DA:1,5\n"
    "DA:2,1\n"
    "DA:3,0\n"
    "BRDA:1,0,0,3\n"
    "BRDA:1,0,1,-\n"
    "end_of_record\n"
    "SF:/repo/src/b.rs\n"
    "DA:1,0\n"
    "DA:2,0\n"
    "end_of_record\n"
    "SF:/repo/src/c.rs\n"
    "DA:1,4\n"
    "BRDA:1,0,0,2\n"
    "BRDA:1,0,1,1\n"
    "end_of_record\n"
)

# Every line and every branch taken, so a pass is demonstrable at any minimum.
COVERED = "SF:/repo/src/a.rs\nDA:1,5\nBRDA:1,0,0,3\nBRDA:1,0,1,2\nend_of_record\nSF:/repo/src/c.rs\nDA:1,4\nend_of_record\n"


def run(tmp_path, *args, profile: str | None = PROFILE, exitcode="0"):
    """The shared flag-contract runner, with this adapter's evidence name."""
    return run_flag_adapter(ADAPTER, tmp_path, "coverage.lcov", profile, *args, exitcode=exitcode)


def reasons_of(envelope, kind):
    return [r for r in envelope.get("reasons", []) if r["kind"] == kind]


# ---- lines -------------------------------------------------------------------


# COVERS: FR-3.4 | positive
def test_a_file_below_the_minimum_becomes_one_reason(tmp_path):
    """Per file, so a well-covered file cannot carry an uncovered one."""
    envelope = run(tmp_path, "--min", "80", "--min-branch", "0")
    below = reasons_of(envelope, "coverage-below-minimum")
    assert {r["file"] for r in below} == {"a.rs", "b.rs"}
    assert envelope["success"] is False


# COVERS: FR-3.4 | edge
def test_the_aggregate_never_rescues_a_file(tmp_path):
    """b.rs is at 0% while the tree is at 50%, and the file is what is judged."""
    envelope = run(tmp_path, "--min", "40", "--min-branch", "0")
    below = reasons_of(envelope, "coverage-below-minimum")
    assert [r["file"] for r in below] == ["b.rs"]
    assert envelope["metadata"]["statistics"]["total_percent"] > 40


# COVERS: FR-3.4 | positive
def test_a_reason_carries_the_counts_it_judged(tmp_path):
    """The numbers are in the reason, so nobody has to re-derive them."""
    envelope = run(tmp_path, "--min", "80", "--min-branch", "0")
    a = next(r for r in reasons_of(envelope, "coverage-below-minimum") if r["file"] == "a.rs")
    assert (a["covered"], a["lines"], a["percent"]) == (2, 3, 66.7)


# ---- branches ----------------------------------------------------------------


# COVERS: FR-3.4 | positive
def test_a_file_below_the_branch_minimum_is_its_own_reason_kind(tmp_path):
    """Branches fail separately from lines, so the two are never conflated."""
    envelope = run(tmp_path, "--min", "0", "--min-branch", "80")
    below = reasons_of(envelope, "branch-coverage-below-minimum")
    assert [r["file"] for r in below] == ["a.rs"]
    assert (below[0]["covered"], below[0]["branches"]) == (1, 2)


# COVERS: FR-3.4 | edge
def test_a_branch_never_taken_is_read_as_zero_not_skipped(tmp_path):
    """`-` is lcov's never-taken marker; dropping it would flatter the file."""
    envelope = run(tmp_path, "--min", "0", "--min-branch", "100")
    a = next(r for r in reasons_of(envelope, "branch-coverage-below-minimum") if r["file"] == "a.rs")
    assert a["branches"] == 2, "the untaken arm must stay in the denominator"
    assert a["covered"] == 1


# COVERS: FR-3.4 | edge
def test_a_file_with_no_branches_is_not_judged_on_branches(tmp_path):
    """Straight-line code has no arms to take, so the question does not apply."""
    envelope = run(tmp_path, "--min", "0", "--min-branch", "100")
    assert "b.rs" not in {r["file"] for r in reasons_of(envelope, "branch-coverage-below-minimum")}


# COVERS: FR-3.4 | edge
def test_lines_and_branches_are_judged_independently(tmp_path):
    """A file can pass one and fail the other, and both are reported."""
    envelope = run(tmp_path, "--min", "60", "--min-branch", "80")
    files = {r["kind"]: r["file"] for r in envelope["reasons"]}
    assert files["branch-coverage-below-minimum"] == "a.rs"
    assert "coverage-below-minimum" in files


# ---- merging -----------------------------------------------------------------


# COVERS: FR-3.4 | edge
def test_a_line_is_covered_if_any_record_reached_it(tmp_path):
    """cargo-llvm-cov writes a record per binary; merging takes the maximum."""
    profile = "SF:/repo/src/a.rs\nDA:1,0\nend_of_record\nSF:/repo/src/a.rs\nDA:1,7\nend_of_record\n"
    envelope = run(tmp_path, "--min", "100", "--min-branch", "0", profile=profile)
    assert envelope["success"] is True, envelope


# COVERS: FR-3.4 | edge
def test_a_branch_is_taken_if_any_record_took_it(tmp_path):
    """The same merge, on the records a summing implementation would double."""
    profile = (
        "SF:/repo/src/a.rs\nDA:1,1\nBRDA:1,0,0,-\nBRDA:1,0,1,-\nend_of_record\nSF:/repo/src/a.rs\nDA:1,1\nBRDA:1,0,0,2\nBRDA:1,0,1,3\nend_of_record\n"
    )
    envelope = run(tmp_path, "--min", "0", "--min-branch", "100", profile=profile)
    assert envelope["success"] is True, envelope


# COVERS: FR-3.4 | edge
def test_several_evidence_files_compose_as_one_document(tmp_path):
    """Two profiles merge exactly as one profile's repeated records do.

    Driven through `run` with an extra `--evidence` rather than by building the
    argument list here, which is what the Go adapter's equivalent case does. Two
    hand-built lists differing only in a filename are one block of duplication
    that pylint's R0801 reads across files, and it is right to: the second copy
    is where a change to the contract gets missed.
    """
    second = tmp_path / "two.lcov"
    second.write_text("SF:/repo/src/a.rs\nDA:1,9\nend_of_record\n", encoding="utf-8")
    envelope = run(
        tmp_path,
        "--min",
        "100",
        "--min-branch",
        "0",
        "--evidence",
        str(second),
        profile="SF:/repo/src/a.rs\nDA:1,0\nend_of_record\n",
    )
    assert envelope["success"] is True, envelope


# ---- the test run it answers for ---------------------------------------------


# COVERS: FR-3.6 | negative
def test_a_failed_suite_is_a_failure_even_with_a_clean_profile(tmp_path):
    """A profile from a failed run measures what ran, not what passed."""
    envelope = run(tmp_path, "--min", "0", "--min-branch", "0", profile=COVERED, exitcode="1")
    assert envelope["success"] is False
    assert reasons_of(envelope, "tests-failed")


# COVERS: FR-3.6 | negative
def test_an_unreadable_exit_status_is_a_failure(tmp_path):
    """Not knowing whether the suite passed is not the same as it passing."""
    envelope = run(tmp_path, "--min", "0", "--min-branch", "0", profile=COVERED, exitcode=None)
    assert envelope["success"] is False
    assert reasons_of(envelope, "exit-status-unreadable")


# COVERS: FR-3.6 | negative
def test_no_evidence_is_a_failure_rather_than_an_empty_pass(tmp_path):
    """Measuring nothing must not report as having found nothing wrong."""
    envelope = run(tmp_path, profile=None)
    assert envelope["success"] is False
    assert reasons_of(envelope, "evidence-missing")


# ---- statistics and the shape of a pass --------------------------------------


# COVERS: FR-3.7 | positive
def test_statistics_are_emitted_on_a_pass(tmp_path):
    """A number is only useful as a series, so a pass reports one too."""
    envelope = run(tmp_path, "--min", "0", "--min-branch", "0", profile=COVERED)
    stats = envelope["metadata"]["statistics"]
    assert envelope["success"] is True
    assert stats["total_percent"] == 100.0
    assert stats["total_branch_percent"] == 100.0
    assert stats["below_minimum"] == 0
    assert stats["branch_below_minimum"] == 0


# COVERS: FR-3.5 | positive
def test_a_pass_omits_the_reasons_block_rather_than_emitting_it_empty(tmp_path):
    """`reasons: []` is a different claim from having nothing to report."""
    envelope = run(tmp_path, "--min", "0", "--min-branch", "0", profile=COVERED)
    assert "reasons" not in envelope


# COVERS: FR-3.4 | edge
def test_an_exclusion_removes_a_file_from_both_judgements(tmp_path):
    """One flag, both metrics, so an exclusion cannot half-apply."""
    envelope = run(tmp_path, "--min", "80", "--min-branch", "80", "--exclude", r"^b\.rs$", "--exclude", r"^a\.rs$")
    assert envelope["success"] is True, envelope


# ---- paths, encoding, and the shapes a real profile arrives in ---------------


# COVERS: FR-3.4 | edge
def test_a_shared_prefix_is_stripped_so_reasons_name_repository_paths(tmp_path):
    """lcov names files absolutely; without this every reason carries a layout."""
    envelope = run(tmp_path, "--min", "80", "--min-branch", "0")
    assert {r["file"] for r in reasons_of(envelope, "coverage-below-minimum")} == {"a.rs", "b.rs"}


# COVERS: FR-3.4 | edge
def test_a_single_file_profile_keeps_its_whole_path(tmp_path):
    """With one entry there is no common prefix to derive, so nothing is cut."""
    profile = "SF:/repo/src/only.rs\nDA:1,0\nend_of_record\n"
    envelope = run(tmp_path, "--min", "80", "--min-branch", "0", profile=profile)
    assert reasons_of(envelope, "coverage-below-minimum")[0]["file"] == "/repo/src/only.rs"


# COVERS: FR-3.4 | edge
def test_a_non_ascii_path_survives_into_the_reason(tmp_path):
    """A source tree may be named in any language, and the file is the reason's
    whole identity. Latin-1-range, CJK and an astral-plane character together,
    because each is a different width in UTF-8 and a byte-oriented read of the
    profile would corrupt them differently."""
    profile = (
        "SF:/repo/src/café.rs\nDA:1,0\nend_of_record\n"
        "SF:/repo/src/設定.rs\nDA:1,0\nend_of_record\n"
        "SF:/repo/src/emoji\U0001f600.rs\nDA:1,0\nend_of_record\n"
    )
    envelope = run(tmp_path, "--min", "80", "--min-branch", "0", profile=profile)
    assert {r["file"] for r in reasons_of(envelope, "coverage-below-minimum")} == {
        "café.rs",
        "設定.rs",
        "emoji\U0001f600.rs",
    }


# COVERS: FR-3.4 | edge
def test_a_non_ascii_path_round_trips_through_the_envelope(tmp_path):
    """The envelope is YAML that bolt reads back, so the escaping has to survive
    a load rather than merely be written without raising."""
    profile = "SF:/repo/src/café.rs\nDA:1,0\nend_of_record\nSF:/repo/src/b.rs\nDA:1,0\nend_of_record\n"
    envelope = run(tmp_path, "--min", "80", "--min-branch", "0", profile=profile)
    names = {r["file"] for r in reasons_of(envelope, "coverage-below-minimum")}
    assert "café.rs" in names
    assert "caf\\xe9.rs" not in names, "an escape that survived the load is a corrupted name"


# COVERS: FR-3.4 | edge
def test_a_common_prefix_is_counted_in_path_segments_not_characters(tmp_path):
    """`src/a.rs` and `src/ab.rs` share the segment `src` and nothing more, so a
    character-wise prefix would cut the `a` off `ab.rs`."""
    profile = "SF:/repo/src/a.rs\nDA:1,0\nend_of_record\nSF:/repo/src/ab.rs\nDA:1,0\nend_of_record\n"
    envelope = run(tmp_path, "--min", "80", "--min-branch", "0", profile=profile)
    assert {r["file"] for r in reasons_of(envelope, "coverage-below-minimum")} == {"a.rs", "ab.rs"}


# COVERS: FR-3.4 | edge
def test_crlf_line_endings_parse(tmp_path):
    """A profile written on Windows, or copied through something that rewrote its
    endings, must not read as a profile with no records at all."""
    envelope = run(tmp_path, "--min", "80", "--min-branch", "0", profile=PROFILE.replace("\n", "\r\n"))
    assert {r["file"] for r in reasons_of(envelope, "coverage-below-minimum")} == {"a.rs", "b.rs"}


# COVERS: FR-3.6 | negative
def test_a_profile_that_parses_to_nothing_does_not_report_a_pass(tmp_path):
    """Silence plus a suite that failed is not success. An empty profile with a
    clean exit is the one case that legitimately has nothing to say."""
    envelope = run(tmp_path, "--min", "80", "--min-branch", "80", profile="", exitcode="1")
    assert envelope["success"] is False
    assert reasons_of(envelope, "tests-failed")


# COVERS: FR-3.4 | edge
def test_records_before_any_source_line_are_ignored(tmp_path):
    """A `DA` with no `SF` above it belongs to no file. Attributing it to the
    next one would move coverage between files."""
    profile = "DA:1,9\nBRDA:1,0,0,9\nSF:/repo/src/a.rs\nDA:1,0\nend_of_record\n"
    envelope = run(tmp_path, "--min", "80", "--min-branch", "0", profile=profile)
    below = reasons_of(envelope, "coverage-below-minimum")
    assert below[0]["lines"] == 1 and below[0]["covered"] == 0


# COVERS: FR-3.7 | edge
def test_a_profile_with_no_branch_records_reads_as_unmeasured(tmp_path):
    """cargo-llvm-cov on a stable toolchain writes BRF:0 and BRH:0 and not one
    BRDA record, so the branch threshold has nothing to judge. That has to read
    as unmeasured rather than as a threshold quietly met on a zero denominator,
    which is the whole reason the statistic exists."""
    profile = "SF:/repo/src/a.rs\nDA:1,1\nBRF:0\nBRH:0\nend_of_record\n"
    envelope = run(tmp_path, "--min", "0", "--min-branch", "100", profile=profile)
    assert envelope["metadata"]["statistics"]["branch_measured"] is False
    assert envelope["success"] is True, "an unmeasured branch is not a failed one"


# COVERS: FR-3.7 | positive
def test_branch_measured_is_true_once_records_arrive(tmp_path):
    """The same statistic on a profile from a toolchain that does emit them."""
    envelope = run(tmp_path, "--min", "0", "--min-branch", "0")
    assert envelope["metadata"]["statistics"]["branch_measured"] is True
