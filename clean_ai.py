#!/usr/bin/env python3
import sys
import re
import io
import collections

# 1. FORCE UTF-8 HANDLING
sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8', errors='replace')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def fix_encoding_artifacts(text):
    """Repairs common 'Mojibake' (UTF-8 interpreted as Windows-1252)."""
    replacements = {
        'â€™': '’', 'â€œ': '“', 'â€\x9d': '”', 'â€': '”', 'â€“': '–', 'â€”': '—',
        'Â': '', 'â€¦': '…', '€™': '’', 'Ã©': 'é', 'Ã ': 'à', 'Ã§': 'ç', 
        'Ã«': 'ë', 'Ã¯': 'ï', 'Ã´': 'ô'
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)
    return text

def detect_column_count(lines, all_cells):
    """
    Forensic analysis to find the TRUE column count (N).
    Priority 1: Separator Line (|---|---|)
    Priority 2: Rhythm of Bold Cells (**Start**)
    Priority 3: Header Line (Sanitized)
    """
    # 1. Check for Separator Line (Most Reliable)
    for line in lines:
        if '|' in line and set(line).issubset({'|', '-', ' ', ':'}):
            parts = [c for c in line.split('|') if c.strip()]
            if len(parts) >= 2:
                return len(parts)

    # 2. Check for Bold Rhythm (The "Anchor" Method)
    # In these tables, the first column usually starts with **Bold Text**
    bold_indices = [i for i, cell in enumerate(all_cells) if cell.startswith('**')]
    
    if len(bold_indices) > 1:
        # Calculate distances between bold cells
        distances = []
        for i in range(len(bold_indices) - 1):
            dist = bold_indices[i+1] - bold_indices[i]
            # Filter out tiny distances (e.g. bold in col 1 AND col 2)
            if dist >= 2:
                distances.append(dist)
        
        if distances:
            # Find the most common distance (Mode)
            # This handles cases where one row might be weird, but most are N
            count_map = collections.Counter(distances)
            most_common = count_map.most_common(1)[0][0]
            if most_common > 1:
                return most_common

    # 3. Fallback: Header Line Analysis
    # Be careful of headers that merge with body rows on the same line
    # e.g. "Col1 | Col2 | Col3 || **Row1Col1**"
    if all_cells:
        # Heuristic: If we see a Bold cell in the first few cells, 
        # the header was likely merged. Cut off there.
        for i, cell in enumerate(all_cells[:10]): # Check first 10 cells
            if i > 0 and cell.startswith('**'):
                return i # Found a bold cell at index i, so header is 0 to i-1
    
    # Last Resort: Just count the header cells from the first line (sanitized)
    header_raw = lines[0].split('|')
    header_clean = [c for c in header_raw if c.strip()]
    return max(2, len(header_clean))

def normalize_table_block(block_lines):
    """
    Bag-of-Cells Strategy with Smart Column Detection.
    """
    lines = [l.strip() for l in block_lines if l.strip()]
    if not lines: return []

    # 1. Harvest ALL Content Cells (Bag of Cells)
    all_content_cells = []
    
    # We skip lines that are purely separator lines from the *content* bag,
    # but we keep them in 'lines' for detection purposes.
    for line in lines:
        # Check if separator
        if set(line).issubset({'|', '-', ' ', ':'}):
            continue
            
        raw_cells = line.split('|')
        for c in raw_cells:
            clean_c = c.strip()
            # Filter garbage empty cells
            if clean_c:
                all_content_cells.append(clean_c)

    if not all_content_cells: return block_lines

    # 2. Detect True Column Count
    col_count = detect_column_count(lines, all_content_cells)

    # 3. Reconstruct Table
    final_lines = []
    
    # Write Header (first N cells)
    header_cells = all_content_cells[:col_count]
    final_lines.append('| ' + ' | '.join(header_cells) + ' |')
    
    # Write Clean Separator
    final_lines.append('|' + '|'.join(['---'] * col_count) + '|')
    
    # Write Body Rows
    body_cells = all_content_cells[col_count:]
    
    for i in range(0, len(body_cells), col_count):
        row_chunk = body_cells[i : i + col_count]
        
        # Pad orphan cells
        while len(row_chunk) < col_count:
            row_chunk.append("")
            
        final_lines.append('| ' + ' | '.join(row_chunk) + ' |')

    return final_lines

def clean_text(text):
    # PHASE 0: Encoding Repair
    text = fix_encoding_artifacts(text)

    # PHASE 1: Structural Merging
    lines = text.split('\n')
    merged_lines = []
    i = 0
    orphan_bullet_pattern = re.compile(r'^(\s*)([-*+]|•|\d+\.?)\s*$')
    
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        # Header Merging
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

        # List Merging
        match = orphan_bullet_pattern.match(line)
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

    # PHASE 2: Typographical
    text = re.sub(r'\s+([?!;:])', r'\1', text)
    text = re.sub(r'\[cite_start\]|\]+\]', '', text)
    text = re.sub(r'\b(?:Artifact|Artefact|Screen|Section)\s+\d+\s*:\s*', '', text)
    text = re.sub(r'(\[\d+\])+', '', text)
    text = re.sub(r'(^|[\s\(\[{])"', r'\1“', text)
    text = re.sub(r'"', r'”', text)
    text = re.sub(r"(\w)'(\w)", r"\1’\2", text)
    text = re.sub(r"'", r"’", text)
    def capitalize_match(match): return ". " + match.group(1).upper()
    text = re.sub(r';\s*([a-z])', capitalize_match, text)
    text = text.replace("—", " – ").replace("---", "").replace("***", "")

    # PHASE 3: Table Detection
    lines = text.split('\n')
    lines_with_tables = []
    buffer = []
    in_table = False
    
    for line in lines:
        stripped = line.strip()
        if '|' in line:
            in_table = True; buffer.append(line)
        elif in_table and not stripped:
            buffer.append(line)
        elif in_table and stripped and '|' not in line:
            lines_with_tables.extend(normalize_table_block(buffer))
            buffer = []; in_table = False
            lines_with_tables.append(line)
        else:
            lines_with_tables.append(line)
    if in_table and buffer:
        lines_with_tables.extend(normalize_table_block(buffer))
    lines = lines_with_tables

    # PHASE 4: Formatting
    final = []
    found_title = False
    promote = False
    
    for line in lines:
        stripped = line.strip()
        if not stripped: final.append(""); continue
        
        if not found_title:
            if re.match(r'^#\s+', line):
                promote = True
                line = re.sub(r'^#\s+', '', line)
            found_title = True; final.append(line); continue

        if re.match(r'^[ \t]*[*•]\s+', line):
            line = re.sub(r'^([ \t]*)[*•]\s+', r'\1- ', line)
        if re.match(r'^\s*\*\*([^*\r\n]+)\*\*\s*$', line):
            line = re.sub(r'^\s*\*\*([^*\r\n]+)\*\*\s*$', r'## \1', line)
        if re.match(r'^(#{1,6}\s+.+?):\s*$', line):
             line = re.sub(r'^(#{1,6}\s+.+?):\s*$', r'\1', line)
        if promote and re.match(r'^#+\s+', line):
            line = re.sub(r'^#', '', line)

        is_struct = re.match(r'^\s*([-*+]|•|\d+\.|#|\|)', line)
        if is_struct:
            final.append(line)
        else:
            abbrevs = {'Mr', 'Mrs', 'Ms', 'Dr', 'Prof', 'Sr', 'Jr', 'vs', 'etc', 'Fig', 'al', 'e.g', 'i.e'}
            words = line.split(' ')
            new_p = []
            for i, w in enumerate(words):
                new_p.append(w)
                if w and w[-1] in '.?!' and '"' not in w and '”' not in w:
                    if i+1 < len(words) and words[i+1] and words[i+1][0].isupper():
                         clean = re.sub(r'[^\w]', '', w)
                         if clean not in abbrevs: new_p.append('\n\n')
            final.append(" ".join(new_p).replace(' \n\n ', '\n\n'))

    return "\n".join(final)

if __name__ == "__main__":
    raw = ""
    try:
        raw = sys.stdin.read()
        if not raw: sys.exit(0)
        print(clean_text(raw))
    except Exception as e:
        if raw: print(raw)