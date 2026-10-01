# A set gaining a file breaks every adopter until it relinks

Adding `bin/voice-tells.py` to the `common` set in `jigs.yaml`, and naming it
from a task in `bolt.common-quality.yaml`, broke the common gate in eight of ten
adopters at once. They hold a symlink to the jig, so they got the new task the
moment it landed, and no link to the checker it names. The task fails with the
script missing, which reads as a broken gate and not as an adoption that is out
of date.

Measured over the estate: agent-support, anvil, bolt, infobot, palette-print,
qwark, silo and skid all lacked the link; dotfiles and wrench had relinked for
their own reasons and were fine. infobot's report says
`wording declared voice-tells.json and did not write it` and exit 2, which names
the evidence and not the cause.

Adding the composition adapter to the `common` set at `b9703d8` did the same to
seven of ten adopters, reported as
`adapter-failed | the adapter adapters/common/bolt-result.py exited 127`.

## What to do when a set gains a file

Relink every adopter in the same change, and check it:

    python3 bin/link-toolbox.py --check ../<adopter> <the sets it holds>
    python3 bin/link-toolbox.py --yes   ../<adopter> <the sets it holds>

The sets an adopter holds are readable from which jigs it links, since a jig
arrives with its set. Where somebody else is working in that tree, file the
relink instead of doing it: a link is a write in a repository that is not yours.

## Two things a relink does not fix

qwark and skid hold a real `just/base.just` rather than a link to toolbox's, so
the linker leaves it alone, reporting `a real file is in the way`. Two copies of
a recipe file can then drift with nothing to say so.

Every adopter carries a dangling `adapters/common/lizard.py`, left by an adapter
deleted with the `complexity` task that read for it. `--check` reports it as
orphaned and removes nothing, so the link stays, pointing at a file that does
not exist.

`clank/tasks/toolbox/adoption/40-one-symlink-instead-of-eleven` proposes one
directory link per adopter in place of one link per file, so a set gaining a
file reaches every adopter without a relink.
