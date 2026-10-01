# An exclusion flag can replace the defaults it should have joined

The sibling lesson, `a-tool-can-accept-an-exclusion-and-exclude-nothing.md`,
covers a flag that is accepted and does nothing. This covers a flag that does
what it says and silently undoes something else.

**ruff's `--exclude` replaces its built-in default exclude list. That list
already holds `.venv`, `venv`, `build`, `dist` and the tool caches.**

So scoping `format` and `lint` with `--exclude` and three directories also sets
them reading every virtualenv in every adopter. A flag meant to narrow the run
widens it.

Measured against a violation planted in a fake `.venv`, counting
findings in the virtualenv and in the project's own file:

    ruff check, no flag                        venv 0   own 2
    ruff check --exclude <three dirs>          venv 2   own 2
    ruff check --extend-exclude <three dirs>   venv 0   own 2

`ruff format` behaves identically. `--extend-exclude` adds to the defaults and
is the correct spelling whenever a tool has defaults to keep.

## Why the other lesson's method misses it

That method plants a violation in the directory being excluded and checks the
finding count goes to zero. It answers *did the flag exclude what it named*, and
for this flag the answer is yes.

It does not ask *what else changed*. A regression introduced by a
correct-looking flag is invisible to a test aimed at the flag. Planting a
violation in a `.venv` as well, because an adopter has one and toolbox does not,
is what shows it.

## A zero beside a zero measures nothing

A sweep can report a tool clean with `venv:0` because the fixture planted
nothing that tool detects, so it finds nothing anywhere. A zero in the excluded
column beside a zero in the control column is an unmeasured row. The fixture
carries a violation for every tool at once, and the control column is checked
first.

## What to do

**Read what a tool excludes by default before adding an exclusion to it**, and
prefer the additive spelling wherever one exists:

    ruff         --extend-exclude       --exclude replaces the defaults
    pylint       --ignore               takes basenames; --ignore-paths misses
                                        a dot directory entirely
    vulture      --exclude              no defaults to lose
    bandit       -x                     no defaults to lose
    interrogate  -e, once per path      already names .venv itself

**Then plant a violation in a directory you did not name** as well as in one you
did. The named directory tests the flag, and the unnamed one tests its side
effects.
