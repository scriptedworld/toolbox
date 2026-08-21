# An uncovered settled requirement fails the gate

**Decided** 2026-08-20 by the owner, in session. **Implemented** in `05f3a52`.

## What was decided

`traceability` fails when a requirement no test cites is **settled**. It reports,
without failing, when that requirement's row marks it `[?]`.

    | FR-1.1 | Any command-line tool can be run.  | [A] |   uncovered -> FAILURE
    | FR-5.9 | Schema versioning is unresolved.   | [?] |   uncovered -> context

`[A]`, `[D]`, `[A/D]` and **no marker column at all** are settled. A document
with no markers therefore claims no exemptions, which is the right way round:
**exemption is claimed, never granted by omission.**

## Why

Before this, an uncovered requirement was printed as context and the task exited
0. That made `REQUIREMENTS.md` a document nothing held the code to — the exact
failure the task exists to prevent, occurring inside the task itself.

The previous exemption was sized for open questions that cannot have a test yet,
and it covered *every* untested requirement whatever its status. Splitting it is
what turns a report into a gate.

## What it cost, measured on the day

FACT 2026-08-20, both real adopters, same tooling:

| Repo | Result |
|---|---|
| `bolt` | exit 1 — 28 settled requirements untested, 3 open and exempt |
| `qwark` | exit 0 — 16 untested, **all** marked `[?]` |

The difference is not luck. qwark had been marking open decisions honestly all
along, so the gate found nothing to complain about.

## What was rejected, and why

**A ratchet flag** (`--allow-uncovered N`, pinned to today's count and only ever
lowered) was offered and declined. It would have let bolt and qwark adopt the
gate immediately and burn the number down, at the cost of a knob that can be
left permanently loose.

**Report-only with `--strict` opt-in** was offered and declined for the same
reason: it is another report rather than the gate that was asked for.

## Revisit if

An adopter's honest state is genuinely unrepresentable — a requirement that is
settled, testable in principle, and that no test can reach for a reason nobody
can fix. Reaching for `[?]` to quiet the gate is the failure mode to watch: the
marker says *this decision is open*, not *this is inconvenient*, so a
requirement moved to `[?]` states the open question in its own text.
