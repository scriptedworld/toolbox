# An exclusion flag can replace the defaults it should have joined

The sibling lesson, `a-tool-can-accept-an-exclusion-and-exclude-nothing.md`,
covers a flag that is accepted and does nothing. This is the other direction,
and it is worse, because the flag does exactly what it says while silently
undoing something else.

**ruff's `--exclude` REPLACES its built-in default exclude list. That list
already held `.venv`, `venv`, `build`, `dist` and the tool caches.**

So `format` and `lint` were scoped with three directories and, in the same
gesture, told to start reading every virtualenv in every adopter. The flag was
added to narrow the run and it widened it.

Measured 2026-08-28 against a violation planted in a fake `.venv`, counting
findings in the virtualenv and in the project's own file:

    ruff check, no flag                        venv 0   own 2
    ruff check --exclude <three dirs>          venv 2   own 2
    ruff check --extend-exclude <three dirs>   venv 0   own 2

`ruff format` behaves identically. `--extend-exclude` adds to the defaults and
is the correct spelling whenever a tool has defaults worth keeping.

## Why it survived a year of the other lesson's method

The planted-violation method that caught the four wrong spellings **could not
catch this one**, and the reason is worth keeping.

That method plants a violation in the directory being excluded and checks the
finding count goes to zero. It answers *did the flag exclude what it named*.
This flag did. Every one of those tests passed.

The question it does not ask is *what else changed*, and nothing about a
passing exclusion test suggests there is a second question. **A regression
introduced by a correct-looking flag is invisible to a test aimed at the
flag.**

What found it was widening the fixture rather than sharpening the assertion:
planting a violation in a `.venv` as well, because an adopter has one and
toolbox does not.

## The measurement that nearly went wrong

The first sweep reported four tools clean, with `venv:0` for each. Three of
those four were wrong, and they were wrong because the fixture planted nothing
those tools detect, so they found nothing anywhere and reported zero.

**A zero in the excluded column beside a zero in the control column is an
unmeasured row wearing a pass**, which is precisely the failure this whole
family of lessons is about, occurring inside the script written to detect it.
The fixture now carries a violation for every tool at once and the control
column is checked first.

## What to do

**Read what a tool excludes by default before adding an exclusion to it**, and
prefer the additive spelling wherever one exists:

    ruff         --extend-exclude       --exclude replaces the defaults
    pylint       --ignore               takes basenames; --ignore-paths misses
                                        a dot directory entirely
    vulture      --exclude              no defaults to lose
    bandit       -x                     no defaults to lose
    interrogate  -e, once per path      already names .venv itself

**Then plant a violation in a directory you did not name**, not only in one you
did. The named directory tests the flag. The unnamed one tests the flag's
side effects, and that is where this lived.
