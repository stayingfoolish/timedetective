"""Offline evidence explorer for the cached NASA weather demonstration."""

import json
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from timedetective.agent.report import render
from timedetective.packs.earth.adapters.power import PARAMETERS, load_power
from timedetective.packs.earth.run import investigate

st.title("TimeDetective")
st.caption("Reproducible weather evidence · no live model calls")
st.info("Real NASA POWER daily records, 2000–2024, queried at 3°N, 42°E. "
        "This is a grid-cell comparison—not an average for the Horn of Africa. "
        "Current findings are descriptive, not calibrated climate attribution or forecasts.")
raw = Path(__file__).resolve().parents[1] / "data/cache/earth/power_3N_42E_2000_2024_20261115.json"
with st.form("investigation"):
    question = st.text_area("Question", "How did MAM and OND rainfall in 2020–2022 compare with the earlier baseline, and what does the record establish about lasting decline?")
    parameter = st.selectbox("Variable", list(PARAMETERS))
    seasons = st.selectbox("Season definition", ["MAM and OND", "Each calendar month", "Calendar year"])
    baseline = st.slider("Baseline years", 2000, 2024, (2000, 2019))
    event = st.slider("Event years", 2000, 2024, (2020, 2022))
    compare = st.checkbox("Compare the two precipitation products", value=True)
    submitted = st.form_submit_button("Investigate cached data")
if submitted:
    x = load_power(raw, parameter)
    other = {"PRECTOTCORR": "IMERG_PRECTOT", "IMERG_PRECTOT": "PRECTOTCORR"}.get(parameter)
    companion = load_power(raw, other) if compare and other else None
    season_map = {"MAM": [3, 4, 5], "OND": [10, 11, 12]} if seasons == "MAM and OND" else (
        {f"month_{m:02d}": [m] for m in range(1, 13)} if seasons == "Each calendar month" else {"annual": list(range(1, 13))})
    finding = investigate(x, question=question, companion=companion, seasons=season_map,
                          baseline=baseline, event=event)
    st.subheader("Finding")
    if finding.claim:
        st.write(finding.claim.statement)
        st.write("Claim strength:", finding.claim.strength)
    else:
        st.warning("No claim: required inputs or analysis capability are missing.")
    for step in finding.path:
        values = json.loads(step.values_json)
        if step.node == "seasons":
            for label, evidence in values["seasons"].items():
                st.subheader(label)
                st.write(f"Event mean anomaly: {evidence['event_mean_anomaly']:.2f} {evidence['unit']}")
                st.line_chart(pd.DataFrame(evidence["years"]).set_index("year")[["anomaly"]])
        with st.expander(f"Evidence: {step.node}"):
            st.write("Source:", step.source, "| Edge:", step.edge_source)
            st.json(values)
    for refusal in finding.refusals:
        st.warning(f"{refusal.procedure}: {refusal.failed}. Needed: {refusal.would_change}")
    st.download_button("Download Finding JSON", finding.model_dump_json(indent=2), "weather_finding.json")
    st.download_button("Download evidence report", render(finding), "weather_finding.md")

st.divider()
st.header("Automatic precipitation investigation")
st.caption("Distill an explicit request, then fetch real NASA data. Preview never calls the API. "
           "Trend/change bootstrap tests failed dependence calibration and remain experimental.")
from timedetective.agent.precipitation import distill
from timedetective.packs.earth.precipitation import investigate_question, render_run

with st.form("automatic_precipitation"):
    live_question = st.text_area("Precipitation question", "Is annual rainfall trending, and do MERRA-2 and IMERG agree?")
    lat = st.number_input("Latitude", min_value=-90., max_value=90., value=3.)
    lon = st.number_input("Longitude", min_value=-180., max_value=180., value=42.)
    first = st.number_input("First complete year", min_value=1981, max_value=date.today().year-1, value=2000)
    last = st.number_input("Last complete year", min_value=1981, max_value=date.today().year-1, value=2024)
    reference = st.text_input("Baseline years (start,end)", "2000,2019")
    comparison_period = st.text_input("Comparison years (start,end)", "2020,2022")
    season_json = st.text_area("Seasons JSON", '{"annual":[1,2,3,4,5,6,7,8,9,10,11,12]}')
    methods = st.multiselect("Requested analyses", ["summary", "trend", "period_change", "changepoint", "extremes", "spi", "return_levels", "timing", "agreement"],
                            default=["summary", "trend", "agreement"])
    target = st.selectbox("Statistical target", ["seasonal_total", "rx1day", "rx5day", "wet_days", "dry_spell", "sdii"])
    windows = st.text_input("Timing search windows JSON (required only for timing)", "null")
    offline = st.checkbox("Use downloaded cache only", value=False)
    preview = st.form_submit_button("Preview distilled request")
    fetch = st.form_submit_button("Fetch and investigate precipitation")
if preview or fetch:
    try:
        controls = dict(latitude=lat, longitude=lon, start=f"{int(first)}-01-01", end=f"{int(last)}-12-31",
            baseline=[int(v.strip()) for v in reference.split(",")], event=[int(v.strip()) for v in comparison_period.split(",")],
            seasons=json.loads(season_json), analyses=methods, target=target, timing_windows=json.loads(windows))
        plan = distill(live_question, **controls)
        st.json(plan.model_dump(mode="json"))
        if fetch:
            with st.spinner("Acquiring and checking NASA records, then running cited procedures…"):
                st.session_state["precipitation_result"] = investigate_question(live_question, **controls,
                    cache_dir=raw.parents[3] / "downloads/power", offline=offline)
    except (ValueError, TypeError) as exc:
        st.error(f"Distillation refused before acquisition: {exc}")
if "precipitation_result" in st.session_state:
    bundle = st.session_state["precipitation_result"]
    st.info("The request and all refusals are retained. Nominal p-values are not certified significance claims.")
    for product, finding_data in bundle["findings"].items():
        with st.expander(f"Precipitation evidence: {product}"):
            st.json(finding_data)
        for item in finding_data["refusals"]:
            st.warning(f"{product} / {item['procedure']}: {item['failed']}. Needed: {item['would_change']}")
    if bundle.get("global_family"):
        with st.expander("Statistical results across all products"):
            st.json(bundle["global_family"])
    st.download_button("Download precipitation investigation", json.dumps(bundle, indent=2, allow_nan=False), "precipitation_investigation.json")
    st.download_button("Download precipitation report", render_run(bundle), "precipitation_report.md")
