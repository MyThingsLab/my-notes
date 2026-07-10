# my-notes — agent instructions

You are developing **my-notes**, a MyThingsLab My[X] tool.

**Inherited rules:** obey [`./HARNESS.md`](./HARNESS.md) in full — the vendored
MyThingsLab build-harness rules. Do not restate or override them. Anything not
covered here defers to `HARNESS.md`, then `my-things-core/docs/CONVENTIONS.md`.

## This tool

- **Purpose:** a personal freeform note-capture tool — a note is filed as a
  GitHub issue (mirroring MyIdea's issue-driven pattern); MyNotes reads the
  issue body, runs one Engine call to extract tags/topics and propose a
  concise title, and comments the structured result back on the issue.
- **The single Engine call:** "extract 3-7 tags/topics and propose one
  concise title for this note." Input: the (capped) note text plus
  `context = {"note_chars": int, "truncated": bool}`. Output:
  `data = {"title": str, "tags": [str]}` — tags bound to a max of 7, deduped.
  Against `NoopEngine`: `tags = []`, `title` falls back to the first
  non-empty line of the note text (truncated to ~60 chars).
- **Invariants / rules:** no `Workspace`, no PR — read-only utility, comment
  only side effect (via `Policy.evaluate()`, default-allow, no MyGuard
  dependency). No local-file mode — always requires `--issue` + `--repo`.
  Stateless: no cross-run corpus, no persistence beyond the one issue comment
  per run. Note text capped at 10,000 chars before it reaches the Engine
  prompt. Empty (whitespace-only) issue body short-circuits before the
  Engine call, outcome `skipped`.
- **Backlog label:** my-notes
