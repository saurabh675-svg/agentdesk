# Skill: Data Analysis

## When to use
CSV/Excel/JSON data, statistics, trends, cleaning, charts, reports from numbers, "what does this data say".

## Workflow
1. **Inspect first**: read the file (read_file), print shape, columns, dtypes, missing values, head/tail. Never assume the schema.
2. **One reproducible script**: write a Python script with pandas/matplotlib to a work folder, run with the shell tool, iterate. Keep every step in the script so it can re-run.
3. **Clean**: handle missing values explicitly (drop/fill — say which), fix types, dedupe, filter garbage rows. Report what was removed.
4. **Analyze**: descriptive stats first, then the actual question (groupbys, trends, correlations). Compute ALL numbers with code — never mental math.
5. **Visualize**: charts with real titles/labels; save as PNG files next to the results.
6. **Deliver**: findings (numbered, each backed by a computed number), the output files (CSV/JSON/PNG), and the script path so the user can re-run.

## Rules
- Big files: process in chunks; never dump raw data into chat.
- Charts must render Chinese/unicode if present (use a CJK-capable font in matplotlib).
- State assumptions (e.g., "rows with null revenue dropped, n=143").
