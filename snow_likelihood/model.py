"""
Top-level model: fetches data, scores every hour, blends the synoptic and
ensemble methods, and aggregates to daily summaries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from . import data as data_mod
from . import methods


@dataclass
class HourResult:
    time: str
    synoptic_score: Optional[float]
    ensemble_probability: Optional[float]
    ensemble_members_evaluated: int
    final_score_pct: float
    category: str
    detail: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DayResult:
    date: str
    peak_score_pct: float
    peak_hour: str
    mean_score_pct: float
    category: str
    hours: List[HourResult] = field(default_factory=list)


@dataclass
class ModelRun:
    location_name: str
    latitude: float
    longitude: float
    elevation_m: float
    synoptic_model: str
    ensemble_models: List[str]
    ensemble_weight: float
    synoptic_weight: float
    days: List[DayResult] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def _safe_get(hourly: Dict[str, Any], key: str, index: int):
    series = hourly.get(key)
    if series is None or index >= len(series):
        return None
    return series[index]


def run_model(
    *,
    location_name: str,
    lat: float,
    lon: float,
    elevation_m: Optional[float] = None,
    forecast_days: int = 5,
    synoptic_model: str = data_mod.DEFAULT_SYNOPTIC_MODEL,
    ensemble_models: Optional[List[str]] = None,
    ensemble_weight: float = 0.6,
    snowfall_member_threshold_cm: float = 0.1,
    fetch_synoptic_fn=None,
    fetch_ensemble_fn=None,
) -> ModelRun:
    """Run the full blended model and return a ModelRun with daily/hourly
    detail. `fetch_synoptic_fn` / `fetch_ensemble_fn` are injectable for
    testing/demo mode (see cli.py --demo); by default they call the real
    Open-Meteo endpoints in `data.py`.
    """
    ensemble_models = ensemble_models or list(data_mod.DEFAULT_ENSEMBLE_MODELS)
    synoptic_weight = 1.0 - ensemble_weight

    fetch_synoptic_fn = fetch_synoptic_fn or (
        lambda: data_mod.fetch_synoptic(lat, lon, forecast_days, model=synoptic_model)
    )
    fetch_ensemble_fn = fetch_ensemble_fn or (
        lambda m: data_mod.fetch_ensemble_one_model(lat, lon, forecast_days, model=m)
    )

    # ---- Synoptic data ----
    syn_payload = fetch_synoptic_fn()
    syn_hourly = syn_payload.get("hourly", {})
    times = syn_hourly.get("time", [])
    if not times:
        raise data_mod.SnowDataError("Synoptic forecast response had no hourly time series.")

    if elevation_m is None:
        # Fall back to the weather model's own grid elevation for this point
        # -- consistent with the freezing-level figures it also returns.
        elevation_m = float(syn_payload.get("elevation", 0.0))

    run = ModelRun(
        location_name=location_name,
        latitude=lat,
        longitude=lon,
        elevation_m=elevation_m,
        synoptic_model=synoptic_model,
        ensemble_models=ensemble_models,
        ensemble_weight=ensemble_weight,
        synoptic_weight=synoptic_weight,
    )

    # ---- Ensemble data, one model at a time ----
    ensemble_member_flags_by_time: Dict[str, List[bool]] = {t: [] for t in times}
    for model_id in ensemble_models:
        try:
            ens_payload = fetch_ensemble_fn(model_id)
        except data_mod.SnowDataError as exc:
            run.warnings.append(f"Skipped ensemble model '{model_id}': {exc}")
            continue

        ens_hourly = ens_payload.get("hourly", {})
        ens_times = ens_hourly.get("time", [])
        if not ens_times:
            run.warnings.append(f"Ensemble model '{model_id}' returned no hourly data; skipped.")
            continue

        snowfall_members = data_mod.collect_member_series(ens_hourly, "snowfall")
        weathercode_members = data_mod.collect_member_series(ens_hourly, "weather_code")
        member_keys = sorted(set(snowfall_members.keys()) | set(weathercode_members.keys()))
        if not member_keys:
            run.warnings.append(
                f"Ensemble model '{model_id}' returned no recognisable member fields "
                f"(expected '<var>_memberNN' or '<var>'); skipped."
            )
            continue

        time_index = {t: i for i, t in enumerate(ens_times)}

        # Evaluate each member independently across the time series.
        snow_key_suffixes = {k[len("snowfall"):] for k in snowfall_members.keys()}
        wx_key_suffixes = {k[len("weather_code"):] for k in weathercode_members.keys()}
        suffixes = snow_key_suffixes | wx_key_suffixes
        for suffix in suffixes:
            snow_series = snowfall_members.get(f"snowfall{suffix}")
            wx_series = weathercode_members.get(f"weather_code{suffix}")
            for t in times:
                if t not in time_index:
                    continue
                i = time_index[t]
                snow_val = snow_series[i] if snow_series and i < len(snow_series) else None
                wx_val = wx_series[i] if wx_series and i < len(wx_series) else None
                is_snow = methods.ensemble_member_is_snow(snow_val, wx_val, snowfall_member_threshold_cm)
                ensemble_member_flags_by_time.setdefault(t, []).append(is_snow)

    # ---- Score every hour ----
    hour_results: List[HourResult] = []
    for i, t in enumerate(times):
        thickness_dam = None
        gph500 = _safe_get(syn_hourly, "geopotential_height_500hPa", i)
        gph1000 = _safe_get(syn_hourly, "geopotential_height_1000hPa", i)
        if gph500 is not None and gph1000 is not None:
            thickness_dam = (gph500 - gph1000) / 10.0

        syn_detail = methods.synoptic_hour_score(
            thickness_dam=thickness_dam,
            freezing_level_m=_safe_get(syn_hourly, "freezing_level_height", i),
            elevation_m=elevation_m,
            temp_c=_safe_get(syn_hourly, "temperature_2m", i),
            relative_humidity_pct=_safe_get(syn_hourly, "relative_humidity_2m", i),
            precipitation_mm=_safe_get(syn_hourly, "precipitation", i),
            snowfall_cm=_safe_get(syn_hourly, "snowfall", i),
            precipitation_probability_pct=_safe_get(syn_hourly, "precipitation_probability", i),
        )

        member_flags = ensemble_member_flags_by_time.get(t, [])
        ens_prob = methods.ensemble_probability(member_flags)

        syn_score = syn_detail["synoptic_score"]
        if ens_prob is not None:
            final = ensemble_weight * ens_prob + synoptic_weight * syn_score
        else:
            # No ensemble data available for this hour: fall back to
            # synoptic-only rather than silently zeroing it out.
            final = syn_score
        final_pct = round(max(0.0, min(1.0, final)) * 100, 1)

        hour_results.append(
            HourResult(
                time=t,
                synoptic_score=round(syn_score, 3),
                ensemble_probability=round(ens_prob, 3) if ens_prob is not None else None,
                ensemble_members_evaluated=len(member_flags),
                final_score_pct=final_pct,
                category=methods.categorise(final_pct),
                detail=syn_detail,
            )
        )

    if all(h.ensemble_members_evaluated == 0 for h in hour_results):
        run.warnings.append(
            "No ensemble members were successfully evaluated for any hour -- "
            "results are synoptic-method-only. Check network access and model IDs."
        )

    # ---- Aggregate to days ----
    by_date: Dict[str, List[HourResult]] = {}
    for h in hour_results:
        date_part = h.time.split("T")[0]
        by_date.setdefault(date_part, []).append(h)

    for date_part in sorted(by_date.keys()):
        hrs = by_date[date_part]
        peak = max(hrs, key=lambda h: h.final_score_pct)
        mean_score = round(sum(h.final_score_pct for h in hrs) / len(hrs), 1)
        run.days.append(
            DayResult(
                date=date_part,
                peak_score_pct=peak.final_score_pct,
                peak_hour=peak.time,
                mean_score_pct=mean_score,
                category=methods.categorise(peak.final_score_pct),
                hours=hrs,
            )
        )

    return run
