"""
Data access layer: geocoding and Open-Meteo API calls.

Open-Meteo (https://open-meteo.com) is used because it is free, requires no
API key, and exposes both a deterministic forecast API (with pressure-level
variables, needed for thickness charts) and a genuine multi-member ensemble
API covering the UK Met Office (MOGREPS), ECMWF, NOAA GFS and DWD ICON
systems.

Every function here either returns parsed data or raises SnowDataError with
a human-readable message -- callers (the CLI) are expected to catch that and
report it cleanly rather than letting a stack trace surface.

NOTE ON TESTING: this module could not be exercised against the live
Open-Meteo API from the environment this project was built in (outbound
network access to api.open-meteo.com was blocked there). The request/response
shapes below follow Open-Meteo's published documentation as of August 2026.
The parsing code is written defensively (see `_collect_member_series`) so
that reasonable variations in the exact JSON field naming don't cause a
crash -- but you should run `--demo` first, and then a real one-off query,
before relying on this day to day. Please report anything that looks off.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ENSEMBLE_URL = "https://ensemble-api.open-meteo.com/v1/ensemble"

DEFAULT_SYNOPTIC_MODEL = "gfs_seamless"
DEFAULT_ENSEMBLE_MODELS = [
    "ukmo_global_20km",
    "icon_seamless_eps",
    "gfs_ensemble_025",
    "ecmwf_ifs_025",
]

REQUEST_TIMEOUT_S = 20


class SnowDataError(RuntimeError):
    """Raised for anything that goes wrong fetching or parsing weather data."""


@dataclass
class Location:
    name: str
    latitude: float
    longitude: float
    elevation_m: float
    country: str = ""
    admin1: str = ""


def geocode(place_name: str, prefer_country_code: str = "GB") -> Location:
    """Resolve a free-text place name to coordinates using Open-Meteo's
    geocoding service. Prefers a UK match if one is present in the results,
    but falls back to the top global match (with a warning left to the
    caller to surface) rather than failing outright.
    """
    try:
        resp = requests.get(
            GEOCODING_URL,
            params={"name": place_name, "count": 10, "language": "en", "format": "json"},
            timeout=REQUEST_TIMEOUT_S,
        )
        resp.raise_for_status()
        payload = resp.json()
    except requests.RequestException as exc:
        raise SnowDataError(f"Could not reach the geocoding service: {exc}") from exc
    except ValueError as exc:
        raise SnowDataError("Geocoding service returned something that wasn't valid JSON.") from exc

    results = payload.get("results") or []
    if not results:
        raise SnowDataError(
            f"No location found for '{place_name}'. Try a more specific name, "
            f"or pass --lat/--lon directly."
        )

    gb_matches = [r for r in results if r.get("country_code") == prefer_country_code]
    chosen = gb_matches[0] if gb_matches else results[0]

    loc = Location(
        name=chosen.get("name", place_name),
        latitude=float(chosen["latitude"]),
        longitude=float(chosen["longitude"]),
        elevation_m=float(chosen.get("elevation") or 0.0),
        country=chosen.get("country", ""),
        admin1=chosen.get("admin1", ""),
    )
    if not gb_matches:
        loc.name = f"{loc.name} (WARNING: no UK match found -- best global match used, country={loc.country})"
    return loc


def fetch_synoptic(
    lat: float,
    lon: float,
    forecast_days: int,
    model: str = DEFAULT_SYNOPTIC_MODEL,
) -> Dict[str, Any]:
    """Fetch deterministic surface + pressure-level data used for the
    synoptic rules-based scoring (thickness, freezing level, wet bulb
    inputs). Returns the raw Open-Meteo JSON payload.
    """
    hourly_vars = [
        "temperature_2m",
        "relative_humidity_2m",
        "precipitation",
        "precipitation_probability",
        "snowfall",
        "freezing_level_height",
        "weather_code",
        "geopotential_height_1000hPa",
        "geopotential_height_500hPa",
    ]
    try:
        resp = requests.get(
            FORECAST_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "hourly": ",".join(hourly_vars),
                "models": model,
                "forecast_days": forecast_days,
                "timezone": "Europe/London",
            },
            timeout=REQUEST_TIMEOUT_S,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        raise SnowDataError(f"Could not reach the Open-Meteo forecast API: {exc}") from exc
    except ValueError as exc:
        raise SnowDataError("Forecast API returned something that wasn't valid JSON.") from exc


def fetch_ensemble_one_model(
    lat: float,
    lon: float,
    forecast_days: int,
    model: str,
) -> Dict[str, Any]:
    """Fetch multi-member ensemble data for a single forecasting system.

    Deliberately one model per request rather than a combined
    `models=a,b,c` call: Open-Meteo's documented member-naming convention
    ('<var>_member01', etc) doesn't specify how it disambiguates members
    once several ensemble systems are combined in one response, and that
    couldn't be verified against a live call while this was built. Fetching
    one model at a time means each response's members are unambiguously
    that model's, at the cost of one HTTP request per model.
    """
    hourly_vars = ["temperature_2m", "precipitation", "snowfall", "weather_code"]
    try:
        resp = requests.get(
            ENSEMBLE_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "hourly": ",".join(hourly_vars),
                "models": model,
                "forecast_days": forecast_days,
                "timezone": "Europe/London",
            },
            timeout=REQUEST_TIMEOUT_S,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        raise SnowDataError(f"Could not reach the Open-Meteo ensemble API for model '{model}': {exc}") from exc
    except ValueError as exc:
        raise SnowDataError(f"Ensemble API returned something that wasn't valid JSON for model '{model}'.") from exc


def collect_member_series(hourly: Dict[str, Any], base_var: str) -> Dict[str, List[Any]]:
    """Given the 'hourly' dict of an ensemble API response, find every
    series that represents a member of `base_var` (e.g. 'snowfall').

    Open-Meteo's documented convention is to suffix member fields as
    '<var>_member01', '<var>_member02', ... with the unsuffixed '<var>'
    representing the control run where present. This function matches that
    convention but does not assume a fixed member count or that every
    variable has a control run, so it degrades gracefully if the exact
    naming differs slightly from what's documented.
    """
    pattern = re.compile(rf"^{re.escape(base_var)}(_member\d+)?$")
    series = {key: values for key, values in hourly.items() if pattern.match(key)}
    return series
