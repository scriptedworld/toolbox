#!/usr/bin/env python3
"""Link a project to the jigs it adopts, as `jigs.yaml` declares them.

A definition is only half of what a project needs. It names checkers, adapters
and tool configuration that live beside it in this repository, and
`{config_dir}` resolves those against the definition's own directory, so a
definition reached through a symlink resolves them back through that same link,
and every path the project runs stays inside the project. Adoption is therefore
a set of symlinks, and this makes them.

Entries land at the same relative path in the target that they have here. That
is forced rather than chosen: a linked definition sits at the target's root,
which makes `{config_dir}` the target's root, so `bin/x.py` has to be at
`bin/x.py` for the definition to find it. There is no destination to configure
and so no mapping to keep in step.

NOTHING IS EVER OVERWRITTEN. A real file where a link belongs is reported and
left alone. It is usually a vendored copy that predates adoption, and deleting
someone's file is their decision rather than this script's.

The default is to enumerate, ask, then act: the shape `bolt plan` and `bolt`
already have. A run with no terminal to ask at refuses rather than assuming
consent; `--yes` is how a script says it meant to.
"""

# pylint: disable=duplicate-code
#
# STRUCTURAL, NOT INCIDENTAL. Every script in `bin/` and `adapters/` is spawned
# by path from a directory that is not a package, so none can import another,
# so anything two of them must both do is written twice. R0801 finds a different
# pair each time one is dissolved: the coverage adapters' judgement, the
# checkers' `SKIP_DIRS`, the adapters' `emit`. Registered as S-3 in SUPPRESSIONS,
# with what would retire it.

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import yaml

DEFAULT_MANIFEST = Path(__file__).resolve().parent.parent / "jigs.yaml"


class State(Enum):
    """What is at the destination now, and therefore what has to happen."""

    LINKED = "already linked"
    CREATE = "to link"
    RELINK = "pointing somewhere else, to be repaired"
    BLOCKED = "a real file is in the way, left alone"
    ESCAPES = "resolves outside the project, refused"


ACTIONABLE = (State.CREATE, State.RELINK)
FAULTS = (State.BLOCKED, State.ESCAPES)


@dataclass(frozen=True)
class Link:
    """One manifest entry, resolved against a target project."""

    entry: str
    source: Path
    destination: Path
    points_to: str
    state: State


class ManifestError(Exception):
    """The manifest cannot be read, or names something that is not there."""


def load_manifest(path: Path) -> dict[str, dict]:
    """Read the manifest and return its sets, or say why it cannot be used."""
    if not path.exists():
        raise ManifestError(f"{path} does not exist; there is nothing to link from")
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ManifestError(f"{path} is not a mapping")
    if document.get("version") != 1:
        raise ManifestError(f"{path} declares version {document.get('version')!r}; only 1 exists")
    sets = document.get("sets")
    if not isinstance(sets, dict) or not sets:
        raise ManifestError(f"{path} declares no sets; refusing to link nothing")
    return sets


def closure(sets: dict[str, dict], names: list[str]) -> list[str]:
    """Expand the named sets through `includes`, depth first and cycle safe."""
    ordered: list[str] = []
    walking: list[str] = []

    def visit(name: str) -> None:
        if name in ordered:
            return
        if name in walking:
            cycle = " -> ".join([*walking, name])
            raise ManifestError(f"sets include each other in a cycle: {cycle}")
        if name not in sets:
            known = ", ".join(sorted(sets))
            raise ManifestError(f"no set named {name!r}; the manifest has {known}")
        walking.append(name)
        for included in sets[name].get("includes") or []:
            visit(included)
        walking.pop()
        ordered.append(name)

    for name in names:
        visit(name)
    return ordered


def entries_for(sets: dict[str, dict], names: list[str]) -> list[str]:
    """Every file the named sets ask for, in order, without repeats."""
    seen: dict[str, None] = {}
    for name in closure(sets, names):
        for entry in sets[name].get("files") or []:
            seen.setdefault(entry, None)
    return list(seen)


def inside(path: Path, root: Path) -> bool:
    """True when path is at or below root once every link on the way is followed."""
    resolved = Path(os.path.realpath(path))
    return resolved == Path(os.path.realpath(root)) or Path(os.path.realpath(root)) in resolved.parents


def points_to(source: Path, destination: Path, absolute: bool) -> str:
    """The text the symlink will hold: relative by default, so the pair can move."""
    if absolute:
        return str(source)
    return os.path.relpath(source, destination.parent)


def classify(source: Path, destination: Path, target: Path) -> State:
    """Decide what has to happen to make destination the link we want."""
    if not inside(destination.parent, target):
        return State.ESCAPES
    if destination.is_symlink():
        if destination.resolve() == source.resolve():
            return State.LINKED
        return State.RELINK
    if destination.exists():
        return State.BLOCKED
    return State.CREATE


def plan(root: Path, target: Path, entries: list[str], absolute: bool) -> list[Link]:
    """Resolve every entry against the target and say what state it is in."""
    links = []
    for entry in entries:
        source = root / entry
        destination = target / entry
        links.append(
            Link(
                entry=entry,
                source=source,
                destination=destination,
                points_to=points_to(source, destination, absolute),
                state=classify(source, destination, target),
            )
        )
    return links


def missing_sources(root: Path, entries: list[str]) -> list[str]:
    """Entries the manifest names that this repository does not have."""
    return [entry for entry in entries if not (root / entry).exists()]


def orphans(root: Path, target: Path, sets: dict[str, dict], keep: set[Path]) -> list[Path]:
    """Links into this repository that no longer belong to the adopted sets.

    Only the directories the manifest itself uses are scanned, across every set
    rather than only the chosen ones, so dropping `go` still finds the
    `config/` link it left behind, and a project's own tree is never walked.
    """
    every = {entry for one in sets.values() for entry in one.get("files") or []}
    found = []
    for directory in sorted({(target / entry).parent for entry in every}):
        if not directory.is_dir():
            continue
        for path in sorted(directory.iterdir()):
            if path.is_symlink() and path not in keep and inside(path, root):
                found.append(path)
    return found


def render(links: list[Link], orphaned: list[Path], target: Path) -> None:
    """Print what was found, grouped by what it means."""
    for state in State:
        matching = [link for link in links if link.state is state]
        if not matching or state is State.LINKED:
            continue
        print(f"{len(matching)} {state.value}:")
        for link in matching:
            print(f"  {link.entry}")
        print()
    if orphaned:
        print(f"{len(orphaned)} link(s) no longer in any adopted set:")
        for path in orphaned:
            print(f"  {path.relative_to(target)}")
        print()


def apply(links: list[Link]) -> int:
    """Create or repair every link that needs it. Returns how many changed."""
    changed = 0
    for link in links:
        if link.state not in ACTIONABLE:
            continue
        link.destination.parent.mkdir(parents=True, exist_ok=True)
        if link.destination.is_symlink():
            link.destination.unlink()
        link.destination.symlink_to(link.points_to)
        changed += 1
    return changed


def summarise(links: list[Link], orphaned: list[Path]) -> int:
    """Say where the project stands, and return the exit status that matches."""
    faults = [link for link in links if link.state in FAULTS]
    pending = [link for link in links if link.state in ACTIONABLE]
    if not faults and not pending and not orphaned:
        print(f"all {len(links)} link(s) present and correct")
        return 0
    print(
        f"{len(links) - len(pending) - len(faults)} of {len(links)} link(s) correct; "
        f"{len(pending)} to make, {len(faults)} refused, {len(orphaned)} orphaned"
    )
    return 1


def confirm(count: int) -> bool:
    """Ask before writing into someone else's repository."""
    answer = input(f"link {count} file(s)? [y/N] ")
    return answer.strip().lower() in {"y", "yes"}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Read the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path, help="the project to link into")
    parser.add_argument("sets", nargs="+", help="which sets from the manifest")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--plan", action="store_true", help="say what would happen, and stop")
    parser.add_argument("--check", action="store_true", help="verify without writing; exit 1 on drift")
    parser.add_argument("--yes", action="store_true", help="do not ask")
    parser.add_argument(
        "--absolute",
        action="store_true",
        help="hold an absolute path, for a toolbox that does not travel with the project",
    )
    return parser.parse_args(argv)


def validate(args: argparse.Namespace) -> str | None:
    """Reject a command line that asks for two things, or for a target that is not one."""
    if args.plan and args.check:
        return "--plan and --check ask for different things; choose one"
    if not args.target.is_dir():
        return f"{args.target} is not a directory"
    return None


def gather(args: argparse.Namespace, root: Path) -> tuple[dict[str, dict], list[str]]:
    """Read the manifest and resolve the named sets to the files they ask for."""
    sets = load_manifest(args.manifest)
    entries = entries_for(sets, args.sets)
    absent = missing_sources(root, entries)
    if absent:
        named = "\n".join(f"  {entry}" for entry in absent)
        raise ManifestError(f"{len(absent)} entry(ies) named by the manifest are not here:\n{named}\n\nthe manifest is wrong, and nothing was linked")
    return sets, entries


def act(args: argparse.Namespace, links: list[Link]) -> int | None:
    """Ask, unless told not to, and then link. None means it went ahead."""
    pending = [link for link in links if link.state in ACTIONABLE]
    if not pending:
        return None
    if not args.yes:
        if not sys.stdin.isatty():
            print("nothing to ask at; pass --yes to link without being asked")
            return 1
        if not confirm(len(pending)):
            print("nothing was linked")
            return 1
    print(f"linked {apply(links)} file(s)\n")
    return None


def main() -> int:
    """Enumerate, then (unless asked only to look) link."""
    args = parse_args()
    problem = validate(args)
    if problem:
        print(problem)
        return 1

    root = args.manifest.resolve().parent
    try:
        sets, entries = gather(args, root)
    except ManifestError as unusable:
        print(unusable)
        return 1

    links = plan(root, args.target, entries, args.absolute)
    orphaned = orphans(root, args.target, sets, {link.destination for link in links})
    render(links, orphaned, args.target)

    if args.plan:
        return 0
    if args.check:
        return summarise(links, orphaned)

    refused = act(args, links)
    if refused is not None:
        return refused
    return summarise(plan(root, args.target, entries, args.absolute), orphaned)


if __name__ == "__main__":
    sys.exit(main())
