from __future__ import annotations

import json
from pathlib import Path

from mythings.engine import ClaudeCLIEngine, NoopEngine

from mynotes import cli
from mynotes.tag import TagResult


def test_build_engine_noop_by_default() -> None:
    assert isinstance(cli._build_engine("noop", None), NoopEngine)


def test_build_engine_claude_cli() -> None:
    assert isinstance(cli._build_engine("claude-cli", None), ClaudeCLIEngine)


def test_tag_prints_json(monkeypatch, tmp_path: Path, capsys) -> None:
    result = TagResult(
        outcome="success", issue=5, title="a title", tags=["a", "b"], posted=True
    )
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
