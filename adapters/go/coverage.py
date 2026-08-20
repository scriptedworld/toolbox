#!/usr/bin/env python3
"""Adapter for a Go coverage profile: one reason per file below the minimum.

Judged PER FILE, never in aggregate. An aggregate threshold is precisely what
lets a well-tested file carry an untested one, so the total is reported as
context in statistics and nothing branches on it.

A file with no test at all still appears in the profile with every statement
at count 0, so this sees it as 0% rather than not seeing it. That matters: a
per-file gate that read only the files it found would silently pass exactly
the files nobody had written a test for.

    coverage.py --min 80 [--exclude REGEX]...

Reads an execution record on stdin, writes an envelope on stdout. Runs in the
same directory the task ran in, so the profile resolves the way it was written.
"""

import argparse
import os
import re
import sys

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
    block appears once per binary — nine times over, in a nine-package module.
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min", type=float, default=80.0)
    ap.add_argument("--profile", default="coverage.out")
    ap.add_argument("--exclude", action="append", default=[])
    args = ap.parse_args()

    yaml.safe_load(sys.stdin.read())  # the record; drained so nothing blocks

    if not os.path.exists(args.profile):
        emit(
            False,
            [
                {
                    "checker": CHECKER,
                    "message": f"no coverage profile at {args.profile}",
                    "detail": "the tests task declares it as an output; a run that "
                    "reports success without one measured nothing",
                }
            ],
        )
        return

    with open(args.profile, encoding="utf-8") as fh:
        files = shorten(parse_profile(fh.read()))

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
                    "checker": CHECKER,
                    "file": name,
                    "message": f"{pct:.1f}% of statements covered, below {args.min:.0f}%",
                    "covered": covered,
                    "statements": total,
                    "percent": round(pct, 1),
                }
            )

    total_pct = 100.0 * covered_total / statements_total if statements_total else 0.0
    emit(
        not reasons,
        reasons,
        {
            "files": len(files),
            "below_minimum": len(reasons),
            # Context only. Nothing branches on the total, by design.
            "total_percent": round(total_pct, 1),
        },
    )


def emit(success, reasons, statistics=None):
    doc = {"success": success}
    if reasons:
        doc["reasons"] = reasons
    if statistics:
        doc["statistics"] = statistics
    yaml.safe_dump(doc, sys.stdout, sort_keys=False)


if __name__ == "__main__":
    main()
