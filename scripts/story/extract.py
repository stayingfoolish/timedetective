"""Run the water-and-greenness check on the cached NASA records and write out everything the story draws.

    uv run python scripts/story/extract.py

Writes scripts/story/data.json. The story page (docs/story/index.html) and the walkthrough in the README are
built from that file by build_page.py, so no figure about the two regions is typed by hand.
"""

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from timedetective.engine.critic import CALIBRATED
from timedetective.packs.earth.adapters.gldas import groundwater_estimate, load_gldas_storage
from timedetective.packs.earth.adapters.mod13c2 import load_mod13c2_region
from timedetective.packs.earth.adapters.stories import load_gsfc_mascons, load_power_regional
from timedetective.packs.earth.skills.changepoint import storage as handover_mod
from timedetective.packs.earth.skills.relationship.greenness import yearly_greenness
from timedetective.packs.earth.stories import check_storage, check_storage_and_greenness
from timedetective.skills.transforms.deseasonalize import deseasonalize_harmonic

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data" / "cache" / "earth" / "stories"
QUESTION = "Is the water under these farms running out, and would the fields show it?"
DISTRICT = {"name": "Ludhiana", "lat": 30.9, "lon": 75.85, "blocks": 3}


def r(x, n=3):
    return None if x is None or (isinstance(x, float) and not np.isfinite(x)) else round(float(x), n)


def placebos(x, gap_start="2017-07-01", gap_end="2018-05-31"):
    """The measurement the hand-over procedure makes, returning every placebo value so they can be drawn."""
    series = deseasonalize_harmonic(x, 12).series
    v = series.to_numpy(dtype=float)
    t = np.arange(len(v), dtype=float)
    ok = np.isfinite(v)
    v = v - np.polyval(np.polyfit(t[ok], v[ok], 1), t)
    inside = (series.index >= pd.Timestamp(gap_start)) & (series.index <= pd.Timestamp(gap_end))
    start, gap = int(np.argmax(inside)), int(inside.sum())
    window = handover_mod.WINDOW
    out = []
    for pos in range(window, len(v) - gap - window + 1):
        if abs(pos - start) < gap + window:
            continue
        jump = handover_mod._jump(v, pos, gap)
        if jump is not None:
            out.append(jump)
    return handover_mod._jump(v, start, gap), out


def load(tag):
    total = load_gsfc_mascons(CACHE / f"gsfc_mascons_{tag}.csv")
    meta_path = CACHE / f"gsfc_mascons_{tag}.meta.yaml"
    modelled = load_gldas_storage(CACHE / f"gldas_noah025_m_{tag}.json.gz", meta_path)
    rain = load_power_regional(CACHE / f"power_monthly_PRECTOTCORR_SUM_{tag}_2000_2025_20261115.json", "PRECTOTCORR_SUM")
    green = load_mod13c2_region(CACHE / f"mod13c2_{tag}.json.gz", meta_path)
    return total, modelled, rain, green, yaml.safe_load(meta_path.read_text())


def region(tag, label):
    total, modelled, rain, green, meta = load(tag)
    gw = groundwater_estimate(total, modelled)
    f = check_storage_and_greenness(gw, question=QUESTION, vegetation=green, rainfall=rain)
    v = {s.node: json.loads(s.values_json) for s in f.path}
    observed, plac = placebos(gw)
    ann = v["annual"]["annual"]
    years, values = [a["year"] for a in ann], [a["value"] for a in ann]
    t, rf, gr, ho = v["trend"], v["rainfall"], v["greenness"], v["handover"]
    rain_year = rain.groupby(rain.index.year).sum(min_count=12).dropna()
    model_aligned = modelled.reindex(total.index)
    page = {
        "label": label, "strength": f.claim.strength, "statement": f.claim.statement, "would_strengthen": f.would_strengthen,
        "steps": [{"node": s.node, "procedure": s.procedure, "source": s.source, "edge": s.edge_taken, "edge_source": s.edge_source} for s in f.path],
        "audit": {k: v["audit"].get(k) for k in ("storage_kind", "measures", "years", "n_months", "n_missing_months", "longest_gap_months",
                                                 "region_resolution_cells", "provider_resolution_cells", "area_km2", "start", "end")},
        "mascons": [{"lat": m["lat_center"], "lon": m["lon_center"], "dlat": m["lat_span"], "dlon": m["lon_span"]} for m in meta["mascons"]],
        "box": meta["selection"],
        "monthly": [{"t": str(i.date())[:7], "total": r(a, 2), "model": r(b, 2), "gw": r(c, 2)}
                    for i, a, b, c in zip(total.index, total.to_numpy(), model_aligned.to_numpy(), gw.to_numpy())],
        "annual": [{"year": y, "value": r(x, 2)} for y, x in zip(years, values)],
        "changes": [{"year": y, "value": r(b - a, 2)} for y, a, b in zip(years[1:], values[:-1], values[1:])],
        "thin_years": v["annual"]["thin_years"],
        "trend": {"slope": r(t["slope_cm_per_year"]), "low": r(t["slope_interval"][0]), "high": r(t["slope_interval"][1]),
                  "total_change": r(t["total_change_cm"], 1), "p": r(t["p_value"], 4), "detected": t["trend_detected"],
                  "mean_change": r(t["mean_yearly_change_cm"]), "lag1": r(t["lag1_of_yearly_changes"]),
                  "second_p": r(t["second_method"]["p_value"], 4), "second_detected": t["second_method"]["trend_detected"],
                  "mdt": r(t["minimum_detectable_trend"]), "sign_stable": t["sign_stable"],
                  "window_range": [r(x) for x in t["slope_range_over_windows"]], "n": t["n_years"]},
        "handover": {"observed": r(observed, 2), "placebos": [r(p, 2) for p in plac], "share": r(ho.get("share_of_placebos_at_least_as_large"), 3),
                     "flag": ho.get("break_at_handover"), "typical": r(ho.get("typical_change_cm"), 2), "n": ho.get("placebo_positions")},
        "rainfall": {"pairs": [{"year": p["year"], "change": r(p["storage_change_cm"], 2), "rain": r(p["rainfall_mm_per_year"], 0)} for p in rf["pairs"]],
                     "a": r(rf["storage_change_at_average_rainfall_cm_per_year"]), "a_low": r(rf["interval_at_average_rainfall"][0]),
                     "a_high": r(rf["interval_at_average_rainfall"][1]), "b": r(rf["response_cm_per_100mm"]),
                     "b_low": r(rf["response_interval"][0]), "b_high": r(rf["response_interval"][1]),
                     "mean_rain": r(rf["average_rainfall_mm_per_year"], 0), "link": rf["link"], "responds": rf["responds_to_rainfall"],
                     "rain_trend": rf["rainfall_trend"], "yearly": [{"year": int(y), "mm": r(x, 0)} for y, x in rain_year.items()]},
        "greenness": {"yearly": [{"year": int(i.year), "ndvi": r(x, 4)} for i, x in yearly_greenness(green.dropna()).items()],
                      "values": {k: gr.get(k) for k in gr if k not in ("conclusion", "years")}},
    }
    build = {"evidence": json.loads(f.path[-1].values_json)["conclusion"]["evidence"], "total_change_cm": t["total_change_cm"]}
    return page, build, (gw, green, rain, meta)


def main():
    page = {"question": QUESTION, "regions": {}}
    build = {"evidence": {}}
    for tag, label in (("nw_india", "North-west India"), ("high_plains", "US High Plains")):
        page["regions"][tag], b, kept = region(tag, label)
        build["evidence"][tag] = b["evidence"]
        if tag == "nw_india":
            gw, green, rain, meta = kept
            build["total_change_cm"] = b["total_change_cm"]

    # The reference study's window, for the comparison in the footer.
    w = gw["2002-08":"2008-10"].dropna()
    page["rodell_window_slope"] = r(np.polyfit((w.index - w.index[0]).days / 365.25, w.to_numpy(), 1)[0], 2)

    # A region the size of a few districts: the same record, declared as three blocks.
    small = gw.copy()
    small.attrs = {**gw.attrs, "resolution_units": DISTRICT["blocks"]}
    refusal = check_storage(small, question="Is the groundwater under my district falling?")
    page["district_refusal"] = {"failed": refusal.refusals[0].failed, "would_change": refusal.refusals[0].would_change,
                                "procedure": refusal.refusals[0].procedure, "steps": [s.node for s in refusal.path]}
    why = check_storage_and_greenness(gw, question="Why is the groundwater falling here?", vegetation=green, rainfall=rain)
    page["cause_sentences"] = [s for s in why.claim.statement.split(". ") if "cause" in s]

    playbook_path = ROOT / "knowledge" / "playbooks" / "water_and_greenness_check.yaml"
    pb = yaml.safe_load(playbook_path.read_text())
    page["playbook"] = {"name": pb["name"], "question": pb["question"],
                        "nodes": [{k: n.get(k) for k in ("id", "procedure", "terminal")} for n in pb["nodes"]],
                        "edges": [{k: e[k] for k in ("id", "origin", "target", "outcome", "source")} for e in pb["edges"]]}
    sources = yaml.safe_load((ROOT / "knowledge" / "sources.yaml").read_text())
    page["procedures"], paths = {}, {}
    for n in pb["nodes"]:
        if n.get("procedure"):
            path = next((ROOT / "knowledge" / "procedures").glob(f"*/{n['procedure']}.yaml"))
            page["procedures"][n["procedure"]] = yaml.safe_load(path.read_text())
            paths[n["procedure"]] = str(path.relative_to(ROOT))
    cited = {e["source"] for e in pb["edges"]} | {d["source"] for d in page["procedures"].values()}
    page["sources"] = {k: {kk: sources[k].get(kk) for kk in ("title", "authors", "year", "kind", "url", "venue")} for k in sorted(cited)}

    cells = meta["mascons"]
    k = math.cos(math.radians(DISTRICT["lat"]))
    nearest = sorted(range(len(cells)), key=lambda i: math.hypot(cells[i]["lat_center"] - DISTRICT["lat"], (cells[i]["lon_center"] - DISTRICT["lon"]) * k))
    build.update({
        "hot": nearest[: DISTRICT["blocks"]], "district": DISTRICT,
        "extent": {"lat": [min(c["lat_center"] - c["lat_span"] / 2 for c in cells), max(c["lat_center"] + c["lat_span"] / 2 for c in cells)],
                   "lon": [min(c["lon_center"] - c["lon_span"] / 2 for c in cells), max(c["lon_center"] + c["lon_span"] / 2 for c in cells)]},
        "calibrated": CALIBRATED["drift_test"],
        "playbook_path": str(playbook_path.relative_to(ROOT)), "procedure_paths": paths,
        "playbook_yaml": playbook_path.read_text(),
        "procedure_yaml": (ROOT / paths["storage_rainfall"]).read_text(),
    })
    out = Path(__file__).with_name("data.json")
    out.write_text(json.dumps({"page": page, "build": build}, default=str, indent=1) + "\n")
    print(f"wrote {out.relative_to(ROOT)} ({out.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
