#!/usr/bin/env python3
"""Pick the shell files out of a list of paths, by extension, by name and by shebang.

    git ls-files -z | shell-files.py [--for shellcheck] | xargs -r -0 TOOL

Paths arrive NUL-separated on stdin and the shell files leave the same way, so
a name holding a space or a newline survives. A file is shell when its
extension is one a shell uses, when its name is a shell's startup file such as
`.zshrc`, or when its first line is a shebang naming a shell. The shebang is
what reaches a script with no extension, which is how an entry point under
`bin/` or a hook under `home/` is usually written.

A symlink is skipped. In an adopter, a link under `bin/` is toolbox's own
checker, and its target is gated here.

`--for shellcheck` leaves out zsh, which shellcheck cannot parse; how many it
left out is printed on stderr with the count selected.

Exits 0 having selected something, or having left everything out for the
named tool. Exits 1 when no path given is a shell file at all, because a shell
jig with nothing to read would otherwise pass. Exits 2 when the command is
wrong.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SUFFIXES = {".sh": "sh", ".bash": "bash", ".ksh": "ksh", ".zsh": "zsh"}
NAMES = {
    ".bashrc": "bash",
    ".bash_profile": "bash",
    ".bash_login": "bash",
    ".bash_logout": "bash",
    ".profile": "sh",
    ".zshrc": "zsh",
    ".zshenv": "zsh",
    ".zprofile": "zsh",
    ".zlogin": "zsh",
    ".zlogout": "zsh",
}
# `#!/bin/sh`, `#!/usr/bin/env bash`, `#!/usr/bin/env -S zsh -f`.
SHEBANG = re.compile(r"^#!\s*\S*?/(?:env\s+(?:-\S+\s+)*)?(?P<shell>sh|bash|dash|ksh|mksh|zsh)\b")
UNPARSED = {"shellcheck": {"zsh"}}


def dialect(path: Path) -> str | None:
    """The shell a file is written for, or None when it is not a shell file."""
    if path.suffix in SUFFIXES:
        return SUFFIXES[path.suffix]
    if path.name in NAMES:
        return NAMES[path.name]
    try:
        with path.open("rb") as handle:
            first = handle.readline(256).decode("utf-8", "replace")
    except OSError:
        return None
    found = SHEBANG.match(first)
    return found.group("shell") if found else None


def main(argv: list[str] | None = None) -> int:
    """Read paths on stdin and write the shell files among them."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").partition("\n")[0])
    parser.add_argument("--for", dest="tool", choices=sorted(UNPARSED), help="leave out what this tool cannot parse")
    args = parser.parse_args(argv)
    unparsed = UNPARSED.get(args.tool or "", set())

    chosen: list[str] = []
    left_out = 0
    for name in sys.stdin.buffer.read().decode("utf-8", "surrogateescape").split("\0"):
        path = Path(name)
        if not name or path.is_symlink() or not path.is_file():
            continue
        shell = dialect(path)
        if shell is None:
            continue
        if shell in unparsed:
            left_out += 1
            continue
        chosen.append(name)

    if not chosen and not left_out:
        print("shell files: none among the paths given, so there is nothing for a shell jig to read", file=sys.stderr)
        return 1
    sys.stdout.buffer.write("".join(f"{name}\0" for name in chosen).encode("utf-8", "surrogateescape"))
    note = f", {left_out} left out that {args.tool} cannot parse" if args.tool else ""
    print(f"shell files: {len(chosen)} selected{note}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
