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
| `shared-checkers` | The three defects that affect **every adopter**: the directory crash, the Go-only pragma scan, and `complexity` measuring the wrong files |
| `own-gate` | Getting toolbox's own four failing tasks green |
| `python-jig` | Adapters, and coverage enforced per file |
| `new-languages` | Rust, Ruby, shell, and the `LANGUAGES` change Rust forces |
| `adoption` | What `link-jigs` still does not record, ignore, or compose |

**Start with `shared-checkers`.** Those three are producing wrong answers in
other people's repositories, and two of them are false greens: a gate reporting
safety it never established.

## Open decisions with no task

Where does the schema belong? `schema/jig.schema.json` describes bolt's
configuration format, which is bolt's to define, and it lives here only because
this is where jigs live. If bolt ever ships its own, this one is deleted rather
than left to drift into a second, disagreeing description of one format. Nothing
to do until bolt does something.

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
`{configdir}/tools/test-traceability.py`, which is bolt's own pre-split fork.
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
