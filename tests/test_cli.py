from __future__ import annotations

import json
from pathlib import Path

import pytest
from mythings.engine import ClaudeCLIEngine, NoopEngine

from mynotes import cli
from mynotes.tag import TagResult


def test_build_engine_noop_by_default() -> None:
    assert isinstance(cli._build_engine("noop", None), NoopEngine)


def test_build_engine_claude_cli() -> None:
    assert isinstance(cli._build_engine("claude-cli", None), ClaudeCLIEngine)


def test_tag_prints_json(monkeypatch, tmp_path: Path, capsys) -> None:
    result = TagResult(outcome="success", issue=5, title="a title", tags=["a", "b"], posted=True)
    monkeypatch.setattr(cli, "tag", lambda **kwargs: result)

    code = cli.main(
        ["tag", "--repo", "o/r", "--issue", "5", "--ledger", str(tmp_path / "l.jsonl"), "--json"]
    )
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["title"] == "a title"
    assert out["tags"] == ["a", "b"]
    assert out["posted"] is True


def test_tag_prints_summary_without_json_flag(monkeypatch, tmp_path: Path, capsys) -> None:
    result = TagResult(outcome="success", issue=5, title="a title", tags=["a", "b"], posted=False)
    monkeypatch.setattr(cli, "tag", lambda **kwargs: result)

    cli.main(["tag", "--repo", "o/r", "--issue", "5", "--ledger", str(tmp_path / "l.jsonl")])
    out = capsys.readouterr().out
    assert "a title" in out
    assert "comment NOT posted" in out


def test_tag_prints_skip_message(monkeypatch, tmp_path: Path, capsys) -> None:
    result = TagResult(outcome="skipped", issue=6)
    monkeypatch.setattr(cli, "tag", lambda **kwargs: result)

    cli.main(["tag", "--repo", "o/r", "--issue", "6", "--ledger", str(tmp_path / "l.jsonl")])
    out = capsys.readouterr().out
    assert "empty note body" in out


def test_new_files_a_note_and_prints_the_url(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from mythings.github import Issue

    from mynotes import cli as cli_mod

    created = Issue(number=9, title="a thought", body="", url="https://github.com/o/r/issues/9")
    monkeypatch.setattr(cli_mod, "file_note", lambda **kwargs: created)

    code = cli_mod.main(
        ["new", "a thought", "--repo", "o/r", "--ledger", str(tmp_path / "l.jsonl")]
    )

    assert code == 0
    assert "filed note #9" in capsys.readouterr().out


def test_new_exits_nonzero_when_policy_denies(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from mynotes import cli as cli_mod

    monkeypatch.setattr(cli_mod, "file_note", lambda **kwargs: None)

    code = cli_mod.main(
        ["new", "a thought", "--repo", "o/r", "--ledger", str(tmp_path / "l.jsonl")]
    )

    assert code == 1
    assert "denied by policy" in capsys.readouterr().out


def test_new_json_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from mythings.github import Issue

    from mynotes import cli as cli_mod

    created = Issue(number=9, title="a thought", body="", url="https://github.com/o/r/issues/9")
    monkeypatch.setattr(cli_mod, "file_note", lambda **kwargs: created)

    cli_mod.main(
        ["new", "a thought", "--repo", "o/r", "--json", "--ledger", str(tmp_path / "l.jsonl")]
    )

    assert json.loads(capsys.readouterr().out) == {
        "issue": 9,
        "url": "https://github.com/o/r/issues/9",
    }
