# A checker is only exercised by the repository it happens to be pointed at

## What it cost

`test-traceability.py` sorted requirement ids with a key that compared an `int`
segment against a `str` one:

    parts = tuple(int(p) if p.isdigit() else p for p in re.split(r"[.]", number))

`FR-4.13` keys as `(4, 13)`. `FR-4.13a` keys as `(4, '13a')`. Comparing them
raises:

    TypeError: '<' not supported between instances of 'str' and 'int'

`bolt` has no lettered requirement id, so a full run against bolt passes.
`qwark` has eleven, `FR-4.9a`, `FR-4.13a`, `FR-10.3b` and the rest, and a run
against it raises.

The fix keys every segment as `(number, suffix)`, so both shapes compare:

    split = len(part) - len(part.lstrip(DIGITS))
    segments.append((int(part[:split] or 0), part[split:]))

## Why it matters more here than elsewhere

These checkers are shared. They get pointed at repositories their author has
never seen, and whoever runs them will read a traceback as *their* repository
being broken. A crash is loud. A wrong answer given quietly is not: a scan
that reads only one language's files passes every adopter written in another.

A checker run against one repository has been tested on that repository's
conventions and no others.

## What to do with it

Write tests, as `docs/PATTERNS/testing-checkers-and-adapters.md` describes.
`test_a_lettered_requirement_id_sorts_without_raising` pins this case and needs
no repository to run.

**Where a checker takes a convention as input, whether an id format, a marker or
a pragma spelling, get a second real example before believing it works.**

## A second instance

Over qwark's requirements, `grep -oE '\| *\[[^]]*\] *\|? *$'` matches 9 of the
19 `[?]` markers the checker counts.

**Count with the checker, never with a regex over the same table.** A second
parser of one format can disagree with the first.
