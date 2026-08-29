#!/usr/bin/env python3
"""Check that the suppression register and the source agree about what is silenced.

A register nobody is held to becomes decoration in exactly the way a
requirements document does, and the drift is invisible because nothing compares
the two. This project's register was once found naming two files that had moved
months of commits earlier, listing a gosec rule that does not exist, and missing
three pragmas entirely, while carrying a line saying it had been verified by
hand. Checking it by hand is what failed.

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

A ROW IS ONE PRAGMA'S CODE SET, NOT A FILE'S. `×2  #nosec B404, B603` says the
file carries two pragmas, each silencing both codes. Two pragmas of one code
each are two rows:

    src/app.py   #nosec B404
    src/app.py   #nosec B603

Both readings are defensible and the example above does not distinguish them, so
this says which one the checker uses. Raised by wrench, who wrote the first and
meant the second.

PATHS IN A ROW ARE RELATIVE TO THE REPOSITORY, found by walking up for `.git`,
and never to the register's own directory or to the directory being scanned.
That is what lets ONE register serve a repository whose packs are checked at
their own bases: a scan at `python/` and a row saying `python/tests/x.py` both
resolve to the same absolute path.

    UPGRADING FROM A VERSION THAT KEYED ON THE SCAN ROOT HAS TWO STEPS.

An adopter that worked around the old behaviour has the register itself to put
back into the repository frame, AND any wrapper that rewrote rows between frames
before calling this. With both sides resolved, such a translation doubles the
prefix, and the symptom is the ROOT spelling failing a root-based run after the
upgrade. Reported by wrench, who hit exactly that and had two things to undo.

Exiting 0 is this task's contract, which is why it prints its findings rather
than returning an envelope: bolt's configuration never says what success means,
and a tool whose exit code genuinely is the answer needs no adapter.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from collections.abc import Iterator
from pathlib import Path

# EVERY SPELLING THAT SILENCES A CHECKER, in the languages this estate writes.
#
# ONE TABLE, READ BY BOTH SIDES. The source scan and the register scan run the
# same patterns, so "what counts as a pragma" cannot mean two different things
# in one program. The previous version spelled it twice, once for each side,
# and the two were free to drift; a drift there is a silent pass, because a
# pragma the source scan sees and the register scan cannot parse reads as
# unregistered forever.
#
# WHY ALL OF THEM AND NOT ONLY THE SECURITY ONES. Decided 2026-08-28. Hard rule
# 4 says never insert a suppression pragma without asking first, and a noqa is
# one. A rule covering nosec and not noqa would be enforced against whichever
# tool the author happened to be silencing.
#
# Each pattern captures its rule ids in `rules`, which may be empty: a bare
# directive naming no ids silences everything and names nothing, and that is
# worth registering more than a narrow one, not less.
#
# THE SPELLINGS ARE NAMED WITHOUT THEIR LEADING HASH IN THIS COMMENT. Written
# in full, ruff reads the prose as a malformed suppression directive and warns,
# which is this file's own subject arriving one level out: a mention of a
# pragma taken for one, by a different tool, in the file that exists to tell
# the two apart.
SPELLINGS = (
    ("nosec", r"#\s*nosec\b[:=]?[ \t]*(?P<rules>[A-Z]+\d+(?:[ \t,]+[A-Z]+\d+)*)?"),
    ("nolint", r"//\s*nolint:(?P<rules>[\w,]+)"),
    ("noqa", r"#\s*noqa\b(?::[ \t]*(?P<rules>[\w][\w, \t]*?))?[ \t]*(?=$|#)"),
    ("type-ignore", r"#\s*type:[ \t]*ignore(?:\[(?P<rules>[^\]]+)\])?"),
    ("pylint", r"#\s*pylint:[ \t]*disable=(?P<rules>[\w,\- \t]+)"),
    ("shellcheck", r"#\s*shellcheck\s+disable=(?P<rules>SC\d+(?:[ \t,]+SC\d+)*)"),
    ("allow", r"#!?\[allow\((?P<rules>[^)]+)\)\]"),
    ("rubocop", r"#\s*rubocop:disable\s+(?P<rules>[\w/,\- \t]+)"),
)

PRAGMAS = tuple((kind, re.compile(pattern)) for kind, pattern in SPELLINGS)

# In the register: an indented row naming a file, an optional count, and then
# the pragma it carries, which is read with the SAME patterns as the source.
# Anything after the rule ids is prose and is ignored.
INDEX_ROW = re.compile(r"^\s{2,}(?P<path>\S+)\s+(?:×(?P<count>\d+)\s+)?(?P<pragma>.+)$")


def rules_of(found: re.Match) -> frozenset[str]:
    """The rule ids one pragma names, however it spells them."""
    text = found.groupdict().get("rules") or ""
    return frozenset(part for part in re.split(r"[\s,]+", text.strip()) if part)


def in_a_string(line: str, column: int) -> bool:
    """Whether a position on a line sits inside a quoted string.

    A PRAGMA IS IN A COMMENT. THIS IS THE TOOL SAYING IT IS NOT A USE OF THE
    TOOL. Without it this checker fails on its own source, because the table
    above quotes every spelling it hunts for, and on its own tests, whose
    fixtures are pragmas by construction. Measured 2026-08-28 before the guard:
    28 findings in toolbox, 22 in `tests/test_suppression_register.py` and 6
    here, and not one of them a suppression of anything.

    That is the shape wrench filed as `a-project-cannot-test-its-own-tooling`,
    and the answer here is a property of the text rather than a list of
    exempted filenames: a filename list would have to name every adopter's
    copy, and would exempt a real pragma written in the same file.

    A single-line scanner and not a parser. It is right for the case that
    matters, a pragma spelling inside a string literal, and it knows nothing of
    a string spanning lines; `code_lines` handles the triple-quoted case
    separately, and neither knows about an implicit continuation.
    """
    return _scan(line, column)[0] is not None


def _scan(line: str, stop: int) -> tuple[str | None, int]:
    """Walk a line to `stop`, returning the open quote and the comment opener.

    TRACKS THE DELIMITER, NOT THE PARITY. Counting quotes was measured wrong on
    a real line: a test fixture spelling `'\"\"\"prose\"\"\"'` has four quotes
    before its `#`, an even count, so parity called it code and the checker
    matched its own fixture. Remembering WHICH quote opened the string gets it
    right, and it is the same amount of work.
    """
    delim: str | None = None
    opener = -1
    index = 0
    while index < min(stop, len(line)):
        char = line[index]
        if char == "\\":
            index += 2
            continue
        if delim is not None:
            if char == delim:
                delim = None
        elif char in "\"'":
            delim = char
        elif opener < 0 and (char == "#" or line.startswith("//", index)):
            opener = index
        index += 1
    return delim, opener


def comment_opens_at(line: str) -> int:
    """Where the line's comment or attribute begins, or -1.

    `#` for Python, shell and Ruby, `//` for Go and Rust, and `#[` for a Rust
    attribute, which is not a comment but sits in the same position and is the
    same kind of declaration. The first one outside a string wins, so a `#`
    inside a quoted string does not open a comment.
    """
    return _scan(line, len(line))[1]


def pragma_may_start_at(line: str, opens_at: int) -> frozenset[int]:
    """The positions on a line where a real pragma may begin.

    THE COMMENT OPENER, OR THE FIRST THING INSIDE IT. Requiring the opener
    alone was measured wrong: palette-print writes `// #nosec G304 -- reason`,
    where the marker is `//` and the pragma starts three characters later, and
    three genuine Go suppressions went silently unseen. A false negative here
    is the one direction that matters, since it turns a gate green.

    Prose about a pragma is still excluded, because it mentions the spelling
    mid-sentence rather than at either position.
    """
    if opens_at < 0 or in_a_string(line, opens_at):
        return frozenset()
    marker = 2 if line.startswith("//", opens_at) else 1
    body = opens_at + marker
    while body < len(line) and line[body] in " \t":
        body += 1
    return frozenset({opens_at, body})


def code_lines(text: str) -> Iterator[str]:
    """Every line outside a triple-quoted block.

    A TRIPLE-QUOTED BLOCK IS PROSE, and prose about pragmas is where a
    checker's own documentation lives. This file's module docstring shows two
    example register rows; without this they count as suppressions of toolbox's
    own, which is the tool graded as a use of itself, one level up from the
    string-literal case `in_a_string` handles.

    Separated from `pragmas_in` because keeping it there put that function at
    cognitive complexity 18 against the jig's limit of 15. Walking the text and
    matching against it are two jobs.
    """
    fence = None
    for line in text.splitlines():
        if fence:
            if fence in line:
                fence = None
            continue
        opener = re.search(r'"""|\'\'\'', line)
        if opener and line.count(opener.group()) == 1:
            fence = opener.group()
            continue
        yield line


def pragmas_in(text: str) -> list[tuple[str, frozenset[str]]]:
    """Every pragma in a blob of text, as (kind, rules) pairs.

    The kind is carried because two spellings can name the same id and mean
    different things: `# noqa: E501` and `# pylint: disable=E501` are not one
    suppression written twice.
    """
    found = []
    for line in code_lines(text):
        starts = pragma_may_start_at(line, comment_opens_at(line))
        for kind, pattern in PRAGMAS:
            for match in pattern.finditer(line):
                # A PRAGMA STARTS THE COMMENT IT IS IN. Prose ABOUT a pragma
                # mentions it mid-sentence, and a pragma IS a comment, so no
                # rule about strings can separate them. The one that does is
                # position: a trailing `noqa: E402` comment starts at the
                # opener, where a sentence mentioning one mid-clause does not.
                #
                # The spellings are named without their `#` here ON PURPOSE.
                # Written in full, ruff reads this comment as a malformed
                # suppression directive and warns, which is this function's own
                # subject arriving one level out: prose about a pragma being
                # taken for one, by a different tool, in the file that exists to
                # tell them apart.
                #
                # This is the answer to `shared-checkers/20` question 4, and it
                # is a property of the text rather than a list of exempt
                # filenames, so it holds in every adopter and for a real pragma
                # written in this file.
                if match.start() in starts:
                    found.append((kind, rules_of(match)))
    return found


# Directories holding code this project is not answerable for. A vendored
# dependency carrying `//nolint` would otherwise be reported as an unregistered
# pragma, failing the project that vendored it for somebody else's decision, and
# a scratch file in `.ephemera` would do the same for a file that is not part of
# the project at all.
#
# KEPT IN STEP WITH `test-traceability.py` BY A TEST, because the two checkers
# are loaded by path and share no module, so this list is a second copy free to
# drift from the first.
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
        "target",
    }
)


SUFFIXES = frozenset({".go", ".py", ".sh", ".bash", ".zsh", ".rs", ".rb"})


def is_source(path: Path) -> bool:
    """Whether a file is source this checker should read.

    BY SUFFIX, AND THEN BY SHEBANG. Selecting on the extension alone is the
    defect this checker exists beside: `silo/bin/statusline` is a shell script
    with no suffix, and `dotfiles/home/.git-hooks/no-ai-attribution` is 170
    lines of bash enforcing a hard rule, both invisible to any extension match.
    A file with no suffix whose first line is a shebang is source.

    RESOLVED, NOT TESTED FOR A LINK. Adoption puts symlinks to this
    repository's own checkers in every adopter's `bin/`, and this file quotes
    the pragma spellings it hunts for, so an adopter reading it would be failed
    for toolbox's patterns. `is_symlink()` answers only for the last component,
    so a file reached through a symlinked PARENT reports False; comparing
    resolved parents catches both.
    """
    if not path.is_file() or not SKIP_DIRS.isdisjoint(path.parts):
        return False
    if path.resolve().parent != path.parent.resolve():
        return False
    if path.suffix in SUFFIXES:
        return True
    if path.suffix:
        return False
    try:
        with path.open("rb") as handle:
            return handle.read(2) == b"#!"
    except OSError:
        return False


def scan_source(root: Path) -> tuple[Counter[tuple[Path, str, frozenset[str]]], int]:
    """Count the pragmas in the tree, and how many files were read.

    THE FILE COUNT IS RETURNED BECAUSE A ZERO IS NOT A PASS. "No pragmas
    found" and "no pragmas exist" are different results, and this checker
    conflated them: reading `*.go` only, it reported `no suppression pragmas
    anywhere` over a Python tree holding five registered ones and exited 0.
    A reader takes that as a clean bill. Callers can now tell the two apart.
    """
    found: Counter[tuple[Path, str, frozenset[str]]] = Counter()
    read = 0
    for path in sorted(p for p in root.rglob("*") if is_source(p)):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        read += 1
        # RESOLVED, NOT RELATIVE TO THE SCAN ROOT. The register is one document
        # at the repository root and the shared jig runs at each pack's base, so
        # the two speak different frames: a scan at `python/` calls a file
        # `tests/x.py` where the register at the root calls it
        # `python/tests/x.py`. Both spellings are correct and they are not the
        # same string, so comparing them as strings makes one of the two wrong
        # and there is no spelling a two-base repository can choose.
        #
        # Both sides resolve to an absolute path, and the frame question stops
        # existing. Filed by wrench, who declined a task over it.
        key = path.resolve()
        for kind, rules in pragmas_in(text):
            found[(key, kind, rules)] += 1
    return found, read


def register_documents(path: Path) -> list[Path]:
    """The documents a `--register` path names: one file, or a tree of them.

    The same split `--requirements` takes, for the same reason: one file per
    suppression means adding one creates a file instead of reopening a shared
    document, and two sessions do not collide in it.
    """
    if path.is_dir():
        return sorted(p for p in path.rglob("*.md") if p.is_file())
    return [path]


def repository_of(document: Path, fallback: Path) -> Path:
    """The repository a register document sits in, or the fallback frame.

    Walking up for `.git` finds the frame register rows are written in. It is
    what a person means by a path in that document: skid's register is at
    `docs/SUPPRESSIONS.md` and names `src/skid/install.py`, which is relative to
    the repository and not to `docs/`, so resolving against the document's own
    directory would break an adopter that works today.

    THE FALLBACK IS THE SCAN ROOT, which is what this checker always used, so a
    register outside any repository behaves exactly as it did before the frame
    existed. A fixture in a scratch directory is that case.
    """
    here = document.resolve().parent
    for candidate in (here, *here.parents):
        if (candidate / ".git").exists():
            return candidate
    return fallback.resolve()


def scan_register(path: Path, root: Path) -> Counter[tuple[Path, str, frozenset[str]]]:
    """Read the register's index into the same shape as the source scan.

    Counts add across documents, so one file per suppression totals the same as
    one document listing them all, and a file carrying `×2` still says two.

    A ROW'S PATH IS RESOLVED AGAINST THE REPOSITORY, not against the document
    and not against the scan root. That is the frame people actually write in,
    measured rather than assumed: skid's register sits at `docs/SUPPRESSIONS.md`
    and names `src/skid/install.py`, so resolving against the document's own
    directory would look for `docs/src/skid/install.py` and break an adopter
    that works today.

    Both sides of the comparison are then absolute and the scan root stops
    mattering, which is what lets one register serve two bases.
    """
    listed: Counter[tuple[Path, str, frozenset[str]]] = Counter()
    if not path.exists():
        return listed
    for document in register_documents(path):
        base = repository_of(document, root)
        for line in document.read_text(encoding="utf-8").splitlines():
            row = INDEX_ROW.match(line)
            if not row:
                continue
            # The row's pragma is read with the SAME patterns as the source, so
            # a spelling the source can see is always one the register can
            # express. A row naming no recognised pragma is prose.
            for kind, rules in pragmas_in(row.group("pragma")):
                count = int(row.group("count") or 1)
                where = (base / row.group("path")).resolve()
                listed[(where, kind, rules)] += count
    return listed


def describe(key: tuple[Path, str, frozenset[str]], frame: Path) -> str:
    """Name one entry in the frame a reader of the register would use."""
    where, kind, rules = key
    try:
        shown = where.relative_to(frame).as_posix()
    except ValueError:
        shown = str(where)
    named = " ".join(sorted(rules)) if rules else "everything"
    return f"{shown} ({kind}: {named})"


def compare(
    source: Counter[tuple[Path, str, frozenset[str]]],
    register: Counter[tuple[Path, str, frozenset[str]]],
    root: Path,
    frame: Path,
) -> list[str]:
    """Every way the two can disagree, said in the register's own terms.

    A REGISTER ROW OUTSIDE THE SCAN ROOT BELONGS TO ANOTHER SCAN. Resolving both
    sides is necessary and not sufficient: one register serving two bases is
    read whole by each scan, so every row for the other base would report as a
    pragma that has gone. Those are held to existing rather than to being found,
    which is the half of the phantom check that still means something here.

    A row naming a file that exists nowhere is still a phantom and still fails,
    whichever base it sits in, because nothing else would ever catch it.
    """
    failures = []
    for key in sorted(set(source) | set(register), key=lambda k: (str(k[0]), k[1])):
        where = key[0]
        if where not in source and not where.is_relative_to(root):
            if not where.exists():
                failures.append(
                    f"{describe(key, frame)} ×{register[key]} names a file that does "
                    "not exist; the register points at nothing"
                )
            continue
        here, there = source[key], register[key]
        if there == 0:
            failures.append(
                f"{describe(key, frame)} ×{here} is in the source and in no register "
                "entry; ask before it stays, then register it, or remove it"
            )
        elif here == 0:
            failures.append(
                f"{describe(key, frame)} ×{there} is registered and is not in the "
                "source; the pragma moved or went, and the register did not follow"
            )
        elif here != there:
            failures.append(
                f"{describe(key, frame)}: the source carries {here}, "
                f"the register says {there}"
            )
    return failures


def report(failures: list[str], total: int, files: int, register: Path) -> int:
    """Print the findings and return the exit status."""
    if failures:
        print(f"{len(failures)} disagreement(s) between the source and {register}:")
        for failure in failures:
            print(f"  {failure}")
        return 1
    if total == 0:
        print(f"no suppression pragmas in {files} source file(s), and none registered")
        return 0
    print(
        f"every suppression is registered, and every entry is real "
        f"({total} pragma(s) across {files} source file(s))"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--register", required=True, type=Path)
    parser.add_argument("root", type=Path, nargs="?", default=Path("."))
    args = parser.parse_args()

    source, files = scan_source(args.root)

    # A CHECKER THAT READ NOTHING HAS NOT PASSED. Reading no files at all is
    # indistinguishable, in the old output, from reading the whole tree and
    # finding it clean, and the second is what a reader takes it for. Measured
    # 2026-08-28: over skid, which is Python, this printed `no suppression
    # pragmas anywhere` and exited 0 while five registered pragmas sat in the
    # source. It is a failure rather than a warning because a task that cannot
    # fail is worse than an absent one, which is this repository's own decision.
    if files == 0:
        print(
            f"no source files found under {args.root}; "
            "this checker read nothing and cannot report on what it did not read"
        )
        return 1

    # Unreadable is not absent. A register that exists and cannot be opened
    # would otherwise raise, and a traceback from a gate task reads as a broken
    # checker rather than as a permission the adopter can fix.
    try:
        register = scan_register(args.register, args.root)
    except OSError as unreadable:
        print(f"{args.register} cannot be read: {unreadable.strerror}")
        return 1

    if not args.register.exists() and source:
        print(f"{sum(source.values())} pragma(s) in the source and no {args.register}")
        return 1

    # Findings are reported in the register's own frame, so a person reads a
    # path they can check by hand against the document they are holding.
    frame = repository_of(args.register, args.root)
    failures = compare(source, register, args.root.resolve(), frame)
    return report(failures, sum(source.values()), files, args.register)


if __name__ == "__main__":
    sys.exit(main())
