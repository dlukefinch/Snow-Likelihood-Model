"""UK Snow Outlook -- live web app.

Serves the reference-station map (twelve fixed UK stations, refreshed
periodically in the background) and a postcode endpoint that runs the real
snow_likelihood model live, for the caller's exact geocoded coordinates --
not an approximation borrowed from the nearest fixed station.

Run locally:
    uvicorn webapp.app:app --reload --port 8000

Deploy: run behind a reverse proxy (nginx) terminating TLS, e.g.
    uvicorn webapp.app:app --host 127.0.0.1 --port 8000 --workers 2
as a systemd service, with nginx proxy_pass to 127.0.0.1:8000.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from snow_likelihood import data as data_mod
from snow_likelihood import model as model_mod
from snow_likelihood.mapgeo import haversine_km
from snow_likelihood.stations import LOCATIONS, SEA_LEVEL_MAX_M, elev_class

from webapp.geocode import GeocodeError, geocode_postcode
from webapp.render import HTML_TEMPLATE, build_demo

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("snow_outlook")

app = FastAPI(title="UK Snow Outlook")

STATION_REFRESH_INTERVAL_S = 30 * 60  # keep the 12-station snapshot this fresh
POSTCODE_CACHE_TTL_S = 30 * 60
POSTCODE_RATE_LIMIT = 15          # requests
POSTCODE_RATE_WINDOW_S = 60 * 60  # per rolling hour, per IP

_state_lock = threading.Lock()
_station_state = {"live": None, "demo": None, "rendered_html": "<p>Loading&hellip;</p>"}

_postcode_cache: dict[str, tuple[float, dict]] = {}
_postcode_cache_lock = threading.Lock()

_rate_state: dict[str, list[float]] = {}
_rate_lock = threading.Lock()


def _check_rate_limit(ip: str) -> Optional[float]:
    """Returns None if allowed, else seconds until the caller may retry."""
    now = time.time()
    with _rate_lock:
        hits = [t for t in _rate_state.get(ip, []) if now - t < POSTCODE_RATE_WINDOW_S]
        if len(hits) >= POSTCODE_RATE_LIMIT:
            return POSTCODE_RATE_WINDOW_S - (now - hits[0])
        hits.append(now)
        _rate_state[ip] = hits
    return None


def _fetch_stations_live(forecast_days: int = 4) -> dict:
    out_locations = []
    for loc in LOCATIONS:
        run = model_mod.run_model(
            location_name=loc["name"], lat=loc["lat"], lon=loc["lon"],
            elevation_m=loc["elev"], forecast_days=forecast_days,
        )
        days = [{"date": d.date, "peak_pct": d.peak_score_pct, "category": d.category} for d in run.days]
        best = max(days, key=lambda d: d["peak_pct"]) if days else {"peak_pct": 0.0, "category": "Very low", "date": None}
        out_locations.append({
            "name": loc["name"], "region": loc["region"], "elev": loc["elev"],
            "elev_class": elev_class(loc["elev"]),
            "lat": loc["lat"], "lon": loc["lon"], "days": days,
            "peak_pct": best["peak_pct"], "peak_category": best["category"], "peak_date": best["date"],
        })
    return {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "locations": out_locations}


def _refresh_stations():
    try:
        live = _fetch_stations_live()
    except data_mod.SnowDataError as exc:
        log.warning("station refresh failed: %s", exc)
        return
    demo = build_demo()
    html = HTML_TEMPLATE(live=live, demo=demo)
    with _state_lock:
        _station_state["live"] = live
        _station_state["demo"] = demo
        _station_state["rendered_html"] = html
    log.info("station snapshot refreshed: %s", live["generated"])


async def _refresh_loop():
    while True:
        await asyncio.to_thread(_refresh_stations)
        await asyncio.sleep(STATION_REFRESH_INTERVAL_S)


@app.on_event("startup")
async def on_startup():
    await asyncio.to_thread(_refresh_stations)
    asyncio.create_task(_refresh_loop())


@app.get("/", response_class=HTMLResponse)
def index():
    with _state_lock:
        return _station_state["rendered_html"]


def _run_point_lookup(lat: float, lon: float, label: str, precise: bool) -> dict:
    try:
        run = model_mod.run_model(
            location_name=label, lat=lat, lon=lon,
            elevation_m=None, forecast_days=4,
        )
    except data_mod.SnowDataError as exc:
        raise HTTPException(status_code=502, detail=f"Couldn't fetch live forecast data: {exc}")

    days = [{"date": d.date, "peak_pct": d.peak_score_pct, "category": d.category} for d in run.days]
    best = max(days, key=lambda d: d["peak_pct"]) if days else {"peak_pct": 0.0, "category": "Very low", "date": None}

    nearest_name, nearest_km = None, None
    for loc in LOCATIONS:
        d = haversine_km(lat, lon, loc["lat"], loc["lon"])
        if nearest_km is None or d < nearest_km:
            nearest_km, nearest_name = d, loc["name"]

    return {
        "label": label,
        "precise": precise,
        "lat": round(lat, 4), "lon": round(lon, 4),
        "elevation_m": round(run.elevation_m, 0),
        "days": days,
        "peak_pct": best["peak_pct"], "peak_category": best["category"], "peak_date": best["date"],
        "nearest_station": nearest_name, "nearest_station_km": round(nearest_km, 1) if nearest_km is not None else None,
        "warnings": run.warnings,
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }


@app.get("/api/postcode")
def api_postcode(pc: str, request: Request):
    ip = request.client.host if request.client else "unknown"
    retry_after = _check_rate_limit(ip)
    if retry_after is not None:
        raise HTTPException(status_code=429, detail=f"Too many lookups -- try again in {int(retry_after / 60) + 1} min.")

    key = pc.strip().upper()
    now = time.time()
    with _postcode_cache_lock:
        cached = _postcode_cache.get(key)
        if cached and now - cached[0] < POSTCODE_CACHE_TTL_S:
            return JSONResponse(cached[1])

    try:
        geo = geocode_postcode(pc)
    except GeocodeError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    result = _run_point_lookup(geo.lat, geo.lon, geo.label, geo.precise)
    with _postcode_cache_lock:
        _postcode_cache[key] = (now, result)
    return JSONResponse(result)


@app.get("/api/location")
def api_location(lat: float, lon: float, label: str, request: Request):
    """Re-run the live model for a saved favourite's coordinates. Same cache
    and rate limit as /api/postcode (they share the underlying live calls
    each uncached lookup makes)."""
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise HTTPException(status_code=422, detail="Invalid coordinates.")

    ip = request.client.host if request.client else "unknown"
    retry_after = _check_rate_limit(ip)
    if retry_after is not None:
        raise HTTPException(status_code=429, detail=f"Too many lookups -- try again in {int(retry_after / 60) + 1} min.")

    key = f"{round(lat, 3)},{round(lon, 3)}"
    now = time.time()
    with _postcode_cache_lock:
        cached = _postcode_cache.get(key)
        if cached and now - cached[0] < POSTCODE_CACHE_TTL_S:
            return JSONResponse(cached[1])

    result = _run_point_lookup(lat, lon, label[:60], True)
    with _postcode_cache_lock:
        _postcode_cache[key] = (now, result)
    return JSONResponse(result)
