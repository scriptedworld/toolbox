#!/usr/bin/env python3
"""Adapter for `go vet`: one reason per diagnostic.

go vet writes diagnostics to stderr as `file:line:col: message`, interleaved
with `# package` headers. Exit 1 means "found something", but says nothing
about what or where; these reasons carry the location so a merged result stays
actionable.

Reads an execution record on stdin, writes an envelope on stdout.
"""

import re
import sys

import yaml

DIAGNOSTIC = re.compile(r"^(?P<file>[^:\s]+\.go):(?P<line>\d+):(?:(?P<col>\d+):)?\s*(?P<msg>.+)$")

CHECKER = "vet"


def reasons_from(text):
    out = []
    package = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if line.startswith("#"):
            package = line.lstrip("# ").strip()
            continue
        m = DIAGNOSTIC.match(line.strip())
        if not m:
            continue
        reason = {
            "checker": CHECKER,
            "file": m.group("file").lstrip("./"),
            "line": int(m.group("line")),
            "message": m.group("msg").strip(),
        }
        if m.group("col"):
            reason["column"] = int(m.group("col"))
        if package:
            reason["package"] = package
        out.append(reason)
    return out


def main():
    record = yaml.safe_load(sys.stdin.read()) or {}
    captures = record.get("captures") or {}
    text = (captures.get("stderr") or "") + "\n" + (captures.get("stdout") or "")

    reasons = reasons_from(text)
    code = captures.get("exitcode", 0)

    if reasons:
        yaml.safe_dump({"success": False, "reasons": reasons}, sys.stdout, sort_keys=False)
        return

    if code not in (0, None):
        # vet failed for a reason this adapter cannot attribute -- a package
        # that would not build, most often. Reporting a pass would hide it.
        yaml.safe_dump(
            {
                "success": False,
                "reasons": [
                    {
                        "checker": CHECKER,
                        "message": f"go vet exited {code} with no diagnostic this adapter could parse",
                        "detail": text.strip()[:2000],
                    }
                ],
            },
            sys.stdout,
            sort_keys=False,
        )
        return

    yaml.safe_dump({"success": True}, sys.stdout, sort_keys=False)


if __name__ == "__main__":
    main()
