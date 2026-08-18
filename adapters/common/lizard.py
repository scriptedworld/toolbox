#!/usr/bin/env python3
"""Adapter for lizard: threshold warnings become reasons, the summary becomes
statistics.

Reads an execution record on stdin, writes an envelope on stdout. Pure: it runs
nothing, reads no clock and does not search the filesystem, so it is testable
from a fixture record with lizard not installed.

Two jobs, and they are independent.

REASONS. lizard exits 1 when anything is over threshold, which says only that
something is wrong. The reasons below say which function, in which file, on
which line, and by which measure -- which is what survives a merge across many
invocations and what a person needs in order to act.

STATISTICS. lizard's summary table carries the numbers worth watching over time:
how many functions there are, how complex the average one is, how much code
there is at all. They are emitted WHETHER OR NOT the task passes, because a
number is only useful as a series -- "average CCN 3.5" means nothing once and
means a great deal against last month's 2.9. A gate that reports nothing when it
passes cannot show a trend.

Requires that lizard NOT be run with `-w`. Warnings-only mode suppresses the
summary, so the statistics never reach this adapter. The jig runs it without.
"""

import re
import sys

import yaml

# ./internal/run/run.go:75: warning: Execute has 63 NLOC, 11 CCN, 572 token, 4 PARAM, 72 length, 0 ND
WARNING = re.compile(
    r"^(?P<file>.+?):(?P<line>\d+):\s*warning:\s*(?P<func>\S*)\s*has\s+"
    r"(?P<nloc>\d+)\s+NLOC,\s*(?P<ccn>\d+)\s+CCN,\s*(?P<token>\d+)\s+token,\s*"
    r"(?P<param>\d+)\s+PARAM,\s*(?P<length>\d+)\s+length"
)

# The summary table, which looks like:
#
#   Total nloc   Avg.NLOC  AvgCCN  Avg.token   Fun Cnt  Warning cnt   Fun Rt   nloc Rt
#   ------------------------------------------------------------------------------
#         6820      14.1     3.5       98.9      425            0      0.00    0.00
#
# Matched by finding the header rather than by counting lines from the end, so
# trailing output from anything else cannot shift it.
SUMMARY_HEADER = re.compile(r"^\s*Total\s+nloc\b.*\bFun\s+Cnt\b", re.IGNORECASE)
NUMERIC_ROW = re.compile(r"^\s*[\d.]+(?:\s+[\d.]+){7}\s*$")

# In header order. Names are snake_case rather than lizard's column headings,
# which contain dots and spaces and would be awkward to read back.
SUMMARY_FIELDS = (
    "total_nloc",
    "avg_nloc",
    "avg_ccn",
    "avg_token",
    "functions",
    "warnings",
    "function_rate",
    "nloc_rate",
)

CHECKER = "complexity"


def reasons_from(text):
    out = []
    for raw in text.splitlines():
        m = WARNING.match(raw.strip())
        if not m:
            continue
        func = m.group("func") or "(anonymous)"
        out.append(
            {
                "checker": CHECKER,
                "file": m.group("file").lstrip("./"),
                "line": int(m.group("line")),
                "function": func,
                "message": (
                    f"{func} is over threshold: "
                    f"cyclomatic complexity {m.group('ccn')}, "
                    f"{m.group('length')} lines, "
                    f"{m.group('param')} parameter(s)"
                ),
                "ccn": int(m.group("ccn")),
                "length": int(m.group("length")),
                "parameters": int(m.group("param")),
            }
        )
    return out


def statistics_from(text):
    """The summary table, or {} when lizard did not print one.

    Absence is not an error: `-w` suppresses the summary, and an adapter that
    failed the task over a missing statistic would be failing over presentation.
    """
    lines = text.splitlines()
    for i, raw in enumerate(lines):
        if not SUMMARY_HEADER.match(raw):
            continue
        # The numeric row follows, usually after a rule of dashes. Look ahead a
        # few lines rather than assuming the exact offset.
        for candidate in lines[i + 1 : i + 5]:
            if not NUMERIC_ROW.match(candidate):
                continue
            values = candidate.split()
            stats = {}
            for name, value in zip(SUMMARY_FIELDS, values):
                # Integers stay integers so they read as counts rather than
                # measurements; the averages and rates keep their decimals.
                stats[name] = int(value) if "." not in value else float(value)
            return stats
    return {}


def emit(success, reasons=None, statistics=None):
    """Write one envelope. Optional blocks are omitted rather than empty --
    `reasons: []` on a pass reads as "checked and found nothing to say", which
    is not the same as having nothing to report."""
    envelope: dict[str, object] = {"success": success}
    if reasons:
        envelope["reasons"] = reasons
    if statistics:
        envelope["statistics"] = statistics
    yaml.safe_dump(envelope, sys.stdout, sort_keys=False)


def main():
    record = yaml.safe_load(sys.stdin.read()) or {}
    captures = record.get("captures") or {}
    text = (captures.get("stdout") or "") + "\n" + (captures.get("stderr") or "")

    reasons = reasons_from(text)
    stats = statistics_from(text)

    if reasons:
        emit(False, reasons, stats)
        return

    # lizard said nothing this adapter recognises. If it also exited non-zero,
    # something is wrong that this adapter cannot name, and reporting a pass
    # would hide it.
    code = captures.get("exitcode", 0)
    if code not in (0, None):
        emit(
            False,
            [
                {
                    "checker": CHECKER,
                    "message": (
                        f"lizard exited {code} and produced no warnings this "
                        "adapter could parse"
                    ),
                }
            ],
            stats,
        )
        return

    emit(True, statistics=stats)


if __name__ == "__main__":
    main()
