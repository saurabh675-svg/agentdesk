# Skill: Document Creation

## When to use
Reports, letters, resumes, proposals, slides, spreadsheets — any file deliverable (docx / xlsx / pptx / pdf / html).

## Workflow
1. **Lock the deliverable**: format, filename, audience, tone, length. If unclear, pick the obvious default and say it.
2. **Content first**: outline the sections with the actual facts/data the user gave. Real names, real numbers — never placeholder junk.
3. **Generate via script** (most reliable, free): python-docx / openpyxl / python-pptx / reportlab, or clean HTML for pdf-style pages. Write the script with the file tools, run with the shell tool, verify the file exists and opens.
4. **Verify**: re-open the generated file programmatically (page count, sheet names, headings) before reporting done.
5. **Deliver**: the file path + one-line summary of what's inside.

## Quality bar
- No "TODO", no lorem ipsum, no unfilled 【placeholders】 — every section complete or explicitly marked as needing user input.
- Match the user's language for all content.
- Professional defaults: readable fonts, consistent styling, page numbers for multi-page docs.

## If office libs are missing
pip install python-docx openpyxl python-pptx reportlab — via the shell tool (free, offline-friendly).
