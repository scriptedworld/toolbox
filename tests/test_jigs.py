"""Tests for the jigs themselves, rather than for the scripts they name.

A jig is a document, so these are document tests: they hold every
`bolt.*.yaml` in this repository against the schema it claims to satisfy and
against the path rule that decides whether it is adoptable at all.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import referencing
import yaml
from conftest import ROOT

JIGS = sorted(ROOT.glob("bolt.*.yaml"))

SCHEMA_DIR = ROOT / "schema"
SCHEMA = SCHEMA_DIR / "jig.schema.json"

# The schemas bolt actually enforces, through wrench. This repository keeps a
# copy so its own tests need nothing outside the tree, and the copy is only
# worth having while it agrees with the original.
ENFORCED_DIR = Path.home() / ".projects" / "wrench" / "schemas"

# A jig schema refers to the definitions schema by its published URI, which
# nothing resolves offline. Registering each local file under its own $id is
# what lets the reference resolve without a network call.
SCHEMAS = ("jig.schema.json", "definitions.schema.json")


def registry() -> referencing.Registry:
    """Every local schema, keyed by the $id it publishes itself under."""
    store = referencing.Registry()
    for name in SCHEMAS:
        document = json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))
        resource = referencing.Resource.from_contents(document)
        store = resource @ store
    return store


# Directories that belong to this repository. A command reaching one of them is
# reaching for THE RULE, and must say {config_dir} to find it in the adopter's
# checkout rather than in the adopter's own tree.
OURS = ("bin/", "adapters/", "config/", "schema/")


def commands(jig: dict) -> list[tuple[str, str]]:
    """Every command line a jig declares, paired with the task name."""
    found = []
    for task in jig.get("tasks") or []:
        for key in ("command", "adapter", "adapter-command"):
            if task.get(key):
                found.append((task["name"], task[key]))
    return found


# COVERS: FR-1.2 | edge
def test_there_are_jigs_to_check():
    """A glob matching nothing would make every test below pass vacuously."""
    assert JIGS, "no bolt.*.yaml found; the rest of this file proves nothing"


# COVERS: FR-1.2 | property
def test_every_jig_validates_against_the_schema():
    """A jig that does not validate is one bolt may accept today and reject tomorrow."""
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema, registry=registry())
    for path in JIGS:
        validator.validate(yaml.safe_load(path.read_text(encoding="utf-8")))


# COVERS: FR-1.2 | regression
def test_the_local_schemas_still_match_the_ones_bolt_enforces():
    """Drift here is silent and it hid a dead gate in eight repositories.

    The local copy required `id` and `command` long after wrench's required
    `name`, so every jig validated in this suite while bolt refused the same
    files. A test that checks a document against a copy of the rule nobody
    enforces reports on the copy.
    """
    for name in SCHEMAS:
        enforced = ENFORCED_DIR / name
        if not enforced.exists():
            continue
        assert (SCHEMA_DIR / name).read_text(encoding="utf-8") == enforced.read_text(
            encoding="utf-8"
        ), f"schema/{name} has drifted from {enforced}; sync it or resolve NFR-6"


# COVERS: FR-1.4 | property
def test_every_path_into_this_repository_is_config_dir_rooted():
    """The rule travels with the jig; only the subject is base-relative.

    This is the mistake that is invisible where it is written: a jig at its own
    repository root has {config_dir} equal to the base, so both spellings
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
                    assert prefix.endswith("{config_dir}/"), (
                        f"{path.name}:{task} reaches {directory} without {{config_dir}}: {command!r}"
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
