"""Tests for `bin/suppression-register.py`.

Both directions fail: an unregistered pragma is a suppression nobody justified,
and a registered row with nothing behind it is a justification for something
already gone. The count is part of the comparison, so a second pragma added to
an already-registered file is caught rather than hidden behind the first.
"""

from __future__ import annotations

import subprocess  # nosec B404
from pathlib import Path

import pytest
from conftest import ROOT, load, script_argv

register_checker = load("bin/suppression-register.py")

ARGV = ["--register", "SUPPRESSIONS", "."]


def project(tmp_path: Path, register: str | None, **sources: str) -> Path:
    """Write a register, if there is one, and the sources it describes."""
    if register is not None:
        (tmp_path / "SUPPRESSIONS").write_text(register, encoding="utf-8")
    for name, text in sources.items():
        path = tmp_path / name.replace("_go", ".go")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return tmp_path


# ---- agreement --------------------------------------------------------------


# COVERS FR-5.3 | positive
def test_no_pragmas_and_no_register_passes(checker, tmp_path):
    """A project that silences nothing needs no register."""
    tree = project(tmp_path, None, main_go="package main\n\nfunc main() {}\n")
    code, out = checker(register_checker, ARGV, tree)
    assert code == 0
    assert "no suppression pragmas in 1 source file(s)" in out


# COVERS FR-5.2 | regression
def test_a_run_that_read_no_source_at_all_fails(checker, tmp_path):
    """Read nothing and found nothing are different results.

    One message for both reads as a clean bill over a tree the scan never
    entered, such as a Python project read by a Go-only scan. It fails rather
    than warns, per `docs/DECISIONS/a-task-that-cannot-fail-leaves-the-jig.md`.
    """
    (tmp_path / "README.md").write_text("Prose, and no source.\n", encoding="utf-8")
    code, out = checker(register_checker, ARGV, tmp_path)
    assert code == 1
    assert "read nothing" in out


# COVERS FR-5.1 | positive
def test_a_registered_pragma_passes(checker, tmp_path):
    """The pragma is in the source and the register says why. Nothing to report."""
    tree = project(
        tmp_path,
        "Register.\n\n  main.go   #nosec G304\n",
        main_go="package main\n\nfunc read() { open(p) } //#nosec G304\n",
    )
    code, out = checker(register_checker, ARGV, tree)
    assert code == 0, out
    assert "1 pragma(s)" in out


# ---- the two directions -----------------------------------------------------


# COVERS FR-5.1, FR-2.2 | negative
def test_an_unregistered_pragma_fails(checker, tmp_path):
    """A suppression nobody justified."""
    tree = project(
        tmp_path,
        "Register.\n",
        main_go="package main\n\nfunc read() { open(p) } //#nosec G304\n",
    )
    code, out = checker(register_checker, ARGV, tree)
    assert code == 1
    assert "main.go" in out
    assert "in no register entry" in out


# COVERS FR-5.1 | negative
def test_a_registered_entry_with_nothing_behind_it_fails(checker, tmp_path):
    """A justification for something already gone reads as cover for its replacement."""
    tree = project(
        tmp_path,
        "Register.\n\n  gone.go   #nosec G304\n",
        main_go="package main\n\nfunc main() {}\n",
    )
    code, out = checker(register_checker, ARGV, tree)
    assert code == 1
    assert "gone.go" in out
    assert "not in the source" in out


# COVERS FR-5.2 | edge
def test_a_second_pragma_in_a_registered_file_fails(checker, tmp_path):
    """The count is the comparison: one registered pragma does not cover two."""
    tree = project(
        tmp_path,
        "Register.\n\n  main.go   #nosec G304\n",
        main_go=("package main\n\nfunc a() { open(p) } //#nosec G304\nfunc b() { open(q) } //#nosec G304\n"),
    )
    code, out = checker(register_checker, ARGV, tree)
    assert code == 1
    assert "the source carries 2, the register says 1" in out


# COVERS FR-5.3 | negative
def test_pragmas_with_no_register_at_all_fails(checker, tmp_path):
    """A missing register is not an empty one."""
    tree = project(
        tmp_path,
        None,
        main_go="package main\n\nfunc read() { open(p) } //#nosec G304\n",
    )
    code, out = checker(register_checker, ARGV, tree)
    assert code == 1
    assert "no SUPPRESSIONS" in out


# ---- the empty case, where the false green is --------------------------------


# COVERS FR-5.4 | regression
def test_a_python_pragma_is_seen_and_must_be_registered(checker, tmp_path):
    """A Python pragma is read, where a Go-only scan passed over it.

    A checker reading `*.go` only leaves a Python project's `# nosec`
    silenced and unseen instead of silenced and justified, and the gate
    reports a pass. In skid that printed `no suppression pragmas anywhere`,
    exit 0, over a tree holding five registered ones.

    This is a regression test because the failure it describes is invisible
    from toolbox: this repository is Go-free and Python-only, so the checker's
    own suite could pass forever while the shipped behaviour is wrong in every
    adopter.
    """
    tree = tmp_path
    (tree / "SUPPRESSIONS").write_text("Register.\n", encoding="utf-8")
    (tree / "app.py").write_text(
        "import subprocess\n\nsubprocess.run(cmd, shell=True)  # nosec B602\n",
        encoding="utf-8",
    )
    code, out = checker(register_checker, ARGV, tree)
    assert code == 1
    assert "app.py" in out
    assert "B602" in out


# COVERS FR-5.2 | regression
def test_a_pragma_in_a_script_with_no_extension_is_seen(checker, tmp_path):
    """Selecting by extension is the fault this checker sat beside.

    A reporting script and a git hook, both shell with no suffix, and the
    second 170 lines enforcing a project rule. A shebang says what a file is
    where an extension does not.
    """
    tree = tmp_path
    (tree / "SUPPRESSIONS").write_text("Register.\n", encoding="utf-8")
    hook = tree / "hook"
    hook.write_text("#!/usr/bin/env bash\n# shellcheck disable=SC2086\necho $x\n", encoding="utf-8")
    code, out = checker(register_checker, ARGV, tree)
    assert code == 1
    assert "hook" in out
    assert "SC2086" in out


# COVERS FR-5.2 | regression
def test_prose_about_a_pragma_is_not_a_pragma(checker, tmp_path):
    """A pragma is itself a comment, so no rule about strings separates the two.

    Position does: a real pragma opens its comment, and prose mentions the
    spelling mid-sentence. Without this the checker fails on its own source and
    its own fixtures, which is the tool being graded as a use of itself: 28
    findings in toolbox, none of them a suppression.
    """
    tree = tmp_path
    (tree / "SUPPRESSIONS").write_text("Register.\n", encoding="utf-8")
    (tree / "doc.py").write_text(
        '"""A rule covering `# nosec` and not `# noqa` is arbitrary."""\n\n'
        "# The spellings are `# nosec`, `# noqa` and `# type: ignore`.\n"
        'PATTERN = "# nosec"\n',
        encoding="utf-8",
    )
    code, out = checker(register_checker, ARGV, tree)
    assert code == 0, out
    assert "no suppression pragmas" in out


# COVERS FR-5.2 | regression
def test_a_pragma_after_a_comment_marker_is_still_a_pragma(checker, tmp_path):
    """`// #nosec G304 -- reason` is a pragma.

    Requiring the pragma exactly at the comment opener misses this form, which
    turns a gate green. The pragma may open the comment or be the first thing
    inside it.
    """
    tree = tmp_path
    (tree / "SUPPRESSIONS").write_text("Register.\n", encoding="utf-8")
    (tree / "load.go").write_text(
        "package main\n\n// #nosec G304 -- the path is the user's own\nfunc read() { open(p) }\n",
        encoding="utf-8",
    )
    code, out = checker(register_checker, ARGV, tree)
    assert code == 1
    assert "G304" in out


# ---- the wiring -------------------------------------------------------------


# COVERS NFR-3 | positive
def test_the_script_runs_as_a_script(tmp_path):
    """In-process tests cannot catch a broken shebang or a missing import."""
    (tmp_path / "SUPPRESSIONS").write_text("Register.\n", encoding="utf-8")
    (tmp_path / "main.go").write_text("package main\n\nfunc read() { open(p) } //#nosec G304\n", encoding="utf-8")
    result = subprocess.run(  # nosec B603
        script_argv(ROOT / "bin" / "suppression-register.py", *ARGV),
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1, result.stderr
    assert "main.go" in result.stdout


# COVERS FR-5.2 | regression
def test_a_pragma_with_a_trailing_reason_is_still_seen(checker, tmp_path):
    """Writing why beside a suppression is the good habit, and it hid one.

    A rule list running to end of line means `# noqa: BLE001 - the reason`
    matches nothing and the pragma is invisible, which hides the suppressions
    whose authors documented them. The codes end the pragma and prose may
    follow, as with `nosec`.
    """
    tree = tmp_path
    (tree / "SUPPRESSIONS").write_text("Register.\n", encoding="utf-8")
    (tree / "app.py").write_text(
        "import os  # noqa: E402 - imported late on purpose, see the docstring\n",
        encoding="utf-8",
    )
    code, out = checker(register_checker, ARGV, tree)
    assert code == 1
    assert "app.py" in out
    assert "E402" in out


# COVERS FR-5.2 | negative
def test_a_sentence_beginning_with_a_spelling_is_not_a_pragma(checker, tmp_path):
    """`# nosec` alone is a pragma; `#  nosec marks are...` is a sentence.

    Both open their comment, so the position rule cannot separate them and the
    trailing text is what does: a bare spelling naming no codes must end the
    line.

    Requiring code before the comment would lose a pragma written on its own
    line above the statement.
    """
    tree = tmp_path
    (tree / "SUPPRESSIONS").write_text("Register.\n", encoding="utf-8")
    (tree / "notes.py").write_text(
        "#   nosec marks in one file they do not own.\n#   noqa marks are the same shape.\n",
        encoding="utf-8",
    )
    code, out = checker(register_checker, ARGV, tree)
    assert code == 0, out


# COVERS FR-5.2 | regression
def test_a_triple_quote_inside_a_string_does_not_open_a_docstring(checker, tmp_path):
    """A delimiter spelled inside a string is not a fence.

    `code_lines` finds a fence with `re.search(r'\"\"\"|...', line)`, and that
    line spells the delimiter inside a raw string. Counted as a fence, it
    toggles the state, so every later docstring reads as code and a sentence
    about a pragma reads as one.
    """
    tree = tmp_path
    (tree / "SUPPRESSIONS").write_text("Register.\n", encoding="utf-8")
    (tree / "scanner.py").write_text(
        "import re\n\n"
        'FENCE = re.search(r\'"""|x\', "")\n\n'
        "def f():\n"
        '    """Prose mentioning `# nosec B404` after a quote in a literal."""\n'
        "    return 1\n",
        encoding="utf-8",
    )
    code, out = checker(register_checker, ARGV, tree)
    assert code == 0, out


# ---- one register, more than one scan base ----------------------------------


def two_base_repo(tmp_path):
    """A repository with two packs, one register at its root.

    The `.git` marker is what makes the root discoverable, and it is how a real
    adopter is shaped. Without it the checker falls back to the scan root, which
    is the behaviour it had before a frame existed.
    """
    (tmp_path / ".git").mkdir()
    for pack, name in (("python", "app.py"), ("go", "main.go")):
        (tmp_path / pack).mkdir()
        (tmp_path / pack / name).write_text(
            "import subprocess  # nosec B404\n" if name.endswith(".py") else "package main\n\nfunc f() { g() } //nolint:errcheck\n",
            encoding="utf-8",
        )
    return tmp_path


# COVERS FR-5.1 | regression
def test_a_root_register_is_read_from_a_pack_below_it(checker, tmp_path):
    """The register names a file from the ROOT and the scan runs at the pack.

    Both spellings are correct and they are not the same string: a scan at
    `python/` calls the file `app.py` where the register at the root calls it
    `python/app.py`. Compared as strings, one of the two is always wrong, and a
    repository running the shared jig at two bases has no valid register.
    """
    tree = two_base_repo(tmp_path)
    (tree / "SUPPRESSIONS").write_text(
        "Register.\n\n    python/app.py   # nosec B404\n    go/main.go   //nolint:errcheck\n",
        encoding="utf-8",
    )
    code, out = checker(register_checker, ["--register", "../SUPPRESSIONS", "."], tree / "python")
    assert code == 0, out


# COVERS FR-5.1 | regression
def test_the_other_packs_rows_are_not_phantoms(checker, tmp_path):
    """Resolving both sides is necessary and not sufficient.

    One register serving two bases is read whole by each scan, so every row for
    the other pack would report as a pragma that has gone. A row outside the
    scan root whose file exists belongs to another scan and is left alone.
    """
    tree = two_base_repo(tmp_path)
    (tree / "SUPPRESSIONS").write_text(
        "Register.\n\n    python/app.py   # nosec B404\n    go/main.go   //nolint:errcheck\n",
        encoding="utf-8",
    )
    code, out = checker(register_checker, ["--register", "../SUPPRESSIONS", "."], tree / "go")
    assert code == 0, out
    assert "app.py" not in out


# COVERS FR-5.1 | negative
def test_a_row_naming_nothing_is_still_a_phantom(checker, tmp_path):
    """The half of the phantom check that still means something outside the scan.

    A row pointing at a file that exists nowhere is caught wherever it sits,
    because no other scan would ever catch it either.
    """
    tree = two_base_repo(tmp_path)
    (tree / "SUPPRESSIONS").write_text(
        "Register.\n\n    python/app.py   # nosec B404\n    go/gone.go   //nolint:errcheck\n",
        encoding="utf-8",
    )
    code, out = checker(register_checker, ["--register", "../SUPPRESSIONS", "."], tree / "python")
    assert code == 1
    assert "gone.go" in out
    assert "points at nothing" in out


# ---- a directory of suppressions --------------------------------------------


DIR_ARGV = ["--register", "SUPPRESSIONS", "."]


# COVERS FR-5.5 | positive
def test_a_directory_register_totals_what_one_document_totals(checker, tmp_path):
    """One file per suppression is the same register, written differently."""
    entries = tmp_path / "SUPPRESSIONS"
    (entries / "a").mkdir(parents=True)
    (entries / "b").mkdir(parents=True)
    (entries / "a" / "one.md").write_text("# One\n\n    one.go   //nolint:errcheck\n", encoding="utf-8")
    (entries / "b" / "two.md").write_text("# Two\n\n    two.go   //nolint:errcheck\n", encoding="utf-8")
    for name in ("one.go", "two.go"):
        (tmp_path / name).write_text("package main\n\nfunc f() { g() } //nolint:errcheck\n", encoding="utf-8")
    code, out = checker(register_checker, DIR_ARGV, tmp_path)
    assert code == 0, out
    assert "2 pragma(s)" in out


# COVERS FR-5.5 | negative
def test_a_directory_register_still_fails_an_unregistered_pragma(checker, tmp_path):
    """Splitting the register may not soften either direction of the check."""
    entries = tmp_path / "SUPPRESSIONS" / "a"
    entries.mkdir(parents=True)
    (entries / "one.md").write_text("# One\n\n    one.go   //nolint:errcheck\n", encoding="utf-8")
    for name in ("one.go", "two.go"):
        (tmp_path / name).write_text("package main\n\nfunc f() { g() } //nolint:errcheck\n", encoding="utf-8")
    code, out = checker(register_checker, DIR_ARGV, tmp_path)
    assert code == 1
    assert "two.go" in out


# COVERS FR-2.3 | negative
def test_an_unreadable_register_reports_why_and_does_not_raise(checker, tmp_path):
    """Absent and unreadable are different, and neither is a traceback."""
    (tmp_path / "SUPPRESSIONS").write_text("# Register\n\n    main.go   //nolint:errcheck\n", encoding="utf-8")
    (tmp_path / "main.go").write_text("package main\n\nfunc f() { g() } //nolint:errcheck\n", encoding="utf-8")
    (tmp_path / "SUPPRESSIONS").chmod(0o000)
    try:
        code, out = checker(register_checker, ARGV, tmp_path)
    finally:
        (tmp_path / "SUPPRESSIONS").chmod(0o644)
    assert code == 1
    assert "cannot be read" in out


# ---- trees this project is not answerable for -------------------------------


# COVERS FR-2.5 | regression
def test_a_vendored_or_scratch_pragma_is_not_the_projects(checker, tmp_path):
    """The register walked every `*.go` with no skip list at all.

    A vendored dependency carrying `//nolint` failed the project that vendored
    it, for somebody else's decision, and a scratch file in `.ephemera` did the
    same for a file that is no part of the project. Both directions of the
    check were wrong about whose code they were reading.
    """
    for relative in ("vendor/dep/v.go", ".ephemera/probe/p.go"):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("package main\n\nfunc f() { g() } //nolint:errcheck\n", encoding="utf-8")
    # The project's own file, carrying nothing. Without it this tree holds no
    # readable source at all, and the run fails for having read nothing rather
    # than passing for having correctly skipped what it should skip. The two
    # outcomes agreed before that distinction existed, which is why the fixture
    # did not need it.
    (tmp_path / "main.go").write_text("package main\n\nfunc main() {}\n", "utf-8")
    code, out = checker(register_checker, ARGV, tmp_path)
    assert code == 0, out
    assert "no suppression pragmas in 1 source file(s)" in out


# COVERS FR-2.5 | positive
def test_the_projects_own_pragma_is_still_found(checker, tmp_path):
    """The skip list may not swallow the thing the check exists for."""
    vendored = tmp_path / "vendor" / "v.go"
    vendored.parent.mkdir(parents=True)
    vendored.write_text("package main\n\nfunc f() { g() } //nolint:errcheck\n", encoding="utf-8")
    (tmp_path / "main.go").write_text("package main\n\nfunc h() { i() } //nolint:errcheck\n", encoding="utf-8")
    code, out = checker(register_checker, ARGV, tmp_path)
    assert code == 1
    assert "1 pragma(s)" in out


# ---- TypeScript, detect-secrets, and other checkouts --------------------------


def tree_with(tmp_path: Path, register: str, files: dict[str, str]) -> Path:
    """A register and any files, named exactly."""
    (tmp_path / "SUPPRESSIONS").write_text(register, encoding="utf-8")
    for name, text in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return tmp_path


SPELLED = [
    ("src/a.ts", "const x = y; // eslint-disable-line no-unused-vars", "eslint-disable-line no-unused-vars"),
    ("src/a.ts", "// eslint-disable-next-line @typescript-eslint/no-explicit-any -- the shape is open", "eslint-disable-next-line @typescript-eslint/no-explicit-any"),
    ("src/a.mjs", "/* eslint-disable no-console */", "eslint-disable no-console"),
    ("src/a.ts", "// deno-lint-ignore no-explicit-any", "deno-lint-ignore no-explicit-any"),
    ("src/a.tsx", "// @ts-expect-error the fixture is malformed on purpose", "@ts-expect-error"),
    ("src/a.ts", "// @ts-ignore", "@ts-ignore"),
    ("config.py", 'TOKEN = "fixture"  # pragma: allowlist secret', "pragma: allowlist secret"),
]


# COVERS FR-5.4, FR-5.6 | negative
@pytest.mark.parametrize(("name", "line", "spelling"), SPELLED, ids=[case[2] for case in SPELLED])
def test_each_typescript_and_detect_secrets_spelling_must_be_registered(checker, tmp_path, name, line, spelling):
    """Every spelling is seen, so an unregistered one fails and names its file."""
    tree = tree_with(tmp_path, "Register.\n", {name: f"{line}\n"})
    code, out = checker(register_checker, ARGV, tree)
    assert code == 1, out
    assert name in out and "in no register entry" in out


# COVERS FR-5.4, FR-5.6 | positive
@pytest.mark.parametrize(("name", "line", "spelling"), SPELLED, ids=[case[2] for case in SPELLED])
def test_each_spelling_passes_once_registered(checker, tmp_path, name, line, spelling):
    """The register row is read with the same pattern, so the same spelling registers it."""
    marker = "#" if name.endswith(".py") else "//"
    tree = tree_with(tmp_path, f"Register.\n\n  {name}   {marker} {spelling}\n", {name: f"{line}\n"})
    code, out = checker(register_checker, ARGV, tree)
    assert code == 0, out


# COVERS FR-5.4 | edge
def test_a_private_field_does_not_hide_a_typescript_pragma(checker, tmp_path):
    """`#` opens no comment in TypeScript, so the `//` after a `#private` field is still where the comment starts."""
    tree = tree_with(tmp_path, "Register.\n", {"src/a.ts": "this.#count = 0; // eslint-disable-line no-param-reassign\n"})
    code, out = checker(register_checker, ARGV, tree)
    assert code == 1 and "src/a.ts" in out


# COVERS FR-5.7 | regression
def test_a_nested_checkout_is_not_read(checker, tmp_path):
    """An agent's worktree, or any directory holding its own `.git`, is another repository's to register."""
    pragma = "package main\n\nfunc read() { open(p) } //#nosec G304\n"
    tree = tree_with(
        tmp_path,
        "Register.\n\n  main.go   #nosec G304\n",
        {"main.go": pragma, "work/agent-1/.git": "gitdir: elsewhere\n", "work/agent-1/main.go": pragma},
    )
    code, out = checker(register_checker, ARGV, tree)
    assert code == 0, out
    assert "1 pragma(s)" in out


# COVERS FR-2.5 | property
def test_both_checkers_skip_the_same_directories():
    """Two copies of one list, in scripts that share no module.

    They are loaded by path, so neither can import the other, and the list in
    each is free to drift from the other, which this test catches.
    """
    traceability = load("bin/test-traceability.py")
    assert register_checker.SKIP_DIRS == traceability.SKIP_DIRS, (
        "bin/suppression-register.py and bin/test-traceability.py disagree about "
        f"which trees to skip: {register_checker.SKIP_DIRS ^ traceability.SKIP_DIRS}"
    )
