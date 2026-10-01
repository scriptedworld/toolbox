# A jig nobody ran against a real project of that language is a jig nobody tested

## What it cost

Two defects in `bolt.python-std-quality.yaml` failed every adopter, and both
showed on the first run of the jig against a Python project with tests.

**`cognitive` never ran at all.** The task was `complexipy --max-complexity 15 .`
and that flag does not exist: complexipy 7.0.1 takes `--max-complexity-allowed`,
and exits on a usage error instead of a verdict. Every adopter saw a failure that
looked like their own code.

    $ complexipy --max-complexity 15 .
    No such option: --max-complexity (Possible options: --ignore-complexity,
    --install-completion, --max-complexity-allowed)

`security` fails any project that has tests. `bandit -r -q .` exits non-zero
on any finding at any severity. Over this repository's first test suite it
reported 72 findings: all Low, zero Medium, zero High, and 66 of them
`B101 assert_used`, which is what a test is made of. Every assertion added is
another finding, so the count grows with how well tested the code is, which is
not what the task measures.

## Why it went unnoticed

The Go jig was run against `bolt` and `qwark`, two real Go projects. The Python
jig was run only against a repository with no Python tests in it.

A jig is a claim about how a language is checked, and the claim is only tested by
pointing it at a project written in that language, shaped the way a real project
is shaped, tests included. Tests are where `assert` lives and where `B101` bites.

## What to do with it

**A new language jig is not finished until it has been run against a real project
in that language and its `result.yaml` read.** Not a fixture, and not this
repository's own checkers reached through symlinks: a project of that language
with tests in it.

This holds for a task as much as for a jig. In `agent-support` the `complexity`
task passed having read 23 functions, every one of them toolbox's own code
reached through the adoption symlinks, and not one line of the project's own.
Its `install.sh` is shell, which lizard does not parse.

So when a task passes, confirm what it read. A green task that measured nothing
reports a guarantee it never established.
