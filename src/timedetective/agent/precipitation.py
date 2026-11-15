"""Inspectable, deterministic precipitation distillation; no guessed geography or dates."""

from datetime import date
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


Analysis = Literal["summary", "trend", "period_change", "changepoint", "extremes", "spi", "return_levels", "timing", "agreement"]
PATTERNS = {
    "summary": r"total|average|mean|anomal|wet|dry|rainfall|precipitation|recover",
    "trend": r"trend|increas|decreas|declin|long.term",
    "period_change": r"compar|versus|\bvs\b|difference|recover",
    "changepoint": r"change.?point|break|step|regime|abrupt|lasting|permanent",
    "extremes": r"extreme|heav|intens|maximum|spell|wet.day|dry.day",
    "spi": r"\bspi\b|drought",
    "return_levels": r"return.period|return.level|\d+.year (?:rain|storm|event)",
    "timing": r"onset|cessation|season.*(?:start|end|duration)|timing",
    "agreement": r"agree|merra|imerg|product|bias|accurac",
}
UNSUPPORTED = r"\b(forecast\w*|predict\w*|tomorrow|why|caus\w*|attribut\w*|flood\w*|SPEI|hourly|sub.hourly|snow\w*|hail|ENSO|El Ni[ñn]o|teleconnection\w*|IDF|equivalence|nonstationary|temperature|humidity|wind|evapotranspiration|soil moisture)\b"


class PrecipitationRequest(BaseModel):
    """Run contract, separate from the public Finding schema; all defaults are serialized."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    question: str = Field(min_length=3)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    start: date
    end: date
    baseline: tuple[int, int]
    event: tuple[int, int]
    seasons: dict[str, list[int]] = Field(default_factory=lambda: {"annual": list(range(1, 13))})
    analyses: list[Analysis] = Field(min_length=1)
    target: Literal["seasonal_total", "rx1day", "rx5day", "wet_days", "dry_spell", "sdii"] = "seasonal_total"
    products: list[Literal["PRECTOTCORR", "IMERG_PRECTOT"]] = Field(default_factory=lambda: ["PRECTOTCORR", "IMERG_PRECTOT"])
    spi_scale: int = Field(default=3, ge=1, le=24)
    return_periods: list[float] = Field(default_factory=lambda: [2, 5, 10, 20])
    wet_threshold: float = Field(default=1, gt=0)
    seed: int = Field(default=1729, ge=0)
    resamples: int = Field(default=1999, ge=199, le=9999)
    fit_resamples: int = Field(default=199, ge=99, le=999)
    alpha: float = Field(default=.05, gt=0, le=.05)
    timing_windows: dict[str, tuple[str, str]] | None = None
    scope: Literal["point_query"] = "point_query"
    distillation: str = "deterministic keyword routing plus explicit spatial/temporal controls; not a general semantic parser"

    @model_validator(mode="after")
    def validate_contract(self) -> "PrecipitationRequest":
        if self.start > self.end or self.start < date(1981, 1, 1):
            raise ValueError("ordered dates from 1981 onward required")
        if self.end.year >= date.today().year:
            raise ValueError("use completed historical years; near-real-time mixed products are not supported")
        if self.start.month != 1 or self.start.day != 1 or (self.end.month, self.end.day) != (12, 31):
            raise ValueError("this historical investigator requires complete calendar-year requests")
        if not (self.start.year <= self.baseline[0] <= self.baseline[1] < self.event[0] <= self.event[1] <= self.end.year):
            raise ValueError("baseline and event must be ordered, disjoint and inside the requested record")
        if not self.products or len(set(self.products)) != len(self.products):
            raise ValueError("supply unique precipitation products")
        if len(set(self.analyses)) != len(self.analyses):
            raise ValueError("duplicate analyses")
        if not self.return_periods or any(t <= 1 for t in self.return_periods):
            raise ValueError("return periods must exceed one year")
        if not self.seasons:
            raise ValueError("declare at least one season")
        if self.target != "seasonal_total" and self.seasons != {"annual": list(range(1, 13))}:
            raise ValueError("daily-index inference currently requires the explicit annual season")
        for months in self.seasons.values():
            if not months or len(set(months)) != len(months) or any(type(m) is not int or not 1 <= m <= 12 for m in months):
                raise ValueError("season months must be unique integers in 1..12")
            if any(b != a % 12 + 1 for a, b in zip(months, months[1:])):
                raise ValueError("season months must be contiguous and ordered")
        if "timing" in self.analyses and not self.timing_windows:
            raise ValueError("timing needs explicit broad search windows as MM-DD pairs, one per wet season")
        for start, end in (self.timing_windows or {}).values():
            date.fromisoformat(f"2001-{start}")
            date.fromisoformat(f"2001-{end}")
        return self


def distill(question: str, **controls: object) -> PrecipitationRequest:
    """Reject unsupported questions before any I/O; controls are displayed, not inferred."""
    unsupported = re.search(UNSUPPORTED, question, re.I)
    if unsupported:
        raise ValueError(f"unsupported precipitation question component: {unsupported.group(0)}")
    explicit = controls.get("analyses")
    if explicit is None:
        controls["analyses"] = [name for name, pattern in PATTERNS.items() if re.search(pattern, question, re.I)]
    if not controls.get("analyses"):
        raise ValueError("question did not map to a supported analysis; specify analyses explicitly")
    targets = {"rx1day": r"rx1day|maximum daily|daily maximum", "rx5day": r"rx5day|5.day maximum|maximum 5.day",
               "wet_days": r"wet.day (?:count|frequency)|number of wet days", "dry_spell": r"dry.spell (?:length|duration)",
               "sdii": r"\bsdii\b|wet.day intensity"}
    detected = [key for key, pattern in targets.items() if re.search(pattern, question, re.I)]
    if len(detected) > 1:
        raise ValueError("multiple statistical targets: make separate explicit requests; do not mix distinct estimands")
    if detected:
        if "target" in controls and controls["target"] != detected[0]:
            raise ValueError("question target conflicts with control")
        controls["target"] = detected[0]
    elif any(a in controls["analyses"] for a in ["trend", "period_change", "changepoint"]) and re.search(r"extreme|intens|spell", question, re.I) and "target" not in controls:
        raise ValueError("specify target: seasonal_total, rx1day, rx5day, wet_days, dry_spell or sdii; extreme-intensity trends are not total-rain trends")
    spi = re.search(r"\bSPI[- ]?(\d+)\b", question, re.I)
    if spi:
        scale = int(spi.group(1))
        if "spi_scale" in controls and controls["spi_scale"] != scale:
            raise ValueError("question SPI scale conflicts with explicit control")
        controls["spi_scale"] = scale
        if "spi" not in controls["analyses"]:
            controls["analyses"] = [*controls["analyses"], "spi"]
    periods = re.findall(r"\b(\d+(?:\.\d+)?)[ -]year (?:rain|storm|event|return)", question, re.I)
    if periods:
        values = [float(t) for t in periods]
        if "return_periods" in controls and controls["return_periods"] != values:
            raise ValueError("question return periods conflict with control")
        controls["return_periods"] = values
    ranges = re.findall(r"\b((?:19|20)\d{2})\s*[-–]\s*((?:19|20)\d{2})\b", question)
    declared_ranges = [tuple(controls[k]) for k in ["baseline", "event"] if k in controls]
    if "start" in controls and "end" in controls:
        declared_ranges.append((int(str(controls["start"])[:4]), int(str(controls["end"])[:4])))
    if any(tuple(map(int,pair)) not in declared_ranges for pair in ranges):
        raise ValueError("question year range conflicts with the declared baseline, event or full record")
    # Controls are authoritative, but conflicting named seasons are never silently ignored.
    named = {"MAM": [3,4,5], "OND": [10,11,12], "DJF": [12,1,2], "JJA": [6,7,8], "SON": [9,10,11]}
    found = {k: v for k, v in named.items() if re.search(rf"\b{k}\b", question, re.I)}
    if found:
        if "seasons" not in controls:
            controls["seasons"] = found
        elif any(v not in list(controls["seasons"].values()) for v in found.values()):
            raise ValueError("question seasons conflict with explicit season controls")
    return PrecipitationRequest(question=question, **controls)
