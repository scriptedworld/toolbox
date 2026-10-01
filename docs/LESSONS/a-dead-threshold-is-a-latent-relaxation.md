# A dead threshold is a latent relaxation waiting for a simplification

Where a jig has two tools measuring one property at two limits, the looser limit
can never be the binding constraint. It is a hidden number that becomes the real
one the moment somebody removes the redundancy for good reasons.

## The Python case

`bolt.python-std-quality.yaml` measures docstring coverage twice:

    docstrings   interrogate --fail-under 80        a percentage
    analyse      pylint missing-function-docstring  per function, no threshold

pylint's rule fires on every public function without one, so `analyse` is a
100% requirement. `docstrings` is an 80% requirement. A project lands in one
of three bands, and **no project can be failed by the 80 while passing
`analyse`**. The real floor is 100, enforced by the task that does not mention
docstrings in its name or its description.

toolbox sits at 100% on its own suite, in the top band where the two agree, so
running the jig here cannot show it. Only a project in the middle band can.

## The Rust case

`bolt.rust-quality.yaml`, bolt `363c6c9`:

    lizard    --length 60          --arguments 5
    clippy    too_many_lines 100   too_many_arguments 7

No `clippy.toml`, so those are clippy's defaults, and both lints are already on
through pedantic. lizard binds first, so neither clippy lint can ever fire.

bolt's own output shows it: `run_task` at 73 lines and `write_manifest` at 6
parameters both failed lizard and passed clippy under `-D warnings`. That reads
as the complexity gate working, and it is also two lints shown to be dead.

Dropping lizard for the clippy lints, on the grounds that they measure the same
things, moves the limits from 60 and 5 to 100 and 7, because they measure them
*at different thresholds*. **No line of that diff mentions a threshold.**

## What to do

**Pin both tools to the same number and say which is authoritative**, so
removing either is a visible change and not a silent one. Where two tools
genuinely cannot agree, delete one.

## The half that is not about thresholds

The Python jig is also inconsistent about who configures a tool: `types` and
`lint` both state that strictness is the adopter's, made in its own
`pyproject.toml`. `analyse` says nothing, and pylint reads `[tool.pylint]`
exactly as mypy and ruff read theirs. The jig defers to the adopter for two of
its three configurable tools and not the third, and the third is where the
docstring collision sits.

The docstring question is half a symptom and half a real gap.

The symptom: `analyse` runs pylint's entire default rule set because nothing
configures it, which is the only reason `missing-function-docstring` was a
second docstring gate. Configuring the split the jig's header already describes
removes the collision without anyone choosing a percentage.

The real gap is a direction I have set: **the test side is held to a more
relaxed standard than the source side, and nothing in the jig expresses that.**
Tests must carry their `COVERS` metadata, which
`bin/test-traceability.py` already enforces on `def test_*` alone, so fixtures
and helpers are exempt by construction. Docstrings are wanted on tests and are
not the same requirement they are on source.

So there is no percentage to pick, and there is a distinction to encode: per-file
ignores for the test tree.
