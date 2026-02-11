#!/usr/bin/env python3
import sys
import re
import io

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

def normalize_table_block(block_lines):
    """
    Reconstructs malformed tables where rows are split across multiple lines.
    Strategy: Merge lines until the pipe count matches the header's pipe count.
    """
    # 1. Remove pure blank lines (noise)
    lines = [line.strip() for line in block_lines if line.strip()]
    if not lines: return []

    # 2. Identify Header & Target Pipe Count
    header = lines[0]
    # We count pipes to know what a "complete" row looks like.
    target_pipes = header.count('|')
    # Safety: If header has fewer than 2 pipes, it's not a valid table.
    if target_pipes < 2: return block_lines

    reconstructed_rows = []
    current_buffer = ""
    
    # 3. Merge fragmented lines
    for line in lines:
        # If buffer is empty, start new row.
        # If buffer has content, join.
        # Heuristic: If the continuation line starts with '|', just concat (it's a delimiter).
        # If it starts with text, add a space (it's a word wrap).
        if not current_buffer:
            current_buffer = line
        else:
            if line.startswith('|'):
                current_buffer += line # likely " | next cell"
            else:
                current_buffer += " " + line # likely " wrapped text"
        
        # Check if we have formed a complete row
        # (We count escaped pipes \| as 0, but here we assume simple pipes)
        if current_buffer.count('|') >= target_pipes:
            reconstructed_rows.append(current_buffer)
            current_buffer = ""
    
    # Append any leftover buffer (e.g. last row missing a closing pipe)
    if current_buffer:
        reconstructed_rows.append(current_buffer)

    # 4. Standardize columns (Fill missing cells, fix separators)
    final_lines = []
    header_cells = [c.strip() for c in reconstructed_rows[0].strip('|').split('|')]
    col_count = len(header_cells)

    for row in reconstructed_rows:
        # Split cells
        cells = [c.strip() for c in row.strip('|').split('|')]
        
        # Detect Separator Line (e.g. ---|---)
        is_separator = all(re.match(r'^[-:\s]+$', c) for c in cells if c)
        
        if is_separator:
            new_row = '|' + '|'.join(['---'] * col_count) + '|'
            final_lines.append(new_row)
            continue

        # Normalize Cell Count
        current_len = len(cells)
        if current_len == col_count:
            new_row = '| ' + ' | '.join(cells) + ' |'
        elif current_len < col_count:
            # Pad missing cells
            padded_cells = cells + [''] * (col_count - current_len)
            new_row = '| ' + ' | '.join(padded_cells) + ' |'
        elif current_len > col_count:
            # Merge extra cells
            keep_cells = cells[:col_count-1]
            merged_last = " ".join(cells[col_count-1:])
            keep_cells.append(merged_last)
            new_row = '| ' + ' | '.join(keep_cells) + ' |'
        else:
            new_row = '| ' + ' | '.join(cells) + ' |'
            
        final_lines.append(new_row)

    return final_lines

def clean_text(text):
    # PHASE 0: Encoding Repair
    text = fix_encoding_artifacts(text)

    # PHASE 1: Structural Repairs (Orphan Bullets)
    lines = text.split('\n')
    merged_lines = []
    i = 0
    orphan_bullet_pattern = re.compile(r'^\s*([-*+]|\d+\.?)\s*$')
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if orphan_bullet_pattern.match(line) and i + 1 < len(lines):
            next_line = lines[i+1].strip()
            if next_line:
                merged_lines.append(f"{stripped} {next_line}")
                i += 2
                continue
        merged_lines.append(line)
        i += 1
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

    text = text.replace("—", " – ")
    text = text.replace("---", "")
    text = text.replace("***", "")

    # PHASE 3: Smart Table Detection
    lines = text.split('\n')
    lines_with_tables_fixed = []
    table_buffer = []
    in_table = False
    
    for line in lines:
        stripped = line.strip()
        
        # Table Start Trigger: Contains a pipe
        if '|' in line:
            in_table = True
            table_buffer.append(line)
        
        # Table Continuation: If we are in a table, capture blank lines too
        # (so we don't break the table on a blank line between fragments)
        elif in_table and not stripped:
            table_buffer.append(line)
            
        # Table End: Text line with NO pipe
        elif in_table and stripped and '|' not in line:
            # Process the buffer we collected
            lines_with_tables_fixed.extend(normalize_table_block(table_buffer))
            table_buffer = []
            in_table = False
            lines_with_tables_fixed.append(line)
            
        else:
            # Not in table, just normal text
            lines_with_tables_fixed.append(line)
            
    # Flush buffer if file ends with a table
    if in_table and table_buffer:
        lines_with_tables_fixed.extend(normalize_table_block(table_buffer))
        
    lines = lines_with_tables_fixed

    # PHASE 4: Formatting (Headings, Lists, Sentences)
    final_lines = []
    found_title = False
    promote_headings = False
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            final_lines.append("")
            continue
            
        if not found_title:
            if re.match(r'^#\s+', line):
                promote_headings = True
                line = re.sub(r'^#\s+', '', line)
            found_title = True
            final_lines.append(line)
            continue

        if re.match(r'^\s*\*\s+', line):
            line = re.sub(r'^(\s*)\*\s+', r'\1- ', line)
            
        if re.match(r'^\s*\*\*(.*?)\*\*\s*$', line):
            line = re.sub(r'^\s*\*\*(.*?)\*\*\s*$', r'## \1', line)
            
        if promote_headings and re.match(r'^#+\s+', line):
            line = re.sub(r'^#', '', line)

        is_list_or_table = re.match(r'^\s*([-*+]|\d+\.|#|\|)', line)
        if is_list_or_table:
            final_lines.append(line)
        else:
            abbrevs = {'Mr', 'Mrs', 'Ms', 'Dr', 'Prof', 'Sr', 'Jr', 'vs', 'etc', 'Fig', 'al', 'e.g', 'i.e'}
            words = line.split(' ')
            new_paragraph = []
            for i, word in enumerate(words):
                new_paragraph.append(word)
                if word and word[-1] in '.?!' and '"' not in word and '”' not in word:
                    if i + 1 < len(words) and words[i+1] and words[i+1][0].isupper():
                         clean_word = re.sub(r'[^\w]', '', word)
                         if clean_word not in abbrevs:
                             new_paragraph.append('\n\n')
            processed = " ".join(new_paragraph).replace(' \n\n ', '\n\n')
            final_lines.append(processed)

    return "\n".join(final_lines)

if __name__ == "__main__":
    raw_input = ""
    try:
        raw_input = sys.stdin.read()
        if not raw_input: sys.exit(0)
        print(clean_text(raw_input))
    except Exception as e:
        if raw_input: print(raw_input)