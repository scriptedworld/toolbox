"""Tests for `bin/tool-versions.py`.

The tools a jig names are not installed where the suite runs (NFR-1), so the
version reports come from small `sh` scripts placed on a PATH of the test's own.
"""

from __future__ import annotations

import subprocess  # nosec B404
from pathlib import Path

import pytest
import yaml
from conftest import ROOT, load, script_argv

versions = load("bin/tool-versions.py")


def jig(tmp_path: Path, *tools: str) -> Path:
    """A jig naming these tools under `requires:`, with a comment between two of them."""
    entries = "".join(f"  - {tool}\n" for tool in tools)
    path = tmp_path / "bolt.fixture.yaml"
    path.write_text(f'version: "1.0.0"\n\nrequires:\n  # a note\n{entries}\ntasks: []\n', encoding="utf-8")
    return path


def tool(bin_dir: Path, name: str, body: str) -> None:
    """An executable `sh` script standing in for a tool."""
    bin_dir.mkdir(exist_ok=True)
    path = bin_dir / name
    path.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    path.chmod(0o755)


def run(monkeypatch, capsys, tmp_path, *tools: str) -> tuple[int, str]:
    """main() over a fixture jig, with only the test's own tools on PATH."""
    monkeypatch.setenv("PATH", f"{tmp_path / 'bin'}:/usr/bin:/bin")
    code = versions.main([str(jig(tmp_path, *tools))])
    return code, capsys.readouterr().out


# COVERS FR-1.8 | positive
def test_each_tool_is_recorded_by_its_version_line(monkeypatch, capsys, tmp_path):
    """A banner line is skipped for the one carrying the number, and the named line wins over the first."""
    tool(tmp_path / "bin", "lint", 'printf "Lint - a linter\\nversion: 0.11.0\\n"')
    tool(tmp_path / "bin", "scan", '[ "$1" = "-version" ] && printf "Go: go1.27.1\\nScanner: scan@v1.8.0\\n" || exit 2')

    code, out = run(monkeypatch, capsys, tmp_path, "lint", "scan")

    assert code == 0, out
    assert "lint: version: 0.11.0" in out and "scan: Scanner: scan@v1.8.0" in out


# COVERS FR-1.8 | negative
def test_a_tool_not_on_path_fails_the_task(monkeypatch, capsys, tmp_path):
    """A required tool that is absent is the one thing this records as a failure."""
    tool(tmp_path / "bin", "lint", "echo lint 1.0")

    code, out = run(monkeypatch, capsys, tmp_path, "lint", "nowhere-tool")

    assert code == 1
    assert "nowhere-tool: NOT FOUND on PATH" in out and "lint: lint 1.0" in out


# COVERS FR-1.8 | edge
def test_a_tool_answering_no_flag_is_recorded_by_its_digest(monkeypatch, capsys, tmp_path):
    """bolt has no version flag, and it still has to be identified."""
    tool(tmp_path / "bin", "mute", "exit 1")

    code, out = run(monkeypatch, capsys, tmp_path, "mute")

    assert code == 0
    assert "mute: no version flag; sha256 " in out and str(tmp_path / "bin" / "mute") in out


# COVERS FR-1.8 | edge
def test_gofmt_is_recorded_by_the_toolchain_that_ships_it(monkeypatch, capsys, tmp_path):
    """gofmt has no version of its own, so `go version` speaks for it."""
    tool(tmp_path / "bin", "gofmt", "exit 2")
    tool(tmp_path / "bin", "go", '[ "$1" = "version" ] && echo "go version go1.27.1 linux/amd64" || exit 2')

    code, out = run(monkeypatch, capsys, tmp_path, "gofmt")

    assert code == 0
    assert "gofmt: ships with go version go1.27.1" in out


# COVERS FR-1.8 | edge
def test_a_cargo_subcommand_is_asked_with_its_own_name_first(monkeypatch, capsys, tmp_path):
    """`cargo-llvm-cov --version` is refused; `cargo-llvm-cov llvm-cov --version` answers."""
    tool(tmp_path / "bin", "cargo-llvm-cov", '[ "$1 $2" = "llvm-cov --version" ] && echo "cargo-llvm-cov 0.9.1" || exit 1')

    code, out = run(monkeypatch, capsys, tmp_path, "cargo-llvm-cov")

    assert code == 0
    assert "cargo-llvm-cov: cargo-llvm-cov 0.9.1" in out


# COVERS FR-1.8 | negative
def test_a_jig_naming_no_tools_is_refused(capsys, tmp_path):
    """Recording nothing is not a pass."""
    assert versions.main([str(jig(tmp_path))]) == 2
    assert "names no tools" in capsys.readouterr().out


# COVERS FR-1.8 | property
@pytest.mark.parametrize(
    "path",
    sorted(path for path in ROOT.glob("bolt.*.yaml") if not path.name.endswith(".definitions.yaml")),
    ids=lambda path: path.name,
)
def test_every_jig_records_its_versions_first(path):
    """The first task runs the recorder over the jig's own file, so every name in `requires:` is recorded."""
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    first = document["tasks"][0]
    assert first["name"] == "versions"
    assert first["command"] == f"python3 {{config_dir}}/bin/tool-versions.py {{config_dir}}/{path.name}"
    assert versions.required(path) == document["requires"], "the line reader and YAML disagree on requires"


# COVERS NFR-3 | positive
def test_the_script_runs_as_a_script(tmp_path):
    """Spawned the way the jig spawns it, over a jig needing only the interpreter and git."""
    result = subprocess.run(script_argv(ROOT / "bin" / "tool-versions.py", str(jig(tmp_path, "git"))), capture_output=True, text=True, check=False)  # nosec B603

    assert result.returncode == 0, result.stdout
    assert result.stdout.startswith("git: git version")
