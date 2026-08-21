# toolbox — Next Steps

**The queue is not here.** It is `~/.projects/clank/tasks/toolbox/`, one
directory per task, and **the listing is the index** — a table here would go
stale the moment a task changed state.

    ( setopt null_glob; print -l ~/.projects/clank/tasks/toolbox/*/*.ready )
    ( setopt null_glob; print -l ~/.projects/clank/tasks/toolbox/*/*.questions )

The second query is *what is waiting on the owner*. FACT 2026-08-21, counted
from the directory: **11 `.ready`, 4 `.questions`, 2 `.planning`.** Each
`.questions` task has its questions numbered inside `TASK.md`, so answering is a
reply rather than a rediscovery.

This file holds only what has no task yet: decisions still open, and the state
of the two documents that describe the project.

Read `silo/docs/GLOSSARY.md` if any of *jig*, *checker*, *adapter*, *envelope*
or *the rule versus the subject* is unfamiliar. The terminology is load-bearing
and most of the tasks are meaningless without it.

---

## The shape of the queue, 2026-08-21

Five groups, seventeen tasks, written at commissioning from this document and
from the eleven findings in `clank/inbox/toolbox/`.

| Group | About |
|---|---|
| `shared-checkers` | The three defects that affect **every adopter**: the directory crash, the Go-only pragma scan, and `complexity` measuring the wrong files |
| `own-gate` | Getting toolbox's own four failing tasks green |
| `python-jig` | Adapters, and coverage enforced per file |
| `new-languages` | Rust, Ruby, shell — and the `LANGUAGES` change Rust forces |
| `adoption` | What `link-jigs` still does not record, ignore, or compose |

**`shared-checkers` first.** Those three are the ones producing wrong answers in
other people's repositories right now, and two of them are **false greens**
rather than failures — a gate reporting safety it never established.

## Open decisions with no task

**Where does the schema belong?** `schema/jig.schema.json` describes bolt's
configuration format, which is bolt's to define — but it lives here because this
is where jigs live. If bolt ever ships its own, this one must be **deleted**
rather than allowed to drift into a second, disagreeing description of one
format. Nothing to do until bolt does something; recorded so it is not
rediscovered.

**Should jigs be discoverable by short name?** `bolt --use go-std-quality`
resolving against a `BOLT_TOOLBOX` environment variable, rather than repeated
`-c` with full paths. Ordering must stay explicit — a directory glob has no
order, and order is semantics here. **Needs a change to bolt**, so it is not a
toolbox task.

Note that `jigs.yaml` and `link-jigs.py` have since answered the *adjacent*
question — a project now declares which sets it adopts, and the files arrive as
symlinks. What remains unanswered is invoking them by name rather than by path.

**`entrypoint` ordering may also need a change to bolt.** See
`clank/tasks/toolbox/jig-content/10-entrypoint-ordering-and-home.questions/`:
bolt has no ordering between tasks by design, and the fix may need one. That
would make two things waiting on bolt.

## Handoff owed to bolt

**`bolt` does not use this repository.** FACT 2026-08-20: `just checks` runs
`./bin/bolt -c bolt.go-std-quality.yaml`, whose `traceability` task names
`{configdir}/tools/test-traceability.py` — bolt's own pre-split fork. Same tree,
same minute: bolt's copy exits **0** where this one exits **1**.

Adoption was attempted and **four paths were refused** because real files were in
the way, which is `link-jigs` behaving correctly rather than failing.

This is not toolbox's work to do. It is filed with evidence and a regenerating
script at `clank/inbox/bolt/gate-runs-a-stale-fork-of-the-checkers/`, and only
bolt's own session resolves it.

## The two documents that moved, 2026-08-21

**`TESTING.md` → `docs/PATTERNS/testing-checkers-and-adapters.md`.** It has a
*"when you are working on X"* precondition, which belongs in `docs/` proper
rather than in the always-read tier.

**`GLOSSARY.md` → `silo/docs/GLOSSARY.md`.** It governs `bolt`, `toolbox` and
`anvil`, and a vocabulary living inside one of the three is read by sessions in
the other two only if they think to look. `bolt/CLAUDE.md` and `anvil/README.md`
still point at the old location; findings are filed against both.
