#!/usr/bin/env python3
"""Print the version of every tool a jig's `requires:` names, so a verdict records what produced it.

    tool-versions.py JIG

Each tool is asked `--version`, `version`, `-version` and `-V` in turn, and the
first that exits 0 with output is recorded by the line carrying its version. A
tool answering none is recorded by the digest of its binary. The list is read
from the jig itself, so a tool added to `requires:` is recorded without
anything else changing.

An upgraded tool can change an adopter's verdict with nothing in toolbox or the
adopter changing, and without this a run shows nothing of why.

Exits 0 when every tool was recorded, 1 when one is not on PATH, and 2 when the
command or the jig is wrong. The
list is read without a YAML library, so the task needs nothing beyond the
interpreter.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import subprocess  # nosec B404
import sys
from pathlib import Path

FLAGS = (("--version",), ("version",), ("-version",), ("-V",))
SECONDS = 30
ENTRY = re.compile(r"^\s+-\s+(?P<tool>[\w.+-]+)\s*(?:#.*)?$")
NUMBER = re.compile(r"\d+\.\d+")
# A tool with no version of its own is recorded by the toolchain that ships it.
SHIPPED_WITH = {"gofmt": ("go", "version")}


def required(jig: Path) -> list[str]:
    """The tools under `requires:` in a jig, read line by line."""
    tools: list[str] = []
    inside = False
    for line in jig.read_text(encoding="utf-8").splitlines():
        if line.startswith("requires:"):
            inside = True
            continue
        if inside and line and not line[0].isspace():
            break
        entry = ENTRY.match(line) if inside else None
        if entry:
            tools.append(entry.group("tool"))
    return tools


def version_line(tool: str, output: str) -> str | None:
    """The line of a version report that carries the version.

    The first line holding a version number and the tool's name, else the first
    holding a number, else the first line: shellcheck opens with a banner and
    govulncheck with the Go version before its own.
    """
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    numbered = [line for line in lines if NUMBER.search(line)]
    named = [line for line in numbered if tool.lower() in line.lower()]
    return (named or numbered or lines or [None])[0]


def version_of(tool: str) -> str | None:
    """What a tool reports for the first version flag it accepts, or None."""
    program = shutil.which(tool)
    if program is None:
        return None
    if tool in SHIPPED_WITH:
        owner, *flag = SHIPPED_WITH[tool]
        found = version_of_command([shutil.which(owner) or owner, *flag], owner)
        return f"ships with {found}" if found else None
    # A cargo subcommand's binary takes its own name first, as cargo passes it.
    own = ((tool.removeprefix("cargo-"), "--version"),) if tool.startswith("cargo-") else ()
    for flag in (*FLAGS, *own):
        found = version_of_command([program, *flag], tool)
        if found:
            return found
    return fingerprint(program)


def fingerprint(program: str) -> str | None:
    """The binary's own digest, for a tool that answers no version flag.

    It identifies what ran as well as a version would, and two runs that differ
    here ran different binaries. A mise shim resolves to mise itself, so behind
    a shim this names mise's build and not the tool's.
    """
    try:
        digest = hashlib.sha256(Path(program).resolve().read_bytes()).hexdigest()[:16]
    except OSError:
        return None
    return f"no version flag; sha256 {digest} of {Path(program).resolve()}"


def version_of_command(argv: list[str], tool: str) -> str | None:
    """The version line one command prints, when it exits 0."""
    try:
        done = subprocess.run(argv, capture_output=True, text=True, timeout=SECONDS, check=False)  # nosec B603
    except (OSError, subprocess.TimeoutExpired):
        return None
    if done.returncode != 0:
        return None
    return version_line(tool, done.stdout or done.stderr)


def main(argv: list[str] | None = None) -> int:
    """Record each required tool's version, and fail on one that gave none."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").partition("\n")[0])
    parser.add_argument("jig", type=Path)
    args = parser.parse_args(argv)
    try:
        tools = required(args.jig)
    except OSError as unreadable:
        print(f"{args.jig} cannot be read: {unreadable.strerror}")
        return 2
    if not tools:
        print(f"{args.jig} names no tools under requires:, so there is nothing to record")
        return 2
    missing = []
    for tool in tools:
        found = version_of(tool)
        print(f"{tool}: {found if found is not None else 'NOT FOUND on PATH'}")
        if found is None:
            missing.append(tool)
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
