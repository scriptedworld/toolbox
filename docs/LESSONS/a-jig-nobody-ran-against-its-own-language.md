# A jig nobody ran against a real project of that language is a jig nobody tested

Learned by running this repository's own gate against this repository for the
first time.

## What it cost

Two defects had been shipping in `bolt.python-std-quality.yaml` since it was
first drafted, and both failed for **every adopter**.

**`cognitive` never ran at all.** The task was `complexipy --max-complexity 15 .`
and that flag does not exist: complexipy 7.0.1 takes `--max-complexity-allowed`,
and exits on a usage error instead of a verdict. Every adopter saw a failure that
looked like their own code.

    $ complexipy --max-complexity 15 .
    No such option: --max-complexity (Possible options: --ignore-complexity,
    --install-completion, --max-complexity-allowed)

Fixed in `d243a18`.

**`security` fails any project that has tests.** `bandit -r -q .` exits non-zero
on any finding at any severity. This repository produced 72 findings the moment
it grew a test suite: **all Low, zero Medium, zero High**, and 66 of them
`B101 assert_used`, which is what a test is made of.

The count only goes one way: the same command now reports 117 and 108, because
every assertion written since is another finding. A gate whose failure count is a
function of how well tested the code is was never measuring what it claimed to.

## Why it went unnoticed

The Go jig had been run against `bolt` and `qwark`, two real Go projects, so its
faults surfaced. The Python jig had only ever been run against a repository with
**no Python tests in it**. It looked exercised and was not.

A jig is a claim about how a language is checked, and the claim is only tested by
pointing it at a project written in that language, shaped the way a real project
is shaped, tests included. Tests are where `assert` lives and where `B101` bites.

## What to do with it

**A new language jig is not finished until it has been run against a real project
in that language and its `run_result.yaml` read.** Not a fixture, and not this
repository's own checkers reached through symlinks: a project of that language
with tests in it.

This generalises past jigs. Measured in `agent-support`, the `complexity` task
passed there having read 23 functions, **every one of them toolbox's own code
reached through the adoption symlinks**, and not one line of the project's own.
Its `install.sh` is shell, which lizard does not parse.

So when a task passes, confirm **what it read**. A green task that measured
nothing is worse than a red one, because it reports safety it never established.
