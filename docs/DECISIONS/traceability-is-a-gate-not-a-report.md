# An uncovered settled requirement fails the gate

Decided in session. Implemented in `05f3a52`.

## What was decided

`traceability` fails when a requirement that no test cites is **settled**. It
reports without failing when that requirement's row marks it `[?]`.

    | FR-1.1 | Any command-line tool can be run.  | [A] |   uncovered -> FAILURE
    | FR-5.9 | Schema versioning is unresolved.   | [?] |   uncovered -> context

`[A]`, `[D]`, `[A/D]` and **no marker column at all** are settled. A document
with no markers therefore claims no exemptions, which is the right way round:
exemption is claimed, never granted by omission.

## Why

Before this, an uncovered requirement was printed as context and the task exited
0, which left `REQUIREMENTS.md` unenforced by the one task meant to enforce it.

The old exemption had been sized for open questions that cannot have a test yet,
and it covered *every* untested requirement whatever its status. Splitting it is
what turns a report into a gate.

## What it cost, measured on the day

Both real adopters, same tooling:

| Repo | Result |
|---|---|
| `bolt` | exit 1: 28 settled requirements untested, 3 open and exempt |
| `qwark` | exit 0: 19 untested, **all** marked `[?]` |

The difference is not luck. qwark had been marking its open decisions honestly
all along, so the gate found nothing to complain about.

## What was rejected, and why

A ratchet flag (`--allow-uncovered N`, pinned to the current count and only ever
lowered) was offered and declined. It would have let bolt and qwark adopt the
gate at once and burn the number down, at the cost of a knob that can be left
permanently loose.

Report-only with a `--strict` opt-in was offered and declined for the same
reason: it is another report, and a gate is what was asked for.

## Revisit if

An adopter's honest state turns out to be genuinely unrepresentable: a
requirement that is settled, testable in principle, and that no test can reach
for a reason nobody can fix.

Reaching for `[?]` to quiet the gate is the failure mode to watch, because the
marker says *this decision is open* and not *this is inconvenient*. A requirement
moved to `[?]` states the open question in its own text.
