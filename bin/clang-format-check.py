#!/usr/bin/env python3
"""Report every translation unit in a compilation database that is not formatted.

clang-format is the one tool in the C++ jig with no directory mode and no
project mode: it takes file paths and nothing else. Every other tool here reads
`compile_commands.json` directly, so this reads the same database and hands it
the files instead of globbing a tree and guessing which of them are compiled.

    clang-format-check.py --style FILE [--database PATH] [--exclude REGEX]...

Exits 1 when any file would be reformatted and prints one path per line. A
checker exits; it does not return an envelope. bolt's configuration never says
what success means for a checker, so the exit status is the whole answer, and
`bin/suppression-register.py` beside this makes the same choice.

The database is read instead of a glob because a glob finds headers nobody
compiles, vendored third-party sources, and generated files, and each of those
is a formatting failure the project cannot act on. The database is the project's
own statement of what it builds. The cost is that a header included by nothing
is unchecked, which is the right side to be wrong on: an unformatted file that
is never compiled is not what a gate is for.

It runs `--dry-run --Werror`, not `-output-replacements-xml`. Both report without
writing. The first gives a diagnostic per site with a line and column, which is
what a person needs to fix it; the second gives an XML blob that has to be
parsed to say anything at all.
"""

import argparse
import json
import pathlib
import re
import subprocess  # nosec B404
import sys


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--style",
        required=True,
        help="path to the clang-format configuration, passed as --style=file:PATH",
    )
    parser.add_argument(
        "--database",
        default="compile_commands.json",
        help="the compilation database (default: %(default)s)",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="REGEX",
        help="skip files whose path matches; repeatable",
    )
    parser.add_argument(
        "--clang-format",
        default="clang-format",
        help="the binary to run (default: %(default)s)",
    )
    parser.add_argument(
        "--base",
        default=".",
        help=("the project root an exclusion is relative to (default: %(default)s)"),
    )
    return parser.parse_args(argv)


def sources(database: pathlib.Path, base: pathlib.Path, excludes: list[re.Pattern]) -> list[str]:
    """Every distinct file the database names, in a stable order.

    A database can name one file twice, once per configuration it is built in,
    and formatting is a property of the text rather than of the build. So the
    set is deduplicated and sorted: a checker that reported the same file twice
    would read as two failures.

    An exclusion matches the path relative to the base, never the absolute one.
    A compilation database records absolute paths, and the jigs' exclusions are
    project-relative directory names like `.ephemera`. Matching those against an
    absolute path makes the answer depend on where the project happens to be
    checked out: a fixture living under a directory called `.ephemera` excluded
    every one of its own files and the checker reported an empty database. A
    project cannot be responsible for its own parent directories' names.
    """
    entries = json.loads(database.read_text(encoding="utf-8"))
    found: set[str] = set()
    for entry in entries:
        name = entry.get("file")
        if not name:
            continue
        absolute = pathlib.Path(entry.get("directory", ".")) / name
        try:
            relative = absolute.resolve().relative_to(base)
        except ValueError:
            # Compiled from outside the tree being checked. A generated source
            # in a build directory elsewhere is the usual case, and it is not
            # the project's to format.
            continue
        if any(pattern.search(str(relative)) for pattern in excludes):
            continue
        found.add(str(absolute.resolve()))
    return sorted(found)


def unformatted(binary: str, style: pathlib.Path, files: list[str]) -> list[str]:
    """The files clang-format would change, one run per file.

    One run per file and not one over all of them, because --Werror makes the exit
    status a single bit for the whole invocation. Run together, one unformatted
    file and forty unformatted files are the same answer, and the point of this
    checker is to say which.
    """
    bad = []
    for name in files:
        result = subprocess.run(  # nosec B603
            [binary, f"--style=file:{style}", "--dry-run", "--Werror", name],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            bad.append(name)
            sys.stderr.write(result.stderr)
    return bad


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    database = pathlib.Path(args.database)
    if not database.is_file():
        print(
            f"no compilation database at {database}. The C++ jig is driven by "
            f"one; produce it with `bear -- <your build>` or with cmake's "
            f"CMAKE_EXPORT_COMPILE_COMMANDS=ON.",
            file=sys.stderr,
        )
        return 1

    style = pathlib.Path(args.style)
    if not style.is_file():
        print(f"no clang-format configuration at {style}", file=sys.stderr)
        return 1

    excludes = [re.compile(pattern) for pattern in args.exclude]
    files = sources(database, pathlib.Path(args.base).resolve(), excludes)
    if not files:
        print(
            f"{database} named no files to check. An empty database passes "
            f"every per-file check in this jig, so it is refused here rather "
            f"than reported as success.",
            file=sys.stderr,
        )
        return 1

    bad = unformatted(args.clang_format, style, files)
    for name in bad:
        print(name)

    print(f"{len(files) - len(bad)}/{len(files)} formatted", file=sys.stderr)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
