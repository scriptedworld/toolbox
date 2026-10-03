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
target, so an adopter needs its own `bin/` and `adapters/` links and cannot
simply name a jig that lives elsewhere.

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
                                 coverage, vuln, licences. Lines, not branches:
                                 cargo-llvm-cov needs nightly for those.
    bolt.shell-std-quality.yaml  shell: shfmt and shellcheck over files chosen by
                                 extension, startup-file name or shebang
    bolt.typescript-std-quality.yaml, bolt.node-std-quality.yaml,
    bolt.deno-std-quality.yaml, bolt.ruby-std-quality.yaml
                                 the other languages; the Ruby jig has never run
    bolt.secrets.yaml            gitleaks, detect-secrets
    bolt.toolbox.definitions.yaml               this repository's own overrides
    bolt.requirements-directory.definitions.yaml for an adopter whose
                                 requirements are a directory
    jigs.yaml                    which files a project links to adopt a set
    just/base.just               the shared recipes, linked by the base set

    bin/            checkers written here, because no tool does the job
      test-traceability.py     tests cite what they discharge; requirements have tests
      suppression-register.py  every pragma registered, every entry real
      link-toolbox.py          makes an adopter's symlinks, per jigs.yaml
      voice-tells.py           the wording the writing standard names, by pattern
      voice-review.py          a model's findings on the same text, run by hand,
                               never a gate
      flay-envelope            flay's report as an envelope, for the Ruby jig
      shell-files.py           the shell files among the tracked ones, for the
                               shell jig
    adapters/       record -> envelope, per task that needs one
      common/bolt-result.py    a child bolt run's verdict becomes this task's
      go/{gofmt,govet,coverage}.py
      python/coverage.py       Cobertura: lines and branches, per file
      lcov/coverage.py         lcov: lines per file, and branches where a
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
the real files, so taking the default would stop it gating its own checkers.
`bolt.toolbox.definitions.yaml` carries the override and says so.

One jig and one directory per run. Flags come before the positionals, and the
jig is named bare, read as `bolt.<name>.yaml` from `--config-dir`.

**Read `result.yaml`, never bolt's exit status.** Bolt exits 0 when the run
completed, whatever the tools concluded, and the verdict is in the artifact. It
also exits 0 when it refuses the jig outright.

The gate cannot be asserted from inside the suite, which is why NFR-5 stays
marked open: NFR-1 has the suite running with none of the tools the jigs name, so
running the three jigs is the only check there is.

`complexity` measures each adopter's own code, because the shared jigs exclude
the directories adoption fills. It does not read a script with no file
extension.

Every settled requirement is cited by a test, and two rows carry `[?]`:
`FR-6.2` and `NFR-5`. The `traceability` task prints the count.

A COVERS mark is written `# COVERS FR-1.2 | kind`, with no colon; the colon
form fails (FR-4.26). A repository whose requirements are a directory runs
common-quality with `--definitions requirements-directory`, and the jig's
default flips to `docs/REQUIREMENTS` once no repository holds a single file.

Some requirements that read as design statements are tested by holding the jig
documents and the scripts to them. No command names `REQUIREMENTS.md` or
`SUPPRESSIONS` except through a placeholder; no adapter imports a clock, a
socket or `subprocess`; no test spawns anything but the interpreter and git.

Retired requirements are listed with their replacements in `REQUIREMENTS.md`'s
`## Retired` section.

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
- `REQUIREMENTS.md`, what must be true, one row per requirement.
- `NEXT_STEPS.md`, the open decisions, never the queue.
- `docs/PATTERNS/testing-checkers-and-adapters.md`, how the two contracts are
  tested and why they differ.
- `docs/DECISIONS/` and `docs/LESSONS/`, one file per decision and per lesson.

`REQUIREMENTS.md` and `SUPPRESSIONS` are single files. Both checkers read either
a file or a directory, and in a directory `.retired` names a retired requirement
without a `## Retired` heading, so splitting either is open and changes no
verdict.

`SUPPRESSIONS` registers every pragma here, S-1 to S-4. There is no
`docs/MOCKS/`: tests hand fakes in through each script's own parameters, and
nothing is patched.

There is no project `CLAUDE.md`. Every rule that applies here comes from the
global one.

## How it fits with the others

    bolt      runs jigs. Knows nothing about any checker.
    toolbox   holds the jigs, and the checkers and adapters they name.
    anvil     builds images carrying the tools a jig `requires:`.

`requires:` declares **executables**, not libraries. Nothing here declares that
the adapters need PyYAML: it works by ambient availability, and
`pyproject.toml` carries a mypy override in place of the `types-PyYAML` stub
package. anvil cannot install the adapters' libraries from a declaration until
one exists.
