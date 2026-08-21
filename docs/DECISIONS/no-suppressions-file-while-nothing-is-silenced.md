# This repository carries no SUPPRESSIONS file

**Decided** 2026-08-20, in session, and reaffirmed at commissioning 2026-08-21.

## What was decided

There is no `SUPPRESSIONS` file and no `docs/SUPPRESSIONS/` directory here, and
that is the honest state rather than a gap.

FACT 2026-08-21, re-measured at commissioning:

    $ python3 bin/suppression-register.py --register SUPPRESSIONS .
    no suppression pragmas anywhere, and none registered
    exit: 0

    $ grep -rnE 'type: ignore|noqa|nosec|pylint: disable' bin/ adapters/ tests/
    (no matches)

## Why

An empty register asserts that something is silenced when nothing is. The
standard treats `SUPPRESSIONS` and `MOCKS` as **claimed, never granted by
omission** — a project with nothing silenced says so by having neither
directory, and an empty one reads to the next session as a lost file.

The checker agrees: it passes a project with no pragmas and no register, and
fails a project with pragmas and no register. Those are different states and it
tells them apart.

## The near miss that made this concrete

While writing the sort key for `test-traceability.py`, a
`# type: ignore[union-attr]` was added to satisfy mypy. It typechecked. It would
also have been **the first pragma in this repository**, requiring a
`SUPPRESSIONS` file, an owner's answer to the question *why is this needed*, and
a registered entry — all for a regex match that cannot fail.

Slicing the digit prefix by hand removed the need for the pragma entirely:

    split = len(part) - len(part.lstrip(DIGITS))
    segments.append((int(part[:split] or 0), part[split:]))

**The rule is fix it or ask, never silence it.** Here the fix was three lines
and no question was needed.

## Revisit if

A pragma is genuinely required. That is the owner's answer to give, before it is
written — at which point this file is replaced by the register, and this
decision becomes the record of how long the repository went without one.
