# toolbox, the project

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

> **A path resolves against `{config_dir}` if it travels with the jig.** A
> checker, an adapter, a linter's config: these are **the rule**.
>
> **A path stays relative to the run root if it belongs to the project being
> checked.** Its source, its `REQUIREMENTS.md`, its `SUPPRESSIONS`: these are
> **the subject**.

A shared jig carries the rule and never the subject. Bundle a document *about a
codebase* into one and it has stopped being adoptable, since every adopter is
then judged against its author's answers.

Getting this backwards is invisible in the repository that gets it wrong: a jig
at its own root has `{config_dir}` equal to the run root, so both spellings
resolve to the same file. `tests/test_jigs.py` exists to catch it, and fails any
jig that reaches `bin/`, `adapters/`, `config/` or `schema/` without
`{config_dir}`.

Measured in `agent-support`: `{config_dir}` resolves against **the symlink's own
directory and not its target**, which is why an adopter needs its own `bin/` and
`adapters/` links and cannot simply name a jig.

## Layout

    bolt.common-quality.yaml     language-agnostic: traceability, suppressions, complexity
    bolt.go-std-quality.yaml     Go: format, tidy, build, vet, lint, tests, vuln.
                                 No coverage; see docs/DECISIONS/
                                 a-task-that-cannot-fail-leaves-the-jig.md
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
    schema/         jig.schema.json and definitions.schema.json, copied from
                    wrench and held equal to it by a test
    tests/          one file per script under test; see
                    docs/PATTERNS/testing-checkers-and-adapters.md

## The gate

This repository is **its own adopter**, and uniquely so: it holds the real files
instead of symlinks, so `{config_dir}` is the repository root natively.

    bolt --definitions toolbox common-quality .
    bolt --definitions toolbox python-std-quality .
    bolt secrets .

**`--definitions toolbox` is not optional here, and no other adopter passes
it.** The shared jigs exclude `bin/` and `adapters/`, because in every other
adopter those hold symlinks to this repository's checkers and the adopter's
tools would grade toolbox's code as their own. This repository holds the real
files, so taking the default would stop it gating its own checkers, which is
silencing a gate rather than scoping one. `bolt.toolbox.definitions.yaml`
carries the override and says so.

One jig and one directory per run. Flags come before the positionals, and the
jig is named bare, read as `bolt.<name>.yaml` from `--config-dir`. Running three
in one invocation was the overlay model, which the current CLI does not have.

**Read `result.yaml`, never bolt's exit status.** Bolt exits 0 when the run
completed, whatever the tools concluded, and the verdict is in the artifact. It
also exits 0 when it refuses the jig outright.

From that artifact, **10 pass and 4 fail**. All four are open defects with a task
each.

| Task | | Why | Tracked as |
|---|---|---|---|
| `traceability` | ✗ 1 | 12 settled requirements have no test | `own-gate/10` |
| `analyse` | ✗ 16 | pylint 9.91/10, two missing docstrings in `adapters/common/lizard.py` | `own-gate/20` |
| `security` | ✗ 1 | bandit, 181 findings, **all Low**, 175 of them `assert` in a test, every one in `tests/` | `own-gate/20` |
| `detect-secrets` | ✗ 2 | crashes where no baseline exists | `own-gate/30` |

`complexity` measures each adopter's own code now, which it did not before. The
shared jigs exclude the directories adoption fills, so an adopter is no longer
graded on the checkers it adopted. Measured 2026-08-27: `agent-support` reads 1
function of its own where it read 23 of toolbox's, and `dotfiles`, `qwark` and
`palette-print` read 428, 485 and 232.

What remains of `shared-checkers/30` is narrower than it was: `complexity` still
misses a script with no file extension, which is how `silo`'s only source went
unread.

Of the 12 uncovered requirements, three are testable and are `own-gate/10`. The
other nine are design properties held by review, and *"a jig carries the rule and
never the subject"* is not an assertion. They are settled and not open, so they
carry no `[?]`.

## Its adopters

**Eight repositories run `common-quality` from this file**, measured 2026-08-27
by resolving each `bolt.common-quality.yaml`: `agent-support`, `anvil`,
`dotfiles`, `infobot`, `palette-print`, `qwark`, `silo`, and toolbox itself,
which holds the real file. `skid` runs the Python jig too.

All eight were refused outright until `51b8d59` ported the jigs to the format
the rebuilt bolt reads. `qwark` passes; the other seven fail on findings of
their own.

The table below is from commissioning and counts links rather than adopters.

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
overwrite them, and against the same tree bolt's fork exits 0 where this
repository's checker exits 1. Filed at
`clank/inbox/bolt/gate-runs-a-stale-fork-of-the-checkers/`; only bolt's own
session resolves it.

**Adoption records nothing about itself.** `--check` needs the set list as an
argument, and which sets a project adopted is written nowhere, so a wrong guess
reports drift that does not exist. It is `adoption/10`, and a precondition for
`--check` ever becoming a gate task.

## Where the work lives

`~/.projects/clank/tasks/toolbox/` holds the tasks, one directory each, grouped.
The listing is the index, and `NEXT_STEPS.md` holds only what has no task yet.

`~/.projects/clank/inbox/toolbox/` holds 14 findings filed by other sessions.
Not all are tracked by a task. An inbox entry is an observation, and
**only this project's session resolves one**.

## Documents

- `README.md`, for a human arriving cold.
- `REQUIREMENTS.md`, 59 requirements, still one file and no longer forced to be.
- `NEXT_STEPS.md`, the open decisions and the handoff owed to bolt, never the
  queue.
- `docs/PATTERNS/testing-checkers-and-adapters.md`, how the two contracts are
  tested and why they differ.
- `docs/DECISIONS/` and `docs/LESSONS/`, one file per decision and per lesson.
- `silo/docs/GLOSSARY.md`, the vocabulary, shared with bolt and anvil.

**`REQUIREMENTS.md` and `SUPPRESSIONS` are still single files and are no longer
forced to be.** They stayed single because `--requirements <DIR>` died with an
unhandled `IsADirectoryError`, the guard being `.exists()`, which a directory
satisfies. `shared-checkers/10` closed that at `cc65aad`: both checkers read a
directory or a file, and `.retired` names a retired requirement without needing
a `## Retired` heading.

Measured 2026-08-27, splitting a copy of this repository's own document: 59 rows
into 59 files, both forms reporting `43 of 55 requirements covered; 4 open and
exempt`, byte-identical output. So the split is available and is a separate
change nobody has made. `skid` and `agent-support` have made theirs.

There is no `SUPPRESSIONS` file and no `docs/SUPPRESSIONS/`, because nothing here
is silenced. See `docs/DECISIONS/no-suppressions-file-while-nothing-is-silenced.md`.
The same holds for `docs/MOCKS/`.

There is no project `CLAUDE.md`. Everything a session must obey here arrives from
the global one.

## How it fits with the others

    bolt      runs jigs. Knows nothing about any checker.
    toolbox   holds the jigs, and the checkers and adapters they name.
    anvil     builds images carrying the tools a jig `requires:`.

`requires:` declares **executables**, not libraries. Nothing here declares that
the adapters need PyYAML: it works by ambient availability, which is why
`types-PyYAML` was unavailable and `pyproject.toml` carries a mypy override in
place of the stub package. If anvil is ever to install from a declaration instead
of a guess, that gap is what it will hit.
