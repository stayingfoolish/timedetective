"""Reproducible method audit, with measured failures; never auto-promotes the critic."""

import argparse
import importlib.util
import json
from pathlib import Path

import numpy as np
from scipy import stats
from statsmodels.stats.multitest import multipletests

from timedetective.packs.earth.skills.trend.precipitation import dependent_test

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("synthetic_generators",ROOT / "data/synthetic/generators.py")
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)


def audit(repetitions: int, resamples: int, seed: int) -> dict:
    """Fixed scenarios, 5% target; includes both rejection frequency and Monte Carlo uncertainty."""
    scenarios = [(25,0.,"gamma"),(25,.6,"gamma"),(45,0.,"gamma"),(45,.6,"gamma"),
                 (45,.85,"gamma"),(45,.6,"intermittent"),(45,0.,"long_memory")]
    rows = []
    for n, phi, kind in scenarios:
        counts = dict(trend=0,period_change=0,changepoint=0,family=0)
        powers = dict(trend=0,period_change=0,changepoint=0)
        contrast = np.r_[np.full(n//2,-1/(n//2)), np.full(n-n//2,1/(n-n//2))]
        for repeat in range(repetitions):
            y = g.annual_precipitation_null(n,phi,seed+repeat,kind)
            pvalues = []
            for method in powers:
                kwargs = dict(method=method,seed=seed+100_000+repeat,resamples=resamples,contrast=contrast)
                p = dependent_test(y,**kwargs)["p_value"]
                pvalues.append(p)
                counts[method] += p <= .05
                # Declared strong signals: +300 mm end-to-end trend or +300 mm step.
                effect = np.linspace(0,300,n) if method == "trend" else np.r_[np.zeros(n//2),np.full(n-n//2,300)]
                powers[method] += dependent_test(y+effect,**kwargs)["p_value"] <= .05
            counts["family"] += bool(multipletests(pvalues,alpha=.05,method="holm")[0].any())
        for method,count in counts.items():
            interval = stats.binomtest(count,repetitions).proportion_ci(confidence_level=.95,method="exact")
            row = {"n":n,"phi":phi,"kind":kind,"method":method,"repetitions":repetitions,
                "false_positives":int(count),"false_positive_rate":count/repetitions,
                "rate_exact_95_interval":[float(interval.low),float(interval.high)],
                "meets_empirical_5pct_target":count/repetitions <= .05,
                "upper_95_bound_at_most_5pct":bool(interval.high <= .05),
                "strong_signal_power":powers.get(method)/repetitions if method in powers else None}
            rows.append(row)
        print(json.dumps({"completed":{"n":n,"phi":phi,"kind":kind},"rates":{k:v/repetitions for k,v in counts.items()}}),flush=True)
    return {"seed":seed,"resamples":resamples,"nominal_alpha":.05,"rows":rows,
        "scope":"Component methods and three-test single-product family on explicit synthetic annual nulls; not daily ingestion, SPI, GEV interval coverage, observational validity or full spatial discovery certification.",
        "claim_promotion_authorized":False,
        "decision":"experimental until all required validation gates pass; no automatic promotion"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repetitions",type=int,default=500)
    parser.add_argument("--resamples",type=int,default=1999)
    parser.add_argument("--seed",type=int,default=77123)
    parser.add_argument("--output",type=Path,required=True)
    args = parser.parse_args()
    if args.output.exists() or args.repetitions < 100:
        parser.error("use a new output path and at least 100 repetitions")
    result = audit(args.repetitions,args.resamples,args.seed)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    payload = json.dumps(result,indent=2,allow_nan=False)
    with args.output.open("x") as handle:
        handle.write(payload)


if __name__ == "__main__":
    main()
