# Contributing

A change here reaches every project that has adopted a jig, so the checks below
are about not breaking somebody else's gate.

## Running the gate

toolbox is its own adopter, and uniquely so: it holds the real checkers and
adapters where every other adopter holds symlinks to them. That changes the
invocation.

```sh
bolt --definitions toolbox common-quality .
bolt --definitions toolbox python-std-quality .
bolt secrets .
```

**`--definitions toolbox` is not optional here, and no other adopter passes
it.** The shared jigs exclude `bin/` and `adapters/`, because everywhere else
those directories hold links to this repository's code and an adopter's tools
would otherwise grade toolbox's work as their own. Here they are the real files,
so taking the default would stop toolbox gating its own checkers.
`bolt.toolbox.definitions.yaml` holds the override.

Read `result.yaml` rather than the exit status. bolt exits 0 when the run
completed, whatever the tools concluded, and also when it refuses the jig
outright.

The Python suite runs on its own and needs none of the external tools:

```sh
python3 -m pytest
```

## The mistake that costs the most

Getting the path rule backwards. A path resolves against `{config_dir}` if it
travels with the jig, and stays relative to the run root if it belongs to the
project being checked. The README states it in full.

This is worth singling out because **it is invisible in the repository that gets
it wrong.** A jig sitting at its own root has a `{config_dir}` equal to its run
root, so both spellings resolve to the same file and the mistake shows up only
in somebody else's project.

`tests/test_jigs.py` is the guard. It fails a jig that reaches `bin/`,
`adapters/` or `config/` without `{config_dir}`, and fails one that prefixes an
`adapter:` with it, which would resolve twice.

## Changing a jig

Every jig validates against the schema wrench ships, which
`tests/test_jigs.py` imports rather than copying. If a jig needs a field the
schema does not have, the change starts in wrench.

bolt embeds those schemas at build time, so a binary enforces whatever the
schema said when it was built. Agreeing with wrench's source is necessary and
not sufficient: a jig using a field younger than an adopter's binary is accepted
and silently ignored, because the schema does not refuse unknown keys.

Two rules the tests enforce that are easy to trip:

- **A shared jig states no project-specific name.** No main package, no module
  path, no repository name. Those make the jig fail for every adopter, and the
  failure reads as the adopter's own.
- **A task that excludes anything names every exclusion slot.** Each slot
  carries a default and an override, because a placeholder holds one argument
  and the tools spell exclusion differently from one another.

## Adding a task

Prefer a checker whose exit code is the verdict. Add an adapter only when the
exit code cannot be the answer, and say in the task's comment which case it is.

**Do not ship a task that cannot fail.** Where no adapter can yet read a tool's
output, leave the task out. An absent check tells a reader the gate does not
cover that property; a green one claims a guarantee it never established.
`docs/DECISIONS/a-task-that-cannot-fail-leaves-the-jig.md` carries the worked
case.

## Adding a language

`bin/test-traceability.py` has a `LANGUAGES` table giving each language its test
file globs, its test declaration pattern and its comment marker. A language with
a jig here but no entry in that table finds no tests, cites nothing, and fails
every requirement at once, so the entry lands in the same change as the jig.

## Requirements and tests

`REQUIREMENTS.md` says what must be true. Every test names the requirement it
discharges, in a comment directly above it:

```python
# COVERS: FR-1.2 | property
```

The kinds are `positive`, `negative`, `edge`, `property` and `regression`, and
the checker rejects anything else. The `traceability` task fails a test that
cites nothing, and fails a settled requirement that no test cites.

A requirement can be retired or superseded, and its ID is never reused, because
reuse silently rewrites what every existing reference to that ID means. Retiring
one leaves its `COVERS:` marks pointing at nothing, and they are repointed or
removed in the same change.

`[?]` in a requirement's status cell marks an open decision that cannot have a
test yet and is reported without failing. Reaching for it to quiet the gate is
the failure mode to watch: the marker says the decision is open, not that the
test is inconvenient.

## Tests

One test file per script under test, named for that script.
`docs/PATTERNS/testing-checkers-and-adapters.md` is the full account. Three
things it asks for that a reviewer will look for:

- **Fixtures are captured, never composed.** Run the real tool once, save what
  it printed under `tests/fixtures/`, and record the tool version and the
  capture date in the file. An adapter fed output somebody imagined tests their
  imagination.
- **Assert the verdict and what the verdict says.** `success is False` passes
  just as happily when the adapter fails for the wrong reason on the wrong file.
- **Cover the empty case.** A checker that finds nothing after looking in the
  wrong place is indistinguishable from one that found nothing wrong.

Tests call `main()` in process rather than through a subprocess, because
coverage sees nothing a subprocess does. One subprocess smoke test per script
covers the wiring that in-process testing cannot reach: a bad shebang, a file
that is not executable, a crash on import.

## Suppressions

There is no `SUPPRESSIONS` file here, because nothing is silenced. That is the
honest state rather than a gap: an empty register asserts that something is
suppressed when nothing is.

If a change genuinely needs a `#nosec`, `# noqa`, `//nolint` or a `type: ignore`,
the register comes back with it, carrying the reason. The `suppressions` task
fails in both directions, on an unregistered pragma and on a registered row with
nothing behind it. Fixing the underlying problem is almost always smaller than
it looks.

## Commit messages

Conventional commits, with a scope naming the part of the repository that
changed:

```
fix(traceability): a wrapped decorator no longer hides a test's COVERS mark
```

The subject says what changed. The body says what it cost, in counts and
verdicts, and where the rest lives. The reasoning belongs in the file the commit
changed, and a sentence that would survive being moved into that file belongs
there instead.

## Prose

`README.md` and the documents under `docs/` are held to the same bar as the
code. State what is true rather than narrating what changed and when, since git
already records that. No em-dashes. A document earns its length by covering its
subject, not by explaining a decision twice in two places.
