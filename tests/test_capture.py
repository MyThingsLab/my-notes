from __future__ import annotations

import json
from pathlib import Path

import pytest
from mythings.github import GitHub, GitHubError
from mythings.ledger import Ledger
from mythings.policy import ALLOW, Action, Decision, PolicyResult

from mynotes.capture import NOTE_LABEL, file_note


class FakeGh:
    # The `gh` subprocess is the one mocked boundary, same as test_tag.py.
    def __init__(self, *, label_missing: bool = False) -> None:
        self.calls: list[list[str]] = []
        self._label_missing = label_missing
        self._label_created = False

    def __call__(self, argv: list[str]) -> str:
        self.calls.append(argv)
        if argv[:2] == ["issue", "create"]:
            return "https://github.com/o/r/issues/9\n"
        if argv[:2] == ["issue", "edit"]:
            if self._label_missing and not self._label_created:
                raise GitHubError("could not add label: 'my-notes' not found")
            return ""
        if argv[:2] == ["label", "create"]:
            self._label_created = True
            return ""
        if argv[:2] == ["issue", "list"]:
            return json.dumps([])
        raise AssertionError(f"unexpected gh call: {argv}")


class _Deny:
    def evaluate(self, action: Action) -> PolicyResult:
        return PolicyResult(Decision.DENY, reason="no", rule="deny")


class _Ask:
    def evaluate(self, action: Action) -> PolicyResult:
        return PolicyResult(Decision.ASK, reason="confirm", rule="ask")


class _Allow:
    def evaluate(self, action: Action) -> PolicyResult:
        return ALLOW


def _file(fake: FakeGh, ledger: Ledger, policy=None, *, title="a thought", body=""):
    return file_note(
        title=title,
        body=body,
        github=GitHub(repo="o/r", runner=fake),
        policy=policy or _Allow(),
        ledger=ledger,
        runner=fake,
    )


def test_file_note_creates_labels_and_records(tmp_path: Path) -> None:
    fake = FakeGh()
    ledger = Ledger(tmp_path / "l.jsonl")

    created = _file(fake, ledger, title="caching strategies", body="look into it")

    assert created is not None
    assert created.number == 9
    assert ["issue", "create"] == fake.calls[0][:2]
    assert any(argv[:2] == ["issue", "edit"] for argv in fake.calls)  # the label

    entry = ledger.read(tool="mynotes", kind="note_filed")[0]
    assert entry.outcome == "success"
    assert entry.data["note_issue"] == 9


def test_file_note_falls_back_when_the_body_is_empty(tmp_path: Path) -> None:
    fake = FakeGh()

    _file(fake, Ledger(tmp_path / "l.jsonl"), body="")

    create = next(argv for argv in fake.calls if argv[:2] == ["issue", "create"])
    body = create[create.index("--body") + 1]
    assert body.strip() != ""


def test_file_note_denied_by_policy_creates_nothing(tmp_path: Path) -> None:
    fake = FakeGh()
    ledger = Ledger(tmp_path / "l.jsonl")

    assert _file(fake, ledger, _Deny()) is None
    assert fake.calls == []
    assert list(ledger) == []


def test_file_note_fails_closed_when_policy_would_ask(tmp_path: Path) -> None:
    # Unattended callers (the Telegram daemon) have nobody to ask.
    fake = FakeGh()

    assert _file(fake, Ledger(tmp_path / "l.jsonl"), _Ask()) is None
    assert fake.calls == []


def test_file_note_creates_the_label_once_on_a_fresh_repo(tmp_path: Path) -> None:
    # First note against a repo that has no my-notes label yet: create it, retry.
    fake = FakeGh(label_missing=True)

    created = _file(fake, Ledger(tmp_path / "l.jsonl"))

    assert created is not None
    label_create = [argv for argv in fake.calls if argv[:2] == ["label", "create"]]
    assert len(label_create) == 1
    assert NOTE_LABEL in label_create[0]
    # edit attempted, failed, label created, edit retried
    assert [argv[:2] for argv in fake.calls].count(["issue", "edit"]) == 2


def test_file_note_propagates_a_second_label_failure(tmp_path: Path) -> None:
    class AlwaysFails(FakeGh):
        def __call__(self, argv: list[str]) -> str:
            self.calls.append(argv)
            if argv[:2] == ["issue", "create"]:
                return "https://github.com/o/r/issues/9\n"
            if argv[:2] == ["issue", "edit"]:
                raise GitHubError("still broken")
            return ""

    with pytest.raises(GitHubError, match="still broken"):
        _file(AlwaysFails(), Ledger(tmp_path / "l.jsonl"))
