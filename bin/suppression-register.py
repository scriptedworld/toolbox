#!/usr/bin/env python3
"""Check that the suppression register and the source agree about what is silenced.

A register nobody is held to becomes decoration in exactly the way a
requirements document does, and the drift is invisible because nothing compares
the two. On 2026-08-16 this project's register named two files that had been
moved months of commits earlier, listed a gosec rule that does not exist, and
missed three pragmas entirely -- while carrying a line saying it had been
verified by hand. That is the failure this exists to make impossible.

Every `#nosec` or `//nolint` in the source must appear in the register's index,
and every row of that index must correspond to a pragma that is really there.
Both directions matter: an unregistered pragma is a suppression nobody
justified, and a registered row with nothing behind it is a justification for
something that has already gone, which reads as cover for whatever replaces it.

The index is the indented block at the end of the register, one row per file:

    internal/artifact/artifact.go   #nosec G304
    internal/cli/cli.go        ×2   #nosec G304

`×N` says how many pragmas that file carries; absent means one. The count is
part of the comparison, so a second suppression added to an already-registered
file is caught rather than hidden behind the first.

Exiting 0 is this task's contract, which is why it prints its findings rather
than returning an envelope: bolt's configuration never says what success means,
and a tool whose exit code genuinely is the answer needs no adapter.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

# In the source. Both forms the register's own grep looks for.
SOURCE_PRAGMA = re.compile(r"#nosec\s+(?P<rules>(?:G\d+[\s,]*)+)|//nolint:(?P<linters>[\w,]+)")

# In the register: an indented row naming a file, an optional count, and the
# pragma it carries. Anything after the rule ids is prose and is ignored.
INDEX_ROW = re.compile(
    r"^\s{2,}(?P<path>[\w./-]+\.(?:go|py))\s+"
    r"(?:×(?P<count>\d+)\s+)?"
    r"(?:#nosec\s+(?P<rules>(?:G\d+[\s,]*)+)|//nolint:(?P<linters>[\w,]+))"
)


def rules_of(found: re.Match) -> frozenset[str]:
    """The rule ids one pragma names, however it spells them."""
    text = found.group("rules") or found.group("linters") or ""
    return frozenset(part for part in re.split(r"[\s,]+", text.strip()) if part)


def scan_source(root: Path) -> Counter[tuple[str, frozenset[str]]]:
    """Count the pragmas in the tree, by file and by the rules they silence."""
    found: Counter[tuple[str, frozenset[str]]] = Counter()
    for path in sorted(root.rglob("*.go")):
        text = path.read_text(encoding="utf-8")
        for match in SOURCE_PRAGMA.finditer(text):
            key = path.relative_to(root).as_posix()
            found[(key, rules_of(match))] += 1
    return found


def scan_register(path: Path) -> Counter[tuple[str, frozenset[str]]]:
    """Read the register's index into the same shape as the source scan."""
    listed: Counter[tuple[str, frozenset[str]]] = Counter()
    if not path.exists():
        return listed
    for line in path.read_text(encoding="utf-8").splitlines():
        row = INDEX_ROW.match(line)
        if row:
            count = int(row.group("count") or 1)
            listed[(row.group("path"), rules_of(row))] += count
    return listed


def describe(key: tuple[str, frozenset[str]]) -> str:
    """Name one entry the way the register writes it."""
    where, rules = key
    return f"{where} ({' '.join(sorted(rules))})"


def compare(
    source: Counter[tuple[str, frozenset[str]]],
    register: Counter[tuple[str, frozenset[str]]],
) -> list[str]:
    """Every way the two can disagree, said in the register's own terms."""
    failures = []
    for key in sorted(set(source) | set(register)):
        here, there = source[key], register[key]
        if there == 0:
            failures.append(
                f"{describe(key)} ×{here} is in the source and in no register entry; "
                "ask before it stays, then register it -- or remove it"
            )
        elif here == 0:
            failures.append(
                f"{describe(key)} ×{there} is registered and is not in the source; "
                "the pragma moved or went, and the register did not follow"
            )
        elif here != there:
            failures.append(
                f"{describe(key)}: the source carries {here}, the register says {there}"
            )
    return failures


def report(failures: list[str], total: int, register: Path) -> int:
    """Print the findings and return the exit status."""
    if failures:
        print(f"{len(failures)} disagreement(s) between the source and {register}:")
        for failure in failures:
            print(f"  {failure}")
        return 1
    if total == 0:
        print("no suppression pragmas anywhere, and none registered")
        return 0
    print(f"every suppression is registered, and every entry is real ({total} pragma(s))")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--register", required=True, type=Path)
    parser.add_argument("root", type=Path, nargs="?", default=Path("."))
    args = parser.parse_args()

    source = scan_source(args.root)
    register = scan_register(args.register)
    if not args.register.exists() and source:
        print(f"{sum(source.values())} pragma(s) in the source and no {args.register}")
        return 1

    return report(compare(source, register), sum(source.values()), args.register)


if __name__ == "__main__":
    sys.exit(main())
