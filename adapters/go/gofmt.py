#!/usr/bin/env python3
"""Adapter for `gofmt -l`: one reason per unformatted file.

gofmt lists unformatted files on stdout and exits 0 whether or not it found
any, so its exit status cannot be the verdict and this adapter reads the list.

Reads an execution record on stdin, writes an envelope on stdout.
"""

# pylint: disable=duplicate-code
#
# Every script in `bin/` and `adapters/` is spawned by path from a directory that
# is not a package, so none can import another and shared code is written twice.
# Registered as S-3 in SUPPRESSIONS, with what would retire it.

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
            "kind": "not-formatted",
            "file": f.lstrip("./"),
            "message": f"{f.lstrip('./')} is not gofmt-clean",
            "fix": "gofmt -w " + f,
        }
        for f in files
    ]
    yaml.safe_dump({"success": False, "reasons": reasons}, sys.stdout, sort_keys=False)


if __name__ == "__main__":
    main()
