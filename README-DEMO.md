# Sample Documentation Directory

This README-DEMO.md file demonstrates all the tags and features available for the docs2md tool.

The `doc2md#aikb` tag above is required — without it, docs2md will skip this directory entirely.

doc2md#aikb

## Files to process (explicit listing)

These files will be processed by docs2md because they are explicitly mentioned:

Document1.txt - file description
Presentation.pptx
Spreadsheet.xlsx

## Files to skip (using skipfile tag)

These files will be skipped even though they're mentioned:

SkipMe.txt (doc2md#skipfile)
DoNotProcess.docx (doc2md#skipfile)

## Using file masks

You can use wildcard (glob) patterns to match multiple files with similar names.
Supported wildcards: `*` (any characters), `?` (single character). Quotes are optional.

doc2md#mask=*.xlsx
doc2md#mask=*Transcript.docx
