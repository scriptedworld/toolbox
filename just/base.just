# The ten recipes, supplied for every project whatever it is written in.
#
# A recipe that does not apply exists and succeeds instead of being absent, so
# `just build` never fails for the wrong reason. A language layer overrides
# whichever of these it can really implement, by writing just/lang.just; a
# project overrides further in just/project.just. Both beat this file.
#
# `checks` invokes the others through `just`, which re-enters the import chain,
# so it reaches the language layer's real recipe and not the no-op below. With
# a lang.just defining `test`, `just checks` runs that one.

# Three things every bolt call here does, and why.
#
# 1. It reads the verdict out of result.yaml and never bolt's exit status.
#    bolt exits 0 whenever it carried a run out, whatever the tools concluded:
#    a jig with one passing and one failing task writes "success": false into
#    result.yaml and exits 0. Reading the artifact and not the exit status is
#    a standing rule here.
#
#    bolt's own --result-to-exitcode does make the status carry the verdict,
#    and is still not used: it collapses a refusal, where no result was
#    written at all, into the same exit 1 as a failed run. Those are different
#    answers and a recipe that cannot tell them apart reports the wrong one.
#
# 2. It takes bolt's default output directory and names no --output-dir at
#    all. A fixed directory is what is forbidden, because bolt refuses one that
#    already holds a run, so naming one works exactly once. The default is
#    unique per run and `clean` removes them.
#    Every project answering to the same two words is a settled decision.
#
# 3. It quotes the path it read. A verdict with no artifact beside it cannot be
#    checked by whoever reads the output.

# Variadic, because an adopter that fills a placeholder has to pass its own
# definitions, and a recipe cannot add an argument to another recipe's command.
#
#     just _verdict go-std-quality --definitions go-std-quality
#     just _verdict common-quality --definitions skid
#     just _verdict common-quality --config-dir ..        jigs one level up
#
# Without the flag, the failure does not look like a missing flag. The
# placeholder keeps its default and the jig reports a problem in the adopter's
# own tree: qwark's `entrypoint` stayed `true`, so cover-entrypoint.sh never ran
# and main.go read 0.0% against an 80% floor. Skid's `requirements` stayed the
# retired single-file path, so traceability and suppressions both failed. On a
# fixture, the task passes with the flag and fails without it, and nothing in
# either message says "definitions".
#
# So an adopter hitting this goes and changes their coverage or requirements
# configuration instead of suspecting this file. qwark and skid both hit it,
# in different languages, from the same cause.
_verdict jig *flags:
    #!/usr/bin/env bash
    set -euo pipefail
    out=$(bolt {{ flags }} "{{ jig }}" .)
    result=$(printf '%s\n' "$out" | tail -1)
    if [ ! -f "$result" ]; then
        echo "REFUSED: bolt wrote no result for {{ jig }}" >&2
        printf '%s\n' "$out" >&2
        exit 1
    fi
    if grep -q '"success": *true' "$result"; then
        echo "pass  {{ jig }}  $result"
    else
        echo "FAIL  {{ jig }}  $result" >&2
        exit 1
    fi

# Everything. Quality, tests, coverage, secrets and requirements coverage: the
# biggest full gate this tree can run. The other nine exist so a piece can be
# run alone during development; this is what runs before anything lands.
#
# The secrets scan arrives through common-quality, which composes it as a child
# so `bolt.secrets.yaml` stays the one definition of what a scan is. Do not add
# `leak-scan` here: it would run the same jig a second time.

# everything: quality, tests, coverage, secrets
checks:
    @just _verdict common-quality
    @just test
    @just coverage

# the suite
test:
    @echo "test: no language layer applied"

# the suite with coverage, and the minimum enforced
coverage:
    @echo "coverage: no language layer applied"

# formatting verified, nothing written
format-check:
    @echo "format-check: no language layer applied"

# formatting written
format:
    @echo "format: no language layer applied"

# may be a no-op
build:
    @echo "build: nothing to build"

# whatever this language distributes
dist:
    @echo "dist: nothing to distribute"

# put the built artefact where it is used from
install:
    @echo "install: nothing to install"

# A clean recipe must not remove anything another process executes.
#
# The rule is neither "do not delete bin/" nor "do not delete anything on PATH".
# It is about who runs the file, because in this estate a project's build output
# and its deployed artefact are routinely the same file, and the ways a file
# gets reached are not limited to PATH.
#
# The PATH directory itself can be a symlink into a project tree:
#
#     ~/bin -> <some project>/bin
#
# So a clean in that project removing bin/ removes the entire PATH directory,
# not one command, and every other project reachable through it goes at the
# same time. Two of the commands behind such a link are a build gate and a
# pre-execution hook, and removing the hook changes what every process is
# permitted to do.
#
# Being reachable is not the same as being on PATH. A link in one project
# pointing into another, invoked by absolute path from a configuration file, is
# not on PATH at all, and a check that swept PATH would miss it. So the question
# to ask of a path before deleting it is "does anything execute this", which
# includes hooks, service units and configuration.
#
# infobot's clean once carried `rm -f bin/statusline bin/forget` under the
# heading "remove build output". Those were deployed artefacts that Claude Code
# executes on every event, and running `just clean` stopped fifteen status files
# being written for 25 minutes while every instrument reading them kept printing
# the last values as current. Anyone writing a clean recipe from this template
# will assume build output is disposable, because in most projects it is.
#
# So a language layer overriding this removes run directories, coverage output
# and intermediate build trees, and leaves the installed artefact alone. `just
# install` is what refreshes that, and it already compares bytes, not
# timestamps.

# remove run directories and build output
clean:
    rm -rf .bolt-*

# Named leak-scan and not secrets, because that name trips its own scanner.
#
# detect-secrets reads a recipe name as a key and the following line as its
# value, so `secrets:` with an ordinary body is reported as a Secret Keyword
# and a project fails its own leak check on the recipe that runs it.
#
# A fixture testing this is easy to get wrong. just's `@` quiet marker, which
# is how recipes are written here, happens to break the pairing:
#
#     secrets:  +  just _verdict secrets    FLAGGED
#     secrets:  +  @just _verdict secrets   clean
#
# so a fixture written in the house style reports the name as safe by accident.
#
# The verdict also depends on prose. This file stays clean with the `@`
# removed, while the same three lines cut out of it flag, because the word
# appears eight times in the comments above. The check clears a file whose name
# is genuinely hazardous, and would equally condemn one that had done nothing
# but lose a comment.
#
# `leak-scan` is clean with no `@`, in isolation, and with a body that itself
# invokes `bolt secrets`. The jig keeps its name: `bolt.secrets.yaml` is
# toolbox's and is untouched. Only the recipe is renamed.
#
# Every project answering to the same two words is a settled decision.

# the secrets jig alone
leak-scan:
    @just _verdict secrets
