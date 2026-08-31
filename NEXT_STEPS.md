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
is the mechanism, and `silo/docs/ARCHITECTURE.md` already expects per-language
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

**Per-file coverage for Python.** The Go jig judges coverage per file at 80% of
statements and refuses an aggregate, because an aggregate lets a well-tested
file carry an untested one. The Python `tests` task already produces
`coverage.xml`, so the data is there. What is missing is an adapter that reads
Cobertura XML and applies the threshold per file. Until it exists, coverage is
measured for Python and not enforced.

**Three adapters still speak a retired contract.** `adapters/go/gofmt.py`,
`adapters/go/govet.py` and `adapters/common/lizard.py` each read a record and
write an envelope, and none is wired to a task, so none can currently fail.
Wiring one before porting it produces an invalid envelope. Porting them buys
back per-finding reasons and, for `lizard`, the complexity statistics that
currently sit unread in captured stdout. It does not change any verdict.

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
