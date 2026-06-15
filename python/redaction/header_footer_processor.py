def get_docx_headers_footers(doc):
    """
    Returns a list of all header and footer objects in the given docx Document.
    Handles different_first_page_header_footer, even_and_odd_headers_footers, etc.
    """
    headers_footers = []
    for section in doc.sections:
        if section.header:
            headers_footers.append(section.header)
        if section.footer:
            headers_footers.append(section.footer)
        if hasattr(section, 'first_page_header') and section.first_page_header:
            headers_footers.append(section.first_page_header)
        if hasattr(section, 'first_page_footer') and section.first_page_footer:
            headers_footers.append(section.first_page_footer)
        if hasattr(section, 'even_page_header') and section.even_page_header:
            headers_footers.append(section.even_page_header)
        if hasattr(section, 'even_page_footer') and section.even_page_footer:
            headers_footers.append(section.even_page_footer)
    return headers_footers

def process_docx_headers_footers(doc, p_callback, t_callback):
    """
    Applies the paragraph and table callbacks to all header/footer sections in doc.
    """
    for hf in get_docx_headers_footers(doc):
        for p in hf.paragraphs:
            p_callback(p)
        for table in hf.tables:
            t_callback(table)
