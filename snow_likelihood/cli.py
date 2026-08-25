from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import List, Optional

from . import data as data_mod
from . import model as model_mod
from . import MODEL_NAME, MODEL_FULL_NAME, __version__

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="slm",
        description=(
            f"{MODEL_NAME} ({MODEL_FULL_NAME}) -- a UK snow likelihood model that blends "
            "a synoptic rules-based method (thickness / freezing level / wet-bulb "
            "temperature) with multi-model NWP ensemble agreement."
        ),
    )
    p.add_argument(
        "--version",
        action="version",
        version=f"{MODEL_NAME} ({MODEL_FULL_NAME}) v{__version__}",
    )
    loc_group = p.add_mutually_exclusive_group(required=False)
    loc_group.add_argument("--location", type=str, help="Free-text UK place name, e.g. 'Aviemore'.")
    p.add_argument("--lat", type=float, help="Latitude (use with --lon instead of --location).")
    p.add_argument("--lon", type=float, help="Longitude (use with --lat instead of --location).")
    p.add_argument("--elevation", type=float, default=None, help="Override site elevation in metres.")

    p.add_argument("--days", type=int, default=5, help="Forecast days ahead (default 5, max ~15).")
    p.add_argument(
        "--ensemble-models",
        type=str,
        default=",".join(data_mod.DEFAULT_ENSEMBLE_MODELS),
        help="Comma-separated Open-Meteo ensemble model IDs.",
    )
    p.add_argument(
        "--synoptic-model",
        type=str,
        default=data_mod.DEFAULT_SYNOPTIC_MODEL,
        help="Deterministic model ID used for thickness/freezing-level/wet-bulb scoring.",
    )
    p.add_argument(
        "--ensemble-weight",
        type=float,
        default=0.6,
        help="Weight (0-1) given to ensemble agreement vs. synoptic rules (default 0.6).",
    )
    p.add_argument("--hourly", action="store_true", help="Print full hourly breakdown, not just daily summary.")
    p.add_argument("--json", type=str, metavar="PATH", help="Write full results as JSON to PATH.")
    p.add_argument("--csv", type=str, metavar="PATH", help="Write the daily summary as CSV to PATH.")
    p.add_argument(
        "--demo",
        action="store_true",
        help="Run against bundled sample data instead of the live API (no network needed).",
    )
    return p


def _resolve_location(args) -> data_mod.Location:
    if args.demo:
        return data_mod.Location(
            name="Aviemore, Scotland (demo fixture)",
            latitude=57.19,
            longitude=-3.83,
            elevation_m=228.0,
            country="United Kingdom",
            admin1="Scotland",
        )
    if args.lat is not None and args.lon is not None:
        return data_mod.Location(
            name=f"({args.lat:.3f}, {args.lon:.3f})",
            latitude=args.lat,
            longitude=args.lon,
            elevation_m=args.elevation if args.elevation is not None else 0.0,
        )
    if args.location:
        return data_mod.geocode(args.location)
    raise SystemExit("Provide --location NAME, or --lat/--lon, or use --demo.")


def _demo_fetchers():
    syn_payload = json.loads((FIXTURES_DIR / "sample_synoptic.json").read_text())

    def fetch_synoptic():
        return syn_payload

    ensemble_payloads = {
        "demo_ukmo": json.loads((FIXTURES_DIR / "sample_ensemble_ukmo.json").read_text()),
        "demo_icon": json.loads((FIXTURES_DIR / "sample_ensemble_icon.json").read_text()),
        "demo_gfs": json.loads((FIXTURES_DIR / "sample_ensemble_gfs.json").read_text()),
    }

    def fetch_ensemble(model_id: str):
        if model_id not in ensemble_payloads:
            raise data_mod.SnowDataError(f"No demo fixture for model '{model_id}'.")
        return ensemble_payloads[model_id]

    return fetch_synoptic, fetch_ensemble, list(ensemble_payloads.keys())


def _print_daily_table(run: model_mod.ModelRun) -> None:
    header = f"{'Date':<12}{'Peak %':>8}{'Peak time':>18}{'Mean %':>8}   Category"
    print(header)
    print("-" * len(header))
    for day in run.days:
        peak_time = day.peak_hour.replace("T", " ")
        print(f"{day.date:<12}{day.peak_score_pct:>7.1f}%{peak_time:>18}{day.mean_score_pct:>7.1f}%   {day.category}")


def _print_hourly_table(run: model_mod.ModelRun) -> None:
    header = f"{'Time':<17}{'Final %':>9}{'Category':<12}{'Synoptic':>9}{'Ensemble':>10}{'Members':>9}"
    print()
    print(header)
    print("-" * len(header))
    for day in run.days:
        for h in day.hours:
            ens = f"{h.ensemble_probability * 100:.0f}%" if h.ensemble_probability is not None else "n/a"
            syn = f"{h.synoptic_score * 100:.0f}%" if h.synoptic_score is not None else "n/a"
            print(
                f"{h.time.replace('T', ' '):<17}{h.final_score_pct:>8.1f}%  {h.category:<10}"
                f"{syn:>9}{ens:>10}{h.ensemble_members_evaluated:>9}"
            )


def _write_json(run: model_mod.ModelRun, path: str) -> None:
    payload = {
        "location": run.location_name,
        "latitude": run.latitude,
        "longitude": run.longitude,
        "elevation_m": run.elevation_m,
        "synoptic_model": run.synoptic_model,
        "ensemble_models": run.ensemble_models,
        "ensemble_weight": run.ensemble_weight,
        "synoptic_weight": run.synoptic_weight,
        "warnings": run.warnings,
        "days": [
            {
                "date": d.date,
                "peak_score_pct": d.peak_score_pct,
                "peak_hour": d.peak_hour,
                "mean_score_pct": d.mean_score_pct,
                "category": d.category,
                "hours": [
                    {
                        "time": h.time,
                        "final_score_pct": h.final_score_pct,
                        "category": h.category,
                        "synoptic_score": h.synoptic_score,
                        "ensemble_probability": h.ensemble_probability,
                        "ensemble_members_evaluated": h.ensemble_members_evaluated,
                        "detail": h.detail,
                    }
                    for h in d.hours
                ],
            }
            for d in run.days
        ],
    }
    Path(path).write_text(json.dumps(payload, indent=2))


def _write_csv(run: model_mod.ModelRun, path: str) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "peak_score_pct", "peak_hour", "mean_score_pct", "category"])
        for d in run.days:
            writer.writerow([d.date, d.peak_score_pct, d.peak_hour, d.mean_score_pct, d.category])


def main(argv: Optional[List[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)

    try:
        loc = _resolve_location(args)
    except data_mod.SnowDataError as exc:
        print(f"Error resolving location: {exc}", file=sys.stderr)
        return 1

    print(f"{MODEL_NAME} -- {MODEL_FULL_NAME}")
    print(f"Location: {loc.name}  ({loc.latitude:.3f}, {loc.longitude:.3f}, elevation {loc.elevation_m:.0f} m)")

    if args.demo:
        fetch_synoptic_fn, fetch_ensemble_fn, ensemble_models = _demo_fetchers()
        print("Running in --demo mode against bundled sample data (no network calls made).")
    else:
        fetch_synoptic_fn = None
        fetch_ensemble_fn = None
        ensemble_models = [m.strip() for m in args.ensemble_models.split(",") if m.strip()]

    try:
        run = model_mod.run_model(
            location_name=loc.name,
            lat=loc.latitude,
            lon=loc.longitude,
            elevation_m=loc.elevation_m,
            forecast_days=args.days,
            synoptic_model=args.synoptic_model,
            ensemble_models=ensemble_models,
            ensemble_weight=args.ensemble_weight,
            fetch_synoptic_fn=fetch_synoptic_fn,
            fetch_ensemble_fn=fetch_ensemble_fn,
        )
    except data_mod.SnowDataError as exc:
        print(f"Error fetching forecast data: {exc}", file=sys.stderr)
        return 1

    print(
        f"Method blend: {run.ensemble_weight * 100:.0f}% ensemble agreement, "
        f"{run.synoptic_weight * 100:.0f}% synoptic rules "
        f"(synoptic model: {run.synoptic_model}; ensemble models: {', '.join(run.ensemble_models)})"
    )
    for w in run.warnings:
        print(f"Warning: {w}", file=sys.stderr)
    print()
    _print_daily_table(run)
    if args.hourly:
        _print_hourly_table(run)

    if args.json:
        _write_json(run, args.json)
        print(f"\nWrote full JSON results to {args.json}")
    if args.csv:
        _write_csv(run, args.csv)
        print(f"Wrote daily summary CSV to {args.csv}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
