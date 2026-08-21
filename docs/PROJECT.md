# toolbox — the project

Commissioned 2026-08-21. Derived from `README.md`, `silo/docs/GLOSSARY.md`,
`docs/PATTERNS/testing-checkers-and-adapters.md` and from measuring this
repository and its six adopters.

Read **`silo/docs/GLOSSARY.md`** before editing anything here. *Checker* and
*adapter* mean specific and opposite things, and most of what follows is
meaningless if they are read as synonyms.

## What toolbox is FOR

It holds the **jigs** — `bolt.*.yaml` files, each a set of tasks — and the
**checkers** and **adapters** those tasks name. bolt runs them; anvil installs
the tools they require.

**It exists as a separate repository so that neither bolt nor anvil owns them.**
The three depend on each other in a line rather than a circle: bolt knows
nothing about any checker, this repository knows nothing about how the tools get
installed, and anvil derives its package lists from the `requires:` fields here
rather than maintaining a second copy beside them.

## The one rule that decides whether a jig is adoptable

> **A path resolves against `{configdir}` if it travels with the jig.** A
> checker, an adapter, a linter's config — these are **the rule**.
>
> **A path stays relative to the run root if it belongs to the project being
> checked.** Its source, its `REQUIREMENTS.md`, its `SUPPRESSIONS` — these are
> **the subject**.

A shared jig carries the rule and never the subject. One that bundles a document
*about a codebase* has stopped being adoptable, because it judges every adopter
against its author's answers.

**Getting this backwards is invisible in the repository that gets it wrong** — a
jig at its own root has `{configdir}` equal to the run root, so both spellings
resolve to the same file. `tests/test_jigs.py` exists to catch it: it fails any
jig reaching `bin/`, `adapters/`, `config/` or `schema/` without `{configdir}`.

FACT 2026-08-20, measured in `agent-support`: `{configdir}` resolves against
**the symlink's own directory, not its target**, which is why an adopter needs
its own `bin/` and `adapters/` links and cannot simply name a jig.

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
rather than symlinks, so `{configdir}` is the repository root natively.

    bolt -c bolt.common-quality.yaml -c bolt.python-std-quality.yaml -c bolt.secrets.yaml

**Read `run_result.yaml`, never bolt's exit status.** FACT 2026-08-20: that run
exited **0** while `run_result.yaml` said `success: false`.

FACT 2026-08-20 23:48, from that artifact — **10 pass, 4 fail**. All four are
open defects with a task each; none is accepted permanent state.

| Task | | Why | Tracked as |
|---|---|---|---|
| `traceability` | ✗ 1 | 12 settled requirements have no test | `own-gate/10` |
| `analyse` | ✗ 16 | pylint 9.79/10 — two missing docstrings in `lizard.py` | `own-gate/20` |
| `security` | ✗ 1 | bandit, 72 findings, **all Low**, 66 of them `assert` in a test | `own-gate/20` |
| `detect-secrets` | ✗ 2 | crashes where no baseline exists | `own-gate/30` |

FACT 2026-08-20: `complexity` genuinely measures this repository's own code — the
artifact lists functions from `adapters/common/` and `tests/`. **It does not do
that for the other five adopters**, which is `shared-checkers/30`.

Of the 12 uncovered requirements, three are testable and are `own-gate/10`. The
other nine are design properties held by review — *"a jig carries the rule and
never the subject"* is not an assertion. **They are settled, not open, so they
are not marked `[?]`.**

## Its adopters

FACT 2026-08-21, measured with `link-jigs.py --check`:

| Adopter | Sets | Links | `--check` |
|---|---|---|---|
| `qwark` | go, secrets | 10 | ✓ |
| `dotfiles` | go, secrets | 10 | ✓ — its Go lives under `go/` |
| `silo` | common, secrets | 5 | ✓ |
| `agent-support` | common, secrets | 5 | ✓ |
| `anvil` | common, secrets | 5 | ✓ |
| `bolt` | go, secrets | 6 | ✗ |

**`bolt` is the one that has not taken.** It still carries its own pre-split
copies at `tools/` and `adapters/`, so `link-jigs` refused four paths rather than
overwriting them. Measured against the same tree, bolt's fork exits 0 where this
repository's checker exits 1. Filed at
`clank/inbox/bolt/gate-runs-a-stale-fork-of-the-checkers/`; only bolt's own
session resolves it.

**Adoption records nothing about itself.** `--check` needs the set list as an
argument, and which sets a project adopted is written nowhere — so a wrong guess
reports drift that does not exist. That happened during this commissioning
against `dotfiles`. It is `adoption/10`, and it is a precondition for `--check`
ever becoming a gate task.

## Where the work lives

**`~/.projects/clank/tasks/toolbox/`** — five groups, seventeen tasks. The
listing is the index; `NEXT_STEPS.md` holds only what has no task.

**`~/.projects/clank/inbox/toolbox/`** — eleven findings filed by other sessions,
every one of them now tracked by a task. An inbox entry is an observation;
**only this project's session resolves one.**

## Documents

- `README.md` — for a human arriving cold.
- `REQUIREMENTS.md` — 48 requirements, **deliberately still one file**.
- `NEXT_STEPS.md` — open decisions and the bolt handoff; not the queue.
- `docs/PATTERNS/testing-checkers-and-adapters.md` — how the two contracts are
  tested, and why they differ.
- `docs/DECISIONS/`, `docs/LESSONS/` — one file each.
- `silo/docs/GLOSSARY.md` — the vocabulary, shared with bolt and anvil.

**`REQUIREMENTS.md` and `SUPPRESSIONS` stay single files, and the reason is
mechanical.** FACT 2026-08-20: `test-traceability.py --requirements <DIR>` dies
with an unhandled `IsADirectoryError` — the guard is `.exists()`, which a
directory satisfies. This repository is gated on that checker, so splitting its
own requirements would turn a passing check into a crashing one. The split is
pending on `shared-checkers/10`.

**There is no `SUPPRESSIONS` file and no `docs/SUPPRESSIONS/`.** Nothing here is
silenced — see `docs/DECISIONS/no-suppressions-file-while-nothing-is-silenced.md`.
The same holds for `docs/MOCKS/`.

**There is no project `CLAUDE.md`, and that is correct.** Everything a session
must obey here arrives from the global one.

## How it fits with the others

    bolt      runs jigs. Knows nothing about any checker.
    toolbox   holds the jigs, and the checkers and adapters they name.
    anvil     builds images carrying the tools a jig `requires:`.

`requires:` declares **executables**, not libraries. FACT 2026-08-20: nothing
here declares that the adapters need PyYAML — it works by ambient availability,
which is why `types-PyYAML` was unavailable and `pyproject.toml` carries a mypy
override instead of the stub package. If anvil is ever to install from a
declaration rather than a guess, that gap is what it will hit.
