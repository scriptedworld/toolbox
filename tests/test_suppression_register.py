"""Tests for `bin/suppression-register.py`.

Both directions fail: an unregistered pragma is a suppression nobody justified,
and a registered row with nothing behind it is a justification for something
already gone. The count is part of the comparison, so a second pragma added to
an already-registered file is caught rather than hidden behind the first.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from conftest import ROOT, load

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


# COVERS: FR-5.3 | positive
def test_no_pragmas_and_no_register_passes(checker, tmp_path):
    """A project that silences nothing needs no register and is not suspicious."""
    tree = project(tmp_path, None, main_go="package main\n\nfunc main() {}\n")
    code, out = checker(register_checker, ARGV, tree)
    assert code == 0
    assert "no suppression pragmas in 1 source file(s)" in out


# COVERS: FR-5.2 | regression
def test_a_run_that_read_no_source_at_all_fails(checker, tmp_path):
    """Read nothing and found nothing are different results.

    The old output said `no suppression pragmas anywhere` for both, and a
    reader takes that as a clean bill. Measured 2026-08-28 over skid, which is
    Python: the Go-only scan printed exactly that and exited 0 while five
    registered pragmas sat in the tree.

    It fails rather than warns on this repository's own decision that a task
    which cannot fail is worse than an absent one.
    """
    (tmp_path / "README.md").write_text("Prose, and no source.\n", encoding="utf-8")
    code, out = checker(register_checker, ARGV, tmp_path)
    assert code == 1
    assert "read nothing" in out


# COVERS: FR-5.1 | positive
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


# COVERS: FR-5.1 | negative
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


# COVERS: FR-5.1 | negative
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


# COVERS: FR-5.2 | edge
def test_a_second_pragma_in_a_registered_file_fails(checker, tmp_path):
    """The count is the comparison: one registered pragma does not cover two."""
    tree = project(
        tmp_path,
        "Register.\n\n  main.go   #nosec G304\n",
        main_go=(
            "package main\n\n"
            "func a() { open(p) } //#nosec G304\n"
            "func b() { open(q) } //#nosec G304\n"
        ),
    )
    code, out = checker(register_checker, ARGV, tree)
    assert code == 1
    assert "the source carries 2, the register says 1" in out


# COVERS: FR-5.3 | negative
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


# COVERS: FR-5.4 | regression
def test_a_python_pragma_is_seen_and_must_be_registered(checker, tmp_path):
    """The defect this test used to PIN is fixed, so the test is inverted.

    It read `*.go` only, so a Python project's `# nosec` was not
    silenced-and-justified but silenced and unseen, and the gate reported a
    pass. Measured 2026-08-28 in skid: `no suppression pragmas anywhere`, exit
    0, over a tree holding five registered ones.

    Kept as a regression rather than deleted, because the failure it describes
    was invisible from toolbox: this repository is Go-free and Python-only, so
    the checker's own suite could pass forever while the shipped behaviour was
    wrong in every adopter.
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


# COVERS: FR-5.2 | regression
def test_a_pragma_in_a_script_with_no_extension_is_seen(checker, tmp_path):
    """Selecting by extension is the fault this checker sat beside.

    `silo/bin/board` and `dotfiles/home/.git-hooks/no-ai-attribution` are shell
    with no suffix, and the second is 170 lines enforcing a hard rule. A
    shebang says what a file is where an extension does not.
    """
    tree = tmp_path
    (tree / "SUPPRESSIONS").write_text("Register.\n", encoding="utf-8")
    hook = tree / "hook"
    hook.write_text(
        "#!/usr/bin/env bash\n# shellcheck disable=SC2086\necho $x\n", encoding="utf-8"
    )
    code, out = checker(register_checker, ARGV, tree)
    assert code == 1
    assert "hook" in out
    assert "SC2086" in out


# COVERS: FR-5.2 | regression
def test_prose_about_a_pragma_is_not_a_pragma(checker, tmp_path):
    """A pragma IS a comment, so no rule about strings separates the two.

    Position does: a real pragma opens its comment, and prose mentions the
    spelling mid-sentence. Without this the checker fails on its own source and
    its own fixtures, which is the tool being graded as a use of itself.
    Measured 2026-08-28: 28 findings in toolbox, none of them a suppression.
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


# COVERS: FR-5.2 | regression
def test_a_pragma_after_a_comment_marker_is_still_a_pragma(checker, tmp_path):
    """`// #nosec G304 -- reason` is how palette-print writes every one of its.

    Requiring the pragma AT the comment opener missed three genuine Go
    suppressions there, which is the false-negative direction: it turns a gate
    green. The pragma may open the comment or be the first thing inside it.
    """
    tree = tmp_path
    (tree / "SUPPRESSIONS").write_text("Register.\n", encoding="utf-8")
    (tree / "load.go").write_text(
        "package main\n\n// #nosec G304 -- the path is the user's own\n"
        "func read() { open(p) }\n",
        encoding="utf-8",
    )
    code, out = checker(register_checker, ARGV, tree)
    assert code == 1
    assert "G304" in out


# ---- the wiring -------------------------------------------------------------


# COVERS: NFR-3 | positive
def test_the_script_runs_as_a_script(tmp_path):
    """In-process tests cannot catch a broken shebang or a missing import."""
    (tmp_path / "SUPPRESSIONS").write_text("Register.\n", encoding="utf-8")
    (tmp_path / "main.go").write_text(
        "package main\n\nfunc read() { open(p) } //#nosec G304\n", encoding="utf-8"
    )
    result = subprocess.run(
        [sys.executable, str(ROOT / "bin" / "suppression-register.py"), *ARGV],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1, result.stderr
    assert "main.go" in result.stdout


# ---- a directory of suppressions --------------------------------------------


DIR_ARGV = ["--register", "SUPPRESSIONS", "."]


# COVERS: FR-5.5 | positive
def test_a_directory_register_totals_what_one_document_totals(checker, tmp_path):
    """One file per suppression is the same register, written differently."""
    entries = tmp_path / "SUPPRESSIONS"
    (entries / "a").mkdir(parents=True)
    (entries / "b").mkdir(parents=True)
    (entries / "a" / "one.md").write_text(
        "# One\n\n    one.go   //nolint:errcheck\n", encoding="utf-8"
    )
    (entries / "b" / "two.md").write_text(
        "# Two\n\n    two.go   //nolint:errcheck\n", encoding="utf-8"
    )
    for name in ("one.go", "two.go"):
        (tmp_path / name).write_text(
            "package main\n\nfunc f() { g() } //nolint:errcheck\n", encoding="utf-8"
        )
    code, out = checker(register_checker, DIR_ARGV, tmp_path)
    assert code == 0, out
    assert "2 pragma(s)" in out


# COVERS: FR-5.5 | negative
def test_a_directory_register_still_fails_an_unregistered_pragma(checker, tmp_path):
    """Splitting the register may not soften either direction of the check."""
    entries = tmp_path / "SUPPRESSIONS" / "a"
    entries.mkdir(parents=True)
    (entries / "one.md").write_text(
        "# One\n\n    one.go   //nolint:errcheck\n", encoding="utf-8"
    )
    for name in ("one.go", "two.go"):
        (tmp_path / name).write_text(
            "package main\n\nfunc f() { g() } //nolint:errcheck\n", encoding="utf-8"
        )
    code, out = checker(register_checker, DIR_ARGV, tmp_path)
    assert code == 1
    assert "two.go" in out


# COVERS: FR-2.3 | negative
def test_an_unreadable_register_reports_why_and_does_not_raise(checker, tmp_path):
    """Absent and unreadable are different, and neither is a traceback."""
    (tmp_path / "SUPPRESSIONS").write_text(
        "# Register\n\n    main.go   //nolint:errcheck\n", encoding="utf-8"
    )
    (tmp_path / "main.go").write_text(
        "package main\n\nfunc f() { g() } //nolint:errcheck\n", encoding="utf-8"
    )
    (tmp_path / "SUPPRESSIONS").chmod(0o000)
    try:
        code, out = checker(register_checker, ARGV, tmp_path)
    finally:
        (tmp_path / "SUPPRESSIONS").chmod(0o644)
    assert code == 1
    assert "cannot be read" in out


# ---- trees this project is not answerable for -------------------------------


# COVERS: FR-2.5 | regression
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
        path.write_text(
            "package main\n\nfunc f() { g() } //nolint:errcheck\n", encoding="utf-8"
        )
    # The project's own file, carrying nothing. Without it this tree holds no
    # readable source at all, and the run fails for having read nothing rather
    # than passing for having correctly skipped what it should skip. The two
    # outcomes agreed before that distinction existed, which is why the fixture
    # did not need it.
    (tmp_path / "main.go").write_text("package main\n\nfunc main() {}\n", "utf-8")
    code, out = checker(register_checker, ARGV, tmp_path)
    assert code == 0, out
    assert "no suppression pragmas in 1 source file(s)" in out


# COVERS: FR-2.5 | positive
def test_the_projects_own_pragma_is_still_found(checker, tmp_path):
    """The skip list may not swallow the thing the check exists for."""
    vendored = tmp_path / "vendor" / "v.go"
    vendored.parent.mkdir(parents=True)
    vendored.write_text(
        "package main\n\nfunc f() { g() } //nolint:errcheck\n", encoding="utf-8"
    )
    (tmp_path / "main.go").write_text(
        "package main\n\nfunc h() { i() } //nolint:errcheck\n", encoding="utf-8"
    )
    code, out = checker(register_checker, ARGV, tmp_path)
    assert code == 1
    assert "1 pragma(s)" in out


# COVERS: FR-2.5 | property
def test_both_checkers_skip_the_same_directories():
    """Two copies of one list, in scripts that share no module.

    They are loaded by path, so neither can import the other, and the list in
    each is free to drift from the other. A tree skipped by one checker and
    walked by the other is the kind of difference nobody looks for.
    """
    traceability = load("bin/test-traceability.py")
    assert register_checker.SKIP_DIRS == traceability.SKIP_DIRS, (
        "bin/suppression-register.py and bin/test-traceability.py disagree about "
        f"which trees to skip: {register_checker.SKIP_DIRS ^ traceability.SKIP_DIRS}"
    )
