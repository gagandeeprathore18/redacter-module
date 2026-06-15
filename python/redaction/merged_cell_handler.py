def get_cell_object(cell_norm):
    return getattr(cell_norm, 'cell_obj', None)

def expand_merged_coordinates(grid: dict, coords: set) -> set:
    """
    Expands the given set of coordinate tuples to include all grid coordinates
    that reference the same underlying python-docx or python-pptx cell object.
    """
    if not grid or not coords:
        return coords
        
    cell_objs = set()
    for coord in coords:
        if coord in grid:
            cell_obj = get_cell_object(grid[coord])
            if cell_obj:
                cell_objs.add(cell_obj)
                
    expanded = set(coords)
    for coord, norm_cell in grid.items():
        cell_obj = get_cell_object(norm_cell)
        if cell_obj and cell_obj in cell_objs:
            expanded.add(coord)
            
    return expanded

def is_cell_merged(grid: dict, coord: tuple) -> bool:
    """
    Returns True if the cell at the given coordinate is merged horizontally or vertically.
    """
    if coord not in grid:
        return False
    cell_obj = get_cell_object(grid[coord])
    if not cell_obj:
        return False
        
    # Count how many grid coordinates reference this same cell object
    count = sum(1 for c, nc in grid.items() if get_cell_object(nc) == cell_obj)
    return count > 1
