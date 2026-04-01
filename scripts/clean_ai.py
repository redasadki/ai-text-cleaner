#!/usr/bin/env python3
"""
AI Text Cleaner
Version: 1.5
Author: Reda Sadki
"""
import sys
import re
import io
import collections

__version__ = "1.5"

# FORCE UTF-8 HANDLING
sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8', errors='replace')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def fix_encoding_artifacts(text):
    replacements = {
        'â€™': '’', 'â€œ': '“', 'â€': '”',
        'â€': '—', 'â€': '–',
        'Â': '', 'â€¦': '…', '€™': '’',
        'Ã©': 'é', 'Ã ': 'à', 'Ã§': 'ç',
        'Ã«': 'ë', 'Ã¯': 'ï', 'Ã´': 'ô'
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)
    return text

def is_table_like(line):
    if not re.search(r'(?<!\\)\|', line):
        return False
    if re.match(r'^\s*(\d+\.|[-*+\u2022])\s+', line):
        return False
    return True

def detect_column_count(lines, all_cells):
    for line in lines:
        if '|' in line and set(line).issubset({'|', '-', ' ', ':'}):
            parts = [c for c in line.split('|') if c.strip()]
            if len(parts) >= 2:
                return len(parts)
    bold_indices = [i for i, cell in enumerate(all_cells) if cell.startswith('**')]
    if len(bold_indices) > 1:
        distances = []
        for i in range(len(bold_indices) - 1):
            dist = bold_indices[i+1] - bold_indices[i]
            if dist >= 2:
                distances.append(dist)
        if distances:
            most_common = collections.Counter(distances).most_common(1)[0][0]
            if most_common > 1:
                return most_common
    header_raw = lines[0].split('|')
    header_clean = [c for c in header_raw if c.strip()]
    return max(2, len(header_clean))

def normalize_table_block(block_lines):
    lines = [l.strip() for l in block_lines if l.strip()]
    if not lines:
        return []
    all_content_cells = []
    for line in lines:
        if set(line).issubset({'|', '-', ' ', ':'}):
            continue
        raw_cells = line.split('|')
        for c in raw_cells:
            if c.strip():
                all_content_cells.append(c.strip())
    if not all_content_cells:
        return block_lines
    col_count = detect_column_count(lines, all_content_cells)
    final_lines = []
    header_cells = all_content_cells[:col_count]
    final_lines.append('| ' + ' | '.join(header_cells) + ' |')
    final_lines.append('|' + '|'.join(['---'] * col_count) + '|')
    body_cells = all_content_cells[col_count:]
    for i in range(0, len(body_cells), col_count):
        row_chunk = body_cells[i:i + col_count]
        while len(row_chunk) < col_count:
            row_chunk.append("")
        final_lines.append('| ' + ' | '.join(row_chunk) + ' |')
    return final_lines

def clean_text(text):
    # PHASE 0: Encoding
    text = fix_encoding_artifacts(text)

    # PHASE 1: Structural Merging
    lines = text.split('\n')
    merged_lines = []
    i = 0
    bullet_pat = re.compile(r'^(\s*)([-*+]|\u2022|\d+\.?)\s*$')

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if re.match(r'^#{1,6}\s+', line):
            found = False
            if i + 1 < len(lines):
                next_l = lines[i+1].strip()
                if next_l and not re.match(r'^[-*#|]', next_l) and next_l[0].islower():
                    merged_lines.append(f"{stripped} {next_l}")
                    i += 2; found = True
                elif not next_l and i + 2 < len(lines):
                    next_next = lines[i+2].strip()
                    if next_next and not re.match(r'^[-*#|]', next_next) and next_next[0].islower():
                        merged_lines.append(f"{stripped} {next_next}")
                        i += 3; found = True
            if not found:
                merged_lines.append(line); i += 1
            continue

        match = bullet_pat.match(line)
        if match:
            prefix, bullet = match.group(1), match.group(2)
            found = False
            if i + 1 < len(lines):
                next_l = lines[i+1].strip()
                if next_l:
                    merged_lines.append(f"{prefix}{bullet} {next_l}")
                    i += 2; found = True
                elif i + 2 < len(lines):
                    next_next = lines[i+2].strip()
                    if next_next:
                        merged_lines.append(f"{prefix}{bullet} {next_next}")
                        i += 3; found = True
            if not found:
                merged_lines.append(line); i += 1
            continue

        merged_lines.append(line); i += 1

    text = "\n".join(merged_lines)

    # PHASE 2: Typo Fixes & Separator Removal
    text = re.sub(r'\s+([?!;:])', r'\1', text)
    text = re.sub(r'\[cite_start\]|\[(?:cite|source):\s*[^\]]+\]', '', text)
    text = re.sub(r'\b(?:Artifact|Artefact|Screen|Section)\s+\d+\s*:\s*', '', text)
    text = re.sub(r'(\[\d+\])+', '', text)
    # Remove Perplexity footnote references: [^1], [^12], sequences like [^1][^2][^3]
    text = re.sub(r'(\[\^\d+\][ \t]*)+', '', text)
    # Remove Perplexity inline citation links; preserve standalone reference list items
    _standalone_ref = re.compile(r'^\s*(?:\d+\.|-|\*)\s+\[[^\]]+\]\([^)]+\)\s*$')
    text = '\n'.join(
        line if _standalone_ref.match(line)
        else re.sub(r'\[[^\]]+\]\([^)]+\)', '', line)
        for line in text.split('\n')
    )
    # Smart quotes: use variables + lambdas to avoid Python 3.12 re.sub bad-escape on \u in raw strings
    LDQUO = '\u201c'
    RDQUO = '\u201d'
    RSQUO = '\u2019'
    text = re.sub(r'(^|[\s\(\[{])"', lambda m: m.group(1) + LDQUO, text)
    text = re.sub(r'"', RDQUO, text)
    text = re.sub(r"(\w)'(\w)", lambda m: m.group(1) + RSQUO + m.group(2), text)
    text = re.sub(r"'", RSQUO, text)
    def capitalize_match(match):
        return ". " + match.group(1).upper()
    text = re.sub(r';\s*([a-z])', capitalize_match, text)
    text = text.replace('\u2014', ' \u2013 ')
    text = text.replace('***', '')
    text = re.sub(r'(?m)^[ \t]*---+[ \t]*$', '', text)

    # PHASE 3: Strict Table Detection
    lines = text.split('\n')
    lines_with_tables = []
    buffer = []
    in_table = False

    for line in lines:
        stripped = line.strip()
        is_table_row = is_table_like(line)
        if is_table_row:
            in_table = True
            buffer.append(line)
        elif in_table and not stripped:
            buffer.append(line)
        else:
            if in_table:
                lines_with_tables.extend(normalize_table_block(buffer))
                lines_with_tables.append("")
                buffer = []
                in_table = False
            lines_with_tables.append(line)

    if in_table and buffer:
        lines_with_tables.extend(normalize_table_block(buffer))
        lines_with_tables.append("")

    lines = lines_with_tables

    # PHASE 4: Formatting
    final = []
    found_title = False
    promote = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            final.append("")
            continue

        if not found_title:
            if re.match(r'^\s*([-*+\u2022]|\d+\.|\|)', line):
                found_title = True
            else:
                if re.match(r'^#\s+', line):
                    promote = True
                    line = re.sub(r'^#\s+', '', line)
                found_title = True
                final.append(line)
                continue

        if re.match(r'^[ \t]*[*\u2022]\s+', line):
            line = re.sub(r'^([ \t]*)[*\u2022]\s+', r'\1- ', line)
        if re.match(r'^\s*\*\*([^*\r\n]+)\*\*\s*$', line):
            line = re.sub(r'^\s*\*\*([^*\r\n]+)\*\*\s*$', r'## \1', line)
        if re.match(r'^(#{1,6}\s+.+?):\s*$', line):
            line = re.sub(r'^(#{1,6}\s+.+?):\s*$', r'\1', line)
        if promote and re.match(r'^#+\s+', line):
            line = re.sub(r'^#', '', line)

        is_struct = re.match(r'^\s*([-*+]|\u2022|\d+\.|#|\|)', line)
        if is_struct:
            final.append(line)
        else:
            abbrevs = {'Mr', 'Mrs', 'Ms', 'Dr', 'Prof', 'Sr', 'Jr', 'vs', 'etc', 'Fig', 'al', 'e.g', 'i.e'}
            words = line.split(' ')
            new_p = []
            for i, w in enumerate(words):
                new_p.append(w)
                if w and w[-1] in '.?!' and '\u201d' not in w:
                    if i+1 < len(words) and words[i+1] and words[i+1][0].isupper():
                        clean = re.sub(r'[^\w]', '', w)
                        if clean not in abbrevs:
                            new_p.append('\n\n')
            final.append(" ".join(new_p).replace(' \n\n ', '\n\n'))

    return "\n".join(final)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        try:
            with open(sys.argv[1], 'r', encoding='utf-8') as f:
                print(clean_text(f.read()))
        except FileNotFoundError:
            print(f"Error: File '{sys.argv[1]}' not found.", file=sys.stderr)
            sys.exit(1)
    else:
        raw = sys.stdin.read()
        if raw:
            print(clean_text(raw))
