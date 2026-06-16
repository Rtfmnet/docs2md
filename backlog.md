# Bugs
BG1. Ignored readme doesn't  incorporate into skipped stats:
Current: The log counter `Files skipped as actual` doesn't include README.md files skipped because their local change date is older than the git change date.
New: Include such skipped README.md files in the `Files skipped as actual` counter.

BG2. Tool hangs forever if the Git server stops responding:
Current: When pushing to GitLab/Azure, if the server is slow or unreachable, the tool waits indefinitely with no timeout. The only way out is to kill the process manually; the run summary is never printed.
New: Add a configurable timeout (default 30 s) to all HTTP calls in git_sync.py.

BG3. tool logs different - readme.md - commited to git, other files - pushed. Change all to pushed as it fact it's commit and push.

# CRs
CR1. Super trivial change for Demo
Change output logging: INFO - PROCEED -> INFO - SUMMARY 
CR2. Standalone MD file:
Current: standalone .md files (no paired source doc) are ignored.
New: collect and push them to git as-is, no pandoc conversion.
CR3. README.md masks and file references can't be used together:
Current: If a README uses doc2md#mask= tags, only files matching the mask are kept — explicitly referenced files are ignored unless they also match the mask.
New: Support both filtering modes simultaneously — a file should be included if it matches a mask OR is explicitly referenced in the README.

CR4. Handle locally deleted files that still exist in git:
Current: If a file is deleted locally but still exists in the remote repo, the tool does nothing — the stale file remains in git indefinitely.
New: Detect such files and define the correct action (e.g. delete from git, warn the user, or skip with a log entry).

# TechDept
TD1. Split test data into categories:
Current: All test data lives in a single folder with no clear separation by origin or purpose.
New: Reorganise tests/test_data/ into three subcategories: manual, ai, and e2e.

# Implemented
CR5. Fore Clean Git config param
Current: noi such a param
New: if user add a new param to config file 'force_clean_git' and connection to Git wors and param: true the tool delete all files from the active project git url before process local files.
Default value if false.
