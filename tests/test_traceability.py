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


# COVERS: FR-4.8 | regression
def test_a_decorator_wrapped_onto_a_second_line_does_not_hide_it(checker, tmp_path):
    """`ruff format` wraps a long decorator, so this is reachable by formatting.

    The continuation line begins with whitespace rather than `@` or `#`, so the
    block walk stopped there and the test reported as citing nothing while
    carrying a correct mark. The failure points the wrong way: the report blames
    the test, so the author's fix is to add a mark that is already present.

    Filed by agent-support 2026-08-28, who hit it on three of seven tests in one
    file and worked around it by hoisting every parametrize list to a module
    constant so each decorator fit on one line.
    """
    tree = project(
        tmp_path,
        requirements(("FR-1.1", "[A]")),
        {
            "test_it.py": (
                "import pytest\n\n\n"
                "# COVERS: FR-1.1 | edge\n"
                '@pytest.mark.parametrize("n", [1, 2],\n'
                '                         ids=["one", "two"])\n'
                "def test_wrapped(n):\n    pass\n"
            )
        },
    )
    code, out = checker(traceability, ARGV, tree)
    assert code == 0, out


# COVERS: FR-4.8 | negative
def test_an_ordinary_statement_still_ends_the_block(checker, tmp_path):
    """The bracket rule must not swallow code between a mark and a test.

    Stepping over any indented line would let a COVERS mark far above attach to
    an unrelated test below it. Only a line inside an unclosed group is stepped
    over, and an ordinary statement is balanced.
    """
    tree = project(
        tmp_path,
        requirements(("FR-1.1", "[A]")),
        {
            "test_it.py": (
                "# COVERS: FR-1.1 | edge\n"
                "VALUE = compute(1)\n"
                "def test_unmarked():\n    pass\n"
            )
        },
    )
    code, out = checker(traceability, ARGV, tree)
    assert code == 1
    assert "test_unmarked" in out


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


# ---- rust, which marks a test with an attribute -----------------------------


RUST_TEST = (
    "// COVERS: FR-1.1 | property\n"
    "/// The walk returns sorted paths, so two runs over one tree agree.\n"
    "#[test]\n"
    "fn the_walk_is_sorted() {\n    assert!(true);\n}\n"
)


# COVERS: FR-4.7, FR-4.8 | positive
def test_a_rust_test_is_found_through_its_attribute_and_doc_comment(checker, tmp_path):
    """`#[test]` and `///` both sit between the COVERS line and the `fn`.

    Stepping over only one of them leaves the annotation unreachable, which
    fails louder than skipping the file and is just as wrong.
    """
    tree = project(
        tmp_path, requirements(("FR-1.1", "[A]")), {"tests/skeleton.rs": RUST_TEST}
    )
    code, out = checker(traceability, ARGV, tree)
    assert code == 0, out


# COVERS: FR-4.16 | negative
def test_a_rust_helper_without_the_attribute_is_not_a_test(checker, tmp_path):
    """A test file's helpers outnumbered its tests 5 to 20 in bolt.

    Reading every `fn` as a test would fail a file for the functions holding
    it up, so the attribute is what separates the two.
    """
    tree = project(
        tmp_path,
        requirements(("FR-1.1", "[A]")),
        {
            "tests/skeleton.rs": (
                "fn write_jig(body: &str) -> PathBuf {\n    todo!()\n}\n\n" + RUST_TEST
            )
        },
    )
    code, out = checker(traceability, ARGV, tree)
    assert code == 0, out
    assert "write_jig" not in out


# COVERS: FR-4.16 | edge
def test_a_rust_test_still_has_to_cite_something(checker, tmp_path):
    """The attribute selects what is a test; it does not exempt one."""
    tree = project(
        tmp_path,
        requirements(("FR-1.1", "[A]")),
        {"tests/skeleton.rs": "#[test]\nfn silent() {\n    assert!(true);\n}\n"},
    )
    code, out = checker(traceability, ARGV, tree)
    assert code == 1
    assert "silent" in out
    assert "// COVERS:" in out


# COVERS: FR-4.7 | edge
def test_a_rust_unit_test_inside_src_is_found(checker, tmp_path):
    """A Rust unit test lives in the file it covers, not under tests/."""
    tree = project(
        tmp_path,
        requirements(("FR-1.1", "[A]")),
        {
            "src/walk.rs": (
                "pub fn walk() {}\n\n"
                "#[cfg(test)]\nmod tests {\n"
                "    // COVERS: FR-1.1 | property\n"
                "    #[test]\n"
                "    fn it_walks() {\n        assert!(true);\n    }\n}\n"
            )
        },
    )
    code, out = checker(traceability, ARGV, tree)
    assert code == 0, out


# COVERS: FR-2.5 | regression
def test_cargo_build_output_is_not_scanned(checker, tmp_path):
    """`target/` carries vendored `.rs` sources, and bolt's held twelve."""
    tree = project(
        tmp_path, requirements(("FR-1.1", "[A]")), {"tests/skeleton.rs": RUST_TEST}
    )
    vendored = tree / "target" / "debug" / "build" / "vendored.rs"
    vendored.parent.mkdir(parents=True)
    vendored.write_text("#[test]\nfn theirs() {}\n", encoding="utf-8")
    code, out = checker(traceability, ARGV, tree)
    assert code == 0, out
    assert "theirs" not in out


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


# COVERS: FR-2.5 | regression
def test_the_session_scratch_directory_is_not_scanned(checker, tmp_path):
    """`.ephemera` is gitignored working space every repository here has.

    A scratch `main_test.go` left in one failed this gate while being no part
    of the project, which is how this entry got added.
    """
    tree = project(
        tmp_path,
        requirements(("FR-1.1", "[A]")),
        {"test_it.py": "# COVERS: FR-1.1 | positive\ndef test_ours():\n    pass\n"},
    )
    scratch = tree / ".ephemera" / "probe" / "scratch_test.go"
    scratch.parent.mkdir(parents=True)
    scratch.write_text("func TestScratch(t *testing.T) {}\n", encoding="utf-8")
    code, out = checker(traceability, ARGV, tree)
    assert code == 0, out
    assert "TestScratch" not in out


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


# ---- a directory of requirements --------------------------------------------


DIR_ARGV = ["--requirements", "docs/REQUIREMENTS", "."]


def split(tmp_path: Path, files: dict[str, str], sources: dict[str, str]) -> Path:
    """Write one requirement file per entry, under docs/REQUIREMENTS."""
    for name, document in files.items():
        path = tmp_path / "docs" / "REQUIREMENTS" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(document, encoding="utf-8")
    for name, text in sources.items():
        source = tmp_path / name
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(text, encoding="utf-8")
    return tmp_path


# COVERS: FR-4.12 | positive
def test_a_directory_reaches_the_same_verdict_as_one_document(checker, tmp_path):
    """The split is a path change, so the verdict may not move with it.

    The same two requirements and the same test, written one way and then the
    other, and the reported figures have to agree.
    """
    covering = {
        "test_it.py": "# COVERS: FR-1.1, FR-1.2 | positive\ndef test_t():\n    pass\n"
    }
    (tmp_path / "whole").mkdir()
    (tmp_path / "parts").mkdir()
    whole = project(
        tmp_path / "whole",
        requirements(("FR-1.1", "[A]"), ("FR-1.2", "[D]")),
        covering,
    )
    parts = split(
        tmp_path / "parts",
        {
            "core/FR-1.1-first.md": requirements(("FR-1.1", "[A]")),
            "core/FR-1.2-second.md": requirements(("FR-1.2", "[D]")),
        },
        covering,
    )
    whole_code, whole_out = checker(traceability, ARGV, whole)
    parts_code, parts_out = checker(traceability, DIR_ARGV, parts)

    assert whole_code == parts_code == 0
    assert "2 of 2" in whole_out
    assert "2 of 2" in parts_out


# COVERS: FR-4.12 | edge
def test_a_readme_preamble_is_read_like_any_other_file(checker, tmp_path):
    """A category README carries the preamble, and a row in one still counts.

    Skipping it by name would let a requirement written in the wrong file pass
    unheld, which is the silent direction. Counting it fails loudly instead.
    """
    tree = split(
        tmp_path,
        {
            "core/FR-1.1-first.md": requirements(("FR-1.1", "[A]")),
            "core/README.md": requirements(("FR-5.5", "[A]")),
        },
        {"test_it.py": "# COVERS: FR-1.1 | positive\ndef test_t():\n    pass\n"},
    )
    code, out = checker(traceability, DIR_ARGV, tree)
    assert code == 1
    assert "FR-5.5" in out


# COVERS: FR-4.13 | negative
def test_one_id_declared_in_two_files_fails(checker, tmp_path):
    """Both files read correctly alone; merged, the later silently wins."""
    tree = split(
        tmp_path,
        {
            "core/FR-1.1-first.md": requirements(("FR-1.1", "[A]")),
            "other/FR-1.1-again.md": requirements(("FR-1.1", "[D]")),
        },
        {"test_it.py": "# COVERS: FR-1.1 | positive\ndef test_t():\n    pass\n"},
    )
    code, out = checker(traceability, DIR_ARGV, tree)
    assert code == 1
    assert "declared more than once" in out
    assert "FR-1.1-first.md" in out
    assert "FR-1.1-again.md" in out


# COVERS: FR-4.14 | regression
def test_a_retired_heading_does_not_reach_the_next_file(checker, tmp_path):
    """Concatenating the tree would retire every row after the section.

    `a/` sorts before `b/`, so a reader that joined the files and kept its
    state would swallow FR-1.1 and report a document declaring nothing.
    """
    tree = split(
        tmp_path,
        {
            "a/retired.md": "# Gone\n" + RETIRED,
            "b/FR-1.1-live.md": requirements(("FR-1.1", "[A]")),
        },
        {},
    )
    code, out = checker(traceability, DIR_ARGV, tree)
    assert code == 1
    assert "FR-1.1" in out
    assert "declares no requirements" not in out


# COVERS: FR-4.17 | positive
def test_a_retired_filename_retires_without_any_heading(checker, tmp_path):
    """The name carries it, so there is no switch for a row to fall under.

    Both spellings, and nested, because a group nests and the retired row
    stays in the group it always sat in.
    """
    tree = split(
        tmp_path,
        {
            "api/v1/FR-1.1-live.md": requirements(("FR-1.1", "[A]")),
            "api/v1/FR-2.2-gone.retired": requirements(("FR-2.2", "[A]")),
            "api/FR-3.3-gone.retired.md": requirements(("FR-3.3", "[A]")),
        },
        {"test_it.py": "# COVERS: FR-1.1 | positive\ndef test_t():\n    pass\n"},
    )
    code, out = checker(traceability, DIR_ARGV, tree)
    assert code == 0, out
    assert "1 of 1" in out
    assert "FR-2.2" not in out
    assert "FR-3.3" not in out


# COVERS: FR-4.17 | regression
def test_a_heading_does_not_un_retire_the_rows_below_it(checker, tmp_path):
    """`whatever it contains` includes its headings.

    A `## Superseded by` section is the likeliest thing to write in a retired
    requirement's file, and it is the record the name-based form exists to
    make room for. Letting it turn retirement off puts back the switch the
    filename removed, in the one document guaranteed to want a heading.
    """
    tree = split(
        tmp_path,
        {
            "core/FR-1.1-live.md": requirements(("FR-1.1", "[A]")),
            "core/FR-2.2-gone.retired": (
                requirements(("FR-2.2", "[A]"))
                + "\n## Superseded by\n\n"
                + requirements(("FR-3.3", "[A]"))
            ),
        },
        {"test_it.py": "# COVERS: FR-1.1 | positive\ndef test_t():\n    pass\n"},
    )
    code, out = checker(traceability, DIR_ARGV, tree)
    assert code == 0, out
    assert "1 of 1" in out
    assert "FR-3.3" not in out


# COVERS: FR-4.17 | regression
def test_an_id_below_a_heading_in_a_retired_file_cannot_be_reused(checker, tmp_path):
    """An escaped row is still caught, and named as the wrong thing.

    Measured against the unfixed checker: redeclaring the id does not pass,
    because the escaped row is live in two documents and the duplicate check
    fires. It reports `declared more than once` rather than `both live and
    retired`, and the obvious remedy for a duplicate is to delete one of the
    two rows, which here would delete the retirement record itself.

    So the assertion is on which check fires, not on whether one does.
    """
    tree = split(
        tmp_path,
        {
            "core/FR-9.9-gone.retired": (
                requirements(("FR-8.8", "[A]"))
                + "\n## Superseded by\n\n"
                + requirements(("FR-9.9", "[A]"))
            ),
            "core/FR-9.9-again.md": requirements(("FR-9.9", "[A]")),
        },
        {},
    )
    code, out = checker(traceability, DIR_ARGV, tree)
    assert code == 1
    assert "both live and retired" in out
    assert "FR-9.9" in out


# COVERS: FR-4.18 | regression
def test_a_retired_file_is_read_so_its_id_cannot_be_reused(checker, tmp_path):
    """A `.retired` document the glob misses holds no id at all.

    Nothing then stops the id being declared again, and every existing
    reference to it silently means something else. That is the failure the
    never-reuse rule exists to prevent, arrived at by an invisible file.
    """
    tree = split(
        tmp_path,
        {
            "core/FR-1.1-gone.retired": requirements(("FR-1.1", "[A]")),
            "core/FR-1.1-again.md": requirements(("FR-1.1", "[A]")),
        },
        {},
    )
    code, out = checker(traceability, DIR_ARGV, tree)
    assert code == 1
    assert "both live and retired" in out
    assert "FR-1.1" in out


# COVERS: FR-4.17 | edge
def test_a_retired_file_still_tells_a_test_where_the_id_went(checker, tmp_path):
    """Retired is not deleted. A test citing one is told, not left guessing."""
    tree = split(
        tmp_path,
        {
            "core/FR-1.1-live.md": requirements(("FR-1.1", "[A]")),
            "core/FR-9.9-gone.retired": requirements(("FR-9.9", "[A]")),
        },
        {
            "test_it.py": "# COVERS: FR-1.1, FR-9.9 | positive\ndef test_t():\n    pass\n"
        },
    )
    code, out = checker(traceability, DIR_ARGV, tree)
    assert code == 1
    assert "FR-9.9" in out
    assert "retired" in out


# COVERS: FR-2.4 | edge
def test_a_directory_holding_no_rows_refuses_to_pass(checker, tmp_path):
    """An empty tree is zero requirements agreeing with zero citations."""
    tree = split(tmp_path, {"core/notes.md": "# Prose, and no table.\n"}, {})
    code, out = checker(traceability, DIR_ARGV, tree)
    assert code == 1
    assert "declares no requirements" in out


# COVERS: FR-4.15 | negative
def test_an_unreadable_document_reports_why_and_does_not_raise(checker, tmp_path):
    """Absent and unreadable are different, and neither is a traceback."""
    tree = project(tmp_path, requirements(("FR-1.1", "[A]")))
    (tree / "REQUIREMENTS.md").chmod(0o000)
    try:
        code, out = checker(traceability, ARGV, tree)
    finally:
        (tree / "REQUIREMENTS.md").chmod(0o644)
    assert code == 1
    assert "cannot be read" in out
