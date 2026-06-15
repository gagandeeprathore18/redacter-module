def validate_table_redaction(original_grid: dict, final_grid: dict, block_coords: set) -> bool:
    """
    Validates table redactions:
    1. Table size and coordinates are preserved.
    2. Target cells cleared.
    3. No orphan continuation rows are left.
    """
    if len(original_grid) != len(final_grid):
        print("Warning: Table grid size changed!")
        return False
        
    for coord in block_coords:
        if coord in final_grid:
            cell_text = final_grid[coord].text.strip()
            if cell_text:
                print(f"Warning: Cell at {coord} not fully cleared! Content: '{cell_text}'")
                return False

    # Check for orphan continuation rows (a row where the label is empty/continuation,
    # but the adjacent value cells are non-empty, and it was not included in the redaction block
    # while a preceding adjacent row was redacted).
    max_row = max(r for r, c in original_grid.keys()) if original_grid else 0
    for r in range(1, max_row + 1):
        # Check if row r has empty label cell in column 0
        label_cell = final_grid.get((r, 0))
        if label_cell and not label_cell.text.strip():
            # If the row directly above (r-1) was redacted
            if any((r - 1, c) in block_coords for c in range(10)):
                # And this row (r) was NOT redacted
                if not any((r, c) in block_coords for c in range(10)):
                    # Check if it has content on the right
                    has_content = False
                    for c in range(1, 10):
                        val_cell = final_grid.get((r, c))
                        if val_cell and val_cell.text.strip():
                            has_content = True
                            break
                    if has_content:
                        print(f"Warning: Potential orphan continuation row detected at row {r}!")
                        return False
                        
    return True
