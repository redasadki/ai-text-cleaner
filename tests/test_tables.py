#!/usr/bin/env python3
"""Regression tests for Phase 3 table handling in scripts/clean_ai.py.

Run from the repository root:
    python3 -m unittest discover -s tests
"""
import os
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(__file__), '..', 'scripts', 'clean_ai.py')


def clean(text):
    with tempfile.NamedTemporaryFile('w', suffix='.md', delete=False, encoding='utf-8') as f:
        f.write(text)
        path = f.name
    try:
        out = subprocess.run([sys.executable, SCRIPT, path], capture_output=True,
                             text=True, encoding='utf-8', check=True).stdout
    finally:
        os.unlink(path)
    return out


class TestTables(unittest.TestCase):

    def test_consecutive_tables_separated_by_blank_line(self):
        src = ("# T\n"
               "| A | B | C | D |\n|---|---|---|---|\n| 1 | 2 | 3 | 4 |\n\n"
               "| E | F | G | H | I |\n|---|---|---|---|---|\n| 5 | 6 | 7 | 8 | 9 |\n\n"
               "| J | K |\n|---|---|\n| x | y |\n")
        out = clean(src)
        self.assertIn("| A | B | C | D |\n|---|---|---|---|\n| 1 | 2 | 3 | 4 |\n\n"
                      "| E | F | G | H | I |\n|---|---|---|---|---|\n| 5 | 6 | 7 | 8 | 9 |\n\n"
                      "| J | K |\n|---|---|\n| x | y |", out)

    def test_consecutive_tables_without_blank_line(self):
        src = "# T\n| A | B |\n|---|---|\n| 1 | 2 |\n| C | D | E |\n|---|---|---|\n| 3 | 4 | 5 |\n"
        out = clean(src)
        self.assertIn("| A | B |\n|---|---|\n| 1 | 2 |\n\n| C | D | E |\n|---|---|---|\n| 3 | 4 | 5 |", out)

    def test_tables_separated_by_prose(self):
        src = "# T\n| A | B |\n|---|---|\n| 1 | 2 |\n\nSome prose.\n\n| C | D | E |\n|---|---|---|\n| 3 | 4 | 5 |\n"
        out = clean(src)
        self.assertIn("| A | B |\n|---|---|\n| 1 | 2 |\n\nSome prose.\n\n| C | D | E |", out)

    def test_blank_lines_between_rows_are_removed(self):
        src = "# T\n| A | B |\n|---|---|\n\n| 1 | 2 |\n\n| 3 | 4 |\n\nAfter text.\n"
        out = clean(src)
        self.assertIn("| A | B |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |\n\nAfter text.", out)

    def test_empty_cells_are_preserved(self):
        src = "# T\n| A | B | C |\n|---|---|---|\n| x |  | z |\n|  | y |  |\n"
        out = clean(src)
        self.assertIn("| x |  | z |\n|  | y |  |", out)

    def test_alignment_colons_are_preserved(self):
        src = "# T\n| A | B | C |\n|:---|:---:|---:|\n| 1 | 2 | 3 |\n"
        self.assertIn("|:---|:---:|---:|", clean(src))

    def test_escaped_pipe_stays_in_cell(self):
        src = "# T\n| Pattern | Use |\n|---|---|\n| `a\\|b` | alternation |\n"
        self.assertIn("| `a\\|b` | alternation |", clean(src))

    def test_broken_row_still_uses_reflow_fallback(self):
        # Behaviour unchanged from v1.10: a row broken across lines is reflowed.
        src = "# T\n| Phase | Action |\n| --- | --- |\n| **Phase 1** | Start /\nRun |\n| **Phase 2** | End |\n"
        out = clean(src)
        self.assertIn("| Phase | Action |\n|---|---|", out)


if __name__ == '__main__':
    unittest.main()
