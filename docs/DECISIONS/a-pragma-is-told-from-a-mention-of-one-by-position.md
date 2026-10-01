# A pragma is told from a mention of one by position

This applies to `suppression-register.py`, which reads every language. It
answers question 4 of `shared-checkers/20`.

## The problem

A pragma is a comment. So no rule about strings, quoting or file type
separates a suppression from prose describing one, and the checker's own source
has to quote every spelling it hunts for.

Without a guard the checker reports 28 findings in toolbox, 22 of them fixture
data in `tests/test_suppression_register.py` and 6 in the checker itself, and
none of them suppresses anything. Every adopter inherits the same, since
adoption links this repository's checkers into their `bin/`.

The traceability checker has the same fault, filed as
`a-project-cannot-test-its-own-tooling`: a tool cannot tell an occurrence that
is its own source from a use of what it checks.

## The decision

**A real pragma opens its comment, or is the first thing inside it. Prose
mentions the spelling mid-sentence.**

    x = 1  # noqa: E402                     the pragma opens the comment
    // #nosec G304 -- the path is the user's   first thing inside it
    a rule covering `# nosec` and not ...    mid-sentence, so not a pragma

## Why position, and not the alternatives

Not a list of exempt filenames. It would have to name every adopter's copy
of every checker, and it would exempt a real pragma written in the same file.
Position is a property of the text, so it holds everywhere with no configuration
and no register of exceptions.

Not "skip anything in a string". Necessary and nowhere near sufficient: a
pragma is a comment, so the interesting false positives are in comments. The
string rule is still there for fixture data on one line, and `code_lines`
handles triple-quoted blocks, but neither addresses prose in a `#` comment.

Not requiring the pragma to sit exactly at the comment opener. palette-print
writes `// #nosec G304 -- reason`, where the marker is `//` and the pragma begins
three characters later, and that rule misses all three of its `load.go` and
`print.go` suppressions. A false negative turns a gate green, so the rule is
"opens the comment, or is the first thing inside it".

## What it does not handle

A string spanning lines by implicit continuation. The line scanner is
single-line and `code_lines` knows only triple-quoted blocks. A pragma spelling
inside such a string, in a comment position, would still be counted. No instance
exists in the estate today and the fix would be a parser per language, which is
more than this checker should carry.

## The general form

Several tools here have a selection rule that is invisible and answers a
narrower question than the tool's name. This is that fault turned inward, where
what is selected wrongly is the tool's own source. A fix for the general fault
should be checked against this case, which already has a working answer.
