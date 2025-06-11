def score_row(row, selected_region, selected_segment):
    score = 0
    try:
        if int(row.get("Employees", 0)) < 100:
            score += 1
    except: pass
    if selected_region != "No preference" and row.get("Region") == selected_region:
        score += 1
    if row.get("Funding Stage") in ["Seed", "Series A"]:
        score += 1
    if selected_segment != "No preference" and row.get("Major Segment") == selected_segment:
        score += 1
    return score