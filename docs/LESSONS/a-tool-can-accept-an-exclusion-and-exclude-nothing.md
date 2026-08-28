# A tool can accept an exclusion flag and exclude nothing

Six tools in `bolt.python-std-quality.yaml` spell exclusion six ways. Three of
them accept the obvious spelling, exit 0, and exclude nothing at all.

Measured 2026-08-27 against a planted violation, a deliberately bad `.py` in a
directory that was supposed to be skipped. The number is findings in that file,
before the flag and after it:

    ruff        --exclude .ephemera,bin,adapters          8 -> 0
    bandit      -x ./.ephemera,./bin,./adapters           3 -> 0
    mypy        --exclude '(^|/)(\.ephemera|bin|adapters)/'  6 -> 0
    pylint      --ignore .ephemera,bin,adapters          24 -> 0

    vulture     --exclude ./.ephemera,./bin,./adapters    3 -> 3   the ./ breaks it
    interrogate -e '.ephemera,bin,adapters'          25% -> 25%   wants one -e each
    complexipy  --exclude .ephemera,bin,adapters          2 -> 2   wants globs
    pylint      --ignore-paths '(^|/)(\.ephemera|...)/'  24 -> 6   misses a dot dir

Every wrong form was accepted without complaint. `interrogate` reported 90.9%
docstring coverage with the comma form and 97.9% with repeated `-e`, which is
the difference between grading this repository's code and grading the adopter's.

## What it cost

Nothing, because the planted violation caught all four before they shipped. The
cost was the habit that produced it: an exclusion had already been added to the
`complexity` task months earlier in a form nobody tested, and `complexity`
passed in `agent-support` having read 23 functions of toolbox's code and none of
the adopter's.

## What to do

**Plant a violation in the directory you are excluding, and count findings with
the flag and without.** An exclusion that changes no number is not excluding.

    ruff check .            8 findings
    ruff check --exclude X  0 findings     the flag works

Exit status will not tell you. Every one of these tools exits 0 when it finds
nothing to report, which is also what it does when it has been pointed at
nothing.

The forms that work are in the jigs with a comment each. Re-measure rather than
copy one to a new tool: `pylint` alone needs `--ignore` and not
`--ignore-paths`, because the latter misses a directory whose name begins with a
dot, and the two flags read as synonyms.

## The general shape

This is the false-green family. A check that runs, reports nothing and exits 0
is indistinguishable from a check that was never pointed at anything, and the
green row reads as a checked property either way.

`clank/inbox/silo/a-claim-outliving-its-own-check/` carries the wider version:
the thing that would falsify a claim living on a shorter timescale than the
claim.
