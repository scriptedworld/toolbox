# The ten recipes, supplied for every project whatever it is written in.
#
# A recipe that does not apply EXISTS AND SUCCEEDS rather than being absent, so
# `just build` never fails for the wrong reason. A language layer overrides
# whichever of these it can really implement, by writing just/lang.just; a
# project overrides further in just/project.just. Both beat this file.
#
# `checks` invokes the others through `just`, which re-enters the import chain,
# so it reaches the language layer's real recipe rather than the no-op below.
# Verified: with a lang.just defining `test`, `just checks` runs that one.

# THREE THINGS EVERY BOLT CALL HERE DOES, AND WHY.
#
# 1. It reads the verdict out of result.yaml and never bolt's exit status.
#    bolt exits 0 whenever it carried a run out, whatever the tools concluded.
#    Measured: a jig with one passing and one failing task printed
#    "success": false into result.yaml and exited 0.
#    silo/docs/LESSONS/read-the-artifact-not-the-exit-status/ is hard rule 6.
#
#    bolt's own --result-to-exitcode does make the status carry the verdict,
#    and is still not used: it collapses a REFUSAL, where no result was
#    written at all, into the same exit 1 as a failed run. Those are different
#    answers and a recipe that cannot tell them apart reports the wrong one.
#
# 2. It takes bolt's default output directory and names no --output-dir at
#    all. A FIXED directory is what is forbidden, because bolt refuses one that
#    already holds a run, so naming one works exactly once. The default is
#    unique per run and `clean` removes them.
#    silo/docs/DECISIONS/a-justfile-gives-every-project-the-same-two-word-interface.md
#
# 3. It quotes the path it read. A verdict with no artifact beside it cannot be
#    checked by whoever reads the output.

# VARIADIC, BECAUSE AN ADOPTER THAT FILLS A PLACEHOLDER HAS TO PASS ITS OWN
# DEFINITIONS AND A RECIPE CANNOT ADD AN ARGUMENT TO ANOTHER RECIPE'S COMMAND.
#
#     just _verdict go-std-quality --definitions go-std-quality
#     just _verdict common-quality --definitions skid
#     just _verdict common-quality --config-dir ..        jigs one level up
#
# WITHOUT IT THE FAILURE DOES NOT LOOK LIKE A MISSING FLAG. The placeholder
# keeps its default and the jig reports a problem in the adopter's own tree:
# qwark's `entrypoint` stayed `true`, so cover-entrypoint.sh never ran and
# main.go read 0.0% against an 80% floor. Skid's `requirements` stayed the
# retired single-file path, so traceability and suppressions both failed.
# Measured on a fixture: with the flag the task passes, without it the same
# task fails, and nothing in either message says "definitions".
#
# So the next adopter would go and change their coverage or requirements
# configuration rather than suspect this file. Found by qwark and skid
# independently, two of two adopters, different languages, same cause.
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

# EVERYTHING. Quality, tests, coverage, secrets and requirements coverage: the
# biggest full gate this tree can run. The other nine exist so a piece can be
# run alone during development; this is what runs before anything lands.
#
# It calls the secrets jig separately because common-quality does not reach it.
# toolbox/jigs.yaml says so in as many words: "Every language set includes this
# one; `secrets` deliberately does not". The decision to fold secrets into
# common-quality is recorded and is not built, so this recipe does it by hand
# and should lose the line when toolbox composes them.

# everything: quality, tests, coverage, secrets
checks:
    @just _verdict common-quality
    @just leak-scan
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

# A CLEAN RECIPE MUST NOT REMOVE ANYTHING ANOTHER PROCESS EXECUTES.
#
# Not "do not delete bin/", and NOT "do not delete anything on PATH". The rule
# is about who RUNS the file, because in this estate a project's build output
# and its deployed artefact are routinely the same file, and the ways a file
# gets reached are not limited to PATH.
#
# `~/bin` IS ITSELF A SYMLINK TO A PROJECT DIRECTORY:
#
#     ~/bin -> ~/.projects/dotfiles/bin
#
# So a clean in dotfiles removing bin/ does not remove one command, it removes
# the entire PATH directory. Five project trees are reachable through it:
# dotfiles, bolt, bolt.go, qwark and toolbox.
#
#     ~/bin/bolt  -> ~/.projects/bolt/bin/bolt      every gate runs through it
#     ~/bin/qwark -> ~/.projects/qwark/bin/qwark    every Bash call runs it
#
# qwark is the sharpest: a PreToolUse hook on every Bash call in every live
# session, so removing it changes what every agent may do rather than degrading
# one program.
#
# BEING REACHABLE IS NOT THE SAME AS BEING ON PATH, and the case that actually
# caused the outage was not on PATH at all:
#
#     ~/.projects/silo/bin/statusline -> ../../infobot/bin/infobot
#     invoked by absolute path from settings.json:36
#
# A check that swept PATH would have missed it. So the question to ask of a
# path before deleting it is not "is it on PATH" but "does anything execute
# this", which includes hooks, service units and configuration.
#
# THIS IS NOT HYPOTHETICAL. infobot's clean carried `rm -f bin/statusline
# bin/forget` under the heading "remove build output". Those were deployed
# artefacts that Claude Code executes on every event in every session, and
# running `just clean` took the whole estate's telemetry down for 25 minutes:
# fifteen status files stopped being written at 20:31:11, and every instrument
# reading them kept printing the last values as current.
#
# WHY IT WILL HAPPEN AGAIN WITHOUT THIS NOTE, in infobot's own words: the next
# person to write a clean recipe from this template will assume build output is
# disposable, because in most projects it is.
#
# So a language layer overriding this removes run directories, coverage output
# and intermediate build trees, and LEAVES the installed artefact alone. `just
# install` is what refreshes that, and it already compares bytes rather than
# timestamps.

# remove run directories and build output
clean:
    rm -rf .bolt-*

# NAMED leak-scan AND NOT secrets, BECAUSE THAT NAME TRIPS ITS OWN SCANNER.
#
# detect-secrets reads a recipe name as a key and the following line as its
# value, so `secrets:` with an ordinary body is reported as a Secret Keyword
# and a project fails its own leak check on the recipe that runs it.
#
# WHAT MAKES THIS WORTH A PARAGRAPH IS THAT TWO SESSIONS MEASURED IT AND BOTH
# GOT THE WRONG ANSWER. Every fixture either of them wrote used just's `@`
# quiet marker, because that is how recipes are written here, and the `@`
# happens to break the pairing:
#
#     secrets:  +  just _verdict secrets    FLAGGED
#     secrets:  +  @just _verdict secrets   clean
#
# So both concluded the name was safe from a fixture that was clean by
# accident. The fixture had inherited the habit of the thing it was testing.
#
# AND THE VERDICT ALSO DEPENDS ON PROSE. This file stays clean with the `@`
# removed, while the same three lines cut out of it flag, because the word
# appears eight times in the comments above. **The check cleared a file whose
# name was genuinely hazardous, and would equally condemn a file that had done
# nothing but lose a comment.** Wrong in both directions, from an edit nobody
# would think to check.
#
# `leak-scan` is clean with no `@`, in isolation, and with a body that itself
# invokes `bolt secrets`. The JIG keeps its name: `bolt.secrets.yaml` is
# toolbox's and is untouched. Only the recipe moved.
#
# silo/docs/DECISIONS/a-justfile-gives-every-project-the-same-two-word-interface.md

# the secrets jig alone
leak-scan:
    @just _verdict secrets
