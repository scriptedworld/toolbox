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
proposal for its own session rather than work to be done here:

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
