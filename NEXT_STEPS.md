# toolbox, next steps

What is undecided, and what is decided but not built. The work queue is tracked
outside this repository; this file holds the questions rather than the tasks.

## Decisions that are open

**How a common jig and a language jig compose.** Today they are separate jigs
and a project wanting both runs both. Composition used to be an overlay where
later files won and tasks merged by id, which let a language jig adjust a common
task without restating it. The current runner has no overlay, and nesting does
not replace it, because a nested jig has no id to override. So a language either
accepts the common thresholds or declares a second task that disagrees with
them, and neither is right.

**Whether a maintainability index belongs in the standard at all, or is declared
Python-only.** Only Python has a maintained tool for it. Go, Rust and TypeScript
have none, and the one multi-language candidate has been unmaintained for years.
The argument for declaring it rather than omitting it: a language that cannot
meet part of the standard should say so, because silence reads as compliance.

**Whether path-invoked scripts may share a module.** `pylint` reports
`duplicate-code` between the two checkers and between the two adapters written
against the current contract, and both are real. They follow from scripts being
invoked by path and therefore sharing no importable module. Fixing it means
deciding that these scripts may import from a common place, which changes how
adoption has to link them.

**Whether a jig can be named rather than pathed.** Resolving a short name
against an environment variable would replace repeating full paths. Ordering has
to stay explicit, because a directory glob has no order and order is semantics
here. It needs a change to the runner, so it is not a change this repository can
make alone.

**Task ordering, for `entrypoint`.** The runner has no ordering between tasks by
design, and giving `entrypoint` a home may need one. Also not this repository's
change to make.

**Whether an adopter's own tool configuration should be live.** `bandit` does not
read a project's `[tool.bandit]` without an explicit `-c`. Passing the flag
makes an adopter's configuration count, which also lets an adopter weaken a
security scan. Deliberately not acted on, because it is one instance of a wider
question about shared tool settings and deciding it alone would likely be undone.

## Decided and not built

**Toolbox is where shared project files live, and the `base` set is the first
of them.** `just/base.just` is here because five repositories held
byte-identical copies with no source and nothing detecting drift; they went out
of step within hours of one being edited.

The direction is a project template covering the three languages against
library, CLI and MCP shapes, with the gate, the recipes and the standard
documents present from the first commit rather than adopted afterwards. Copier
is the mechanism, and the estate architecture already expects per-language
templates to be where `just` recipe contents live. Earlier `python-` and
`rust-` template repositories existed and are gone.

Two things the `base` set does not solve yet, and a template would have to:

- **A file lands at the same relative path in the target**, so wrench cannot
  take this set: it keeps a copy per pack, at `rust/just/base.just` and
  `python/just/base.just`. Either adoption is per pack, or a set has to be able
  to place one source at a different path.
- **Adoption is recorded nowhere**, so `--check` cannot run as a gate task
  without being told which sets a project took. That is the precondition below.

### `just link-project <absolute path>`, and a subproject is a project

The design, and the reason `link-jigs` was renamed rather than only moved:
**adoption should be a recipe rather than a remembered command line**, and a
subdirectory that is its own project should hold its own link to toolbox.

    just link-project /abs/path/to/repo/rust
    just link-project /abs/path/to/repo/python
    just link-project /abs/path/to/repo/go

Each subdirectory then carries its own jigs, checkers and adapters, and is a
contained project rather than a directory the root happens to check. The root
Justfile delegates and nothing more:

    checks:  cd rust && just checks
             cd python && just checks
             cd go && just checks
             then the checks that are genuinely wider

**What stays at the root is what no subproject can answer**: that all three
suites cover the same thing, and that the project-level requirements are
discharged by the three together, whether by all of them individually or by the
mixture. `wrench/bin/test-suite-parity.py` is the first of those and reads all
three at once.

This also dissolves the per-path problem above. A set landing at the same
relative path is correct once the target is the subproject rather than the
repository, and `base.just` then lands once per pack because each pack is where
it belongs.

**Per-file coverage for Python and Rust — landed 2026-09-04.** Both jigs now
judge their `tests` task's report per file at 80% of lines, and the Python one
also at 80% of branches. Two things were learned doing it and are worth keeping:

- **Rust cannot gate branches on a stable toolchain.** cargo-llvm-cov writes
  `BRF:0` and no `BRDA` records at all without its `--branch` flag, which is
  unstable and needs nightly. The plan had assumed the data was already in the
  file. The adapter reads branch records where they exist and reports
  `branch_measured: false` where they do not, so nothing passes on an empty
  denominator.
- **A spawned script is invisible to the parent's coverage.** Every checker and
  adapter tested only as a subprocess reported 0% with a full suite behind it.
  `tests/conftest.py`'s `script_argv` routes them through
  `coverage run --parallel-mode`, and the jig combines before reporting.

**The standalone scripts cannot import each other, so they duplicate.** Every
script in `bin/` and `adapters/` is spawned by path from a directory that is not
a package, so anything two of them must both do is written twice: the coverage
adapters' whole judgement, the checkers' `SKIP_DIRS`, the adapters' `emit`.
pylint's R0801 reports a different pair each time one is dissolved, and all nine
scripts now carry a registered mark (S-3) rather than three separate arguments.

Deciding it means deciding one thing: whether `adapters/common/` and `bin/` gain
shared modules, linked into every adopter through the `common` set and imported
by path. The cost is a module behind nine shipped scripts and a link every
adopter takes whether or not it runs the task needing it. The alternative that
must not be taken is raising `min-similarity-lines` until the findings stop.

**One of the three is already guarded properly** —
`test_both_checkers_skip_the_same_directories` fails if the two skip lists
diverge — and that is the standard the other two should reach whichever way the
extraction goes.

**Two adapters still speak a retired contract.** `adapters/go/gofmt.py` and
`adapters/go/govet.py` each read a record and write an envelope, and neither is
wired to a task, so neither can currently fail. Wiring one before porting it
produces an invalid envelope. Porting them buys back per-finding reasons. It
does not change any verdict. `adapters/common/lizard.py` was a third until it
was deleted on 2026-09-04 with the `complexity` task it read for.

**Adoption records nothing about itself.** `link-toolbox.py --check` needs the set
list as an argument, and which sets a project adopted is written nowhere, so a
wrong guess reports drift that does not exist. Fixing that is a precondition for
`--check` becoming a gate task.

**A jig per language beyond Go and Python.** Rust is the nearest, and it forces a
change to the traceability checker's `LANGUAGES` table in the same commit,
because a language with a jig and no entry there finds no tests, cites nothing,
and fails every requirement at once.

## What blocks publication

The gate is not green. `traceability` reports 11 settled requirements with no
test citing them, `analyse` reports the duplicate code above, and
`security-tests` reports 11 low-severity bandit findings in the test tree. Each
is a known defect rather than an unknown, and none is silenced.

Neither the runner nor the schema library this repository depends on is
published, so a clone cannot run a jig or the test suite. That ordering is not
this repository's to set.

## Splitting the requirements document

`REQUIREMENTS.md` is one file and no longer has to be. Both checkers read a
directory or a single file, and a retired requirement can be named without a
`## Retired` heading. Splitting a copy of this document into one file per
requirement produced byte-identical checker output, so the split is available
and is a separate change nobody has made.

---

# Across the estate, 2026-09-04

Written here rather than in a file at the root of the checkouts, because that
file belongs to a machine and this belongs to the project.

## The gate's invocation is part of its result, and nothing machine-readable says so

Three variants, all of them load-bearing, and getting one wrong produces a wrong
answer that looks like a real one:

    toolbox    bolt --definitions toolbox <jig> .
    skid       bolt --definitions skid <jig> .
    infobot    bolt --definitions go-std-quality go-std-quality .
    qwark      bolt --definitions go-std-quality go-std-quality .
    bolt       bolt <jig> .                        (no definitions file)
    wrench     bolt wrench-quality .               MUST NOT take --definitions

**Each failure mode is silent in a different way.** Without `--definitions skid`,
skid's `traceability` and `suppressions` fail on paths it does not use. Given
`--definitions wrench` at the root, wrench's `requirements` resolves to
`../docs/REQUIREMENTS`, which is outside the repository, and five tasks fail that
otherwise pass — the flag is for the child runs its jig composes, which run at a
pack's base where that path is right. And without
`--definitions go-std-quality`, infobot's and qwark's `entrypoint` resolves to
the jig's default of `true`, so the entry-point coverage step never runs and
`cmd/*/main.go` reports 0.0%.

That last one is the worst of the three, because a coverage figure of 0% for a
file nothing tests is exactly what a correct run would also report.

**A definitions file being named after the jig does not make it load.**
`bolt.go-std-quality.definitions.yaml` looks like it would be found by name and
is not. infobot's `just/lang.just` says so in capitals; nothing a machine reads
says it anywhere.

**This is the same gap as `--check` needing its set list.** Neither the sets a
project adopted nor the command its gate is run with is recorded anywhere a
program can read, so both are re-derived by whoever is looking, and both were got
wrong here on 2026-09-04. One small file per adopter answers both:

    sets: [rust]
    gate: bolt --definitions toolbox

`link-toolbox.py --check` could then take no set argument and become a task in
`common-quality`, which is what turns adoption drift into a gate failure rather
than something somebody notices.

## What each language jig is missing, ranked

Asked for on 2026-09-04. Present today:

| dimension | go-std | python-std | rust-std |
|---|---|---|---|
| format | gofmt | ruff format | cargo fmt |
| lint | golangci-lint, 42 analysers | ruff + pylint | clippy |
| types | (compiler) | mypy | (compiler) |
| build | go build | — | cargo build |
| lockfile / tidy | go mod tidy | — | — |
| tests + coverage | statements | lines **and branches** | lines |
| vulnerabilities | govulncheck | **none** | cargo-audit |
| licences | **none** | **none** | cargo-deny |
| dead code | golangci `unused` | vulture | clippy `dead_code` |
| docstrings | **none** | interrogate | **none** |
| SAST | golangci `gosec` | bandit | **none** |
| cognitive complexity | golangci `gocognit` | complexipy | clippy |
| duplicate code | golangci `dupl` | pylint R0801 | **none** |

1. **Python has no vulnerability check at all**, and is the only language that
   does not. The jig's own footer already carries why it was deferred: Python
   tools report every advisory touching an installed distribution, which is
   noisier than `govulncheck`'s reachability. `pip-audit` against `uv.lock` is
   the closest match. This is the largest real hole.
2. **Licences for Go and Python.** Rust gates them through cargo-deny and the
   other two do not, so the estate's licence position is one language's.
   `go-licenses` and `pip-licenses` exist; the policy in bolt's `deny.toml` is
   worth copying rather than reinventing.
3. **Lockfile freshness for Python and Rust.** `go mod tidy` is gated and nothing
   checks that `uv.lock` or `Cargo.lock` matches its manifest. `uv lock --check`
   and `cargo update --locked` are the direct equivalents and both are cheap.
4. **Docstrings for Go and Rust.** interrogate has no sibling, but the guarantee
   does: `#![warn(missing_docs)]`, which bolt already sets per-project and could
   be a jig-level lint, and revive's exported rule inside golangci.
5. **SAST for Rust: leave the row empty and say so.** `cargo-geiger` counts
   `unsafe` and answers a different question. An empty row with a reason is
   honest; a weak tool wearing the name is not.

Every addition lands with a threshold that can fail and an entry in `requires:`,
because that list is what anvil builds an image from.
