"""Tests for `bin/shell-files.py`, the shell jig's selector."""

from __future__ import annotations

import io
import subprocess  # nosec B404
import sys

import pytest
import yaml
from conftest import ROOT, load, script_argv

shell_files = load("bin/shell-files.py")

JIG = ROOT / "bolt.shell-std-quality.yaml"


def select(monkeypatch, capsys, tree, names, *argv):
    """Hand the selector these paths, NUL-separated, from inside the tree: exit code, chosen paths, stderr."""
    monkeypatch.chdir(tree)
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO("".join(f"{n}\0" for n in names).encode())))
    out = io.BytesIO()
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(out))
    code = shell_files.main(list(argv))
    sys.stdout.flush()
    chosen = [name for name in out.getvalue().decode().split("\0") if name]
    return code, chosen, capsys.readouterr().err


def write(tree, files):
    """Create each file with its content."""
    for name, text in files.items():
        path = tree / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


# COVERS FR-11.1 | positive
def test_extension_name_and_shebang_each_make_a_shell_file(monkeypatch, capsys, tmp_path):
    """A `.sh`, a `.zshrc`, and three scripts with no extension whose shebangs name a shell."""
    write(
        tmp_path,
        {
            "install.sh": "echo hi\n",
            "home/.zshrc": "setopt x\n",
            "bin/infobot": "#!/usr/bin/env bash\necho\n",
            "bin/plain": "#!/bin/sh\necho\n",
            "home/.git-hooks/commit-msg": "#!/usr/bin/env -S bash -e\necho\n",
        },
    )
    names = ["install.sh", "home/.zshrc", "bin/infobot", "bin/plain", "home/.git-hooks/commit-msg"]

    code, chosen, err = select(monkeypatch, capsys, tmp_path, names)

    assert code == 0 and chosen == names
    assert "5 selected" in err


# COVERS FR-11.1 | negative
def test_other_files_symlinks_and_missing_paths_are_not_shell(monkeypatch, capsys, tmp_path):
    """Python, a README, a link to a shell script and a path that does not exist are all left alone."""
    write(tmp_path, {"run.sh": "echo\n", "tool.py": "#!/usr/bin/env python3\n", "README.md": "# r\n"})
    (tmp_path / "linked.sh").symlink_to(tmp_path / "run.sh")

    code, chosen, _ = select(monkeypatch, capsys, tmp_path, ["run.sh", "tool.py", "README.md", "linked.sh", "gone.sh"])

    assert code == 0 and chosen == ["run.sh"]


# COVERS FR-11.1 | edge
def test_a_name_holding_a_space_or_a_newline_survives(monkeypatch, capsys, tmp_path):
    """Paths travel NUL-separated both ways."""
    write(tmp_path, {"two words.sh": "echo\n", "new\nline.sh": "echo\n"})

    _, chosen, _ = select(monkeypatch, capsys, tmp_path, ["two words.sh", "new\nline.sh"])

    assert chosen == ["two words.sh", "new\nline.sh"]


# COVERS FR-11.2 | negative
def test_no_shell_file_at_all_fails(monkeypatch, capsys, tmp_path):
    """A shell jig over a project holding no shell would otherwise pass having read nothing."""
    write(tmp_path, {"tool.py": "print()\n"})

    code, chosen, err = select(monkeypatch, capsys, tmp_path, ["tool.py"])

    assert code == 1 and chosen == []
    assert "nothing for a shell jig to read" in err


# COVERS FR-11.3 | positive
def test_zsh_is_left_out_for_shellcheck_and_counted(monkeypatch, capsys, tmp_path):
    """shellcheck cannot parse zsh, so it is not handed any, and the count says how many."""
    write(tmp_path, {"a.sh": "echo\n", "b.zsh": "echo\n", "bin/z": "#!/bin/zsh\necho\n"})

    code, chosen, err = select(monkeypatch, capsys, tmp_path, ["a.sh", "b.zsh", "bin/z"], "--for", "shellcheck")

    assert code == 0 and chosen == ["a.sh"]
    assert "1 selected, 2 left out that shellcheck cannot parse" in err


# COVERS FR-11.3 | edge
def test_a_project_of_zsh_alone_passes_lint_with_nothing_selected(monkeypatch, capsys, tmp_path):
    """Everything left out is not nothing found, so the selector does not fail."""
    write(tmp_path, {"home/.zshrc": "setopt x\n"})

    code, chosen, err = select(monkeypatch, capsys, tmp_path, ["home/.zshrc"], "--for", "shellcheck")

    assert code == 0 and chosen == []
    assert "0 selected, 1 left out" in err


# COVERS FR-11.4 | property
def test_no_shell_jig_task_pipes_its_steps():
    """A pipeline's status is its last command's, so a selector failing mid-pipe would be hidden."""
    tasks = yaml.safe_load(JIG.read_text(encoding="utf-8"))["tasks"]
    assert tasks, "the jig has no tasks, so the rule is untested"
    for task in tasks:
        command = task["command"]
        assert "|" not in command, f"{task['name']} pipes its steps"
        assert "shell-files.py" in command and "&&" in command, f"{task['name']} does not select through the selector"


# COVERS FR-11.1 | positive
def test_the_script_runs_by_path(tmp_path):
    """Spawned as the jig spawns it, with paths on stdin."""
    write(tmp_path, {"run.sh": "echo\n"})

    result = subprocess.run(script_argv(ROOT / "bin" / "shell-files.py"), cwd=tmp_path, input=b"run.sh\0", capture_output=True, check=False)  # nosec B603

    assert result.returncode == 0 and result.stdout == b"run.sh\0"


# COVERS FR-11.1 | edge
@pytest.mark.parametrize("first", ["#!/usr/bin/env python3\n", "#!/bin/bashful\n", "no shebang\n"])
def test_a_shebang_naming_no_shell_is_not_shell(monkeypatch, capsys, tmp_path, first):
    """python3, a program merely starting with `bash`, and no shebang at all."""
    write(tmp_path, {"bin/x": first, "keep.sh": "echo\n"})

    _, chosen, _ = select(monkeypatch, capsys, tmp_path, ["bin/x", "keep.sh"])

    assert chosen == ["keep.sh"]
