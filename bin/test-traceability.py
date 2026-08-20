#!/usr/bin/env python3
"""Check that every test states which requirement it discharges, and that
every settled requirement has a test.

A requirements document nobody is held to becomes decoration: it drifts from
the code, and the drift is invisible because nothing compares the two. This
compares them, in both directions.

Every test function must carry, somewhere in the comment block immediately
above it, a line of the form:

    // COVERS: FR-4.4 | property          (Go)
    # COVERS: FR-1.4, FR-1.5 | negative   (Python)

The requirement ids must exist in REQUIREMENTS.md, so a renamed or deleted
requirement fails here rather than leaving a test citing something gone. The
kind says which path through the requirement the test walks; a requirement
whose only tests are `positive` has had its happy path checked and nothing
else, and that is worth being able to see.

THE OTHER DIRECTION. A requirement no test cites is a requirement nothing
holds the code to, and it fails -- unless the document marks it open.

    | FR-1.1 | Any command-line tool can be run.       | [A] |   settled: must be covered
    | FR-5.9 | Schema versioning is unresolved.        | [?] |   open: reported, not fatal

The marker is the row's last bracketed cell. `[?]` means an open decision that
cannot have a test yet, and failing on those would make the honest state of the
document unrepresentable. Everything else -- `[A]`, `[D]`, `[A/D]`, or no
marker cell at all -- is settled, and settled means testable. A document with
no marker column therefore has no exemptions, which is the correct reading:
exemption is something you claim, never something you get by omission.

Exiting 0 is this task's contract, which is why it prints its findings rather
than returning an envelope: bolt's configuration never says what success
means, and a tool whose exit code genuinely is the answer needs no adapter.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

KINDS = ("positive", "negative", "edge", "property", "regression")

REQ_ID = re.compile(r"\b((?:FR|NFR)-\d+(?:\.\d+)?[a-z]?)\b")
# A requirement is declared by a table row: the id in the first cell, and the
# status marker -- if the document uses one -- in the last.
REQ_ROW = re.compile(r"^\|\s*((?:FR|NFR)-\d+(?:\.\d+)?[a-z]?)\s*\|(?P<rest>.*)$")
CELL = re.compile(r"(?<!\\)\|")
MARKER = re.compile(r"^\[[^\]]*\]$")

# Directories that hold someone else's tests. Walking into a virtualenv finds
# hundreds of `test_*.py` citing nothing, which under a gate that fails on
# uncovered requirements is not noise -- it is a guaranteed failure.
SKIP_DIRS = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "vendor",
        "__pycache__",
        "testdata",
        "site-packages",
    }
)


@dataclass(frozen=True)
class Language:
    """How to find tests in one language, and how it writes a comment."""

    name: str
    globs: tuple[str, ...]
    declaration: re.Pattern[str]
    comment: str

    @property
    def covers(self) -> re.Pattern[str]:
        """The COVERS line, written in this language's comment syntax."""
        marker = re.escape(self.comment)
        return re.compile(
            rf"^\s*{marker}\s*COVERS:\s*(?P<ids>[^|]+?)\s*\|\s*(?P<kind>\w+)\s*$"
        )

    @property
    def continuation(self) -> re.Pattern[str]:
        """Lines to step over when walking up to the comment block.

        A Python decorator sits between the annotation and the `def`, so a
        block that stopped at the first non-comment line would miss every
        annotated test that is also parametrised.
        """
        marker = re.escape(self.comment)
        return re.compile(rf"^\s*(?:{marker}|@)")


LANGUAGES = (
    Language(
        name="go",
        globs=("*_test.go",),
        declaration=re.compile(r"^func (Test\w+)\("),
        comment="//",
    ),
    Language(
        name="python",
        globs=("test_*.py", "*_test.py"),
        declaration=re.compile(r"^\s*(?:async\s+)?def (test_\w+)\s*\("),
        comment="#",
    ),
)


DIGITS = "0123456789"


def requirement_key(req: str) -> tuple[str, tuple[tuple[int, str], ...]]:
    """Sort FR-7.3 before FR-7.10, which a plain string sort does not.

    Every segment is keyed as (number, suffix) rather than as one or the other,
    so an id carrying a letter -- `FR-4.13a`, which qwark uses and bolt does
    not -- compares against a plain one instead of raising TypeError.
    """
    prefix, _, number = req.partition("-")
    segments = []
    for part in number.split("."):
        split = len(part) - len(part.lstrip(DIGITS))
        segments.append((int(part[:split] or 0), part[split:]))
    return (prefix, tuple(segments))


def declared_requirements(path: Path) -> dict[str, str]:
    """Collect every requirement the document declares, and its status marker.

    The marker is the row's last bracketed cell, or the empty string where the
    document carries no marker column.
    """
    declared: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        row = REQ_ROW.match(line)
        if not row:
            continue
        cells = [cell.strip() for cell in CELL.split(row.group("rest"))]
        trailing = [cell for cell in cells if cell]
        marker = trailing[-1] if trailing and MARKER.match(trailing[-1]) else ""
        declared[row.group(1)] = marker
    return declared


def is_open(marker: str) -> bool:
    """An open decision cannot have a test yet, so it is exempt from coverage."""
    return "?" in marker


def comment_block_above(lines: list[str], index: int, language: Language) -> list[str]:
    """Return the comment lines above index, stepping over decorators."""
    block = []
    cursor = index - 1
    while cursor >= 0 and language.continuation.match(lines[cursor]):
        block.append(lines[cursor])
        cursor -= 1
    return block


def annotation_of(block: list[str], language: Language) -> re.Match[str] | None:
    """Find the COVERS line in a comment block, if it has one."""
    for line in block:
        found = language.covers.match(line)
        if found:
            return found
    return None


def check_annotation(found: re.Match[str], declared: dict[str, str]) -> list[str]:
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


def scan_file(
    path: Path, language: Language, declared: dict[str, str]
) -> tuple[list[str], set[str]]:
    """Check every test in one file. Returns its failures and the ids it cites."""
    failures = []
    cited: set[str] = set()
    lines = path.read_text(encoding="utf-8").splitlines()
    for number, line in enumerate(lines):
        test = language.declaration.match(line)
        if not test:
            continue
        where = f"{path}:{number + 1}: {test.group(1)}"
        found = annotation_of(comment_block_above(lines, number, language), language)
        if not found:
            failures.append(
                f"{where} has no `{language.comment} COVERS: <ids> | <kind>` line"
            )
            continue
        cited.update(REQ_ID.findall(found.group("ids")))
        failures.extend(
            f"{where} {problem}" for problem in check_annotation(found, declared)
        )
    return failures, cited


def test_files(root: Path) -> list[tuple[Path, Language]]:
    """Every test file under root, paired with the language that found it."""
    found: dict[Path, Language] = {}
    for language in LANGUAGES:
        for pattern in language.globs:
            for path in root.rglob(pattern):
                if SKIP_DIRS.isdisjoint(path.parts) and path not in found:
                    found[path] = language
    return sorted(found.items())


def report(failures: list[str], declared: dict[str, str], cited: set[str]) -> int:
    """Print the findings and return the exit status."""
    uncovered = sorted(set(declared) - cited, key=requirement_key)
    unresolved = [req for req in uncovered if is_open(declared[req])]
    untested = [req for req in uncovered if not is_open(declared[req])]

    if unresolved:
        print(
            f"context: {len(unresolved)} open requirement(s) have no test, which is not a failure:"
        )
        for req in unresolved:
            print(f"  {req} {declared[req]}")
        print()

    if untested:
        print(f"{len(untested)} settled requirement(s) have no test citing them:")
        for req in untested:
            print(f"  {req} {declared[req] or '(no marker)'}")
        print()

    if failures:
        print(f"{len(failures)} test(s) do not say what they discharge:")
        for failure in failures:
            print(f"  {failure}")
        print()

    # An open requirement that a test cites anyway is held to its coverage like
    # any other; only the ones actually excused come out of the denominator.
    covered = len(declared) - len(uncovered)
    held = len(declared) - len(unresolved)
    if failures or untested:
        print(
            f"{covered} of {held} requirements covered; {len(unresolved)} open and exempt"
        )
        return 1
    print(
        "all tests cite a declared requirement, and every requirement held to "
        f"coverage has one ({covered} of {held})"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requirements", required=True, type=Path)
    parser.add_argument("root", type=Path, nargs="?", default=Path("."))
    args = parser.parse_args()

    # A missing document is a failure, not a traceback and not a pass. The task
    # is in the shared jig, so this is the first thing an adopter without a
    # requirements document sees, and it should read as an instruction.
    if not args.requirements.exists():
        print(
            f"{args.requirements} does not exist; "
            "traceability has nothing to hold the code to"
        )
        return 1

    declared = declared_requirements(args.requirements)
    if not declared:
        print(
            f"{args.requirements} declares no requirements; refusing to pass vacuously"
        )
        return 1

    failures: list[str] = []
    cited: set[str] = set()
    for path, language in test_files(args.root):
        file_failures, file_cited = scan_file(path, language, declared)
        failures.extend(file_failures)
        cited.update(file_cited)
    return report(failures, declared, cited)


if __name__ == "__main__":
    sys.exit(main())
