# Testing the checkers and the adapters

How this repository tests the code it ships, and why the two kinds of code get
two different shapes of test.

Read `GLOSSARY.md` if *checker*, *adapter*, *record* or *envelope* is
unfamiliar. The split below is the glossary's split, applied to tests.

---

## Why

FACT 2026-08-20: `test-traceability.py` carried a sort key that compared an
`int` against a `str` and raised `TypeError` on any requirement id with a letter
suffix. It survived review and a full run against `bolt`, because `bolt` has no
such id. It surfaced only because the checker happened to be run against
`qwark`, which has eleven.

That is the case for tests here in one sentence: **a checker is only exercised
by the repository it happens to be pointed at**, and the shared ones are pointed
at repositories their author has never seen. A gate that crashes is at least
loud. The worse failure is the one below — a gate that passes when it should
not — and nothing in this repository would currently notice either.

## Two contracts, two shapes of test

The distinction is not stylistic. It decides what a test can even assert.

| | **Checker** (`bin/`) | **Adapter** (`adapters/`) |
|---|---|---|
| Input | `argv`, and the filesystem | `argv`, and a **record** on stdin |
| Output | text on stdout, **exit code is the verdict** | an **envelope** on stdout, exit code means nothing |
| Pure? | No — it reads a project tree | **Yes** — no clock, no filesystem, no network |
| Needs the real tool? | No — it *is* the tool | No — it parses text the tool once produced |
| Test gives it | a tree built under `tmp_path` | a record dict |
| Test asserts on | `(exit code, stdout)` | the parsed envelope |

**Neither kind of test ever runs the tool it is about.** An adapter test does
not run `gofmt`; it feeds the adapter text `gofmt` produced. This is what keeps
the suite runnable on a machine with none of the tools installed, which is the
same property that lets `anvil` build an image without running the suite inside
it.

## The harness

Two facts about the layout dictate it.

`bin/test-traceability.py` and `bin/suppression-register.py` **cannot be
imported by name** — a hyphen is not valid in a Python identifier, and neither
directory is a package. Tests load them by path instead, which `tests/conftest.py`
does once:

```python
traceability = load("bin/test-traceability.py")
```

**Tests call `main()` in-process, not through a subprocess.** Two reasons, and
the second is the one that matters: a subprocess is slower and its assertion
failures are opaque, but more importantly `coverage run -m pytest` sees nothing
a subprocess does, so a suite built on subprocesses would report the checkers as
0% covered while testing them thoroughly. In-process is what makes the `tests`
task's coverage figure mean anything.

The cost is that `main()` must be reached with `argv`, the working directory and
stdin all set. `conftest.py` provides one fixture per contract so no test does
that by hand:

```python
def test_something(checker, tmp_path):
    """One sentence saying what this pins."""
    code, out = checker(
        traceability, ["--requirements", "REQUIREMENTS.md", "."], cwd=tmp_path
    )


def test_something_else(adapter):
    """One sentence saying what this pins."""
    envelope = adapter(gofmt, {"captures": {"stdout": "main.go\n", "exitcode": 0}})
```

Both restore what they changed through `monkeypatch`, so a test that fails
mid-way does not leave the next one running in the wrong directory.

**One subprocess test per script, and no more.** In-process testing cannot catch
a script that is not executable, has a broken shebang, or crashes on import —
and those are exactly the failures that make a task fail for every adopter at
once. One smoke test per script covers the wiring; everything else stays
in-process.

## Fixtures are captured, never composed

An adapter exists because a tool's output needs interpreting. A test that feeds
it output **the author imagined** tests the author's imagination.

So: run the real tool once, save what it printed under `tests/fixtures/`, and
record where it came from.

```
tests/fixtures/
  gofmt/unformatted.txt      # gofmt 1.23.4, captured 2026-08-20
  govet/composites.txt
  lizard/over-threshold.txt
  coverage/mixed-profile.out
```

Every fixture file's first line is a comment naming the tool version and the
date it was captured, because a tool changing its output format is precisely the
break these adapters exist to absorb, and a fixture with no provenance cannot
tell you whether it ever matched reality.

Composing a record by hand is fine for the *shape* around the payload — an empty
stdout, a missing `captures` block, a non-zero exit code. It is not fine for the
payload itself.

## What a test asserts

`assert envelope["success"] is False` is not a test. It passes when the adapter
fails for the wrong reason, on the wrong file, with an unreadable message —
which is the failure mode adapters exist to prevent.

Assert the verdict **and** what the verdict says:

```python
assert envelope["success"] is False
assert [r["file"] for r in envelope["reasons"]] == ["internal/cli/cli.go"]
assert "not gofmt-clean" in envelope["reasons"][0]["message"]
```

For checkers, assert the exit code **and** that the finding names the thing:

```python
assert code == 1
assert "FR-2.1" in out  # the uncovered requirement is named
assert (
    "FR-2.2" not in out.split("settled")[1]
)  # the open one is not in the failing block
```

Three cases every checker and adapter gets, because each is a way to be wrong
that its happy path cannot show:

1. **the passing case** — and that it says so, rather than saying nothing;
2. **the failing case** — and that the reason names the file, line or id;
3. **the empty case** — no input, no findings, a missing file. This is where
   false greens live: a checker that finds nothing because it looked in the
   wrong place is indistinguishable from one that found nothing wrong.

## Layout

```
pyproject.toml              pytest and coverage configuration; declares no package
tests/
  conftest.py               the loader and the two fixtures
  test_traceability.py      bin/test-traceability.py
  test_suppression_register.py   bin/suppression-register.py
  test_gofmt_adapter.py     adapters/go/gofmt.py
  ...                       one file per checker or adapter
  fixtures/<tool>/*.txt     real captured tool output
```

One test file per script under test, named for it. A test file covering two
scripts is a test file nobody can find.

## The order of work

Checkers first, because they are the ones that gate other people's repositories
and the ones where a bug is already proven. Adapters second, in the order of
how much interpretation they do — the more parsing an adapter performs, the more
there is to get wrong.

| | Script | State |
|---|---|---|
| 1 | `bin/test-traceability.py` | **done** 2026-08-20 |
| 2 | `bin/suppression-register.py` | **done** 2026-08-20 |
| 3 | `adapters/go/gofmt.py` | **done** 2026-08-20 — the worked example for the rest |
| 4 | `adapters/go/coverage.py` | queued — parses a profile, applies a threshold, excludes by regex; the most logic of any adapter |
| 5 | `adapters/common/lizard.py` | queued — two parsers in one file, and the only adapter emitting `statistics` |
| 6 | `adapters/go/govet.py` | queued — one regex over diagnostics |

Every adapter written for the Python jig (`NEXT_STEPS.md` item 1) arrives with
its tests, rather than joining this queue.

## What this suite deliberately does not do

**It does not run the tools.** See above; that is `anvil`'s job to make possible
and no test's job to prove.

**It does not test bolt.** A test here that ran `bolt` would be testing the
runner through this repository, which is the dependency the three-repository
split exists to avoid. The `record` a test composes stands in for bolt, and the
schema in `schema/jig.schema.json` is what holds the two ends together.

**It does not assert on exact prose.** Checker output is read by people and will
be reworded. Tests assert that a finding *names* the file, id or count — never
that it phrases it a particular way.
