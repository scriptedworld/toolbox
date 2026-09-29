# toolbox, the project

*Checker* and *adapter* mean specific and opposite things here, and most of what
follows is meaningless if the two are read as synonyms. A checker is what a task
runs and its exit code is the verdict; an adapter reads the execution record
afterwards and returns the envelope that becomes the verdict. `README.md` has
the worked distinction.

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

The path rule, stated in `README.md`: a jig carries whatever does the checking
and never anything about the project being checked. Two things about enforcing
it belong here, not there.

`tests/test_jigs.py` is what catches a breach, because the mistake is invisible
in the repository that makes it. It fails any jig reaching `bin/`, `adapters/`
or `config/` without `{config_dir}`, and any jig that prefixes an `adapter:`
with `{config_dir}`, which would resolve twice.

`{config_dir}` resolves against the symlink's own directory and not its
target. That was measured, not assumed, and it is why an adopter needs
its own `bin/` and `adapters/` links instead of simply naming a jig that lives
elsewhere.

## Layout

    bolt.common-quality.yaml     language-agnostic: traceability, suppressions, secrets,
                                 wording
    bolt.go-std-quality.yaml     Go: format, tidy, build, vet, lint, tests with
                                 per-file coverage, vuln. Statements, not
                                 branches: Go's toolchain has no branch mode.
    bolt.python-std-quality.yaml Python: format, lint, types, analyse, cognitive,
                                 complexity, dead-code, docstrings, security,
                                 security-tests, tests with per-file line and
                                 branch coverage
    bolt.rust-std-quality.yaml   Rust: format, lint, build, tests with per-file
                                 coverage, vuln, licences. Adopted from bolt on
                                 2026-09-03. Lines, not branches: cargo-llvm-cov
                                 needs nightly for those.
    bolt.secrets.yaml            gitleaks, detect-secrets
    jigs.yaml                    which files a project links to adopt a set

    bin/            checkers written here, because no tool does the job
      test-traceability.py     tests cite what they discharge; requirements have tests
      suppression-register.py  every pragma registered, every entry real
      link-toolbox.py          makes an adopter's symlinks, per jigs.yaml
      voice-tells.py           the wording the writing standard names, by pattern
      voice-review.py          a model's findings on the same text, run by hand,
                               never a gate
    adapters/       record -> envelope, per task that needs one
      common/bolt-result.py    a child bolt run's verdict becomes this task's
      go/{gofmt,govet,coverage}.py
      python/coverage.py       Cobertura: lines and branches, per file
      rust/coverage.py         lcov: lines per file, and branches where a
                               toolchain emits them
      */__init__.py            not packages in use; they are what lets coverage
                               see an adapter no test executed
    config/         tool configuration that travels with a jig
    tests/          one file per script under test; see
                    docs/PATTERNS/testing-checkers-and-adapters.md

There is no `schema/`, and that is NFR-6 settled. wrench ships the jig and
definitions schemas and bolt is built from them, so a copy here could only be a
second description free to disagree with the one being enforced.
`tests/test_jigs.py` imports `wrench` and validates against the validator wrench
ships.

## The gate

This repository is its own adopter, and uniquely so: it holds the real files
instead of symlinks, so `{config_dir}` is the repository root natively.

    bolt --definitions toolbox common-quality .
    bolt --definitions toolbox python-std-quality .
    bolt secrets .

**`--definitions toolbox` is not optional here.** The name is toolbox's own; an
adopter overriding a placeholder passes its own file instead, and one taking the
defaults passes none. The shared jigs exclude `bin/` and `adapters/`, because in
every other adopter those hold symlinks to this repository's checkers and the
adopter's tools would grade toolbox's code as their own. This repository holds
the real files, so taking the default would stop it gating its own checkers,
which would silence a gate instead of scoping it. `bolt.toolbox.definitions.yaml`
carries the override and says so.

One jig and one directory per run. Flags come before the positionals, and the
jig is named bare, read as `bolt.<name>.yaml` from `--config-dir`. Running three
in one invocation was the overlay model, which the current CLI does not have.

**Read `result.yaml`, never bolt's exit status.** Bolt exits 0 when the run
completed, whatever the tools concluded, and the verdict is in the artifact. It
also exits 0 when it refuses the jig outright.

All three runs report `success: true` in `result.yaml`. Read that artifact, never
bolt's exit status.

The gate cannot be asserted from inside the suite, which is why NFR-5 stays
marked open: NFR-1 has the suite running with none of the tools the jigs name, so
running the three jigs is the only check there is.

`complexity` measures each adopter's own code, because the shared jigs exclude
the directories adoption fills. Before that an adopter was graded on the checkers
it had adopted instead of on its own source.

One gap remains in what `complexity` reads: it misses a script with no file
extension, which is how one adopter's only source file went unread.

Every settled requirement is cited by a test, 101 of 101 at `4997fb3`, and two
rows carry `[?]`: `FR-6.2` and `NFR-5`.

A COVERS mark is written `# COVERS FR-1.2 | kind`, with no colon; the colon
form fails (FR-4.26). A repository whose requirements are a directory runs
common-quality with `--definitions requirements-directory`, and the jig's
default flips to `docs/REQUIREMENTS` once no repository holds a single file.

Nine of those citations were written by holding the jig documents and the scripts
themselves to what the requirement says, which is how a property that reads like
a design statement turns out assertable. A jig carrying the rule and never the
subject becomes: no command names `REQUIREMENTS.md` or `SUPPRESSIONS` except
through a placeholder. An adapter reading only what it is handed becomes: no
adapter imports a clock, a socket or `subprocess`. The suite running without the
toolchain becomes: no test spawns anything but the interpreter and git.

Three requirements were retired on the way, because they described a toolbox that
had changed under them. `FR-1.1` and `FR-7.2` said jigs compose by overlay, and
bolt runs one jig with composition as a child task. `FR-3.3` said an adapter
touches no filesystem, and the four flag-contract adapters read their evidence
and write `output.yaml`. `FR-1.7`, `FR-7.15` and `FR-3.8` replace them, and
`REQUIREMENTS.md`'s `## Retired` section holds the pointers.

## Adoption

A project adopts a set by linking the files `jigs.yaml` names for it, which
`bin/link-toolbox.py` does. `--check` verifies an existing adoption and exits 1 on
drift.

Two things about adoption matter before relying on it.

**A vendored copy blocks a link, correctly.** `link-toolbox` never overwrites a real
file. A project that carried its own fork of a checker before adopting keeps that
fork, and the fork then runs instead of the shared one. That state looks adopted
and is not, and the way it shows is the two exiting differently against the same
tree.

**Adoption records nothing about itself.** `--check` needs the set list as an
argument, and which sets a project adopted is written nowhere, so a wrong guess
reports drift that does not exist. Fixing that is a precondition for `--check`
ever becoming a gate task.

## Documents

- `README.md`, for somebody arriving cold, and the adoption instructions.
- `CONTRIBUTING.md`, how to run the gate here and what a change has to satisfy.
- `SECURITY.md`, the trust boundary and how to report a vulnerability.
- `REQUIREMENTS.md`, 60 requirements, still one file and no longer forced to be.
- `NEXT_STEPS.md`, the open decisions, never the queue.
- `docs/PATTERNS/testing-checkers-and-adapters.md`, how the two contracts are
  tested and why they differ.
- `docs/DECISIONS/` and `docs/LESSONS/`, one file per decision and per lesson.

`REQUIREMENTS.md` and `SUPPRESSIONS` are still single files and are no longer
forced to be. They stayed single because `--requirements <DIR>` died with an
unhandled `IsADirectoryError`, the guard being `.exists()`, which a directory
satisfies. `shared-checkers/10` closed that at `cc65aad`: both checkers read a
directory or a file, and `.retired` names a retired requirement without needing
a `## Retired` heading.

Splitting a copy of this repository's own document, 59 rows into 59 files, gave
byte-identical output from both forms: `43 of 55 requirements covered; 4 open
and exempt`. So the split is available and is a separate change nobody has
made. `skid` and `agent-support` have made theirs.

There is no `SUPPRESSIONS` file and no `docs/SUPPRESSIONS/`, because nothing here
is silenced. See `docs/DECISIONS/no-suppressions-file-while-nothing-is-silenced.md`.
The same holds for `docs/MOCKS/`.

There is no project `CLAUDE.md`. Every rule that applies here comes from the
global one.

## How it fits with the others

    bolt      runs jigs. Knows nothing about any checker.
    toolbox   holds the jigs, and the checkers and adapters they name.
    anvil     builds images carrying the tools a jig `requires:`.

`requires:` declares **executables**, not libraries. Nothing here declares that
the adapters need PyYAML: it works by ambient availability, which is why
`types-PyYAML` was unavailable and `pyproject.toml` carries a mypy override in
place of the stub package. If anvil is ever to install from a declaration instead
of a guess, that gap is what it will hit.
