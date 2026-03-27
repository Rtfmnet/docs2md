# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**docs2md** converts documents (docx, pptx, xlsx, etc.) to Markdown using pandoc, then optionally syncs them to GitLab via its REST API. The primary use case is feeding a RAG knowledge base. It is a config-driven, non-CLI tool (no argument parsing — only `docs2md.yaml`).

## Commands

```bash
# Run the tool
python docs2md.py

# Run all tests
python -m pytest tests/

# Run a single test file
python -m pytest tests/test_docs2md.py
python -m pytest tests/test_integration_docs2md.py
python -m pytest tests/test_git_manager.py
python -m pytest tests/test_tool.py

# Run a single test class or method
python -m pytest tests/test_docs2md.py::TestConvertToMarkdown
python -m pytest tests/test_docs2md.py::TestConvertToMarkdown::test_convert_success
```

**Prerequisites:** `pandoc` must be installed and on PATH. GitLab push requires `GIT_ACCESS_TOKEN` in `.env`.

## Architecture

All core logic lives in two files:

- **`docs2md.py`** — the entire application: config loading, logging setup, pandoc verification, recursive directory processing, and the main processing pipeline.
- **`git_manager.py`** — `GitManager` class: validates GitLab URLs and pushes files via the GitLab Repository Files API (HEAD to check existence, then POST or PUT).

The `tools/` directory contains standalone utility scripts (bulk converter, md merger, docx converter, transcript sanitizer) that are **not integrated** into the main pipeline.

## Processing Algorithm

The main pipeline (`docs2md.py`) processes each directory under `root_folder`:

1. **Directory evaluation** — skip if no `README.md`; skip if README contains `doc2md#skipdir`
2. **File collection** — gather all files with supported extensions; if `doc2md#mask='<regex>'` tags exist in README, keep only files matching at least one mask
3. **File filtering** — keep files referenced in README (word-boundary, case-insensitive match on filename with or without extension); remove files whose reference line contains `doc2md#skipfile`; if no masks defined and file not referenced — remove it
4. **File processing** — convert via pandoc; skip if `.md` already exists and source is not newer (unless `force_md_generation: true`); place output in `md/` subdirectory if it exists; append source extension to filename if name collision (e.g., `report_docx.md`)

## Key Tags (in directory README.md files)

| Tag | Effect |
|-----|--------|
| `doc2md#aikb` | Required to opt-in a directory for processing |
| `doc2md#skipdir` | Skip this directory and all subdirectories |
| `doc2md#skipfile` | On a file's reference line — skip that file |
| `doc2md#mask='<regex>'` | Only process files matching this regex pattern |

## Configuration (`docs2md.yaml`)

Key fields:
- `root_folder` — directory to scan (relative or absolute)
- `force_md_generation` — regenerate `.md` even if up to date
- `git_commit` — push converted files to GitLab
- `force_readme_git_commit` — also push `README.md` files to GitLab
- `git_url` — GitLab tree URL (format: `https://<host>/<project>/-/tree/<branch>/<path>`)
- `common.supported_extensions` — overrides the hardcoded extension list
- `common.log_level` — logging level (INFO, ERROR)
- `common.pause_before_exit` — pause on exit

## Testing Conventions

- Tests use `unittest` (compatible with pytest). No `pytest.ini` or `pyproject.toml` exists.
- Unit tests mock all external calls (filesystem, subprocess, requests).
- Integration tests (`test_integration_docs2md.py`) create real temp directories under `tests/test_data/` and require pandoc installed; they clean up in `tearDown()`.
- `active-prompt.md` describes the change workflow: plan → temp test → unit tests pass → add new unit test → unit tests pass again.
