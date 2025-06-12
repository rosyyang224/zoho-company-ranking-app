import streamlit as st
import pandas as pd

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

def compute_score(row, config):
    score = 0
    emp_val = row.get("Employees", None)
    region_val = row.get("Region", "")
    funding_val = row.get("Funding Stage", "")
    segment_val = row.get("Major Segment", "")
    threshold = config.get("threshold", 100)

    try:
        emp = int(emp_val) if pd.notnull(emp_val) else None
    except:
        emp = None

    if config["mode"] == "point":
        if config.get("employee") and emp is not None and emp < threshold:
            score += 1
        if config.get("region") and config.get("selected_region") and region_val == config["selected_region"]:
            score += 1
        if config.get("funding") and config.get("selected_funding") and funding_val == config["selected_funding"]:
            score += 1
        if config.get("segment") and config.get("selected_segment") and segment_val == config["selected_segment"]:
            score += 1
    else:
        if emp is not None and emp < threshold:
            score += config.get("employee", 0.0)
        if region_val in config.get("selected_regions", []):
            score += config.get("region", 0.0)
        if funding_val in config.get("selected_funding", []):
            score += config.get("funding", 0.0)
        if segment_val in config.get("selected_segments", []):
            score += config.get("segment", 0.0)

    return score

def show_ranking_config(df, key_prefix="rank"):
    mode = st.radio(
        "Choose scoring mode:",
        ["Point-Based", "Weighted"],
        horizontal=True,
        key=f"{key_prefix}_mode"
    )

    region_options = ["No preference"] + sorted(df.get("Region", pd.Series()).dropna().unique())
    segment_options = ["No preference"] + sorted(df.get("Major Segment", pd.Series()).dropna().unique())
    funding_options = ["No preference"] + sorted(df.get("Funding Stage", pd.Series()).dropna().unique())

    if mode == "Point-Based":
        employee_pref = st.selectbox(
            "Employee threshold",
            options=["No preference", "Custom threshold..."],
            key=f"{key_prefix}emp_pref_choice"
        )

        employee_threshold = None
        if employee_pref == "Custom threshold...":
            employee_threshold = st.number_input(
                "Specify threshold (e.g. < 100)",
                min_value=1,
                max_value=10000,
                value=100,
                step=10,
                key=f"{key_prefix}emp_threshold_input"
            )

        selected_region = st.selectbox(
            "Preferred Region", options=region_options, key=f"{key_prefix}_point_region_select")
        selected_segment = st.selectbox(
            "Preferred Major Segment", options=segment_options, key=f"{key_prefix}_point_segment_select")
        selected_funding = st.selectbox(
            "Preferred Funding Stage", options=funding_options, key=f"{key_prefix}_point_funding_select")

        return {
            "mode": "point",
            "region": selected_region != "No preference",
            "funding": selected_funding != "No preference",
            "segment": selected_segment != "No preference",
            "threshold": employee_threshold,
            "selected_region": selected_region if selected_region != "No preference" else None,
            "selected_segment": selected_segment if selected_segment != "No preference" else None,
            "selected_funding": selected_funding if selected_funding != "No preference" else None,
        }

    else:
        col1, col2 = st.columns(2)

        with col1:
            employee_threshold = st.number_input(
                "Employee count threshold",
                min_value=1,
                max_value=1000,
                value=100,
                step=10,
                key=f"{key_prefix}_emp_thresh"
            )
            selected_regions = st.multiselect(
                "Preferred Regions",
                options=region_options,
                key=f"{key_prefix}_regions"
            )
            selected_segments = st.multiselect(
                "Preferred Major Segments",
                options=segment_options,
                key=f"{key_prefix}_segments"
            )
            selected_funding = st.multiselect(
                "Preferred Funding Stages",
                options=funding_options,
                default=["Seed", "Series A"] if "Seed" in funding_options else [],
                key=f"{key_prefix}_funding"
            )

        with col2:
            st.markdown("")
            weight_emp = st.slider(
                "Weight for employees < threshold", 0.0, 2.0, 1.0,
                key=f"{key_prefix}_weight_emp",
                label_visibility="collapsed"
            )
            st.markdown("")
            weight_region = st.slider(
                "Weight for region match", 0.0, 2.0, 1.0,
                key=f"{key_prefix}_weight_region",
                label_visibility="collapsed"
            )
            st.markdown("")
            weight_funding = st.slider(
                "Weight for funding stage match", 0.0, 2.0, 1.0,
                key=f"{key_prefix}_weight_funding",
                label_visibility="collapsed"
            )
            st.markdown("")
            weight_segment = st.slider(
                "Weight for major segment match", 0.0, 2.0, 1.0,
                key=f"{key_prefix}_weight_segment",
                label_visibility="collapsed"
            )

        return {
            "mode": "weighted",
            "employee": weight_emp,
            "region": weight_region,
            "funding": weight_funding,
            "segment": weight_segment,
            "threshold": employee_threshold,
            "selected_regions": selected_regions,
            "selected_segments": selected_segments,
            "selected_funding": selected_funding,
        }