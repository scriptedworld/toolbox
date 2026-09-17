#!/usr/bin/env python3
"""Fail on the wording the writing standard names, wherever it appears.

    voice-tells.py [FILE...]                  the named files, or the staged ones
    voice-tells.py --all-files                every file, and the commits after the start
    voice-tells.py --from-ref A --to-ref B    what changed between two refs
    voice-tells.py --commit-msg-filename F    one commit message

Reads a project's documentation (`.md`), the comments and Python docstrings in
its source and configuration, and commit messages. The modes are pre-commit's,
so the same script serves a hook and the jig. With no files named and no mode,
the staged copies are read, which is what a commit would carry.

Every instance of a rule below is printed as `where:line: rule: text`. Exits 0
when no error was found, 1 when one was, and 2 when the command or the
repository is wrong, such as a start file naming something that is not a commit.

No model and no network: the same tree gives the same answer on every run, which
is what lets it gate at zero.

A project adopts with nothing accepted. `.voice-baseline.json` holds the
exceptions, each written by hand with the reason it stands, the way
`SUPPRESSIONS` holds a pragma. Nothing here writes entries.

Text a document is reporting rather than asserting is not read: fenced and
indented code, block quotes, `inline code` and quoted spans. The exempt
paths are the voice review's, so both checks read the same project.
"""

from __future__ import annotations

import argparse
import ast
import io
import json
import re
import shutil
import subprocess
import sys
import tokenize
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

DOCS, COMMENTS, COMMITS = "docs", "comments", "commits"
EVERYWHERE = frozenset({DOCS, COMMENTS, COMMITS})

SKIPPED_FILES = frozenset(["CLAUDE.md", "AGENTS.md", "START_HERE.md", "SKILL.md"])
SKIPPED_DIRS = frozenset(["node_modules", "vendor", "venv", "__pycache__", "testdata", "site-packages", "target", "skills", "prompts"])

HASH_SUFFIXES = frozenset([".py", ".sh", ".bash", ".zsh", ".yaml", ".yml", ".toml", ".just", ".pl", ".r"])
HASH_FILES = frozenset(["Justfile", "justfile", "Makefile", "Dockerfile"])
SLASH_SUFFIXES = frozenset(
    [".go", ".rs", ".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".js", ".jsx", ".ts", ".tsx", ".java", ".kt", ".swift", ".cs", ".php", ".scala"]
)

# Comment lines a program reads rather than a person.
DIRECTIVE = re.compile(r"COVERS:|^#!|-\*-|noqa|nosec|nolint|pylint:|type:\s*ignore|go:build|go:generate|eslint-|clippy::|rustfmt::|fmt:\s*(off|on)")
FENCE = re.compile(r"^\s*(```|~~~)")
# Single quotes count only standing apart from letters, so `don't` and `the file's` are not spans.
QUOTED = re.compile(r"`[^`\n]*`|\"[^\"\n]*\"|“[^”\n]*”|(?<![A-Za-z])'[^'\n]*'(?![A-Za-z])")
RATHER_THAN = re.compile(r"\brather than\b", re.IGNORECASE)

RATHER_THAN_PER_TEXT = 2
BOLD_SHARE = 0.3
BOLD_MIN_PARAGRAPHS = 6
COMMIT_BODY_LINES = 20


@dataclass(frozen=True)
class Syntax:
    """How one kind of file writes a comment and a string."""

    line: tuple[str, ...]
    block: tuple[tuple[str, str], ...] = ()
    strings: tuple[str, ...] = ('"', "'")
    # Ruby's `=begin` opens a block only as the whole of a line's start, where
    # `/*` and `--[[` open one anywhere.
    anchored: bool = False


@dataclass(frozen=True)
class Rule:
    """One pattern, the kinds of text it reads, and its name in the output."""

    name: str
    pattern: re.Pattern[str]
    reads: frozenset[str] = EVERYWHERE


def rule(name: str, pattern: str, *, ignore_case: bool = False, reads: frozenset[str] = EVERYWHERE) -> Rule:
    """A rule compiled once."""
    return Rule(name, re.compile(pattern, re.IGNORECASE if ignore_case else 0), reads)


# A finding at `error` fails the run. A `suggestion` is printed and never fails.
ERROR, SUGGESTION = "error", "suggestion"
PROSE_AND_COMMITS = frozenset({COMMENTS, COMMITS})
COMMENT_OPENER = r"^(?:#+|//+|/\*+|\*+)?\s*"


LINE_RULES = (
    rule("em-dash", "—"),
    rule("ascii-dash", r"(?<=[A-Za-z).,'`])\s--\s(?=[A-Za-z(`'])"),
    rule(
        "badge",
        r"\*\*\*?(FACT|CLAIM|PREFERENCE)\b|\b(FACT|CLAIM|PREFERENCE)\s+\d{4}-\d{2}-\d{2}"
        r"|^\s*(FACT|CLAIM|PREFERENCE)\s*:|\b(UNVERIFIED|MEASURED THIS SESSION)\b",
    ),
    rule(
        "audit-date",
        r"\b(checked|measured|re-?measured|verified|confirmed|re-?tested|decided|corrected|re-?derived|held|observed)\b[^.\n]{0,24}?\b\d{4}-\d{2}-\d{2}\b",
        ignore_case=True,
    ),
    rule("audit-marker", r"\b(DECIDED|CORRECTED|RETESTED|SUPERSEDED)\b|\bHELD\s+\d{4}-"),
    # `the owner` alone is also a file's owner, so it counts only as someone who decides.
    rule(
        "third-person",
        r"\bour user\b|\bthe (repo|repository|project) owner\b"
        r"|\bthe owner (is|was|wants|wanted|asks|asked|decides|decided|says|said"
        r"|prefers|preferred|requested|rules|ruled|has ruled|chose|does not want)\b",
        ignore_case=True,
    ),
    rule(
        "session-actor",
        r"\b(this|that|another|the next|the previous|the claiming|the managing|my|our) session\b"
        r"|\bthe [~a-z][a-z0-9._/-]* session\b|\bsession's\b"
        r"|\b(an?|the|this|another|my) (sub)?agent (found|flagged|wrote|noticed|reported|measured|decided|recorded|left|claimed)\b"
        r"|\b(found|flagged|raised|filed|written|recorded|measured|noticed) by (an?|the|this|another|my)\s+[~a-z0-9._/-]*\s*(session|agent)\b",
        ignore_case=True,
        reads=frozenset({COMMITS}),
    ),
    rule("strikethrough", r"~~[^~\n]+~~"),
    rule(
        "narrated-belief",
        r"\b(file|document|note|section|paragraph|page|line|row) used to (say|read|claim|quote)\b"
        r"|\bthe (old|earlier|previous) (wording|reading|note)\b|\bno longer true\b"
        r"|\bthis (paragraph|section|note|document|file|line) (said|claimed|used to)\b|\bearlier note\b",
        ignore_case=True,
    ),
    rule(
        "worth-phrase",
        r"\bworth (knowing|stating|carrying|being precise about|noting|keeping|recording|saying|remembering|naming)\b",
        ignore_case=True,
    ),
    rule(
        "stock-phrase",
        r"which is the failure this exists to prevent|\bthat is not cosmetic\b|\brather than a side effect\b|\bthat is the lesson\b",
        ignore_case=True,
    ),
    rule("caps-run", r"\b[A-Z][A-Z']{2,}(?:\s+[A-Z][A-Z']{1,}){2,}\b"),
    rule(
        "attribution-trailer",
        r"^\s*co-authored-by:.*\b(claude|anthropic|openai|chatgpt|gpt-\d|copilot|gemini)\b"
        r"|\bgenerated (with|by) \[?(claude|chatgpt|copilot|gemini)\b|^\s*claude-session:",
        ignore_case=True,
    ),
    rule(
        "assistant-opener",
        r"^\s*(certainly|sure|of course|absolutely)\s*[!,]|\bgreat question\b|\bi'?d be happy to\b|\bhappy to help\b"
        r"|\bhere'?s the (updated|revised|new version)\b",
        ignore_case=True,
    ),
    rule(
        "this-commit-preamble",
        r"^\s*(this (commit|pr|pull request|change|patch) (adds|introduces|updates|fixes|implements|removes|refactors|changes|makes)\b"
        r"|in this (commit|change|pr)\b)",
        ignore_case=True,
        reads=frozenset({COMMITS}),
    ),
    rule("emoji", "[\U0001f300-\U0001faff☀-⛿⭐✅✨❌]", reads=PROSE_AND_COMMITS),
    rule("hedging-opener", r"\bit(?:'s| is) (worth noting|worth mentioning|important to note)\b|\bnote that this ensures\b", ignore_case=True),
    rule(
        "changelog-comment",
        # Capitalised, so a wrapped sentence's lowercase continuation is not an opener, and
        # followed by `to` somewhere, the shape of `Added X to handle Y` and `Updated to use`.
        COMMENT_OPENER + r"(Added|Updated|Changed|Refactored|Fixed|Modified|Removed|Replaced)\s.*\bto\b",
        reads=frozenset({COMMENTS}),
    ),
    rule(
        "this-function-docstring",
        COMMENT_OPENER + r"this (function|method|class|module) (returns|handles|is|does|takes|will|creates|checks|provides|implements|contains)\b",
        ignore_case=True,
        reads=frozenset({COMMENTS}),
    ),
)

# Words far more common in model output than before it, counted per text and
# reported as a suggestion when they are dense. Narrowed where the bare word is
# ordinary: `realm of`, not `realm`.
EXCESS_VOCABULARY = re.compile(
    r"\b(delv(e|es|ed|ing)|leverag(e|es|ed|ing)|utiliz(e|es|ed|ing)|seamless(ly)?|robust|comprehensive|underscores the"
    r"|showcas(e|es|ed|ing)|tapestry|realm of|landscape of|testament to|myriad|pivotal|meticulous(ly)?|intricate|paramount|commendable)\b",
    re.IGNORECASE,
)
VOCABULARY_PER_THOUSAND = 3
VOCABULARY_MIN_USES = 2


@dataclass(frozen=True)
class Text:
    """A document, a file's comments, or a commit message, as numbered prose lines."""

    kind: str
    where: str
    lines: tuple[tuple[int, str], ...]
    raw: str = ""


@dataclass(frozen=True)
class Finding:
    """One instance: where, which rule, and the text that carried it."""

    where: str
    line: int
    rule: str
    text: str
    severity: str = ERROR

    def render(self) -> str:
        """`where:line: rule: text`, or `where: rule: text` for a whole-text rule, with a suggestion marked."""
        place = f"{self.where}:{self.line}" if self.line else self.where
        name = self.rule if self.severity == ERROR else f"{self.rule} ({self.severity})"
        return f"{place}: {name}: {self.text}"


class StartUnresolved(Exception):
    """The start file names something that is not a commit here."""


# ---- reading the project ----------------------------------------------------


def is_skipped(relative: Path) -> bool:
    """Whether a path is outside what either voice check reads."""
    return relative.name in SKIPPED_FILES or any(part.startswith(".") or part in SKIPPED_DIRS for part in relative.parts[:-1])


def git_lines(git: str | None, base: Path, *args: str) -> list[str]:
    """The null-separated names a git command prints, or nothing where git cannot say."""
    if not git:
        return []
    listed = subprocess.run([git, "-C", str(base), *args], capture_output=True, check=False)
    if listed.returncode != 0:
        return []
    return [name for name in listed.stdout.decode("utf-8", "replace").split("\0") if name]


def readable(base: Path, relative: Path) -> bool:
    """Whether the path is a file of the project's own, on disk."""
    return not is_skipped(relative) and (base / relative).is_file() and not (base / relative).is_symlink()


def listed_files(base: Path, git: str | None) -> list[Path]:
    """The project's own files: git's tracked and unignored view, or a walk outside git. Links are not its writing."""
    names = git_lines(git, base, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    if not names:
        names = [str(path.relative_to(base)) for path in base.rglob("*")]
    return [path for path in sorted({Path(name) for name in names}) if readable(base, path)]


def staged_files(base: Path, git: str | None) -> list[Path]:
    """Files the next commit would add or change, whatever else the working tree holds."""
    names = git_lines(git, base, "diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR")
    return [path for path in sorted({Path(name) for name in names}) if not is_skipped(path)]


def changed_files(base: Path, git: str | None, from_ref: str, to_ref: str) -> list[Path]:
    """Files that differ between the refs, from where the two branches parted."""
    names = git_lines(git, base, "diff", "--name-only", "-z", "--diff-filter=ACMR", f"{from_ref}...{to_ref}")
    return [path for path in sorted({Path(name) for name in names}) if readable(base, path)]


def working_text(base: Path, relative: Path) -> str | None:
    """What the file holds on disk."""
    try:
        return (base / relative).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def staged_text(base: Path, git: str | None, relative: Path) -> str | None:
    """What the index holds for the file, which is what a commit would carry."""
    if not git:
        return None
    shown = subprocess.run([git, "-C", str(base), "show", f":{relative.as_posix()}"], capture_output=True, check=False)
    return shown.stdout.decode("utf-8", "replace") if shown.returncode == 0 else None


def unquoted(line: str) -> str:
    """The line with inline code and quoted spans replaced by an empty code span, so the words either side stay apart."""
    return QUOTED.sub("``", line)


def prose(text: str) -> Iterator[tuple[int, str]]:
    """Numbered lines of markdown or a commit message, leaving out code and block quotes."""
    in_fence = False
    for number, line in enumerate(text.splitlines(), 1):
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence or line.startswith(("    ", "\t")) or line.lstrip().startswith(">"):
            continue
        yield number, unquoted(line)


def language(path: Path) -> Syntax | None:
    """How this kind of file writes a comment and a string, or nothing where it has no comments to read."""
    if path.suffix in SLASH_SUFFIXES:
        return Syntax(("//",), (("/*", "*/"),), ('"', "'", "`"))
    if path.suffix == ".lua":
        return Syntax(("--",), (("--[[", "]]"),))
    if path.suffix == ".rb":
        return Syntax(("#",), (("=begin", "=end"),), anchored=True)
    if path.suffix in HASH_SUFFIXES or path.name in HASH_FILES:
        return Syntax(("#",))
    return None


def string_end(text: str, start: int, quote: str) -> int:
    """The index just past the string opening at `start`, or past the line where it never closes."""
    index = start + len(quote)
    while index < len(text):
        if text[index] == "\\":
            index += 2
        elif text.startswith(quote, index):
            return index + len(quote)
        elif text[index] == "\n" and quote != "`":
            return index
        else:
            index += 1
    return len(text)


def ends_at(text: str, target: str, start: int) -> int:
    """Where the target next appears, or the end of the text when it never does."""
    found = text.find(target, start)
    return len(text) if found == -1 else found


def opener_at(text: str, index: int, syntax: Syntax) -> tuple[str, str] | None:
    """The block comment opening here, where one is and this position may open one."""
    if syntax.anchored and index and text[index - 1] != "\n":
        return None
    return next((pair for pair in syntax.block if text.startswith(pair[0], index)), None)


def scanned_comments(text: str, syntax: Syntax) -> list[tuple[int, str]]:
    """Comments wherever they sit on a line, without reading a marker that is inside a string."""
    found: list[tuple[int, str]] = []
    index = 0
    while index < len(text):
        line = text.count("\n", 0, index) + 1
        if pair := opener_at(text, index, syntax):
            stop = ends_at(text, pair[1], index + len(pair[0]))
            found.append((line, text[index + len(pair[0]) : stop]))
            index = stop + len(pair[1])
        elif marker := next((one for one in syntax.line if text.startswith(one, index)), None):
            stop = ends_at(text, "\n", index)
            found.append((line, text[index + len(marker) : stop]))
            index = stop
        elif quote := next((one for one in syntax.strings if text.startswith(one, index)), ""):
            index = string_end(text, index, quote)
        else:
            index += 1
    return [(line + offset, body.strip()) for line, comment in found for offset, body in enumerate(comment.splitlines()) if body.strip()]


def python_prose(text: str) -> list[tuple[int, str]]:
    """Comments from the tokenizer and docstrings from the syntax tree, so a string is never read as either."""
    found: list[tuple[int, str]] = []
    try:
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.type == tokenize.COMMENT:
                found.append((token.start[0], token.string.lstrip("#").strip()))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return scanned_comments(text, Syntax(("#",)))
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return found
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and (body := ast.get_docstring(node)):
            first = getattr(node.body[0], "lineno", 1)
            found += [(first + offset, line.strip()) for offset, line in enumerate(body.splitlines()) if line.strip()]
    return sorted(set(found))


def comment_lines(path: Path, text: str) -> list[tuple[int, str]]:
    """The prose a file's comments and docstrings hold, without the directives a program reads."""
    if path.suffix == ".py":
        found = python_prose(text)
    elif syntax := language(path):
        found = scanned_comments(text, syntax)
    else:
        return []
    return [(number, unquoted(line)) for number, line in sorted(set(found)) if line.strip("#/*-\"' ") and not DIRECTIVE.search(line)]


def file_texts(base: Path, files: list[Path], read: Callable[[Path, Path], str | None] = working_text) -> list[Text]:
    """Documents and comment material from the project's files, read however the mode reads them."""
    texts = []
    for relative in files:
        content = read(base, relative)
        if content is None:
            continue
        if relative.suffix == ".md":
            texts.append(Text(DOCS, str(relative), tuple(prose(content)), content))
        elif found := comment_lines(relative, content):
            texts.append(Text(COMMENTS, str(relative), tuple(found)))
    return texts


def recorded_start(base: Path, git: str | None, start_file: str) -> tuple[str | None, str]:
    """The start commit, or None and why commits are not read."""
    recorded = base / start_file
    if not recorded.is_file():
        return None, f"commits not read: no start commit is recorded in {start_file}"
    if not git:
        return None, "commits not read: git is not on PATH"
    words = recorded.read_text(encoding="utf-8", errors="replace").split()
    named = words[0] if words else ""
    resolved = subprocess.run(
        [git, "-C", str(base), "rev-parse", "--verify", "--quiet", f"{named}^{{commit}}"], capture_output=True, text=True, check=False
    )
    if not named or resolved.returncode != 0:
        raise StartUnresolved(f"{start_file} names {named or 'nothing'}, which is not a commit in this repository")
    sha = resolved.stdout.strip()
    return sha, f"commits read after {sha[:12]}"


def commit_texts(base: Path, git: str | None, span: str | None) -> list[Text]:
    """Commit messages over a revision span, newest first."""
    if not span or not git:
        return []
    log = subprocess.run([git, "-C", str(base), "log", "--no-merges", "--format=%H%x1f%B%x1e", span], capture_output=True, text=True, check=False)
    texts = []
    for record in log.stdout.split("\x1e"):
        sha, _, message = record.strip("\n").partition("\x1f")
        if sha:
            texts.append(Text(COMMITS, f"commit {sha[:12]}", tuple(prose(message.strip())), message.strip()))
    return texts


def message_text(path: Path) -> Text:
    """One commit message from its file, without the lines git strips."""
    content = path.read_text(encoding="utf-8", errors="replace")
    body = content.split("# ------------------------ >8 ------------------------")[0]
    kept = "\n".join(line for line in body.splitlines() if not line.startswith("#")).strip()
    return Text(COMMITS, path.name, tuple(prose(kept)), kept)


# ---- the rules ----------------------------------------------------------------


def line_findings(text: Text) -> list[Finding]:
    """Every line rule that reads this kind of text, at most one finding per rule per line."""
    return [
        Finding(text.where, number, each.name, line.strip()[:160])
        for number, line in text.lines
        for each in LINE_RULES
        if text.kind in each.reads and re.search(each.pattern, line)
    ]


def paragraphs(markdown: str) -> list[str]:
    """Blank-line separated prose blocks, leaving out code, headings, tables and block quotes."""
    blocks: list[str] = []
    current: list[str] = []
    in_fence = False
    for line in markdown.splitlines():
        if FENCE.match(line):
            in_fence = not in_fence
        elif not in_fence and line.strip() and not line.startswith(("    ", "\t", "#", "|", ">")):
            current.append(line)
            continue
        elif not in_fence and not line.strip() and current:
            blocks.append(" ".join(current))
            current = []
    return blocks + ([" ".join(current)] if current else [])


def rather_than(text: Text) -> list[Finding]:
    """More than two uses of the connective in one document or commit."""
    uses = sum(len(RATHER_THAN.findall(line)) for _, line in text.lines)
    if text.kind == COMMENTS or uses <= RATHER_THAN_PER_TEXT:
        return []
    return [Finding(text.where, 0, "rather-than", f"{uses} uses, at most {RATHER_THAN_PER_TEXT}")]


def bold_density(text: Text) -> list[Finding]:
    """Bold in more than 30% of a document's paragraphs, once it has six."""
    if text.kind != DOCS:
        return []
    blocks = paragraphs(text.raw)
    bold = sum("**" in block for block in blocks)
    if len(blocks) < BOLD_MIN_PARAGRAPHS or bold <= BOLD_SHARE * len(blocks):
        return []
    return [Finding(text.where, 0, "bold-density", f"{bold} of {len(blocks)} paragraphs carry bold, at most {int(BOLD_SHARE * 100)}%")]


def commit_length(text: Text) -> list[Finding]:
    """A commit body over twenty lines."""
    if text.kind != COMMITS:
        return []
    body = text.raw.splitlines()[1:]
    lines = len("\n".join(body).strip("\n").splitlines())
    return [Finding(text.where, 0, "commit-length", f"{lines} body lines, at most {COMMIT_BODY_LINES}")] if lines > COMMIT_BODY_LINES else []


def excess_vocabulary(text: Text) -> list[Finding]:
    """The listed words at more than three per 1,000 words, used at least twice, as a suggestion."""
    words = sum(len(line.split()) for _, line in text.lines)
    uses = [match.group(0).lower() for _, line in text.lines for match in EXCESS_VOCABULARY.finditer(line)]
    if len(uses) < VOCABULARY_MIN_USES or len(uses) * 1000 <= VOCABULARY_PER_THOUSAND * max(words, 1):
        return []
    listed = ", ".join(sorted(set(uses)))
    return [Finding(text.where, 0, "excess-vocabulary", f"{len(uses)} in {words} words: {listed}", SUGGESTION)]


WHOLE_TEXT_RULES: tuple[Callable[[Text], list[Finding]], ...] = (rather_than, bold_density, commit_length, excess_vocabulary)


def findings(texts: list[Text]) -> list[Finding]:
    """Every finding across every text, in reading order."""
    return [found for text in texts for found in (*line_findings(text), *(f for check in WHOLE_TEXT_RULES for f in check(text)))]


# ---- running it ---------------------------------------------------------------


def add_modes(parser: argparse.ArgumentParser) -> None:
    """The arguments that choose what is read, shaped like pre-commit's own. The voice review takes the same."""
    parser.add_argument("files", nargs="*", type=Path, help="the files to read; with none, the staged files")
    parser.add_argument("--all-files", "-a", action="store_true", help="every file the project holds, and the commits after the start")
    parser.add_argument("--from-ref", help="with --to-ref, the files changed between the two refs and the commits in between")
    parser.add_argument("--to-ref", help="see --from-ref")
    parser.add_argument("--commit-msg-filename", type=Path, help="a file holding one commit message, as the commit-msg stage passes it")
    parser.add_argument("--base", default=".", type=Path, help="the repository to read, default the working directory")
    parser.add_argument("--start-file", default=".voice-review-start", help="one SHA; commits after it are read under --all-files")
    parser.add_argument("--report", type=Path, help="write the findings here as JSON")


def check_modes(parser: argparse.ArgumentParser, args: argparse.Namespace) -> argparse.Namespace:
    """Refuse two modes at once and half a ref pair, which argparse reports as exit 2."""
    chosen = [bool(args.files), args.all_files, bool(args.from_ref or args.to_ref), bool(args.commit_msg_filename)]
    if sum(chosen) > 1:
        parser.error("name files, or --all-files, or --from-ref with --to-ref, or --commit-msg-filename, and not two of them")
    if bool(args.from_ref) != bool(args.to_ref):
        parser.error("--from-ref and --to-ref are given together")
    return args


def arguments(argv: list[str] | None) -> argparse.Namespace:
    """The command line."""
    parser = argparse.ArgumentParser(description="Fail on the wording the writing standard names.")
    add_modes(parser)
    parser.add_argument("--baseline", default=".voice-baseline.json", help="findings accepted with a reason, each written by hand")
    return check_modes(parser, parser.parse_args(argv))


def selected(base: Path, git: str | None, args: argparse.Namespace) -> tuple[list[Text], str]:
    """The texts the chosen mode reads, and the line saying what that was."""
    if args.commit_msg_filename:
        return [message_text(args.commit_msg_filename)], f"one commit message, {args.commit_msg_filename}"
    if args.all_files:
        start, why = recorded_start(base, git, args.start_file)
        return file_texts(base, listed_files(base, git)) + commit_texts(base, git, f"{start}..HEAD" if start else None), why
    if args.from_ref:
        changed = changed_files(base, git, args.from_ref, args.to_ref)
        commits = commit_texts(base, git, f"{args.from_ref}..{args.to_ref}")
        return file_texts(base, changed) + commits, f"{len(changed)} changed files and {len(commits)} commits in {args.from_ref}..{args.to_ref}"
    if args.files:
        named = [path for path in args.files if readable(base, path)]
        return file_texts(base, named), f"{len(named)} named files"
    staged = staged_files(base, git)
    return file_texts(base, staged, lambda where, path: staged_text(where, git, path)), f"{len(staged)} staged files, read from the index"


def accepted_entries(base: Path, name: str) -> tuple[list[dict], list[Finding]]:
    """The baseline's entries, and a finding for each one that cannot stand as written."""
    path = base / name
    if not path.is_file():
        return [], []
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        entries = list(document["accepted"])
    except (ValueError, KeyError, TypeError) as broken:
        return [], [Finding(name, 0, "baseline-unreadable", f"{broken}")]
    # An entry with no reason accepts nothing: it is reported, and the finding
    # it names goes on standing.
    unreasoned = [entry for entry in entries if not str(entry.get("reason", "")).strip()]
    wrong = [
        Finding(name, 0, "baseline-entry", f"{entry.get('file', '?')} {entry.get('rule', '?')} has no reason, so nothing says why it stands")
        for entry in unreasoned
    ]
    return [entry for entry in entries if entry not in unreasoned], wrong


def matches(entry: dict, found: Finding) -> bool:
    """Whether the entry accepts this finding: the same rule, in the same place, on the same words."""
    return entry.get("file") == found.where and entry.get("rule") == found.rule and entry.get("text") == found.text


def against_baseline(found: list[Finding], entries: list[dict], whole_tree: bool) -> tuple[list[Finding], list[Finding], list[Finding]]:
    """The findings still standing, the ones an entry accepts, and a finding for each entry nothing matches.

    A stale entry is only known when the whole tree was read. In any other mode
    the files an entry names may simply not have been among the ones selected.
    """
    accepted = [one for one in found if any(matches(entry, one) for entry in entries)]
    standing = [one for one in found if one not in accepted]
    stale = [
        Finding(str(entry.get("file", "?")), 0, "baseline-stale", f"{entry.get('rule', '?')} is accepted here and no longer found")
        for entry in entries
        if whole_tree and not any(matches(entry, one) for one in found)
    ]
    return standing, accepted, stale


def main(argv: list[str] | None = None) -> int:
    """Read what the mode selects, print every finding, and exit 1 if any is an error."""
    args = arguments(argv)
    base = args.base.resolve()
    git = shutil.which("git")
    try:
        texts, commits = selected(base, git, args)
    except StartUnresolved as problem:
        print(f"voice tells: {problem}")
        return 2
    except OSError as unreadable:
        print(f"voice tells: {unreadable}")
        return 2
    entries, wrong = accepted_entries(base, args.baseline)
    standing, accepted, stale = against_baseline(findings(texts), entries, args.all_files)
    found = standing + stale + wrong
    for each in found:
        print(each.render())
    counts: dict[str, int] = {}
    for each in found:
        counts[each.rule] = counts.get(each.rule, 0) + 1
    errors = sum(each.severity == ERROR for each in found)
    summary = ", ".join(f"{name} {count}" for name, count in sorted(counts.items())) or "none"
    print(f"voice tells: {errors} errors, {len(found) - errors} suggestions, {len(accepted)} accepted ({summary}); {commits}")
    if args.report:
        document = {
            "passed": not errors,
            "commits": commits,
            "counts": counts,
            "findings": [vars(f) for f in found],
            "accepted": [vars(f) for f in accepted],
        }
        args.report.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
