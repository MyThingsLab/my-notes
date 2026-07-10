from __future__ import annotations

import argparse
import json
from pathlib import Path

from mythings.engine import ClaudeCLIEngine, Engine, NoopEngine
from mythings.github import GitHub
from mythings.ledger import Ledger
from mythings.policy import ALLOW, Action, Policy, PolicyResult

from mynotes.capture import file_note
from mynotes.tag import tag

_ENGINES: dict[str, type[Engine]] = {"noop": NoopEngine, "claude-cli": ClaudeCLIEngine}
_LEDGER_PATH = Path(".mythings") / "ledger.jsonl"


class _AllowPolicy:
    # Comment-only side effect, default-allow — no MyGuard dependency for v0.
    def evaluate(self, action: Action) -> PolicyResult:
        return ALLOW


def _build_engine(name: str, model: str | None) -> Engine:
    if name == "claude-cli":
        return ClaudeCLIEngine(model=model)
    return _ENGINES[name]()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mynotes")
    sub = parser.add_subparsers(dest="cmd", required=True)

    new_cmd = sub.add_parser("new", help="file a note as a GitHub issue")
    new_cmd.add_argument("title")
    new_cmd.add_argument("--repo", required=True, help="owner/name")
    new_cmd.add_argument("--body", default="", help="extra detail for the note body")
    new_cmd.add_argument("--json", action="store_true", dest="as_json")
    new_cmd.add_argument("--ledger", default=None)

    tag_cmd = sub.add_parser("tag", help="extract tags/title for a note issue")
    tag_cmd.add_argument("--repo", required=True, help="owner/name")
    tag_cmd.add_argument("--issue", type=int, required=True)
    tag_cmd.add_argument(
        "--comment", action="store_true", help="post the result as an issue comment"
    )
    tag_cmd.add_argument("--json", action="store_true", dest="as_json")
    tag_cmd.add_argument("--engine", choices=sorted(_ENGINES), default="noop")
    tag_cmd.add_argument("--engine-model", default=None)
    tag_cmd.add_argument("--ledger", default=None)
    tag_cmd.add_argument("--max-chars", type=int, default=10_000)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.cmd == "new":
        ledger = Ledger(Path(args.ledger) if args.ledger else _LEDGER_PATH)
        created = file_note(
            title=args.title,
            body=args.body,
            github=GitHub(repo=args.repo),
            policy=_AllowPolicy(),
            ledger=ledger,
        )
        if created is None:
            print("mynotes: filing was denied by policy — nothing was created")
            return 1
        if args.as_json:
            print(json.dumps({"issue": created.number, "url": created.url}))
        else:
            print(f"filed note #{created.number}: {created.url}")
        return 0

    if args.cmd == "tag":
        github = GitHub(repo=args.repo)
        ledger = Ledger(Path(args.ledger) if args.ledger else _LEDGER_PATH)
        policy: Policy = _AllowPolicy()
        result = tag(
            issue=args.issue,
            engine=_build_engine(args.engine, args.engine_model),
            github=github,
            policy=policy,
            ledger=ledger,
            repo=args.repo,
            comment=args.comment,
            max_chars=args.max_chars,
        )
        if args.as_json:
            print(
                json.dumps(
                    {
                        "outcome": result.outcome,
                        "issue": result.issue,
                        "title": result.title,
                        "tags": result.tags,
                        "posted": result.posted,
                        "comment_url": result.comment_url,
                    }
                )
            )
        else:
            if result.outcome == "skipped":
                print(f"mynotes: issue #{result.issue} has an empty note body, skipped")
            else:
                print(
                    f"tagged #{result.issue}: {result.title!r} ({len(result.tags)} tags)"
                    f" ({'comment posted' if result.posted else 'comment NOT posted'})"
                )
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
