# toolbox

Quality definitions for [bolt](https://github.com/scriptedworld/bolt), and the
checkers they invoke.

A **definition** is a `bolt.*.yaml` file: a set of tasks, each a command line
and — optionally — something that reads its output and returns a verdict. bolt
runs them; this repository holds them; `anvil` builds the images that contain
the tools they require.

None of the three depends on the other two in a circle. bolt knows nothing about
any checker. This repository knows nothing about how the tools get installed.
anvil reads the `requires:` fields here and installs exactly those.

## Using them

Overlay the common definition under a language one. Later files win and tasks
merge by id, so a language file can adjust anything the common file sets without
restating it:

```sh
bolt -c bolt.common-quality.yaml -c bolt.go-std-quality.yaml
```

A project adjusts by overlaying a third file of its own:

```sh
bolt -c bolt.common-quality.yaml \
     -c bolt.go-std-quality.yaml \
     -c bolt.this-project.yaml
```

## What is here

| Jig | Holds |
|---|---|
| `bolt.common-quality.yaml` | Checks that do not care what language you wrote: requirement traceability, the suppression register, complexity limits |
| `bolt.go-std-quality.yaml` | Go: `gofmt`, `go mod tidy`, build, `vet`, `golangci-lint`, race-and-shuffle tests, per-file coverage, `govulncheck` |
| `bolt.python-std-quality.yaml` | Python: `ruff` format and lint, `mypy`, `pylint`, `complexipy`, `vulture`, `interrogate`, `bandit`, `pytest` |
| `bolt.secrets.yaml` | Secret scanning: `gitleaks`, `detect-secrets` |

## Checkers and adapters

Two roles, and the distinction runs through the whole layout.

A **checker** is what a task runs. Usually an off-the-shelf tool — `gofmt`,
`golangci-lint`, `lizard` — and, where none exists, a script written here.

An **adapter** is a task's `result_command`. It reads the execution record and
returns the envelope that becomes the verdict. Only needed when the checker's
exit code is not the answer.

```
1. bolt runs the CHECKER              gofmt -l .            -> exit 0
2. bolt captures                      stdout, stderr, code  -> the record
3. bolt hands it to the ADAPTER       gofmt.py
4. the adapter returns an envelope    success + reasons + statistics
5. bolt writes <n>_output.yaml        that envelope, captures merged back in
```

Step 4 is why adapters exist. `gofmt -l` lists unformatted files and exits 0
either way, so its exit status answers "did gofmt run", never "is this
formatted". The same shape, measured: `coverage`'s checker is `test -f
coverage.out` and exits 0, while its adapter returned `success: false` with a
file at 0.0% — the adapter's verdict is the task's verdict.

A task with no `result_command` needs no adapter: exiting 0 is its whole
contract, and bolt handles that natively.

```
bin/            checkers written here, because no tool does the job
  test-traceability.py     tests cite what they discharge, requirements have tests
  suppression-register.py  every pragma registered, every entry real
adapters/       record -> envelope, per task that needs one
  common/lizard.py         complexity, any language lizard reads
  go/{gofmt,govet,coverage}.py
config/         tool configuration that travels with a jig
  go-std-quality.golangci.yml   the 42-analyser config `lint` names explicitly
schema/
  jig.schema.json          validates a jig against what the parser accepts
tests/                    one file per script under test; see TESTING.md
  conftest.py              loads scripts by path, one fixture per contract
  fixtures/<tool>/*.txt    real captured tool output, dated and versioned
```

The suite never runs the tools it is about — an adapter test feeds the adapter
text the tool once produced — so it passes on a machine with none of them
installed. `TESTING.md` says why that matters and what a test here must assert.

## The path rule

The single thing most easily got wrong, and the thing that decides whether a
definition is adoptable at all.

> **A path resolves against `{configdir}` if it travels with the definition.**
> A checker, an adapter, a linter's config — these are the rule.
>
> **A path stays relative to the run root if it belongs to the project being
> checked.** Its source, its `REQUIREMENTS.md`, its `SUPPRESSIONS` — these are
> the subject.

A shared definition carries the rule and never the subject. One that bundles a
document *about a codebase* has stopped being adoptable, because it now judges
every adopter against its author's answers.

**Getting this backwards is invisible where it is written.** A definition living
at its own repository root has a `{configdir}` equal to its run root, so both
forms resolve to the same file and the mistake never shows. It breaks for
everyone else. Measured rather than reasoned: pointing `--register` at
`{configdir}` made a project with one justified pragma report ten disagreements
against another project's register, with no state it could reach that would
pass.

## Adopting these in a project

Everything a definition needs is either in this repository or in yours. Nothing
reaches outside both.

What your project supplies, if the relevant check is to do anything:

| File | Used by | Absent means |
|---|---|---|
| `REQUIREMENTS.md` | `traceability` | a failure — the check has nothing to hold the code to |
| `SUPPRESSIONS` | `suppressions` | fine if you have no pragmas; a failure if you do |
| `coverage.out` | `coverage` | produced by `tests`, not by you |

## What is deliberately not here

**`entrypoint`** — measuring the statement in `main()` that `go test` can never
reach. It was in the Go definition and had to come out: it names a specific main
package and a specific harmless invocation of the resulting binary, and bolt has
no substitution that could stand in for either. Left in a shared file it fails
for every adopter, in a way that looks like the adopter's fault.

It belongs in a project's own overlay, where hardcoding is correct because the
file is about that one project. A worked example is in the comment at the foot
of `bolt.go-std-quality.yaml`.

The general form: **a shared definition carries the rule and never the subject.**
`entrypoint` looked like a rule and was a subject.

## Traceability is a gate, not a report

Closed 2026-08-20, and it changes the verdict for adopters upgrading past it.

`traceability` fails in both directions. A test that does not say what it
discharges is one failure; **a requirement no test cites is the other**. Until
this change the second was printed as context and exited 0, which made
`REQUIREMENTS.md` a document nothing held the code to — the exact failure the
task exists to prevent, in the task itself.

The one exemption is the requirement's own status marker, the last bracketed
cell in its row:

| Row | Uncovered means |
|---|---|
| `\| FR-1.1 \| Any command-line tool can be run. \| [A] \|` | **failure** — settled, so testable |
| `\| FR-5.9 \| Schema versioning is unresolved. \| [?] \|` | reported, not fatal |

`[?]` marks an open decision that cannot have a test yet; failing on those would
make the honest state of the document unrepresentable. Everything else — `[A]`,
`[D]`, `[A/D]`, or **no marker column at all** — is settled. A document without
markers claims no exemptions, which is the right way round: exemption is
claimed, never granted by omission.

FACT 2026-08-20, both real adopters measured: `bolt` fails with 28 settled
requirements untested and 3 open ones exempt. `qwark` passes — its 16 untested
requirements are all marked `[?]`.

Facing a wall of these, an adopter has two honest moves: write the test, or mark
the requirement `[?]` and say why it cannot have one yet.

The checker reads Go (`*_test.go`) and Python (`test_*.py`, `*_test.py`) tests.
A language with a jig here but no entry in the checker's `LANGUAGES` table would
find no tests, cite nothing, and fail every requirement at once — so a new
language jig adds its entry in the same change.
