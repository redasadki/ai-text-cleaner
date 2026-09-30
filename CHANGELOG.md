# Changelog

All notable changes to AI Text Cleaner are recorded in this file. Versions follow the `__version__` string in `scripts/clean_ai.py`.

## 1.11 (2026-09-30)

### Fixed: consecutive tables no longer merge into one broken table

Phase 3 keeps blank lines inside its table buffer so that it can repair tables whose rows are separated by blank lines. Side effect: two or more complete tables separated only by a blank line (with no prose in between) were buffered as one block. `normalize_table_block()` then pooled every cell from every table, took the column count from the first separator row, and reflowed all remaining cells into that width. Headers of the second and later tables became body rows, and every row after the first table was shifted.

- New `split_table_block()` splits a buffered block into separate tables. A new table starts at the header row directly above every separator row after the first one. This also separates tables that follow each other with no blank line at all.
- Each table is normalised independently, and the tables are joined with exactly one blank line.

### Fixed: well-formed tables are now rebuilt row by row

A table is treated as well formed when it has a header row, a separator row, and body rows that each open and close with a pipe and have exactly as many cells as the header. Such tables are now rebuilt row by row instead of being reflowed from a flat list of cells. This fixes three silent corruptions in v1.10:

- Empty cells were dropped, which shifted every later cell in the row and in all following rows.
- Escaped pipes (`\|`) inside a cell split the cell in two.
- Alignment colons in the separator row (`:---`, `:---:`, `---:`) were replaced with `---`.

Tables that are not well formed (for example, a row broken across two lines) still use the v1.10 reflow repair unchanged.

### Added

- `tests/test_tables.py`: eight regression tests for table handling. Run with `python3 -m unittest discover -s tests` from the repository root.

### Also included in this commit

The working copy used for this fix already contained changes that had not been pushed after the v1.10 commit (a86fdd3). They are included here as they were:

- `split_prose_line()` CASE C and CASE E: a closing quote that ends with a comma (for example, `“X,” Name said`) is treated as a dialogue tag continuation, not a sentence boundary. Only a quote ending in `.`, `?`, or `!` before the closing mark can end a sentence.
- `split_prose_line()`: leading `*` is stripped, together with opening curly quotes, before the uppercase test on the next word.
- Phase 4: lines starting with `>` (block quotes) are treated as structural and are not split.
- Phase 4: a line with a DOI but no reference heading is routed to `split_reference_block()` only if it also contains author-year entry boundaries. A DOI cited inline in ordinary prose goes through normal prose splitting.

### Known limitation (unchanged)

The reflow fallback for rows broken across lines places the continuation fragment in its own row (for example, `Start /` and `Run` end up in separate rows). This behaviour is identical to v1.10.

## 1.10 (2026-06-16)

- `remove_trailing_cite_links()`: trailing DOI links are preserved.
- Phase 4: reference-block routing. Lines that start with a reference heading and contain a DOI are split into one entry per line by `split_reference_block()`.
- `split_prose_line()`: CASE E for self-contained inline quote tokens, and INITIAL guard so author initials are never treated as sentence ends.

## 1.9 (2026-06-15)

- Interrupted quotations with attribution (`“Quote,” Reda said. “Continuation.”`) stay in one paragraph.

## 1.8 (2026-06-15)

- Sentence splitting around block quotes corrected (CASE A, CASE B, CASE C).

## 1.7 (2026-04-01)

- Trailing end-of-line citation links are removed (any domain). Standalone reference items and annotated bibliography entries are preserved.

## 1.6.1

- Removed a stray backslash line continuation that caused an `IndentationError` on Python 3.12.

## 1.6

- Only Markdown links on Perplexity domains (`perplexity.ai`, `ppl-ai-*`) are removed.

## 1.5

- Python 3.12 smart-quote fix (no `\u` escapes in `re.sub` replacement strings).

## 1.3

- Perplexity footnote references (`[^1]`, `[^1][^2]`) are removed.
