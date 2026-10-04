#!/usr/bin/env python3
"""Check that the suppression register and the source agree about what is silenced.

A register nobody is held to drifts from the source, and nothing else compares
the two.

Every `#nosec` or `//nolint` in the source must appear in the register's index,
and every row of that index must correspond to a pragma that is really there.
An unregistered pragma is a suppression nobody justified, and a registered row
with nothing behind it justifies something that has gone.

The index is the indented block at the end of the register, one row per file:

    internal/artifact/artifact.go   #nosec G304
    internal/cli/cli.go        ×2   #nosec G304

`×N` says how many pragmas that file carries; absent means one. The count is
part of the comparison, so a second suppression added to an already-registered
file is caught instead of hidden behind the first.

A row is one pragma's code set, not a file's. `×2  #nosec B404, B603` says the
file carries two pragmas, each silencing both codes. Two pragmas of one code
each are two rows:

    src/app.py   #nosec B404
    src/app.py   #nosec B603

The example above could be read either way; the checker reads it as two
pragmas, each with both codes.

Paths in a row are relative to the repository, found by walking up for `.git`,
and never to the register's own directory or to the directory being scanned.
That is what lets one register serve a repository whose packs are checked at
their own bases: a scan at `python/` and a row saying `python/tests/x.py` both
resolve to the same absolute path.

A register's rows are written in the repository frame. A wrapper that rewrites
rows between frames before calling this doubles the prefix, and the root
spelling then fails a root-based run.

Exiting 0 is this task's contract, which is why it prints its findings instead
of returning an envelope: bolt's configuration never says what success means,
and a tool whose exit code genuinely is the answer needs no adapter.
"""

# pylint: disable=duplicate-code
#
# Every script in `bin/` and `adapters/` is spawned by path from a directory that
# is not a package, so none can import another and shared code is written twice.
# Registered as S-3 in SUPPRESSIONS, with what would retire it.

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from collections.abc import Iterator
from pathlib import Path

# Every spelling that silences a checker, in the languages this estate writes.
#
# One table, read by both sides. The source scan and the register scan run the
# same patterns, so "what counts as a pragma" cannot mean two different things
# in one program. Spelled once per side, the two would be free to drift, and a
# drift there is a silent pass: a pragma the source scan sees and the register
# scan cannot parse reads as unregistered forever.
#
# All of them are covered, not only the security ones. Hard rule 4 says never
# insert a suppression pragma without asking first, and a noqa is one. A rule
# covering nosec and not noqa would be enforced against whichever tool the
# author happened to be silencing.
#
# Each pattern captures its rule ids in `rules`, which may be empty: a bare
# directive naming no ids silences everything and names nothing, so it needs
# registering more than a narrow one, not less.
#
# The spellings are named without their leading hash in this comment. Written
# in full, ruff reads the prose as a malformed suppression directive and warns:
# a mention of a pragma taken for one, by a different tool, in the file that
# exists to tell the two apart.
SPELLINGS = (
    # A bare spelling naming no codes must end the line. `# nosec` alone is a
    # real pragma; `#  nosec marks in one file they do not own.` is a sentence
    # that begins with the word. Both open their comment, so position cannot
    # separate them and the trailing text is what does.
    #
    # Requiring code before the comment instead would miss palette-print's
    # pragmas, which sit on their own line above the statement.
    (
        "nosec",
        r"#\s*nosec\b[:=]?[ \t]*(?:(?P<rules>[A-Z]+\d+(?:[ \t,]+[A-Z]+\d+)*)|[ \t]*$)",
    ),
    ("nolint", r"//\s*nolint:(?P<rules>[\w,]+)"),
    # The codes end the pragma, and prose may follow. Running the rule list to
    # end-of-line means a noqa directive followed by a dash and a reason matches
    # nothing at all and the pragma is invisible. A false negative here turns a
    # gate green. Spelled without the leading hash for the reason the table's
    # own note gives.
    (
        "noqa",
        r"#\s*noqa\b(?::[ \t]*(?P<rules>[A-Z]+\d+(?:[ \t,]+[A-Z]+\d+)*)|[ \t]*$)",
    ),
    ("type-ignore", r"#\s*type:[ \t]*ignore(?:\[(?P<rules>[^\]]+)\])?"),
    ("pylint", r"#\s*pylint:[ \t]*disable=(?P<rules>[\w,\- \t]+)"),
    ("shellcheck", r"#\s*shellcheck\s+disable=(?P<rules>SC\d+(?:[ \t,]+SC\d+)*)"),
    ("allow", r"#!?\[allow\((?P<rules>[^)]+)\)\]"),
    ("rubocop", r"#\s*rubocop:disable\s+(?P<rules>[\w/,\- \t]+)"),
    # eslint's line, next-line and block forms. A rule starts with a letter or
    # `@`, so the `-- reason` eslint allows after the list is not read as one.
    (
        "eslint",
        (
            r"(?://|/\*)\s*eslint-disable(?:-next-line|-line)?"
            r"(?:[ \t]+(?P<rules>[@\w][@\w/\-]*(?:[ \t]*,[ \t]*[@\w][@\w/\-]*)*))?"
        ),
    ),
    ("deno-lint", r"//\s*deno-lint-ignore(?:-file)?(?:[ \t]+(?P<rules>[\w\-]+(?:[ \t]+[\w\-]+)*))?"),
    # TypeScript's own directives name no rule; the directive is the rule.
    ("ts", r"//\s*@ts-(?P<rules>ignore|expect-error|nocheck)\b"),
    # detect-secrets' allowlist, in either comment syntax.
    ("detect-secrets", r"(?:#|//)\s*pragma:[ \t]*allowlist(?:[ \t]+nextline)?[ \t]+secret\b"),
)

PRAGMAS = tuple((kind, re.compile(pattern)) for kind, pattern in SPELLINGS)

# In the register: an indented row naming a file, an optional count, and then
# the pragma it carries, which is read with the same patterns as the source.
# Anything after the rule ids is prose and is ignored.
INDEX_ROW = re.compile(r"^\s{2,}(?P<path>\S+)\s+(?:×(?P<count>\d+)\s+)?(?P<pragma>.+)$")


def rules_of(found: re.Match) -> frozenset[str]:
    """The rule ids one pragma names, however it spells them."""
    text = found.groupdict().get("rules") or ""
    return frozenset(part for part in re.split(r"[\s,]+", text.strip()) if part)


def in_a_string(line: str, column: int) -> bool:
    """Whether a position on a line sits inside a quoted string.

    A pragma is in a comment, so a spelling inside a string is the tool talking
    about a pragma and not using one. Without this check the checker fails on
    its own source, because the table above quotes every spelling it hunts for,
    and on its own tests, whose fixtures are pragmas by construction.

    The test is a property of the text. A list of exempted filenames would have
    to name every adopter's copy, and would exempt a real pragma written in the
    same file.

    A single-line scanner and not a parser. It is right for the case that
    matters, a pragma spelling inside a string literal, and it knows nothing of
    a string spanning lines; `code_lines` handles the triple-quoted case
    separately, and neither knows about an implicit continuation.
    """
    return _scan(line, column)[0] is not None


def _scan(line: str, stop: int, hashes: bool = True) -> tuple[str | None, int]:
    """Walk a line to `stop`, returning the open quote and the comment opener.

    Tracks the delimiter, not the parity. A test fixture spelling
    `'\"\"\"prose\"\"\"'` has four quotes before its `#`, an even count, so
    counting quotes would call it code. Remembering which quote opened the
    string reads it correctly.

    `hashes` is False for TypeScript and JavaScript, where `#` opens no comment
    and a `#private` field before a `//` would otherwise hide the pragma after it.
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
        elif opener < 0 and ((hashes and char == "#") or line.startswith(("//", "/*"), index)):
            opener = index
        index += 1
    return delim, opener


def comment_opens_at(line: str, hashes: bool = True) -> int:
    """Where the line's comment or attribute begins, or -1.

    `#` for Python, shell and Ruby, `//` for Go, Rust and TypeScript, `/*` for a
    block comment, and `#[` for a Rust attribute, which is not a comment but sits
    in the same position and is the same kind of declaration. The first one
    outside a string wins, so a `#` inside a quoted string does not open a
    comment.
    """
    return _scan(line, len(line), hashes)[1]


def pragma_may_start_at(line: str, opens_at: int) -> frozenset[int]:
    """The positions on a line where a real pragma may begin.

    The comment opener, or the first thing inside it. palette-print writes
    `// #nosec G304 -- reason`, where the marker is `//` and the pragma starts
    three characters later, and requiring the opener alone would miss it and
    pass the gate.

    Prose about a pragma is still excluded, because it mentions the spelling
    mid-sentence and not at either position.
    """
    if opens_at < 0 or in_a_string(line, opens_at):
        return frozenset()
    marker = 2 if line.startswith(("//", "/*"), opens_at) else 1
    body = opens_at + marker
    while body < len(line) and line[body] in " \t":
        body += 1
    return frozenset({opens_at, body})


def code_lines(text: str) -> Iterator[str]:
    """Every line outside a triple-quoted block.

    A triple-quoted block is prose, and prose about pragmas is where a
    checker's own documentation lives. This file's module docstring shows two
    example register rows; without this they count as suppressions of toolbox's
    own, which is the tool graded as a use of itself, one level up from the
    string-literal case `in_a_string` handles.

    Kept apart from `pragmas_in` because walking the text and matching against
    it are two jobs, and together they exceed the cognitive-complexity limit of
    15.
    """
    fence = None
    for line in text.splitlines():
        if fence:
            if fence in line:
                fence = None
            continue
        opener = re.search(r'"""|\'\'\'', line)
        # A triple quote inside a string literal does not open a docstring. The
        # line above spells both delimiters inside a raw string; counted as a
        # fence, it would toggle the state and read every later docstring in
        # this file as code.
        if opener and not in_a_string(line, opener.start()) and line.count(opener.group()) == 1:
            fence = opener.group()
            continue
        yield line


def pragmas_in(text: str, hashes: bool = True) -> list[tuple[str, frozenset[str]]]:
    """Every pragma in a blob of text, as (kind, rules) pairs.

    The kind is carried because two spellings can name the same id and mean
    different things: `# noqa: E501` and `# pylint: disable=E501` are not one
    suppression written twice.
    """
    found = []
    for line in code_lines(text):
        starts = pragma_may_start_at(line, comment_opens_at(line, hashes))
        for kind, pattern in PRAGMAS:
            for match in pattern.finditer(line):
                # A pragma starts the comment it is in. Prose about a pragma
                # mentions it mid-sentence, and a pragma is itself a comment, so
                # no rule about strings can separate them. The one that does is
                # position: a trailing `noqa: E402` comment starts at the
                # opener, where a sentence mentioning one mid-clause does not.
                #
                # The spellings are named without their `#` here on purpose.
                # Written in full, ruff reads this comment as a malformed
                # suppression directive and warns: prose about a pragma taken
                # for one, by a different tool, in the file that exists to tell
                # them apart.
                #
                # Position is a property of the text and not a list of exempt
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
# A test keeps this in step with `test-traceability.py`, because the two checkers
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
        # Agent worktrees live under `.claude/worktrees/`, each a checkout of
        # this same repository, so every pragma would reappear at a second path.
        ".claude",
    }
)


# TypeScript and JavaScript, where `#` opens no comment.
SCRIPT_SUFFIXES = frozenset({".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs"})
SUFFIXES = frozenset({".go", ".py", ".sh", ".bash", ".zsh", ".rs", ".rb"}) | SCRIPT_SUFFIXES


def in_a_nested_checkout(path: Path, root: Path) -> bool:
    """Whether a directory between the scan root and the file holds its own `.git`.

    A nested checkout is another repository, answerable to its own register,
    whether it is a vendored clone or an agent's worktree of this one.
    """
    top = root.resolve()
    for parent in path.resolve().parents:
        if parent == top or top not in parent.parents:
            return False
        if (parent / ".git").exists():
            return True
    return False


def is_source(path: Path) -> bool:
    """Whether a file is source this checker should read.

    By suffix, and then by shebang. A shell script with no suffix, such as a
    statusline or a git hook, is invisible to an extension match, so a file
    with no suffix whose first line is a shebang is source.

    Resolved, not tested for a link. Adoption puts symlinks to this
    repository's own checkers in every adopter's `bin/`, and this file quotes
    the pragma spellings it hunts for, so an adopter reading it would be failed
    for toolbox's patterns. `is_symlink()` answers only for the last component,
    so a file reached through a symlinked parent reports False; comparing
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

    The file count is returned because a zero is not a pass. A scan that read
    no files finds no pragmas just as a clean tree does, and the count lets
    callers tell the two apart.
    """
    found: Counter[tuple[Path, str, frozenset[str]]] = Counter()
    read = 0
    for path in sorted(p for p in root.rglob("*") if is_source(p) and not in_a_nested_checkout(p, root)):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        read += 1
        # Resolved, not relative to the scan root. The register is one document
        # at the repository root and the shared jig runs at each pack's base, so
        # the two speak different frames: a scan at `python/` calls a file
        # `tests/x.py` where the register at the root calls it
        # `python/tests/x.py`. Both spellings are correct and they are not the
        # same string, so comparing them as strings makes one of the two wrong
        # and there is no spelling a two-base repository can choose.
        #
        # Both sides resolve to an absolute path, so the frames agree.
        key = path.resolve()
        for kind, rules in pragmas_in(text, hashes=path.suffix not in SCRIPT_SUFFIXES):
            found[(key, kind, rules)] += 1
    return found, read


def register_documents(path: Path) -> list[Path]:
    """The documents a `--register` path names: one file, or a tree of them.

    The same split `--requirements` takes, for the same reason: one file per
    suppression means adding one creates a file instead of reopening a shared
    document, and two people working at once do not collide in it.
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

    The fallback is the scan root, the frame for a register outside any
    repository, such as a fixture in a scratch directory.
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

    A row's path is resolved against the repository, not against the document
    and not against the scan root; `repository_of` says why. Both sides of the comparison are then absolute and the scan root stops
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
            # The row's pragma is read with the same patterns as the source, so
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

    A register row outside the scan root belongs to another scan. Resolving both
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
                failures.append(f"{describe(key, frame)} ×{register[key]} names a file that does not exist; the register points at nothing")
            continue
        here, there = source[key], register[key]
        if there == 0:
            failures.append(
                f"{describe(key, frame)} ×{here} is in the source and in no register entry; ask before it stays, then register it, or remove it"
            )
        elif here == 0:
            failures.append(
                f"{describe(key, frame)} ×{there} is registered and is not in the source; the pragma moved or went, and the register did not follow"
            )
        elif here != there:
            failures.append(f"{describe(key, frame)}: the source carries {here}, the register says {there}")
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
    print(f"every suppression is registered, and every entry is real ({total} pragma(s) across {files} source file(s))")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--register", required=True, type=Path)
    parser.add_argument("root", type=Path, nargs="?", default=Path("."))
    args = parser.parse_args()

    source, files = scan_source(args.root)

    # A checker that read nothing has not passed, so reading no files at all
    # fails. A warning would leave a task that cannot fail, which
    # `docs/DECISIONS/a-task-that-cannot-fail-leaves-the-jig.md` rules out.
    if files == 0:
        print(f"no source files found under {args.root}; this checker read nothing and cannot report on what it did not read")
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
