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
    Smartly reconstructs tables by identifying 'True' rows vs 'Fragment' lines.
    Handles extra garbage pipes (|| | |) and fragmented cells.
    """
    lines = [l.strip() for l in block_lines if l.strip()]
    if not lines: return []

    # 1. Analyze Header to find True Column Count
    header = lines[0]
    # Split and filter out empty strings to find actual content columns
    header_cells = [c.strip() for c in header.split('|') if c.strip()]
    col_count = len(header_cells)
    if col_count < 2: col_count = 2 # Safety fallback

    merged_rows = []
    current_raw_string = ""
    
    for i, line in enumerate(lines):
        # 2. Logic to detect a "New Row" vs "Continuation"
        # Always treat the first two lines (Header + Separator) as new rows
        is_header_or_sep = (i == 0) or (i == 1 and set(line).issubset({'|', '-', ' ', ':'}))
        
        # Strict Trigger: A new body row MUST start with "| **" (Bold) in this format
        # or be a very clear full row (heuristic).
        is_bold_start = line.startswith('| **') or line.startswith('|**')
        
        if is_header_or_sep or is_bold_start:
            # Save previous buffer
            if current_raw_string: merged_rows.append(current_raw_string)
            current_raw_string = line
        else:
            # Continuation: Append to buffer
            # Cleanly merge: if buffer ends with | and line starts with |, strip one
            clean_line = line.strip()
            if current_raw_string.endswith('|') and clean_line.startswith('|'):
                current_raw_string += " " + clean_line.lstrip('|')
            else:
                current_raw_string += " " + clean_line
    
    # Flush last buffer
    if current_raw_string: merged_rows.append(current_raw_string)
    
    # 3. Rebuild and Sanitize Columns
    final_lines = []
    for row_str in merged_rows:
        # Split by pipe
        cells = [c.strip() for c in row_str.split('|')]
        
        # Remove empty start/end created by split
        if cells and not cells[0]: cells.pop(0)
        if cells and not cells[-1]: cells.pop()
        
        # CRITICAL: Remove garbage empty cells from the END only (fixes || | |)
        while len(cells) > col_count and not cells[-1]:
            cells.pop()
            
        # Merge if still too many (e.g. pipe inside content)
        if len(cells) > col_count:
            base = cells[:col_count-1]
            rest = " ".join(cells[col_count-1:])
            base.append(rest)
            cells = base
        
        # Pad if too few
        while len(cells) < col_count:
            cells.append("")
            
        # Generate clean row
        if all(re.match(r'^[-:\s]+$', c) for c in cells if c):
            final_lines.append('|' + '|'.join(['---'] * col_count) + '|')
        else:
            final_lines.append('| ' + ' | '.join(cells) + ' |')
            
    return final_lines

def clean_text(text):
    # PHASE 0: Encoding Repair
    text = fix_encoding_artifacts(text)

    # PHASE 1: Structural Repairs (Orphan Bullets)
    lines = text.split('\n')
    merged_lines = []
    i = 0
    orphan_bullet_pattern = re.compile(r'^(\s*)([-*+]|•|\d+\.?)\s*$')
    
    while i < len(lines):
        line = lines[i]
        match = orphan_bullet_pattern.match(line)
        if match:
            bullet_char = match.group(2)
            found_text = False
            if i + 1 < len(lines):
                next_line = lines[i+1].strip()
                if next_line:
                    merged_lines.append(f"{match.group(1)}{bullet_char} {next_line}")
                    i += 2
                    found_text = True
                elif i + 2 < len(lines):
                    next_next_line = lines[i+2].strip()
                    if next_next_line:
                        merged_lines.append(f"{match.group(1)}{bullet_char} {next_next_line}")
                        i += 3
                        found_text = True
            if not found_text:
                merged_lines.append(line)
                i += 1
        else:
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
        # Trigger: Pipe exists
        if '|' in line:
            in_table = True
            table_buffer.append(line)
        # Continuation: Empty line inside table
        elif in_table and not stripped:
            table_buffer.append(line)
        # End: Text without pipe
        elif in_table and stripped and '|' not in line:
            lines_with_tables_fixed.extend(normalize_table_block(table_buffer))
            table_buffer = []
            in_table = False
            lines_with_tables_fixed.append(line)
        else:
            lines_with_tables_fixed.append(line)
            
    if in_table and table_buffer:
        lines_with_tables_fixed.extend(normalize_table_block(table_buffer))
        
    lines = lines_with_tables_fixed

    # PHASE 4: Formatting
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

        if re.match(r'^[ \t]*[*•]\s+', line):
            line = re.sub(r'^([ \t]*)[*•]\s+', r'\1- ', line)
            
        if re.match(r'^\s*\*\*([^*\r\n]+)\*\*\s*$', line):
            line = re.sub(r'^\s*\*\*([^*\r\n]+)\*\*\s*$', r'## \1', line)
            
        if re.match(r'^(#{1,6}\s+.+?):\s*$', line):
             line = re.sub(r'^(#{1,6}\s+.+?):\s*$', r'\1', line)

        if promote_headings and re.match(r'^#+\s+', line):
            line = re.sub(r'^#', '', line)

        is_list_or_table = re.match(r'^\s*([-*+]|•|\d+\.|#|\|)', line)
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