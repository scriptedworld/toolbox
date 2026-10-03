#!/usr/bin/env python3
"""Ask a model for the voice habits a pattern cannot catch, and report what it finds.

    voice-review.py [FILE...]                  the named files, or the staged ones
    voice-review.py --all-files                every file, and the commits after the start
    voice-review.py --from-ref A --to-ref B    what changed between two refs
    voice-review.py --commit-msg-filename F    one commit message

The modes and everything about which text is read are `bin/voice-tells.py`'s,
loaded from beside this file, so the two checks always read the same prose.

Each document, each file's comments and each commit message goes to the model
whole, one request apiece, with the prompt in
`config/prompts/voice-findings.md`. The model drafts findings, each a line, a
rule and a quote, then checks each draft against its rule before answering, and
only a draft its own check holds is kept. Each text is asked twice by default
(`--agree`), and a finding stands only when both answers report it on the same
line under the same rule. Two answers keep a document's pass or fail steady
across runs where one does not, and a third adds nothing. No sampling
parameter is sent. A kept finding stands
only when its rule is one the prompt asks for and its quote starts on the line
it names; anything else is dropped and counted.

This never fails a run on what it finds. Two reviews of one unchanged tree
agree on well under half their findings, which is a report to read and not a
verdict to gate on; `bin/voice-tells.py` is the gate. Exits 0 when the review
ran, when it found things, and when no model could be reached, which the output
says in so many words. Exits 2 when the command or the repository is wrong.

Model access, in order: the Messages API when `ANTHROPIC_API_KEY` is set, then
`claude -p` when the fallback is `cli`. No sampling parameter is sent, because
the current models refuse one. `http.client` and `subprocess` only, since this
file is linked into adopting repositories and run by whatever `python3` they
have.
"""

from __future__ import annotations

import argparse
import http.client
import importlib.util
import json
import os
import re
import shutil
import subprocess  # nosec B404
import sys
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

API_HOST = "api.anthropic.com"
API_VERSION = "2023-06-01"
REQUEST_SECONDS = 600
PROMPT = Path(__file__).resolve().parent.parent / "config" / "prompts" / "voice-findings.md"
RULES = frozenset({"closing-aphorism", "emphatic-contrast", "narrated-history", "restated-elsewhere", "table-stakes", "rule-of-three"})
# Independent answers per text by default; a finding stands only when every one reports it.
AGREE = 2
# A quote starts on its line and may run onto this many more where the sentence wraps.
WRAP_LINES = 2


def wording_check() -> ModuleType:
    """`voice-tells.py` from this file's own directory, which adoption always links beside it."""
    path = Path(__file__).with_name("voice-tells.py")
    spec = importlib.util.spec_from_file_location("voice_tells", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("voice_tells", module)
    spec.loader.exec_module(module)
    return module


tells = wording_check()


class Unreachable(Exception):
    """No model could be asked, so nothing was reviewed."""

    def __init__(self, why: str, detail: str):
        super().__init__(f"{why}: {detail}")
        self.why = why
        self.detail = detail


class Unanswered(Exception):
    """A model answered one text with something that is not a list of findings."""


@dataclass(frozen=True)
class Backend:
    """One way of asking the model a question and getting its text back."""

    name: str
    model: str
    ask: Callable[[str, str], str]


# Anything with `request` and `getresponse` as `http.client.HTTPSConnection` has them.
Connection = Any


@dataclass
class Access:
    """What the checker reaches outside itself, so a test can hand in fakes."""

    env: dict[str, str] = field(default_factory=lambda: dict(os.environ))
    which: Callable[[str], str | None] = shutil.which
    connect: Callable[[], Connection] | None = None
    run: Callable[..., subprocess.CompletedProcess] = subprocess.run


# ---- model access -----------------------------------------------------------


def api_error_message(payload: str) -> str:
    """The `error.message` of an API error body, or the body itself."""
    try:
        return str(json.loads(payload)["error"]["message"])
    except (ValueError, KeyError, TypeError):
        return payload.strip()[:300]


def api_answer(status: int, payload: str) -> str:
    """The reply text of a Messages API response, or why there is none."""
    if status == 200:
        try:
            blocks = json.loads(payload)["content"]
            return "".join(block.get("text", "") for block in blocks if block.get("type") == "text")
        except (ValueError, KeyError, TypeError, AttributeError) as broken:
            raise Unanswered(f"the API returned 200 with a body that is not a message: {broken}") from broken
    message = api_error_message(payload)
    if status in (401, 403):
        raise Unreachable("no-credentials", f"the API rejected the credentials (HTTP {status}): {message}")
    if status in (429, 529) or "credit balance" in message.lower():
        raise Unreachable("out-of-quota", f"HTTP {status}: {message}")
    if status >= 500:
        raise Unreachable("unavailable", f"HTTP {status}: {message}")
    raise Unreachable("request-refused", f"the API refused the request (HTTP {status}): {message}")


def api_backend(model: str, key: str, connect: Callable[[], Connection] | None = None) -> Backend:
    """The Messages API."""
    opener: Callable[[], Connection] = connect or (lambda: http.client.HTTPSConnection(API_HOST, timeout=REQUEST_SECONDS))
    headers = {"x-api-key": key, "anthropic-version": API_VERSION, "content-type": "application/json"}

    def ask(system: str, user: str) -> str:
        body = {"model": model, "max_tokens": 16000, "system": system, "messages": [{"role": "user", "content": user}]}
        try:
            connection = opener()
            connection.request("POST", "/v1/messages", json.dumps(body), headers)
            response = connection.getresponse()
            status, payload = response.status, response.read().decode("utf-8", "replace")
        except (OSError, http.client.HTTPException) as broken:
            raise Unreachable("offline", f"could not reach {API_HOST}: {broken}") from broken
        return api_answer(status, payload)

    return Backend("api", model, ask)


def cli_failure(result: str) -> Unreachable:
    """Classify an error the CLI reported in its own result."""
    lowered = result.lower()
    if "login" in lowered or "logged in" in lowered or "api key" in lowered or "auth" in lowered:
        return Unreachable("no-credentials", f"the claude CLI has no usable login: {result}")
    if "limit" in lowered or "quota" in lowered or "credit" in lowered:
        return Unreachable("out-of-quota", f"the claude CLI reported: {result}")
    return Unreachable("cli-failed", f"the claude CLI reported an error: {result}")


def cli_answer(code: int, stdout: str, stderr: str) -> str:
    """The reply text from `claude -p --output-format json`, or why there is none."""
    try:
        document = json.loads(stdout)
    except ValueError:
        tail = (stderr or stdout).strip()[-300:]
        raise Unreachable("cli-failed", f"the claude CLI exited {code} without a result: {tail}") from None
    result = str(document.get("result", "")) if isinstance(document, dict) else ""
    if not isinstance(document, dict) or document.get("is_error") or code != 0:
        raise cli_failure(result or f"exit {code}")
    return result


def cli_backend(model: str, claude: str, run: Callable[..., subprocess.CompletedProcess]) -> Backend:
    """`claude -p`, with no tools, no settings and no session kept."""

    def ask(system: str, user: str) -> str:
        argv = [claude, "-p", "--model", model, "--output-format", "json", "--tools", "", "--no-session-persistence"]
        argv += ["--setting-sources", "", "--strict-mcp-config", "--system-prompt", system]
        try:
            done = run(argv, input=user, capture_output=True, text=True, timeout=REQUEST_SECONDS, check=False)
        except (OSError, subprocess.TimeoutExpired) as broken:
            raise Unreachable("offline", f"the claude CLI did not answer: {broken}") from broken
        return cli_answer(done.returncode, done.stdout, done.stderr)

    return Backend("cli", model, ask)


def resolve_backend(model: str, fallback: str, access: Access) -> Backend:
    """The API when a key is set, else the declared CLI fallback, else unreachable."""
    key = access.env.get("ANTHROPIC_API_KEY")
    if key:
        return api_backend(model, key, access.connect)
    if fallback != "cli":
        raise Unreachable("no-credentials", "ANTHROPIC_API_KEY is not set and the CLI fallback is off")
    claude = access.which("claude")
    if not claude:
        raise Unreachable("no-credentials", "ANTHROPIC_API_KEY is not set and no claude CLI is on PATH")
    return cli_backend(model, claude, access.run)


# ---- findings ---------------------------------------------------------------


def squashed(text: str) -> str:
    """Whitespace folded and case dropped, so a quote survives rewrapping."""
    return re.sub(r"\s+", " ", text).strip().lower()


def parse_findings(answer: str) -> tuple[list[dict], int]:
    """The drafts the model's own check held, and how many it withdrew or left unchecked."""
    start, end = answer.find("{"), answer.rfind("}")
    try:
        document = json.loads(answer[start : end + 1]) if 0 <= start < end else None
    except ValueError:
        document = None
    if not isinstance(document, dict) or not isinstance(document.get("draft"), list) or not isinstance(document.get("checks"), list):
        raise Unanswered(f"the answer carried no drafts and checks: {answer.strip()[:200]!r}")
    drafts = [item for item in document["draft"] if isinstance(item, dict)]
    held = {check.get("draft") for check in document["checks"] if isinstance(check, dict) and check.get("holds") is True}
    kept = [item for index, item in enumerate(drafts) if index in held]
    return kept, len(drafts) - len(kept)


def verified(text: Any, finding: dict) -> bool:
    """Whether the rule is one asked for and the quote starts on the line the finding names."""
    by_line = dict(text.lines)
    line, quote = finding.get("line"), squashed(str(finding.get("quote", "")))
    if finding.get("rule") not in RULES or not isinstance(line, int) or line not in by_line or not quote:
        return False
    first = squashed(by_line[line])
    window = squashed(" ".join(by_line.get(line + offset, "") for offset in range(WRAP_LINES + 1)))
    return 0 <= window.find(quote) < max(len(first), 1)


def answered(backend: Backend, prompt: str, text: Any) -> tuple[list[dict], int, int]:
    """One answer for a text: its verified findings, how many verification dropped, and how many its check withdrew."""
    body = "\n".join(f"{number}| {line}" for number, line in text.lines)
    found, withdrawn = parse_findings(backend.ask(prompt, f"text: {text.where}\nkind: {text.kind}\n\n{body}\n"))
    kept = [item for item in found if verified(text, item)]
    return kept, len(found) - len(kept), withdrawn


def review_text(backend: Backend, prompt: str, text: Any, agree: int = 1) -> dict:
    """One text's findings: those every one of `agree` independent answers reports, by line and rule."""
    answers = [answered(backend, prompt, text) for _ in range(max(agree, 1))]
    keyed = [{(item["line"], item["rule"]): item for item in kept} for kept, _, _ in answers]
    agreed = set(keyed[0]).intersection(*keyed[1:])
    seen = set().union(*keyed)
    kept = [{"where": text.where, **item} for key, item in keyed[0].items() if key in agreed]
    dropped, withdrawn = sum(answer[1] for answer in answers), sum(answer[2] for answer in answers)
    return {"where": text.where, "kept": kept, "dropped": dropped, "withdrawn": withdrawn, "disagreed": len(seen - agreed)}


@dataclass
class Outcome:
    """What a whole review found, and what it set aside on the way."""

    kept: list[dict] = field(default_factory=list)
    dropped: int = 0
    withdrawn: int = 0
    disagreed: int = 0
    unanswered: list[dict] = field(default_factory=list)


def review(backend: Backend, prompt: str, texts: list, workers: int, agree: int = 1) -> Outcome:
    """Every text, in parallel.

    An unreachable model anywhere ends the review, because a partial review
    reads as a complete one.
    """
    outcome = Outcome()
    with ThreadPoolExecutor(max_workers=max(workers, 1)) as pool:
        jobs = [(text, pool.submit(review_text, backend, prompt, text, agree)) for text in texts if text.lines]
        for text, job in jobs:
            try:
                result = job.result()
            except Unanswered as problem:
                outcome.unanswered.append({"where": text.where, "why": str(problem)})
                continue
            outcome.kept += result["kept"]
            outcome.dropped += result["dropped"]
            outcome.withdrawn += result["withdrawn"]
            outcome.disagreed += result["disagreed"]
    return outcome


# ---- running it -------------------------------------------------------------


def arguments(argv: list[str] | None) -> argparse.Namespace:
    """The wording check's modes, and what this review adds to them."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").partition("\n")[0])
    tells.add_modes(parser)
    parser.add_argument("--prompt", type=Path, default=PROMPT, help="the prompt every request sends")
    parser.add_argument("--model", default="claude-sonnet-5")
    parser.add_argument("--fallback", choices=("cli", "none"), default="cli", help="what to use when ANTHROPIC_API_KEY is not set")
    parser.add_argument("--workers", type=int, default=8, help="texts in review at once")
    parser.add_argument("--agree", type=int, default=AGREE, help="independent answers per text; a finding stands only when all report it")
    return tells.check_modes(parser, parser.parse_args(argv))


def finish(report: Path | None, document: dict, lines: list[str]) -> int:
    """Print what a person reads, write the report where one was asked for, and exit 0."""
    print("\n".join(lines))
    if report:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return 0


def main(argv: list[str] | None = None, access: Access | None = None) -> int:
    """Review what the mode selects and report it. Findings never fail the run."""
    args = arguments(argv)
    access = access or Access()
    base = args.base.resolve()
    try:
        prompt = args.prompt.read_text(encoding="utf-8")
        texts, read = tells.selected(base, access.which("git"), args)
    except (OSError, tells.StartUnresolved) as problem:
        print(f"voice review: {problem}")
        return 2
    try:
        backend = resolve_backend(args.model, args.fallback, access)
        outcome = review(backend, prompt, texts, args.workers, args.agree)
    except Unreachable as problem:
        notice = f"voice review: NOT RUN, no model could be reached ({problem.why}): {problem.detail}"
        return finish(args.report, {"status": "unreachable", "why": problem.why, "detail": problem.detail}, [notice])
    lines = [f"{item['where']}:{item['line']}: {item['rule']}: {item.get('quote', '')}" for item in outcome.kept]
    lines += [f"{item['where']}: not reviewed: {item['why']}" for item in outcome.unanswered]
    lines.append(
        f"voice review by {backend.model} through the {backend.name}: {len(outcome.kept)} findings, "
        f"{outcome.withdrawn} withdrawn by its own check, {outcome.dropped} dropped by verification, "
        f"{outcome.disagreed} not in all {args.agree} answers, {len(outcome.unanswered)} texts unanswered; {read}"
    )
    document: dict[str, Any] = {"status": "reviewed", "model": backend.model, "backend": backend.name, "agree": args.agree}
    document |= {"findings": outcome.kept, "withdrawn": outcome.withdrawn, "dropped": outcome.dropped}
    document |= {"disagreed": outcome.disagreed, "unanswered": outcome.unanswered}
    return finish(args.report, document, lines)


if __name__ == "__main__":
    sys.exit(main())
