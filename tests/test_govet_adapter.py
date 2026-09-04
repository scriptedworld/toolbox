"""Tests for `adapters/go/govet.py`.

`go vet` exits 1 to mean "found something" and says nothing in that status about
what or where. The adapter is what turns its stderr into reasons carrying a
location, so a merged result stays actionable.

IT STILL SPEAKS THE RETIRED STDIN CONTRACT and is wired to no task, which is
recorded in `docs/DECISIONS/a-task-that-cannot-fail-leaves-the-jig.md`. These
tests pin what it does today so that porting it is a change with a before and an
after, rather than a rewrite of something nobody had measured.
"""

from __future__ import annotations

from conftest import fixture_text, load

govet = load("adapters/go/govet.py")


def record(stderr: str = "", stdout: str = "", exitcode: int = 1) -> dict[str, object]:
    """An execution record shaped the way bolt writes one.

    `go vet` writes diagnostics to stderr, so that is the default here and the
    exit code defaults to 1 for the same reason: a record carrying diagnostics
    and a zero status is not a shape the tool produces.
    """
    return {"captures": {"stdout": stdout, "stderr": stderr, "exitcode": exitcode}}


# COVERS: FR-3.4 | positive
def test_each_diagnostic_becomes_one_reason(adapter):
    """Captured output from a real run: three diagnostics, three reasons, in order."""
    envelope = adapter(govet, record(fixture_text("govet/composites.txt")))
    assert envelope["success"] is False
    assert [(r["file"], r["line"]) for r in envelope["reasons"]] == [
        ("internal/cli/cli.go", 42),
        ("internal/cli/cli.go", 88),
        ("main.go", 17),
    ]


# COVERS: FR-3.4 | property
def test_a_reason_names_its_checker_and_where_to_look(adapter):
    """A reason nobody can act on is a reason nobody acts on."""
    first = adapter(govet, record(fixture_text("govet/composites.txt")))["reasons"][0]
    assert first["checker"] == "vet"
    assert first["column"] == 9
    assert first["message"] == "composite literal uses unkeyed fields"


# COVERS: FR-3.4 | edge
def test_a_package_header_is_attributed_to_the_diagnostics_beneath_it(adapter):
    """go vet groups by package and the grouping is information the reason keeps."""
    reasons = adapter(govet, record(fixture_text("govet/composites.txt")))["reasons"]
    assert reasons[0]["package"] == "github.com/scriptedworld/example/internal/cli"
    assert reasons[2]["package"] == "github.com/scriptedworld/example"


# COVERS: FR-3.4 | edge
def test_a_diagnostic_before_any_package_header_carries_no_package(adapter):
    """Attributing it to the next header would put it in the wrong package."""
    envelope = adapter(govet, record("main.go:3:1: something\n"))
    assert "package" not in envelope["reasons"][0]


# COVERS: FR-3.4 | edge
def test_a_diagnostic_without_a_column_omits_the_key(adapter):
    """The column is optional in go vet's output and omitted rather than zeroed,
    because 0 is a position and 'not said' is not."""
    envelope = adapter(govet, record("main.go:12: something without a column\n"))
    reason = envelope["reasons"][0]
    assert reason["line"] == 12
    assert "column" not in reason


# COVERS: FR-3.4 | edge
def test_a_leading_dot_slash_is_stripped_from_the_file(adapter):
    """vet echoes the path it was given; the reason names the file, not the walk."""
    envelope = adapter(govet, record("./cmd/bolt/main.go:5:2: x\n"))
    assert envelope["reasons"][0]["file"] == "cmd/bolt/main.go"


# COVERS: FR-3.4 | edge
def test_a_line_that_is_not_a_diagnostic_is_ignored(adapter):
    """vet interleaves prose with diagnostics and only the latter are findings."""
    envelope = adapter(
        govet,
        record("vet: cannot process directory\nmain.go:1:1: real\n\n   \n"),
    )
    assert len(envelope["reasons"]) == 1
    assert envelope["reasons"][0]["message"] == "real"


# COVERS: FR-3.1 | edge
def test_stdout_is_read_as_well_as_stderr(adapter):
    """Which stream a diagnostic arrives on is the tool's business, not the
    adapter's, and a finding on the wrong one must not be lost."""
    envelope = adapter(govet, record(stdout="main.go:7:1: on stdout", stderr=""))
    assert envelope["reasons"][0]["line"] == 7


# COVERS: FR-3.6 | negative
def test_a_non_zero_exit_with_nothing_parseable_is_a_failure(adapter):
    """Silence plus a bad exit code is not success: a package that would not
    build exits non-zero with no diagnostic this adapter can attribute."""
    envelope = adapter(govet, record("# example\nbuild failed somehow\n", exitcode=2))
    assert envelope["success"] is False
    assert "no diagnostic this adapter could parse" in envelope["reasons"][0]["message"]
    assert "build failed somehow" in envelope["reasons"][0]["detail"]


# COVERS: FR-3.5 | positive
def test_a_clean_run_succeeds_and_carries_no_reasons_block(adapter):
    """`reasons: []` reads as 'checked and found nothing to say', which is a
    different claim from having nothing to report."""
    envelope = adapter(govet, record("", exitcode=0))
    assert envelope["success"] is True
    assert "reasons" not in envelope


# COVERS: FR-3.6 | edge
def test_a_diagnostic_outranks_the_exit_code(adapter):
    """Something parseable is always better than the unattributed fallback."""
    envelope = adapter(govet, record("main.go:1:1: real\n", exitcode=2))
    assert len(envelope["reasons"]) == 1
    assert envelope["reasons"][0]["file"] == "main.go"


# COVERS: FR-3.6 | edge
def test_a_missing_exit_code_is_not_read_as_a_failure(adapter):
    """A record with no status says nothing either way, and with no diagnostic
    there is nothing to report."""
    envelope = adapter(govet, {"captures": {"stdout": "", "stderr": ""}})
    assert envelope["success"] is True


# COVERS: FR-3.1 | edge
def test_an_empty_record_is_a_pass_rather_than_a_crash(adapter):
    """bolt writes a record for every execution, including ones that captured
    nothing, and an adapter that raised on one would report a broken adapter
    where the tool had simply found nothing."""
    assert adapter(govet, {})["success"] is True


# COVERS: FR-3.4 | edge
def test_a_non_ascii_message_and_path_survive_into_the_reason(adapter):
    """Go source may be named and commented in any language, and a diagnostic
    quotes the identifier it is about."""
    envelope = adapter(govet, record("internal/café/設定.go:3:1: unknown field café\n"))
    reason = envelope["reasons"][0]
    assert reason["file"] == "internal/café/設定.go"
    assert reason["message"] == "unknown field café"


# COVERS: FR-3.4 | edge
def test_a_message_containing_a_colon_keeps_all_of_it(adapter):
    """vet prefixes the analyser name with a colon, so a greedy split on `:`
    would cut the message in half."""
    envelope = adapter(
        govet,
        record("main.go:17:6: printf: Printf call has arguments but no directives\n"),
    )
    assert envelope["reasons"][0]["message"] == ("printf: Printf call has arguments but no directives")
