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
it belong here rather than there.

`tests/test_jigs.py` is what catches a breach, because the mistake is invisible
in the repository that makes it. It fails any jig reaching `bin/`, `adapters/`
or `config/` without `{config_dir}`, and any jig that prefixes an `adapter:`
with `{config_dir}`, which would resolve twice.

`{config_dir}` resolves against **the symlink's own directory and not its
target**. That is measured rather than assumed, and it is why an adopter needs
its own `bin/` and `adapters/` links instead of simply naming a jig that lives
elsewhere.

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
    tests/          one file per script under test; see
                    docs/PATTERNS/testing-checkers-and-adapters.md

**There is no `schema/`, and that is NFR-6 settled.** wrench ships the jig and
definitions schemas and bolt is built from them, so a copy here could only be a
second description free to disagree with the one being enforced. It disagreed
twice, on `allow-empty` arriving and again on its rename to `optional`, and both
times a test caught the copy rather than anything failing. `tests/test_jigs.py`
imports `wrench` and validates against the validator wrench ships. Deleted
2026-08-29.

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

Across the three runs, **13 of 16 tasks pass**. The three that fail are open
defects rather than unknowns.

| Task | Jig | Why |
|---|---|---|
| `traceability` | common | 11 settled requirements have no test citing them |
| `analyse` | python | pylint 9.99/10, `duplicate-code` between the two checkers and between the two new-contract adapters |
| `security-tests` | python | bandit, 11 findings, all Low and all high confidence, subprocess calls in the test tree |

`security` and `detect-secrets` both pass, and the secrets jig passes whole.

`complexity` measures each adopter's own code, because the shared jigs exclude
the directories adoption fills. Before that an adopter was graded on the checkers
it had adopted rather than on its own source.

One gap remains in what `complexity` reads: it misses a script with no file
extension, which is how one adopter's only source file went unread.

The 11 uncovered requirements are `FR-1.1`, `FR-1.3`, `FR-2.1`, `FR-2.2`,
`FR-3.3`, `FR-6.1`, `FR-7.3`, `FR-7.14`, `NFR-1`, `NFR-2` and `NFR-4`. A few are
straightforwardly testable. The rest are design properties held by review, and
*"a jig carries the rule and never the subject"* is not an assertion a test can
make. All of them are settled rather than open, so they carry no `[?]` and the
gate is right to fail on them.

## Adoption

A project adopts a set by linking the files `jigs.yaml` names for it, which
`bin/link-jigs.py` does. `--check` verifies an existing adoption and exits 1 on
drift.

Two things about adoption are worth knowing before relying on it.

**A vendored copy blocks a link, correctly.** `link-jigs` never overwrites a real
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
