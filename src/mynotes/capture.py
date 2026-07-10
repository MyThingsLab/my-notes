from __future__ import annotations

from mythings.github import GitHub, GitHubError, Issue, _gh
from mythings.ledger import Ledger
from mythings.policy import Action, Decision, Policy

from mynotes.tag import Runner

# The filing half of "a note is filed as a GitHub issue". `tag` has always
# assumed the issue already exists; nothing in this tool could create one, so a
# note could only be captured by hand on github.com first.
#
# Deliberately separate from `tag`: filing is deterministic and makes no Engine
# call. A caller that wants both (MyTelegramBot's /note) composes them, exactly
# as MyIdea's own `file_idea` + `explore` are composed.

NOTE_LABEL = "my-notes"
NOTE_LABEL_DESCRIPTION = "A freeform note captured for MyNotes to tag"
NOTE_LABEL_COLOR = "c5def5"

_EMPTY_BODY_FALLBACK = "(no additional detail)"


def _ensure_note_label(runner: Runner, repo: str | None) -> None:
    argv = [
        "label",
        "create",
        NOTE_LABEL,
        "--description",
        NOTE_LABEL_DESCRIPTION,
        "--color",
        NOTE_LABEL_COLOR,
        "--force",
    ]
    if repo:
        argv += ["--repo", repo]
    runner(argv)


def file_note(
    *,
    title: str,
    github: GitHub,
    policy: Policy,
    ledger: Ledger,
    body: str = "",
    runner: Runner = _gh,
) -> Issue | None:
    # Mirrors myidea.file_idea: one Policy gate, one issue, one label, one ledger
    # entry. Returns None when the gate refuses, so a caller can say so without
    # having to interpret an exception.
    action = Action(kind="issue-create", payload={"title": title, "label": NOTE_LABEL})
    if policy.evaluate(action).under(unattended=True) is not Decision.ALLOW:
        return None

    created = github.create_issue(title=title, body=body or _EMPTY_BODY_FALLBACK)
    try:
        github.add_labels(created.number, [NOTE_LABEL])
    except GitHubError:
        # First note filed against a fresh repo: the label doesn't exist yet.
        # Create it (idempotent via --force) and retry once.
        _ensure_note_label(runner, github.repo)
        github.add_labels(created.number, [NOTE_LABEL])

    ledger.record(
        "mynotes",
        "note_filed",
        "success",
        detail=f"filed note #{created.number}: {title}",
        note_issue=created.number,
    )
    return created
