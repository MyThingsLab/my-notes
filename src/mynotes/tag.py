from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field

from mythings.engine import Engine, EngineRequest
from mythings.github import GitHub, _gh
from mythings.ledger import Ledger
from mythings.policy import Action, Decision, Policy

MAX_TAGS = 7
DEFAULT_MAX_CHARS = 10_000
TITLE_FALLBACK_CHARS = 60

Runner = Callable[[list[str]], str]

_SYSTEM = (
    "You extract structured metadata from a personal freeform note. Reply "
    'with only a JSON object of the shape {"title": str, "tags": [str, ...]}. '
    "Propose 3-7 tags/topics and one concise title. No prose, no markdown "
    "fences — JSON only."
)


@dataclass(frozen=True)
class TagResult:
    outcome: str  # success | skipped
    issue: int
    title: str = ""
    tags: list[str] = field(default_factory=list)
    posted: bool = False
    comment_url: str | None = None


def _fetch_issue_body(runner: Runner, repo: str | None, issue: int) -> tuple[str, str]:
    argv = ["issue", "view", str(issue), "--json", "number,title,body,url"]
    if repo:
        argv += ["--repo", repo]
    raw = json.loads(runner(argv))
    return raw.get("title", ""), raw.get("body", "") or ""


def _cap(text: str, max_chars: int) -> tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars], True


def _fallback_title(note_text: str) -> str:
    for line in note_text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:TITLE_FALLBACK_CHARS]
    return ""


def _dedupe_cap(tags: list[str]) -> list[str]:
    seen: list[str] = []
    for tag_value in tags:
        if tag_value not in seen:
            seen.append(tag_value)
        if len(seen) == MAX_TAGS:
            break
    return seen


def _propose(
    engine: Engine, note_text: str, note_chars: int, truncated: bool
) -> tuple[str, list[str]]:
    context = {"note_chars": note_chars, "truncated": truncated}
    result = engine.run(EngineRequest(prompt=note_text, system=_SYSTEM, context=context))
    try:
        payload = json.loads(result.text) if result.text else {}
    except json.JSONDecodeError:
        payload = {}
    if not payload:
        # Honest degrade (NoopEngine, or no usable reply): deterministic
        # fallback only, never fabricated tags.
        return _fallback_title(note_text), []
    title = str(payload.get("title") or "") or _fallback_title(note_text)
    tags = _dedupe_cap([str(t) for t in payload.get("tags", [])])
    return title, tags


def _render_comment(title: str, tags: list[str]) -> str:
    lines = ["## Note tagged", "", f"**Title:** {title}", ""]
    if tags:
        lines.append("**Tags:** " + ", ".join(f"`{t}`" for t in tags))
    return "\n".join(lines).rstrip() + "\n"


def tag(
    *,
    issue: int,
    engine: Engine,
    github: GitHub,
    policy: Policy,
    ledger: Ledger,
    runner: Runner = _gh,
    repo: str | None = None,
    comment: bool = False,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> TagResult:
    del github  # the gh/Runner boundary is used directly, same as MyIdea's comment path
    _, body = _fetch_issue_body(runner, repo, issue)
    note_text = body.strip()

    if not note_text:
        ledger.record(
            "mynotes",
            "note_tagged",
            "skipped",
            detail=f"issue #{issue}: empty note body",
            issue=issue,
            repo=repo,
            note_chars=0,
            truncated=False,
            title="",
            tags=[],
            comment_url=None,
        )
        return TagResult(outcome="skipped", issue=issue)

    capped, truncated = _cap(note_text, max_chars)
    title, tags = _propose(engine, capped, len(capped), truncated)

    posted = False
    comment_url = None
    if comment:
        action = Action(kind="issue-comment", payload={"issue": issue, "kind": "note_tagged"})
        if policy.evaluate(action).under(unattended=True) is Decision.ALLOW:
            body_text = _render_comment(title, tags)
            argv = ["issue", "comment", str(issue), "--body", body_text]
            if repo:
                argv += ["--repo", repo]
            comment_url = runner(argv).strip() or None
            posted = True

    ledger.record(
        "mynotes",
        "note_tagged",
        "success",
        detail=f"tagged issue #{issue} with {len(tags)} tags",
        issue=issue,
        repo=repo,
        note_chars=len(capped),
        truncated=truncated,
        title=title,
        tags=tags,
        comment_url=comment_url,
    )
    return TagResult(
        outcome="success",
        issue=issue,
        title=title,
        tags=tags,
        posted=posted,
        comment_url=comment_url,
    )
