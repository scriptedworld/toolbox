# toolbox, Requirements

toolbox holds the **jigs** bolt runs, and the **checkers** and **adapters** those
jigs name. *Checker* and *adapter* mean specific and opposite things, and several
requirements below are meaningless if the two are read as synonyms: a checker is
what a task runs and its exit code is the verdict, while an adapter reads the
execution record afterwards and returns the envelope that becomes the verdict.

Each requirement is stated as an observable property, saying what is true of a
run and not how the code is arranged. Mechanism appears only where the
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

*Derives from:* `README.md`, "Adopting a jig".

| ID | Requirement | |
|---|---|---|
| FR-1.1 | A jig is a `bolt.*.yaml` file holding a set of tasks. Jigs compose by overlay: later files win and tasks merge by id, so one jig can adjust an inherited task without restating the whole of it. | [A] |
| FR-1.2 | Every jig here validates against `schema/jig.schema.json`. One that does not is a jig bolt may accept today and reject tomorrow. | [D] |
| FR-1.3 | A jig carries the rule and never the subject. Whatever does the checking travels with the jig; whatever is being checked belongs to the project. Bundle a document *about a codebase* into a jig and it has stopped being adoptable, because every adopter is then judged against its author's answers. | [A] |
| FR-1.4 | `{config_dir}` resolves a path against the directory of the jig that names it; every other path stays relative to the run root. Getting this backwards stays invisible in a repository whose jig sits at its own root, where the two directories are the same one. | [A] |
| FR-1.5 | A shared jig states no project-specific name. `entrypoint` came out of the Go jig for hardcoding `./cmd/bolt`: it looked like a rule and was a subject. | [A] |
| FR-1.6 | A jig does not grade the files it installed. Adoption links this repository's checkers into the adopter's `bin/` and its adapters into `adapters/`, so a tool reading the tree reads them as the adopter's own source. Every task that excludes them names all three exclusion slots, and every slot carries a default and an override, because a placeholder holds one argument and the six tools spell exclusion six ways. | [D] |

## FR-2, Checkers

*Derives from:* `docs/PATTERNS/testing-checkers-and-adapters.md`,
**Two contracts**.

| ID | Requirement | |
|---|---|---|
| FR-2.1 | A checker is what a task runs. Its input is `argv` and the filesystem, and its exit code is the verdict, which is why a checker needs no adapter. | [D] |
| FR-2.2 | A checker written here reports every finding on stdout, naming the file, line or identifier it is about. A finding nobody can locate is a finding nobody acts on. | [D] |
| FR-2.3 | A checker given a document that is absent fails instead of raising. A traceback is not a verdict, and the adopter who has not yet written the document is the reader most in need of an instruction. | [D] |
| FR-2.4 | A checker refuses to pass vacuously. Zero requirements agreeing with zero citations describes a gate with nothing in it, and it must never read as a pass. | [A] |
| FR-2.5 | A checker does not walk trees it is not answerable for: `.venv`, `node_modules`, `vendor`, `testdata`, and `.ephemera`. A vendored suite full of unannotated tests must not fail the project that vendored it, and neither must a scratch file in `.ephemera`. | [D] |

## FR-3, Adapters

*Derives from:* `README.md`, "Checkers and adapters".

| ID | Requirement | |
|---|---|---|
| FR-3.1 | An adapter is a task's `result_command`. Its input is `argv` and an execution **record** on stdin; its output is an **envelope** on stdout. Its own exit code means nothing, because the envelope is the verdict. | [D] |
| FR-3.2 | An adapter exists only where the checker's exit code is not the answer. `gofmt -l` lists unformatted files and exits 0 whichever it finds, so its status answers "did gofmt run" and never "is this formatted". | [A] |
| FR-3.3 | An adapter is pure: no clock, no filesystem, no network. That makes it testable from a fixture record, on a machine where the tool it is about is not installed at all. | [D] |
| FR-3.4 | An adapter emits one reason per finding, naming its `checker` and, where the tool supplies them, the file and line. Where the fix is mechanical, the reason carries the fix. | [D] |
| FR-3.5 | An adapter omits an optional block instead of emitting it empty. `reasons: []` on a pass reads as "checked and found nothing to say", which is a different claim from having nothing to report. | [D] |
| FR-3.6 | An adapter that cannot recognise the output of a checker which also exited non-zero reports a failure it cannot name, never a pass. Silence plus a bad exit code is not success. | [D] |
| FR-3.7 | `[?]` **Every adapter emits `statistics` on pass as well as on fail.** A number is only useful as a series, and a task that reports nothing when it passes can show no trend. True of the three coverage adapters, `adapters/{go,python,rust}/coverage.py`, which report their totals on a pass and not only on a failure; `gofmt.py` and `govet.py` still do not. `lizard.py`, the earlier exemplar, was deleted along with the `complexity` task it read for. Both remaining exceptions are the stdin-contract adapters wired to no task, so neither can report anything today either way. | [?] |

## FR-4, Traceability

*Derives from:* my decision to make this a gate; `README.md`, "Traceability is a gate, not a report".

| ID | Requirement | |
|---|---|---|
| FR-4.1 | Every test states which requirement it discharges and by which path, written as `COVERS: <ids> | <kind>` in the comment block directly above it. | [A] |
| FR-4.2 | A test citing a requirement the document does not declare fails, so a renamed or deleted requirement is caught instead of left rotting in a comment. | [D] |
| FR-4.3 | A `COVERS` line naming a kind outside the declared set fails. The kind states which path through the requirement that test walks. | [D] |
| FR-4.4 | A `COVERS` line citing no requirement id at all fails. It parses as an annotation while discharging nothing. | [D] |
| FR-4.5 | A requirement no test cites fails, unless its row marks it open. Closed 2026-08-20; before that it was reported as context and the task exited 0, which left the document holding the code to nothing. | [A] |
| FR-4.6 | Open is `[?]` in the row's last bracketed cell and nothing else. `[A]`, `[D]`, `[A/D]` and no marker column at all are settled, so a document without markers claims no exemptions: exemption is claimed, never granted by omission. | [A] |
| FR-4.7 | Test discovery reads every language this repository ships a jig for. A language with a jig and no entry in the checker's language table finds no tests, cites nothing, and fails every requirement in one go. | [A] |
| FR-4.8 | Discovery finds a test wherever the language puts one: indented inside a class, declared `async`, or separated from its annotation by a decorator, an attribute, or a doc comment. | [D] |
| FR-4.9 | Requirement ids sort numerically and tolerate a letter suffix, so `FR-7.3` precedes `FR-7.10`, and `FR-4.13a` compares against `FR-4.13` instead of raising. | [D] |
| FR-4.10 | A `## Retired` section records requirements that have gone and what replaced them. Rows there are not live: nothing holds them to coverage, and a test citing one fails saying where it went, not that it does not exist. | [D] |
| FR-4.11 | A requirement id that is both live and retired fails outright, before anything else is reported. Reuse silently rewrites what every existing reference to that id meant, and nothing about the new row looks wrong, so it is the one thing that cannot be left to a reader to notice. | [D] |
| FR-4.12 | `--requirements` accepts a directory as well as a file, reading every `.md` beneath it, `README.md` included. A requirement written in an unexpected file fails loudly for having no test instead of being skipped for its filename, and the cost is that a preamble carries no parseable row. | [D] |
| FR-4.13 | A requirement id declared in more than one file fails. One file per requirement makes that possible in a way a single document never did: two files each declaring the id merge into one entry with the later silently winning, and both read correctly opened alone. | [D] |
| FR-4.14 | A `## Retired` heading's reach ends at the end of its own file. Concatenating a tree would let a document ending inside a retired section silently retire the rows of every file after it. | [D] |
| FR-4.15 | A requirements path that exists and cannot be read reports which path and why, and exits 1. A traceback reads as a broken checker, when the cause is a permission the adopter can fix. | [D] |
| FR-4.16 | Where a language marks a test with an attribute and not in its name, a declaration without that attribute is not a test. Rust names a test function freely and says `#[test]` above it, so without this every helper in a test file reads as a test that cites nothing, and a language gains dozens of failures by being supported. | [D] |
| FR-4.17 | A document whose name ends `.retired`, `.retired.md`, `.superseded` or `.superseded.md` has retired everything in it, whatever it contains. A name has no switch and no below-this-line, so retiring a requirement and appending one are different gestures, not the same gesture in different positions, which is what the `## Retired` heading cannot offer. The suffix records whether the id was replaced or simply dropped; nothing downstream distinguishes them, because either way the id must stay held. | [D] |
| FR-4.18 | `.retired` and `.superseded` are read alongside `.md`. A retired document the checker cannot see holds no id, so declaring that id again passes and every existing reference to it silently means something else, which is the failure the never-reuse rule exists to prevent. | [D] |
| FR-4.19 | A directory holding `requirement.md` is one requirement, and only that note declares anything. What sits beside it is supporting material: repro evidence, captured output, whatever must travel with the row. Read as a requirements document, an evidence write-up containing a table would declare a phantom requirement no test can cover and no author believes they wrote. The name is fixed and does not follow the directory stem, so retiring is a single directory rename with nothing inside to touch. A directory without the note keeps reading every `.md` beneath it. **The requirements root is never such a directory**, being the tree and not a requirement in it: a note written one level too high would otherwise make every document beneath it supporting material, so the ids vanish and the run passes. A note there is read as the ordinary document it appears to be. | [D] |
| FR-4.21 | A requirement directory sitting inside another is reported and fails, naming both. Nothing can tell a genuine nested requirement from a supporting file that happens to carry the note's name, and the sibling rule makes the inner note supporting material either way, so its id is never declared. Silent, a test citing that id is told the requirement does not exist and the obvious remedy is to delete a real test's coverage of a requirement sitting on disk. | [D] |
| FR-4.22 | A diagnostic naming where a requirement should be defined names the `--requirements` path it was given. `REQUIREMENTS.md` is a file that does not exist in a repository holding a tree, so the message whose whole job is to say where to add the row sent a reader looking for a document nobody has. | [D] |
| FR-4.20 | A directory whose name carries a retirement suffix has retired everything beneath it, the note and its supporting material together. The search for such a directory stops at the requirements root: walking to the filesystem root would let a tree archived as `holder.retired/`, or any checkout beneath one, read as retired entire, holding nothing to coverage and passing. | [D] |
| FR-4.24 | The tree to read may be named with `--dir PATH` as well as given positionally, so a scoped run says which rows and which tree separately instead of repeating one word: `--scope go --dir ./go`. Giving both is a usage error, not a precedence, because a caller who wrote two directories meant one of them and choosing for them reads the tree they did not mean. The positional stays: this checker is symlinked into several repositories and their jigs pass it today. | [D] |
| FR-4.23 | `--scope NAME` holds one tree to the rows that name it and to the rows that name no tree, so a repository with several trees against one document holds each to its own coverage and not to the union of all of them. Without it a row covered in one tree alone passes the whole repository, and a tree holding none of a requirement is invisible. The scope clause is the lowercase half of a row's marker, `[A/D python]`; a row also scoping KINDS, `[A go,python:edge,negative]`, stays in scope everywhere, because the rest of that row is still expected in every tree and this checker never asks by which kind. A scoped-out row is exempt exactly as an open one is: out of the denominator, reported as context, never a failure, and still declared so a test citing it is not told the id does not exist. | [D] |

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

*Derives from:* `README.md`, "Adopting these in a project".

| ID | Requirement | |
|---|---|---|
| FR-6.1 | Everything a jig needs lives either in this repository or in the adopting one. Nothing reaches outside those two. | [A] |
| FR-6.2 | `[?]` **A project composes jigs by short name instead of by repeated `-c` with full paths.** Ordering has to stay explicit, because a directory glob has no order and order is semantics here. Needs a change to bolt. See `NEXT_STEPS.md`, open decisions. | [?] |

## FR-7, Adoption by link

*Derives from:* `bin/link-toolbox.py` and `jigs.yaml`, and the reasoning in their
own headers. A jig names checkers, adapters and tool configuration that live
beside it here, and `{config_dir}` resolves those against the jig's own directory,
so a jig reached through a symlink resolves them back through that same link.
Adoption is therefore a set of symlinks.

| ID | Requirement | |
|---|---|---|
| FR-7.1 | An entry lands at the same relative path in the target that it has here. This is forced and not chosen: a linked jig sits at the target's root, which makes `{config_dir}` the target's root, so `bin/x.py` has to be at `bin/x.py` for the jig to find it. There is no destination to configure and so no mapping to keep in step. | [A] |
| FR-7.2 | A set may include another, and adopting it brings the included set along, because the including jig overlays the included one. A set declaring no includes pulls nothing. | [A] |
| FR-7.3 | The manifest is declared, not derived. Reading `{config_dir}` references out of the jigs would build today's list correctly and be wrong tomorrow: a jig running `ruff check .` or `pylint --recursive=y .` needs whatever configuration those tools read by convention, and names none of it on the command line. | [A] |
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

## FR-9, The wording check

*Derives from:* my decision that the voice gate catches specific wording, and
that every rule in it fails on a single instance; `bin/voice-tells.py`.

| ID | Requirement | |
|---|---|---|
| FR-9.1 | Documentation, comments and commit messages are read against a fixed set of rules, and one instance of any error rule fails the task. Each instance is printed with where it is, its line where it has one, and the rule's name. A tree with no errors passes. | [A] |
| FR-9.2 | Punctuation: an em-dash, and ASCII `--` standing between two words. `--name` and `rm -- -f` are not dashes. | [A] |
| FR-9.3 | The audit trail: a `FACT`, `CLAIM` or `PREFERENCE` badge, a checking or deciding verb followed by a date, a `DECIDED`, `CORRECTED`, `RETESTED` or `SUPERSEDED` marker, strikethrough, and narration of what a document, file or note once said. | [A] |
| FR-9.4 | Who is speaking: `our user` and `the project owner` everywhere, `the owner` when it is followed by a verb of deciding or wanting, since alone it is also a file's owner, and a session or agent narrated as the actor in commit messages only, where sessions are not a project's subject. | [A] |
| FR-9.5 | Stock phrasing: `worth knowing` and its kin, the stock phrases the writing standard names, and a run of three or more ALL-CAPS words. | [A] |
| FR-9.6 | Density: `rather than` more than twice in one document or commit message, bold in more than 30% of a document's paragraphs once it has six, and a commit body over 20 lines. | [A] |
| FR-9.7 | Text a document reports and does not assert is not read: fenced and indented code, block quotes, inline code, and spans in double quotes or in single quotes that stand apart from letters, so a contraction is not a quote. | [A] |
| FR-9.8 | The paths the voice review never sends (FR-8.10) are not read, and neither are symlinks or comment lines carrying a directive. | [A] |
| FR-9.9 | Commits are read only after the start the repository records, the same file the voice review reads. With none recorded, commits are not read and the output says so. A start that is not a commit fails. | [A] |
| FR-9.10 | The check asks no model and no network, so the same tree gives the same verdict on every run. | [D] |
| FR-9.11 | Every rule is an error except excess vocabulary, which is a suggestion. A suggestion is printed and written to the report with its severity and never changes the exit status. | [A] |
| FR-9.12 | Assistant voice: an attribution trailer naming a model or its tool, an assistant opener such as `Certainly!` or `Great question`, and in commit messages a `This commit adds` or `In this change` preamble. | [A] |
| FR-9.13 | An emoji in a comment or a commit message. | [A] |
| FR-9.14 | A hedging opener: `it's worth noting`, `it is important to note` and kin. | [A] |
| FR-9.15 | In comments and docstrings: a line opening on a capitalised edit record (`Added`, `Updated`, `Fixed` and kin) that goes on to say what it was `to` do, and a `This function returns` opener naming the kind of thing in place of saying what it does. | [A] |
| FR-9.16 | Excess vocabulary: the listed words used at least twice and more than three times per 1,000 words of one document, file's comments or commit message. | [A] |
| FR-9.17 | With no files named and no mode given, the staged copies of the files the next commit would carry are read, taken from the index and not from the working tree, so a partly staged file is judged by what is being committed. | [A] |
| FR-9.18 | The other modes are pre-commit's: named files are read and nothing else; `--all-files` reads every file the project holds and the commits after the recorded start; `--from-ref` with `--to-ref` reads the files that differ between the refs and the commit messages between them; `--commit-msg-filename` reads one message, without the comment lines and the scissors block git strips. | [A] |
| FR-9.19 | Exit 0 when no error was found, 1 when one was, and 2 when the command or the repository is wrong: two modes at once, one of the two refs, or a start that is not a commit. | [A] |
| FR-9.20 | A `.pre-commit-hooks.yaml` declares the two hooks: the staged files at the pre-commit stage, and the message at the commit-msg stage. | [A] |
| FR-9.21 | A comment is read wherever it sits on a line, including after code, and a comment marker inside a string is not a comment. | [A] |
| FR-9.22 | Block comments are read whole: `/* */`, Lua `--[[ ]]` and its `--` lines, and Ruby `=begin`/`=end` and its `#` lines. | [A] |
| FR-9.23 | A Python docstring is the first string of a module, class or function, taken from the syntax tree, and comments from the tokenizer. Any other string is not prose. A file that does not parse falls back to a scan and is still read. | [A] |
| FR-9.24 | `.voice-baseline.json` at the repository root names the findings accepted as exceptions, each carrying the file, the rule, the finding's text and the reason it stands. A finding an entry matches does not fail, and is counted as accepted. A project adopts with no baseline, and no command writes entries. | [A] |
| FR-9.25 | An entry carrying no reason fails, and so does a baseline that cannot be read. | [A] |
| FR-9.26 | Under `--all-files` an entry that matches no finding fails as stale. The other modes do not judge staleness, because a file an entry names may not have been among those read. | [A] |

## FR-10, The voice review

*Derives from:* my decision that the model review reports and never gates,
after two reviews of one repository agreed on 30 of 77 findings;
`bin/voice-review.py` and `config/prompts/voice-findings.md`.

| ID | Requirement | |
|---|---|---|
| FR-10.1 | The review reads what the wording check's mode selects, through the wording check itself, and sends every selected text whole: one request per document, per file's comments and per commit message, with nothing sampled or cut. | [A] |
| FR-10.2 | Each request sends the one prompt file unchanged and asks only for the judgment habits it names. A finding naming any other rule is dropped. | [A] |
| FR-10.3 | A finding stands only when its quote starts on the line it names, allowing the quote to run on over the next two lines where a sentence wraps. Every other finding is dropped, and the dropped count is reported. | [A] |
| FR-10.4 | Findings never fail the run: a review exits 0 whatever it found. It exits 2 when the command or the repository is wrong, or the prompt cannot be read. | [A] |
| FR-10.5 | When no model can be reached the review exits 0 and says NOT RUN with the cause, and the report's status is `unreachable`. One unreachable request ends the review. An answer that is not a findings list leaves that text reported as unanswered, and the rest are still reviewed. | [A] |
| FR-10.6 | With `ANTHROPIC_API_KEY` set the Messages API is asked with no sampling parameter; without it, `claude -p` is asked only where the fallback is `cli`. | [A] |
| FR-10.7 | `--report` writes the status, the model and backend, every standing finding, the dropped count and the unanswered texts as JSON. | [A] |

## Non-functional

| ID | Requirement | |
|---|---|---|
| NFR-1 | The test suite runs with none of the tools the jigs name installed. A suite needing the toolchain could not run inside the image `anvil` builds it to populate. | [D] |
| NFR-2 | Every script here is measured by the suite that tests it, however the test reaches it. A spawned script is invisible to the parent's coverage, and a suite built on subprocesses reported 0% while testing thoroughly (`adapters/go/coverage.py` read 0 of 96 lines with a full suite behind it), which once forced tests to run in-process. `tests/conftest.py`'s `script_argv` removes that trade: it spawns the child under `coverage run --parallel-mode` when the parent is under coverage, and the jig's `tests` task combines before reporting. So a test may spawn, which it should where the shebang, the imports, or where `main()` writes are part of what is being checked, and the number still moves. | [D] |
| NFR-3 | Every script is also exercised once as a script, because in-process testing catches neither a broken shebang, nor a missing executable bit, nor a failure on import. | [D] |
| NFR-4 | Adapter fixtures are captured from real tool output, and each records the tool version and the date of capture. A fixture composed by hand tests whoever composed it, and a tool changing its output format is the break adapters exist to absorb. | [D] |
| NFR-5 | `[?]` **This repository's own gate passes on this repository.** It does not yet: `security` fails on 117 Low findings, 108 of them `assert` in tests. See `NEXT_STEPS.md` item 11. | [?] |
| NFR-6 | The schema has one home, and it is wrench. A jig schema describes bolt's configuration format, which is not toolbox's to define. wrench ships the schemas and bolt is built from them, so this repository keeps no copy and imports the pack instead. The local `schema/` directory was deleted, not resynced. | [A] |

## Retired

An ID here is never reused. A reader meeting one in an old commit or another
document finds where it went.

| ID | Retired | Was | Where it went |
|---|---|---|---|
| FR-8.1 | 2026-09-16 | a model scores each category from 0 to 100 against one rubric | FR-10.2: findings against one prompt, no score |
| FR-8.2 | 2026-09-16 | a category's score is the median of three runs | nothing: there is no score to take a median of |
| FR-8.3 | 2026-09-16 | a median below a category's floor fails | FR-10.4: findings never fail; FR-9.1 is the gate |
| FR-8.4 | 2026-09-16 | categories are judged and gated separately | FR-10.1: each text is its own request |
| FR-8.5 | 2026-09-16 | commits are judged only after the recorded start | FR-9.18, which the review reads through |
| FR-8.6 | 2026-09-16 | an unreachable model skips the review and passes | FR-10.5: reported as NOT RUN |
| FR-8.7 | 2026-09-16 | the API is asked at temperature 0 | FR-10.6: no sampling parameter is sent |
| FR-8.8 | 2026-09-16 | a request a person must fix fails the review | FR-10.4 and FR-10.5 |
| FR-8.9 | 2026-09-16 | material is sampled up to a byte cap | FR-10.1: every text is sent whole |
| FR-8.10 | 2026-09-16 | exempt paths, links and directives are never sent | FR-9.8, which the review reads through |
| FR-8.11 | 2026-09-16 | the adapter carries the verdict and scores into the envelope | nothing: the adapter is deleted with the task |
