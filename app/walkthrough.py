"""The groundwater walkthrough: one question followed through the six steps of water_and_greenness_check.

Everything shown comes from the Finding the check returns, from the records it was given, or from the
playbook and procedure files. Nothing is fetched and no model is called.
"""

import json
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

from timedetective.agent.report import render
from timedetective.engine.critic import CALIBRATED
from timedetective.packs.earth.adapters.gldas import groundwater_estimate, load_gldas_storage
from timedetective.packs.earth.adapters.mod13c2 import load_mod13c2_region
from timedetective.packs.earth.adapters.stories import load_gsfc_mascons, load_power_regional
from timedetective.packs.earth.stories import check_storage_and_greenness

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data/cache/earth/stories"
PLAYBOOK = ROOT / "knowledge/playbooks/water_and_greenness_check.yaml"
QUESTION = "Is the water under these farms running out, and would the fields show it?"
SMALL_BLOCKS = 3
AREAS = {  # label -> (cached region, number of blocks to declare; None means the whole region)
    "North-west India: Punjab, Haryana, Delhi, northern Rajasthan": ("nw_india", None),
    "US High Plains: western Kansas and its neighbours": ("high_plains", None),
    f"Only {SMALL_BLOCKS} blocks of north-west India (about the size of a few districts)": ("nw_india", SMALL_BLOCKS),
}
STEPS = {  # playbook node -> the question a student would ask at that step
    "audit": "How can anyone know what is underground?",
    "annual": "Is it actually falling?",
    "trend": "Is that real, or could it be noise?",
    "handover": "Could it be the satellites and not the water?",
    "rainfall": "Is it just a dry spell?",
    "greenness": "Would you see it from the fields?",
}
TABS = ["1 Underground?", "2 Falling?", "3 Noise?", "4 Satellites?", "5 Dry spell?", "6 Fields?"]
GUIDE_TITLES = ["The question", *STEPS.values(), "The verdict"]
BLUE, ORANGE, AQUA, YELLOW, GREY = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#9d9b93"
MINUS = "−"


def num(x: float, digits: int = 1, signed: bool = False) -> str:
    text = f"{abs(x):.{digits}f}"
    return (MINUS if x < 0 else "+" if signed else "") + text


def span(low: float, high: float, digits: int = 1) -> str:
    return f"{num(low, digits, True)} to {num(high, digits, True)}"


@st.cache_data(show_spinner="Loading the cached NASA records")
def records(tag: str) -> dict:
    """The four records for a region, each loaded through its adapter (checksums are verified there)."""
    meta = CACHE / f"gsfc_mascons_{tag}.meta.yaml"
    total = load_gsfc_mascons(CACHE / f"gsfc_mascons_{tag}.csv")
    modelled = load_gldas_storage(CACHE / f"gldas_noah025_m_{tag}.json.gz", meta)
    return {"total": total, "modelled": modelled, "groundwater": groundwater_estimate(total, modelled),
            "rain": load_power_regional(CACHE / f"power_monthly_PRECTOTCORR_SUM_{tag}_2000_2025_20261115.json", "PRECTOTCORR_SUM"),
            "green": load_mod13c2_region(CACHE / f"mod13c2_{tag}.json.gz", meta)}


@st.cache_data(show_spinner="Running the six checks")
def follow(tag: str, question: str, blocks: int | None):
    """Run the playbook. `blocks` declares a smaller area, to show what the check does with a region it cannot resolve."""
    r = records(tag)
    storage = r["groundwater"]
    if blocks is not None:
        storage = storage.copy()
        storage.attrs = {**storage.attrs, "resolution_units": blocks}
    return check_storage_and_greenness(storage, question=question, vegetation=r["green"], rainfall=r["rain"])


@st.cache_data
def knowledge() -> dict:
    playbook = yaml.safe_load(PLAYBOOK.read_text())
    procedures = {p.stem: yaml.safe_load(p.read_text()) for p in (ROOT / "knowledge/procedures").glob("*/*.yaml")}
    return {"playbook": playbook, "playbook_text": PLAYBOOK.read_text(), "procedures": procedures,
            "sources": yaml.safe_load((ROOT / "knowledge/sources.yaml").read_text())}


def source_link(key: str) -> str:
    source = knowledge()["sources"].get(key, {})
    title, url = source.get("title", key), source.get("url")
    return f"[{title}]({url})" if url and str(url).startswith("http") else f"{title} (`{url}`)" if url else title


def led_to(step) -> str:
    """Where the playbook sent the run after this step: ok, skipped, finding or refused."""
    edge = next(e for e in knowledge()["playbook"]["edges"] if e["id"] == step.edge_taken)
    if edge["target"] == "refused":
        return "refused"
    if edge["outcome"] != "ok":
        return "skipped"
    return "finding" if edge["target"] == "described" else "ok"


def procedure_line(position: int, step) -> None:
    p = knowledge()["procedures"][step.procedure]
    outcome = led_to(step)
    st.caption(f"Step {position} of {len(STEPS)} · `{step.procedure}` ({p['category']}) · needs {', '.join(p['requires'])} · "
               f"returns {', '.join(p['produces'])} · rule from {source_link(step.source)} → **{outcome}**")


def chart(data: pd.DataFrame, spec: dict) -> None:
    st.vega_lite_chart(data, spec)


def monthly_chart(r: dict, gap: tuple[str, str]) -> None:
    names = ["All stored water", "Soil moisture and snow (model)", "Groundwater estimate"]
    index = r["total"].index
    frame = pd.DataFrame({"month": index, names[0]: r["total"].to_numpy(), names[1]: r["modelled"].reindex(index).to_numpy(),
                          names[2]: r["groundwater"].to_numpy()}).melt("month", var_name="series", value_name="cm")
    chart(frame, {"height": 300, "layer": [
        {"data": {"values": [{"start": gap[0], "end": gap[1]}]}, "mark": {"type": "rect", "color": GREY, "opacity": 0.18},
         "encoding": {"x": {"field": "start", "type": "temporal"}, "x2": {"field": "end"}}},
        {"mark": {"type": "line", "strokeWidth": 1.6},
         "encoding": {"x": {"field": "month", "type": "temporal", "title": None},
                      "y": {"field": "cm", "type": "quantitative", "title": "cm of water"},
                      "color": {"field": "series", "type": "nominal", "scale": {"domain": names, "range": [GREY, YELLOW, BLUE]},
                                "legend": {"orient": "top", "title": None, "labelLimit": 320}},
                      "tooltip": [{"field": "month", "type": "temporal", "format": "%b %Y"}, {"field": "series"}, {"field": "cm", "format": ".1f"}]}}]})


def annual_chart(annual: list[dict]) -> None:
    frame = pd.DataFrame(annual)
    chart(frame, {"height": 280, "mark": {"type": "line", "point": {"size": 50}, "color": BLUE, "strokeWidth": 2},
                  "encoding": {"x": {"field": "year", "type": "quantitative", "title": None, "axis": {"format": "d"}, "scale": {"zero": False}},
                               "y": {"field": "value", "type": "quantitative", "title": "cm of water"},
                               "tooltip": [{"field": "year"}, {"field": "value", "format": ".1f", "title": "cm"}]}})


def changes_chart(annual: list[dict], mean_change: float) -> None:
    frame = pd.DataFrame(annual)
    frame["change"] = frame["value"].diff()
    frame = frame.dropna(subset=["change"])
    chart(frame, {"height": 260, "layer": [
        {"mark": {"type": "bar", "color": BLUE, "size": 16, "cornerRadiusEnd": 3},
         "encoding": {"x": {"field": "year", "type": "quantitative", "title": None, "axis": {"format": "d"}, "scale": {"zero": False}},
                      "y": {"field": "change", "type": "quantitative", "title": "cm of water"},
                      "tooltip": [{"field": "year"}, {"field": "change", "format": "+.1f", "title": "cm"}]}},
        {"data": {"values": [{"mean": mean_change}]}, "mark": {"type": "rule", "strokeWidth": 2}, "encoding": {"y": {"field": "mean", "type": "quantitative"}}}]})


def rank_chart(share: float) -> None:
    chart(pd.DataFrame([{"share": share}]), {"height": 70, "layer": [
        {"mark": {"type": "bar", "color": BLUE, "height": 22},
         "encoding": {"x": {"field": "share", "type": "quantitative", "scale": {"domain": [0, 1]},
                            "axis": {"format": "%", "title": "share of other stretches that moved as much as the real gap"}},
                      "tooltip": [{"field": "share", "format": ".1%"}]}},
        {"data": {"values": [{"bar": 0.05, "label": "a caution is raised below 5%"}]}, "layer": [
            {"mark": {"type": "rule", "strokeWidth": 2, "strokeDash": [4, 3]}, "encoding": {"x": {"field": "bar", "type": "quantitative"}}},
            {"mark": {"type": "text", "align": "left", "dx": 6, "dy": -22}, "encoding": {"x": {"field": "bar", "type": "quantitative"}, "text": {"field": "label"}}}]}]})


def rain_chart(v: dict) -> None:
    frame = pd.DataFrame(v["pairs"])
    mean, a, b = v["average_rainfall_mm_per_year"], v["storage_change_at_average_rainfall_cm_per_year"], v["response_cm_per_100mm"]
    low, high = frame["rainfall_mm_per_year"].min(), frame["rainfall_mm_per_year"].max()
    fitted = [{"rain": x, "fit": a + b * (x - mean) / 100} for x in (low, high)]
    reading = [{"rain": mean, "at": a, "low": v["interval_at_average_rainfall"][0], "high": v["interval_at_average_rainfall"][1]}]
    x = {"field": "rainfall_mm_per_year", "type": "quantitative", "title": "rain over the same two years, mm a year", "scale": {"zero": False}}
    chart(frame, {"height": 320, "layer": [
        {"mark": {"type": "point", "filled": True, "size": 70, "color": BLUE},
         "encoding": {"x": x, "y": {"field": "storage_change_cm", "type": "quantitative", "title": "cm of water"},
                      "tooltip": [{"field": "year"}, {"field": "storage_change_cm", "format": "+.1f", "title": "cm"},
                                  {"field": "rainfall_mm_per_year", "format": ".0f", "title": "mm a year"}]}},
        {"data": {"values": fitted}, "mark": {"type": "line", "color": BLUE, "opacity": 0.55, "strokeWidth": 2},
         "encoding": {"x": {"field": "rain", "type": "quantitative"}, "y": {"field": "fit", "type": "quantitative"}}},
        {"data": {"values": reading}, "mark": {"type": "rule", "color": ORANGE, "strokeWidth": 1.5}, "encoding": {"x": {"field": "rain", "type": "quantitative"}}},
        {"data": {"values": reading}, "mark": {"type": "rule", "strokeWidth": 4},
         "encoding": {"x": {"field": "rain", "type": "quantitative"}, "y": {"field": "low", "type": "quantitative"}, "y2": {"field": "high"}}},
        {"data": {"values": reading}, "mark": {"type": "point", "filled": True, "size": 160, "color": "black", "stroke": "white", "strokeWidth": 1.5},
         "encoding": {"x": {"field": "rain", "type": "quantitative"}, "y": {"field": "at", "type": "quantitative"}}},
        {"data": {"values": [{"zero": 0}]}, "mark": {"type": "rule", "color": GREY}, "encoding": {"y": {"field": "zero", "type": "quantitative"}}}]})


def fields_chart(yearly: list[dict]) -> None:
    frame = pd.DataFrame(yearly)
    for field, title, color, digits, zero in (("storage_cm", "cm of water", BLUE, 1, True), ("greenness", "NDVI", AQUA, 3, False)):
        st.caption("Groundwater estimate, one value per year." if field == "storage_cm" else "Greenness of the land, one value per year.")
        chart(frame, {"height": 190, "mark": {"type": "line", "point": {"size": 45}, "color": color, "strokeWidth": 2},
                      "encoding": {"x": {"field": "year", "type": "quantitative", "title": None, "axis": {"format": "d"}, "scale": {"zero": False}},
                                   "y": {"field": field, "type": "quantitative", "title": title, "scale": {"zero": zero}},
                                   "tooltip": [{"field": "year"}, {"field": field, "format": f".{digits}f"}]}})


def step_audit(v: dict, r: dict, gap: tuple[str, str]) -> None:
    st.write("By weighing it from orbit. The GRACE and GRACE-FO satellites measure tiny changes in Earth's gravity as water moves, which "
             "gives the change in all the water stored in a region. A NASA land model, GLDAS, estimates the soil moisture and snow. "
             "Subtract that, and what is left is an estimate of groundwater, in centimetres of water spread over the whole region.")
    monthly_chart(r, gap)
    st.caption("The shaded stretch is the gap between the two missions. Surface water (rivers, canals, reservoirs) is not subtracted.")
    if "years" in v:
        a, b, c = st.columns(3)
        a.metric("Record", f"{v['years']:.1f} years")
        b.metric("Months with data", f"{v['n_months']} of {v['n_months'] + v['n_missing_months']}")
        c.metric("Region size", f"{v['region_resolution_cells']} blocks", f"{v['provider_resolution_cells']} needed", delta_color="off", delta_arrow="off")


def step_annual(v: dict) -> None:
    first, last = v["annual"][0], v["annual"][-1]
    st.write(f"With the yearly cycle removed and each year averaged, the estimate goes from {num(first['value'], 0, True)} cm in "
             f"{first['year']} to {num(last['value'], 0, True)} cm in {last['year']}.")
    st.caption("Groundwater estimate, one value per year.")
    annual_chart(v["annual"])
    thin = {int(y): m for y, m in v.get("thin_years", {}).items() if m < 6}
    if thin:
        st.caption("Years resting on fewer than six months of data: " + ", ".join(f"{y} ({m} months)" for y, m in sorted(thin.items()))
                   + f". A year is kept if it has at least {v['min_months_per_year']}.")


def step_trend(v: dict, annual: list[dict]) -> None:
    low, high = v["slope_interval"]
    st.write("A line can be fitted to anything, and records like this wander: a wet year leaves the ground wetter the next year too. "
             "So the test ignores the line. It takes the change from each year to the next and asks whether those changes average out to zero.")
    st.caption("The change in the groundwater estimate from each year to the next. The line marks the average change.")
    changes_chart(annual, v["mean_yearly_change_cm"])
    verdict = "The test fired." if v["trend_detected"] else "The test did not fire: a record that simply wanders could look like this."
    st.write(f"**{verdict}** Its p-value is {v['p_value']:.3f}, against a bar of {v['alpha']}. "
             "Whether that earns the word significant is the critic's decision, shown under The label.")
    a, b, c = st.columns(3)
    a.metric("Average yearly change", f"{num(v['mean_yearly_change_cm'], 1, True)} cm")
    b.metric("Straight-line slope", f"{num(v['slope_cm_per_year'], 1, True)} cm a year", f"range {span(low, high)}", delta_color="off", delta_arrow="off")
    second = v["second_method"]
    c.metric("Second method", f"p = {second['p_value']:.3f}", "reported, does not decide", delta_color="off", delta_arrow="off")
    st.caption(f"The smallest steady trend this record could detect is {v['minimum_detectable_trend']:.1f} cm a year. "
               f"The second method is prewhitened Mann-Kendall. It is {second['note']}.")


def step_handover(v: dict) -> None:
    if v.get("break_at_handover") is None:
        st.write("The record does not span the gap between the two missions with enough data on both sides, so this could not be checked.")
        return
    share = v["share_of_placebos_at_least_as_large"]
    st.write(f"The record comes from two missions with {v['gap_months']} months between them, and an offset between them would look like a "
             "change in the water. This step measures the change across that gap, after taking out the overall slide, and ranks it "
             "against the same measurement at every other position in the record.")
    a, b, c = st.columns(3)
    a.metric("Change across the real gap", f"{num(v['change_across_gap_cm'], 1, True)} cm")
    b.metric("A typical stretch moves", f"{v['typical_change_cm']:.1f} cm")
    c.metric("Stretches that moved as much", f"{share:.0%}", f"of {v['placebo_positions']} others", delta_color="off", delta_arrow="off")
    rank_chart(share)
    st.write("**A caution is attached,** so the label cannot rise above descriptive." if v["break_at_handover"]
             else "**No caution is attached.** If one had been, the label could not rise above descriptive, however strong the trend.")


def step_rainfall(v: dict) -> None:
    low, high = v["interval_at_average_rainfall"]
    st.write(f"Groundwater rises after wet years and falls after dry ones. This step sets each year's change in storage against the rain "
             f"of the same two years. In a spell of average rainfall ({v['average_rainfall_mm_per_year']:.0f} mm a year), storage changed by "
             f"**{num(v['storage_change_at_average_rainfall_cm_per_year'], 1, True)} cm a year** (range {span(low, high)}).")
    st.caption("Each dot is one year: its change in storage against the rain of the same two years. The orange line marks average rainfall.")
    rain_chart(v)
    b_low, b_high = v["response_interval"]
    clear = "a clear response" if v["responds_to_rainfall"] else "not a clear response, because the range includes zero"
    st.caption(f"The black marker is the reading at average rainfall, with its range. Each extra 100 mm of yearly rain goes with "
               f"{num(v['response_cm_per_100mm'], 1, True)} cm of storage (range {span(b_low, b_high)}): {clear}. "
               f"Rainfall itself over the period: {v['rainfall_trend']['direction']}.")


def step_greenness(v: dict) -> None:
    low, high = v["greenness_interval_per_decade"]
    st.write(f"Over {v['first_year']} to {v['last_year']}, the greenness of the land changed by "
             f"**{num(v['greenness_slope_per_decade'], 2, True)} NDVI a decade** (range {span(low, high, 2)}): {v['greenness_direction']}. "
             "NDVI is a satellite measure of green plant cover, from NASA's MODIS instrument, averaged over the same blocks.")
    fields_chart(v["yearly"])
    st.caption(f"Pattern recorded by this step: `{v['pattern']}`. "
               f"Rank correlation {num(v['spearman_storage_greenness'], 2, True)}: {v['spearman_note']}.")


def label_table(evidence: dict, strength: str) -> None:
    rule = CALIBRATED.get(evidence.get("test"))
    def mark(ok) -> str:
        return "✓" if ok else "✗"
    rows = [("Needed for significant", "")]
    rows.append(("The test used is one whose false-alarm rate has been measured", f"{mark(rule is not None)} {evidence.get('test')}"))
    rows.append(("The test fired", f"{mark(evidence.get('detected'))} {'yes' if evidence.get('detected') else 'no'}"))
    if rule:
        n, persistence = evidence.get("n"), evidence.get("persistence")
        rows.append((f"The record length is in the range the test was measured on ({rule['min_n']} to {rule['max_n']} years)",
                     f"{mark(n is not None and rule['min_n'] <= n <= rule['max_n'])} {n} years"))
        rows.append((f"One year's change does not copy the last too closely (correlation {rule['max_persistence']} or less)",
                     f"{mark(persistence is not None and persistence <= rule['max_persistence'])} {num(persistence, 2, True) if persistence is not None else 'not measured'}"))
    rows.append(("The slope is larger than the smallest steady trend this record could detect", f"{mark(evidence.get('exceeds_detectable'))}"))
    flag = evidence.get("artifact_flag")
    rows.append(("No caution about the instruments was raised", f"{mark(flag is False)} {'none' if flag is False else 'raised' if flag else 'not checked'}"))
    rows.append(("Also needed for robust", ""))
    rows.append(("The direction holds when the first or last years are dropped", mark(evidence.get("sign_stable"))))
    rows.append(("A second method gives the same verdict", mark(evidence.get("second_method_agrees"))))
    independent = evidence.get("independent_record_agrees")
    rows.append(("An independent record, such as wells, agrees", f"{mark(independent is True)} {'not compared' if independent is None else ''}"))
    table = ["| What the critic reads | This record |", "| --- | --- |"]
    table += [f"| *{a}* | |" if not b else f"| {a} | {b} |" for a, b in rows]
    table.append(f"| **Label** | **{strength}** |")
    st.markdown("\n".join(table))


def playbook_dot(taken: set[str]) -> str:
    pb = knowledge()["playbook"]
    lines = ['digraph playbook {', '  rankdir=TB; bgcolor="white"; nodesep=0.5; ranksep=0.45;',
             '  node [shape=box, style="rounded", fontname="Helvetica", fontsize=11, margin="0.18,0.08"];',
             '  edge [fontname="Helvetica", fontsize=9];']
    position = 0
    for node in pb["nodes"]:
        if node.get("procedure"):
            position += 1
            lines.append(f'  {node["id"]} [label="{position}  {node["id"]}\\n{node["procedure"]}"];')
        elif node.get("terminal") == "claim":
            lines.append(f'  {node["id"]} [label="finding\\nthe critic sets the label", style="rounded,filled", fillcolor="black", fontcolor="white"];')
        else:
            lines.append(f'  {node["id"]} [label="refused\\nsays what failed and what would change it"];')
    for edge in pb["edges"]:
        on = edge["id"] in taken
        style = 'penwidth=2.6, color="black", fontcolor="black"' if on else 'penwidth=1, color="gray55", fontcolor="gray40"'
        spine = "weight=10" if edge["outcome"] == "ok" else "constraint=false"
        lines.append(f'  {edge["origin"]} -> {edge["target"]} [label=" {edge["outcome"]} · {edge["source"]} ", {style}, {spine}];')
    steps = [n["id"] for n in pb["nodes"] if n.get("procedure")]
    lines.append(f'  {{ rank=same; {steps[1]}; refused; }}')
    return "\n".join(lines + ["}"])


def render_step(node: str, ran: dict, finding, r: dict, gap: tuple[str, str]) -> None:
    """Render one recorded step, including a recorded stop, in either view."""
    if node not in ran:
        st.info(f"This step did not run. The check stopped at step {len(ran)}.")
        return
    position, step, values = ran[node]
    if led_to(step) in ("refused", "skipped"):
        for reason in (item for item in finding.refusals if item.procedure == step.procedure):
            st.warning(f"**{reason.failed}.**\n\nWhat would change it: {reason.would_change}.")
        st.write("The check stopped here." if led_to(step) == "refused" else
                 "This step was skipped; the finding is written from the steps that ran.")
    elif node == "audit":
        step_audit(values, r, gap)
    elif node == "annual":
        step_annual(values)
    elif node == "trend":
        step_trend(values, ran["annual"][2]["annual"])
    elif node == "handover":
        step_handover(values)
    elif node == "rainfall":
        step_rainfall(values)
    elif node == "greenness":
        step_greenness(values)
    procedure_line(position, step)


def move_guide(delta: int, max_step: int) -> None:
    st.session_state["story_guide_step"] = max(0, min(max_step, st.session_state["story_guide_step"] + delta))


def guide_navigation(max_step: int) -> int:
    """Keep the visitor's place, but restart when a different question or area is selected."""
    current = min(st.session_state.get("story_guide_step", 0), max_step)
    st.session_state["story_guide_step"] = current
    left, middle, right = st.columns([1, 3, 1])
    with left:
        st.button("← Previous clue", disabled=current == 0, key="story_previous", on_click=move_guide, args=(-1, max_step))
    with middle:
        title = "The verdict" if current == max_step else GUIDE_TITLES[current]
        st.progress(current / max_step, text=f"Clue {current + 1} of {max_step + 1}: {title}")
    with right:
        st.button("Next clue →", disabled=current == max_step, key="story_next", on_click=move_guide, args=(1, max_step))
    return current


def show_walkthrough() -> None:
    st.markdown("""<style>
    .td-hero {background:linear-gradient(125deg,#102b39 0%,#165363 58%,#177765 100%);
      color:#fff;padding:1.5rem 1.8rem;border-radius:1.1rem;margin:.4rem 0 1.2rem;
      box-shadow:0 14px 32px rgba(12,54,67,.16)}
    .td-hero .eyebrow {color:#a6efda;text-transform:uppercase;letter-spacing:.16em;font-size:.78rem;font-weight:700}
    .td-hero h2 {color:#fff;font-size:clamp(1.5rem,3vw,2.35rem);line-height:1.15;margin:.45rem 0}
    .td-hero p {color:#e2f4f1;margin:0;max-width:54rem}
    .td-hero .question {color:#fff;font-weight:650;margin-top:.8rem}
    </style>""", unsafe_allow_html=True)
    st.header("Follow one question all the way")
    st.caption("Real NASA records for two regions large enough for the satellites to resolve: GRACE and GRACE-FO (stored water), GLDAS "
               "(modelled soil moisture and snow), MODIS (greenness) and POWER (rainfall). Information only: no forecasts, no causes.")
    left, right = st.columns([3, 2])
    question = left.text_input("Question", QUESTION, key="story_q")
    area = right.selectbox("Area", list(AREAS), key="story_area")
    st.caption("Things to try: ask *why is the groundwater falling here?*, switch to the US High Plains, or ask about the small area.")
    tag, blocks = AREAS[area]
    scope = (question, area)
    if st.session_state.get("story_guide_scope") != scope:
        st.session_state["story_guide_scope"] = scope
        st.session_state["story_guide_step"] = 0
    finding = follow(tag, question, blocks)
    ran = {step.node: (position, step, json.loads(step.values_json)) for position, step in enumerate(finding.path, 1)}
    gap = ("2017-07-01", "2018-05-31")

    conclusions = [v["conclusion"] for _, _, v in ran.values() if isinstance(v.get("conclusion"), dict)]
    st.markdown(f"""<div class="td-hero"><div class="eyebrow">An evidence-led investigation</div>
      <h2>Follow the water, check every clue.</h2>
      <p>From satellites to seasonal patterns to the strength of the answer. Move through the recorded checks at your own pace.</p>
      <p class="question">{escape(question)}</p></div>""", unsafe_allow_html=True)
    max_step = len(ran) + 1 if not finding.claim else len(STEPS) + 1
    current = guide_navigation(max_step)
    with st.container(border=True):
        st.caption(f"INVESTIGATION {current + 1} / {max_step + 1}")
        st.subheader("The verdict" if current == max_step else GUIDE_TITLES[current])
        if current == 0:
            st.write("First, the question is matched with the data this playbook can check. The area and its satellite footprint matter: a place too small for the sensor can stop the investigation before any trend is calculated.")
            st.write(f"**Area:** {area}")
            st.write("**Records:** GRACE and GRACE-FO water storage, GLDAS modelled water, MODIS greenness, NASA POWER rainfall.")
            st.caption("The data are cached NASA records. The six checks below run in the order specified by the playbook.")
        elif current < max_step and current - 1 < len(ran):
            render_step(list(STEPS)[current - 1], ran, finding, records(tag), gap)
        else:
            if finding.claim:
                st.markdown(f"Label: **{finding.claim.strength}**")
                st.info(finding.claim.statement)
                if conclusions:
                    st.write("The critic reads the recorded checks before setting that label:")
                    label_table(conclusions[-1]["evidence"], finding.claim.strength)
            else:
                st.warning("This investigation stopped before it could make a claim.")
                for refusal in finding.refusals:
                    st.write(f"**{refusal.procedure}:** {refusal.failed}. What would change it: {refusal.would_change}.")
    st.caption("Want to inspect the whole route? Open the complete evidence trail below. The guide and the full view use the same recorded Finding.")

    if st.toggle("Explore the complete evidence trail", key="story_full_evidence"):
        tabs = st.tabs(TABS + ["The label", "The playbook"])
        r = records(tag)
        for tab, (node, asks) in zip(tabs, STEPS.items()):
            with tab:
                st.markdown(f"#### {asks}")
                render_step(node, ran, finding, r, gap)

        with tabs[len(STEPS)]:
            st.markdown("#### How the label was decided")
            st.write("Procedures never choose the label. They record evidence, and one module, the critic, applies a fixed rule to it.")
            if finding.claim and conclusions:
                label_table(conclusions[-1]["evidence"], finding.claim.strength)
                if finding.would_strengthen:
                    st.write("What would make this stronger, in the tool's words:")
                    st.markdown("\n".join(f"- {item}" for item in finding.would_strengthen))
            else:
                st.info("No label: the check stopped before any evidence was recorded.")

        with tabs[len(STEPS) + 1]:
            st.markdown("#### The playbook, as data")
            st.write("The order of the steps is a data file. Every arrow names the source of the rule that justifies it, and the engine rejects "
                     "an arrow that has none. The thick arrows are the route this question took.")
            st.graphviz_chart(playbook_dot({step.edge_taken for step in finding.path}), width="stretch")
            k = knowledge()
            table = ["| Step | Procedure | Needs, then returns | Rule from |", "| --- | --- | --- | --- |"]
            for position, node in enumerate((n for n in k["playbook"]["nodes"] if n.get("procedure")), 1):
                p = k["procedures"][node["procedure"]]
                table.append(f"| {position} | `{p['name']}` | {', '.join(p['requires'])} → {', '.join(p['produces'])} | {source_link(p['source'])} |")
            st.markdown("\n".join(table))
            with st.expander(f"The file: {PLAYBOOK.relative_to(ROOT)}"):
                st.code(k["playbook_text"], language="yaml")

    with st.expander("Everything the check recorded, and downloads"):
        for position, step, v in ran.values():
            st.markdown(f"**{position}. {step.node}** · source `{step.source}` · edge `{step.edge_taken}` (`{step.edge_source}`)")
            st.json(v, expanded=False)
        st.download_button("Download finding (JSON)", finding.model_dump_json(indent=2), "groundwater_finding.json", key="story_json")
        st.download_button("Download evidence report", render(finding), "groundwater_finding.md", key="story_md")
