import re
from redaction.relationship_scorer import is_continuation_row
from redaction.merged_cell_handler import expand_merged_coordinates
from redaction.stop_patterns import should_stop_block

def is_stop_label(text: str) -> bool:
    """Delegates to the shared stop-block checker."""
    return should_stop_block(text)

def get_block_coordinates(grid: dict, target_coord: tuple) -> set:
    """
    Apply relationship rules and scoring starting from target_coord to identify all block cells.
    Enforces anchor validation, protected section boundaries, and expansion limits.
    """
    from redaction.block_validator import is_valid_anchor, validate_block_removal
    from redaction.block_removal_audit import log_block_removal
    from redaction.protected_section_detector import get_protected_section_match
    
    target_row, target_col = target_coord
    anchor_cell = grid.get(target_coord)
    anchor_text = anchor_cell.text if anchor_cell else ""
    
    # 1. Validate Anchor
    if not is_valid_anchor(anchor_text):
        log_block_removal(
            anchor=anchor_text,
            start_paragraph=target_row,
            end_paragraph=target_row,
            boundary_detected=False,
            protected_sections_encountered=[],
            decision="blocked"
        )
        return set()
        
    block = {target_coord}
    
    max_row = max(r for r, c in grid.keys()) if grid else 0
    max_col = max(c for r, c in grid.keys()) if grid else 0
    
    # Rule 1 - Adjacent Cell Rule: Add all cells in the same row to the right
    for c in range(target_col + 1, max_col + 1):
        if (target_row, c) in grid:
            cell = grid.get((target_row, c))
            cell_text = cell.text if cell else ""
            # Stop if any adjacent cell in same row is a boundary/protected
            if should_stop_block(cell_text):
                break
            block.add((target_row, c))
            
    # Check if target row has value text in adjacent cells
    target_row_has_value = False
    for c in range(target_col + 1, max_col + 1):
        cell = grid.get((target_row, c))
        if cell and cell.text.strip():
            target_row_has_value = True
            break
            
    # Check subsequent rows
    curr_row = target_row + 1
    boundary_detected = False
    protected_encountered_list = []
    
    while curr_row <= max_row:
        # Check all cells in the row for boundary crossing or protected sections
        row_has_boundary = False
        for c in range(target_col, max_col + 1):
            cell = grid.get((curr_row, c))
            if cell:
                cell_text = cell.text.strip()
                if should_stop_block(cell_text):
                    row_has_boundary = True
                    boundary_detected = True
                    sec_match = get_protected_section_match(cell_text)
                    if sec_match:
                        protected_encountered_list.append(sec_match)
                    break
        if row_has_boundary:
            break
            
        label_cell = grid.get((curr_row, target_col))
        if label_cell is None:
            curr_row += 1
            continue
            
        label_text = label_cell.text.strip()
        same_col_structure = True
        
        # Calculate continuation score
        is_cont = is_continuation_row(
            label_text=label_text,
            same_col_structure=same_col_structure,
            same_formatting=True,
            adjacent_to_block=(curr_row == target_row + 1 or (curr_row - 1, target_col) in block)
        )
        
        if is_cont or label_cell.is_vmerge_continuation:
            # Continuation row
            for c in range(target_col, max_col + 1):
                if (curr_row, c) in grid:
                    block.add((curr_row, c))
            curr_row += 1
        else:
            # Non-empty cell in the label column
            if is_stop_label(label_text):
                boundary_detected = True
                break
                
            # Vertical Layout Rule:
            # If target row has no adjacent value and this is the row directly below
            if not target_row_has_value and curr_row == target_row + 1:
                for c in range(target_col, max_col + 1):
                    if (curr_row, c) in grid:
                        block.add((curr_row, c))
                target_row_has_value = True
                curr_row += 1
            else:
                boundary_detected = True
                break
                
    # Rule 5: Merged Cell Rule - use merged_cell_handler to expand coordinates safely
    block = expand_coordinates_with_merged(grid, block)
    
    # 2. Block Validation Check before removal
    collected_texts = []
    for coord in block:
        cell = grid.get(coord)
        if cell and cell.text:
            collected_texts.append(cell.text)
            
    decision, reason, protected_secs = validate_block_removal(anchor_text, collected_texts)
    
    # Add any protected sections found during expansion
    all_protected = list(set(protected_encountered_list + protected_secs))
    
    start_row = min(r for r, c in block) if block else target_row
    end_row = max(r for r, c in block) if block else target_row
    
    if decision == "ALLOW":
        log_block_removal(
            anchor=anchor_text,
            start_paragraph=start_row,
            end_paragraph=end_row,
            boundary_detected=boundary_detected,
            protected_sections_encountered=all_protected,
            decision="remove",
            block_id=f"block_{target_row}_{target_col}",
            paragraphs_removed=(end_row - start_row + 1)
        )
        return block
    else:
        log_block_removal(
            anchor=anchor_text,
            start_paragraph=start_row,
            end_paragraph=end_row,
            boundary_detected=boundary_detected,
            protected_sections_encountered=all_protected,
            decision="blocked"
        )
        # Return empty set to prevent removal
        return set()

def expand_coordinates_with_merged(grid: dict, block: set) -> set:
    return expand_merged_coordinates(grid, block)
