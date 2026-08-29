"""Tests for the jigs themselves, rather than for the scripts they name.

A jig is a document, so these are document tests: they hold every
`bolt.*.yaml` in this repository against the schema it claims to satisfy and
against the path rule that decides whether it is adoptable at all.
"""

from __future__ import annotations

import wrench
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

# THE SCHEMAS COME FROM WRENCH AND THIS REPOSITORY KEEPS NO COPY.
#
# Decided 2026-08-29, which settles NFR-6. wrench ships them and bolt is built
# from them, so a second copy here could only ever be a description free to
# disagree with the one being enforced. It did disagree, twice: on `allow-empty`
# when wrench added it, and again when wrench renamed it to `optional`. Both
# times the copy was detected by a test rather than by anything failing, and
# both times the fix was to copy the file again.
#
# Importing the pack removes the class of bug rather than the instance. There is
# no longer a local artefact to drift.
#
# THIS IS THE SOURCE AND NOT WHAT ANY BINARY ENFORCES. Bolt embeds these at
# build time, so a binary enforces whatever wrench said when it was last built.
# Measured 2026-08-27: the field was in the bolt built at 20:11 and absent from
# the one built at 13:11, seven hours after it existed. Agreeing with this
# source is therefore necessary and not sufficient, and a jig using a field
# younger than an adopter's binary is accepted and silently ignored, because the
# schema does not refuse unknown keys.
#
# wrench ships a compiled VALIDATOR rather than a document, and it attaches its
# own registry, so a jig schema referencing the definitions schema by `$id`
# resolves without a network call and without this file assembling one. The
# registry helper that used to live here is gone with the copies.
SCHEMA = wrench.JIG_SCHEMA
DEFINITIONS_SCHEMA = wrench.DEFINITIONS_SCHEMA


# Directories that belong to this repository. A command reaching one of them is
# reaching for THE RULE, and must say {config_dir} to find it in the adopter's
# checkout rather than in the adopter's own tree.
#
# `schema/` was here and is gone with the directory, 2026-08-29. NFR-6 is
# settled: wrench ships the schemas and this repository keeps no copy.
OURS = ("bin/", "adapters/", "config/")


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
    for path in JIGS:
        SCHEMA.validate(yaml.safe_load(path.read_text(encoding="utf-8")))


# COVERS: FR-1.2 | property
def test_every_definitions_file_validates_against_its_own_schema():
    """The definitions files were never validated against anything.

    A jig has been held to its schema since the suite existed; the definitions
    files beside it, which supply that jig's placeholder values, were not. They
    have their own schema and wrench ships it, so the omission was that nobody
    reached for it rather than that it was unavailable.

    Noticed 2026-08-29 while removing the local schema copies: the constant was
    imported and used nowhere.
    """
    assert DEFINITIONS, "no bolt.*.definitions.yaml found; this proves nothing"
    for path in DEFINITIONS:
        DEFINITIONS_SCHEMA.validate(yaml.safe_load(path.read_text(encoding="utf-8")))


# COVERS: NFR-6 | regression
def test_the_schema_comes_from_wrench_and_not_from_a_copy():
    """The drift this replaces was silent and hid a dead gate in eight repos.

    A local copy required `id` and `command` long after wrench's required
    `name`, so every jig validated in this suite while bolt refused the same
    files. A test that checks a document against a copy of the rule nobody
    enforces reports on the copy.

    The copy is gone rather than resynced, which settles NFR-6. This asserts
    the property that replaced it: the schema being validated against is the
    object wrench ships, so there is no local artefact left to drift.
    """
    assert SCHEMA is wrench.JIG_SCHEMA
    assert not (ROOT / "schema").exists(), (
        "a local schema/ has reappeared; NFR-6 says wrench ships these and "
        "this repository keeps no copy"
    )


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
