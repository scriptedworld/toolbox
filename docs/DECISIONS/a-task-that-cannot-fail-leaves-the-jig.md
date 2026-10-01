# A task that cannot fail leaves the jig

A task whose command cannot fail is left out of a jig until an adapter can judge
it. The Go jig's coverage is the worked case, and the same question is open for
the two Go adapters still on the old contract.

## The worked case

Go coverage is judged by `adapters/go/coverage.py`, per file at 80% of
statements, with no aggregate threshold.

It is attached to the `tests` task and not a task of its own, because a task's
work directory is its own and the profile is written into `tests`'s. A separate
task has no path to it that does not hardcode a sibling's directory. So the
adapter answers for both, reading the captured exit status so a suite that
failed while leaving a profile behind is reported as a failure.

## Why a task without an adapter leaves

A task with no adapter is judged by its command's own exit status. Two commands
do not have a meaningful one:

    gofmt -l .            lists unformatted files and exits 0 either way
    test -f coverage.out  exits 0 whenever the file exists

`format` runs `test -z "$(gofmt -l .)"`, which gates correctly and loses only
the file list from the envelope. Coverage has no such shell line: the work is
reading a profile per file and comparing against a threshold.

A coverage task without its adapter would pass every Go adopter without reading
a single percentage. A missing check tells a reader the gate does not cover
coverage. A green one tells them it does, and reports a guarantee it never
established.

Leaving a task out costs its adopters that check until the adapter lands, and
the jig says so where the task would be.

## Where the same question is open

`adapters/go/gofmt.py` and `adapters/go/govet.py` still read an execution record
on stdin, write their envelope to stdout, and emit no `kind`. **Neither is wired
to a jig**, so neither can fail; wiring one before porting it produces
`adapter-wrote-invalid`.

`format` gates on `test -z "$(gofmt -l .)"` and needs no adapter to be correct,
so porting `gofmt.py` buys back the per-file reasons and not the verdict.
`vet` is the same shape. That is `port-the-jigs/10`.

## A task that fails loudly stays

`detect-secrets` keeps its task under this rule. With no baseline the command
exits 2, and with one `scan --baseline` absorbs new findings and exits 0. No
adopter has a baseline, so every adopter runs the half that can fail, and the
jig's comment at the task records the other half.

## Revisit if

`port-the-jigs/10` lands. Wiring `gofmt.py` and `govet.py` is part of porting
them and not a separate edit.
