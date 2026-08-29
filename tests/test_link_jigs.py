"""Tests for `bin/link-jigs.py`.

The script writes into someone else's repository, so most of what follows pins
what it refuses to do: overwrite a real file, write through a link that leaves
the project, act on a manifest naming something that is not here, or assume
consent when there is no terminal to ask at.

The other half is that the state it reports is the state on disk. A link that
is present and correct must be distinguishable from one pointing at the wrong
file, because `--check` is the form this grows into as a jig task.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from conftest import load

link_jigs = load("bin/link-jigs.py")

MANIFEST = """
version: 1
sets:
  common:
    files:
      - bolt.common-quality.yaml
      - bin/checker.py
  go:
    includes: [common]
    files:
      - bolt.go-std-quality.yaml
      - adapters/go/gofmt.py
  lone:
    files:
      - bolt.secrets.yaml
"""

EVERY = (
    "bolt.common-quality.yaml",
    "bin/checker.py",
    "bolt.go-std-quality.yaml",
    "adapters/go/gofmt.py",
    "bolt.secrets.yaml",
)


def toolbox(tmp_path: Path, files: Sequence[str] = EVERY, manifest: str = MANIFEST) -> Path:
    """Build a repository holding a manifest and the files it names."""
    root = tmp_path / "toolbox"
    root.mkdir(exist_ok=True)
    (root / "jigs.yaml").write_text(manifest, encoding="utf-8")
    for name in files:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {name}\n", encoding="utf-8")
    return root


def project(tmp_path: Path) -> Path:
    """An empty target for the links to land in."""
    target = tmp_path / "project"
    target.mkdir(exist_ok=True)
    return target


def argv(root: Path, target: Path, *rest: str) -> list[str]:
    """The command line, with the manifest pointed at the fake toolbox."""
    return [str(target), *rest, "--manifest", str(root / "jigs.yaml")]


# ---- what it links ----------------------------------------------------------


# COVERS: FR-7.1 | property
def test_entries_land_at_the_same_relative_path(checker, tmp_path):
    """A file at bin/checker.py here is at bin/checker.py there, or config_dir breaks."""
    root, target = toolbox(tmp_path), project(tmp_path)
    code, _ = checker(link_jigs, argv(root, target, "go", "--yes"), tmp_path)
    assert code == 0
    assert (target / "bin/checker.py").is_symlink()
    assert (target / "bin/checker.py").read_text(encoding="utf-8") == "# bin/checker.py\n"


# COVERS: FR-7.2 | positive
def test_includes_are_followed(checker, tmp_path):
    """Adopting go brings common with it, because go's definition overlays it."""
    root, target = toolbox(tmp_path), project(tmp_path)
    checker(link_jigs, argv(root, target, "go", "--yes"), tmp_path)
    assert (target / "bolt.common-quality.yaml").is_symlink()
    assert (target / "bolt.go-std-quality.yaml").is_symlink()


# COVERS: FR-7.2 | edge
def test_a_set_without_includes_stands_alone(checker, tmp_path):
    """`secrets` needs nothing else to be true of a repository, so it pulls nothing."""
    root, target = toolbox(tmp_path), project(tmp_path)
    checker(link_jigs, argv(root, target, "lone", "--yes"), tmp_path)
    assert (target / "bolt.secrets.yaml").is_symlink()
    assert not (target / "bolt.common-quality.yaml").exists()


# COVERS: FR-7.4 | property
def test_links_are_relative_so_the_pair_can_move(checker, tmp_path):
    """An absolute link encodes one machine's layout; the default must not."""
    root, target = toolbox(tmp_path), project(tmp_path)
    checker(link_jigs, argv(root, target, "lone", "--yes"), tmp_path)
    assert not Path((target / "bolt.secrets.yaml").readlink()).is_absolute()


# COVERS: FR-7.4 | edge
def test_absolute_is_available_for_a_toolbox_that_does_not_travel(checker, tmp_path):
    """A shared toolbox at a fixed path wants the link to say so."""
    root, target = toolbox(tmp_path), project(tmp_path)
    checker(link_jigs, argv(root, target, "lone", "--absolute", "--yes"), tmp_path)
    assert Path((target / "bolt.secrets.yaml").readlink()).is_absolute()


# ---- what it refuses --------------------------------------------------------


# COVERS: FR-7.5 | negative
def test_a_real_file_is_never_overwritten(checker, tmp_path):
    """A vendored copy predates adoption; deleting it is mine to decide."""
    root, target = toolbox(tmp_path), project(tmp_path)
    vendored = target / "bolt.secrets.yaml"
    vendored.write_text("mine\n", encoding="utf-8")
    code, out = checker(link_jigs, argv(root, target, "lone", "--yes"), tmp_path)
    assert code == 1
    assert "in the way" in out
    assert vendored.read_text(encoding="utf-8") == "mine\n"
    assert not vendored.is_symlink()


# COVERS: FR-7.6 | negative
def test_a_manifest_naming_an_absent_file_links_nothing(checker, tmp_path):
    """Manifest rot surfaces here rather than as a dangling link in another repo."""
    root = toolbox(tmp_path, files=("bolt.secrets.yaml",))
    target = project(tmp_path)
    code, out = checker(link_jigs, argv(root, target, "go", "--yes"), tmp_path)
    assert code == 1
    assert "not here" in out
    assert not any(target.iterdir())


# COVERS: FR-7.7 | negative
def test_an_unknown_set_names_the_ones_that_exist(checker, tmp_path):
    """A typo should print the menu, not a traceback."""
    root, target = toolbox(tmp_path), project(tmp_path)
    code, out = checker(link_jigs, argv(root, target, "rust", "--yes"), tmp_path)
    assert code == 1
    assert "no set named 'rust'" in out
    assert "common" in out and "go" in out


# COVERS: FR-7.8 | negative
def test_sets_that_include_each_other_are_refused(checker, tmp_path):
    """A cycle is a manifest error, and must not be an infinite walk."""
    cyclic = "version: 1\nsets:\n  a:\n    includes: [b]\n  b:\n    includes: [a]\n"
    root = toolbox(tmp_path, files=(), manifest=cyclic)
    code, out = checker(link_jigs, argv(root, project(tmp_path), "a"), tmp_path)
    assert code == 1
    assert "cycle" in out


# COVERS: FR-7.9 | edge
def test_no_terminal_and_no_yes_writes_nothing(checker, tmp_path):
    """Consent is asked for or declared, never assumed from a pipe."""
    root, target = toolbox(tmp_path), project(tmp_path)
    code, out = checker(link_jigs, argv(root, target, "lone"), tmp_path)
    assert code == 1
    assert "--yes" in out
    assert not (target / "bolt.secrets.yaml").exists()


# ---- what it reports --------------------------------------------------------


# COVERS: FR-7.10 | property
def test_running_twice_changes_nothing(checker, tmp_path):
    """Idempotent, and says so rather than relinking what is already right."""
    root, target = toolbox(tmp_path), project(tmp_path)
    checker(link_jigs, argv(root, target, "go", "--yes"), tmp_path)
    code, out = checker(link_jigs, argv(root, target, "go", "--yes"), tmp_path)
    assert code == 0
    assert "present and correct" in out


# COVERS: FR-7.11 | negative
def test_check_fails_on_a_missing_link_and_writes_nothing(checker, tmp_path):
    """`--check` is the form this grows into as a jig task, so drift must exit 1."""
    root, target = toolbox(tmp_path), project(tmp_path)
    code, _ = checker(link_jigs, argv(root, target, "go", "--check"), tmp_path)
    assert code == 1
    assert not any(target.iterdir())


# COVERS: FR-7.11 | positive
def test_check_passes_once_the_links_are_there(checker, tmp_path):
    """The same command that fails on drift confirms a project that is set up."""
    root, target = toolbox(tmp_path), project(tmp_path)
    checker(link_jigs, argv(root, target, "go", "--yes"), tmp_path)
    code, out = checker(link_jigs, argv(root, target, "go", "--check"), tmp_path)
    assert code == 0
    assert "present and correct" in out


# COVERS: FR-7.12 | edge
def test_a_link_pointing_at_the_wrong_file_is_repaired(checker, tmp_path):
    """A stale link is drift, not absence, and reads as a working path until followed."""
    root, target = toolbox(tmp_path), project(tmp_path)
    (target / "bolt.secrets.yaml").symlink_to(root / "bolt.common-quality.yaml")
    code, _ = checker(link_jigs, argv(root, target, "lone", "--yes"), tmp_path)
    assert code == 0
    assert (target / "bolt.secrets.yaml").resolve() == (root / "bolt.secrets.yaml")


# COVERS: FR-7.12 | edge
def test_a_link_left_behind_by_a_dropped_set_is_found(checker, tmp_path):
    """Dropping go must not leave adapters/go/gofmt.py linked and unmentioned."""
    root, target = toolbox(tmp_path), project(tmp_path)
    checker(link_jigs, argv(root, target, "go", "--yes"), tmp_path)
    code, out = checker(link_jigs, argv(root, target, "lone", "--check"), tmp_path)
    assert code == 1
    assert "no longer in any adopted set" in out
    assert "gofmt.py" in out


# COVERS: FR-7.13 | positive
def test_plan_says_what_would_happen_and_stops(checker, tmp_path):
    """Enumerate, then act: the shape `bolt plan` already has."""
    root, target = toolbox(tmp_path), project(tmp_path)
    code, out = checker(link_jigs, argv(root, target, "go", "--plan"), tmp_path)
    assert code == 0
    assert "to link" in out
    assert not any(target.iterdir())
