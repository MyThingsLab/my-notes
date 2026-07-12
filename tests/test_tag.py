from __future__ import annotations

import json
from pathlib import Path

from mythings.engine import EngineRequest, EngineResult, NoopEngine
from mythings.github import GitHub
from mythings.ledger import Ledger
from mythings.policy import ALLOW, Action, Decision, Policy, PolicyResult
from mythings.testing import ScriptedEngine

from mynotes.tag import tag

NOTE_ISSUE = {
    "number": 5,
    "title": "random thought",
    "body": "Remind myself to look into caching strategies for the fleet dispatcher.\n"
    "Also: check if my-server's read-only posture generalizes.",
    "url": "https://github.com/o/r/issues/5",
    "labels": [{"name": "my-notes"}],
}

EMPTY_ISSUE = {
    "number": 6,
    "title": "empty note",
    "body": "   \n\t  ",
    "url": "https://github.com/o/r/issues/6",
    "labels": [{"name": "my-notes"}],
}


class FakeGh:
    def __init__(self, issue: dict) -> None:
        self.issue = issue
        self.calls: list[list[str]] = []
        self.comments: list[str] = []

    def __call__(self, argv: list[str]) -> str:
        self.calls.append(argv)
        if argv[:2] == ["issue", "view"]:
            return json.dumps(self.issue)
        if argv[:2] == ["issue", "comment"]:
            self.comments.append(argv[argv.index("--body") + 1])
            return "https://github.com/o/r/issues/5#issuecomment-1\n"
        raise AssertionError(f"unexpected gh call: {argv}")


def scripted(payload: dict) -> ScriptedEngine:
    return ScriptedEngine(json.dumps(payload))





class SpyEngine:
    def __init__(self) -> None:
        self.calls: list[EngineRequest] = []

    def run(self, request: EngineRequest) -> EngineResult:
        self.calls.append(request)
        raise AssertionError("Engine must not be called for an empty note")


class DenyAll:
    def evaluate(self, action: Action) -> PolicyResult:
        return PolicyResult(Decision.DENY)


class AllowAll:
    def evaluate(self, action: Action) -> PolicyResult:
        return ALLOW


TAGGED = {
    "title": "Look into fleet-dispatcher caching",
    "tags": ["caching", "fleet-dispatcher", "my-server", "performance"],
}


def _tag(fake: FakeGh, engine, policy: Policy, tmp_path: Path, **kwargs):
    return tag(
        issue=fake.issue["number"],
        engine=engine,
        github=GitHub(repo="o/r", runner=fake),
        policy=policy,
        ledger=Ledger(tmp_path / "ledger.jsonl"),
        runner=fake,
        repo="o/r",
        **kwargs,
    )


def test_tag_happy_path_extracts_tags_and_posts_comment(tmp_path: Path) -> None:
    fake = FakeGh(NOTE_ISSUE)
    engine = scripted(TAGGED)

    result = _tag(fake, engine, AllowAll(), tmp_path, comment=True)

    assert result.outcome == "success"
    assert result.title == "Look into fleet-dispatcher caching"
    assert result.tags == ["caching", "fleet-dispatcher", "my-server", "performance"]
    assert len(engine.calls) == 1  # exactly one Engine call
    assert result.posted
    assert result.comment_url == "https://github.com/o/r/issues/5#issuecomment-1"
    (comment,) = fake.comments
    assert "caching" in comment
    assert "Look into fleet-dispatcher caching" in comment

    entries = list(Ledger(tmp_path / "ledger.jsonl"))
    assert entries[-1].kind == "note_tagged"
    assert entries[-1].outcome == "success"
    assert entries[-1].data["issue"] == 5
    assert entries[-1].data["tags"] == result.tags


def test_tag_caps_and_dedupes_at_seven_tags(tmp_path: Path) -> None:
    fake = FakeGh(NOTE_ISSUE)
    payload = {
        "title": "many tags",
        "tags": ["a", "b", "a", "c", "d", "e", "f", "g", "h", "i"],
    }
    result = _tag(fake, scripted(payload), AllowAll(), tmp_path)

    assert result.tags == ["a", "b", "c", "d", "e", "f", "g"]


def test_tag_skips_engine_call_for_empty_body(tmp_path: Path) -> None:
    fake = FakeGh(EMPTY_ISSUE)
    result = _tag(fake, SpyEngine(), AllowAll(), tmp_path, comment=True)

    assert result.outcome == "skipped"
    assert result.tags == []
    assert not result.posted
    assert fake.comments == []

    entries = list(Ledger(tmp_path / "ledger.jsonl"))
    assert entries[-1].kind == "note_tagged"
    assert entries[-1].outcome == "skipped"


def test_noop_engine_degrades_to_first_line_title(tmp_path: Path) -> None:
    fake = FakeGh(NOTE_ISSUE)
    result = _tag(fake, NoopEngine(), AllowAll(), tmp_path)

    assert result.outcome == "success"
    assert result.tags == []
    assert result.title == "Remind myself to look into caching strategies for the fleet dispatch"[
        :60
    ] or result.title.startswith("Remind myself to look into caching strategies")


def test_policy_deny_blocks_comment_but_still_records(tmp_path: Path) -> None:
    fake = FakeGh(NOTE_ISSUE)
    result = _tag(fake, scripted(TAGGED), DenyAll(), tmp_path, comment=True)

    assert result.outcome == "success"
    assert not result.posted
    assert fake.comments == []

    entries = list(Ledger(tmp_path / "ledger.jsonl"))
    assert entries[-1].data["comment_url"] is None


def test_note_text_is_capped_before_reaching_engine(tmp_path: Path) -> None:
    long_issue = dict(NOTE_ISSUE, body="x" * 20_000, number=7)
    fake = FakeGh(long_issue)
    engine = scripted(TAGGED)

    result = _tag(fake, engine, AllowAll(), tmp_path, max_chars=10_000)

    (request,) = engine.calls
    assert len(request.prompt) <= 10_100  # capped, plus small framing overhead
    assert request.context["note_chars"] == 10_000
    assert request.context["truncated"] is True
    assert result.outcome == "success"
