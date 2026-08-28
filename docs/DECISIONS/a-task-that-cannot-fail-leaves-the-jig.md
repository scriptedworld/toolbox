# A task that cannot fail leaves the jig

Decided 2026-08-27, during the port to the format the rebuilt bolt reads.

## What was decided

`coverage` is **not** in `bolt.go-std-quality.yaml`. It was, and it comes back
when `adapters/go/coverage.py` speaks the current contract, which is
`clank/tasks/toolbox/port-the-jigs/10`.

Its rules are unchanged and are recorded there so they are not re-litigated:
judged per file at 80% of statements, no aggregate threshold, generated code
excluded.

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

## What it costs, stated so it is not discovered

Four Go adopters have no coverage gate until `port-the-jigs/10` lands. That is a
real regression from the retired bolt, which ran the adapter. It is written into
the jig, into `START_HERE.md` and here.

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
