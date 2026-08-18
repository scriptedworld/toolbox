#!/usr/bin/env python3
"""Check that every Go test states which requirement it discharges.

A requirements document nobody is held to becomes decoration: it drifts from
the code, and the drift is invisible because nothing compares the two. This
compares them.

Every `func TestXxx(t *testing.T)` must carry, somewhere in the comment block
immediately above it, a line of the form:

    // COVERS: FR-4.4 | property
    // COVERS: FR-1.4, FR-1.5 | negative

The requirement ids must exist in REQUIREMENTS.md, so a renamed or deleted
requirement fails here rather than leaving a test citing something gone. The
kind says which path through the requirement the test walks; a requirement
whose only tests are `positive` has had its happy path checked and nothing
else, and that is worth being able to see.

Exiting 0 is this task's contract, which is why it prints its findings rather
than returning an envelope: bolt's configuration never says what success
means, and a tool whose exit code genuinely is the answer needs no adapter.

Requirements with no test at all are reported as context, never as a failure.
Some are open questions marked [?] that cannot have a test yet, and failing on
them would make the honest state of the document unrepresentable.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

KINDS = ("positive", "negative", "edge", "property", "regression")

TEST_FUNC = re.compile(r"^func (Test\w+)\(")
COVERS = re.compile(r"^\s*//\s*COVERS:\s*(?P<ids>[^|]+?)\s*\|\s*(?P<kind>\w+)\s*$")
REQ_ID = re.compile(r"\b((?:FR|NFR)-\d+(?:\.\d+)?[a-z]?)\b")
# A requirement is declared by a table row or a bare heading-style line; both
# start the line with the id after optional pipe-and-space decoration.
REQ_DECL = re.compile(r"^\|\s*((?:FR|NFR)-\d+(?:\.\d+)?[a-z]?)\s*\|")


def declared_requirements(path: Path) -> set[str]:
    """Collect every requirement id the document defines."""
    ids = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        found = REQ_DECL.match(line)
        if found:
            ids.add(found.group(1))
    return ids


def comment_block_above(lines: list[str], index: int) -> list[str]:
    """Return the contiguous `//` comment lines immediately above index."""
    block = []
    cursor = index - 1
    while cursor >= 0 and lines[cursor].lstrip().startswith("//"):
        block.append(lines[cursor])
        cursor -= 1
    return block


def annotation_of(block: list[str]) -> re.Match | None:
    """Find the COVERS line in a comment block, if it has one."""
    for line in block:
        found = COVERS.match(line)
        if found:
            return found
    return None


def check_annotation(found: re.Match, declared: set[str]) -> list[str]:
    """Validate one COVERS annotation against the requirements document."""
    problems = []
    ids = REQ_ID.findall(found.group("ids"))
    if not ids:
        problems.append(f"cites no requirement id in {found.group('ids')!r}")
    for req in ids:
        if req not in declared:
            problems.append(f"cites {req}, which REQUIREMENTS.md does not define")
    kind = found.group("kind")
    if kind not in KINDS:
        problems.append(f"kind {kind!r} is not one of {', '.join(KINDS)}")
    return problems


def scan_file(path: Path, declared: set[str]) -> tuple[list[str], set[str]]:
    """Check every test in one file. Returns its failures and the ids it cites."""
    failures = []
    cited = set()
    lines = path.read_text(encoding="utf-8").splitlines()
    for number, line in enumerate(lines):
        func = TEST_FUNC.match(line)
        if not func:
            continue
        where = f"{path}:{number + 1}: {func.group(1)}"
        found = annotation_of(comment_block_above(lines, number))
        if not found:
            failures.append(f"{where} has no `// COVERS: <ids> | <kind>` line")
            continue
        cited.update(REQ_ID.findall(found.group("ids")))
        failures.extend(f"{where} {problem}" for problem in check_annotation(found, declared))
    return failures, cited


def report(failures: list[str], declared: set[str], cited: set[str]) -> int:
    """Print the findings and return the exit status."""
    uncited = sorted(declared - cited)
    if uncited:
        print(f"context: {len(uncited)} of {len(declared)} requirements have no test citing them:")
        for req in uncited:
            print(f"  {req}")
        print()
    if failures:
        print(f"{len(failures)} test(s) do not say what they discharge:")
        for failure in failures:
            print(f"  {failure}")
        return 1
    print(f"all tests cite a declared requirement ({len(cited)} of {len(declared)} covered)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requirements", required=True, type=Path)
    parser.add_argument("root", type=Path, nargs="?", default=Path("."))
    args = parser.parse_args()

    declared = declared_requirements(args.requirements)
    if not declared:
        print(f"{args.requirements} declares no requirements; refusing to pass vacuously")
        return 1

    failures: list[str] = []
    cited: set[str] = set()
    for path in sorted(args.root.rglob("*_test.go")):
        file_failures, file_cited = scan_file(path, declared)
        failures.extend(file_failures)
        cited.update(file_cited)
    return report(failures, declared, cited)


if __name__ == "__main__":
    sys.exit(main())
