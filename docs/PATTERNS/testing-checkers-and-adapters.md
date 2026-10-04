# Testing the checkers and the adapters

How this repository tests the code it ships, and why the two kinds of code get
two different shapes of test.

A checker is what a task runs, taking `argv` and the filesystem and returning a
verdict as its exit code. An adapter is handed the paths of what bolt captured
and writes an envelope to `output.yaml` in its work directory. The split below
is that distinction applied to tests.

---

## Why

A checker is only exercised by the repository it is pointed at, and the shared
ones are pointed at repositories their author has never seen.
`docs/LESSONS/a-checker-only-meets-the-repository-it-is-pointed-at.md` has the
case: a sort key that raised on any lettered requirement id passed every run
against a repository with none. So the suite feeds each script the inputs no
single adopter shows it: lettered ids, other languages, empty trees.

## Two contracts, two shapes of test

The contract decides what a test is able to assert.

| | **Checker** (`bin/`) | **Adapter** (`adapters/`) |
|---|---|---|
| Input | `argv`, and the filesystem | flags naming bolt's captures: `--stdout`, `--exitcode`, `--evidence`, `--work-dir` |
| Output | text on stdout, **exit code is the verdict** | an **envelope** in `{work_dir}/output.yaml` |
| Reads | a project tree | only the files it is handed (FR-3.8): no clock, no network |
| Needs the real tool? | No, it *is* the tool | No, it parses text the tool once produced |
| Test gives it | a tree built under `tmp_path` | captured output written under `tmp_path` |
| Test asserts on | `(exit code, stdout)` | the envelope, validated against wrench's schema |

`adapters/go/gofmt.py` and `govet.py` still read a record on stdin and print
their envelope, the retired contract; neither is wired to a task. The
`adapter` fixture serves that shape.

**Neither kind of test ever runs the tool it is about.** An adapter test does not
run `gofmt`; it feeds the adapter text `gofmt` produced. That keeps the suite
runnable on a machine with none of the tools installed, and it is the same
property that lets `anvil` build an image without running the suite inside it.

## The harness

Two facts about the layout dictate its shape.

`bin/test-traceability.py` and `bin/suppression-register.py` cannot be imported
by name: a hyphen is not valid in a Python identifier, and neither directory is
a package. Tests load them by path instead, which `tests/conftest.py` does once:

```python
traceability = load("bin/test-traceability.py")
```

**A checker's tests call `main()` in-process**, where the assertion failures are
readable. An adapter is spawned, because where it writes its envelope is part of
its contract: `run_flag_adapter` and `read_envelope` in `conftest.py` run it as
bolt does and read `output.yaml`. A spawned script is still measured, because
`script_argv` runs it under `coverage run --parallel-mode` when the suite is
under coverage (NFR-2).

**Every helper that reads an envelope validates it** against wrench's
`ENVELOPE_SCHEMA` (FR-3.9), so an adapter writing one bolt would refuse fails its
own suite first, and a convention test fails any adapter no test reaches that
way (FR-3.10).

In-process, `main()` has to be reached with `argv`, the working directory and
stdin set, and `conftest.py` provides fixtures so that no test does it by hand:

```python
def test_something(checker, tmp_path):
    """One sentence saying what this pins."""
    code, out = checker(traceability, ["--requirements", "REQUIREMENTS.md", "."], cwd=tmp_path)


def test_something_else(adapter):
    """One sentence saying what this pins."""
    envelope = adapter(gofmt, {"captures": {"stdout": "main.go\n", "exitcode": 0}})
```

Both restore what they changed through `monkeypatch`, so a test failing mid-way
does not leave the next one running in the wrong directory.

**Every checker gets one subprocess test.** In-process testing cannot catch a
script that is not executable, has a broken shebang, or crashes on import, and
those are exactly the failures that break a task for every adopter at once.

## Fixtures are captured, never composed

An adapter exists because a tool's output needs interpreting, so a test feeding
it invented output tests only whoever invented it.

Run the real tool once, save what it printed under `tests/fixtures/`, and
record where it came from.

```
tests/fixtures/
  gofmt/unformatted.txt      # gofmt 1.23.4, captured 2026-08-20
  govet/composites.txt
  coverage/mixed-profile.out
```

Every fixture file opens with a comment naming the tool version and the date of
capture. A tool changing its output format is the break these adapters exist to
absorb, and a fixture with no provenance cannot tell you whether it ever matched
reality.

Composing by hand is fine for the *shape* around the payload: an empty stdout, a
missing evidence file, a non-zero exit code. It is not fine for the
payload itself.

## What a test asserts

`assert envelope["success"] is False` is not a test. It passes just as happily
when the adapter fails for the wrong reason, on the wrong file, and reports it
unreadably.

Assert the verdict and what the verdict says:

```python
assert envelope["success"] is False
assert [r["file"] for r in envelope["reasons"]] == ["internal/cli/cli.go"]
assert "not gofmt-clean" in envelope["reasons"][0]["message"]
```

For a checker, assert the exit code and that the finding names the thing:

```python
assert code == 1
assert "FR-2.1" in out  # the uncovered requirement is named
assert "FR-2.2" not in out.split("settled")[1]  # the open one is not in the failing block
```

Three cases every checker and adapter gets, each of them a way to be wrong that
the happy path cannot show:

1. **the passing case**, and that it says so instead of saying nothing;
2. **the failing case**, and that the reason names the file, line or id;
3. **the empty case**: no input, no findings, a missing file. This is where false
   greens live, because a checker that finds nothing after looking in the wrong
   place is indistinguishable from one that found nothing wrong.

## Layout

```
pyproject.toml              pytest and coverage configuration; declares no package
tests/
  conftest.py               the loader, the fixtures and the envelope helpers
  test_traceability.py      bin/test-traceability.py
  test_suppression_register.py   bin/suppression-register.py
  test_gofmt_adapter.py     adapters/go/gofmt.py
  ...                       one file per checker or adapter
  fixtures/<tool>/*.txt     real captured tool output
```

One test file per script under test, named for that script, so the tests for a
script are found by its name.

## Every script has tests

Every script in `bin/` and `adapters/` has a test file. `bolt
python-std-quality .` keeps it so: it judges coverage per file at 80% of lines
and 80% of branches, so a new script arriving without tests fails the gate.
`bin/voice-review.py` is tested with a fake API connection and a fake CLI handed
in, never a model, and `bin/voice-tells.py` against real git repositories built
in the test.

## What this suite deliberately does not do

**It does not run the tools.** That is `anvil`'s job to make possible, and no
test's job to prove.

**It does not test bolt.** A test here that ran `bolt` would be testing the
runner through this repository, and that is the dependency the three-repository
split avoids. The captures a test writes stand in for bolt, and the schemas
wrench ships, which `tests/test_jigs.py` and `conftest.py` import, hold the two
ends together.

It does not assert on exact prose. Checker output is read by people and will
be reworded. A test asserts that a finding *names* the file, id or count, never
that it phrases it a particular way.
