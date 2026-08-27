# This repository carries no SUPPRESSIONS file

## What was decided

There is no `SUPPRESSIONS` file and no `docs/SUPPRESSIONS/` directory here. That
is the honest state and not a gap.

Measured:

    $ python3 bin/suppression-register.py --register SUPPRESSIONS .
    no suppression pragmas anywhere, and none registered
    exit: 0

    $ grep -rnE 'type: ignore|noqa|nosec|pylint: disable' bin/ adapters/ tests/
    (no matches)

## Why

An empty register asserts that something is silenced when nothing is. The
standard treats `SUPPRESSIONS` and `MOCKS` as **claimed, never granted by
omission**: a project with nothing silenced says so by having neither directory,
while an empty one reads to the next session as a file somebody lost.

The checker agrees. It passes a project with no pragmas and no register, and it
fails a project with pragmas and no register. Those are different states, and it
tells them apart.

## The near miss that made this concrete

While the sort key for `test-traceability.py` was being written, a
`# type: ignore[union-attr]` went in to satisfy mypy. It typechecked. It would
also have been **the first pragma in this repository**, requiring a
`SUPPRESSIONS` file, an answer to the question *why is this needed*,
and a registered entry, all for a regex match that cannot fail.

Slicing the digit prefix by hand removed the need for a pragma at all:

    split = len(part) - len(part.lstrip(DIGITS))
    segments.append((int(part[:split] or 0), part[split:]))

**The rule is fix it or ask, never silence it.** Here the fix was three lines,
and no question was needed.

## Revisit if

A pragma is genuinely required. That is my answer to give, before anything is
written, and at that point the register replaces this file.
