# toolbox — Requirements

First derived 2026-08-20, from this repository as it stands and from the
decisions recorded in `README.md`, `GLOSSARY.md` and `NEXT_STEPS.md`. Where a
requirement traces to a decision the owner took in a session, it says so.

toolbox holds the **jigs** bolt runs, and the **checkers** and **adapters** they
name. Read `GLOSSARY.md` first: *checker* and *adapter* mean specific and
opposite things, and several requirements below are meaningless without that
distinction.

Requirements are stated as observable properties: each says what is true of a
run, not how the code is arranged. Mechanism appears only where the mechanism is
itself the requirement — the path rule is the clearest case, because getting it
backwards is invisible in the repository that gets it wrong.

**The chain is meant to be followed in both directions.** A requirement says
what must be true; a test says `COVERS:` and names the requirement it
discharges. The `traceability` task in this repository's own
`bolt.common-quality.yaml` enforces that link mechanically, on this repository
as on any other.

**Status markers.** `[A]` traces to an author statement. `[D]` is derived
reasoning, to be accepted or rejected on its merits. `[?]` is an open decision,
recorded so it is not lost; it must be resolved before the affected requirement
is testable.

---

## FR-1 — What a jig is

*Derives from:* `GLOSSARY.md`, **The file**; `README.md`, **Using them**.

| ID | Requirement | |
|---|---|---|
| FR-1.1 | A jig is a `bolt.*.yaml` file holding a set of tasks. It is composed with other jigs by overlay: later files win, and tasks merge by id, so a jig can adjust an inherited task without restating it. | [A] |
| FR-1.2 | Every jig in this repository validates against `schema/jig.schema.json`. A jig that does not is a jig bolt may accept today and reject tomorrow. | [D] |
| FR-1.3 | A jig carries **the rule and never the subject**. What does the checking travels with the jig; what is being checked belongs to the project. A jig bundling a document *about a codebase* has stopped being adoptable, because it judges every adopter against its author's answers. | [A] |
| FR-1.4 | `{configdir}` resolves a path against the directory of the jig naming it; every other path stays relative to the run root. Getting this backwards is invisible in a repository whose jig sits at its own root, because the two are then the same directory. | [A] |
| FR-1.5 | A shared jig states no project-specific name. `entrypoint` was removed from the Go jig for hardcoding `./cmd/bolt`; it looked like a rule and was a subject. | [A] |

## FR-2 — Checkers

*Derives from:* `GLOSSARY.md`, **Inside a jig**; `TESTING.md`, **Two contracts**.

| ID | Requirement | |
|---|---|---|
| FR-2.1 | A checker is what a task runs. Its input is `argv` and the filesystem; **its exit code is the verdict**, which is why a checker needs no adapter. | [D] |
| FR-2.2 | A checker written here reports its findings on stdout, naming the file, line or identifier the finding is about. A finding nobody can locate is a finding nobody acts on. | [D] |
| FR-2.3 | A checker fails rather than raising when the document it is given is absent. A traceback is not a verdict, and the adopter who has not yet written the document is the reader most in need of an instruction. | [D] |
| FR-2.4 | A checker refuses to pass vacuously. Zero requirements agreeing with zero citations is not a passing gate; it is a gate with nothing in it. | [A] |
| FR-2.5 | A checker does not walk trees belonging to someone else — `.venv`, `node_modules`, `vendor`, `testdata`. A vendored suite full of unannotated tests must not fail the project that vendored it. | [D] |

## FR-3 — Adapters

*Derives from:* `README.md`, **Checkers and adapters**; `GLOSSARY.md`, **What a run produces**.

| ID | Requirement | |
|---|---|---|
| FR-3.1 | An adapter is a task's `result_command`. Its input is `argv` and an execution **record** on stdin; its output is an **envelope** on stdout. Its own exit code means nothing — the envelope is the verdict. | [D] |
| FR-3.2 | An adapter exists only where the checker's exit code is not the answer. `gofmt -l` lists unformatted files and exits 0 either way, so its status answers "did gofmt run" and never "is this formatted". | [A] |
| FR-3.3 | An adapter is pure: no clock, no filesystem, no network. It is therefore testable from a fixture record with the tool it is about absent from the machine. | [D] |
| FR-3.4 | An adapter emits one reason per finding, naming its `checker` and, where the tool gives them, the file and line. Where a fix is mechanical, the reason carries it. | [D] |
| FR-3.5 | An adapter omits optional blocks rather than emitting them empty. `reasons: []` on a pass reads as "checked and found nothing to say", which is not the same as having nothing to report. | [D] |
| FR-3.6 | An adapter reading output it does not recognise from a checker that also exited non-zero reports a failure it cannot name, rather than a pass. Silence plus a bad exit code is not success. | [D] |
| FR-3.7 | `[?]` **Every adapter emits `statistics` on pass as well as on fail.** A number is only useful as a series, and a task reporting nothing when it passes cannot show a trend. Currently true of `lizard.py` alone; the Python jig has no adapters at all. See `NEXT_STEPS.md` item 1. | [?] |

## FR-4 — Traceability

*Derives from:* the owner's decision of 2026-08-20 to make this a gate; `README.md`, **Traceability is a gate, not a report**.

| ID | Requirement | |
|---|---|---|
| FR-4.1 | Every test states which requirement it discharges and by which path, as `COVERS: <ids> | <kind>` in the comment block immediately above it. | [A] |
| FR-4.2 | A test citing a requirement the document does not declare fails, so a renamed or deleted requirement is caught rather than left rotting in a comment. | [D] |
| FR-4.3 | A `COVERS` line naming a kind outside the declared set fails. The kind says which path through the requirement the test walks. | [D] |
| FR-4.4 | A `COVERS` line citing no requirement id at all fails. It parses as an annotation and discharges nothing. | [D] |
| FR-4.5 | A requirement no test cites **fails**, unless its row marks it open. Until 2026-08-20 this was reported as context and exited 0, which made the document something nothing held the code to. | [A] |
| FR-4.6 | Open is `[?]` in the row's last bracketed cell, and nothing else. `[A]`, `[D]`, `[A/D]` and **no marker column at all** are settled, so a document without markers claims no exemptions: exemption is claimed, never granted by omission. | [A] |
| FR-4.7 | Test discovery reads every language this repository ships a jig for. A language with a jig and no entry in the checker's language table finds no tests, cites nothing, and fails every requirement at once. | [A] |
| FR-4.8 | Discovery finds a test wherever the language puts one — indented in a class, declared `async`, or separated from its annotation by a decorator. | [D] |
| FR-4.9 | Requirement ids order numerically and tolerate a letter suffix, so `FR-7.3` precedes `FR-7.10` and `FR-4.13a` compares against `FR-4.13` rather than raising. | [D] |

## FR-5 — The suppression register

*Derives from:* `bolt.common-quality.yaml`, the `suppressions` task; the 2026-08-16 incident recorded in `bin/suppression-register.py`.

| ID | Requirement | |
|---|---|---|
| FR-5.1 | Every suppression pragma in the source appears in the register, and every row of the register corresponds to a pragma that is really there. Both directions fail. | [A] |
| FR-5.2 | The count is part of the comparison, so a second pragma added to an already-registered file is caught rather than hidden behind the first. | [A] |
| FR-5.3 | A project with no pragmas and no register passes. A project with pragmas and no register does not. | [A] |
| FR-5.4 | `[?]` **The register covers every language this repository ships a jig for.** FACT 2026-08-20: it walks `*.go` only and requires gosec or `//nolint` rule ids, so a Python `# nosec` is not silenced-and-justified but silenced and unseen — a false green in a gate. Open because fixing it newly fails every adopter carrying an unregistered pragma. See `NEXT_STEPS.md` item 7. | [?] |

## FR-6 — Adoption

*Derives from:* `README.md`, **Adopting these in a project**.

| ID | Requirement | |
|---|---|---|
| FR-6.1 | Everything a jig needs is either in this repository or in the adopting one. Nothing reaches outside both. | [A] |
| FR-6.2 | `[?]` **A project composes jigs by short name rather than by repeated `-c` with full paths.** Ordering must stay explicit, because a directory glob has no order and order is semantics here. Needs a change to bolt. See `NEXT_STEPS.md`, open decisions. | [?] |

## FR-7 — Adoption by link

*Derives from:* `bin/link-jigs.py` and `jigs.yaml`, and the reasoning in their
own headers. A jig names checkers, adapters and tool configuration that live
beside it here; `{configdir}` resolves those against the jig's own directory, so
a jig reached through a symlink resolves them back through that same link.
Adoption is therefore a set of symlinks.

| ID | Requirement | |
|---|---|---|
| FR-7.1 | An entry lands at the same relative path in the target that it has here. This is forced rather than chosen: a linked jig sits at the target's root, which makes `{configdir}` the target's root, so `bin/x.py` must be at `bin/x.py` for the jig to find it. There is no destination to configure and so no mapping to keep in step. | [A] |
| FR-7.2 | A set may include another, and adopting it brings the included set with it — because the including jig overlays the included one. A set declaring no includes pulls nothing. | [A] |
| FR-7.3 | The manifest is **declared, not derived**. Reading `{configdir}` references out of the jigs would build today's list correctly and be wrong tomorrow: a jig running `ruff check .` or `pylint --recursive=y .` needs whatever configuration those tools read by convention and names none of it on the command line. | [A] |
| FR-7.4 | Links are relative by default, so the pair can move together; an absolute link encodes one machine's layout. Absolute is available for a toolbox that sits at a fixed path and does not travel. | [D] |
| FR-7.5 | **Nothing is ever overwritten.** A real file where a link belongs is reported and left alone: it is usually a vendored copy predating adoption, and deleting someone's file is their decision. | [A] |
| FR-7.6 | A manifest naming a file that is not here links nothing. Manifest rot surfaces in this repository rather than as a dangling link in someone else's. | [D] |
| FR-7.7 | An unknown set name prints the sets that do exist. A typo deserves the menu, not a traceback. | [D] |
| FR-7.8 | Sets that include one another are refused. A cycle is a manifest error and must not become an infinite walk. | [D] |
| FR-7.9 | Consent is asked for or declared, never assumed. A run with no terminal to ask at refuses rather than proceeding; `--yes` is how a script says it meant to. | [A] |
| FR-7.10 | Running twice changes nothing, and says so rather than relinking what is already correct. | [D] |
| FR-7.11 | `--check` writes nothing and exits 1 on drift, and passes on a project that is set up. It is the form this grows into as a jig task, so the same command must both detect drift and confirm health. | [A] |
| FR-7.12 | Drift is found in both directions: a link pointing at the wrong file is repaired, and a link left behind by a dropped set is reported. A stale link reads as a working path until it is followed. | [D] |
| FR-7.13 | The default is to enumerate, ask, then act — the shape `bolt plan` and `bolt` already have. `--plan` says what would happen and stops. | [A] |
| FR-7.14 | A link whose destination resolves outside the target project is refused, so adoption cannot write through a symlink that leaves the repository. | [D] |

## Non-functional

| ID | Requirement | |
|---|---|---|
| NFR-1 | The test suite runs with none of the tools the jigs name installed. A suite requiring the toolchain could not run in the image `anvil` builds it to populate. | [D] |
| NFR-2 | Tests exercise the scripts in-process, so `coverage run -m pytest` measures them. A suite built on subprocesses reports 0% while testing thoroughly. | [D] |
| NFR-3 | Every script is additionally exercised once as a script, because in-process testing cannot catch a broken shebang, a missing executable bit, or a failure on import. | [D] |
| NFR-4 | Adapter fixtures are captured from real tool output and record the tool version and the date of capture. A fixture composed by hand tests its author's imagination, and a tool changing its output format is precisely the break adapters exist to absorb. | [D] |
| NFR-5 | `[?]` **This repository's own gate passes on this repository.** FACT 2026-08-20: `security` fails on 72 Low findings, 66 of them `assert` in tests. See `NEXT_STEPS.md` item 11. | [?] |
| NFR-6 | `[?]` **The schema has one home.** `schema/jig.schema.json` describes bolt's configuration format, which is bolt's to define, but lives here because this is where jigs live. If bolt ships its own, this one is deleted rather than allowed to drift into a second, disagreeing description. | [?] |
