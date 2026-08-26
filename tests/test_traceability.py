"""Tests for `bin/test-traceability.py`.

The checker fails in two directions: a test that does not say what it
discharges, and a requirement no test cites. The second is exempt only when the
requirement's row marks it `[?]`, and most of what follows pins that boundary,
because a gate that exempts too much is indistinguishable from no gate at all.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from conftest import ROOT, load

traceability = load("bin/test-traceability.py")

ARGV = ["--requirements", "REQUIREMENTS.md", "."]

HEADER = "# Fixture\n\n| ID | Requirement | |\n|---|---|---|\n"


def requirements(*rows: tuple[str, str]) -> str:
    """Build a requirements document from (id, marker) pairs."""
    body = "".join(
        f"| {req} | Some requirement. | {marker} |\n" for req, marker in rows
    )
    return HEADER + body


def project(tmp_path: Path, document: str, files: dict[str, str] | None = None) -> Path:
    """Write a requirements document and a tree of sources beside it."""
    (tmp_path / "REQUIREMENTS.md").write_text(document, encoding="utf-8")
    for name, text in (files or {}).items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return tmp_path


# ---- the verdict ------------------------------------------------------------


# COVERS: FR-4.5 | positive
def test_every_settled_requirement_covered_passes(checker, tmp_path):
    """A document whose settled requirements all have tests exits 0 and says so."""
    tree = project(
        tmp_path,
        requirements(("FR-1.1", "[A]"), ("FR-1.2", "[D]")),
        {
            "test_it.py": "# COVERS: FR-1.1, FR-1.2 | positive\ndef test_both():\n    pass\n"
        },
    )
    code, out = checker(traceability, ARGV, tree)
    assert code == 0
    assert "2 of 2" in out


# COVERS: FR-4.5 | negative
def test_uncovered_settled_requirement_fails_and_is_named(checker, tmp_path):
    """An uncovered settled requirement is the failure this change exists for."""
    tree = project(
        tmp_path,
        requirements(("FR-1.1", "[A]"), ("FR-2.1", "[D]")),
        {"test_it.py": "# COVERS: FR-1.1 | positive\ndef test_one():\n    pass\n"},
    )
    code, out = checker(traceability, ARGV, tree)
    assert code == 1
    assert "1 settled requirement(s) have no test" in out
    assert "FR-2.1 [D]" in out


# COVERS: FR-4.6 | edge
def test_uncovered_open_requirement_is_context_not_failure(checker, tmp_path):
    """`[?]` marks a decision that cannot have a test yet, so it does not fail."""
    tree = project(
        tmp_path,
        requirements(("FR-1.1", "[A]"), ("FR-2.1", "[?]")),
        {"test_it.py": "# COVERS: FR-1.1 | positive\ndef test_one():\n    pass\n"},
    )
    code, out = checker(traceability, ARGV, tree)
    assert code == 0
    assert "1 open requirement(s) have no test" in out
    assert "FR-2.1 [?]" in out
    assert "settled requirement(s) have no test" not in out


# COVERS: FR-4.6 | edge
def test_a_row_with_no_marker_claims_no_exemption(checker, tmp_path):
    """Exemption is claimed with `[?]`, never granted by an absent marker column."""
    tree = project(
        tmp_path,
        "# Fixture\n\n| ID | Requirement |\n|---|---|\n| FR-1.1 | Uncovered. |\n",
        {
            "test_it.py": "# COVERS: FR-9.9 | positive\ndef test_nothing_real():\n    pass\n"
        },
    )
    code, out = checker(traceability, ARGV, tree)
    assert code == 1
    assert "FR-1.1 (no marker)" in out


# ---- what a test must say ---------------------------------------------------


# COVERS: FR-4.1 | negative
def test_a_test_without_a_covers_line_fails(checker, tmp_path):
    """The other direction: a test that does not say what it discharges."""
    tree = project(
        tmp_path,
        requirements(("FR-1.1", "[?]")),
        {"test_it.py": "def test_silent():\n    pass\n"},
    )
    code, out = checker(traceability, ARGV, tree)
    assert code == 1
    assert "test_silent" in out
    assert "# COVERS:" in out


# COVERS: FR-4.2 | negative
def test_citing_an_undeclared_requirement_fails(checker, tmp_path):
    """A renamed or deleted requirement fails here rather than rotting in a comment."""
    tree = project(
        tmp_path,
        requirements(("FR-1.1", "[A]")),
        {
            "test_it.py": "# COVERS: FR-1.1, FR-4.4 | positive\ndef test_one():\n    pass\n"
        },
    )
    code, out = checker(traceability, ARGV, tree)
    assert code == 1
    assert "FR-4.4" in out
    assert "does not define" in out


# COVERS: FR-4.3 | negative
def test_an_unknown_kind_fails(checker, tmp_path):
    """The kind says which path through the requirement the test walks."""
    tree = project(
        tmp_path,
        requirements(("FR-1.1", "[A]")),
        {"test_it.py": "# COVERS: FR-1.1 | vibes\ndef test_one():\n    pass\n"},
    )
    code, out = checker(traceability, ARGV, tree)
    assert code == 1
    assert "'vibes'" in out


# COVERS: FR-4.4 | negative
def test_a_covers_line_citing_no_id_at_all_fails(checker, tmp_path):
    """`COVERS: whatever | positive` parses as an annotation and cites nothing."""
    tree = project(
        tmp_path,
        requirements(("FR-1.1", "[?]")),
        {"test_it.py": "# COVERS: the parser | positive\ndef test_one():\n    pass\n"},
    )
    code, out = checker(traceability, ARGV, tree)
    assert code == 1
    assert "cites no requirement id" in out


# ---- the empty cases, where false greens live -------------------------------


# COVERS: FR-2.3 | edge
def test_a_missing_document_fails_without_a_traceback(checker, tmp_path):
    """An adopter with no REQUIREMENTS.md gets an instruction, not a stack trace."""
    code, out = checker(traceability, ARGV, tmp_path)
    assert code == 1
    assert "does not exist" in out
    assert "Traceback" not in out


# COVERS: FR-2.4 | edge
def test_a_document_declaring_nothing_refuses_to_pass(checker, tmp_path):
    """Zero requirements and zero citations agree with each other and mean nothing."""
    tree = project(tmp_path, "# Fixture\n\nProse, and no table.\n")
    code, out = checker(traceability, ARGV, tree)
    assert code == 1
    assert "refusing to pass vacuously" in out


# COVERS: FR-4.5, FR-4.7 | edge
def test_a_tree_with_no_tests_fails_every_settled_requirement(checker, tmp_path):
    """Finding no tests is not the same as finding nothing wrong."""
    tree = project(tmp_path, requirements(("FR-1.1", "[A]"), ("FR-1.2", "[D]")))
    code, out = checker(traceability, ARGV, tree)
    assert code == 1
    assert "2 settled requirement(s) have no test" in out


# ---- finding the tests ------------------------------------------------------


# COVERS: FR-4.7 | positive
def test_go_and_python_tests_are_both_found(checker, tmp_path):
    """The task is in the language-agnostic jig, so it reads both languages."""
    tree = project(
        tmp_path,
        requirements(("FR-1.1", "[A]"), ("FR-1.2", "[D]")),
        {
            "thing_test.go": "// COVERS: FR-1.1 | positive\nfunc TestThing(t *testing.T) {}\n",
            "test_thing.py": "# COVERS: FR-1.2 | positive\ndef test_thing():\n    pass\n",
        },
    )
    code, out = checker(traceability, ARGV, tree)
    assert code == 0, out


# COVERS: FR-4.8 | edge
def test_a_decorator_does_not_hide_the_annotation(checker, tmp_path):
    """A parametrised test keeps its COVERS line above the decorator."""
    tree = project(
        tmp_path,
        requirements(("FR-1.1", "[A]")),
        {
            "test_it.py": (
                "import pytest\n\n\n"
                "# COVERS: FR-1.1 | edge\n"
                '@pytest.mark.parametrize("n", [1, 2])\n'
                "def test_decorated(n):\n    pass\n"
            )
        },
    )
    code, out = checker(traceability, ARGV, tree)
    assert code == 0, out


# COVERS: FR-4.8 | edge
def test_indented_and_async_tests_are_found(checker, tmp_path):
    """A method on a test class and an async test are both tests."""
    tree = project(
        tmp_path,
        requirements(("FR-1.1", "[A]"), ("FR-1.2", "[D]")),
        {
            "test_it.py": (
                "class TestGroup:\n"
                "    # COVERS: FR-1.1 | negative\n"
                "    def test_method(self):\n        pass\n\n\n"
                "# COVERS: FR-1.2 | property\n"
                "async def test_async():\n    pass\n"
            )
        },
    )
    code, out = checker(traceability, ARGV, tree)
    assert code == 0, out


# COVERS: FR-2.5 | edge
def test_someone_elses_tests_are_not_scanned(checker, tmp_path):
    """A virtualenv full of unannotated tests must not fail this project."""
    tree = project(
        tmp_path,
        requirements(("FR-1.1", "[A]")),
        {"test_it.py": "# COVERS: FR-1.1 | positive\ndef test_ours():\n    pass\n"},
    )
    vendored = tree / ".venv" / "lib" / "test_theirs.py"
    vendored.parent.mkdir(parents=True)
    vendored.write_text("def test_not_ours():\n    pass\n", encoding="utf-8")
    code, out = checker(traceability, ARGV, tree)
    assert code == 0, out
    assert "test_not_ours" not in out


# ---- the regression ---------------------------------------------------------


# COVERS: FR-4.9 | regression
def test_a_lettered_requirement_id_sorts_without_raising():
    """FR-4.13a compared against FR-4.13 raised TypeError until 2026-08-20.

    bolt has no lettered id, so bolt could never have found this; qwark's
    FR-4.13a did, on the first run against a second repository.
    """
    ordered = sorted(
        ["FR-4.13", "FR-4.9a", "FR-4.9", "FR-10.1", "NFR-1", "FR-4.13a"],
        key=traceability.requirement_key,
    )
    assert ordered == ["FR-4.9", "FR-4.9a", "FR-4.13", "FR-4.13a", "FR-10.1", "NFR-1"]


# COVERS: FR-4.9 | property
def test_requirements_sort_numerically_not_lexically():
    """FR-7.10 comes after FR-7.3, which a string sort gets backwards."""
    assert traceability.requirement_key("FR-7.3") < traceability.requirement_key(
        "FR-7.10"
    )


# ---- the wiring -------------------------------------------------------------


# COVERS: NFR-3 | positive
def test_the_script_runs_as_a_script(tmp_path):
    """In-process tests cannot catch a broken shebang or an import that fails."""
    (tmp_path / "REQUIREMENTS.md").write_text(
        requirements(("FR-1.1", "[?]")), encoding="utf-8"
    )
    result = subprocess.run(
        [sys.executable, str(ROOT / "bin" / "test-traceability.py"), *ARGV],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "FR-1.1" in result.stdout


# ---- retired requirements ---------------------------------------------------


RETIRED = (
    "\n## Retired\n\n| ID | Retired | Superseded by |\n|---|---|---|\n"
    "| FR-9.9 | 2026-08-26 | FR-1.1, which says it better. |\n"
)


# COVERS: FR-4.10 | positive
def test_a_retired_requirement_is_not_held_to_coverage(checker, tmp_path):
    """It has gone. Holding it to coverage would make retiring one impossible."""
    tree = project(
        tmp_path,
        requirements(("FR-1.1", "[A]")) + RETIRED,
        {"test_it.py": "# COVERS: FR-1.1 | positive\ndef test_one():\n    pass\n"},
    )
    code, out = checker(traceability, ARGV, tree)
    assert code == 0, out
    assert "FR-9.9" not in out


# COVERS: FR-4.10 | negative
def test_citing_a_retired_requirement_says_where_it_went(checker, tmp_path):
    """A bare "does not define" leaves the reader to find the replacement."""
    tree = project(
        tmp_path,
        requirements(("FR-1.1", "[A]")) + RETIRED,
        {
            "test_it.py": (
                "# COVERS: FR-1.1 | positive\ndef test_one():\n    pass\n\n"
                "# COVERS: FR-9.9 | positive\ndef test_two():\n    pass\n"
            )
        },
    )
    code, out = checker(traceability, ARGV, tree)
    assert code == 1
    assert "test_two" in out
    assert "retired" in out
    assert "FR-1.1, which says it better" in out


# COVERS: FR-4.11 | negative
def test_an_id_that_is_both_live_and_retired_fails(checker, tmp_path):
    """Reuse rewrites what every existing reference to that id meant."""
    tree = project(
        tmp_path,
        requirements(("FR-1.1", "[A]"), ("FR-9.9", "[A]")) + RETIRED,
        {
            "test_it.py": (
                "# COVERS: FR-1.1 | positive\ndef test_one():\n    pass\n\n"
                "# COVERS: FR-9.9 | positive\ndef test_two():\n    pass\n"
            )
        },
    )
    code, out = checker(traceability, ARGV, tree)
    assert code == 1
    assert "both live and retired" in out
    assert "FR-9.9" in out


# COVERS: FR-4.11 | edge
def test_reuse_is_reported_before_anything_else(checker, tmp_path):
    """Every other finding is downstream of an id meaning two things at once,
    so reporting them alongside would bury the one that explains them."""
    tree = project(
        tmp_path,
        requirements(("FR-1.1", "[A]"), ("FR-9.9", "[A]")) + RETIRED,
        {"test_it.py": "def test_silent():\n    pass\n"},
    )
    code, out = checker(traceability, ARGV, tree)
    assert code == 1
    assert "both live and retired" in out
    assert "test_silent" not in out


# COVERS: FR-4.10 | edge
def test_a_heading_after_retired_returns_to_live_rows(checker, tmp_path):
    """Only the rows under the heading are retired. A section following it
    declares live requirements like any other."""
    document = (
        requirements(("FR-1.1", "[A]"))
        + RETIRED
        + "\n## Later\n\n| ID | Requirement | |\n|---|---|---|\n"
        + "| FR-2.2 | Live again. | [A] |\n"
    )
    tree = project(
        tmp_path,
        document,
        {"test_it.py": "# COVERS: FR-1.1 | positive\ndef test_one():\n    pass\n"},
    )
    code, out = checker(traceability, ARGV, tree)
    assert code == 1
    assert "FR-2.2" in out
