#!/usr/bin/env python3
"""Adapter for a Go coverage profile: one reason per file below the minimum.

Judged PER FILE, never in aggregate. An aggregate threshold is precisely what
lets a well-tested file carry an untested one, so the total is reported as
context in statistics and nothing branches on it.

A file with no test at all still appears in the profile with every statement
at count 0, so this sees it as 0% rather than not seeing it. That matters: a
per-file gate that read only the files it found would silently pass exactly
the files nobody had written a test for.

    coverage.py --min 80 [--exclude REGEX]... --evidence PROFILE --work-dir DIR

Bolt names the profile with `--evidence`, once per file the task declared, so
the adapter never guesses a path or discovers whatever a tool left behind. It
writes its envelope to `output.yaml` in `--work-dir`; stdout is captured beside
the command's as `adapter-output` and is for reading a broken adapter, not for
returning a verdict. No stdin is supplied.

Bolt checks declared evidence exists before invoking an adapter, so a missing
profile arrives as its `evidence-missing` verdict and never reaches here.
"""

import argparse
import pathlib
import re

import yaml

CHECKER = "coverage"

# github.com/x/y/pkg/file.go:12.34,15.2 3 1
#                           ^block span      ^statements ^count
LINE = re.compile(
    r"^(?P<file>.+?):(?P<span>\d+\.\d+,\d+\.\d+) (?P<stmts>\d+) (?P<count>\d+)$"
)


def parse_profile(text):
    """Return {file: (covered_statements, total_statements)}.

    Blocks are keyed by file and span, not merely accumulated. With
    `-coverpkg=./...` every test binary instruments every package, so the same
    block appears once per binary, nine times over in a nine-package module.
    Summing those would count each statement nine times in the denominator
    while the numerator only counted the binaries that reached it, reporting
    a well-tested file at a fraction of its real coverage.

    A block is covered if ANY binary reached it, which is what merging profiles
    means.
    """
    blocks = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("mode:"):
            continue
        m = LINE.match(line)
        if not m:
            continue
        key = (m.group("file"), m.group("span"))
        stmts, count = int(m.group("stmts")), int(m.group("count"))
        prev_stmts, prev_count = blocks.get(key, (stmts, 0))
        blocks[key] = (prev_stmts, max(prev_count, count))

    files = {}
    for (name, _), (stmts, count) in blocks.items():
        covered, total = files.get(name, (0, 0))
        files[name] = (covered + (stmts if count > 0 else 0), total + stmts)
    return files


def shorten(files):
    """Strip the module path the entries share, so reasons name repo paths.

    Derived from the entries rather than read from go.mod: the adapter is a
    filter over what it was handed, and the common prefix is already in the
    data.
    """
    if len(files) < 2:
        return files
    parts = [name.split("/") for name in files]
    common = 0
    for segs in zip(*parts):
        if len(set(segs)) != 1:
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
            "detail": "the test run's status could not be read, so whether the "
            "suite passed is unknown and coverage alone cannot stand for it",
        }
    if status == 0:
        return None
    return {
        "kind": "tests-failed",
        "checker": CHECKER,
        "message": f"the test run exited {status}",
        "detail": "coverage is reported for context; a profile from a failed "
        "run measures what ran, not what passed",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min", type=float, default=80.0)
    ap.add_argument("--exclude", action="append", default=[])
    ap.add_argument("--evidence", action="append", default=[])
    ap.add_argument("--work-dir", dest="work_dir", required=True)
    # Bolt passes these to every adapter. Declared so an unexpected one is an
    # error here rather than a silently ignored argument.
    ap.add_argument("--stdout")
    ap.add_argument("--stderr")
    ap.add_argument("--exitcode")
    ap.add_argument("--project-root", dest="project_root")
    ap.add_argument("--base-dir", dest="base_dir")
    args = ap.parse_args()

    work_dir = pathlib.Path(args.work_dir)

    # This adapter is attached to the task that RUNS the tests, because that is
    # the task whose work directory holds the profile. So it answers for the
    # test run as well: a suite that failed while leaving a profile behind would
    # otherwise be reported as a pass with a coverage number beside it.
    failed = test_failure(args.exitcode)

    if not args.evidence:
        emit(
            work_dir,
            False,
            [
                {
                    "kind": "evidence-missing",
                    "checker": CHECKER,
                    "message": "no --evidence profile was named",
                    "detail": "the tests task must declare its coverage profile as "
                    "evidence; without one this adapter measured nothing",
                }
            ],
        )
        return

    # Every profile named is merged. parse_profile keys blocks by file and span
    # and takes the highest count, which is what merging means, so several
    # profiles compose the same way one profile's repeated blocks do.
    text = "\n".join(
        pathlib.Path(path).read_text(encoding="utf-8") for path in args.evidence
    )
    files = shorten(parse_profile(text))

    excluded = [re.compile(p) for p in args.exclude]
    reasons = []
    covered_total = statements_total = 0

    for name in sorted(files):
        covered, total = files[name]
        if total == 0 or any(p.search(name) for p in excluded):
            continue
        covered_total += covered
        statements_total += total
        pct = 100.0 * covered / total
        if pct + 1e-9 < args.min:
            reasons.append(
                {
                    "kind": "coverage-below-minimum",
                    "checker": CHECKER,
                    "file": name,
                    "message": f"{name}: {pct:.1f}% of statements covered, below {args.min:.0f}%",
                    "covered": covered,
                    "statements": total,
                    "percent": round(pct, 1),
                }
            )

    total_pct = 100.0 * covered_total / statements_total if statements_total else 0.0
    # Counted before the test failure joins them, so the statistic keeps meaning
    # the number of files under the minimum rather than the number of reasons.
    below_minimum = len(reasons)
    if failed:
        reasons.insert(0, failed)
    emit(
        work_dir,
        not reasons,
        reasons,
        {
            "files": len(files),
            "below_minimum": below_minimum,
            # Context only. Nothing branches on the total, by design.
            "total_percent": round(total_pct, 1),
        },
    )


def emit(work_dir, success, reasons, statistics=None):
    """Write the envelope bolt reads, in the shape wrench validates.

    The name never varies and the directory is the one bolt gave, so nothing
    here decides where a verdict goes. Writing to stdout would be captured as
    `adapter-output` and read by nobody.

    `envelope.schema.json` requires `message` and `kind` on every reason, and
    puts statistics under `metadata`. The reason shape is open past those two,
    so the per-file counts travel with the verdict.
    """
    doc = {"success": success}
    if reasons:
        doc["reasons"] = reasons
    if statistics:
        doc["metadata"] = {"statistics": statistics}
    with open(work_dir / "output.yaml", "w", encoding="utf-8") as fh:
        yaml.safe_dump(doc, fh, sort_keys=False)


if __name__ == "__main__":
    main()
