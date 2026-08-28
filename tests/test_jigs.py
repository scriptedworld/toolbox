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

# `bolt.<name>.definitions.yaml` matches the same glob and is not a jig. It
# supplies values for a jig's placeholders and validates against a different
# schema, so a glob that swallows it fails every run here. The same shape of
# mistake is why qwark names its adoption entries one at a time.
JIGS = sorted(
    path
    for path in ROOT.glob("bolt.*.yaml")
    if not path.name.endswith(".definitions.yaml")
)

DEFINITIONS = sorted(ROOT.glob("bolt.*.definitions.yaml"))

SCHEMA_DIR = ROOT / "schema"
SCHEMA = SCHEMA_DIR / "jig.schema.json"

# Wrench's schemas, which are the source bolt is built from. This repository
# keeps a copy so its own tests need nothing outside the tree, and the copy is
# only worth having while it agrees with the original.
#
# THIS IS THE SOURCE AND NOT WHAT ANY BINARY ENFORCES. Bolt embeds these at
# build time, so a binary enforces whatever wrench said when it was last built.
# Measured: `allow-empty` is in the binary built at 20:11 and absent from the
# one built at 13:11, seven hours after the field existed. Agreeing with this
# source is therefore necessary and not sufficient, and a jig using a field
# younger than an adopter's binary is accepted and silently ignored, because the
# schema does not refuse unknown keys.
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
    """Every SHELL LINE a jig declares, paired with the task name.

    `adapter` is deliberately not one. It names an adapter rather than invoking
    it, and bolt resolves that name against the config directory itself, so a
    `{config_dir}/` prefix there would resolve twice and the adapter would not
    be found. `adapter-command` is a shell line and is included.
    """
    found = []
    for task in jig.get("tasks") or []:
        for key in ("command", "adapter-command"):
            if task.get(key):
                found.append((task["name"], task[key]))
    return found


def adapters(jig: dict) -> list[tuple[str, str]]:
    """Every adapter a jig names, paired with the task name."""
    return [
        (task["name"], task["adapter"])
        for task in jig.get("tasks") or []
        if task.get("adapter")
    ]


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
def test_the_local_schemas_still_match_wrenchs_source():
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


# COVERS: FR-1.4 | regression
def test_an_adapter_is_named_and_not_config_dir_prefixed():
    """bolt resolves an adapter's name against the config directory itself.

    `adapter: adapters/go/coverage.py` is the correct form. Writing
    `{config_dir}/adapters/...` resolves twice and bolt reports the adapter as
    not being in the config directory. The path rule still holds; it is
    satisfied by the resolution rather than by the spelling, which is why this
    is pinned rather than left to be rediscovered by whoever `test_every_path`
    sends looking.
    """
    for path in JIGS:
        jig = yaml.safe_load(path.read_text(encoding="utf-8"))
        for task, adapter in adapters(jig):
            assert "{config_dir}" not in adapter, (
                f"{path.name}:{task} prefixes its adapter with {{config_dir}}, "
                f"which resolves twice: {adapter!r}"
            )
            assert not adapter.startswith("/"), (
                f"{path.name}:{task} names an absolute adapter path: {adapter!r}"
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


# ---- what is excluded, and in six spellings ---------------------------------


SLOTS = ("excluded_one", "excluded_two", "excluded_three")


def excluding_tasks(jig: dict) -> list[tuple[str, str]]:
    """Every task whose command names an exclusion slot."""
    return [
        (task, command)
        for task, command in commands(jig)
        if any(f"{{{slot}}}" in command for slot in SLOTS)
    ]


# COVERS: FR-1.6 | property
def test_a_task_that_excludes_anything_names_every_slot():
    """Six tools spell exclusion six ways, and three of the obvious forms are
    accepted while excluding nothing.

    A placeholder cannot hold more than one argument, because bolt quotes each
    substitution as a single shell word, so each command composes the slots
    itself. Naming two of three is how a directory quietly stops being
    excluded in one tool and not the others.
    """
    for path in JIGS:
        jig = yaml.safe_load(path.read_text(encoding="utf-8"))
        for task, command in excluding_tasks(jig):
            missing = [slot for slot in SLOTS if f"{{{slot}}}" not in command]
            assert not missing, (
                f"{path.name}:{task} excludes but does not name {missing}: {command!r}"
            )


# COVERS: FR-1.6 | regression
def test_a_python_task_that_excludes_anything_keeps_a_virtualenv_out():
    """An adopter's `.venv` is thousands of files nobody here wrote.

    Measured 2026-08-28 against a violation planted in a fake `.venv`: five of
    the eight tasks read it. `analyse` does not fail on it, it HANGS, because
    skid's virtualenv holds 11,795 files and the task was killed at 900s having
    produced nothing.

    TWO SPELLINGS SATISFY THIS AND THEY ARE NOT INTERCHANGEABLE. Naming
    `.venv` works for a tool with no opinion of its own. `--extend-exclude` is
    for ruff, whose `--exclude` REPLACES a built-in default list that already
    held `.venv`, so scoping the task with the obvious flag silently un-excluded
    what ruff was already excluding. A future edit swapping one spelling for the
    other reintroduces the defect in whichever direction it moves, which is why
    this asserts on the command rather than on a run.
    """
    for path in JIGS:
        if "python" not in path.name:
            continue
        jig = yaml.safe_load(path.read_text(encoding="utf-8"))
        for task, command in excluding_tasks(jig):
            covered = ".venv" in command or "--extend-exclude" in command
            assert covered, (
                f"{path.name}:{task} excludes directories but would still walk "
                f"a virtualenv; name .venv or use --extend-exclude: {command!r}"
            )


# COVERS: FR-1.6 | property
def test_every_slot_a_jig_uses_has_a_default_and_an_override():
    """A slot with no default fails only in the adopter that first runs it.

    The override matters as much: this repository holds the real checkers
    where every other adopter holds links to them, so a missing entry there
    would silently stop it gating its own code.
    """
    overrides = {
        path.name: yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for path in DEFINITIONS
    }
    assert overrides, "no definitions file found; the override is untested"

    for path in JIGS:
        jig = yaml.safe_load(path.read_text(encoding="utf-8"))
        used = {
            slot
            for _, command in commands(jig)
            for slot in (*SLOTS, "excluded_regex")
            if f"{{{slot}}}" in command
        }
        declared = jig.get("definitions") or {}
        for slot in sorted(used):
            assert slot in declared, f"{path.name} uses {slot} and defines no default"
            for name, override in overrides.items():
                assert slot in override, f"{name} does not override {slot}"
