import re

class NormalizedCell:
    def __init__(self, r, c, cell_obj, is_docx, text, is_vmerge_continuation=False):
        self.r = r
        self.c = c
        self.cell_obj = cell_obj  # docx.table._Cell or pptx.table._Cell
        self.is_docx = is_docx
        self.text = text
        self.is_vmerge_continuation = is_vmerge_continuation

def is_docx_vmerge_continuation(cell) -> bool:
    try:
        tcPr = cell._tc.tcPr
        if tcPr is None:
            return False
        vMerge_list = tcPr.xpath('w:vMerge')
        if not vMerge_list:
            return False
        vMerge = vMerge_list[0]
        val = vMerge.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val')
        return val != 'restart'
    except Exception:
        return False

def parse_docx_table(table) -> dict:
    """
    Returns a dict mapping (r, c) -> NormalizedCell
    """
    grid = {}
    for r_idx, row in enumerate(table.rows):
        for c_idx, cell in enumerate(row.cells):
            text = "".join(p.text for p in cell.paragraphs).strip()
            is_vcont = is_docx_vmerge_continuation(cell)
            grid[(r_idx, c_idx)] = NormalizedCell(
                r=r_idx,
                c=c_idx,
                cell_obj=cell,
                is_docx=True,
                text=text,
                is_vmerge_continuation=is_vcont
            )
    return grid

def parse_pptx_table(table) -> dict:
    """
    Returns a dict mapping (r, c) -> NormalizedCell
    """
    grid = {}
    for r_idx, row in enumerate(table.rows):
        for c_idx, cell in enumerate(row.cells):
            text = cell.text_frame.text.strip() if cell.text_frame else ""
            # pptx vertical merge detection is not standard in python-pptx,
            # but we can check if it's empty as a fallback or if it's merged.
            grid[(r_idx, c_idx)] = NormalizedCell(
                r=r_idx,
                c=c_idx,
                cell_obj=cell,
                is_docx=False,
                text=text,
                is_vmerge_continuation=False
            )
    return grid

def normalize_table(table) -> dict:
    # Check if table is python-docx or python-pptx
    # We can detect by checking attributes or class name
    class_name = table.__class__.__name__
    if 'Table' in class_name:
        # Check if python-docx Table
        if hasattr(table, 'rows') and len(table.rows) > 0:
            first_row = table.rows[0]
            if hasattr(first_row, 'cells'):
                # Check cell type
                if len(first_row.cells) > 0:
                    first_cell = first_row.cells[0]
                    if hasattr(first_cell, 'paragraphs'):
                        return parse_docx_table(table)
                    else:
                        return parse_pptx_table(table)
    return {}
