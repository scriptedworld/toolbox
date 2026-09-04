#!/usr/bin/env python3
"""Check that every test states which requirement it discharges, and that
every settled requirement has a test.

A requirements document nobody is held to becomes decoration: it drifts from
the code, and the drift is invisible because nothing compares the two. This
compares them, in both directions.

Every test function must carry, somewhere in the comment block immediately
above it, a line of the form:

    // COVERS: FR-4.4 | property          (Go, and Rust)
    # COVERS: FR-1.4, FR-1.5 | negative   (Python)

RUST WRITES IT `//` AND NEVER `///`. A doc comment is not a comment for this
purpose: the pattern wants whitespace or `COVERS:` where the third slash sits,
so `/// COVERS: FR-1.1 | positive` matches nothing and the test then reads as
carrying no annotation at all. That is invisible rather than loud, which is the
kind of wrong that survives, and `///` is exactly what a doc-comment reflex
reaches for. A `///` line between the marker and the `fn` is fine and expected;
it is stepped over.

A Rust test is found by its `#[test]` attribute rather than by its name, so a
helper function in a test file is not a test and is not asked to cite anything.

The requirement ids must exist in REQUIREMENTS.md, so a renamed or deleted
requirement fails here rather than leaving a test citing something gone. The
kind says which path through the requirement the test walks; a requirement
whose only tests are `positive` has had its happy path checked and nothing
else, and that is worth being able to see.

RETIRED REQUIREMENTS. A requirement can be retired or superseded, and its id
is never reused. Two things record it, and a split repository should use the
first.

THE FILENAME, which is the better one:

    docs/REQUIREMENTS/<level>/<group>/FR-7.4-a-thing.retired

Everything in a `.retired` document has gone, whatever is inside it. There is
no heading, no switch and no below-this-line, so retiring a requirement and
appending one are different gestures rather than the same gesture in different
positions. It shows in `ls` without opening anything, and it leaves the row in
the group it always sat in. `.retired.md` is read the same way.

`.superseded` and `.superseded.md` say the id was replaced rather than simply
dropped, and are read the same way again. The suffix is the record; the
checker treats all four alike, because what it needs from any of them is that
the id stays held.

A `## Retired` HEADING, for a document that has nowhere else to put the record:

    ## Retired

    | ID | Retired | Superseded by |
    |---|---|---|
    | FR-13.1 | 2026-08-26 | FR-6.2b, the adapter writes into the work directory |

This is a state switch that runs to the end of the file, so a row appended
after it is retired by where it landed. Put such a section last and a careless
append is a silent retirement. It stays because a single `REQUIREMENTS.md` has
no alternative, and it goes when every repository has split.

Rows retired either way are not live: they are not held to coverage, and a test
citing one fails saying where it went rather than saying it does not exist. An
id that is both live and retired fails outright, because reuse silently
rewrites what every existing reference to that id meant.

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

# pylint: disable=duplicate-code
#
# STRUCTURAL, NOT INCIDENTAL. Every script in `bin/` and `adapters/` is spawned
# by path from a directory that is not a package, so none can import another,
# so anything two of them must both do is written twice. R0801 finds a different
# pair each time one is dissolved: the coverage adapters' judgement, the
# checkers' `SKIP_DIRS`, the adapters' `emit`. Registered as S-3 in SUPPRESSIONS,
# with what would retire it.

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Iterator
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
        return re.compile(rf"^\s*{marker}\s*COVERS:\s*(?P<ids>[^|]+?)\s*\|\s*(?P<kind>\w+)\s*$")

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

# The note inside a directory that IS one requirement. Fixed rather than
# derived from the directory's name, so retiring is one rename and nothing
# inside the directory has to change with it.
REQUIREMENT_NOTE = "requirement.md"


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


def is_retired_by_name(path: Path) -> bool:
    """A document whose name retires everything in it.

    Retirement carried by the filename has no heading, no switch and no
    below-this-line, so the row that retires something and the row appended
    after it cannot be confused. It is also visible in `ls` without opening
    anything, and it leaves a retired requirement in the group it always sat
    in, so a reader meeting an old id finds it where it was.

    Both spellings count. `.retired` is the shape a split repository uses, and
    `.retired.md` is the one that stays readable to anything expecting
    markdown.

    `.superseded` and `.superseded.md` are read the same way, and record that
    the id was replaced rather than simply dropped. The name carries the
    difference for a reader; nothing downstream needs it, because either way
    the id has gone and either way it must stay held so it cannot be declared
    again.

    A suffix ending `.md` is the one that has to be recognised here rather
    than left to the glob, which collects it already. Unrecognised, such a
    document is read and every row in it reads live, which inverts the
    never-reuse guarantee instead of merely failing to enforce it.

    This tests a NAME, so it answers for a directory exactly as for a file.
    Where a requirement is a directory, retiring it is renaming that directory
    and the suffix lands there rather than on anything inside.
    `is_retired_by_position` is what applies it to a document's holders.
    """
    return path.name.endswith((".retired", ".retired.md", ".superseded", ".superseded.md"))


def enclosing_directories(path: Path, root: Path) -> Iterator[Path]:
    """Every directory holding a document, from its own up to the root.

    BOUNDED AT THE ROOT, which is the whole point of taking one. Walking to
    the filesystem root instead reads whatever happens to be above the
    repository: a tree archived as `holder.retired/`, or a checkout beneath
    one, would retire every requirement in it. Nothing would then be held to
    coverage and the run would pass, which is the failure mode this checker
    exists to prevent arriving through the checker itself.
    """
    current = path.parent
    while True:
        yield current
        if current == root or current.parent == current:
            return
        current = current.parent


def is_retired_by_position(path: Path, root: Path) -> bool:
    """Whether a document has gone, by its own name or by a directory's.

    A requirement that is a directory carries its state in that directory's
    name, so everything beneath it has gone with it: the note, and the
    supporting material beside the note. Retiring is one rename and nothing
    inside is touched, which is the property the fixed note name buys.
    """
    if is_retired_by_name(path):
        return True
    return root.is_dir() and any(is_retired_by_name(holder) for holder in enclosing_directories(path, root))


def declares_requirements(document: Path, notes: set[Path], root: Path) -> bool:
    """Whether a document declares requirements or is supporting material.

    `notes` is every directory holding a `requirement.md`, so each such
    directory is one requirement and only its own note declares anything.

    Nesting resolves outwards: a note inside another requirement's directory is
    supporting material, because everything beside a note is. Comparing against
    the NEAREST holder is what says so, `enclosing_directories` yielding from
    the document's own directory upwards.

    A file called `requirement.md` whose own directory is NOT one of `notes` is
    read as the ordinary document it appears to be. That is the root's case,
    the root being excluded from `notes` deliberately: testing the name alone
    would drop it from the tree entirely rather than merely refusing to treat
    its directory as one requirement.
    """
    holders = [d for d in enclosing_directories(document, root) if d in notes]
    if document.name == REQUIREMENT_NOTE and document.parent in notes:
        return holders == [document.parent]
    return not holders


def requirement_documents(path: Path) -> list[Path]:
    """The documents a `--requirements` path names: one file, or a tree of them.

    A directory holds one file per requirement, `<category>/<ID>-<slug>.md`,
    and a category may carry a `README.md` for its preamble. Every `.md`
    beneath is read, README included: a requirement written somewhere
    unexpected should fail loudly for having no test rather than be skipped for
    sitting in the wrong file. The cost is that a preamble must not contain a
    parseable requirement row.

    `.retired` and `.superseded` are read as well as `.md`. A retired document
    that the checker cannot see is the quiet way to lose the never-reuse
    guarantee: nothing holds the id, so declaring it again passes, and every
    existing reference to it silently means something else.

    Their `.md` spellings need no pattern of their own, being `.md` files.
    What they need is `is_retired_by_name`, or they are collected here and
    read as live.

    A DIRECTORY HOLDING `requirement.md` IS ONE REQUIREMENT, and only that note
    declares anything. Everything beside it is supporting material: repro
    evidence, captured output, whatever has to travel with the row. Read as a
    requirements document, an evidence write-up containing a table would
    declare a phantom requirement that no test can cover and no author believes
    they wrote.

    The note's name is fixed rather than matching the directory stem, so
    retiring is a single directory rename with nothing inside to touch. A
    stem-matching name would stop matching at exactly that rename.

    A directory without a note keeps the older behaviour, where every `.md`
    beneath is read and a row in an unexpected file fails loudly rather than
    being skipped. That is what makes the rule above safe to add: it narrows
    only where a note says it should.

    THE ROOT IS NEVER ONE OF THOSE DIRECTORIES. It is the tree, not a
    requirement in it, and a note written one level too high would otherwise
    make every document beneath it supporting material: the ids vanish and the
    run passes, which is the one outcome this checker exists to prevent.
    `requirement.md` at the root is read as the ordinary document it appears to
    be, so a row in it fails loudly for having no test.

    FR-4.20 bounds the retirement walk at the root for that same reason. Both
    rules walk upwards and both stop in the same place.

    Sorted, so a duplicate id names the same two files whatever order the
    filesystem hands them back in.
    """
    if not path.is_dir():
        return [path]

    documents = collected_documents(path)
    notes = requirement_directories(documents, path)
    return sorted(p for p in documents if declares_requirements(p, notes, path))


def collected_documents(path: Path) -> set[Path]:
    """Every file under a requirements tree that could carry a row."""
    found = (p for pattern in ("*.md", "*.retired", "*.superseded") for p in path.rglob(pattern))
    return {p for p in found if p.is_file()}


def requirement_directories(documents: set[Path], root: Path) -> set[Path]:
    """The directories that are one requirement each, never including the root.

    See `requirement_documents` for why the root is excluded: it is the tree
    rather than a requirement in it, and including it makes every document
    beneath supporting material.
    """
    return {p.parent for p in documents if p.name == REQUIREMENT_NOTE} - {root}


def report_nested(nested: list[tuple[Path, Path]]) -> None:
    """Say which requirement directories sit inside another, and what follows.

    The closing line is the point of the message. Naming the pair without
    saying that the inner note declares nothing leaves a reader to discover
    that from a missing id somewhere else.
    """
    print(f"{len(nested)} requirement directory(ies) sit inside another:")
    for inner, outer in nested:
        print(f"  {inner} is inside another, {outer}")
    print("  everything beside a note is supporting material, so the inner note declares nothing")


def nested_requirement_directories(path: Path) -> list[tuple[Path, Path]]:
    """Requirement directories sitting inside another, as (inner, outer) pairs.

    Reported rather than resolved, the way a duplicate id is. Nothing here can
    tell a genuine nested requirement from a supporting file that happens to
    carry the note's name, and the sibling rule silently makes the inner one
    supporting material either way.

    Silence is the expensive outcome: the inner id is never declared, so a test
    citing it is told the requirement does not exist, and the obvious remedy is
    to delete a real test's coverage of a requirement sitting on disk. That is
    the same misleading remedy the retirement suffixes were fixed for twice.
    """
    if not path.is_dir():
        return []

    notes = requirement_directories(collected_documents(path), path)
    nested = []
    for directory in sorted(notes):
        outer = [d for d in enclosing_directories(directory / REQUIREMENT_NOTE, path) if d in notes and d != directory]
        if outer:
            nested.append((directory, outer[0]))
    return nested


def rows_in_retirement_order(
    path: Path,
    retired_by_name: bool,
) -> Iterator[tuple[bool, str, list[str]]]:
    """Every requirement row in one document, each with whether it has gone.

    Walking and classifying are separated because the retirement state is a
    property of position in the file, and the caller only wants the answer. It
    yields `(gone, id, cells)` so `read_document` sorts rows into two
    dictionaries and does no parsing of its own.

    `retired_by_name` arrives rather than being derived here, because it is now
    a property of position in the TREE as well as in the name, and only a
    caller holding the requirements root can bound the search for a retired
    directory. See `is_retired_by_position`.
    """
    in_retired = retired_by_name

    for line in path.read_text(encoding="utf-8").splitlines():
        heading = HEADING.match(line)
        if heading and not retired_by_name:
            in_retired = bool(RETIRED_HEADING.match(heading.group("title")))
            continue
        if heading:
            continue

        row = REQ_ROW.match(line)
        if not row:
            continue
        cells = [cell.strip() for cell in CELL.split(row.group("rest"))]
        yield in_retired, row.group(1), [cell for cell in cells if cell]


def read_document(path: Path, retired_by_name: bool) -> tuple[dict[str, str], dict[str, str]]:
    """Collect what one document declares live, and what it has retired.

    A live requirement carries its status marker: the row's last bracketed
    cell, or the empty string where the document has no marker column.

    A requirement has gone if the document's NAME retires it, if a DIRECTORY
    holding it does, or if the row sits under a `## Retired` heading. All three
    keep it out of the live set so nothing holds it to coverage, and remember
    it so a test still citing it can be told where it went.

    THE TWO ARE NOT EQUAL AND THE NAME IS THE BETTER ONE. A heading is a state
    switch that runs to the end of the file, so appending a requirement and
    retiring one are the same gesture, and only their position in the file
    tells them apart. A name has no below-this-line to fall under.

    The heading survives because a single `REQUIREMENTS.md` has nowhere else to
    put the record, and seven of the eight repositories here are still one
    file. It goes when they have all split, not before.

    The heading's reach stops at the end of the file either way. Concatenating
    a tree would let a document ending inside `## Retired` carry that state
    into the next one and silently retire its rows.

    A NAME-RETIRED DOCUMENT IGNORES ITS HEADINGS ENTIRELY. Otherwise the first
    heading that is not `## Retired` turns retirement back off for the rest of
    the file, and `## Superseded by` is the likeliest thing to write in a
    retired requirement's file. The failure points the wrong way: the id leaves
    the retired set, so declaring it again passes the never-reuse check and the
    gate demands a test for a requirement that has gone.
    """
    declared: dict[str, str] = {}
    retired: dict[str, str] = {}

    for gone, req_id, trailing in rows_in_retirement_order(path, retired_by_name):
        if gone:
            retired[req_id] = " ".join(trailing)
            continue
        declared[req_id] = trailing[-1] if trailing and MARKER.match(trailing[-1]) else ""
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
        document_declared, document_retired = read_document(document, is_retired_by_position(document, path))
        for req in document_declared:
            sources.setdefault(req, []).append(document)
        declared.update(document_declared)
        retired.update(document_retired)

    duplicated = {req: paths for req, paths in sources.items() if len(paths) > 1}
    return declared, retired, duplicated


def is_open(marker: str) -> bool:
    """An open decision cannot have a test yet, so it is exempt from coverage."""
    return "?" in marker


# The scope clause inside a status marker: `[A/D python]`, or with a kind half,
# `[A go,python:edge,negative]`. One bracket and no `|` in it, because a row's
# marker is its last bracketed cell and MARKER matches `^\[[^\]]*\]$`.
SCOPE_CLAUSE = re.compile(
    r"^\[\s*[^\s\]]*\s+"
    r"(?P<suites>[a-z][a-z0-9_-]*(?:,[a-z][a-z0-9_-]*)*)"
    r"(?P<kinds>:[a-z][a-z0-9_-]*(?:,[a-z][a-z0-9_-]*)*)?"
    r"\s*\]$"
)


def out_of_scope(marker: str, scope: str) -> bool:
    """Whether a row belongs to some other tree than the one being checked.

    A scope names the trees expected to discharge a row, so a row naming none is
    expected everywhere and a row naming others is not this run's to cover. It
    is what lets one requirements document hold three packs to their own trees
    rather than to the union of all of them, which passes whenever any one pack
    covers a row.

    **A KIND-SCOPED ROW STAYS IN SCOPE EVERYWHERE, and that is not an
    approximation.** `[A go,python:edge,negative]` scopes two KINDS of a row and
    leaves the rest of it expected in every tree, so the row is still this run's
    to cover. This checker asks whether an id is cited at all and never asks by
    which kind, so the row-level answer is the whole of the question here.
    Which suite holds which kind is `test-suite-parity.py`'s to answer, and it
    reads the same clause for it: this is a coarser reading of one grammar
    rather than a second copy of the list.
    """
    if not scope:
        return False
    clause = SCOPE_CLAUSE.match(marker)
    if not clause or clause.group("kinds"):
        return False
    return scope not in clause.group("suites").split(",")


def comment_block_above(lines: list[str], index: int, language: Language) -> list[str]:
    """Return the comment lines above index, stepping over decorators.

    A DECORATOR MAY WRAP, AND ITS CONTINUATION LINE STARTS WITH NEITHER `@` NOR
    `#`. Walking up from the declaration, a line inside an unclosed bracket
    group belongs to whatever opened it, so it is stepped over whatever it
    begins with. Without that the block stops at the wrapped line and a test
    carrying a correct mark reports as citing nothing.

    Filed by agent-support 2026-08-28 after three of seven tests read as uncited
    on first run, all three from wrapped decorators. **`ruff format` wraps a long
    decorator by default**, so this is reachable by formatting a conformant file
    rather than by writing one oddly, and the failure points the wrong way: the
    report blames the test for citing nothing while the mark sits right there,
    so the author's fix is to add what is already present.

    Balance is counted from the declaration upwards, so a line only counts as a
    continuation while something below it is still open. An ordinary statement
    is balanced and ends the block exactly as before.
    """
    block = []
    cursor = index - 1
    owed = 0
    while cursor >= 0:
        line = lines[cursor]
        closes = (line.count(")") - line.count("(")) + (line.count("]") - line.count("["))
        # A line closing more than it opens is finishing something declared
        # above it, so read upward it is a continuation whatever it starts
        # with. `owed` carries that need until the opener is found.
        if owed <= 0 and closes <= 0 and not language.continuation.match(line):
            break
        block.append(line)
        owed = max(0, owed + closes)
        cursor -= 1
    return block


def annotation_of(block: list[str], language: Language) -> re.Match[str] | None:
    """Find the COVERS line in a comment block, if it has one."""
    for line in block:
        found = language.covers.match(line)
        if found:
            return found
    return None


def check_annotation(found: re.Match[str], declared: dict[str, str], retired: dict[str, str], source: str) -> list[str]:
    """Validate one COVERS annotation against the requirements document.

    `source` is the `--requirements` path as given, because the message whose
    job is to say where to add a row must name somewhere that exists. Naming
    `REQUIREMENTS.md` sent a tier 2 or tier 3 reader looking for a document
    nobody has.
    """
    problems = []
    ids = REQ_ID.findall(found.group("ids"))
    if not ids:
        problems.append(f"cites no requirement id in {found.group('ids')!r}")
    for req in ids:
        if req in retired:
            problems.append(f"cites {req}, retired: {retired[req]}")
        elif req not in declared:
            problems.append(f"cites {req}, which {source} does not define")
    kind = found.group("kind")
    if kind not in KINDS:
        problems.append(f"kind {kind!r} is not one of {', '.join(KINDS)}")
    return problems


def scan_file(path: Path, language: Language, declared: dict[str, str], retired: dict[str, str], source: str) -> tuple[list[str], set[str]]:
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
        if language.attribute and not any(language.attribute.match(above) for above in block):
            continue

        where = f"{path}:{number + 1}: {test.group(1)}"
        found = annotation_of(block, language)
        if not found:
            failures.append(f"{where} has no `{language.comment} COVERS: <ids> | <kind>` line")
            continue
        cited.update(REQ_ID.findall(found.group("ids")))
        failures.extend(f"{where} {problem}" for problem in check_annotation(found, declared, retired, source))
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


def print_block(heading: str, rows: list[str]) -> None:
    """A heading, its indented rows, and a blank line. Nothing when there are none.

    Four findings groups had this shape written out four times, which is most of
    what took `report` to a cognitive complexity of 23 against a limit of 15.
    """
    if not rows:
        return
    print(heading)
    for row in rows:
        print(f"  {row}")
    print()


def print_rows(heading: str, rows: list[str]) -> int:
    """The same, for a group that ends the run, and the failing status with it."""
    print(heading)
    for row in rows:
        print(f"  {row}")
    return 1


def report(failures: list[str], declared: dict[str, str], cited: set[str], scope: str = "") -> int:
    """Print the findings and return the exit status.

    A scoped run holds this tree to the rows that name it and to the rows that
    name no tree at all. The others are exempt exactly as an open row is: out of
    the denominator, reported as context, and never a failure. They stay in
    `declared` rather than being dropped, so a test in this tree citing one is
    still told the id exists and is answered by parity's `cited by X but scoped
    to Y` rather than by this checker claiming the requirement does not exist.
    """
    elsewhere = sorted((req for req in declared if out_of_scope(declared[req], scope)), key=requirement_key)
    held_here = {req: marker for req, marker in declared.items() if req not in set(elsewhere)}

    uncovered = sorted(set(held_here) - cited, key=requirement_key)
    unresolved = [req for req in uncovered if is_open(held_here[req])]
    untested = [req for req in uncovered if not is_open(held_here[req])]

    print_block(
        f"context: {len(elsewhere)} requirement(s) are scoped to another tree, not this one:",
        [f"{req} {declared[req]}" for req in elsewhere],
    )
    print_block(
        f"context: {len(unresolved)} open requirement(s) have no test, which is not a failure:",
        [f"{req} {held_here[req]}" for req in unresolved],
    )
    print_block(
        f"{len(untested)} settled requirement(s) have no test citing them:",
        [f"{req} {held_here[req] or '(no marker)'}" for req in untested],
    )
    print_block(
        f"{len(failures)} test(s) do not say what they discharge:",
        list(failures),
    )

    # An open requirement that a test cites anyway is held to its coverage like
    # any other; only the ones actually excused come out of the denominator.
    covered = len(held_here) - len(uncovered)
    held = len(held_here) - len(unresolved)
    # The scoped-out count is stated whether the run passes or fails, so the
    # arithmetic a wrapper checks — files on disk against denominator plus
    # exemptions — reaches every number it needs from one line.
    scoped_out = f"; {len(elsewhere)} scoped elsewhere" if elsewhere else ""
    if failures or untested:
        print(f"{covered} of {held} requirements covered; {len(unresolved)} open and exempt{scoped_out}")
        return 1
    print(f"all tests cite a declared requirement, and every requirement held to coverage has one ({covered} of {held}){scoped_out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """The command line, built apart from `main` so `main` reads as its steps."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requirements", required=True, type=Path)
    parser.add_argument(
        "--scope",
        default="",
        metavar="NAME",
        help=(
            "hold this tree only to the rows that name it and the rows that name "
            "no tree, so one requirements document can hold several trees to their "
            "own coverage rather than to the union of all of them"
        ),
    )
    parser.add_argument(
        "--dir",
        dest="directory",
        type=Path,
        metavar="PATH",
        help=(
            "the tree to read, named rather than positional. `--scope go --dir ./go` "
            "says which rows and which tree separately, where `--scope go go` reads "
            "as one word written twice"
        ),
    )
    # THE POSITIONAL STAYS, and `--dir` is added beside it rather than replacing
    # it. This file is symlinked into bolt and wrench, and the positional is what
    # `bolt.common-quality.yaml`, `bolt.rust-quality.yaml`,
    # `bolt.wrench-quality.yaml` and wrench's `test-requirement-count.py` all
    # pass today. Removing it would be a breaking change to a shared checker, and
    # every consumer of one needs somebody.
    parser.add_argument("root", type=Path, nargs="?", default=None)
    return parser


def scan_tree(root: Path, declared: dict[str, str], retired: dict[str, str], requirements: str) -> tuple[list[str], set[str]]:
    """Every test file under root, and what it cites."""
    failures: list[str] = []
    cited: set[str] = set()
    for path, language in test_files(root):
        file_failures, file_cited = scan_file(path, language, declared, retired, requirements)
        failures.extend(file_failures)
        cited.update(file_cited)
    return failures, cited


def main() -> int:
    args = build_parser().parse_args()

    # Both is a mistake worth naming rather than resolving by precedence: a
    # caller who wrote two directories meant one of them, and picking one for
    # them reads whichever tree they did not mean.
    #
    # Printed and returned rather than `parser.error`, which raises SystemExit.
    # Every other failure here prints and returns, a traceback reads as a broken
    # checker rather than as something the caller can fix, and the tests call
    # main() directly and read a return code.
    if args.directory is not None and args.root is not None:
        print("give --dir or a positional directory, not both")
        return 2
    root = args.directory if args.directory is not None else (args.root or Path("."))

    # A missing document is a failure, not a traceback and not a pass. The task
    # is in the shared jig, so this is the first thing an adopter without a
    # requirements document sees, and it should read as an instruction.
    if not args.requirements.exists():
        print(f"{args.requirements} does not exist; traceability has nothing to hold the code to")
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
        print(f"{args.requirements} declares no requirements; refusing to pass vacuously")
        return 1

    # An ambiguous tree shape is reported before anything derived from reading
    # it, because it is why an id is missing. Left silent, the inner note's
    # rows are absent and a test citing them is told the requirement does not
    # exist, which points a reader at deleting real coverage.
    nested = nested_requirement_directories(args.requirements)
    if nested:
        report_nested(nested)
        return 1

    # Two files declaring one id is the split's own failure mode, and it is
    # reported before coverage because the merged entry hides one of them.
    if duplicated:
        return print_rows(
            f"{len(duplicated)} requirement id(s) are declared more than once:",
            [f"{req} is declared in {', '.join(str(p) for p in duplicated[req])}" for req in sorted(duplicated, key=requirement_key)],
        )

    # A retired id is never reused. Declaring one again silently rewrites what
    # every existing reference to it meant, and nothing about the new row looks
    # wrong, so this is checked before anything else is reported.
    reused = sorted(set(declared) & set(retired), key=requirement_key)
    if reused:
        return print_rows(
            f"{len(reused)} requirement id(s) are both live and retired:",
            [f"{req} is declared again after being retired: {retired[req]}" for req in reused],
        )

    failures, cited = scan_tree(root, declared, retired, str(args.requirements))
    return report(failures, declared, cited, args.scope)


if __name__ == "__main__":
    sys.exit(main())
