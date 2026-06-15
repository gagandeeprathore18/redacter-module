def extract_block_cells(grid: dict, block_coords: set) -> list:
    """
    Returns unique Cell objects corresponding to the block coordinates.
    """
    unique_cells = []
    seen = set()
    for coord in sorted(list(block_coords)):
        if coord in grid:
            cell_obj = grid[coord].cell_obj
            if cell_obj not in seen:
                seen.add(cell_obj)
                unique_cells.append(cell_obj)
    return unique_cells
