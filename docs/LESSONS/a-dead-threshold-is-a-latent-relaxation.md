# A dead threshold is a latent relaxation waiting for a simplification

Where a jig has two tools measuring one property at two limits, the looser limit
can never be the binding constraint. It is not merely redundant. **It is a
hidden number that becomes the real one the moment somebody removes the
redundancy for good reasons.**

Found by the wrench session 2026-08-28, generalised by bolt the same day.

## The Python case

`bolt.python-std-quality.yaml` measures docstring coverage twice:

    docstrings   interrogate --fail-under 80        a percentage
    analyse      pylint missing-function-docstring  per function, no threshold

pylint's rule fires on every public function without one, so `analyse` is a
**100%** requirement. `docstrings` is an 80% requirement. A project lands in one
of three bands, and **no project can be failed by the 80 while passing
`analyse`**. The 80 is decoration; the real floor is 100, enforced by the task
that does not mention docstrings in its name or its description.

It was invisible from toolbox because toolbox sits at 100% on its own suite, in
the top band where the two agree. **The jig had never been run by its author
against a project in the middle band.**

## The Rust case, which is worse and is why this generalises

`bolt.rust-quality.yaml`, bolt `363c6c9`:

    lizard    --length 60          --arguments 5
    clippy    too_many_lines 100   too_many_arguments 7

No `clippy.toml`, so those are clippy's defaults, and both lints are already on
through pedantic. lizard binds first, so **neither clippy lint can ever fire.**

Bolt had the proof and had misread it: while implementing its skeleton,
`run_task` at 73 lines and `write_manifest` at 6 parameters both failed lizard
and passed clippy under `-D warnings`. That reads as the complexity gate
working. It is also two lints proving themselves dead, in the same output.

**Bolt's `NEXT_STEPS` carried a documented plan to drop lizard and rely on the
clippy lints, on the grounds that they measure the same things.** They measure
the same things *at different thresholds*, so the swap moves the limits from 60
and 5 to 100 and 7 with **no line of the diff mentioning a threshold**, and
every reason written down for it is true.

## What to do

**Pin both tools to the same number and say which is authoritative**, so
removing either is a visible change rather than a silent one. Where two tools
genuinely cannot agree, delete one.

**This bears on the Rust promotion.** `bolt.rust-quality.yaml` is going to
toolbox as the shared standard and the dead pair ships with it. Any adopter
enabling pedantic inherits both, and the first one to tidy lizard away relaxes
its gate without knowing. Better settled before promotion than by that adopter.

## The half that is not about thresholds

The Python case also exposed an inconsistency worth keeping separate: `types`
and `lint` both state that strictness is the adopter's, made in its own
`pyproject.toml`. `analyse` says nothing, and pylint reads `[tool.pylint]`
exactly as mypy and ruff read theirs. The jig defers to the adopter for two of
its three configurable tools and not the third, and the third is where the
collision happened.

**The docstring question this file came from was half a symptom and half a real
gap**, and calling it simply "retired" was wrong.

The symptom: `analyse` runs pylint's entire default rule set because nothing
configures it, which is the only reason `missing-function-docstring` was a
second docstring gate. Configuring the split the jig's header already describes
removes the collision without anyone choosing a percentage.

The real gap, given as direction 2026-08-28: **the test side is held to a more
relaxed standard than the source side, and nothing in the jig expresses that.**
Tests must carry their `COVERS` metadata, which
`bin/test-traceability.py` already enforces on `def test_*` alone, so fixtures
and helpers are exempt by construction. Docstrings are wanted on tests and are
not the same requirement they are on source.

So there is still no percentage to pick, and there IS a distinction to encode.
Per-file ignores for the test tree are the shape that says it.
`clank/tasks/toolbox/own-gate/20` carries it.
