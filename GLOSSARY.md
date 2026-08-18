# Glossary

One word, one meaning. Where a word has been used two ways — and several have —
this file picks one and says what the other was.

Applies across `bolt`, `toolbox` and `anvil`.

---

## The three repositories

| Term | Means |
|---|---|
| **bolt** | The runner. Executes declared command lines over a file set and records what happened as envelopes. Knows nothing about any checker. |
| **toolbox** | This repository. Holds jigs, and the checkers and adapters they name. |
| **anvil** | The layered container images. Reads the `requires:` fields in this repository's jigs and installs exactly those tools. |

None depends on the other two in a circle: bolt runs jigs, toolbox holds them,
anvil provides the tools they require.

## The file

**jig** — a `bolt.*.yaml` file. A set of tasks, composed with other jigs by
overlay.

> A jig holds the work and guides the tool so the same cut comes out the same
> every time. That is what these files do: they guide bolt so the same checks
> come out the same on every project.

⚠️ **Two older words mean the same thing and should not be used in new writing:
"descriptor" and "definition".** Both appear in bolt's own comments and in
earlier drafts here. They are not wrong, they are just a third and fourth name
for one concept. Prefer **jig**.

⚠️ **A jig is not "a bolt".** Calling the files bolts was considered and
rejected: it collides with the runner's name, and *"run bolt against the go
bolt"* is genuinely ambiguous.

## Inside a jig

| Term | Means |
|---|---|
| **task** | One unit of work, with an `id`. Produces exactly one envelope. Tasks are independent and merge — there is no ordering and no dependency between them. |
| **checker** | **The thing a task runs.** Usually an off-the-shelf tool (`gofmt`, `golangci-lint`, `lizard`); where none exists, a script in `bin/`. |
| **adapter** | **A task's `result_command`.** Reads the execution record and returns the envelope that becomes the verdict. Needed only when the checker's exit code is not the answer. |
| **runtime** | What the process receives: `once` (no files), `allFiles` (one process, the whole list), `eachFile` (one process per file). |
| **selector** | A positional word naming a task id or a tag. One matching neither is an error, never an empty run. |
| **overlay** | Composing jigs. Later files win, tasks merge by id, so a jig can adjust an inherited task without restating it. |

⚠️ **"Checker" is the collision most worth watching.** It has been used to mean
the adapter. It does not. The checker *generates* the output; the adapter
*interprets* it. bolt's own docs are consistent on this — *"a checker that could
not run at all… fails without consulting a `result_command`"* names them as two
different things in one sentence.

## What a run produces

| Term | Means |
|---|---|
| **envelope** | The standard document: `success`, and optionally `reasons`, `evidence`, `captures`, `statistics`. One shape at every tier. |
| **record** | The execution record — what happened when the checker ran. It *is* an envelope, with `captures` filled in. There is no separate schema. |
| **captures** | `stdout`, `stderr`, `exitcode`. Describes one process, so a merged envelope carries none. |
| **reason** | One entry saying why `success` is false. Names its `checker`, and where it can, the file and line. |
| **evidence** | Files a task promises to produce, declared so that a run reporting success without producing them is a failure rather than a silent gap. |
| **verdict** | The `success` value that a task or run settles on. bolt's own exit status is never the verdict — `run_result.yaml` is. |

The pipeline, in order:

```
1. bolt runs the CHECKER          -> exit code, stdout, stderr
2. bolt captures those            -> the record
3. bolt hands the record to the ADAPTER   (if the task names one)
4. the adapter returns an ENVELOPE        -> the verdict
5. bolt writes <n>_output.yaml            the envelope, captures merged back
```

Measured, not asserted: `coverage`'s checker is `test -f coverage.out` and exits
**0**, while its adapter returns `success: false`. The adapter's verdict is the
task's verdict.

## Paths

| Term | Means |
|---|---|
| **`{configdir}`** | The directory of the jig naming the path. Substituted at parse time. |
| **run root** | The directory the run happens in — the project being checked. |
| **the rule** | What does the checking: a checker, an adapter, a linter's config. Travels with the jig, so `{configdir}`-relative. |
| **the subject** | What is being checked: the source, `REQUIREMENTS.md`, `SUPPRESSIONS`. Belongs to the project, so run-root-relative. |

> **A shared jig carries the rule and never the subject.**

## Names considered and rejected

Kept for the same reason a suppression register keeps its withdrawals: a name
considered and rejected is worth more to the next reader than one never
mentioned.

| Name | For | Why not |
|---|---|---|
| **thread** | the file | Bolts have threads, so the metaphor is the tightest available — but "thread" is the most overloaded word in computing, and bolt is written in Go. "bolt runs threads in parallel threads" is a sentence waiting to happen. |
| **bolt** | the file | Collides with the runner. |
| **nut** | the file | The natural fastener pairing, and undescriptive — a nut fastens, a jig shapes. |
| **cast** | the file | Semantically backwards: a cast is what comes *out* of the mould. These files are the mould. |
| **die**, **tap** | the file | Both cut threads, so the metaphor is right; both are unfortunate words. |
| **gauge** | the file | The most precise option — a go/no-go gauge is literally a pass/fail measuring tool — but "the Go gauge" reads as metrology jargon. |
| **blank-slate** | the images | Name previously used elsewhere; new work gets new names. |
| **checkers/** | the `bin/` directory | Contested word, so not a directory name. |
