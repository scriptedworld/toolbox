#!/usr/bin/env python3
"""Adapter for a Cobertura coverage report: one reason per file below the minimum.

Judged PER FILE, never in aggregate. An aggregate threshold is precisely what
lets a well-tested file carry an untested one, so the total is reported as
context in statistics and nothing branches on it. The Go and Rust adapters
beside this one make the same choice for the same reason, and the three are
meant to read alike.

A file with no test at all appears in the report with every line at zero hits,
so this sees it as 0% rather than not seeing it — BUT ONLY IF THE PRODUCER PUT
IT THERE, and coverage.py does not always. It adds an unexecuted file to the
report only where it can reach it as a package, so a source root whose
subdirectories carry no `__init__.py` yields the files that ran and silently
omits the ones that did not.

That is the one failure this adapter cannot detect from the inside: a file
missing from the report and a file that does not exist look identical here.
`toolbox/pyproject.toml` names the leaf directories in `[tool.coverage.run]
source` for that reason, with the measurement, and `tests/test_python_coverage.py`
pins the shape so the blind spot cannot come back unnoticed.

The Go and Rust adapters beside this one do not share it. `-coverpkg=./...`
instruments every package in the module, and cargo-llvm-cov instruments every
file compiled into the binary, so in both an untested file is present at 0%
rather than absent.

    coverage.py --min 80 --min-branch 80 [--exclude REGEX]...
                --evidence REPORT --work-dir DIR

Bolt names the report with `--evidence`, once per file the task declared, so the
adapter never guesses a path or discovers whatever a tool left behind. It writes
its envelope to `output.yaml` in `--work-dir`; stdout is captured beside the
command's as `adapter-output` and is for reading a broken adapter, not for
returning a verdict. No stdin is supplied.

Bolt checks declared evidence exists before invoking an adapter, so a missing
report arrives as its `evidence-missing` verdict and never reaches here.

LINE-RATE IS NOT READ, and the lines are counted instead. Cobertura carries a
`line-rate` attribute per class, already rounded, and deriving a percentage from
it would report a number this adapter did not compute. Counting `<line>`
elements gives the covered and total counts the reason needs anyway, so the
attribute would be a second source for something already in hand.

`branch-rate` IS NOT READ EITHER, for the same reason and one more: it is
rounded, and it is also present and zero when branch measurement was never
switched on. Counting `condition-coverage` tells the two apart, because an
absent attribute means no branch data rather than no branches taken.

XML FROM A TOOL IS STILL UNTRUSTED INPUT. `defusedxml` is not a dependency here,
so this uses the standard parser on a file the task next to it just wrote. That
is the one case where the standard parser is defensible: the producer is the
`tests` task in the same jig, not a document arriving from somewhere.

BRANCHES ARE GATED HERE AND IN NEITHER OF THE OTHER TWO, and that asymmetry is
deliberate. Cobertura carries `condition-coverage` in the same document the
lines come from, and coverage.py produces it on the stable interpreter, so here
the data really is free.

It is not free elsewhere, which the first draft of these three adapters had
wrong. Go has no branch mode at all: `-covermode` offers set, count and atomic
and all three count statements. Rust has one behind cargo-llvm-cov's unstable
`--branch`, which needs a nightly compiler, and on stable the profile carries
`BRF:0` and no `BRDA` records at all — measured 2026-09-04 against bolt on
1.98.1.

Holding Python to lines alone would discard a guarantee it has for free, to
match two languages that cannot have it. That is levelling down to the weakest
tooling. The three numbers were never one number, and a gate that pretends
otherwise reports a guarantee nothing established.

THE PRODUCER HAS TO BE ASKED FOR BRANCHES. coverage.py writes no
`condition-coverage` unless it ran in branch mode, and a report without it
parses cleanly and reports nothing — the failure mode is a silent pass, not an
error. The jig's `tests` task therefore names `--cov-branch` explicitly, and
`branch_measured` in the statistics below says whether any arrived.
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
import xml.etree.ElementTree as ET  # nosec B405 - see the module docstring

import yaml

CHECKER = "coverage"

# condition-coverage="50% (1/2)" — the parenthesised pair is the count, and the
# percentage before it is derived from exactly those two numbers, so the pair is
# read and the percentage ignored.
CONDITION = re.compile(r"\((?P<covered>\d+)/(?P<total>\d+)\)")


def parse_report(path):
    """Return {filename: {"lines": {line: hits}, "branches": {line: (cov, total)}}}.

    Keyed by line rather than accumulated, and merged by taking the highest
    count, because a filename can appear in more than one `<package>` and the
    same line then arrives twice. A line is covered if ANY entry reached it,
    which is what merging reports means; summing would count a line's hits once
    per entry and overwriting would let a later miss erase an earlier hit.

    A branch entry merges on the covered count alone. The denominator is a
    property of the source line rather than of the run, so it is the same in
    every entry and taking the larger covered count is the whole merge.
    """
    files = {}
    root = ET.parse(path).getroot()  # nosec B314 - see the module docstring
    for klass in root.iter("class"):
        name = klass.get("filename")
        if not name:
            continue
        record = files.setdefault(name, {"lines": {}, "branches": {}})
        for line in klass.iter("line"):
            number, hits = line.get("number"), line.get("hits")
            if number is None or hits is None:
                continue
            number, hits = int(number), int(hits)
            record["lines"][number] = max(record["lines"].get(number, 0), hits)

            # `branch="true"` marks the line as a branch point; the counts live
            # in condition-coverage. A line marked as a branch with no counts
            # carries no information, so it is skipped rather than read as 0/0.
            condition = line.get("condition-coverage")
            if not condition:
                continue
            m = CONDITION.search(condition)
            if not m:
                continue
            covered, total = int(m.group("covered")), int(m.group("total"))
            previous = record["branches"].get(number, (0, total))
            record["branches"][number] = (max(previous[0], covered), total)
    return files


def counted(files):
    """Turn the parsed report into {file: (cov_lines, lines, cov_branches, branches)}."""
    out = {}
    for name, record in files.items():
        branch_covered = sum(c for c, _ in record["branches"].values())
        branch_total = sum(t for _, t in record["branches"].values())
        out[name] = (
            sum(1 for hits in record["lines"].values() if hits > 0),
            len(record["lines"]),
            branch_covered,
            branch_total,
        )
    return out


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
        "detail": "coverage is reported for context; a report from a failed run measures what ran, not what passed",
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


def merged_report(paths):
    """Every named report, read as one set of files."""
    merged = {}
    for path in paths:
        for name, record in parse_report(path).items():
            into = merged.setdefault(name, {"lines": {}, "branches": {}})
            for number, hits in record["lines"].items():
                into["lines"][number] = max(into["lines"].get(number, 0), hits)
            for number, (covered, total) in record["branches"].items():
                previous = into["branches"].get(number, (0, total))
                into["branches"][number] = (max(previous[0], covered), total)
    return counted(merged)


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
    for lines. A whole report with no branch data anywhere is the same shape,
    which is why `branch_measured` is reported rather than inferred from a zero.
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
    "message": "no --evidence report was named",
    "detail": "the tests task must declare its coverage report as evidence; without one this adapter measured nothing",
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
    # the task whose work directory holds the report. So it answers for the test
    # run as well: a suite that failed while leaving a report behind would
    # otherwise be reported as a pass with a coverage number beside it.
    failed = test_failure(args.exitcode)

    if not args.evidence:
        emit(work_dir, False, [dict(NO_EVIDENCE)])
        return

    files = merged_report(args.evidence)
    reasons, statistics = judge(files, args.min, args.min_branch, args.exclude)

    # The test failure joins the list after the statistics are counted, so the
    # counts keep meaning the number of files under each minimum rather than the
    # number of reasons.
    if failed:
        reasons.insert(0, failed)
    emit(work_dir, not reasons, reasons, statistics)


if __name__ == "__main__":
    main()
