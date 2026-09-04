#!/usr/bin/env python3
"""Adapter for an lcov coverage profile: one reason per file below the minimum.

Judged PER FILE, never in aggregate. An aggregate threshold is precisely what
lets a well-tested file carry an untested one, so the total is reported as
context in statistics and nothing branches on it. The Go adapter beside this one
makes the same choice for the same reason, and the two are meant to read alike.

A file with no test at all still appears in the profile with every line at count
0, so this sees it as 0% rather than not seeing it. That matters: a per-file gate
that read only the files it found would silently pass exactly the files nobody
had written a test for.

    coverage.py --min 80 --min-branch 80 [--exclude REGEX]...
                --evidence PROFILE --work-dir DIR

Bolt names the profile with `--evidence`, once per file the task declared, so
the adapter never guesses a path or discovers whatever a tool left behind. It
writes its envelope to `output.yaml` in `--work-dir`; stdout is captured beside
the command's as `adapter-output` and is for reading a broken adapter, not for
returning a verdict. No stdin is supplied.

Bolt checks declared evidence exists before invoking an adapter, so a missing
profile arrives as its `evidence-missing` verdict and never reaches here.

LINES AND NOT STATEMENTS, which is the honest name for what lcov carries. Go's
profile counts statements per block; lcov's `DA` records count executable lines.
The threshold is the same number against a slightly different denominator, and
calling it lines here rather than statements is what stops a reader comparing
the two as though they measured one thing.

BRANCH RECORDS ARE READ WHERE THEY EXIST, AND ON A STABLE TOOLCHAIN THEY DO NOT.
The lcov format carries `BRDA` records and this adapter reads them. cargo-llvm-cov
emits none without its `--branch` flag, which is unstable and needs a nightly
compiler: it passes `-Z coverage-options=branch`, which stable rustc rejects
outright.

Measured 2026-09-04 against bolt on 1.98.1: the profile carried `BRF:0` and
`BRH:0` for every file and not one `BRDA` record. The branch data is NOT sitting
in the file waiting to be read, which is what this adapter was first written
believing.

So the Rust jig sets no branch minimum, and `branch_measured` in the statistics
below reports false rather than letting a threshold pass quietly on a zero
denominator. A check that cannot fail is not a check, and one that looks like it
could is worse than one that is plainly absent.

THE THREE LANGUAGES ARE NOT LEVEL ON THIS, AND SAYING SO IS THE POINT. Python's
coverage.py measures branches on the stable toolchain, so the Python jig gates
them. Go has no branch mode at all. Rust could on nightly and does not, because
the estate builds on stable. Holding all three to lines would discard a
guarantee Python has for free; reporting all three as though they had it would
claim one that nothing established.
"""

# pylint: disable=duplicate-code
#
# STRUCTURAL, NOT INCIDENTAL. Every script in `bin/` and `adapters/` is spawned
# by path from a directory that is not a package, so none can import another,
# so anything two of them must both do is written twice. R0801 finds a different
# pair each time one is dissolved: the coverage adapters' judgement, the
# checkers' `SKIP_DIRS`, the adapters' `emit`. Registered as S-3 in SUPPRESSIONS,
# with what would retire it.

import argparse
import pathlib
import re

import yaml

CHECKER = "coverage"

# SF:/abs/path/to/file.rs   starts a record
# DA:12,3                   line 12 was hit 3 times
# BRDA:12,0,1,3             line 12, block 0, branch 1, taken 3 times ('-' = never)
SOURCE = re.compile(r"^SF:(?P<file>.+)$")
LINE = re.compile(r"^DA:(?P<line>\d+),(?P<count>\d+)")
BRANCH = re.compile(r"^BRDA:(?P<line>\d+),(?P<block>\d+),(?P<branch>[^,]+),(?P<taken>.+)$")


def parse_profile(text):
    """Return {file: {"lines": {line: count}, "branches": {key: taken}}}.

    A file appears once per record and cargo-llvm-cov writes a record per
    binary, so the same line arrives several times over. Taking the maximum is
    what merging profiles means: a line is covered if ANY binary reached it.
    Summing instead would count a line's hits once per binary and say nothing
    useful, and overwriting would let the last binary's miss erase the first
    binary's hit.

    Branches merge the same way and for the same reason, keyed by the triple
    lcov identifies them with. `-` means the branch was never taken and is read
    as zero, so an untaken branch merges against a taken one correctly rather
    than being discarded as unparseable.
    """
    files = {}
    current = None
    for raw in text.splitlines():
        line = raw.strip()
        source = SOURCE.match(line)
        if source:
            current = files.setdefault(source.group("file"), {"lines": {}, "branches": {}})
            continue
        if current is None:
            continue
        hit = LINE.match(line)
        if hit:
            number, count = int(hit.group("line")), int(hit.group("count"))
            current["lines"][number] = max(current["lines"].get(number, 0), count)
            continue
        arm = BRANCH.match(line)
        if arm:
            key = (int(arm.group("line")), arm.group("block"), arm.group("branch"))
            taken = arm.group("taken").strip()
            count = 0 if taken == "-" else int(taken)
            current["branches"][key] = max(current["branches"].get(key, 0), count)
    return files


def counted(files):
    """Turn the parsed profile into {file: (cov_lines, lines, cov_branches, branches)}."""
    return {
        name: (
            sum(1 for count in record["lines"].values() if count > 0),
            len(record["lines"]),
            sum(1 for count in record["branches"].values() if count > 0),
            len(record["branches"]),
        )
        for name, record in files.items()
    }


def shorten(files):
    """Strip the directory prefix the entries share, so reasons name repo paths.

    Derived from the entries rather than from a manifest: the adapter is a
    filter over what it was handed, and the common prefix is already in the
    data. lcov from cargo-llvm-cov names files absolutely, so without this every
    reason carries one machine's layout.
    """
    if len(files) < 2:
        return files
    parts = [name.split("/") for name in files]
    common = 0
    for segments in zip(*parts):
        if len(set(segments)) != 1:
            break
        common += 1
    if common == 0:
        return files
    return {"/".join(p[common:]): v for p, v in zip(parts, files.values())}


def test_failure(path):
    """Return a reason when the test run itself failed, else None.

    Bolt captures the status to a file rather than passing it, so an absent or
    unreadable one is treated as a failure: an adapter that assumed success
    where it could not tell would report the guarantee it exists to check.
    """
    if not path:
        return None
    try:
        status = int(pathlib.Path(path).read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return {
            "kind": "exit-status-unreadable",
            "checker": CHECKER,
            "message": f"no readable exit status at {path}",
            "detail": "the test run's status could not be read, so whether the suite passed is unknown and coverage alone cannot stand for it",
        }
    if status == 0:
        return None
    return {
        "kind": "tests-failed",
        "checker": CHECKER,
        "message": f"the test run exited {status}",
        "detail": "coverage is reported for context; a profile from a failed run measures what ran, not what passed",
    }


def arguments():
    """The command line bolt hands an adapter.

    Every flag bolt passes is declared, including the ones this adapter does not
    read, so an unexpected argument is an error here rather than something
    silently ignored.
    """
    ap = argparse.ArgumentParser()
    ap.add_argument("--min", type=float, default=80.0)
    # A SEPARATE FLAG, WHICH TODAY CARRIES THE SAME NUMBER. Branch coverage is
    # normally lower than line coverage, because reaching a line proves only
    # that one of its arms ran, so the two have to be settable apart even when
    # they agree.
    #
    # 80 is measured rather than conventional. Across toolbox's own checkers on
    # 2026-09-04 the worst per-file branch figure was 84.1%
    # (`bin/link-toolbox.py`) against a worst line figure of 91.8% in the same
    # file, so 80 clears every file that has tests with a little headroom and
    # fails one that has none.
    ap.add_argument("--min-branch", dest="min_branch", type=float, default=80.0)
    ap.add_argument("--exclude", action="append", default=[])
    ap.add_argument("--evidence", action="append", default=[])
    ap.add_argument("--work-dir", dest="work_dir", required=True)
    ap.add_argument("--stdout")
    ap.add_argument("--stderr")
    ap.add_argument("--exitcode")
    ap.add_argument("--project-root", dest="project_root")
    ap.add_argument("--base-dir", dest="base_dir")
    return ap.parse_args()


def merged_profile(paths):
    """Every named profile, read as one document.

    `parse_profile` takes the highest count per line and per branch, which is
    what merging means, so several profiles compose exactly the way one
    profile's repeated records do.
    """
    text = "\n".join(pathlib.Path(path).read_text(encoding="utf-8") for path in paths)
    return shorten(counted(parse_profile(text)))


# The two metrics differ only in what they are called and what the denominator
# is named in the reason, so they are described rather than written twice. That
# also keeps `judge` below the cognitive limit: inlining both arms took it to 22
# against a limit of 15, which is the shape complexipy exists to catch.
LINES = {
    "kind": "coverage-below-minimum",
    "unit": "lines covered",
    "denominator": "lines",
}
BRANCHES = {
    "kind": "branch-coverage-below-minimum",
    "unit": "branches taken",
    "denominator": "branches",
}


def below(name, covered, total, minimum, metric):
    """One metric for one file: a reason, or None where it clears the minimum."""
    pct = 100.0 * covered / total
    if pct + 1e-9 >= minimum:
        return None
    return {
        "kind": metric["kind"],
        "checker": CHECKER,
        "file": name,
        "message": f"{name}: {pct:.1f}% of {metric['unit']}, below {minimum:.0f}%",
        "covered": covered,
        metric["denominator"]: total,
        "percent": round(pct, 1),
    }


def kept_files(files, patterns):
    """The files to judge, sorted, with the excluded ones dropped."""
    excluded = [re.compile(pattern) for pattern in patterns]
    return [name for name in sorted(files) if not any(p.search(name) for p in excluded)]


def statistics_for(files, kept, reasons):
    """The totals, summed over the kept set. Context only; nothing branches on them.

    Index 0 and 1 of a record are covered lines and lines, 2 and 3 the same for
    branches. `branch_measured` says whether any branch data arrived at all, so
    a profile carrying none reads as unmeasured rather than as a threshold met
    on an empty denominator.
    """
    covered = sum(files[name][0] for name in kept)
    lines = sum(files[name][1] for name in kept)
    branch_covered = sum(files[name][2] for name in kept)
    branches = sum(files[name][3] for name in kept)
    return {
        "files": len(files),
        "below_minimum": sum(1 for r in reasons if r["kind"] == LINES["kind"]),
        "branch_below_minimum": sum(1 for r in reasons if r["kind"] == BRANCHES["kind"]),
        "branch_measured": branches > 0,
        "total_percent": round(100.0 * covered / lines, 1) if lines else 0.0,
        "total_branch_percent": round(100.0 * branch_covered / branches, 1) if branches else 0.0,
    }


def judge(files, minimum, branch_minimum, patterns):
    """Per file against each minimum, with the totals for context.

    PER FILE AND NOT IN AGGREGATE, which is hard rule 5's reason: an aggregate
    lets a well-tested file carry an untested one, and the exclusion that would
    settle a failure drops the guarantee quietly.

    A FILE WITH NO BRANCHES IS NOT JUDGED ON BRANCHES. Straight-line code has no
    arms to take, so a zero denominator means the question does not apply rather
    than that the file failed it — the same reading `total == 0` already gets
    for lines. On a stable toolchain that is EVERY file, which is why
    `branch_measured` is reported rather than left to be inferred from a pass.
    """
    kept = kept_files(files, patterns)

    reasons = []
    for name in kept:
        covered, total, branch_covered, branches = files[name]
        if total:
            reasons.append(below(name, covered, total, minimum, LINES))
        if branches:
            reasons.append(below(name, branch_covered, branches, branch_minimum, BRANCHES))
    reasons = [reason for reason in reasons if reason]

    return reasons, statistics_for(files, kept, reasons)


NO_EVIDENCE = {
    "kind": "evidence-missing",
    "checker": CHECKER,
    "message": "no --evidence profile was named",
    "detail": "the tests task must declare its coverage profile as evidence; without one this adapter measured nothing",
}


def emit(work_dir, success, reasons, statistics=None):
    """Write the envelope bolt reads, in the shape wrench validates.

    The name never varies and the directory is the one bolt gave, so nothing
    here decides where a verdict goes. Writing to stdout would be captured as
    `adapter-output` and read by nobody.
    """
    doc = {"success": success}
    if reasons:
        doc["reasons"] = reasons
    if statistics:
        doc["metadata"] = {"statistics": statistics}
    with open(work_dir / "output.yaml", "w", encoding="utf-8") as fh:
        yaml.safe_dump(doc, fh, sort_keys=False)


def main():
    args = arguments()
    work_dir = pathlib.Path(args.work_dir)

    # This adapter is attached to the task that RUNS the tests, because that is
    # the task whose work directory holds the profile. So it answers for the
    # test run as well: a suite that failed while leaving a profile behind would
    # otherwise be reported as a pass with a coverage number beside it.
    failed = test_failure(args.exitcode)

    if not args.evidence:
        emit(work_dir, False, [dict(NO_EVIDENCE)])
        return

    files = merged_profile(args.evidence)
    reasons, statistics = judge(files, args.min, args.min_branch, args.exclude)

    # The test failure joins the list after the statistics are counted, so the
    # counts keep meaning the number of files under each minimum rather than the
    # number of reasons.
    if failed:
        reasons.insert(0, failed)
    emit(work_dir, not reasons, reasons, statistics)


if __name__ == "__main__":
    main()
