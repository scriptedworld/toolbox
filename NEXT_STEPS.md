# toolbox, Next Steps

**The queue is not here.** It is `~/.projects/clank/tasks/toolbox/`, one
directory per task, and the listing is the index. A table in this file would go
stale the moment a task changed state.

    ( setopt null_glob; print -l ~/.projects/clank/tasks/toolbox/*/*.ready )
    ( setopt null_glob; print -l ~/.projects/clank/tasks/toolbox/*/*.questions )

The second query is *what is waiting on me*. Every `.questions` task numbers
its questions inside `TASK.md`, so answering is a reply and not a rediscovery.

This file holds only what has no task yet: the decisions still open, and the
state of the two documents that describe the project.

Read `silo/docs/GLOSSARY.md` if any of *jig*, *checker*, *adapter*, *envelope* or
*the rule versus the subject* is unfamiliar. The terminology is load-bearing, and
most of the tasks are meaningless without it.

---

## The shape of the queue

| Group | About |
|---|---|
| `shared-checkers` | The defects that affect **every adopter**. The directory crash closed at `cc65aad` and the Go-only pragma scan at `6ac4304`; what remains is `complexity` measuring the wrong files |
| `own-gate` | Getting toolbox's own four failing tasks green |
| `python-jig` | Adapters, and coverage enforced per file |
| `new-languages` | Rust, Ruby, shell, and the `LANGUAGES` change Rust forces |
| `adoption` | What `link-jigs` still does not record, ignore, or compose |

**`shared-checkers` was the place to start and two of its three are closed.**
Both were false greens, a gate reporting safety it never established. The
directory crash went at `cc65aad`; the Go-only pragma scan went at `6ac4304`,
which also made a run that reads no source fail rather than pass. What remains
is `complexity` measuring the wrong files, and that one is now understood as an
instance of a wider fault rather than a defect of its own: see
`clank/tasks/toolbox/jig-validation/20`, where the selection rule being invisible
and narrower than the question is stated generally with five instances.

## Open decisions with no task

**Where do the two migration scripts live?** `.ephemera/split-probe.py` splits a
`REQUIREMENTS.md` into a directory and proves the verdict does not move;
`.ephemera/retired-parity.sh` checks that every retired id survived such a split,
and names the dropped one. Both are gitignored, so they exist in one working
tree and no clone.

The asymmetry is the whole argument, and bolt put it best: each repository
migrates once, so the tools run eight times and then never, which argues for
scratch. But the cost of not having them once is a silently reusable requirement
id, which is unbounded and undetectable. The eighth person should not be
rewriting either from memory.

Both were cited as evidence from places that outlive a scratch directory, a
`.complete` task and a message to another session. Those citations are removed
as an interim rather than the question pre-empted.

**~~Where does the schema belong?~~ ANSWERED 2026-08-29: wrench, and this
repository keeps no copy.** `schema/` is deleted and `tests/test_jigs.py`
imports the pack and validates against the validator wrench ships. `NFR-6` moves
from `[?]` to settled.

The copy disagreed twice, on `allow-empty` arriving and again on its rename to
`optional`, and each time a test caught the copy and the fix was to copy the
file again. **Importing removes the class rather than the instance: there is no
local artefact left to drift.**

One thing that survives the answer, because it is about bolt rather than about
the copy: **bolt embeds the schemas at build time**, so a binary enforces
whatever wrench said when it was last built. Measured 2026-08-27, the field was
in the bolt built at 20:11 and absent from the one built at 13:11. **Agreeing
with wrench's source is necessary and not sufficient**, and a jig using a field
younger than an adopter's binary is accepted and silently ignored, because the
schema does not refuse unknown keys. That is recorded in `tests/test_jigs.py`
where somebody validating a jig will meet it.

**Maintainability index: drop it from the standard, or declare it Python-only?**
Only Python has a tool, `radon mi`. Go, Rust and TypeScript have no maintained
one, and the multi-language candidate `rust-code-analysis` was last updated
2023-01-13. From
`clank/inbox/toolbox/quality-jigs-with-comparable-analysis-per-language/`, which
argues a language that cannot meet the standard should declare it rather than
omit it silently.

**Promoting bolt's Rust jig to a shared `bolt.rust-quality.yaml`.** Routed
2026-08-27 through silo from wrench as our user's choice, so it is second-hand
here; confirm the shape with our user rather than with either of them. It needs
bolt to agree and toolbox to take it. `bolt/bolt.rust-quality.yaml` exists and
is used, and its header already records which shared jig each task belongs to.

Should jigs be discoverable by short name? `bolt --use go-std-quality` would
resolve against a `BOLT_TOOLBOX` environment variable instead of repeated `-c`
with full paths. Ordering has to stay explicit, because a directory glob has no
order and order is semantics here. It needs a change to bolt, so it is not a
toolbox task.

`jigs.yaml` and `link-jigs.py` answer the *adjacent* question: a project declares
which sets it adopts, and the files arrive as symlinks. What is unanswered is
invoking them by name instead of by path.

`entrypoint` ordering may also need a change to bolt. See
`clank/tasks/toolbox/jig-content/10-entrypoint-ordering-and-home.questions/`:
bolt has no ordering between tasks by design, and the fix may need one. That
would make two things waiting on bolt.

## Handoff owed to bolt

`bolt` does not use this repository. `just checks` there runs
`./bin/bolt -c bolt.go-std-quality.yaml`, whose `traceability` task names
`{config_dir}/tools/test-traceability.py`, which is bolt's own pre-split fork.
Against the same tree in the same minute, bolt's copy exits **0** where this one
exits **1**.

Adoption was attempted and four paths were refused because real files stood in
the way, which is `link-jigs` behaving correctly and not failing.

None of this is toolbox's work to do. It is filed with its evidence and a
regenerating script at
`clank/inbox/bolt/gate-runs-a-stale-fork-of-the-checkers/`, and only bolt's own
session resolves it.

## Stale pointers owed to two siblings

The glossary lives at `silo/docs/GLOSSARY.md`, governing `bolt`, `toolbox` and
`anvil` alike. `bolt/CLAUDE.md` and `anvil/README.md` still point at this
repository's old copy, and a finding is filed against each.
