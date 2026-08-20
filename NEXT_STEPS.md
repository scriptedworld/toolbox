# toolbox — Next Steps

Queued work, and the decisions recent enough to still be worth stating.

Read `GLOSSARY.md` first if any of *jig*, *checker*, *adapter*, *envelope* or
*the rule versus the subject* is unfamiliar. The terminology is load-bearing and
several of these tasks are meaningless without it.

---

## Current state

Four jigs, all validating against `schema/jig.schema.json`:

| Jig | Tasks |
|---|---|
| `bolt.common-quality.yaml` | traceability, suppressions, complexity |
| `bolt.go-std-quality.yaml` | format, tidy, build, vet, lint, tests, coverage, vuln |
| `bolt.python-std-quality.yaml` | format, lint, types, analyse, cognitive, dead-code, docstrings, security, tests |
| `bolt.secrets.yaml` | gitleaks, detect-secrets |

FACT 2026-08-18: common + go, run against a copy of `bolt`, gives 11 pass and
one fail — `coverage`, on `cmd/bolt/main.go` at 0.0%, which is the expected
consequence of task 2 below and not a defect.

FACT 2026-08-18: `{configdir}` resolution was verified across a real repository
boundary for the first time. Checkers and the golangci config resolved into this
repository; `REQUIREMENTS.md` and `SUPPRESSIONS` stayed in the project being
checked. Inside `bolt` the two are the same directory, so the rule could never
previously be exercised.

FACT 2026-08-20: the traceability known gap is closed. `traceability` now fails
on an uncovered **settled** requirement and reports an uncovered **open** one,
open being `[?]` in the row's last bracketed cell. It reads Go and Python tests.
Measured against both real adopters: `bolt` exits 1 with 28 settled requirements
untested and 3 open ones exempt; `qwark` exits 0, its 16 untested requirements
all marked `[?]`. Owner's decision, taken deliberately as a tightening rather
than absorbed as drift. See the README section *Traceability is a gate, not a
report*.

FACT 2026-08-20: the checkers have tests. 32 of them, at 100% statement and
branch coverage of `bin/` and `adapters/go/gofmt.py`, running in 0.16s with none
of the tools they are about installed. `TESTING.md` is the standing document for
how and why; the adapter queue is at the foot of it.

FACT 2026-08-20: adding Python surfaced a latent crash in the checker's sort
key, which compared an `int` segment against a `str` one and raised `TypeError`
on any id carrying a letter. `bolt` has none, so `bolt` could never have found
it; `qwark`'s `FR-4.13a` did on the first run. Fixed by keying every segment as
`(number, suffix)`.

---

## 1. Adapters for the Python jig — the largest gap

**Every Python task fails with `exited 1` and nothing else.** No file, no line,
no reason. The tools all exit non-zero correctly; nothing turns their output
into an envelope, so the gate says *that* it failed and never *why*.

FACT 2026-08-18, measured against this repository: `format`, `lint`, `types`,
`analyse` and `docstrings` all failed with an empty `reasons` list.

**Write it as one adapter first, not seven.** Most of these emit the same
near-universal shape — `file:line:col: message` — so a single
`adapters/common/lineformat.py` parameterised by checker name would cover ruff,
mypy, vulture and more. Reach for a per-tool adapter only where the tool's
native structured output carries something the line format loses.

| Checker | Structured output | Notes |
|---|---|---|
| `ruff` | `--output-format=json` | Rich: rule code, fix availability, ranges |
| `pylint` | `--output-format=json` | Includes symbol and category |
| `mypy` | line format | JSON output varies by version; parse lines |
| `bandit` | `-f json` | Carries severity and confidence — put both in the reason |
| `vulture` | line format | Confidence percentage is in the message text |
| `complexipy` | check for a JSON flag | Otherwise line format |
| `interrogate` | table only | Coverage percentage belongs in `statistics`, not reasons |

**Every adapter emits `statistics` as well as `reasons`, on pass and on fail.**
That is the lesson from `lizard.py`: a number is only useful as a series, and a
task that reports nothing when it passes cannot show a trend. `interrogate`'s
docstring percentage and `ruff`'s finding count are exactly this.

Adapters are pure — record in, envelope out, no clock, no filesystem — so each
is testable from a fixture record with the tool absent.

## 2. `entrypoint` coverage needs a home

Pulling `entrypoint` out of the Go jig was right: it hardcoded `./cmd/bolt` and
would fail for every adopter. But nothing now measures the statement in `main()`
that `go test` cannot reach, so `coverage` fails on any Go project with an entry
point — which is all of them.

Three routes, and this wants deciding rather than defaulting:

- **A documented project-overlay pattern.** A worked example already sits in the
  comment at the foot of `bolt.go-std-quality.yaml`. Cheapest, and it puts the
  hardcoding where hardcoding is correct.
- **A `main.go`-shaped exclusion in the coverage adapter.** Simple, and it is
  exactly the "settle a coverage failure by excluding the file" move that a
  standing rule elsewhere forbids. Recorded so it is rejected deliberately.
- **Parameterise it.** Needs a substitution bolt does not have. Would require a
  change to bolt, which is out of scope here.

## 3. More from lizard, and from the checkers generally

`lizard.py` now emits eight summary fields. FACT 2026-08-18, verified in a
passing run: `total_nloc`, `avg_nloc`, `avg_ccn`, `avg_token`, `functions`,
`warnings`, `function_rate`, `nloc_rate`.

What is still on the floor: lizard's **per-file** table, which it prints above
the summary and which nothing currently reads. Per-file NLOC and average CCN
would let a report say which file is drifting rather than only that the average
moved. Consider `--csv` for this, but keep the thresholds as flags in the jig —
moving policy into an adapter is how two gates start disagreeing.

## 4. The Python coverage threshold is measured but not enforced

`tests` produces `coverage.xml`; nothing reads it. The Go jig judges coverage
**per file** at 80%, deliberately refusing an aggregate because an aggregate
lets a well-tested file carry an untested one. The same task belongs here and
needs an adapter that reads Cobertura XML and applies the threshold per file.

Until then coverage is collected and not enforced, which is worth saying out
loud rather than leaving as an apparent oversight.

## 5. Second opinions on the secrets jig

`trufflehog` is the obvious third scanner and it goes further than both current
ones by **verifying** findings against the provider's API. That is a network
call to a third party carrying a credential found in your source, so adopting it
is a decision about egress rather than about coverage. FACT 2026-08-18: not
installed on this machine.

Also worth stating in the jig: **rotation is not a check.** Neither scanner can
tell whether a found credential has been revoked, and a green run after deleting
a secret from the working tree has reported on the tree, not on the secret.

## 6. The uncovered requirements are now a backlog, not a note

`bolt`'s 28 untested settled requirements were previously context; they are now
a failing gate. The checker prints the list with each requirement's marker on
any failing run, so the backlog is derived rather than copied here — copying it
is how it goes stale. Each entry wants one of two things, and the choice is per
requirement rather than per batch:

- **a test**, where the requirement is genuinely testable and nobody wrote one;
- **`[?]` and a sentence saying why**, where it cannot be tested yet.

Reaching for `[?]` to quiet the gate is how the exemption stops meaning
anything. The marker says *this decision is open*, not *this is inconvenient* —
so a requirement moved to `[?]` states the open question in its own text, the
way `FR-4.10` and `FR-5.9` already do.

Several of the 28 look like the second case on their face — `NFR-1` ("no AI
dependency") and `NFR-3` (a cost claim about runtimes) are properties of the
design rather than observable in a run. CLAIM, not measured: that is a reading
of the requirement text, not an audit. Walking the list is bolt's session, not
this one.

## 7. `suppressions` is Go-only inside the language-agnostic jig

DEFECT, FACT 2026-08-20, measured: a Python project with `# nosec B602` in its
source and nothing in its register **passes**. `scan_source` walks `*.go` only,
and `INDEX_ROW` requires gosec's `G\d+` or a `//nolint:` list — while the
register format documented in the same file accepts `.py` paths, which implies
a Python support that does not exist.

This is the traceability defect's twin: a shared task in
`bolt.common-quality.yaml` that silently reads one language. The traceability
version was loud once uncovered meant fail. This one is **a false green** —
Python's `# nosec`, `# noqa`, `# type: ignore` and `# pylint: disable` are not
silenced-and-justified, they are silenced and unseen.

Pinned executably by `tests/test_suppression_register.py::
test_python_pragmas_are_invisible_to_this_checker`, so it stays a defect rather
than becoming folklore. Fixing it newly fails every adopter carrying an
unregistered pragma, so it is the same shape of deliberate tightening the
traceability change was, and wants the same explicit decision.

## 8. The Rust jig, and what it costs the shared checkers

FACT 2026-08-20, installed on this machine and available to `requires:`:
`cargo fmt`, `cargo clippy`, `cargo audit`, `cargo deny`, `cargo llvm-cov`.
`cargo-tarpaulin` is **not** installed — use `llvm-cov` for coverage.

**Rust breaks the traceability checker's current design, and this is the part
worth knowing before starting.** FACT 2026-08-20, read from real crate source
(`hashbrown-0.17.1/src/{table,set,map}.rs`): a Rust unit test is

```rust
    #[test]
    fn test_allocation_info() {
```

— indented inside `#[cfg(test)] mod tests`, **in an ordinary `.rs` source
file**, not in a `*_test.rs` file. The `LANGUAGES` table keys on a filename
glob plus a declaration regex. For Go and Python the glob is a reliable filter:
a test lives in a test file. For Rust it is not. The glob would have to be
`*.rs`, which matches every function in the crate, and what makes a function a
test is the **attribute above it**, not its name or its file.

So Rust needs one new field on `Language`: a **gate** — a pattern that must
appear in the block above a declaration for it to count as a test. The
machinery is already half there, because stepping over Python's decorators
means the block above the declaration is already being walked.

Also needed: `suppression-register.py` learning `#[allow(clippy::…)]` and
`#[allow(dead_code)]`, which item 7 is the prerequisite for.

## 9. The Ruby jig, which splits in two

FACT 2026-08-20, installed: `rubocop`, `rspec`, `reek`, `bundler`.
`brakeman` is **not** installed, so the security task needs deciding rather
than assuming.

Traceability splits by test framework, and only one half drops in:

| Framework | Shape | Fits the current `LANGUAGES` table? |
|---|---|---|
| minitest | `test/**/*_test.rb`, `def test_foo` | **yes**, unchanged — a glob and a declaration regex |
| RSpec | `spec/**/*_spec.rb`, `it "…" do` | **no** — an example has no function name; its identity is a string |

Either the checker learns a block-declared form where the name is a quoted
string, or the Ruby jig states plainly that traceability covers minitest only.
CLAIM, not yet decided: stating the limit is better than a half-working parser,
because a checker that silently misses every RSpec example is item 7 again.

`suppression-register.py` also needs `# rubocop:disable Style/Foo`.

## 10. `mypy .` failed on this repository before this session

FACT 2026-08-20: `mypy .` reported 4 errors on a clean tree at `2adfcae`, all
`Library stubs not installed for "yaml"`. The `types` task was red on toolbox
itself and nothing said so.

Settled for now in `pyproject.toml`, which is where the python jig's own comment
says strictness decisions belong — the jig runs a bare `mypy .` deliberately.
The better answer is `types-PyYAML`, not an override, and it is not used because
nothing here declares runtime dependencies: bolt invokes these scripts by path
against whatever interpreter `anvil` built. Revisit when anvil carries the stub
packages.

## 11. `bandit -r -q .` fails any project that has tests

FACT 2026-08-20, measured the moment this repository grew a test suite: 72
findings, **all Low severity, zero Medium, zero High**. 66 are `B101
assert_used` — an `assert` in a test is the test — and the rest are `B404`/`B603`
for the `subprocess` calls that check each script runs as a script.

`bandit -r -q .` exits non-zero on any finding at any severity, so the
`security` task now fails on toolbox, and would fail on every adopter with a
pytest suite. The jig's own comment says findings are silenced with `#nosec` and
held by the `suppressions` task — which is right for a real finding and absurd
for sixty-six asserts.

Two conventional answers, and this wants deciding rather than defaulting:

- **`-x ./tests`** — exclude the test tree. Says test code is not the attack
  surface, which is true of B101 and not true of a test that shells out.
- **`--severity-level medium`** — report Low, fail on Medium and above. Keeps
  the test tree scanned. Loses the ability to fail on a genuine Low finding,
  which for bandit is mostly noise anyway.

Recommended: `--severity-level medium`, because excluding a directory is the
move that stops being revisited, and because item 7 is a live example of what a
silently unscanned tree costs.

## 12. Two shipped jig defects found by running the gate on this repository

Both were invisible because nothing ran the Python jig against a Python project
that had tests. FACT 2026-08-20:

| Task | Was | Effect on an adopter |
|---|---|---|
| `cognitive` | `complexipy --max-complexity 15 .` | **Fixed.** The flag is `--max-complexity-allowed`; complexipy 7.0.1 exits on a usage error rather than a verdict, so the task failed for everyone in a way that looked like their code |
| `security` | `bandit -r -q .` | Open — see item 11 |

`analyse` (`pylint --recursive=y .`) is also red on this repository, at 9.79/10
with two missing docstrings in `adapters/common/lizard.py`. Pre-existing and
small; it belongs with the lizard work in item 3.

The general lesson, and the reason items 1 and 4 matter more than they look:
**a jig nobody runs against a real project of that language is a jig nobody has
tested.** The Go jig has been run against `bolt` and `qwark`; the Python jig had
been run against a repository with no Python tests in it.

## 13. toolbox's own requirements, and its own backlog

FACT 2026-08-20: `REQUIREMENTS.md` written, 48 requirements, and this repository
now runs its own traceability gate against itself. `36 of 48 requirements
covered; 4 open and exempt` — so it **fails its own gate on 12**, and that is
the honest state rather than a reason to soften the gate.

The 12 split into two kinds, and only one of them is a test-writing task:

**Genuinely testable, and queued.** `FR-3.6` (an adapter reporting output it
cannot parse from a checker that also exited non-zero) needs the `lizard`
adapter tests from `TESTING.md`'s queue. `FR-7.14` (a link resolving outside the
target is refused) has a `State.ESCAPES` in `link-jigs.py` and no test reaching
it. `NFR-4` (fixtures carry provenance) is assertable directly: every file under
`tests/fixtures/` should open with a comment naming the tool version and the
capture date.

**Design properties a unit test cannot reach.** `FR-1.1`, `FR-1.3`, `FR-2.1`,
`FR-2.2`, `FR-3.3`, `FR-6.1`, `FR-7.3`, `NFR-1`, `NFR-2` — *"a jig carries the
rule and never the subject"* is enforced by review, not by assertion.
`tests/test_jigs.py` shows the middle ground: `FR-1.4` and `FR-1.5` looked like
design properties and turned out to be assertable against the jig documents
themselves. Some of the nine may go the same way; reaching for `[?]` to quiet
them would not, because they are not open questions.

**No `SUPPRESSIONS` file, deliberately.** FACT 2026-08-20: this repository
carries no suppression pragma of any kind, and `suppression-register.py` reports
*"no suppression pragmas anywhere, and none registered"* and exits 0. An empty
register would be a file asserting nothing.

## Open decisions

**Where does the schema belong?** `schema/jig.schema.json` describes bolt's
configuration format, which is bolt's to define — but it lives here because this
is where jigs live. If bolt ever ships its own, this one must be deleted rather
than allowed to drift into a second, disagreeing description of one format.

**Should jigs be discoverable by short name?** `bolt --use go-std-quality`
resolving against a `BOLT_TOOLBOX` environment variable, rather than repeated
`-c` with full paths. Ordering must stay explicit — a directory glob has no
order, and order is semantics here. Needs a change to bolt.

**A project-level composition file.** `use: [common-quality, go-std-quality]` in
the project, so the invariant part is not retyped and bare `bolt` knows what the
gate is. Also needs a change to bolt, and interacts with the previous item.

---

## Handoff owed to bolt

`bolt` still carries its own copies of everything in this repository. **It is
hands-off to this session by the owner's instruction**, so the following is a
proposal for its own session rather than work to be done here.

FACT 2026-08-20, and the reason this stopped being tidiness and became a
correctness problem: **`just checks` in `bolt` does not run this repository's
checkers.** It runs `./bin/bolt -c bolt.go-std-quality.yaml`, whose
`traceability` task points at `{configdir}/tools/test-traceability.py` — bolt's
own pre-split fork, which still carries *"requirements with no test at all are
reported as context, never as a failure"*. Against the same tree, on the same
day: bolt's copy exits **0**, this repository's exits **1**. `bolt` contains no
reference to `toolbox` at all.

So the traceability tightening is invisible from inside `bolt`, and will stay
invisible until the handoff below lands. Verified working through the runner
rather than only through `python3`:

    ./bin/bolt -c …/toolbox/bolt.common-quality.yaml \
               -c …/toolbox/bolt.go-std-quality.yaml traceability

gives `FAIL traceability · 1 of 1 failing` and `success: false` in
`run_result.yaml`. Note that **bolt's own exit status is 0 on that run**, which
is FR-6.8 working as specified and not a second bug — the verdict is the file,
never the exit code.

The proposal:

1. Delete `bolt.go-std-quality.yaml`, `go-std-quality.golangci.yml`,
   `adapters/` and `tools/` from `bolt`, now that they live here.
2. Add `bolt.this-project.yaml` carrying the `entrypoint` task, which is the
   only genuinely bolt-specific check.
3. Point `just checks` at this repository. Note this changes bolt's stated
   property that its gate *"must pass on a fresh clone with `GATES` unset"* —
   the gate would then need this repository cloned too. That is a real change to
   a recorded requirement and should be decided, not absorbed.
4. `CLAUDE.md`'s task count and the `~~Ten~~ twelve` line will both need
   revisiting once the split lands.
