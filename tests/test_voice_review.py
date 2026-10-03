"""Tests for `bin/voice-review.py`.

No test calls a model. The API backend is handed a fake connection that answers
the way the Messages API does, and the CLI backend a fake `run` that answers the
way `claude -p --output-format json` does, both through the `Access` the checker
takes, so nothing is patched.
"""

from __future__ import annotations

import json
import shutil
import subprocess  # nosec B404
import threading
from collections.abc import Callable
from pathlib import Path

import pytest
from conftest import ROOT, load, repository, script_argv

review = load("bin/voice-review.py")

PROMPT = ROOT / "config" / "prompts" / "voice-findings.md"
APHORISM = "Nothing in the engine can undo a click."


class Response:
    """What `getresponse()` returns: a status and a body."""

    def __init__(self, status: int, body: str):
        self.status = status
        self.body = body.encode()

    def read(self) -> bytes:
        """The body, once."""
        return self.body


class FakeAPI:
    """Answers each request from a function of the text it names, and keeps every request body."""

    def __init__(self, answer: Callable[[str, str], dict | str] | None = None, status: int = 200):
        self.answer: Callable[[str, str], dict | str] = answer or (lambda where, user: checked([]))
        self.status = status
        self.requests: list[dict] = []
        self.lock = threading.Lock()

    def __call__(self):
        """One connection per request, as the backend opens them."""
        return FakeConnection(self)


class FakeConnection:
    """Records the request and replies as the API would."""

    def __init__(self, api: FakeAPI):
        self.api = api
        self.body: dict = {}

    def request(self, method: str, path: str, body: str, headers: dict) -> None:
        """Keep what was sent, having checked it goes where the Messages API takes it."""
        assert (method, path, headers["x-api-key"]) == ("POST", "/v1/messages", "k")
        self.body = json.loads(body)
        with self.api.lock:
            self.api.requests.append(self.body)

    def getresponse(self) -> Response:
        """A message whose text is the answer for this request, or an error body."""
        user = self.body["messages"][0]["content"]
        where = user.splitlines()[0].removeprefix("text: ")
        if self.api.status != 200:
            return Response(self.api.status, json.dumps({"error": {"message": "nope"}}))
        answer = self.api.answer(where, user)
        text = answer if isinstance(answer, str) else json.dumps(answer)
        return Response(200, json.dumps({"content": [{"type": "text", "text": text}]}))


def claude_at(path: str):
    """A `which` that places claude where the test says and finds everything else, git included, for real."""
    return lambda name: path if name == "claude" else shutil.which(name)


def api_access(api: FakeAPI):
    """An Access with a key set and the fake connection in place."""
    return review.Access(env={"ANTHROPIC_API_KEY": "k"}, connect=api)


def run(tree: Path, access, *flags: str, capsys) -> tuple[int, dict, str]:
    """One in-process review over the whole tree, one answer per text unless the flags say otherwise."""
    report = tree.parent / "review.json"
    agree = () if "--agree" in flags else ("--agree", "1")
    code = review.main(["--all-files", "--base", str(tree), "--report", str(report), *agree, *flags], access)
    return code, json.loads(report.read_text(encoding="utf-8")), capsys.readouterr().out


def checked(drafts: list[dict], holds: list[bool] | None = None) -> dict:
    """An answer carrying these drafts and a check of each, every check holding unless told otherwise."""
    outcomes = holds if holds is not None else [True] * len(drafts)
    return {"draft": drafts, "checks": [{"draft": index, "holds": held, "why": "w"} for index, held in enumerate(outcomes)]}


def one_finding(rule: str, line: int, quote: str):
    """An answer that reports one finding for every text."""
    return lambda where, user: checked([{"line": line, "rule": rule, "quote": quote}])


# COVERS FR-10.1 | positive
def test_every_text_is_sent_whole_in_its_own_request(tmp_path, capsys):
    """A long document's last line reaches the model, and the comments go in a request of their own."""
    lines = [f"Line number {n} of a long document." for n in range(1, 401)]
    tree = repository(tmp_path, {"README.md": "# r\n\n" + "\n".join(lines) + "\n", "tool.go": "package main\n\n// A comment.\n"})
    api = FakeAPI()

    code, report, _ = run(tree, api_access(api), capsys=capsys)

    sent = {request["messages"][0]["content"].splitlines()[0]: request["messages"][0]["content"] for request in api.requests}
    assert code == 0 and report["status"] == "reviewed"
    assert set(sent) == {"text: README.md", "text: tool.go"}
    assert "402| Line number 400 of a long document." in sent["text: README.md"]


# COVERS FR-10.2 | positive
def test_the_prompt_file_is_sent_unchanged(tmp_path, capsys):
    """Every request carries the prompt as its system text."""
    tree = repository(tmp_path, {"README.md": "# r\n\nA sentence.\n"})
    api = FakeAPI()

    run(tree, api_access(api), capsys=capsys)

    assert api.requests and all(request["system"] == PROMPT.read_text(encoding="utf-8") for request in api.requests)


# COVERS FR-10.2 | negative
def test_a_finding_under_a_rule_not_asked_for_is_dropped(tmp_path, capsys):
    """The model does not get to invent a rule."""
    tree = repository(tmp_path, {"README.md": f"# r\n\n{APHORISM}\n"})

    _, report, _ = run(tree, api_access(FakeAPI(one_finding("em-dash", 3, APHORISM))), capsys=capsys)

    assert report["findings"] == [] and report["dropped"] == 1


# COVERS FR-10.3 | positive
def test_a_quote_on_its_line_stands_and_may_wrap(tmp_path, capsys):
    """A quote on the named line, and one that runs onto the next, both stand."""
    tree = repository(tmp_path, {"README.md": f"# r\n\n{APHORISM}\n\nA sentence that\nwraps onto the next line.\n"})

    def answer(where, user):
        return checked(
            [
                {"line": 3, "rule": "closing-aphorism", "quote": APHORISM},
                {"line": 5, "rule": "table-stakes", "quote": "A sentence that wraps onto the next line."},
            ]
        )

    code, report, output = run(tree, api_access(FakeAPI(answer)), capsys=capsys)

    assert code == 0
    assert [(f["line"], f["rule"]) for f in report["findings"]] == [(3, "closing-aphorism"), (5, "table-stakes")]
    assert f"README.md:3: closing-aphorism: {APHORISM}" in output


# COVERS FR-10.3 | negative
@pytest.mark.parametrize(
    ("line", "quote"),
    [(3, "Words that appear nowhere in the file."), (1, APHORISM), (99, APHORISM), ("3", APHORISM)],
)
def test_a_quote_not_starting_on_its_line_is_dropped(tmp_path, capsys, line, quote):
    """An invented quote, a real one on the wrong line, a line that does not exist, and a line that is not a number."""
    tree = repository(tmp_path, {"README.md": f"# r\n\n{APHORISM}\n"})

    _, report, output = run(tree, api_access(FakeAPI(one_finding("closing-aphorism", line, quote))), capsys=capsys)

    assert report["findings"] == [] and report["dropped"] == 1
    assert "0 findings, 0 withdrawn by its own check, 1 dropped by verification" in output


# COVERS FR-10.4 | positive
def test_findings_never_fail_the_run(tmp_path, capsys):
    """Findings are reported and the exit is still 0."""
    tree = repository(tmp_path, {"README.md": f"# r\n\n{APHORISM}\n"})

    code, report, _ = run(tree, api_access(FakeAPI(one_finding("closing-aphorism", 3, APHORISM))), capsys=capsys)

    assert code == 0 and len(report["findings"]) == 1


# COVERS FR-10.4 | negative
def test_a_wrong_command_or_repository_exits_two(tmp_path, capsys):
    """Two modes at once, a start that is not a commit, and a prompt that cannot be read."""
    tree = repository(tmp_path, {"README.md": "# r\n"})
    with pytest.raises(SystemExit) as refused:
        review.main(["--all-files", "README.md"], api_access(FakeAPI()))
    assert refused.value.code == 2

    (tree / ".voice-review-start").write_text("0123456789abcdef\n", encoding="utf-8")
    assert review.main(["--all-files", "--base", str(tree)], api_access(FakeAPI())) == 2
    (tree / ".voice-review-start").unlink()
    assert review.main(["--all-files", "--base", str(tree), "--prompt", str(tmp_path / "missing.md")], api_access(FakeAPI())) == 2
    assert "voice review:" in capsys.readouterr().out


# COVERS FR-10.5 | positive
@pytest.mark.parametrize(
    ("access", "why"),
    [
        (review.Access(env={}, which=lambda name: None), "no-credentials"),
        (review.Access(env={}, which=claude_at("/bin/claude"), run=None), "no-credentials"),
        (api_access(FakeAPI(status=401)), "no-credentials"),
        (api_access(FakeAPI(status=529)), "out-of-quota"),
        (api_access(FakeAPI(status=500)), "unavailable"),
        (api_access(FakeAPI(status=404)), "request-refused"),
    ],
)
def test_an_unreachable_model_is_reported_as_not_run(tmp_path, capsys, access, why):
    """No credentials, no CLI, a rejected key, no quota, an outage and a refused request all say NOT RUN and exit 0."""
    tree = repository(tmp_path, {"README.md": "# r\n\nA sentence.\n"})
    flags = ("--fallback", "none") if access.run is None else ()

    code, report, output = run(tree, access, *flags, capsys=capsys)

    assert code == 0
    assert report["status"] == "unreachable" and report["why"] == why
    assert "NOT RUN" in output


# COVERS FR-10.5 | edge
def test_an_answer_that_is_not_a_findings_list_leaves_only_that_text_unreviewed(tmp_path, capsys):
    """One text's answer is prose; the other text is still reviewed."""
    tree = repository(tmp_path, {"a.md": f"# a\n\n{APHORISM}\n", "b.md": "# b\n\nA sentence.\n"})

    def answer(where, user):
        return "I could not decide." if where == "b.md" else checked([{"line": 3, "rule": "closing-aphorism", "quote": APHORISM}])

    code, report, output = run(tree, api_access(FakeAPI(answer)), capsys=capsys)

    assert code == 0
    assert [f["where"] for f in report["findings"]] == ["a.md"]
    assert [item["where"] for item in report["unanswered"]] == ["b.md"]
    assert "b.md: not reviewed:" in output


# COVERS FR-10.1 | positive
def test_a_commit_message_file_is_reviewed_through_the_wording_modes(tmp_path, capsys):
    """The commit-msg mode sends the one message and nothing from the tree."""
    message = tmp_path / "COMMIT_EDITMSG"
    message.write_text("fix: a typo\n\nThe typo is gone.\n", encoding="utf-8")
    api = FakeAPI()

    code = review.main(["--commit-msg-filename", str(message), "--agree", "1"], api_access(api))

    assert code == 0
    assert [request["messages"][0]["content"].splitlines()[:2] for request in api.requests] == [["text: COMMIT_EDITMSG", "kind: commits"]]
    assert "one commit message" in capsys.readouterr().out


# COVERS FR-10.6 | positive
def test_the_api_request_carries_no_sampling_parameter(tmp_path, capsys):
    """The current models refuse temperature, so it is never sent."""
    tree = repository(tmp_path, {"README.md": "# r\n\nA sentence.\n"})
    api = FakeAPI()

    run(tree, api_access(api), "--model", "claude-opus-5", capsys=capsys)

    assert api.requests[0]["model"] == "claude-opus-5"
    assert not {"temperature", "top_p", "top_k"} & set(api.requests[0])


# COVERS FR-10.6 | positive
def test_without_a_key_the_cli_is_asked_with_no_tools_or_settings(tmp_path, capsys):
    """The CLI fallback passes the prompt as the system prompt and the text on stdin."""
    tree = repository(tmp_path, {"README.md": f"# r\n\n{APHORISM}\n"})
    calls: list[tuple[list[str], str]] = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs["input"]))
        result = json.dumps(checked([{"line": 3, "rule": "closing-aphorism", "quote": APHORISM}]))
        return subprocess.CompletedProcess(argv, 0, json.dumps({"result": result, "is_error": False}), "")

    access = review.Access(env={}, which=claude_at("/usr/bin/claude"), run=fake_run)
    code, report, output = run(tree, access, capsys=capsys)

    argv, stdin = calls[0]
    assert code == 0 and len(report["findings"]) == 1
    assert argv[:2] == ["/usr/bin/claude", "-p"] and argv[argv.index("--tools") + 1] == ""
    assert argv[argv.index("--system-prompt") + 1] == PROMPT.read_text(encoding="utf-8")
    assert stdin.startswith("text: README.md") and "through the cli" in output


# COVERS FR-10.6 | negative
@pytest.mark.parametrize(
    ("returned", "why"),
    [
        (subprocess.CompletedProcess([], 1, json.dumps({"result": "Not logged in", "is_error": True}), ""), "no-credentials"),
        (subprocess.CompletedProcess([], 1, json.dumps({"result": "usage limit reached", "is_error": True}), ""), "out-of-quota"),
        (subprocess.CompletedProcess([], 1, json.dumps({"result": "something broke", "is_error": True}), ""), "cli-failed"),
        (subprocess.CompletedProcess([], 2, "not json", "crashed"), "cli-failed"),
        (subprocess.TimeoutExpired("claude", 600), "offline"),
    ],
)
def test_a_cli_that_cannot_answer_is_unreachable(tmp_path, capsys, returned, why):
    """A missing login, a spent quota, a CLI error, garbage output and a hang."""
    tree = repository(tmp_path, {"README.md": "# r\n\nA sentence.\n"})

    def fake_run(argv, **kwargs):
        if isinstance(returned, Exception):
            raise returned
        return returned

    code, report, _ = run(tree, review.Access(env={}, which=claude_at("/usr/bin/claude"), run=fake_run), capsys=capsys)

    assert code == 0 and report["status"] == "unreachable" and report["why"] == why


# COVERS FR-10.6 | edge
def test_an_api_body_that_is_not_a_message_leaves_the_text_unanswered(tmp_path, capsys):
    """A 200 whose body cannot be read is an answer problem, not an outage."""
    tree = repository(tmp_path, {"README.md": "# r\n\nA sentence.\n"})

    class Broken(FakeConnection):
        def getresponse(self) -> Response:
            return Response(200, "not json")

    code, report, _ = run(tree, review.Access(env={"ANTHROPIC_API_KEY": "k"}, connect=lambda: Broken(FakeAPI())), capsys=capsys)

    assert code == 0 and [item["where"] for item in report["unanswered"]] == ["README.md"]


# COVERS FR-10.6 | edge
def test_a_connection_failure_is_offline(tmp_path, capsys):
    """A socket error before any response is reported as offline."""
    tree = repository(tmp_path, {"README.md": "# r\n\nA sentence.\n"})

    def refuse():
        raise OSError("connection refused")

    code, report, _ = run(tree, review.Access(env={"ANTHROPIC_API_KEY": "k"}, connect=refuse), capsys=capsys)

    assert code == 0 and report["why"] == "offline"


# COVERS FR-10.7 | positive
def test_the_report_names_the_model_backend_findings_and_counts(tmp_path, capsys):
    """Everything a later reader needs is in the JSON."""
    tree = repository(tmp_path, {"README.md": f"# r\n\n{APHORISM}\n"})

    _, report, _ = run(tree, api_access(FakeAPI(one_finding("closing-aphorism", 3, APHORISM))), capsys=capsys)

    assert report["model"] == "claude-sonnet-5" and report["backend"] == "api"
    assert report["findings"] == [{"where": "README.md", "line": 3, "rule": "closing-aphorism", "quote": APHORISM}]
    assert report["withdrawn"] == 0 and report["dropped"] == 0 and report["unanswered"] == []


# COVERS FR-10.8 | positive
def test_only_a_draft_its_own_check_holds_is_kept(tmp_path, capsys):
    """Two drafts, one check holding and one not: one finding stands and one is withdrawn."""
    tree = repository(tmp_path, {"README.md": f"# r\n\n{APHORISM}\n\nA plain sentence.\n"})
    drafts = [{"line": 3, "rule": "closing-aphorism", "quote": APHORISM}, {"line": 5, "rule": "table-stakes", "quote": "A plain sentence."}]

    _, report, output = run(tree, api_access(FakeAPI(lambda where, user: checked(drafts, [True, False]))), capsys=capsys)

    assert [f["line"] for f in report["findings"]] == [3]
    assert report["withdrawn"] == 1 and report["dropped"] == 0
    assert "1 findings, 1 withdrawn by its own check" in output


# COVERS FR-10.8 | negative
@pytest.mark.parametrize(
    "answer",
    [
        {"draft": [{"line": 3, "rule": "closing-aphorism", "quote": APHORISM}], "checks": []},
        {"draft": [{"line": 3, "rule": "closing-aphorism", "quote": APHORISM}], "checks": [{"draft": 0, "holds": "yes"}]},
        {"draft": [{"line": 3, "rule": "closing-aphorism", "quote": APHORISM}], "checks": [{"draft": 1, "holds": True}]},
    ],
)
def test_a_draft_with_no_holding_check_is_withdrawn(tmp_path, capsys, answer):
    """No check at all, a check that is not true, and a check naming another draft all withdraw it."""
    tree = repository(tmp_path, {"README.md": f"# r\n\n{APHORISM}\n"})

    _, report, _ = run(tree, api_access(FakeAPI(lambda where, user: answer)), capsys=capsys)

    assert report["findings"] == [] and report["withdrawn"] == 1


# COVERS FR-10.8 | edge
def test_an_answer_with_findings_but_no_checks_is_unanswered(tmp_path, capsys):
    """The unchecked shape is not accepted, so the check cannot be skipped by answering the old way."""
    tree = repository(tmp_path, {"README.md": f"# r\n\n{APHORISM}\n"})
    unchecked = {"findings": [{"line": 3, "rule": "closing-aphorism", "quote": APHORISM}]}

    _, report, _ = run(tree, api_access(FakeAPI(lambda where, user: unchecked)), capsys=capsys)

    assert report["findings"] == [] and [item["where"] for item in report["unanswered"]] == ["README.md"]


def alternating(*answers: dict):
    """An answer function returning each answer in turn, one per request."""
    calls = iter(range(10_000))
    return lambda where, user: answers[next(calls) % len(answers)]


# COVERS FR-10.9 | positive
def test_a_finding_stands_only_when_every_answer_reports_it(tmp_path, capsys):
    """Two answers share one finding and differ on another: the shared one stands and the other is counted."""
    tree = repository(tmp_path, {"README.md": f"# r\n\n{APHORISM}\n\nA plain sentence.\n"})
    shared = {"line": 3, "rule": "closing-aphorism", "quote": APHORISM}
    extra = {"line": 5, "rule": "table-stakes", "quote": "A plain sentence."}
    api = FakeAPI(alternating(checked([shared, extra]), checked([shared])))

    _, report, output = run(tree, api_access(api), "--agree", "2", capsys=capsys)

    assert len(api.requests) == 2
    assert [(f["line"], f["rule"]) for f in report["findings"]] == [(3, "closing-aphorism")]
    assert report["agree"] == 2 and report["disagreed"] == 1
    assert "1 not in all 2 answers" in output


# COVERS FR-10.9 | positive
def test_two_answers_per_text_is_the_default(tmp_path, capsys):
    """With no flag, each text is asked twice."""
    tree = repository(tmp_path, {"README.md": f"# r\n\n{APHORISM}\n"})
    api = FakeAPI()
    report = tmp_path / "review.json"

    review.main(["--all-files", "--base", str(tree), "--report", str(report)], api_access(api))

    assert len(api.requests) == 2 and json.loads(report.read_text(encoding="utf-8"))["agree"] == 2


# COVERS FR-10.9 | edge
def test_answers_that_share_nothing_leave_no_finding(tmp_path, capsys):
    """Each answer finds something different, so nothing stands and both are counted as not agreed."""
    tree = repository(tmp_path, {"README.md": f"# r\n\n{APHORISM}\n\nA plain sentence.\n"})
    first = checked([{"line": 3, "rule": "closing-aphorism", "quote": APHORISM}])
    second = checked([{"line": 5, "rule": "table-stakes", "quote": "A plain sentence."}])

    _, report, _ = run(tree, api_access(FakeAPI(alternating(first, second))), "--agree", "2", capsys=capsys)

    assert report["findings"] == [] and report["disagreed"] == 2


# COVERS FR-10.4 | positive
def test_the_script_runs_by_path_and_says_not_run_without_a_model(tmp_path):
    """Spawned as a hook would spawn it, with no fallback, it exits 0 and says why nothing ran."""
    tree = repository(tmp_path, {"README.md": "# r\n\nA sentence.\n"})
    argv = script_argv(ROOT / "bin" / "voice-review.py", "--all-files", "--fallback", "none")

    result = subprocess.run(argv, cwd=tree, capture_output=True, text=True, check=False, env={"PATH": "/usr/bin:/bin"})  # nosec B603

    assert result.returncode == 0
    assert "NOT RUN" in result.stdout
