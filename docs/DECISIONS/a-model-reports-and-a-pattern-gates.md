# A model reports, and a pattern gates

The `wording` task in `bolt.common-quality.yaml` fails an adopter on the
phrasing `silo/docs/PATTERNS/writing-standard.md` names. It runs
`bin/voice-tells.py`, which asks no model. The model review beside it,
`bin/voice-review.py`, is no task at all: it is run by hand and never fails
anything.

That split is the decision, and the measurement behind it is here because the
first design was the other way round.

## What was tried first

A model scored documentation, comments and commit messages from 0 to 100 against
a rubric, three runs per category, the median held against a floor per category.
It shipped with the floors at 0, which fails nobody, and the question of what the
floors should be is what produced the evidence.

Scored three times over each of 21 repositories, the same unchanged tree came
back with medians up to 21 points apart: toolbox's documentation scored 58, 74
and 79. A floor anywhere near a repository's own score decides pass or fail by
which run it got.

Findings instead of a score did not fix it. Asked for instances and not a grade,
over whole files and not a sample, two runs over ratchet's 19 documents
agreed on 30 findings out of a union of 77, and several that appeared once were
wrong: a plain requirement, `The engine makes no model call, ever.`, was reported
as a closing aphorism.

Verifying a finding's quote against the line it names removes an invented quote,
6 of 113 in that trial. It cannot remove a wrong judgment.

## Why the pattern check can gate and the model cannot

A pattern reads every line, gives the same answer every run, and names the file
and line of each instance. That is what lets it fail on one instance with no
floor to argue about. Where a rule cannot be a pattern, it is not a gate.

A house rule is also a different question from the one a detector answers. The
research this drew on rates a lexical marker by how often it misfires on human
prose, and concludes that a single em-dash must never block. The writing standard
bans em-dashes whoever wrote them, so a hit is a violation rather than a guess,
and blocking is right here for a reason that does not generalise.

## What the model is still for

The habits a pattern cannot catch: a closing aphorism, an emphatic contrast with
nothing contrasted, narrated history, a passage restating another file, table
stakes, a rule of three. `config/prompts/voice-findings.md` asks for those and
nothing else, and a finding stands only when its quote starts on the line it
names.

A rule the model applies consistently belongs in `bin/voice-tells.py` as a
pattern. That is the route from the report to the gate, and it is the only one.
