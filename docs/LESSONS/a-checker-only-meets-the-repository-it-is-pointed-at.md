# A checker is only exercised by the repository it happens to be pointed at

**Learned** 2026-08-20, from a crash that survived review and a full clean run.

## What it cost

`test-traceability.py` sorted requirement ids with a key that compared an `int`
segment against a `str` one:

    parts = tuple(int(p) if p.isdigit() else p for p in re.split(r"[.]", number))

`FR-4.13` keys as `(4, 13)`. `FR-4.13a` keys as `(4, '13a')`. Comparing them
raises:

    TypeError: '<' not supported between instances of 'str' and 'int'

**`bolt` has no lettered requirement id, so bolt could never have found it.** It
passed review, and it passed a full run against bolt. It surfaced on the first
run against `qwark`, which has eleven — `FR-4.9a`, `FR-4.13a`, `FR-10.3b` and
the rest.

The fix keys every segment as `(number, suffix)`, so both shapes compare:

    split = len(part) - len(part.lstrip(DIGITS))
    segments.append((int(part[:split] or 0), part[split:]))

## Why it matters more here than elsewhere

These checkers are **shared**. They are pointed at repositories their author has
never seen, by sessions that will read a traceback as *their* repository being
broken. A crash is at least loud; the worse case is the same class of bug
producing a wrong answer quietly, which is what
`suppression-register.py` scanning `rglob("*.go")` does for every non-Go
adopter.

One repository is one sample. Two repositories with different conventions is a
test.

## What to do with it

**Tests, and this is the case for them in one sentence.** See
`docs/PATTERNS/testing-checkers-and-adapters.md`. The suite that now exists would
have caught this: `test_a_lettered_requirement_id_sorts_without_raising` pins it
as a regression, and takes no repository to run.

**Where a checker takes a convention as input — an id format, a marker, a
pragma spelling — get a second real example before believing it works.** The
formats that exist on this machine are not the formats that exist.

## A second instance, same day

Estimating how many `[?]` markers qwark carried was done with
`grep -oE '\| *\[[^]]*\] *\|? *$'`. It matched 9 of a true 19, and the wrong
blast-radius figure was reported to the owner before the checker itself
corrected it.

**Count with the checker, not with a regex over the same table.** A second
parser of one format is a second thing to be wrong.
