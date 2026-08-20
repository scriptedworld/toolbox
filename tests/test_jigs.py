"""Tests for the jigs themselves, rather than for the scripts they name.

A jig is a document, so these are document tests: they hold every
`bolt.*.yaml` in this repository against the schema it claims to satisfy and
against the path rule that decides whether it is adoptable at all.
"""

from __future__ import annotations

import json

import jsonschema
import yaml
from conftest import ROOT

JIGS = sorted(ROOT.glob("bolt.*.yaml"))

# Directories that belong to this repository. A command reaching one of them is
# reaching for THE RULE, and must say {configdir} to find it in the adopter's
# checkout rather than in the adopter's own tree.
OURS = ("bin/", "adapters/", "config/", "schema/")


def commands(jig: dict) -> list[tuple[str, str]]:
    """Every command line a jig declares, paired with the task id."""
    found = []
    for task in jig.get("tasks") or []:
        for key in ("command", "result_command"):
            if task.get(key):
                found.append((task["id"], task[key]))
    return found


# COVERS: FR-1.2 | edge
def test_there_are_jigs_to_check():
    """A glob matching nothing would make every test below pass vacuously."""
    assert JIGS, "no bolt.*.yaml found; the rest of this file proves nothing"


# COVERS: FR-1.2 | property
def test_every_jig_validates_against_the_schema():
    """A jig that does not validate is one bolt may accept today and reject tomorrow."""
    schema = json.loads(
        (ROOT / "schema" / "jig.schema.json").read_text(encoding="utf-8")
    )
    for path in JIGS:
        jsonschema.validate(yaml.safe_load(path.read_text(encoding="utf-8")), schema)


# COVERS: FR-1.4 | property
def test_every_path_into_this_repository_is_configdir_rooted():
    """The rule travels with the jig; only the subject is run-root relative.

    This is the mistake that is invisible where it is written: a jig at its own
    repository root has {configdir} equal to the run root, so both spellings
    resolve to the same file and the break only happens for adopters.
    """
    for path in JIGS:
        jig = yaml.safe_load(path.read_text(encoding="utf-8"))
        for task, command in commands(jig):
            for directory in OURS:
                for hit in [
                    i for i in range(len(command)) if command.startswith(directory, i)
                ]:
                    prefix = command[:hit]
                    assert prefix.endswith("{configdir}/"), (
                        f"{path.name}:{task} reaches {directory} without {{configdir}}: {command!r}"
                    )


# COVERS: FR-1.5 | negative
def test_no_jig_names_a_project_specific_entry_point():
    """`entrypoint` hardcoded ./cmd/bolt and failed for every adopter.

    It looked like a rule and was a subject. Nothing shared may name one
    project's main package, its binary, or its module path.
    """
    for path in JIGS:
        jig = yaml.safe_load(path.read_text(encoding="utf-8"))
        for task, command in commands(jig):
            assert "./cmd/" not in command, (
                f"{path.name}:{task} names a specific main package: {command!r}"
            )
            assert "github.com/" not in command, (
                f"{path.name}:{task} names a specific module: {command!r}"
            )
