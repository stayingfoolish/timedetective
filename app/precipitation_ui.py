"""Present a precipitation run as an inspectable story, without changing its evidence."""

import json

import pandas as pd
import streamlit as st

from timedetective.packs.earth.precipitation import render_run

PRODUCT_NAMES = {"PRECTOTCORR": "MERRA-2 corrected rainfall", "IMERG_PRECTOT": "IMERG satellite rainfall"}
STAGES = ["1 · Question", "2 · Data", "3 · Checks", "4 · Answer"]
STEP_PURPOSE = {
    "audit": "Check the record and its spatial support",
    "monthly": "Build the monthly record",
    "totals": "Measure precipitation totals",
    "summary": "Compare seasons with the baseline",
    "trend": "Describe the trend evidence",
    "period": "Compare the selected periods",
    "changepoint": "Check for an abrupt shift",
    "spells": "Inspect wet and dry spells",
    "spi": "Calculate the requested precipitation index",
    "return_levels": "Estimate the requested return levels",
    "timing": "Check seasonal timing",
    "comparison": "Compare seasonal results across products",
    "daily_agreement": "Compare daily product agreement",
    "family": "Account for the declared family of tests",
}


def show_precipitation_story(plan: dict | None, bundle: dict | None) -> None:
    """Show only what the distilled request and recorded Findings establish."""
    if plan is None and bundle is None:
        return
    st.markdown("### Follow this rainfall investigation")
    st.caption("Choose a stage to inspect. The checks and answers below come from the recorded run, not a generated explanation.")
    if bundle:
        for product, finding in bundle["findings"].items():
            if not finding["path"]:
                for refusal in finding["refusals"]:
                    st.warning(f"{PRODUCT_NAMES.get(product, product)}: {refusal['failed']}. Needed: {refusal['would_change']}")
    available = STAGES if bundle else STAGES[:1]
    if st.session_state.get("precip_story_stage") not in available:
        st.session_state["precip_story_stage"] = available[0]
    stage = st.radio("Investigation stage", available, horizontal=True, key="precip_story_stage")
    with st.container(border=True):
        if stage == STAGES[0]:
            request = plan or bundle.get("request")
            st.subheader("What will be checked")
            if not request:
                st.warning("The question could not be distilled into a supported precipitation request.")
                return
            st.write(request["question"])
            a, b, c = st.columns(3)
            a.metric("Latitude", f"{request['latitude']:g}°")
            b.metric("Longitude", f"{request['longitude']:g}°")
            c.metric("Record", f"{request['start'][:4]}–{request['end'][:4]}")
            st.write(f"**Baseline:** {request['baseline'][0]}–{request['baseline'][1]} · "
                     f"**Comparison:** {request['event'][0]}–{request['event'][1]}")
            st.write(f"**Analyses:** {', '.join(request['analyses'])} · **Target:** {request['target']}")
            st.write(f"**Seasons:** {request['seasons']}")
            st.caption("This is a gridded point query, not an average over a whole region. Check the controls above before fetching.")
            with st.expander("Complete distilled request"):
                st.json(request)
        elif stage == STAGES[1]:
            st.subheader("Where the records came from")
            st.caption("Each product keeps its own coverage and provenance. A missing product is reported, not replaced.")
            for product, coverage in bundle.get("coverage", {}).items():
                finding = bundle["findings"][product]
                with st.container(border=True):
                    st.markdown(f"**{PRODUCT_NAMES.get(product, product)}**")
                    st.write(f"Requested from {coverage['requested_start']} to {coverage['end']}; "
                             f"provider coverage in this run starts {coverage['provider_start']}.")
                    if coverage["precoverage_unavailable"]:
                        st.info("The product does not cover the full requested period; the earlier part was not invented.")
                    st.write(f"**Recorded subjects:** {len(finding['subject'])} · **Completed steps:** {len(finding['path'])}")
                    for subject in finding["subject"]:
                        with st.expander(f"Provenance: {subject['name']}"):
                            st.json(json.loads(subject["metadata_json"]))
                    for refusal in finding["refusals"]:
                        st.warning(f"{refusal['failed']}. Needed: {refusal['would_change']}")
        elif stage == STAGES[2]:
            st.subheader("What the checks recorded")
            st.caption("Open a step for its values, procedure and source. Skipped analyses remain visible in the recorded path.")
            for product, finding in bundle["findings"].items():
                st.markdown(f"#### {PRODUCT_NAMES.get(product, product)}")
                if not finding["path"]:
                    st.info("No analysis steps ran for this product.")
                for position, step in enumerate(finding["path"], 1):
                    purpose = STEP_PURPOSE.get(step["node"], step["node"].replace("_", " ").title())
                    with st.expander(f"{position}. {purpose}"):
                        st.caption(f"Procedure: {step['procedure']} · Method source: {step['source']} · Routing source: {step['edge_source']}")
                        values = json.loads(step["values_json"])
                        if step["node"] == "summary" and isinstance(values.get("seasons"), dict):
                            for name, season in values["seasons"].items():
                                st.write(f"**{name}**")
                                if "event_mean_anomaly" in season:
                                    st.write(f"Recorded comparison anomaly: {season['event_mean_anomaly']:.2f} {season.get('unit', '')}")
                                years = season.get("years", [])
                                if years and all("year" in row and "anomaly" in row for row in years):
                                    st.line_chart(pd.DataFrame(years).set_index("year")[["anomaly"]])
                        st.json(values, expanded=False)
        else:
            st.subheader("What the evidence supports")
            st.info("Precipitation findings are descriptive. Nominal p-values and experimental bootstrap tests do not certify significance.")
            for product, finding in bundle["findings"].items():
                st.markdown(f"#### {PRODUCT_NAMES.get(product, product)}")
                if finding["claim"]:
                    st.write(finding["claim"]["statement"])
                    st.caption(f"Claim strength: {finding['claim']['strength']}")
                else:
                    st.warning("No scientific claim was made for this product.")
                for refusal in finding["refusals"]:
                    st.write(f"**What stopped or limited a check:** {refusal['failed']}. Needed: {refusal['would_change']}")
                if finding["would_strengthen"]:
                    st.write("**What would strengthen it:**")
                    for item in finding["would_strengthen"]:
                        st.write(f"- {item}")
            if bundle.get("global_family"):
                for step in bundle["global_family"]["path"]:
                    values = json.loads(step["values_json"])
                    if values.get("interpretation"):
                        st.write(values["interpretation"])
            for limitation in bundle.get("limitations", []):
                st.caption(limitation)
    if bundle:
        with st.expander("Full evidence and downloads"):
            st.json(bundle, expanded=False)
            st.download_button("Download precipitation investigation", json.dumps(bundle, indent=2, allow_nan=False),
                               "precipitation_investigation.json")
            st.download_button("Download precipitation report", render_run(bundle), "precipitation_report.md")
