# A task that cannot fail leaves the jig

Decided 2026-08-27, during the port to the format the rebuilt bolt reads.

## The decision, and it has since been discharged

`coverage` was removed from `bolt.go-std-quality.yaml` rather than shipped with
its adapter unported. **It is back**, at `adapters/go/coverage.py` speaking the
current contract, and its rules are unchanged: judged per file at 80% of
statements, no aggregate threshold.

It returned attached to the `tests` task rather than as a task of its own,
because a task's work directory is its own and the profile is written into
`tests`'s. A separate task had no path to it that did not hardcode a sibling's
directory. So the adapter answers for both, reading the captured exit status so
a suite that failed while leaving a profile behind is a failure and not a pass
with a coverage number beside it.

The decision below is kept because the reasoning is what generalises, and three
adapters are still unported under exactly the same question.

## Why it left rather than shipping

The port moved every task from an adapter that reached the verdict to the
command's own exit status. Two commands do not have one:

    gofmt -l .            lists unformatted files and exits 0 either way
    test -f coverage.out  exits 0 whenever the file exists

`format` was rewritten to `test -z "$(gofmt -l .)"`, which gates correctly and
loses only the file list from the envelope. `coverage` has no such rewrite: the
work is reading a profile per file and comparing against a threshold, and no
shell line does it.

So the choice was a `coverage` task that passes for `dotfiles`,
`palette-print`, `qwark` and `toolbox` without reading a single percentage, or
no `coverage` task at all.

**An absent task is honest and a task that cannot fail is not.** A missing check
tells a reader the gate does not cover coverage. A green one tells them it does,
and reports a guarantee it never established. The second is worse in exactly the
way this repository exists to prevent, and it is worse in four repositories at
once.

## What it cost while it was out

Four Go adopters had no coverage gate. That was a real regression from the
retired bolt, which ran the adapter, and it was written into the jig, into
`START_HERE.md` and here rather than left to be discovered. It lasted one day.

## Where the same question is still open

`adapters/go/gofmt.py` and `adapters/go/govet.py` still read an execution record
on stdin, write their envelope to stdout, and emit no `kind`. Measured
2026-08-28. **Neither is wired to a jig**, so neither can fail; wiring one
before porting it produces `adapter-wrote-invalid`.

`adapters/common/lizard.py` was the third until 2026-09-04. It went with the
`complexity` task it read for, having been unwired the whole time: the task ran
on the exit-code adapter because this one spoke the retired contract, so every
adopter linked a file nothing invoked.

`format` gates on `test -z "$(gofmt -l .)"` and needs no adapter to be correct,
so porting `gofmt.py` buys back the per-file reasons rather than the verdict.
`vet` is the same shape. That is `port-the-jigs/10`.

## The same test applied elsewhere in the same change

`detect-secrets` **kept** its task under this rule rather than losing it. It
gates in neither of its states: with no baseline the command exits 2, and with
one `scan --baseline` absorbs new findings and exits 0. No adopter has a
baseline, so every adopter gets the loud half, and a task that fails honestly is
worth keeping where one that passes falsely is not. The jig says so at the task.

## Revisit if

A shell line is found that judges per-file coverage without an adapter, or
`port-the-jigs/10` lands. Restoring the task is part of porting the adapter and
not a separate edit.
