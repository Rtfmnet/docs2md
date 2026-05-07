# CLAUDE.md

For a full project description, see @README.md

## Commands

```bash
# Run the tool
python docs2md.py

# Run all tests
python -m pytest tests/

# Run a specific test file
python -m pytest tests/test_docs2md.py
python -m pytest tests/e2e_docs2md.py
python -m pytest tests/test_git_sync.py

# Run a specific test class or method
python -m pytest tests/test_docs2md.py::TestConvertToMarkdown
python -m pytest tests/test_docs2md.py::TestConvertToMarkdown::test_convert_success
```

## Environment
- Python 3.x; no virtual env required beyond `pip install pyyaml requests python-dotenv`
- `pandoc` must be installed and on PATH for e2e tests and runtime

## Testing Conventions
- Tests use `unittest` (pytest-compatible). No `pytest.ini` or `pyproject.toml`.
- Unit tests mock all external calls (filesystem, subprocess, requests).
- Integration tests (`e2e_docs2md.py`) create real temp dirs under `tests/test_data/` and require pandoc; they clean up in `tearDown()`.
- Write the minimum tests needed based on change impact:
  - Low (cosmetic): no tests. Example: change format or labeling in logging output
  - Medium (non-critical behavior): 1 unit test. Example: change in logging output
  - High (shared or critical logic): 1–3 unit + 1–3 e2e tests. Example: support new config key.

## Code Change Prompt Execution Flow 
MANDATORY — complete ALL steps in order for every change request:
1. Analyze the request
2. Make the required code changes
3. Run a temporary e2e test in `ai-sandbox/` to verify the change; iterate until passing
4. Ask the user to verify the changes
5. Add new unit and/or e2e tests per the Testing Conventions above
6. Update any existing tests affected by the change
7. Run all permanent tests (`python -m pytest tests/`) and fix failures until fully green

## Working Folders
- `ai-sandbox/` — temporary files created during the session (not committed)
- `ai-results/` — output files explicitly requested by the user (not committed)
