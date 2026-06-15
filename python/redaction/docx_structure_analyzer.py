def analyze_and_redact_runs(runs, find_pattern_or_fn, replacement=" "):
    """
    Given a list of python-docx runs, reconstructs the full text,
    finds matches using a pattern or a callback function, and maps
    the matched character ranges back to individual runs to replace
    the text in-place while preserving formatting.
    
    find_pattern_or_fn can be:
    - a compiled regex pattern
    - a callable that takes full_text and returns list of (start, end) ranges
    """
    if not runs:
        return
        
    # Reconstruct text and track run boundaries
    full_text = ""
    run_ranges = []
    for run in runs:
        run_text = run.text if run.text is not None else ""
        start = len(full_text)
        full_text += run_text
        end = len(full_text)
        run_ranges.append((start, end, run))
        
    # Find matching ranges
    ranges = []
    if hasattr(find_pattern_or_fn, 'finditer'):
        # Compiled regex pattern
        for match in find_pattern_or_fn.finditer(full_text):
            ranges.append((match.start(), match.end()))
    elif callable(find_pattern_or_fn):
        # Callback function
        ranges = find_pattern_or_fn(full_text)
        
    if not ranges:
        return
        
    # Sort and merge overlapping/adjacent ranges to avoid issues, then process reverse
    ranges.sort(key=lambda x: x[0])
    merged_ranges = []
    for current in ranges:
        if not merged_ranges:
            merged_ranges.append(current)
        else:
            prev_start, prev_end = merged_ranges[-1]
            curr_start, curr_end = current
            if curr_start < prev_end:
                merged_ranges[-1] = (prev_start, max(prev_end, curr_end))
            else:
                merged_ranges.append(current)
                
    # Process reverse (back to front) to preserve offsets of earlier runs
    merged_ranges.sort(key=lambda x: x[0], reverse=True)
    
    for start, end in merged_ranges:
        # Find runs overlapping this range
        overlapping = []
        for r_start, r_end, run in run_ranges:
            if max(r_start, start) < min(r_end, end):
                overlapping.append((r_start, r_end, run))
                
        if not overlapping:
            continue
            
        # Replace the characters within the matched index range across overlapping runs
        for i, (r_start, r_end, run) in enumerate(overlapping):
            run_text = run.text if run.text is not None else ""
            
            # Identify what parts of the run's text are outside/inside the matched range
            # Prefix: text before the match
            prefix = ""
            if r_start < start:
                prefix = run_text[:start - r_start]
                
            # Suffix: text after the match
            suffix = ""
            if r_end > end:
                suffix = run_text[end - r_start:]
                
            # Perform replacement in the first overlapping run, and empty the other overlapping runs
            if i == 0:
                run.text = prefix + replacement + suffix
            else:
                run.text = prefix + suffix
