# toolbox, Requirements

toolbox holds the **jigs** bolt runs, and the **checkers** and **adapters** those
jigs name. Read `silo/docs/GLOSSARY.md` before this document: *checker* and
*adapter* mean specific and opposite things, and several requirements below are
meaningless if the two are read as synonyms.

Each requirement is stated as an observable property, saying what is true of a
run rather than how the code is arranged. Mechanism appears only where the
mechanism is itself the requirement.

The chain is followed in both directions. A requirement says what must be true; a
test says `COVERS:` and names the requirement it discharges. The `traceability`
task in this repository's own `bolt.common-quality.yaml` enforces that link
mechanically.

**Status markers.** `[A]` traces the requirement to something I stated. `[D]`
is derived reasoning, to be accepted or rejected on its merits. `[?]` is an open
decision, recorded so it is not lost, and it has to be resolved before the
requirement it marks is testable.

---

## FR-1, What a jig is

*Derives from:* `silo/docs/GLOSSARY.md`, **The file**; `README.md`, **Using them**.

| ID | Requirement | |
|---|---|---|
| FR-1.1 | A jig is a `bolt.*.yaml` file holding a set of tasks. Jigs compose by overlay: later files win and tasks merge by id, so one jig can adjust an inherited task without restating the whole of it. | [A] |
| FR-1.2 | Every jig here validates against `schema/jig.schema.json`. One that does not is a jig bolt may accept today and reject tomorrow. | [D] |
| FR-1.3 | A jig carries **the rule and never the subject**. Whatever does the checking travels with the jig; whatever is being checked belongs to the project. Bundle a document *about a codebase* into a jig and it has stopped being adoptable, because every adopter is then judged against its author's answers. | [A] |
| FR-1.4 | `{config_dir}` resolves a path against the directory of the jig that names it; every other path stays relative to the run root. Getting this backwards stays invisible in a repository whose jig sits at its own root, where the two directories are the same one. | [A] |
| FR-1.5 | A shared jig states no project-specific name. `entrypoint` came out of the Go jig for hardcoding `./cmd/bolt`: it looked like a rule and was a subject. | [A] |
| FR-1.6 | A jig does not grade the files it installed. Adoption links this repository's checkers into the adopter's `bin/` and its adapters into `adapters/`, so a tool reading the tree reads them as the adopter's own source. Every task that excludes them names all three exclusion slots, and every slot carries a default and an override, because a placeholder holds one argument and the six tools spell exclusion six ways. | [D] |

## FR-2, Checkers

*Derives from:* `silo/docs/GLOSSARY.md`, **Inside a jig**;
`docs/PATTERNS/testing-checkers-and-adapters.md`, **Two contracts**.

| ID | Requirement | |
|---|---|---|
| FR-2.1 | A checker is what a task runs. Its input is `argv` and the filesystem, and **its exit code is the verdict**, which is why a checker needs no adapter. | [D] |
| FR-2.2 | A checker written here reports every finding on stdout, naming the file, line or identifier it is about. A finding nobody can locate is a finding nobody acts on. | [D] |
| FR-2.3 | A checker given a document that is absent fails instead of raising. A traceback is not a verdict, and the adopter who has not yet written the document is the reader most in need of an instruction. | [D] |
| FR-2.4 | A checker refuses to pass vacuously. Zero requirements agreeing with zero citations describes a gate with nothing in it, and it must never read as a pass. | [A] |
| FR-2.5 | A checker does not walk trees it is not answerable for: `.venv`, `node_modules`, `vendor`, `testdata`, and `.ephemera`. A vendored suite full of unannotated tests must not fail the project that vendored it, and neither must a scratch file in the session's own working directory. | [D] |

## FR-3, Adapters

*Derives from:* `README.md`, **Checkers and adapters**;
`silo/docs/GLOSSARY.md`, **What a run produces**.

| ID | Requirement | |
|---|---|---|
| FR-3.1 | An adapter is a task's `result_command`. Its input is `argv` and an execution **record** on stdin; its output is an **envelope** on stdout. Its own exit code means nothing, because the envelope is the verdict. | [D] |
| FR-3.2 | An adapter exists only where the checker's exit code is not the answer. `gofmt -l` lists unformatted files and exits 0 whichever it finds, so its status answers "did gofmt run" and never "is this formatted". | [A] |
| FR-3.3 | An adapter is pure: no clock, no filesystem, no network. That makes it testable from a fixture record, on a machine where the tool it is about is not installed at all. | [D] |
| FR-3.4 | An adapter emits one reason per finding, naming its `checker` and, where the tool supplies them, the file and line. Where the fix is mechanical, the reason carries the fix. | [D] |
| FR-3.5 | An adapter omits an optional block instead of emitting it empty. `reasons: []` on a pass reads as "checked and found nothing to say", which is a different claim from having nothing to report. | [D] |
| FR-3.6 | An adapter that cannot recognise the output of a checker which also exited non-zero reports a failure it cannot name, never a pass. Silence plus a bad exit code is not success. | [D] |
| FR-3.7 | `[?]` **Every adapter emits `statistics` on pass as well as on fail.** A number is only useful as a series, and a task that reports nothing when it passes can show no trend. True of `lizard.py` alone so far, and the Python jig has no adapters at all. See `NEXT_STEPS.md` item 1. | [?] |

## FR-4, Traceability

*Derives from:* my decision to make this a gate; `README.md`, **Traceability is a gate, not a report**.

| ID | Requirement | |
|---|---|---|
| FR-4.1 | Every test states which requirement it discharges and by which path, written as `COVERS: <ids> | <kind>` in the comment block directly above it. | [A] |
| FR-4.2 | A test citing a requirement the document does not declare fails, so a renamed or deleted requirement is caught instead of left rotting in a comment. | [D] |
| FR-4.3 | A `COVERS` line naming a kind outside the declared set fails. The kind states which path through the requirement that test walks. | [D] |
| FR-4.4 | A `COVERS` line citing no requirement id at all fails. It parses as an annotation while discharging nothing. | [D] |
| FR-4.5 | A requirement no test cites **fails**, unless its row marks it open. Closed 2026-08-20; before that it was reported as context and the task exited 0, which left the document holding the code to nothing. | [A] |
| FR-4.6 | Open is `[?]` in the row's last bracketed cell and nothing else. `[A]`, `[D]`, `[A/D]` and **no marker column at all** are settled, so a document without markers claims no exemptions: exemption is claimed, never granted by omission. | [A] |
| FR-4.7 | Test discovery reads every language this repository ships a jig for. A language with a jig and no entry in the checker's language table finds no tests, cites nothing, and fails every requirement in one go. | [A] |
| FR-4.8 | Discovery finds a test wherever the language puts one: indented inside a class, declared `async`, or separated from its annotation by a decorator, an attribute, or a doc comment. | [D] |
| FR-4.9 | Requirement ids sort numerically and tolerate a letter suffix, so `FR-7.3` precedes `FR-7.10`, and `FR-4.13a` compares against `FR-4.13` instead of raising. | [D] |
| FR-4.10 | A `## Retired` section records requirements that have gone and what replaced them. Rows there are not live: nothing holds them to coverage, and a test citing one fails saying where it went rather than saying it does not exist. | [D] |
| FR-4.11 | A requirement id that is both live and retired fails outright, before anything else is reported. Reuse silently rewrites what every existing reference to that id meant, and nothing about the new row looks wrong, so it is the one thing that cannot be left to a reader to notice. | [D] |
| FR-4.12 | `--requirements` accepts a directory as well as a file, reading every `.md` beneath it, `README.md` included. A requirement written in an unexpected file fails loudly for having no test rather than being skipped for its filename, and the cost is that a preamble carries no parseable row. | [D] |
| FR-4.13 | A requirement id declared in more than one file fails. One file per requirement makes that possible in a way a single document never did: two files each declaring the id merge into one entry with the later silently winning, and both read correctly opened alone. | [D] |
| FR-4.14 | A `## Retired` heading's reach ends at the end of its own file. Concatenating a tree would let a document ending inside a retired section silently retire the rows of every file after it. | [D] |
| FR-4.15 | A requirements path that exists and cannot be read reports which path and why, and exits 1. A traceback reads as a broken checker rather than as a permission the adopter can fix. | [D] |
| FR-4.16 | Where a language marks a test with an attribute rather than in its name, a declaration without that attribute is not a test. Rust names a test function freely and says `#[test]` above it, so without this every helper in a test file reads as a test that cites nothing, and a language gains dozens of failures by being supported. | [D] |
| FR-4.17 | A document whose name ends `.retired` or `.retired.md` has retired everything in it, whatever it contains. A name has no switch and no below-this-line, so retiring a requirement and appending one are different gestures rather than the same gesture in different positions, which is what the `## Retired` heading cannot offer. | [D] |
| FR-4.18 | `.retired` is read alongside `.md`. A retired document the checker cannot see holds no id, so declaring that id again passes and every existing reference to it silently means something else, which is the failure the never-reuse rule exists to prevent. | [D] |

## FR-5, The suppression register

*Derives from:* `bolt.common-quality.yaml`, the `suppressions` task; the incident
recorded in `bin/suppression-register.py`.

| ID | Requirement | |
|---|---|---|
| FR-5.1 | Every suppression pragma in the source appears in the register, and every row of the register names a pragma that is really there. Both directions fail. | [A] |
| FR-5.2 | The count is part of the comparison, so a second pragma added to an already-registered file is caught instead of hiding behind the first. | [A] |
| FR-5.3 | A project with no pragmas and no register passes. A project that has pragmas and no register does not. | [A] |
| FR-5.4 | `[?]` **The register covers every language this repository ships a jig for.** It walks `*.go` only and requires gosec or `//nolint` rule ids, so a Python `# nosec` is silenced and unseen instead of silenced and justified: a false green in a gate. Open because fixing it newly fails every adopter carrying an unregistered pragma. See `NEXT_STEPS.md` item 7. | [?] |
| FR-5.5 | `--register` accepts a directory as well as a file, reading every `.md` beneath it. Counts add across documents, so one file per suppression totals what one document listing them all totals. | [D] |

## FR-6, Adoption

*Derives from:* `README.md`, **Adopting these in a project**.

| ID | Requirement | |
|---|---|---|
| FR-6.1 | Everything a jig needs lives either in this repository or in the adopting one. Nothing reaches outside those two. | [A] |
| FR-6.2 | `[?]` **A project composes jigs by short name instead of by repeated `-c` with full paths.** Ordering has to stay explicit, because a directory glob has no order and order is semantics here. Needs a change to bolt. See `NEXT_STEPS.md`, open decisions. | [?] |

## FR-7, Adoption by link

*Derives from:* `bin/link-jigs.py` and `jigs.yaml`, and the reasoning in their
own headers. A jig names checkers, adapters and tool configuration that live
beside it here, and `{config_dir}` resolves those against the jig's own directory,
so a jig reached through a symlink resolves them back through that same link.
Adoption is therefore a set of symlinks.

| ID | Requirement | |
|---|---|---|
| FR-7.1 | An entry lands at the same relative path in the target that it has here. This is forced and not chosen: a linked jig sits at the target's root, which makes `{config_dir}` the target's root, so `bin/x.py` has to be at `bin/x.py` for the jig to find it. There is no destination to configure and so no mapping to keep in step. | [A] |
| FR-7.2 | A set may include another, and adopting it brings the included set along, because the including jig overlays the included one. A set declaring no includes pulls nothing. | [A] |
| FR-7.3 | The manifest is **declared, not derived**. Reading `{config_dir}` references out of the jigs would build today's list correctly and be wrong tomorrow: a jig running `ruff check .` or `pylint --recursive=y .` needs whatever configuration those tools read by convention, and names none of it on the command line. | [A] |
| FR-7.4 | Links are relative by default, so the pair can move together; an absolute link encodes one machine's layout. Absolute stays available for a toolbox that sits at a fixed path and never travels. | [D] |
| FR-7.5 | **Nothing is ever overwritten.** A real file sitting where a link belongs is reported and left alone: it is usually a vendored copy predating adoption, and deleting someone's file is their decision to make. | [A] |
| FR-7.6 | A manifest naming a file that is not here links nothing. Manifest rot surfaces in this repository instead of as a dangling link in someone else's. | [D] |
| FR-7.7 | An unknown set name prints the sets that do exist. A typo earns the menu, never a traceback. | [D] |
| FR-7.8 | Sets that include one another are refused. A cycle is a manifest error, and it must not turn into an infinite walk. | [D] |
| FR-7.9 | Consent is asked for or declared, never assumed. A run with no terminal to ask at refuses instead of proceeding, and `--yes` is how a script says it meant to. | [A] |
| FR-7.10 | Running twice changes nothing, and says so instead of relinking what is already correct. | [D] |
| FR-7.11 | `--check` writes nothing, exits 1 on drift, and passes on a project that is set up. It is the form this grows into as a jig task, so one command has to both detect drift and confirm health. | [A] |
| FR-7.12 | Drift is found in both directions: a link pointing at the wrong file is repaired, and a link left behind by a dropped set is reported. A stale link reads as a working path right up until it is followed. | [D] |
| FR-7.13 | The default is to enumerate, ask, then act, which is the shape `bolt plan` and `bolt` already have. `--plan` says what would happen and stops. | [A] |
| FR-7.14 | A link whose destination resolves outside the target project is refused. Adoption cannot write through a symlink that leaves the repository. | [D] |

## Non-functional

| ID | Requirement | |
|---|---|---|
| NFR-1 | The test suite runs with none of the tools the jigs name installed. A suite needing the toolchain could not run inside the image `anvil` builds it to populate. | [D] |
| NFR-2 | Tests exercise the scripts in-process, so `coverage run -m pytest` measures them. A suite built on subprocesses reports 0% while testing the scripts thoroughly. | [D] |
| NFR-3 | Every script is also exercised once as a script, because in-process testing catches neither a broken shebang, nor a missing executable bit, nor a failure on import. | [D] |
| NFR-4 | Adapter fixtures are captured from real tool output, and each records the tool version and the date of capture. A fixture composed by hand tests whoever composed it, and a tool changing its output format is the break adapters exist to absorb. | [D] |
| NFR-5 | `[?]` **This repository's own gate passes on this repository.** It does not yet: `security` fails on 117 Low findings, 108 of them `assert` in tests. See `NEXT_STEPS.md` item 11. | [?] |
| NFR-6 | `[?]` **The schema has one home.** `schema/jig.schema.json` describes bolt's configuration format, which is bolt's to define, and it lives here only because this is where jigs live. If bolt ships its own, this one is deleted rather than left to drift into a second, disagreeing description. | [?] |
