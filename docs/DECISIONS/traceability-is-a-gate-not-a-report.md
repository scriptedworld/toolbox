# An uncovered settled requirement fails the gate

## What was decided

`traceability` fails when a requirement that no test cites is **settled**. It
reports without failing when that requirement's row marks it `[?]`.

    | FR-1.1 | Any command-line tool can be run.  | [A] |   uncovered -> FAILURE
    | FR-5.9 | Schema versioning is unresolved.   | [?] |   uncovered -> context

`[A]`, `[D]`, `[A/D]` and no marker column at all are settled. A document
with no markers therefore claims no exemptions, which is the right way round:
exemption is claimed, never granted by omission.

## Why

An uncovered requirement printed as context with the task exiting 0 leaves
`REQUIREMENTS.md` unenforced by the one task meant to enforce it. The exemption
exists for open questions that cannot have a test yet, so it covers only rows
marked `[?]`.

## What it cost

Both real adopters, same tooling:

| Repo | Result |
|---|---|
| `bolt` | exit 1: 28 settled requirements untested, 3 open and exempt |
| `qwark` | exit 0: 19 untested, all marked `[?]` |

## What was rejected, and why

A ratchet flag (`--allow-uncovered N`, pinned to the current count and only ever
lowered) is declined. It would let an adopter take the gate at once and burn the
number down, at the cost of a knob that can be left permanently loose.

Report-only with a `--strict` opt-in is declined for the same reason: it is
another report, and the requirement is a gate.

## Revisit if

An adopter's honest state turns out to be genuinely unrepresentable: a
requirement that is settled, testable in principle, and that no test can reach
for a reason nobody can fix.

`[?]` marks an open decision. A requirement moved to `[?]` states the open
question in its own text, so a marker used to quiet the gate shows as a row with
no question in it.
