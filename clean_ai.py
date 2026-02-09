#!/usr/bin/env python3
import sys
import re

def normalize_table_block(block_lines):
    """
    Takes a list of lines (strings) that are suspected to be a table.
    Returns a list of clean, formatted Markdown table lines.
    """
    cleaned_rows = []
    for line in block_lines:
        s = line.strip()
        if not s.startswith('|'): s = '| ' + s
        if not s.endswith('|'): s = s + ' |'
        cleaned_rows.append(s)

    if not cleaned_rows: return block_lines
        
    header_row = cleaned_rows[0]
    # Extract cells, ignoring empty strings from split
    header_cells = [c for c in header_row.strip('|').split('|')]
    col_count = len(header_cells)
    
    final_lines = []
    
    for index, row in enumerate(cleaned_rows):
        cells = [c for c in row.strip('|').split('|')]
        
        # Check if Separator Line (e.g. ---|---)
        is_separator = all(re.match(r'^\s*[-:]+\s*$', c) for c in cells if c.strip())
        
        if is_separator:
            new_row = '|' + '|'.join(['---'] * col_count) + '|'
            final_lines.append(new_row)
            continue
            
        current_len = len(cells)
        
        if current_len == col_count:
            new_row = '| ' + ' | '.join(c.strip() for c in cells) + ' |'
            final_lines.append(new_row)
        elif current_len < col_count:
            padded_cells = cells + [''] * (col_count - current_len)
            new_row = '| ' + ' | '.join(c.strip() for c in padded_cells) + ' |'
            final_lines.append(new_row)
        elif current_len > col_count:
            keep_cells = cells[:col_count-1]
            merged_last = " ".join(cells[col_count-1:])
            keep_cells.append(merged_last)
            new_row = '| ' + ' | '.join(c.strip() for c in keep_cells) + ' |'
            final_lines.append(new_row)

    return final_lines

def clean_text(text):
    # --- PHASE 1: Structural Repairs (Orphan Bullets) ---
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
                merged_line = f"{stripped} {next_line}"
                merged_lines.append(merged_line)
                i += 2
                continue
        merged_lines.append(line)
        i += 1
    
    text = "\n".join(merged_lines)

    # --- PHASE 2: Typographical & Pattern Cleanup ---
    text = re.sub(r'\s+([?!;:])', r'\1', text) # Remove space before punctuation
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

    # --- PHASE 3: Table Detection & Repair ---
    lines = text.split('\n')
    lines_with_tables_fixed = []
    table_buffer = []
    in_table = False
    
    for line in lines:
        if '|' in line:
            in_table = True
            table_buffer.append(line)
        else:
            if in_table:
                if len(table_buffer) > 1 or (len(table_buffer) == 1 and '---' in table_buffer[0]):
                     lines_with_tables_fixed.extend(normalize_table_block(table_buffer))
                else:
                     lines_with_tables_fixed.extend(table_buffer)
                table_buffer = []
                in_table = False
            lines_with_tables_fixed.append(line)
            
    if in_table and table_buffer:
        lines_with_tables_fixed.extend(normalize_table_block(table_buffer))
        
    lines = lines_with_tables_fixed

    # --- PHASE 4: Line-by-Line Formatting & Heading Promotion ---
    final_lines = []
    found_title = False
    promote_headings = False
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            final_lines.append("")
            continue
            
        # A. TITLE LOGIC: Remove # from first line, trigger promotion
        if not found_title:
            # Check if it IS a level 1 heading
            if re.match(r'^#\s+', line):
                promote_headings = True
                line = re.sub(r'^#\s+', '', line) # Remove the #
            # Even if not level 1, we mark title found so we don't strip later
            found_title = True
            final_lines.append(line)
            continue

        # B. LIST LOGIC: Change '*' to '-'
        if re.match(r'^\s*\*\s+', line):
            line = re.sub(r'^(\s*)\*\s+', r'\1- ', line)
            
        # C. HEADING LOGIC
        
        # 1. Fix "Fake" Headings (**Bold**)
        if re.match(r'^\s*\*\*(.*?)\*\*\s*$', line):
            line = re.sub(r'^\s*\*\*(.*?)\*\*\s*$', r'## \1', line)
            
        # 2. Promote Headings (if title was removed)
        if promote_headings and re.match(r'^#+\s+', line):
            # Reduce number of # by 1
            # "## Title" -> "# Title"
            line = re.sub(r'^#', '', line)

        # D. SENTENCE SPLITTING
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
    try:
        input_text = sys.stdin.read()
        print(clean_text(input_text))
    except Exception as e:
        sys.stderr.write(str(e))
        pass