# toolbox, the project

Derived from `README.md`, `silo/docs/GLOSSARY.md`,
`docs/PATTERNS/testing-checkers-and-adapters.md`, and from measuring this
repository and its six adopters.

Read `silo/docs/GLOSSARY.md` before editing anything here. *Checker* and
*adapter* mean specific and opposite things, and most of what follows is
meaningless if the two are read as synonyms.

## What toolbox is FOR

It holds the **jigs**, which are `bolt.*.yaml` files each carrying a set of
tasks, and it holds the **checkers** and **adapters** those tasks name. bolt runs
them; anvil installs the tools they require.

It is a separate repository so that neither bolt nor anvil owns them. The three
depend on each other in a line and never a circle: bolt knows nothing about any
checker, this repository knows nothing about how the tools get installed, and
anvil derives its package lists from the `requires:` fields here instead of
keeping a second copy beside them.

## The one rule that decides whether a jig is adoptable

> **A path resolves against `{configdir}` if it travels with the jig.** A
> checker, an adapter, a linter's config: these are **the rule**.
>
> **A path stays relative to the run root if it belongs to the project being
> checked.** Its source, its `REQUIREMENTS.md`, its `SUPPRESSIONS`: these are
> **the subject**.

A shared jig carries the rule and never the subject. Bundle a document *about a
codebase* into one and it has stopped being adoptable, since every adopter is
then judged against its author's answers.

Getting this backwards is invisible in the repository that gets it wrong: a jig
at its own root has `{configdir}` equal to the run root, so both spellings
resolve to the same file. `tests/test_jigs.py` exists to catch it, and fails any
jig that reaches `bin/`, `adapters/`, `config/` or `schema/` without
`{configdir}`.

Measured in `agent-support`: `{configdir}` resolves against **the symlink's own
directory and not its target**, which is why an adopter needs its own `bin/` and
`adapters/` links and cannot simply name a jig.

## Layout

    bolt.common-quality.yaml     language-agnostic: traceability, suppressions, complexity
    bolt.go-std-quality.yaml     Go: format, tidy, build, vet, lint, tests, coverage, vuln
    bolt.python-std-quality.yaml Python: format, lint, types, analyse, cognitive,
                                 dead-code, docstrings, security, tests
    bolt.secrets.yaml            gitleaks, detect-secrets
    jigs.yaml                    which files a project links to adopt a set

    bin/            checkers written here, because no tool does the job
      test-traceability.py     tests cite what they discharge; requirements have tests
      suppression-register.py  every pragma registered, every entry real
      link-jigs.py             makes an adopter's symlinks, per jigs.yaml
    adapters/       record -> envelope, per task that needs one
      common/lizard.py         complexity, any language lizard reads
      go/{gofmt,govet,coverage}.py
    config/         tool configuration that travels with a jig
    schema/         jig.schema.json — validates a jig against what the parser accepts
    tests/          one file per script under test; see
                    docs/PATTERNS/testing-checkers-and-adapters.md

## The gate

This repository is **its own adopter**, and uniquely so: it holds the real files
instead of symlinks, so `{configdir}` is the repository root natively.

    bolt -c bolt.common-quality.yaml -c bolt.python-std-quality.yaml -c bolt.secrets.yaml

**Read `run_result.yaml`, never bolt's exit status.** That run exited **0** while
`run_result.yaml` said `success: false`.

From that artifact, **10 pass and 4 fail**. All four are open defects with a task
each, and none is accepted as permanent state.

| Task | | Why | Tracked as |
|---|---|---|---|
| `traceability` | ✗ 1 | 12 settled requirements have no test | `own-gate/10` |
| `analyse` | ✗ 16 | pylint 9.83/10, nine missing docstrings across six files | `own-gate/20` |
| `security` | ✗ 1 | bandit, 117 findings, **all Low**, 108 of them `assert` in a test | `own-gate/20` |
| `detect-secrets` | ✗ 2 | crashes where no baseline exists | `own-gate/30` |

`complexity` genuinely measures this repository's own code: the artifact lists
functions from `adapters/common/` and `tests/`. **It does not do that for the
other five adopters**, which is `shared-checkers/30`.

Of the 12 uncovered requirements, three are testable and are `own-gate/10`. The
other nine are design properties held by review, and *"a jig carries the rule and
never the subject"* is not an assertion. They are settled and not open, so they
carry no `[?]`.

## Its adopters

Measured with `link-jigs.py --check`:

| Adopter | Sets | Links | `--check` |
|---|---|---|---|
| `qwark` | go, secrets | 10 | ✓ |
| `dotfiles` | go, secrets | 10 | ✓, its Go lives under `go/` |
| `silo` | common, secrets | 5 | ✓ |
| `agent-support` | common, secrets | 5 | ✓ |
| `anvil` | common, secrets | 5 | ✓ |
| `bolt` | go, secrets | 6 | ✗ |

`bolt` is the one that has not taken. It still carries its own pre-split copies
at `tools/` and `adapters/`, so `link-jigs` refused four paths rather than
overwrite them. Against the same tree, bolt's fork exits 0 where this
repository's checker exits 1. It is filed at
`clank/inbox/bolt/gate-runs-a-stale-fork-of-the-checkers/`, and only bolt's own
session resolves it.

**Adoption records nothing about itself.** `--check` needs the set list as an
argument, and which sets a project adopted is written nowhere, so a wrong guess
reports drift that does not exist. That happened at commissioning, against
`dotfiles`. It is `adoption/10`, and a precondition for `--check` ever becoming a
gate task.

## Where the work lives

`~/.projects/clank/tasks/toolbox/` holds the tasks, one directory each, grouped.
The listing is the index, and `NEXT_STEPS.md` holds only what has no task yet.

`~/.projects/clank/inbox/toolbox/` holds eleven findings filed by other sessions,
every one of them now tracked by a task. An inbox entry is an observation, and
**only this project's session resolves one**.

## Documents

- `README.md`, for a human arriving cold.
- `REQUIREMENTS.md`, 48 requirements, deliberately still one file.
- `NEXT_STEPS.md`, the open decisions and the handoff owed to bolt, never the
  queue.
- `docs/PATTERNS/testing-checkers-and-adapters.md`, how the two contracts are
  tested and why they differ.
- `docs/DECISIONS/` and `docs/LESSONS/`, one file per decision and per lesson.
- `silo/docs/GLOSSARY.md`, the vocabulary, shared with bolt and anvil.

**`REQUIREMENTS.md` and `SUPPRESSIONS` stay single files, and the reason is
mechanical.** `test-traceability.py --requirements <DIR>` dies with an unhandled
`IsADirectoryError`, because the guard is `.exists()` and a directory satisfies
it. This repository is gated on that checker, so splitting its own requirements
would turn a check that runs into one that crashes. The split waits on
`shared-checkers/10`.

There is no `SUPPRESSIONS` file and no `docs/SUPPRESSIONS/`, because nothing here
is silenced. See `docs/DECISIONS/no-suppressions-file-while-nothing-is-silenced.md`.
The same holds for `docs/MOCKS/`.

There is no project `CLAUDE.md`, and that is correct. Everything a session must
obey here arrives from the global one.

## How it fits with the others

    bolt      runs jigs. Knows nothing about any checker.
    toolbox   holds the jigs, and the checkers and adapters they name.
    anvil     builds images carrying the tools a jig `requires:`.

`requires:` declares **executables**, not libraries. Nothing here declares that
the adapters need PyYAML: it works by ambient availability, which is why
`types-PyYAML` was unavailable and `pyproject.toml` carries a mypy override in
place of the stub package. If anvil is ever to install from a declaration instead
of a guess, that gap is what it will hit.
