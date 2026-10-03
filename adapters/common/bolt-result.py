#!/usr/bin/env python3
"""Turn a child bolt run's result into the composing task's envelope.

This adapter is the whole of composition. Bolt has no nested jigs, so a jig
that wants another jig run over a subdirectory writes an ordinary command task
whose command is `bolt` and names this adapter:

    - name: python-common
      command: bolt --config-dir . --definitions wrench common-quality python
                    --output-dir {work_dir}/child
      adapter: adapters/common/bolt-result.py

Without it the composed task cannot fail. A task naming no adapter gets the
generic exit-code one, and **bolt exits 0 whenever it carried a run out**,
whatever the tools concluded, so every composed task would pass however badly
the child failed.

The child's stdout ends with the path to the `result.yaml` that run wrote, by
bolt FR-10.3a, on every path including a refusal.

The child's reasons come up to the parent, instead of the parent pointing down
at the child. A parent whose only reason is "the child failed" sends a reader
down a level for every failure, when the child's list is already structured and
already says which task and why. Each folded reason keeps its own `kind` and
`message` and gains `child`, naming the result it came from, so a reader can
tell one composed jig from another without opening either.

A child result validates as an envelope, which is checked rather than assumed,
so a malformed one is refused with its own `kind` instead of being folded in as
though it said something.
"""

# pylint: disable=duplicate-code
#
# Every script in `bin/` and `adapters/` is spawned by path from a directory that
# is not a package, so none can import another and shared code is written twice.
# Registered as S-3 in SUPPRESSIONS, with what would retire it.

from __future__ import annotations

import argparse
import json
import pathlib
import sys


def refusal(missing: ImportError) -> dict:
    """The failing envelope for a package this interpreter cannot import (FR-3.11).

    bolt reports a crashed adapter only as the status it exited with, which
    names neither the package nor the interpreter.
    """
    need = f"{pathlib.Path(sys.argv[0]).name} needs the Python package {missing.name}"
    have = f"{sys.executable} (Python {sys.version.split()[0]}) cannot import it"
    return {"success": False, "reasons": [{"kind": "adapter-dependency-missing", "message": f"{need}, and {have}"}]}


# JSON is valid YAML, so writing the refusal needs no yaml.
try:
    import wrench
    import yaml
except ImportError as missing:
    WORK = sys.argv[sys.argv.index("--work-dir") + 1] if "--work-dir" in sys.argv[:-1] else "."
    pathlib.Path(WORK, "output.yaml").write_text(json.dumps(refusal(missing)), encoding="utf-8")
    sys.exit(0)

CHECKER = "bolt-result"


def arguments():
    """The command line bolt hands an adapter.

    Every flag bolt passes is declared, including the ones this adapter does not
    read, so an unexpected argument is an error here rather than something
    silently ignored. `--stdout` and `--work-dir` are the two that matter.
    """
    ap = argparse.ArgumentParser()
    ap.add_argument("--stdout")
    ap.add_argument("--work-dir", dest="work_dir", required=True)
    ap.add_argument("--stderr")
    ap.add_argument("--exitcode")
    ap.add_argument("--evidence", action="append", default=[])
    ap.add_argument("--project-root", dest="project_root")
    ap.add_argument("--base-dir", dest="base_dir")
    return ap.parse_args()


def reason(kind: str, message: str, **extra) -> dict:
    """One reason in the shape the envelope schema requires.

    `kind` so a consumer can tell one sort of failure from another without
    reading English, `message` so any consumer can render it.
    """
    return {"kind": kind, "checker": CHECKER, "message": message, **extra}


def named_result(stdout: str | None) -> tuple[pathlib.Path | None, dict | None]:
    """The result path the child printed, or the reason there is not one.

    An empty stdout is the child dying before it wrote anything, which is bolt
    FR-10.7's reading and deserves its own kind instead of arriving as a parse
    failure on an empty file. The two have different causes and different fixes,
    which is the same distinction bolt draws between an adapter that wrote
    nothing and one that wrote something invalid.
    """
    if not stdout:
        return None, reason(
            "child-wrote-nothing",
            "the child run named no result; bolt prints the path to the result.yaml it wrote, so nothing printed means nothing was written",
        )
    lines = [line.strip() for line in pathlib.Path(stdout).read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        return None, reason(
            "child-wrote-nothing",
            f"the child run printed nothing to {stdout}; it died before writing a result rather than completing with a verdict",
        )
    # The last line, not the first. FR-10.3a says bolt prints the path to the
    # result it wrote, and the Rust build prints that alone. The Go build prints
    # a task-by-task transcript and a summary first, with the path last, so its
    # first line is a task name. The last line is the path from both builds.
    return pathlib.Path(lines[-1]), None


def child_verdict(path: pathlib.Path) -> tuple[dict | None, dict | None]:
    """The child's envelope, or the reason it could not be read.

    Validated against the envelope schema wrench ships, because a result bolt
    wrote is envelope-shaped and a malformed one must be refused rather than
    folded in as though it carried a verdict. Reading `success` off a document
    that does not validate would let a truncated write read as a pass.
    """
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as unreadable:
        return None, reason(
            "child-result-unreadable",
            f"{path} could not be read: {unreadable.strerror}",
        )
    except yaml.YAMLError as broken:
        return None, reason("child-result-invalid", f"{path} is not YAML: {broken}")

    try:
        wrench.ENVELOPE_SCHEMA.validate(document)
    except wrench.ValidationError as invalid:
        return None, reason(
            "child-result-invalid",
            f"{path} is not a valid result: {invalid}",
        )
    return document, None


def fold(document: dict, where: pathlib.Path) -> list[dict]:
    """The child's reasons, as this task's.

    A failing child hands its list up unchanged except for `child`, which names
    the result it came from, so a reader can tell one composed jig from another
    without opening either.

    There is no fallback for a failing child that said nothing, because the
    envelope schema makes that document invalid and `child_verdict` has already
    refused it. Both `success: false` alone and `success: false` with
    `reasons: []` fail validation, so a validated failure carries at least one
    reason.
    """
    if document.get("success"):
        return []
    return [{**item, "child": str(where)} for item in document["reasons"]]


def emit(work_dir: pathlib.Path, success: bool, reasons: list[dict], statistics=None):
    """Write the envelope bolt reads, in the shape wrench validates.

    The name never varies and the directory is the one bolt gave, so nothing
    here decides where a verdict goes. Writing to stdout would be discarded and
    read by nobody.
    """
    doc: dict = {"success": success}
    if reasons:
        doc["reasons"] = reasons
    if statistics:
        doc["metadata"] = {"statistics": statistics}
    with open(work_dir / "output.yaml", "w", encoding="utf-8") as fh:
        yaml.safe_dump(doc, fh, sort_keys=False)


def main() -> None:
    args = arguments()
    work_dir = pathlib.Path(args.work_dir)

    where, missing = named_result(args.stdout)
    if missing or where is None:
        emit(work_dir, False, [missing] if missing else [])
        return

    if not where.exists():
        emit(
            work_dir,
            False,
            [
                reason(
                    "child-result-missing",
                    f"the child named {where} and no result is there",
                )
            ],
        )
        return

    document, unreadable = child_verdict(where)
    if unreadable or document is None:
        emit(work_dir, False, [unreadable] if unreadable else [])
        return

    reasons = fold(document, where)
    emit(work_dir, not reasons, reasons, {"child_reasons": len(reasons)})


if __name__ == "__main__":
    main()
