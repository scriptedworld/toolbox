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

RETIRED REQUIREMENTS. A requirement can be retired or superseded, and its id
is never reused. A `## Retired` section records each one and what replaced it:

    ## Retired

    | ID | Retired | Superseded by |
    |---|---|---|
    | FR-13.1 | 2026-08-26 | FR-6.2b, the adapter writes into the work directory |

Rows there are not live: they are not held to coverage, and a test citing one
fails saying where it went rather than saying it does not exist. An id that is
both live and retired fails outright, because reuse silently rewrites what
every existing reference to that id meant.

THE OTHER DIRECTION. A requirement no test cites is a requirement nothing
holds the code to, and it fails: unless the document marks it open.

    | FR-1.1 | Any command-line tool can be run.       | [A] |   settled: must be covered
    | FR-5.9 | Schema versioning is unresolved.        | [?] |   open: reported, not fatal

The marker is the row's last bracketed cell. `[?]` means an open decision that
cannot have a test yet, and failing on those would make the honest state of the
document unrepresentable. Everything else (`[A]`, `[D]`, `[A/D]`, or no
marker cell at all) is settled, and settled means testable. A document with
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
# status marker (if the document uses one) in the last.
REQ_ROW = re.compile(r"^\|\s*((?:FR|NFR)-\d+(?:\.\d+)?[a-z]?)\s*\|(?P<rest>.*)$")
CELL = re.compile(r"(?<!\\)\|")
MARKER = re.compile(r"^\[[^\]]*\]$")
# A `## Retired` heading switches which set the rows below it land in, and any
# other second-level heading switches back.
HEADING = re.compile(r"^##\s+(?P<title>.+?)\s*$")
RETIRED_HEADING = re.compile(r"^retired\b", re.IGNORECASE)

# Directories that hold tests this project is not answerable for. Walking into a
# virtualenv finds hundreds of `test_*.py` citing nothing, which under a gate
# that fails on uncovered requirements is not noise: it is a guaranteed failure.
#
# `.ephemera` is the same problem from the other end. Every repository here has
# one, it is gitignored working space, and a scratch `main_test.go` left in it
# failed this gate while being no part of the project.
SKIP_DIRS = frozenset(
    {
        ".git",
        ".ephemera",
        ".venv",
        "venv",
        "node_modules",
        "vendor",
        "__pycache__",
        "testdata",
        "site-packages",
        # Cargo's build output, which carries vendored `.rs` sources. Reading
        # every `.rs` file reaches it, and bolt's held 12 of them.
        "target",
    }
)


@dataclass(frozen=True)
class Language:
    """How to find tests in one language, and how it writes a comment."""

    name: str
    globs: tuple[str, ...]
    declaration: re.Pattern[str]
    comment: str
    # Lines a language allows between the comment block and the declaration.
    # A block stopping at the first non-comment line would miss every test
    # written with one.
    interposed: tuple[str, ...] = ()
    # What marks a declaration as a test, where the name does not. Go and
    # Python say so in the name; Rust says so in an attribute, so without this
    # every helper function in a test file reads as an unannotated test.
    attribute: re.Pattern[str] | None = None

    @property
    def covers(self) -> re.Pattern[str]:
        """The COVERS line, written in this language's comment syntax.

        A Rust doc comment does not match this and is not meant to. `///` puts
        a third slash where the pattern wants whitespace or `COVERS:`, so a
        doc comment is stepped over as continuation rather than read as an
        annotation carrying nothing.
        """
        marker = re.escape(self.comment)
        return re.compile(
            rf"^\s*{marker}\s*COVERS:\s*(?P<ids>[^|]+?)\s*\|\s*(?P<kind>\w+)\s*$"
        )

    @property
    def continuation(self) -> re.Pattern[str]:
        """Lines to step over when walking up to the comment block."""
        alternatives = "|".join((re.escape(self.comment), *self.interposed))
        return re.compile(rf"^\s*(?:{alternatives})")


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
        # A decorator sits between the annotation and the `def`.
        interposed=(r"@",),
    ),
    Language(
        name="rust",
        # Every `.rs` file, not just `tests/`, because a unit test lives in a
        # `#[cfg(test)] mod tests` inside the source file it covers. The
        # attribute below is what keeps that from reading every function as a
        # test.
        globs=("*.rs",),
        declaration=re.compile(r"^\s*(?:pub\s+)?(?:async\s+)?fn (\w+)\s*\("),
        comment="//",
        # `#[test]` sits directly above the `fn`, and a `///` doc comment may
        # sit between that and the COVERS line. The doc comment already matches
        # the `//` marker, so only the attribute needs naming here.
        interposed=(r"#\[",),
        attribute=re.compile(r"^\s*#\[(?:\w+::)*test\b"),
    ),
)


DIGITS = "0123456789"


def requirement_key(req: str) -> tuple[str, tuple[tuple[int, str], ...]]:
    """Sort FR-7.3 before FR-7.10, which a plain string sort does not.

    Every segment is keyed as (number, suffix) rather than as one or the other,
    so an id carrying a letter (`FR-4.13a`, which qwark uses and bolt does
    not) compares against a plain one instead of raising TypeError.
    """
    prefix, _, number = req.partition("-")
    segments = []
    for part in number.split("."):
        split = len(part) - len(part.lstrip(DIGITS))
        segments.append((int(part[:split] or 0), part[split:]))
    return (prefix, tuple(segments))


def requirement_documents(path: Path) -> list[Path]:
    """The documents a `--requirements` path names: one file, or a tree of them.

    A directory holds one file per requirement, `<category>/<ID>-<slug>.md`,
    and a category may carry a `README.md` for its preamble. Every `.md`
    beneath is read, README included: a requirement written somewhere
    unexpected should fail loudly for having no test rather than be skipped for
    sitting in the wrong file. The cost is that a preamble must not contain a
    parseable requirement row.

    Sorted, so a duplicate id names the same two files whatever order the
    filesystem hands them back in.
    """
    if path.is_dir():
        return sorted(p for p in path.rglob("*.md") if p.is_file())
    return [path]


def read_document(path: Path) -> tuple[dict[str, str], dict[str, str]]:
    """Collect what one document declares live, and what it has retired.

    A live requirement carries its status marker: the row's last bracketed
    cell, or the empty string where the document has no marker column.

    A row under a `## Retired` heading has gone. It is kept out of the live set
    so nothing holds it to coverage, and remembered so a test still citing it
    can be told where it went.

    The heading's reach stops at the end of the file. Concatenating a tree
    would let a document ending inside `## Retired` carry that state into the
    next one and silently retire its rows.
    """
    declared: dict[str, str] = {}
    retired: dict[str, str] = {}
    in_retired = False

    for line in path.read_text(encoding="utf-8").splitlines():
        heading = HEADING.match(line)
        if heading:
            in_retired = bool(RETIRED_HEADING.match(heading.group("title")))
            continue

        row = REQ_ROW.match(line)
        if not row:
            continue
        cells = [cell.strip() for cell in CELL.split(row.group("rest"))]
        trailing = [cell for cell in cells if cell]

        if in_retired:
            retired[row.group(1)] = " ".join(trailing)
            continue
        declared[row.group(1)] = (
            trailing[-1] if trailing and MARKER.match(trailing[-1]) else ""
        )
    return declared, retired


def read_requirements(
    path: Path,
) -> tuple[dict[str, str], dict[str, str], dict[str, list[Path]]]:
    """Read every document the path names, and report ids declared twice.

    One file per requirement makes a duplicate id possible in a way a single
    document never made it: two files each declaring `FR-4.1` merge into one
    entry, the later silently winning, and both look correct opened alone.
    That is the same corruption reusing a retired id causes, so it is reported
    the same way rather than resolved.
    """
    declared: dict[str, str] = {}
    retired: dict[str, str] = {}
    sources: dict[str, list[Path]] = {}

    for document in requirement_documents(path):
        document_declared, document_retired = read_document(document)
        for req in document_declared:
            sources.setdefault(req, []).append(document)
        declared.update(document_declared)
        retired.update(document_retired)

    duplicated = {req: paths for req, paths in sources.items() if len(paths) > 1}
    return declared, retired, duplicated


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


def check_annotation(
    found: re.Match[str], declared: dict[str, str], retired: dict[str, str]
) -> list[str]:
    """Validate one COVERS annotation against the requirements document."""
    problems = []
    ids = REQ_ID.findall(found.group("ids"))
    if not ids:
        problems.append(f"cites no requirement id in {found.group('ids')!r}")
    for req in ids:
        if req in retired:
            problems.append(f"cites {req}, retired: {retired[req]}")
        elif req not in declared:
            problems.append(f"cites {req}, which REQUIREMENTS.md does not define")
    kind = found.group("kind")
    if kind not in KINDS:
        problems.append(f"kind {kind!r} is not one of {', '.join(KINDS)}")
    return problems


def scan_file(
    path: Path, language: Language, declared: dict[str, str], retired: dict[str, str]
) -> tuple[list[str], set[str]]:
    """Check every test in one file. Returns its failures and the ids it cites."""
    failures = []
    cited: set[str] = set()
    lines = path.read_text(encoding="utf-8").splitlines()
    for number, line in enumerate(lines):
        test = language.declaration.match(line)
        if not test:
            continue
        block = comment_block_above(lines, number, language)

        # Where a language marks its tests with an attribute rather than in the
        # name, a declaration without it is a helper and not a test. Reporting
        # it would fail every test file for the functions supporting its tests.
        if language.attribute and not any(
            language.attribute.match(above) for above in block
        ):
            continue

        where = f"{path}:{number + 1}: {test.group(1)}"
        found = annotation_of(block, language)
        if not found:
            failures.append(
                f"{where} has no `{language.comment} COVERS: <ids> | <kind>` line"
            )
            continue
        cited.update(REQ_ID.findall(found.group("ids")))
        failures.extend(
            f"{where} {problem}"
            for problem in check_annotation(found, declared, retired)
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

    # Unreadable is its own case. A traceback here reads as a broken checker
    # rather than as a permission the adopter can fix, and the gate that ran it
    # reports a crash instead of a verdict.
    try:
        declared, retired, duplicated = read_requirements(args.requirements)
    except OSError as unreadable:
        print(f"{args.requirements} cannot be read: {unreadable.strerror}")
        return 1
    if not declared:
        print(
            f"{args.requirements} declares no requirements; refusing to pass vacuously"
        )
        return 1

    # Two files declaring one id is the split's own failure mode, and it is
    # reported before coverage because the merged entry hides one of them.
    if duplicated:
        print(f"{len(duplicated)} requirement id(s) are declared more than once:")
        for req in sorted(duplicated, key=requirement_key):
            where = ", ".join(str(p) for p in duplicated[req])
            print(f"  {req} is declared in {where}")
        return 1

    # A retired id is never reused. Declaring one again silently rewrites what
    # every existing reference to it meant, and nothing about the new row looks
    # wrong, so this is checked before anything else is reported.
    reused = sorted(set(declared) & set(retired), key=requirement_key)
    if reused:
        print(f"{len(reused)} requirement id(s) are both live and retired:")
        for req in reused:
            print(f"  {req} is declared again after being retired: {retired[req]}")
        return 1

    failures: list[str] = []
    cited: set[str] = set()
    for path, language in test_files(args.root):
        file_failures, file_cited = scan_file(path, language, declared, retired)
        failures.extend(file_failures)
        cited.update(file_cited)
    return report(failures, declared, cited)


if __name__ == "__main__":
    sys.exit(main())
