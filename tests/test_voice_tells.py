"""Tests for `bin/voice-tells.py`.

Each rule is shown firing on a line that carries it and staying quiet on a near
miss, in a real git repository, through `main()`. The offending phrases live in
string literals, which the checker does not read, so this file passes its own
check.
"""

from __future__ import annotations

import json
import subprocess  # nosec B404
from pathlib import Path

import pytest
import yaml
from conftest import ROOT, git, load, script_argv
from conftest import repository as committed

tells = load("bin/voice-tells.py")

DASH = "—"


def repository(tmp_path: Path, files: dict[str, str] | None = None) -> Path:
    """A committed repository holding the files named, and a clean README when none are."""
    return committed(tmp_path, files or {"README.md": "# repo\n\nA plain sentence.\n"})


def start_here(tree: Path) -> None:
    """Record HEAD as the start, committed so the tree is clean."""
    (tree / ".voice-review-start").write_text(git(tree, "rev-parse", "HEAD") + "\n", encoding="utf-8")


def commit(tree: Path, message: str) -> None:
    """An empty commit carrying the message."""
    git(tree, "commit", "-q", "--allow-empty", "-m", message)


def run(tree: Path, capsys) -> tuple[int, dict, str]:
    """Exit code, report and output of one in-process run."""
    report = tree.parent / "report.json"
    code = tells.main(["--all-files", "--report", str(report), "--base", str(tree)])
    output = capsys.readouterr().out
    return code, json.loads(report.read_text(encoding="utf-8")), output


def rules_hit(tree: Path, capsys) -> set[str]:
    """The names of every rule that fired."""
    _, report, _ = run(tree, capsys)
    return {finding["rule"] for finding in report["findings"]}


def doc_rules(tmp_path: Path, capsys, sentence: str) -> set[str]:
    """Rules that fire on one sentence in a document."""
    return rules_hit(repository(tmp_path, {"README.md": f"# repo\n\n{sentence}\n"}), capsys)


# COVERS: FR-9.1 | positive
def test_a_clean_tree_passes_and_says_what_it_read(tmp_path, capsys):
    """Nothing found is exit 0, and the summary names why commits were or were not read."""
    code, report, output = run(repository(tmp_path), capsys)

    assert code == 0
    assert report["passed"] is True and report["findings"] == []
    assert "0 errors, 0 suggestions, 0 accepted (none)" in output
    assert "no start commit is recorded" in output


# COVERS: FR-9.1, FR-2.2 | negative
def test_one_instance_fails_and_names_where_the_line_and_the_rule(tmp_path, capsys):
    """A single instance is enough, and the output is enough to go and fix it."""
    tree = repository(tmp_path, {"docs/guide.md": f"# guide\n\nplain\n\nThe run stopped {DASH} twice.\n"})

    code, report, output = run(tree, capsys)

    assert code == 1
    assert report["passed"] is False
    assert f"docs/guide.md:5: em-dash: The run stopped {DASH} twice." in output
    assert report["counts"] == {"em-dash": 1}


# COVERS: FR-9.1 | positive
def test_the_script_runs_by_path_from_the_project_directory(tmp_path):
    """Invoked as the jig invokes it, the exit code is the verdict."""
    tree = repository(tmp_path, {"README.md": "# repo\n\nFound -- twice.\n"})

    result = subprocess.run(script_argv(ROOT / "bin" / "voice-tells.py", "--all-files"), cwd=tree, capture_output=True, text=True, check=False)  # nosec B603

    assert result.returncode == 1
    assert "README.md:3: ascii-dash:" in result.stdout


# COVERS: FR-9.2 | positive
@pytest.mark.parametrize("sentence", [f"one {DASH} two", "one -- two", "slow -- a full rebuild"])
def test_dashes_between_words_are_found(tmp_path, capsys, sentence):
    """The character, and the two hyphens standing in for it."""
    assert doc_rules(tmp_path, capsys, sentence) & {"em-dash", "ascii-dash"}


# COVERS: FR-9.2 | negative
@pytest.mark.parametrize("sentence", ["Pass --verbose to see more.", "Then rm -- -f removes it.", "2011--2014 at the same place."])
def test_flags_option_ends_and_ranges_are_not_dashes(tmp_path, capsys, sentence):
    """A flag, the end of options and a numeric range all keep their hyphens."""
    assert doc_rules(tmp_path, capsys, sentence) == set()


# COVERS: FR-9.3 | positive
@pytest.mark.parametrize(
    ("sentence", "expected"),
    [
        ("**FACT 2026-09-14:** the set is two files.", "badge"),
        ("CLAIM: it processes on receive.", "badge"),
        ("Measured 2026-09-01: called once per render.", "audit-date"),
        ("Checked on 2026-08-30, a 6MB transcript.", "audit-date"),
        ("DECIDED: dropped.", "audit-marker"),
        ("### HELD 2026-08-19: not yet", "audit-marker"),
        ("The ~~three~~ two checks.", "strikethrough"),
        ("The figure this file used to quote was capped.", "narrated-belief"),
        ("That is no longer true.", "narrated-belief"),
    ],
)
def test_the_audit_trail_is_found(tmp_path, capsys, sentence, expected):
    """Badges, dated verbs, caps markers, strikethrough and narrated belief."""
    assert expected in doc_rules(tmp_path, capsys, sentence)


# COVERS: FR-9.3 | negative
@pytest.mark.parametrize(
    "sentence",
    ["Captured 2026-08-20 with gofmt 1.23.4.", "The FACT table has two columns.", "A request is held until it is decided."],
)
def test_a_date_that_is_data_and_ordinary_words_are_not_the_audit_trail(tmp_path, capsys, sentence):
    """A capture date, the word used as a name, and the verbs without a date pass."""
    assert doc_rules(tmp_path, capsys, sentence) == set()


# COVERS: FR-9.4 | positive
@pytest.mark.parametrize("sentence", ["Our user asked for it.", "The owner decides."])
def test_the_person_described_from_outside_is_found(tmp_path, capsys, sentence):
    """Both spellings, in any case."""
    assert "third-person" in doc_rules(tmp_path, capsys, sentence)


# COVERS: FR-9.4 | positive
def test_a_session_as_the_actor_is_found_in_a_commit(tmp_path, capsys):
    """A commit message crediting a session with the work."""
    tree = repository(tmp_path)
    start_here(tree)
    commit(tree, "fix: the rename\n\nFound by the dotfiles session while fixing it.")

    code, report, _ = run(tree, capsys)

    assert code == 1
    assert [f["rule"] for f in report["findings"]] == ["session-actor"]
    assert report["findings"][0]["where"].startswith("commit ")


# COVERS: FR-9.4 | negative
def test_a_session_in_documentation_is_the_subject_and_passes(tmp_path, capsys):
    """Where sessions are what a project is about, a document may talk about one."""
    assert doc_rules(tmp_path, capsys, "The status line reads this session's transcript.") == set()


# COVERS: FR-9.5 | positive
@pytest.mark.parametrize(
    ("sentence", "expected"),
    [
        ("A trap worth knowing about.", "worth-phrase"),
        ("It is worth keeping.", "worth-phrase"),
        ("And that is not cosmetic.", "stock-phrase"),
        ("That is the lesson.", "stock-phrase"),
        ("THE RED CHANNEL IS LOAD-BEARING, and not obvious.", "caps-run"),
    ],
)
def test_stock_phrasing_is_found(tmp_path, capsys, sentence, expected):
    """The phrases and the shouted run."""
    assert expected in doc_rules(tmp_path, capsys, sentence)


# COVERS: FR-9.5 | negative
@pytest.mark.parametrize("sentence", ["It is worth the wait.", "Set HOME and PATH first.", "The GNU C library."])
def test_ordinary_worth_and_acronyms_pass(tmp_path, capsys, sentence):
    """The word on its own, and two acronyms side by side."""
    assert doc_rules(tmp_path, capsys, sentence) == set()


# COVERS: FR-9.6 | positive
def test_rather_than_three_times_in_one_document_is_found_once(tmp_path, capsys):
    """Density is judged per document and reported once."""
    text = "# r\n\nThis rather than that.\n\nThat rather than this.\n\nMore rather than less.\n"
    _, report, _ = run(repository(tmp_path, {"README.md": text}), capsys)

    assert [(f["rule"], f["line"]) for f in report["findings"]] == [("rather-than", 0)]


# COVERS: FR-9.6 | edge
def test_rather_than_twice_and_in_comments_passes(tmp_path, capsys):
    """Twice is allowed, and comments are not held to the per-document count."""
    files = {
        "README.md": "# r\n\nThis rather than that.\n\nThat rather than this.\n",
        "x.py": "# a rather than b\n# c rather than d\n# e rather than f\n",
    }
    assert rules_hit(repository(tmp_path, files), capsys) == set()


# COVERS: FR-9.6 | positive
def test_bold_in_most_paragraphs_is_found(tmp_path, capsys):
    """Three of six paragraphs is over the share."""
    paragraphs = ["**One** thing.", "**Two** things.", "**Three** things.", "Four.", "Five.", "Six."]
    text = "# r\n\n" + "\n\n".join(paragraphs) + "\n"
    assert rules_hit(repository(tmp_path, {"README.md": text}), capsys) == {"bold-density"}


# COVERS: FR-9.6 | edge
def test_bold_in_a_short_document_passes(tmp_path, capsys):
    """Under six paragraphs the share is not judged."""
    text = "# r\n\n**One.**\n\n**Two.**\n\nThree.\n"
    assert rules_hit(repository(tmp_path, {"README.md": text}), capsys) == set()


# COVERS: FR-9.6 | positive
def test_a_commit_body_over_twenty_lines_is_found(tmp_path, capsys):
    """Twenty-one body lines fail and twenty pass."""
    tree = repository(tmp_path)
    start_here(tree)
    commit(tree, "long\n\n" + "\n".join(f"line {n}" for n in range(21)))
    commit(tree, "fits\n\n" + "\n".join(f"line {n}" for n in range(20)))

    _, report, _ = run(tree, capsys)

    assert [(f["rule"], f["text"]) for f in report["findings"]] == [("commit-length", "21 body lines, at most 20")]


# COVERS: FR-9.7 | negative
def test_code_quotes_and_quoted_spans_are_not_read(tmp_path, capsys):
    """Every way a document reports text it is not asserting."""
    text = (
        f"# r\n\nUse `a {DASH} b` inline.\n\n"
        f'The standard bans "worth knowing" by name.\n\n'
        f"> Measured 2026-08-20: quoted from the log.\n\n"
        f"```\nFACT 2026-01-01: in a fence\n```\n\n"
        f"    DECIDED: indented output\n"
    )
    assert rules_hit(repository(tmp_path, {"README.md": text}), capsys) == set()


# COVERS: FR-9.7 | positive
def test_a_comment_is_read_with_its_quoted_span_removed(tmp_path, capsys):
    """Comments are prose, and the same quoting applies inside them."""
    files = {"tool.go": 'package main\n\n// Upgrades are slow -- a full rebuild.\n// The "worth knowing" phrase.\n'}
    _, report, _ = run(repository(tmp_path, files), capsys)

    assert [(f["where"], f["line"], f["rule"]) for f in report["findings"]] == [("tool.go", 3, "ascii-dash")]


# COVERS: FR-9.8 | negative
def test_exempt_paths_links_and_directives_are_not_read(tmp_path, capsys):
    """Prompt bodies, handoffs, dot directories, links and pragmas are not the project's voice."""
    tell = f"one {DASH} two\n"
    files = {name: tell for name in ("CLAUDE.md", "START_HERE.md", ".ephemera/x.md", "skills/s/SKILL.md", "prompts/p.md", "docs/AGENTS.md")}
    files["x.py"] = f"# pylint: disable=duplicate-code {DASH} two entry points\nx = 1\n"
    tree = repository(tmp_path, files)
    (tree / "linked.md").symlink_to(tree / "CLAUDE.md")

    assert rules_hit(tree, capsys) == set()


# COVERS: FR-9.8 | positive
def test_python_docstrings_are_read(tmp_path, capsys):
    """A docstring is prose a person reads."""
    files = {"x.py": f'def f():\n    """Does it {DASH} twice."""\n'}
    _, report, _ = run(repository(tmp_path, files), capsys)

    assert [(f["where"], f["line"]) for f in report["findings"]] == [("x.py", 2)]


# COVERS: FR-9.8 | edge
def test_a_tree_outside_git_is_walked(tmp_path, capsys):
    """No repository still reads the files, and commits are not read."""
    tree = tmp_path / "plain"
    tree.mkdir()
    (tree / "README.md").write_text(f"one {DASH} two\n", encoding="utf-8")

    code, _, output = run(tree, capsys)

    assert code == 1 and "README.md:1: em-dash" in output


# COVERS: FR-9.9 | negative
def test_commits_up_to_the_start_are_not_read(tmp_path, capsys):
    """History before the gate landed is left alone."""
    tree = repository(tmp_path)
    commit(tree, f"old {DASH} message")
    start_here(tree)
    commit(tree, "new message")

    code, report, output = run(tree, capsys)

    assert code == 0 and report["findings"] == []
    assert "commits read after" in output


# COVERS: FR-9.9 | negative
def test_a_start_that_is_not_a_commit_fails(tmp_path, capsys):
    """A start file naming nothing real is a problem a person must fix."""
    tree = repository(tmp_path)
    (tree / ".voice-review-start").write_text("0123456789abcdef\n", encoding="utf-8")

    code = tells.main(["--all-files", "--base", str(tree)])

    assert code == 2
    assert "not a commit in this repository" in capsys.readouterr().out


# COVERS: FR-9.10 | property
def test_the_same_tree_gives_the_same_report(tmp_path, capsys):
    """Two runs over one tree agree exactly."""
    tree = repository(tmp_path, {"README.md": f"# r\n\nOur user said {DASH} twice.\n"})

    first = run(tree, capsys)
    second = run(tree, capsys)

    assert first[0] == second[0] == 1
    assert first[1] == second[1]


def with_baseline(tmp_path: Path, entries: list[dict], sentence: str) -> Path:
    """A repository holding one finding and the baseline entries given."""
    tree = repository(tmp_path, {"README.md": f"# repo\n\n{sentence}\n"})
    (tree / ".voice-baseline.json").write_text(json.dumps({"accepted": entries}), encoding="utf-8")
    return tree


ACCEPTED = {"file": "README.md", "rule": "third-person", "text": "The owner decides.", "reason": "quoted from the licence"}


# COVERS: FR-9.24 | positive
def test_an_accepted_finding_does_not_fail(tmp_path, capsys):
    """The entry stands in for the finding, which is counted and not failed."""
    tree = with_baseline(tmp_path, [ACCEPTED], "The owner decides.")

    code, report, output = run(tree, capsys)

    assert code == 0 and report["passed"] is True
    assert report["findings"] == [] and len(report["accepted"]) == 1
    assert "0 errors, 0 suggestions, 1 accepted" in output


# COVERS: FR-9.24 | negative
def test_an_entry_does_not_accept_another_instance(tmp_path, capsys):
    """Acceptance is of one finding, not of the rule or the file."""
    tree = with_baseline(tmp_path, [ACCEPTED], "The owner decides.\n\nOur user asked for it.")

    code, report, _ = run(tree, capsys)

    assert code == 1
    assert [f["text"] for f in report["findings"]] == ["Our user asked for it."]


# COVERS: FR-9.24 | edge
def test_an_accepted_finding_survives_its_line_moving(tmp_path, capsys):
    """Entries are keyed on the words, so inserting a paragraph above changes nothing."""
    tree = with_baseline(tmp_path, [ACCEPTED], "A plain sentence.\n\nAnother one.\n\nThe owner decides.")

    code, report, _ = run(tree, capsys)

    assert code == 0 and report["accepted"][0]["line"] == 7


# COVERS: FR-9.25 | negative
def test_an_entry_without_a_reason_fails(tmp_path, capsys):
    """An exception nobody justified is not an exception."""
    entry = {name: value for name, value in ACCEPTED.items() if name != "reason"}
    code, report, _ = run(with_baseline(tmp_path, [entry], "The owner decides."), capsys)

    assert code == 1
    assert {f["rule"] for f in report["findings"]} == {"baseline-entry", "third-person"}


# COVERS: FR-9.25 | negative
def test_a_baseline_that_cannot_be_read_fails(tmp_path, capsys):
    """A broken file is a problem to fix, never a pass."""
    tree = repository(tmp_path)
    (tree / ".voice-baseline.json").write_text("{not json", encoding="utf-8")

    code, report, _ = run(tree, capsys)

    assert code == 1
    assert [f["rule"] for f in report["findings"]] == ["baseline-unreadable"]


# COVERS: FR-9.26 | negative
def test_a_stale_entry_fails_over_the_whole_tree(tmp_path, capsys):
    """An entry whose finding is gone names itself so the baseline can shrink."""
    tree = with_baseline(tmp_path, [ACCEPTED], "A plain sentence.")

    code, report, output = run(tree, capsys)

    assert code == 1
    assert [f["rule"] for f in report["findings"]] == ["baseline-stale"]
    assert "README.md: baseline-stale: third-person is accepted here and no longer found" in output


# COVERS: FR-9.26 | edge
def test_staleness_is_not_judged_when_only_some_files_are_read(tmp_path, capsys):
    """A mode that reads two files cannot know an entry elsewhere is stale."""
    tree = with_baseline(tmp_path, [ACCEPTED], "A plain sentence.")

    code = tells.main(["--base", str(tree), str(tree / "README.md")])

    assert code == 0
    assert "baseline-stale" not in capsys.readouterr().out


# COVERS: FR-9.21 | positive
def test_a_comment_after_code_is_read(tmp_path, capsys):
    """A trailing comment is prose in the same way a whole line is."""
    files = {"tool.go": f"package main\n\nvar x = 1 // Our user set it {DASH} once.\n"}
    _, report, _ = run(repository(tmp_path, files), capsys)

    assert {(f["line"], f["rule"]) for f in report["findings"]} == {(3, "em-dash"), (3, "third-person")}


# COVERS: FR-9.21 | negative
@pytest.mark.parametrize(
    ("name", "text"),
    [
        ("tool.go", 'package main\n\nvar marker = "// Our user wrote this"\n'),
        ("tool.py", 'marker = "# Our user wrote this"\n'),
        ("tool.go", "package main\n\nvar marker = `a raw // Our user string`\n"),
    ],
)
def test_a_marker_inside_a_string_is_not_a_comment(tmp_path, capsys, name, text):
    """Code that mentions a comment marker is still code."""
    assert rules_hit(repository(tmp_path, {name: text}), capsys) == set()


# COVERS: FR-9.22 | positive
@pytest.mark.parametrize(
    ("name", "text"),
    [
        ("tool.go", "package main\n\n/*\nOur user asked for it.\n*/\n"),
        ("script.lua", "-- Our user asked for it.\nlocal x = 1\n"),
        ("script.lua", "--[[\nOur user asked for it.\n]]\nlocal x = 1\n"),
        ("script.rb", "# Our user asked for it.\nx = 1\n"),
        ("script.rb", "=begin\nOur user asked for it.\n=end\nx = 1\n"),
    ],
)
def test_block_and_line_comments_are_read_in_each_language(tmp_path, capsys, name, text):
    """Every comment form the estate's languages write."""
    assert "third-person" in rules_hit(repository(tmp_path, {name: text}), capsys)


# COVERS: FR-9.23 | positive
def test_a_docstring_is_read_and_another_string_is_not(tmp_path, capsys):
    """The first string of a function is prose; a string it assigns is not."""
    quotes = '"' * 3
    source = f"def f():\n    {quotes}Our user asked for it.{quotes}\n    note = {quotes}The owner said so.{quotes}\n    return note\n"
    _, report, _ = run(repository(tmp_path, {"x.py": source}), capsys)

    assert [(f["line"], f["rule"]) for f in report["findings"]] == [(2, "third-person")]


# COVERS: FR-9.23 | edge
def test_a_python_file_that_does_not_parse_is_still_read(tmp_path, capsys):
    """A syntax error loses the docstrings, not the comments."""
    files = {"broken.py": "def f(:\n    # Our user asked for it.\n"}

    assert "third-person" in rules_hit(repository(tmp_path, files), capsys)


def hook_config() -> list[dict]:
    """The hooks this repository declares for pre-commit."""
    return yaml.safe_load((ROOT / ".pre-commit-hooks.yaml").read_text(encoding="utf-8"))


# COVERS: FR-9.17 | positive
def test_with_no_mode_the_staged_copy_is_read(tmp_path, capsys):
    """A file staged clean and then dirtied in the working tree is judged by what is staged."""
    tree = repository(tmp_path)
    (tree / "README.md").write_text("# repo\n\nA staged sentence.\n", encoding="utf-8")
    git(tree, "add", "README.md")
    (tree / "README.md").write_text(f"# repo\n\nA working copy {DASH} dirtied.\n", encoding="utf-8")

    code = tells.main(["--base", str(tree)])

    assert code == 0
    assert "1 staged files, read from the index" in capsys.readouterr().out


# COVERS: FR-9.17 | negative
def test_a_staged_instance_fails_even_when_the_working_tree_is_clean(tmp_path, capsys):
    """The other direction: staged text carries the finding, the file on disk does not."""
    tree = repository(tmp_path)
    (tree / "README.md").write_text(f"# repo\n\nStaged {DASH} badly.\n", encoding="utf-8")
    git(tree, "add", "README.md")
    (tree / "README.md").write_text("# repo\n\nFixed on disk.\n", encoding="utf-8")

    assert tells.main(["--base", str(tree)]) == 1
    assert "README.md:3: em-dash" in capsys.readouterr().out


# COVERS: FR-9.18 | positive
def test_named_files_are_the_only_ones_read(tmp_path, capsys):
    """One file named, another left alone, and no commits read."""
    tree = repository(tmp_path, {"a.md": f"# a\n\nOne {DASH} two.\n", "b.md": f"# b\n\nThree {DASH} four.\n"})

    code = tells.main(["--base", str(tree), str(tree / "a.md")])
    output = capsys.readouterr().out

    assert code == 1
    assert "a.md" in output and "b.md" not in output
    assert "1 named files" in output


# COVERS: FR-9.18 | positive
def test_a_ref_range_reads_what_changed_and_the_commits_between(tmp_path, capsys):
    """A branch's own files and messages, and nothing from before it."""
    tree = repository(tmp_path, {"old.md": f"# old\n\nBefore {DASH} the branch.\n"})
    base_ref = git(tree, "rev-parse", "HEAD")
    (tree / "new.md").write_text(f"# new\n\nOn the branch {DASH} here.\n", encoding="utf-8")
    git(tree, "add", "new.md")
    git(tree, "commit", "-q", "-m", "feat: a file\n\nThis commit adds the file.")

    code = tells.main(["--base", str(tree), "--from-ref", base_ref, "--to-ref", "HEAD"])
    output = capsys.readouterr().out

    assert code == 1
    assert "new.md:3: em-dash" in output and "old.md" not in output
    assert "this-commit-preamble" in output


# COVERS: FR-9.18 | positive
def test_a_commit_message_file_is_read_without_what_git_strips(tmp_path, capsys):
    """Comment lines and the scissors block are not the message."""
    message = tmp_path / "COMMIT_EDITMSG"
    stripped = "# Please enter the commit message\n# ------------------------ >8 ------------------------\ndiff --git a/x b/x\n"
    message.write_text(f"feat: a change\n\nOur user asked for it.\n{stripped}", encoding="utf-8")

    code = tells.main(["--commit-msg-filename", str(message)])
    output = capsys.readouterr().out

    assert code == 1
    assert "COMMIT_EDITMSG:3: third-person" in output
    assert "one commit message" in output


# COVERS: FR-9.19 | negative
@pytest.mark.parametrize(
    "argv",
    [["--all-files", "x.md"], ["--from-ref", "HEAD"], ["--to-ref", "HEAD"], ["--all-files", "--commit-msg-filename", "m"]],
)
def test_two_modes_or_half_a_ref_pair_is_a_usage_error(argv):
    """argparse exits 2 and says which combinations are allowed."""
    with pytest.raises(SystemExit) as refused:
        tells.main(argv)

    assert refused.value.code == 2


# COVERS: FR-9.20 | positive
def test_the_declared_hooks_run_the_checker_at_both_stages():
    """One hook for the staged files, one for the message."""
    hooks = {hook["id"]: hook for hook in hook_config()}

    assert hooks["voice-tells"]["stages"] == ["pre-commit"]
    assert hooks["voice-tells-commit-msg"]["stages"] == ["commit-msg"]
    assert hooks["voice-tells-commit-msg"]["entry"].endswith("--commit-msg-filename")
    assert all("bin/voice-tells.py" in hook["entry"] for hook in hooks.values())


# COVERS: FR-9.20 | positive
def test_the_commit_msg_hook_contract_matches_the_flag(tmp_path, capsys):
    """pre-commit appends the message path to the entry, which is what the flag takes."""
    message = tmp_path / "COMMIT_EDITMSG"
    message.write_text("fix: a typo\n\nCertainly! It is fixed.\n", encoding="utf-8")
    entry = next(hook["entry"] for hook in hook_config() if hook["id"] == "voice-tells-commit-msg")
    flags = entry.split()[2:]

    code = tells.main([*flags, str(message)])

    assert code == 1
    assert "assistant-opener" in capsys.readouterr().out


def comment_rules(tmp_path: Path, capsys, comment: str) -> set[str]:
    """Rules that fire on one comment line in a Go file."""
    return rules_hit(repository(tmp_path, {"tool.go": f"package main\n\n// {comment}\n"}), capsys)


def commit_rules(tmp_path: Path, capsys, message: str) -> set[str]:
    """Rules that fire on one commit message after the start."""
    tree = repository(tmp_path)
    start_here(tree)
    commit(tree, message)
    return rules_hit(tree, capsys)


VOCABULARY = "We delve into a robust and comprehensive design that will leverage a seamless tapestry of ideas."


# COVERS: FR-9.11 | positive
def test_a_suggestion_is_reported_and_does_not_fail(tmp_path, capsys):
    """Dense excess vocabulary prints as a suggestion, marked, and exits 0."""
    code, report, output = run(repository(tmp_path, {"README.md": f"# r\n\n{VOCABULARY}\n"}), capsys)

    assert code == 0 and report["passed"] is True
    assert [(f["rule"], f["severity"]) for f in report["findings"]] == [("excess-vocabulary", "suggestion")]
    assert "README.md: excess-vocabulary (suggestion): 6 in" in output
    assert "0 errors, 1 suggestions" in output


# COVERS: FR-9.11 | negative
def test_an_error_beside_a_suggestion_still_fails(tmp_path, capsys):
    """A suggestion does not soften an error in the same text."""
    code, report, _ = run(repository(tmp_path, {"README.md": f"# r\n\n{VOCABULARY}\n\nOur user asked.\n"}), capsys)

    assert code == 1 and report["passed"] is False
    assert {f["severity"] for f in report["findings"]} == {"error", "suggestion"}


# COVERS: FR-9.12 | positive
@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("fix: the rename\n\nCo-Authored-By: Claude Opus 5 <noreply@anthropic.com>", "attribution-trailer"),
        ("fix: the rename\n\nClaude-Session: https://claude.ai/code/session_x", "attribution-trailer"),
        ("docs: guide\n\nGenerated with [Claude Code](https://claude.com/claude-code)", "attribution-trailer"),
        ("feat: modes\n\nThis commit adds two modes to the checker.", "this-commit-preamble"),
        ("feat: modes\n\nIn this change the checker reads staged files.", "this-commit-preamble"),
        ("fix: typo\n\nCertainly! The typo is fixed.", "assistant-opener"),
    ],
)
def test_assistant_voice_in_a_commit_is_found(tmp_path, capsys, message, expected):
    """Trailers, preambles and chat openers in a message."""
    assert expected in commit_rules(tmp_path, capsys, message)


# COVERS: FR-9.12 | negative
@pytest.mark.parametrize(
    "message",
    ["fix: the rename\n\nCo-Authored-By: Sam Lee <sam@example.invalid>", "feat: modes\n\nThe commit graph is read once.", "fix: be sure, then retry"],
)
def test_a_human_coauthor_and_ordinary_words_pass(tmp_path, capsys, message):
    """A person as co-author, the word commit, and sure mid-sentence are not assistant voice."""
    assert commit_rules(tmp_path, capsys, message) == set()


# COVERS: FR-9.12 | edge
def test_a_preamble_in_documentation_is_not_read_as_a_commit(tmp_path, capsys):
    """The preamble rule reads commit messages only."""
    assert doc_rules(tmp_path, capsys, "This change adds a mode, as the release notes describe.") == set()


# COVERS: FR-9.13 | positive
@pytest.mark.parametrize("glyph", ["\U0001f680", "✨", "✅"])
def test_an_emoji_in_a_comment_or_commit_is_found(tmp_path, capsys, glyph):
    """A rocket, sparkles, a check box."""
    assert "emoji" in comment_rules(tmp_path, capsys, f"ship it {glyph}")


# COVERS: FR-9.13 | negative
def test_an_emoji_in_documentation_and_a_plain_tick_pass(tmp_path, capsys):
    """Documentation is not read for emoji, and a dingbat tick is not one."""
    assert doc_rules(tmp_path, capsys, "Status ✅ in the table.") == set()
    assert "emoji" not in comment_rules(tmp_path / "tick", capsys, "passes ✔")


# COVERS: FR-9.14 | positive
@pytest.mark.parametrize("sentence", ["It's important to note that the cache is cold.", "It is worth mentioning the flag."])
def test_a_hedging_opener_is_found(tmp_path, capsys, sentence):
    """The opener, contracted or not."""
    assert "hedging-opener" in doc_rules(tmp_path, capsys, sentence)


# COVERS: FR-9.14 | negative
def test_note_on_its_own_passes(tmp_path, capsys):
    """Asking the reader to note something is not a hedge."""
    assert doc_rules(tmp_path, capsys, "Note the cache is cold on first run.") == set()


# COVERS: FR-9.15 | positive
@pytest.mark.parametrize(
    ("comment", "expected"),
    [
        ("Added a retry to handle the flaky socket.", "changelog-comment"),
        ("Updated to use the new API.", "changelog-comment"),
        ("This function returns the sum of both.", "this-function-docstring"),
    ],
)
def test_an_edit_record_or_a_this_function_opener_is_found(tmp_path, capsys, comment, expected):
    """A comment narrating its edit, and one naming its kind in place of its job."""
    assert expected in comment_rules(tmp_path, capsys, comment)


# COVERS: FR-9.4 | negative
@pytest.mark.parametrize(
    "sentence",
    [
        "The temporary is created with the owner's permissions only.",
        "History search, and the owner of the key binding.",
        "Only the owner can reach it.",
    ],
)
def test_the_owner_of_a_file_or_a_binding_is_not_the_person(tmp_path, capsys, sentence):
    """Ownership in the filesystem sense, found in wrench, dotfiles and skid, is not a third-person reference."""
    assert doc_rules(tmp_path, capsys, sentence) == set()


# COVERS: FR-9.3 | negative
def test_what_a_link_used_to_say_is_not_narration(tmp_path, capsys):
    """A thing other than a document having said something before is ordinary prose, found in silo."""
    assert doc_rules(tmp_path, capsys, "So the manifest has to carry what the link used to say.") == set()


# COVERS: FR-9.7 | negative
def test_a_single_quoted_span_is_not_read_and_a_contraction_is(tmp_path, capsys):
    """A quoted value in a commented-out config line passes; the apostrophe in a word does not hide what follows."""
    files = {"prompt.zsh": "# typeset -g ICON='⭐'\n", "README.md": "# r\n\nIt doesn't matter what our user said.\n"}
    _, report, _ = run(repository(tmp_path, files), capsys)

    assert [(f["where"], f["rule"]) for f in report["findings"]] == [("README.md", "third-person")]


# COVERS: FR-9.15 | negative
@pytest.mark.parametrize(
    "comment",
    [
        "Adds a retry for the flaky socket.",
        "Fixed-width output only.",
        "this function's caller holds the lock",
        "removed and nothing fails.",
        "Removed after each case, so a leftover cannot leak into the next.",
    ],
)
def test_a_present_tense_comment_and_near_misses_pass(tmp_path, capsys, comment):
    """Present tense, a compound word, and the phrase mid-sentence pass."""
    assert comment_rules(tmp_path, capsys, comment) == set()


# COVERS: FR-9.15 | positive
def test_a_python_docstring_opener_is_found(tmp_path, capsys):
    """The docstring delimiters do not hide the opener."""
    # The delimiters are built, because the checker's docstring reader would otherwise read this literal in this file.
    quotes = '"' * 3
    files = {"x.py": f"def add(a, b):\n    {quotes}This function returns the sum of a and b.{quotes}\n    return a + b\n"}
    assert rules_hit(repository(tmp_path, files), capsys) == {"this-function-docstring"}


# COVERS: FR-9.16 | edge
@pytest.mark.parametrize(
    "sentence",
    ["A robust parser.", " ".join(["The parser reads each line and keeps what it can use."] * 60) + " It is robust and comprehensive."],
)
def test_one_use_or_a_thin_spread_is_not_dense(tmp_path, capsys, sentence):
    """One use anywhere, and two uses across 660 words, stay under the density."""
    assert doc_rules(tmp_path, capsys, sentence) == set()
