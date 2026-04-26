# docs2md

Converts documents (docx, pptx, xlsx, and more) to Markdown via pandoc, optionally syncs to GitLab, GitHub, or Azure DevOps. Primary use case: feeding a RAG knowledge base.

Config-driven — no CLI arguments, only `docs2md.yaml`.

## Quick Start

| Step | Action |
|---|---|
| 1. Install pandoc | [pandoc.org/installing.html](https://pandoc.org/installing.html) |
| 2. Install Python deps | `pip install pyyaml requests python-dotenv` |
| 3. Configure | edit `docs2md.yaml` |
| 4. (Optional) Set git token | add `GIT_ACCESS_TOKEN=<token>` to `.env` |
| 5. Run | `python docs2md.py` |
| 6. Test | `python -m pytest tests/` |

## Configuration (`docs2md.yaml`)

Supports two formats:

Set `active_project` to switch between named project sections:

```yaml
active_project: my_project   # change this to switch projects

my_project:
  root_folder: '/path/to/documents'
  force_md_generation: false
  git_commit: true
  force_readme_git_commit: false
  git_url: 'https://github.com/owner/repo/tree/main/docs'

common:
  pause_before_exit: false
  log_level: INFO             # INFO | DEBUG | ERROR
  supported_extensions:       # overrides built-in extension list
    - .docx
    - .pptx
    - .xlsx
```

### Config Keys

| Key | Description |
|---|---|
| `root_folder` | Directory to scan (relative or absolute) |
| `force_md_generation` | Regenerate `.md` even when up to date |
| `git_commit` | Push converted files to git |
| `force_readme_git_commit` | Also push `README.md` files to git (always, not mtime-guarded) |
| `git_url` | Repository tree URL (see format below) |
| `common.log_level` | Logging level: `INFO`, `DEBUG`, `ERROR` |
| `common.pause_before_exit` | Pause for keypress before exiting |
| `common.supported_extensions` | Override built-in list of convertible extensions |

### Git URL Formats

| Provider | URL format |
|---|---|
| GitLab | `https://<host>/<project>/-/tree/<branch>[/<path>]` |
| GitHub | `https://github.com/<owner>/<repo>/tree/<branch>[/<path>]` |
| Azure DevOps | `https://dev.azure.com/<org>/<project>/_git/<repo>` |

## Key Tags (in directory `README.md` files)

Tags are placed in `README.md` files inside each directory to control processing.

| Tag | Effect |
|---|---|
| `doc2md#aikb` | **Required** — opt-in this directory for processing |
| `doc2md#skipdir` | Skip this directory and all subdirectories |
| `doc2md#skipfile` | On a file's reference line — skip that specific file |
| `doc2md#mask=<glob>` | Only process files matching the wildcard (e.g. `*Transcript.docx`) |

## Processing Logic

For each directory under `root_folder`:

1. **Skip** if no `README.md` present, or README lacks `doc2md#aikb`
2. **Skip** if README contains `doc2md#skipdir`
3. **Collect** all files with supported extensions
4. **Apply masks** — if `doc2md#mask=<glob>` tags exist, keep only matching files
5. **Filter by README** — keep only files referenced in README; drop files whose reference line contains `doc2md#skipfile`; if no masks defined and file not referenced — skip it
6. **Convert** via pandoc; skip if `.md` already exists and source is not newer (unless `force_md_generation: true`)
7. **Output** — place `.md` in `md/` subdirectory if it exists; append source extension to filename on name collision (e.g. `report_docx.md`)
8. **Git sync** — if `git_commit: true`, push the generated `.md` (and optionally `README.md`) to the configured repository

## Supported Extensions (built-in)

`.asciidoc` `.biblatex` `.bibtex` `.bits` `.commonmark` `.commonmark_x` `.creole` `.csljson` `.csv` `.djot` `.docbook` `.docx` `.dokuwiki` `.eml` `.endnotexml` `.epub` `.fb2` `.gfm` `.haddock` `.html` `.ipynb` `.jats` `.jira` `.json` `.latex` `.man` `.markdown` `.markdown_github` `.markdown_mmd` `.markdown_phpextra` `.markdown_strict` `.mdoc` `.mediawiki` `.muse` `.native` `.odt` `.opml` `.org` `.pod` `.pptx` `.ris` `.rst` `.rtf` `.t2t` `.textile` `.tikiwiki` `.tsv` `.twiki` `.typst` `.vimwiki` `.xlsx` `.xml` `.txt`

Override with `common.supported_extensions` in config.

## Project Structure

```
docs2md.py        — main application (config loading, processing pipeline)
git_sync.py       — GitManager class (GitLab, GitHub, Azure DevOps push via REST API)
docs2md.yaml      — configuration file
.env              — GIT_ACCESS_TOKEN (not committed)
tests/
  test_docs2md.py     — unit tests for docs2md.py
  test_git_sync.py    — unit tests for git_sync.py
  e2e_docs2md.py      — integration tests (require pandoc installed)
samples/          — standalone utility scripts (not part of main pipeline)
  merge_md.py         — merge multiple .md files into one
  batch_docx2md.py    — bulk docx converter
  whisper2txt.py      — Whisper transcript sanitizer
  fixmd.py            — Markdown fixer/sanitizer
  codemie/            — Codemie agent demo scripts
```

## Running Tests

```bash
# All tests
python -m pytest tests/

# Unit tests only
python -m pytest tests/test_docs2md.py
python -m pytest tests/test_git_sync.py

# Integration tests (requires pandoc)
python -m pytest tests/e2e_docs2md.py

# Single test class or method
python -m pytest tests/test_docs2md.py::TestConvertToMarkdown
python -m pytest tests/test_docs2md.py::TestConvertToMarkdown::test_convert_success
```

## Dependencies

| Package | Purpose |
|---|---|
| `pandoc` | Document conversion (system binary, must be on PATH) |
| `pyyaml` | Config file parsing |
| `requests` | Git REST API calls |
| `python-dotenv` | Load `GIT_ACCESS_TOKEN` from `.env` |
