# docs2md

Converts documents (docx, pptx, xlsx, and more) to Markdown via pandoc, optionally syncs to GitLab/GitHub/Azure DevOps. Primary use case: feeding a RAG knowledge base.

## Quick Start

| Step | Command |
|---|---|
| 1. Install pandoc | [pandoc.org](https://pandoc.org/installing.html) |
| 2. Configure | edit `docs2md.yaml` |
| 3. Run | `python docs2md.py` |
| 4. Test | `python -m pytest tests/` |

## Key Tags (in `README.md` files)

| Tag | Effect |
|---|---|
| `doc2md#aikb` | Opt-in directory for processing |
| `doc2md#skipdir` | Skip this directory |
| `doc2md#skipfile` | Skip a specific file |
| `doc2md#mask=<glob>'` | Only process files matching wildcard pattern (e.g. `*Transcript.docx`) |
