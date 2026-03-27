# docs2md tool
# tool to synchronize documents to md (*.md) files
# context
There is a project having project files and knowledge base.
It is required to convert such documents into text files to provide text files to RAG later to enable AI capabilities for the project.

# high level requirements
- user specifies root directory for project knowledge base (kb)
- user marks any directory recursively within his root directory should it be processed by this tool or not
- user specify mask to process set of files or specify each file individually
- when user specifies individual file in readme file, it should be ability to ignore this file for processing
- when tool regenerate md file it should do it for outdated files, unless force parameter provided
- integration with pandoc (https://pandoc.org/installing.html)
  - use this tool via command line to create md files (convert doc file to md)
  - supported file extensions:`*.asciidoc, *.biblatex, *.bibtex, *.bits, *.commonmark, *.commonmark_x, *.creole, *.csljson, *.csv, *.djot, *.docbook, *.docx, *.dokuwiki, *.endnotexml, *.epub, *.fb2, *.gfm, *.haddock, *.html, *.ipynb, *.jats, *.jira, *.json, *.latex, *.man, *.markdown, *.markdown_github, *.markdown_mmd, *.markdown_phpextra, *.markdown_strict, *.mdoc, *.mediawiki, *.muse, *.native, *.odt, *.opml, *.org, *.pod, *.pptx, *.ris, *.rst, *.rtf, *.t2t, *.textile, *.tikiwiki, *.tsv, *.twiki, *.typst, *.vimwiki, *.xlsx, *.xml`

# algorithm

## initial setup
  - read config file
  - initialize log file 
  - to verify is pandoc installed, if not raise exception and exit

## process each directory and all it's subdirectories starting from root_folder

1. DIRECTORY EVALUATION
   - Check if directory has README.md file
   - If README.md is missing, skip this directory entirely
   - If README.md exists:
     - Check for `doc2md#skipdir` tag in README.md
     - If `doc2md#skipdir` is present (search text in file), skip processing this directory and its subdirectories
     - Otherwise, continue processing

2. FILE COLLECTION (current directory only) all supported files, optinally by masks
   - Collect all files in current directory with supported extensions (see them above)
   - Apply filtering based on masks:
     - If masks are defined in README.md using "doc2md#mask='^regex_pattern$'" format (search text in file)
        - Mask tag example: `doc2md#mask='^.*Transcript\.docx$'`
       - Keep only files matching at least one mask (regex pattern)
     - If no masks are defined in README.md, keep all files with supported extensions
   - Result: Initial file list for this directory

3. FILE FILTERING based on content of readme file
   - For each file in the initial list:
     - Extract fist line of the file reference in README.md (case insensitive, word-boundary search, with or without extension)
        - examples for `file_name2.docx` file:
            - match: `some_text_before file_name2 some_text_after`
            - match: `some_text_before file_name2.docx some_text_after`
            - unmatch: `some_text_before file_name2moretext some_text_after`
            - unmatch: `some_text_before file_name2moretext.docx some_text_after`
     - If no such line and no masks in readme - remove file from processig list
     - else if tag `doc2md#skipfile` case insensitive found in the extracted line - remove file from processig list
   - Result: Final filtered list for this directory

4. FILE PROCESSING
   - For each file in filtered list:
     - Determine target MD path
        - if directory 'md' found in the current directory, all md files must be stored into this directory
        - if two files have the same name but different extensions, (e.g., report.docx and report.xls): to add doc file extension into md file name (e.g. report_docx.md and report_xls.md)
        - else md file should have the same name as doc (source) file but with extention .md
     - Check if target MD already exists
       - If doesn't exist:
         - Process file with pandoc (convert to markdown)
       - If exists:
         - If "force_md_generation: true" in Config:
           - Process file with pandoc (generate MD regardless of timestamps)
         - Else:
           - Check if source file is newer than MD file (using system file properties)
           - If source is newer, process file with pandoc
           - If MD is newer or same age, skip file
     - add info to log (see log example)

5. add info to log (see log example)

## finally `pause_before_exit: true` in config file, output message 'Press any key to exit...' and wait

# config file `docs2md.yaml` example: 
```
root_folder: 'C:\Users\path\\'
# or
# root_folder: '\folder\subfolder'
pause_before_exit: true
force_md_generation: false
```
## the tool must support both relative and absolute paths, see examples above

# logs
  - file: `docs2md.log
  - level: INFO
  - rotation: by size (4Kb)
  - duplicate output to console
  - don't use DEBUG from logging, use only INFO, ERROR and WARNING (if any needs for warning)
## log file  example:
```
each line starts from INFO - or ERROR or WARNING
<date time>
<root_folder>
<folder1>
Skiped due to...
<folder2>
<doc file_name> MD generated | Skipped due to ...
Skipped: 3; Generated: 3; Errors: 4 (means for folder2)
<folder3>  
```

# technical details
- use Python
- CLI doesn't support, only config file
- working folder: log and config file shoudl be in the same folder as a main Python script
- code:
  - keep code clean: add only code that matches with requirements, do not add not nessesory code
  - use constants when it's required, e.g. tag names
- use logging module for logs
- exception handing
  - log all exceptions such as running pandoc, file operations
  - exit if exception is critical and the tool can't proceed (e.g. root path is not accessible or pandoc is no installed)
- use yaml module for config
- file structure
  - docs2md.py - main function and all logic (place all into one file including logging and config)
  - docs2md.yaml -  config file
  - README.md - documentation
  - docs2md.log - log file
  - tests - folder contains all tests and test data
    - test_docs2md.py - unit tests
    - test_integration_docs2md.py - integration tests
    - test_data - folder to create directories and files for integration tests
- unit tests
  - use unittest module
  - utilize mocking
  - unit test coverage: one positive and one negative per each step of algorithm
- integration tests coverage:
  - depth: root\sub1\sub2\sub3
  - readme - exists, not exists, exists but havign special tag to skip directory
  - cover all cases of doc file conversion (md file generation/regeneration) conditions:
    - content of readme file including special tags
    - outdated / not outdated
    - force config parameter
  - make sure that all test data within test_data folder is removed after accomplished or if exception