# my-notes

[![CI](https://github.com/MyThingsLab/my-notes/actions/workflows/ci.yml/badge.svg)](https://github.com/MyThingsLab/my-notes/actions/workflows/ci.yml) [![codecov](https://codecov.io/gh/MyThingsLab/my-notes/branch/main/graph/badge.svg)](https://codecov.io/gh/MyThingsLab/my-notes) ![Python](https://img.shields.io/badge/python-3.11%2B-blue) [![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

A [MyThingsLab](../my-things-core) `My[X]` tool for personal freeform note
capture. A note is filed as a GitHub issue (mirroring MyIdea's issue-driven
pattern); MyNotes reads the issue body, runs one Engine call to extract
tags/topics and propose a concise title, and comments the structured result
back on the issue.

Standalone v0 — no shared storage backend with MyIdea or a future MyWiki, no
`Workspace`, no PR. See
[`my-things-core/docs/tools/my-notes.md`](../my-things-core/docs/tools/my-notes.md)
for the design doc.

## CLI

```
mynotes tag --repo owner/name --issue N [--comment] [--json] \
            [--engine noop|claude-cli] [--engine-model ...] \
            [--ledger path] [--max-chars 10000]
```

## Install (development)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ../my-things-core -e ".[dev]"
pytest
```

## License

MIT — see [`LICENSE`](LICENSE).
