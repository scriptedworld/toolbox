#!/usr/bin/env python3
"""Turn a child bolt run's result into the composing task's envelope.

THIS ADAPTER IS THE WHOLE OF COMPOSITION. Bolt retired nested jigs at
`f3304d8`, so a jig that wants another jig run over a subdirectory writes an
ordinary command task whose command is `bolt` and names this adapter:

    - name: python-common
      command: bolt --config-dir . --definitions wrench common-quality python
                    --output-dir {work_dir}/child
      adapter: adapters/common/bolt-result.py

WITHOUT IT THE COMPOSED TASK CANNOT FAIL. A task naming no adapter gets the
generic exit-code one, and **bolt exits 0 whenever it carried a run out**,
whatever the tools concluded. So every composed task would pass however badly
the child failed, which is the shape this estate has spent its time finding: a
green that answers a narrower question than the reader's.

WHAT IT READS. The child's stdout is one line, the path to the `result.yaml`
that run wrote, by bolt FR-10.3a. That requirement landed with composition
precisely so this works on every path: a refusal used to write a result and
print nothing, so an adapter would have read an empty file and had nothing to
say about a run that had genuinely refused.

THE CHILD'S REASONS COME UP, RATHER THAN A PATH GOING DOWN. A parent whose only
reason is "the child failed" sends a reader down a level for every failure, when
the child's list is already structured and already says which task and why. Each
folded reason keeps its own `kind` and `message` and gains `child`, naming the
result it came from, so a reader can tell one composed jig from another without
opening either.

A child result validates as an envelope, which is checked rather than assumed,
so a malformed one is refused with its own `kind` instead of being folded in as
though it said something.
"""

from __future__ import annotations

import argparse
import pathlib

import wrench
import yaml

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

    AN EMPTY STDOUT IS THE CHILD DYING BEFORE IT WROTE ANYTHING, which is bolt
    FR-10.7's reading and deserves its own kind rather than arriving as a parse
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
    # THE LAST LINE, NOT THE FIRST. FR-10.3a says bolt prints the path to the
    # result it wrote, and the Rust build prints that alone. The Go build still
    # on PATH prints a task-by-task transcript and a summary first, with the
    # path last. Measured 2026-08-29: reading the first line got `always-fails-0`,
    # a task name, and reported a missing result over a child that had written
    # one. Taking the last line satisfies both builds, which matters while the
    # cutover this adapter exists to unblock is still in progress.
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

    NO FALLBACK FOR A FAILING CHILD THAT SAID NOTHING, because the envelope
    schema makes that document invalid and `child_verdict` has already refused
    it. Measured 2026-08-29: both `success: false` alone and `success: false`
    with `reasons: []` fail validation, so a validated failure carries at least
    one reason. A fallback here would be a branch that cannot fire, which is the
    thing this repository keeps finding in other people's gates.
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
