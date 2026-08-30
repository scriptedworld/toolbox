---
name: Adoption problem
about: A jig fails in your project in a way that looks like the jig's fault
labels: adoption
---

## What the task reported

The task name and its output from `result.yaml`.

## Whether it is the jig or your project

Two checks separate these, and they are worth running before filing.

**Does the jig reach outside your project?** A shared jig should name only its
own checkers and your project's own documents. If a path in the failing command
points into another repository, that is a jig defect and this is the right place
for it.

**Is the finding about a file you did not write?** Adoption links this
repository's checkers into your `bin/` and `adapters/`. The shared jigs exclude
those directories so your tools do not grade code you adopted. If a finding
names one of those files, say so.

## Your adoption

```sh
python3 bin/link-jigs.py --check /path/to/your-project <sets>
```

Whether any link was refused because a real file was in the way. A vendored copy
that predates adoption keeps running instead of the shared checker, and the
symptom is the two disagreeing about the same tree.

## What you have supplied

`traceability` needs a `REQUIREMENTS.md`, and `suppressions` needs a
`SUPPRESSIONS` file once you have any pragmas. Absent, both fail by design
rather than by accident.
