"""Tests for `bin/clang-format-check.py`.

clang-format is never installed for these. A stand-in script takes its place
through `--clang-format` and exits 1 for a file holding the word `BAD`, which is
the only thing the checker reads from it. That keeps NFR-1: the suite runs where
none of the tools a jig names exist.
"""

from __future__ import annotations

import json
import subprocess  # nosec B404
from pathlib import Path

from conftest import ROOT, load, script_argv

formatting = load("bin/clang-format-check.py")

STYLE = "BasedOnStyle: LLVM\n"
FAKE = """#!/bin/sh
for arg in "$@"; do last=$arg; done
if grep -q BAD "$last"; then
  echo "$last: would reformat" >&2
  exit 1
fi
exit 0
"""


def fake_clang_format(tmp_path: Path) -> Path:
    """A stand-in that fails a file holding BAD, the way clang-format fails an unformatted one."""
    path = tmp_path / "clang-format"
    path.write_text(FAKE, encoding="utf-8")
    path.chmod(0o755)
    return path


def project(tmp_path: Path, files: dict[str, str], style: str | None = STYLE) -> Path:
    """A tree with a compilation database naming its sources, and a style file unless told otherwise."""
    tree = tmp_path / "project"
    (tree / "src").mkdir(parents=True)
    entries = []
    for name, text in files.items():
        (tree / name).parent.mkdir(parents=True, exist_ok=True)
        (tree / name).write_text(text, encoding="utf-8")
        entries.append({"directory": str(tree), "file": name, "command": f"c++ -c {name}"})
    (tree / "compile_commands.json").write_text(json.dumps(entries), encoding="utf-8")
    if style is not None:
        (tree / ".clang-format").write_text(style, encoding="utf-8")
    return tree


def run(tree: Path, tmp_path: Path, *extra: str) -> tuple[int, str]:
    """The checker over a tree, with the stand-in in place of clang-format."""
    argv = [
        "--style",
        str(tree / ".clang-format"),
        "--database",
        str(tree / "compile_commands.json"),
        "--base",
        str(tree),
        "--clang-format",
        str(fake_clang_format(tmp_path)),
        *extra,
    ]
    return formatting.main(argv), ""


# COVERS: FR-2.1 | positive
def test_a_formatted_tree_exits_zero(tmp_path, capsys):
    """Every file in the database is formatted, so the checker exits 0 and says so."""
    tree = project(tmp_path, {"src/a.cpp": "int a() { return 1; }\n", "src/b.cpp": "int b() { return 2; }\n"})

    code, _ = run(tree, tmp_path)

    assert code == 0
    assert "2/2 formatted" in capsys.readouterr().err


# COVERS: FR-2.2 | negative
def test_each_unformatted_file_is_named_on_stdout(tmp_path, capsys):
    """A finding nobody can locate is a finding nobody acts on, so every path is printed."""
    tree = project(tmp_path, {"src/a.cpp": "int a() { return 1; }\n", "src/bad.cpp": "int BAD() {}\n"})

    code, _ = run(tree, tmp_path)
    captured = capsys.readouterr()

    assert code == 1
    assert captured.out.strip().endswith("src/bad.cpp")
    assert "1/2 formatted" in captured.err


# COVERS: FR-2.3 | negative
def test_an_absent_database_or_style_fails_with_an_instruction(tmp_path, capsys):
    """The adopter who has not produced a database is the reader most needing to be told how."""
    tree = project(tmp_path, {"src/a.cpp": "int a() { return 1; }\n"})
    (tree / "compile_commands.json").unlink()

    assert formatting.main(["--style", str(tree / ".clang-format"), "--database", str(tree / "compile_commands.json")]) == 1
    assert "bear --" in capsys.readouterr().err

    tree = project(tmp_path / "second", {"src/a.cpp": "int a() { return 1; }\n"}, style=None)
    assert run(tree, tmp_path)[0] == 1
    assert "no clang-format configuration" in capsys.readouterr().err


# COVERS: FR-2.4 | negative
def test_a_database_naming_nothing_is_refused_rather_than_passed(tmp_path, capsys):
    """An empty database passes every per-file check in the jig, so it cannot read as success."""
    tree = project(tmp_path, {})

    code, _ = run(tree, tmp_path)

    assert code == 1
    assert "named no files to check" in capsys.readouterr().err


# COVERS: FR-2.5 | negative
def test_an_exclusion_matches_the_project_relative_path(tmp_path, capsys):
    """A tree living under a directory the exclusion names must not exclude itself.

    The absolute path is what a compilation database records, and matching an
    exclusion against it once emptied a fixture's own database.
    """
    tree = project(tmp_path, {"src/a.cpp": "int a() { return 1; }\n", ".ephemera/scratch.cpp": "int BAD() {}\n"})

    code, _ = run(tree, tmp_path, "--exclude", r"(^|/)\.ephemera/")

    assert code == 0
    assert "1/1 formatted" in capsys.readouterr().err


# COVERS: FR-2.2 | edge
def test_a_file_named_twice_is_reported_once(tmp_path, capsys):
    """A database names a file once per configuration, and formatting is a property of the text."""
    tree = project(tmp_path, {"src/bad.cpp": "int BAD() {}\n"})
    entries = json.loads((tree / "compile_commands.json").read_text(encoding="utf-8"))
    (tree / "compile_commands.json").write_text(json.dumps(entries * 3), encoding="utf-8")

    code, _ = run(tree, tmp_path)
    captured = capsys.readouterr()

    assert code == 1
    assert captured.out.count("bad.cpp") == 1
    assert "0/1 formatted" in captured.err


# COVERS: FR-2.5 | edge
def test_a_source_compiled_from_outside_the_tree_is_not_the_projects_to_format(tmp_path, capsys):
    """A generated source in a build directory elsewhere belongs to whoever generated it."""
    tree = project(tmp_path, {"src/a.cpp": "int a() { return 1; }\n"})
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (outside / "generated.cpp").write_text("int BAD() {}\n", encoding="utf-8")
    entries = json.loads((tree / "compile_commands.json").read_text(encoding="utf-8"))
    entries.append({"directory": str(outside), "file": "generated.cpp", "command": "c++ -c generated.cpp"})
    (tree / "compile_commands.json").write_text(json.dumps(entries), encoding="utf-8")

    code, _ = run(tree, tmp_path)

    assert code == 0
    assert "1/1 formatted" in capsys.readouterr().err


# COVERS: NFR-3 | positive
def test_the_script_runs_by_path(tmp_path):
    """Spawned as bolt spawns it: the shebang, the imports and the exit status."""
    tree = project(tmp_path, {"src/bad.cpp": "int BAD() {}\n"})
    argv = script_argv(
        ROOT / "bin" / "clang-format-check.py",
        "--style",
        str(tree / ".clang-format"),
        "--database",
        str(tree / "compile_commands.json"),
        "--base",
        str(tree),
        "--clang-format",
        str(fake_clang_format(tmp_path)),
    )

    result = subprocess.run(argv, capture_output=True, text=True, check=False)  # nosec B603

    assert result.returncode == 1
    assert "bad.cpp" in result.stdout
