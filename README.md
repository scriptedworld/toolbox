# toolbox

Quality jigs for bolt, a runner that executes a project's quality gate, and the
checkers those jigs invoke.

Most projects grow a gate of their own: a lint config here, a coverage threshold
there, a script checking the thing nobody else checks. Across several projects
those drift, and the two obvious fixes both fail. Copy the configuration and
every copy is free to disagree with the others. Share one file and every project
is judged against whichever project's answers got baked into it.

A **jig** is a `bolt.*.yaml` file holding a set of tasks, where a task is a
command line plus, where one is needed, something that reads the output and
returns a verdict. This repository holds the jigs and the checkers they name.
What makes them shareable is the path rule below: a jig carries whatever does
the checking and never anything about the project being checked.

The dependencies run in a line and never a circle. bolt knows nothing about any
checker, and this repository knows nothing about how the tools get installed.
anvil, which builds the images the tools live in, reads the `requires:` fields
here and installs exactly those.

## What is not ready

**bolt is not published, and nothing here runs without it.** The jigs are
readable from a clone; running one is not yet possible for anybody outside the
machine bolt is built on.

The Python test suite imports `wrench` for the jig schema. wrench is also
unpublished and is currently resolved as a sibling checkout, so `pytest` does not
pass from a standalone clone either.

There are no releases and no version tags. Adoption tracks the default branch.

Jigs exist for Go and Python. Three adapters still speak a retired contract and
are wired to no task, so `format`, `vet` and `complexity` gate on exit status and
report no per-finding detail.

## What is here

| Jig | Checks |
|---|---|
| `bolt.common-quality.yaml` | Whatever the language: requirement traceability, the suppression register, complexity limits, and a composed secret scan |
| `bolt.go-std-quality.yaml` | Go: `gofmt`, `go mod tidy`, build, `vet`, `golangci-lint`, race-and-shuffle tests, per-file coverage, `govulncheck` |
| `bolt.python-std-quality.yaml` | Python: `ruff` format and lint, `mypy`, `pylint`, `complexipy`, `vulture`, `interrogate`, `bandit`, `pytest` |
| `bolt.secrets.yaml` | `gitleaks` and `detect-secrets` |

`common-quality` runs the secrets jig as a child task, so adopting the common
set gets you a secret scan. The reverse does not hold: `secrets` includes
nothing, because scanning a repository for credentials needs nothing else to be
true of it, and a project may adopt it alone.

## Adopting a jig

Adoption needs a clone of this repository, Python 3 with PyYAML for the linking
script, and bolt to run the result. Linking works today; running does not, for
the reason above.

`jigs.yaml` declares four sets: `common`, `go`, `python` and `secrets`. A
language set includes `common`, and `common` includes `secrets`, so naming one
set brings what it depends on.

Run this from your clone of toolbox, naming the project to link into:

```sh
python3 bin/link-jigs.py --plan ../your-project python
python3 bin/link-jigs.py --yes  ../your-project python
```

That links seven files into `../your-project`: three jigs, two checkers under
`bin/`, and two adapters under `adapters/common/`.

Adoption is symlinks rather than copies. A jig names its checkers through
`{config_dir}`, which resolves against the directory of the jig naming them, so
a jig reached through a link resolves them back through that same link and every
path stays inside the adopting project. Entries land at the same relative path
they have here, which the same rule forces: a linked jig sits at the target's
root, so `bin/x.py` has to be at `bin/x.py` to be found.

The links are relative by default, so the adopting project and this repository
have to keep their relative positions. `--absolute` writes absolute paths
instead, for a toolbox that does not travel with the project.

Nothing is ever overwritten. A real file where a link belongs is reported and
left alone, usually a vendored copy that predates adoption. That state looks
adopted and is not: the vendored copy runs instead of the shared one.

`--check` verifies an adoption without writing, and exits 1 on drift.

### What your project supplies

| File | Read by | Absent means |
|---|---|---|
| `REQUIREMENTS.md` | `traceability` | a failure: the check has nothing to hold the code to |
| `SUPPRESSIONS` | `suppressions` | fine if you have no pragmas, a failure if you do |
| `coverage.out` | `tests` | produced by the `tests` task, not by you |

Everything else a jig needs lives here. Nothing reaches outside those two places.

### Running one

One jig over one directory. The jig is named bare and read as `bolt.<name>.yaml`
from the config directory:

```sh
bolt common-quality .
bolt python-std-quality .
```

**Read `result.yaml`, not the exit status.** bolt exits 0 when the run
completed, whatever the tools concluded, and it exits 0 when it refuses the jig
outright. The verdict is `success` in that artifact. A failing run lists each
failure under `reasons`; a passing run carries no `reasons` key at all.

The common and language jigs are separate, so a project wanting both runs both.

### What a first run tends to report

`traceability` fails in both directions: a test that does not say what it
discharges, and a settled requirement that no test cites. Against an established
project the second is usually a long list.

The one exemption is the requirement's own status marker, the last bracketed
cell in its row.

| Row | Uncovered means |
|---|---|
| `\| FR-1.1 \| Any command-line tool can be run. \| [A] \|` | failure: settled, so testable |
| `\| FR-5.9 \| Schema versioning is unresolved. \| [?] \|` | reported, not fatal |

`[?]` marks an open decision that cannot have a test yet. Everything else is
settled: `[A]`, `[D]`, `[A/D]`, and no marker column at all. A document without
markers claims no exemptions, since exemption is claimed and never granted by
omission.

So there are two honest responses to that list: write the test, or mark the
requirement `[?]` and state in its own text what is still open.
`docs/DECISIONS/traceability-is-a-gate-not-a-report.md` carries the reasoning
and what was rejected.

## Checkers and adapters

A **checker** is what a task runs: usually an off-the-shelf tool such as
`gofmt`, `golangci-lint` or `lizard`, and where no such tool exists, a script
written here. Its exit code is the verdict, which is why most tasks need nothing
else.

An **adapter** is what a task names in its `adapter:` field. It reads the
execution record bolt captured and returns the envelope that becomes the
verdict. A task needs one only when the checker's exit code is not the answer.

```
1. bolt runs the CHECKER              gofmt -l .            -> exit 0
2. bolt captures                      stdout, stderr, code  -> the record
3. bolt hands the record to the ADAPTER
4. the adapter returns an envelope    success, reasons, statistics
5. bolt folds that envelope into the run's result
```

Step 4 is why adapters exist. `gofmt -l` lists unformatted files and exits 0
whichever it finds, so its exit status answers "did gofmt run" and never "is
this formatted".

The jig and envelope schemas live in wrench and this repository keeps no copy,
because a second description of a format is free to disagree with the one being
enforced. `tests/test_jigs.py` validates every jig here against the validator
wrench ships.

## The path rule

The easiest thing here to get wrong, and it decides whether a jig is adoptable
at all.

> **A path resolves against `{config_dir}` if it travels with the jig.** A
> checker, an adapter, a linter's config: these are the rule.
>
> **A path stays relative to the run root if it belongs to the project being
> checked.** Its source, its `REQUIREMENTS.md`, its `SUPPRESSIONS`: these are
> the subject.

A shared jig carries the rule and never the subject. Bundle a document *about a
codebase* into one and it has stopped being adoptable, because every adopter is
now judged against its author's answers.

Getting this backwards is invisible in the repository that gets it wrong. A jig
living at its own root has a `{config_dir}` equal to its run root, so both
spellings resolve to the same file and nothing ever shows. It breaks for
everyone else. Pointing the suppression register's `--register` at
`{config_dir}` made a project with one justified pragma report ten disagreements
against another project's register, and no state that project could reach would
have passed.

`tests/test_jigs.py` fails any jig that reaches `bin/`, `adapters/` or `config/`
without `{config_dir}`, and fails any jig that prefixes an `adapter:` with it,
which would resolve twice.

## Layout

```
bolt.*.yaml     the jigs
jigs.yaml       which files a project links to adopt a set
bin/            checkers written here, because no tool does the job
adapters/       record -> envelope, per task that needs one
config/         tool configuration that travels with a jig
tests/          one file per script under test
```

The suite never runs the tools it is about. An adapter test feeds the adapter
text the tool once produced, so the suite passes on a machine with none of them
installed. `docs/PATTERNS/testing-checkers-and-adapters.md` says why that
matters and what a test here has to assert.

## What is deliberately not here

**`entrypoint`**, which measures the statement in `main()` that `go test` can
never reach. It has to name a specific main package and a specific harmless
invocation of the resulting binary, and no substitution stands in for either, so
in a shared jig it fails for every adopter and the failure looks like the
adopter's own. It belongs in a project's own jig. The comment at the foot of
`bolt.go-std-quality.yaml` carries a worked example.

**A task that cannot fail.** Where no adapter can read a tool's output yet, the
task is left out rather than shipped green. An absent check tells a reader the
gate does not cover that property; a green one claims a guarantee it never
established. `docs/DECISIONS/a-task-that-cannot-fail-leaves-the-jig.md` has the
worked case and the one exception.

## Documentation

- `docs/PATTERNS/testing-checkers-and-adapters.md`, the two contracts and the
  different shape of test each one takes.
- `docs/DECISIONS/`, one file per decision, each with what was rejected and what
  would justify revisiting it.
- `docs/LESSONS/`, one file per fault worth not repeating.
- `REQUIREMENTS.md`, what a jig, a checker and an adapter have to be true of.
- `docs/PROJECT.md`, how this repository is laid out and gated.
- `CONTRIBUTING.md` and `SECURITY.md`.

## Licence

Apache-2.0. See `LICENSE` and `NOTICE`.
