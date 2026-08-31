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

**bolt is not published, and nothing here runs without it.** The test suite also
imports wrench, likewise unpublished and currently resolved as a sibling
checkout. So the jigs are readable from a clone, but neither running one nor
running `pytest` works from a standalone one.

There are no releases and no version tags, so adoption tracks the default
branch. Jigs exist for Go and Python only. Three adapters still speak a retired
contract and are wired to no task, which leaves `format`, `vet` and `complexity`
gating on exit status with no per-finding detail.

## What is here

| Jig | Checks |
|---|---|
| `bolt.common-quality.yaml` | Whatever the language: requirement traceability, the suppression register, complexity limits, and a composed secret scan |
| `bolt.go-std-quality.yaml` | Go: `gofmt`, `go mod tidy`, build, `vet`, `golangci-lint`, race-and-shuffle tests, per-file coverage, `govulncheck` |
| `bolt.python-std-quality.yaml` | Python: `ruff` format and lint, `mypy`, `pylint`, `complexipy`, `vulture`, `interrogate`, `bandit`, `pytest` |
| `bolt.secrets.yaml` | `gitleaks` and `detect-secrets` |

`common-quality` runs the secrets jig as a child task, so adopting the common
set brings a secret scan with it. `secrets` includes nothing and can be adopted
alone.

## Adopting a jig

Needs a clone of this repository, Python 3 with PyYAML, and bolt to run the
result. Linking works today; running does not, for the reason above.

`jigs.yaml` declares four sets: `common`, `go`, `python` and `secrets`. A
language set includes `common`, and `common` includes `secrets`, so naming one
brings what it depends on. Run this from your clone of toolbox:

```sh
python3 bin/link-toolbox.py --plan ../your-project python
python3 bin/link-toolbox.py --yes  ../your-project python
```

That links seven files: three jigs, two checkers and two adapters. They are
symlinks rather than copies, landing at the same relative path they have here,
because a jig finds its checkers through `{config_dir}` and a jig reached
through a link resolves them back through that link. The links are relative
unless you pass `--absolute`, so the two directories have to keep their
positions.

Nothing is ever overwritten, so a project holding an older vendored copy looks
adopted and is not. `--check` verifies an adoption without writing, and exits 1
on drift.

### A repository holding several projects

**Adoption assumes one root.** A file lands at the same relative path it has
here, so linking into a repository root gates that root. A repository holding
several projects has two ways to use that and they are not interchangeable.

**Adopt per subproject** when each is its own project in its own language. Run
the linker once per directory. Each then gates itself and knows nothing about
its siblings, and the root coordinates them: a `just` recipe that fans out, or a
bolt task that runs bolt against each subdirectory and takes its verdict.
`wrench/docs/runbook.md` is a worked example, three packs in three languages
plus one check at the root that no pack could run because it reads all three.

**Adopt at the root** when the subdirectories are parts of one project rather
than projects in their own right.

The question is who owns the verdict. If a subdirectory can fail on its own
terms, it adopts on its own terms.

### What your project supplies

| File | Read by | Absent means |
|---|---|---|
| `REQUIREMENTS.md` | `traceability` | a failure: the check has nothing to hold the code to |
| `SUPPRESSIONS` | `suppressions` | fine if you have no pragmas, a failure if you do |
| `coverage.out` | `tests` | produced by the `tests` task, not by you |
| `bolt.<name>.definitions.yaml` | any task carrying a placeholder | the jig's own defaults stand, which suit a project laid out like this one |

Everything else a jig needs lives here. Nothing reaches outside those two places.

A definitions file overrides a jig's placeholders and is passed by name, so
`bolt --definitions mine common-quality .` reads `bolt.mine.definitions.yaml`
from the config directory. It is a flat mapping of placeholder to scalar and
carries no `definitions:` wrapper, unlike the block inside a jig that declares
the defaults. Each value becomes one shell word, so a placeholder names a path
or a program and never a command line. Every jig's header lists what it defines
and what its default assumes; the Go jig's `entrypoint` is the one most adopters
have to fill, because it names the script that measures `main()`.

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

`traceability` is the strict one, and it fails in both directions: a test that
does not say what it discharges, and a settled requirement that no test cites.
Against an established project the second is usually a long list, and the two
honest responses are to write the test or to mark the requirement as an open
decision. `docs/DECISIONS/traceability-is-a-gate-not-a-report.md` has the status
markers and the reasoning.

## Checkers and adapters

A **checker** is what a task runs: usually an off-the-shelf tool such as
`gofmt`, `golangci-lint` or `lizard`, and where no such tool exists, a script in
`bin/`. Its exit code is the verdict, which is why most tasks need nothing else.

An **adapter**, in `adapters/`, is what a task names in its `adapter:` field. It
reads the execution record bolt captured and returns the envelope that becomes
the verdict. A task needs one only when the checker's exit code is not the
answer. `gofmt -l` is the case that forces them: it lists unformatted files and
exits 0 whichever it finds, so its exit status answers "did gofmt run" and never
"is this formatted".

The rest of the tree is `config/` for tool configuration travelling with a jig,
and `tests/`, one file per script under test.
`docs/PATTERNS/testing-checkers-and-adapters.md` has the two contracts in full.

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
spellings resolve to the same file and nothing shows. It breaks for everyone
else: pointing the suppression register at `{config_dir}` made a project with
one justified pragma report ten disagreements against another project's
register, and no state that project could reach would have passed.

## What is deliberately not here

**`entrypoint`**, which measures the statement in `main()` that `go test` cannot
reach. It has to name a specific main package and a specific invocation of the
built binary, so in a shared jig it fails for every adopter and the failure
looks like the adopter's own. The foot of `bolt.go-std-quality.yaml` shows where
it belongs instead.

**A task that cannot fail.** Where no adapter can read a tool's output yet, the
task is left out rather than shipped green. An absent check tells you the gate
does not cover that property; a green one claims a guarantee it never
established. `docs/DECISIONS/a-task-that-cannot-fail-leaves-the-jig.md` has the
worked case.

## Documentation

`CONTRIBUTING.md` to change something here, `SECURITY.md` for the trust boundary
and how to report a vulnerability, `REQUIREMENTS.md` for what a jig, a checker
and an adapter have to be true of, and `docs/` for the decisions, the lessons
and how the two contracts are tested.

## Licence

Apache-2.0. See `LICENSE` and `NOTICE`.
