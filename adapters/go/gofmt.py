#!/usr/bin/env python3
"""Adapter for `gofmt -l`: one reason per unformatted file.

gofmt lists unformatted files on stdout and exits 0 whether or not it found
any: the exit status answers "did gofmt run", never "is this formatted".
That is the whole reason an adapter exists.

Reads an execution record on stdin, writes an envelope on stdout.
"""

# pylint: disable=duplicate-code
#
# STRUCTURAL, NOT INCIDENTAL. Every script in `bin/` and `adapters/` is spawned
# by path from a directory that is not a package, so none can import another,
# so anything two of them must both do is written twice. R0801 finds a different
# pair each time one is dissolved: the coverage adapters' judgement, the
# checkers' `SKIP_DIRS`, the adapters' `emit`. Registered as S-3 in SUPPRESSIONS,
# with what would retire it.

import sys

import yaml

CHECKER = "format"


def main():
    record = yaml.safe_load(sys.stdin.read()) or {}
    captures = record.get("captures") or {}

    files = [line.strip() for line in (captures.get("stdout") or "").splitlines()]
    files = [f for f in files if f and not f.startswith("gofmt clean")]

    if not files:
        yaml.safe_dump({"success": True}, sys.stdout, sort_keys=False)
        return

    reasons = [
        {
            "checker": CHECKER,
            "file": f.lstrip("./"),
            "message": f"{f.lstrip('./')} is not gofmt-clean",
            "fix": "gofmt -w " + f,
        }
        for f in files
    ]
    yaml.safe_dump({"success": False, "reasons": reasons}, sys.stdout, sort_keys=False)


if __name__ == "__main__":
    main()
