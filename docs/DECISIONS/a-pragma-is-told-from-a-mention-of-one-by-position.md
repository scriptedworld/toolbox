# A pragma is told from a mention of one by position

Decided 2026-08-28, while making `suppression-register.py` read every language
at `6ac4304`. It was question 4 of `shared-checkers/20`, and it had no answer
when the other three were settled.

## The problem

A pragma **is** a comment. So no rule about strings, quoting or file type
separates a suppression from prose describing one, and the checker's own source
has to quote every spelling it hunts for.

Measured before the guard existed: 28 findings in toolbox, 22 of them fixture
data in `tests/test_suppression_register.py` and 6 in the checker itself. Not
one was a suppression of anything. Every adopter would have inherited the same,
since adoption links this repository's checkers into their `bin/`.

This is `a-project-cannot-test-its-own-tooling`, filed by wrench against the
traceability checker, arriving in a second checker: the tool cannot say *this
occurrence is the tool, not a use of the tool.*

## The decision

**A real pragma opens its comment, or is the first thing inside it. Prose
mentions the spelling mid-sentence.**

    x = 1  # noqa: E402                     the pragma opens the comment
    // #nosec G304 -- the path is the user's   first thing inside it
    a rule covering `# nosec` and not ...    mid-sentence, so not a pragma

## Why position, and not the alternatives

**Not a list of exempt filenames.** It would have to name every adopter's copy
of every checker, and it would exempt a real pragma written in the same file.
Position is a property of the text, so it holds everywhere with no configuration
and no register of exceptions.

**Not "skip anything in a string".** Necessary and nowhere near sufficient: a
pragma is a comment, so the interesting false positives are in comments. The
string rule is still there for fixture data on one line, and `code_lines`
handles triple-quoted blocks, but neither addresses prose in a `#` comment.

**Not requiring the pragma AT the comment opener.** Tried, and measured wrong:
palette-print writes `// #nosec G304 -- reason` for all twelve of its, where the
marker is `//` and the pragma begins three characters later. That version
silently missed all three of its `load.go` and `print.go` suppressions. **A
false negative here is the direction that matters, because it turns a gate
green.** Hence "opens the comment OR is the first thing inside it".

## What it does not handle, so nobody assumes it does

A string spanning lines by implicit continuation. The line scanner is
single-line and `code_lines` knows only triple-quoted blocks. A pragma spelling
inside such a string, in a comment position, would still be counted. No instance
exists in the estate today and the fix would be a parser per language, which is
more than this checker should carry.

## The general form, which outlives this checker

The estate spent 2026-08-28 on one fault: **a tool's selection rule is invisible
and answers a narrower question than its name.** This is that fault turned
inward, where the thing being selected wrongly is the tool's own source.

`clank/tasks/toolbox/jig-validation/20` holds the general version with five
instances. Whatever is decided there should be checked against this one, because
this is the case where the answer already exists and works.
