"""Build (and optionally refresh) the shareable UK Snow Outlook map artifact.

Usage:
    python tools/build_snow_map.py                 # refresh live data (rate-limited) + rebuild
    python tools/build_snow_map.py --dry-run        # rebuild from cached data, doesn't touch quota
    python tools/build_snow_map.py --limit 8         # change the rolling-24h refresh cap

Live data is fetched straight from Open-Meteo via snow_likelihood.model.run_model
for every station in map_locations.py, subject to the rate limiter in
rate_limit.py. The illustrative "Example scenario" dataset is a fixed,
hand-set cold-snap scenario -- it doesn't call the network and isn't
rate-limited, since it's just there to show the color/size range.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

TOOLS_DIR = Path(__file__).parent
REPO_ROOT = TOOLS_DIR.parent
sys.path.insert(0, str(REPO_ROOT))

import rate_limit
from map_locations import LOCATIONS, SEA_LEVEL_MAX_M, elev_class
from snow_likelihood import model as model_mod

OUTPUT_PATH = TOOLS_DIR / "output" / "snow_map.html"
LIVE_CACHE_PATH = TOOLS_DIR / "output" / "live_cache.json"
FORECAST_DAYS_DEFAULT = 4

CATEGORY_THRESHOLDS = [(10, "Very low"), (30, "Low"), (55, "Moderate"), (75, "High"), (101, "Very high")]


def categorise(pct):
    for upper, label in CATEGORY_THRESHOLDS:
        if pct < upper:
            return label
    return "Very high"


# ---- coastline projection (fixed once the location list is fixed) ----

def build_projection():
    geo = json.loads((TOOLS_DIR / "gb_coastline.geo.json").read_text())
    all_lonlat = []
    polygons = []
    for feature in geo["features"]:
        for poly in feature["geometry"]["coordinates"]:
            rings = []
            for ring in poly:
                pts = [(c[0], c[1]) for c in ring]
                rings.append(pts)
                all_lonlat.extend(pts)
            polygons.append(rings)
    for loc in LOCATIONS:
        all_lonlat.append((loc["lon"], loc["lat"]))

    lons = [p[0] for p in all_lonlat]
    lats = [p[1] for p in all_lonlat]
    lat_mean = (min(lats) + max(lats)) / 2
    cos_lat = math.cos(math.radians(lat_mean))
    raw_x_min, raw_x_max = min(lons) * cos_lat, max(lons) * cos_lat
    raw_y_min, raw_y_max = -max(lats), -min(lats)

    pad, w, h = 28, 640, 780
    scale = min((w - 2 * pad) / (raw_x_max - raw_x_min), (h - 2 * pad) / (raw_y_max - raw_y_min))

    def project(lon, lat):
        x = (lon * cos_lat - raw_x_min) * scale + pad
        y = (-lat - raw_y_min) * scale + pad
        return round(x, 2), round(y, 2)

    paths = []
    for rings in polygons:
        for ring in rings:
            pts = [project(lon, lat) for lon, lat in ring]
            paths.append("M " + " L ".join(f"{x},{y}" for x, y in pts) + " Z")

    xy_by_name = {loc["name"]: project(loc["lon"], loc["lat"]) for loc in LOCATIONS}
    return {"viewbox": [0, 0, w, h], "coastline_paths": paths, "xy": xy_by_name}


# ---- live dataset ----

def fetch_live(forecast_days: int, xy_by_name: dict) -> dict:
    out_locations = []
    for loc in LOCATIONS:
        run = model_mod.run_model(
            location_name=loc["name"], lat=loc["lat"], lon=loc["lon"],
            elevation_m=loc["elev"], forecast_days=forecast_days,
        )
        days = [
            {"date": d.date, "peak_pct": d.peak_score_pct, "category": d.category}
            for d in run.days
        ]
        best = max(days, key=lambda d: d["peak_pct"]) if days else {"peak_pct": 0.0, "category": "Very low", "date": None}
        x, y = xy_by_name[loc["name"]]
        out_locations.append({
            "name": loc["name"], "region": loc["region"], "elev": loc["elev"],
            "elev_class": elev_class(loc["elev"]), "x": x, "y": y, "days": days,
            "peak_pct": best["peak_pct"], "peak_category": best["category"], "peak_date": best["date"],
        })
    return {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "locations": out_locations,
    }


# ---- static illustrative dataset (not rate-limited, doesn't touch the network) ----

PEAK_BY_NAME = {
    "Ben Nevis Summit": 96, "Cairn Gorm Summit": 93, "Nevis Range (Aonach Mor)": 89,
    "The Lecht": 79, "Glenshee": 73, "Glencoe Mountain": 68, "Cross Fell": 59,
    "Scafell Pike": 53, "Yr Wyddfa (Snowdon)": 47, "Kinder Scout": 26,
    "Edinburgh": 16, "London": 3,
}
DEMO_DATES = ["2026-01-14", "2026-01-15", "2026-01-16", "2026-01-17"]
DEMO_DAY_FACTORS = [0.72, 1.0, 0.86, 0.55]


def build_demo(xy_by_name: dict) -> dict:
    out_locations = []
    for loc in LOCATIONS:
        peak = PEAK_BY_NAME[loc["name"]]
        days = []
        for date, factor in zip(DEMO_DATES, DEMO_DAY_FACTORS):
            p = round(min(99.0, peak * factor), 1)
            days.append({"date": date, "peak_pct": p, "category": categorise(p)})
        best = max(days, key=lambda d: d["peak_pct"])
        x, y = xy_by_name[loc["name"]]
        out_locations.append({
            "name": loc["name"], "region": loc["region"], "elev": loc["elev"],
            "elev_class": elev_class(loc["elev"]), "x": x, "y": y, "days": days,
            "peak_pct": best["peak_pct"], "peak_category": best["category"], "peak_date": best["date"],
        })
    return {"generated": "2026-01-13 (example)", "locations": out_locations}


HTML_TEMPLATE = r"""<!doctype html>
<title>UK Snow Outlook</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;0,6..72,600;1,6..72,500&family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">

<style>
  :root {
    --bg: #f8fafb; --surface: #fdfeff; --ink: #101d28; --ink-secondary: #47616e; --ink-muted: #7f97a2;
    --hairline: #dae5ea; --hairline-strong: #c2d3da; --accent: #104281; --accent-ink: #ffffff;
    --land: #dbe7ec; --land-stroke: #aec2cb;
    --cat-1: #86b6ef; --cat-2: #5598e7; --cat-3: #2a78d6; --cat-4: #1c5cab; --cat-5: #104281;
    --shadow: 0 1px 2px rgba(16,29,40,0.04), 0 8px 24px rgba(16,29,40,0.06);
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      --bg: #0b141c; --surface: #101b24; --ink: #edf4f7; --ink-secondary: #a7bfca; --ink-muted: #6b8493;
      --hairline: #1f2e38; --hairline-strong: #2a3c48; --accent: #86b6ef; --accent-ink: #08131c;
      --land: #16232c; --land-stroke: #263944;
      --cat-1: #9ec5f4; --cat-2: #6da7ec; --cat-3: #3987e5; --cat-4: #256abf; --cat-5: #184f95;
      --shadow: 0 1px 2px rgba(0,0,0,0.3), 0 12px 28px rgba(0,0,0,0.35);
    }
  }
  :root[data-theme="dark"] {
    --bg: #0b141c; --surface: #101b24; --ink: #edf4f7; --ink-secondary: #a7bfca; --ink-muted: #6b8493;
    --hairline: #1f2e38; --hairline-strong: #2a3c48; --accent: #86b6ef; --accent-ink: #08131c;
    --land: #16232c; --land-stroke: #26394d;
    --cat-1: #9ec5f4; --cat-2: #6da7ec; --cat-3: #3987e5; --cat-4: #256abf; --cat-5: #184f95;
    --shadow: 0 1px 2px rgba(0,0,0,0.3), 0 12px 28px rgba(0,0,0,0.35);
  }

  * { box-sizing: border-box; }
  html, body { background: var(--bg); }
  body {
    margin: 0; background: var(--bg); color: var(--ink);
    font-family: "IBM Plex Sans", "Segoe UI", system-ui, sans-serif;
    -webkit-font-smoothing: antialiased; padding: 40px 20px 64px;
  }
  .page { max-width: 980px; margin: 0 auto; }

  .eyebrow {
    font-family: "IBM Plex Mono", ui-monospace, monospace; font-size: 12px; letter-spacing: 0.14em;
    text-transform: uppercase; color: var(--ink-muted); display: flex; align-items: center; gap: 10px;
  }
  .eyebrow .dot { width: 6px; height: 6px; border-radius: 50%; background: var(--accent); flex: none; }

  header.masthead {
    display: flex; justify-content: space-between; align-items: flex-end; gap: 24px;
    border-bottom: 1px solid var(--hairline-strong); padding-bottom: 22px; margin-bottom: 16px; flex-wrap: wrap;
  }
  h1 {
    font-family: "Newsreader", Georgia, serif; font-weight: 500; font-size: clamp(32px, 5vw, 46px);
    line-height: 1.05; margin: 6px 0 0; text-wrap: balance; letter-spacing: -0.01em;
  }
  .subhead { margin: 10px 0 0; color: var(--ink-secondary); font-size: 15px; max-width: 46ch; }
  .masthead-meta { text-align: right; font-family: "IBM Plex Mono", ui-monospace, monospace; font-size: 12px; color: var(--ink-muted); line-height: 1.7; }
  .masthead-meta strong { color: var(--ink-secondary); font-weight: 500; }

  .toggle { display: inline-flex; border: 1px solid var(--hairline-strong); border-radius: 999px; padding: 3px; gap: 2px; background: var(--surface); }
  .toggle button {
    font-family: "IBM Plex Mono", ui-monospace, monospace; font-size: 12px; letter-spacing: 0.04em;
    border: none; background: transparent; color: var(--ink-secondary); padding: 7px 14px; border-radius: 999px; cursor: pointer;
  }
  .toggle button.active { background: var(--accent); color: var(--accent-ink); }
  .toggle button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }

  .status-row { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 20px; flex-wrap: wrap; }

  .refresh-control { position: relative; }
  .refresh-btn {
    font-family: "IBM Plex Mono", ui-monospace, monospace; font-size: 11.5px; color: var(--ink-secondary);
    background: var(--surface); border: 1px solid var(--hairline-strong); border-radius: 8px;
    padding: 7px 11px; cursor: pointer; display: inline-flex; align-items: center; gap: 7px;
  }
  .refresh-btn:hover { border-color: var(--accent); color: var(--ink); }
  .refresh-btn .quota { font-weight: 600; color: var(--ink); }
  .refresh-pop {
    display: none; position: absolute; top: calc(100% + 8px); left: 0; z-index: 30; width: 300px;
    background: var(--ink); color: var(--bg); font-size: 12.5px; line-height: 1.6; padding: 13px 15px;
    border-radius: 10px; box-shadow: 0 12px 28px rgba(0,0,0,0.28);
  }
  .refresh-pop.visible { display: block; }
  .refresh-pop b { display: block; margin-bottom: 4px; }

  .scenario-banner {
    display: none; align-items: center; gap: 10px; font-size: 13px; color: var(--ink-secondary);
    background: var(--surface); border: 1px dashed var(--hairline-strong); border-radius: 10px;
    padding: 10px 14px; margin-bottom: 20px;
  }
  .scenario-banner.visible { display: flex; }
  .scenario-banner .tag {
    font-family: "IBM Plex Mono", ui-monospace, monospace; font-size: 10px; letter-spacing: 0.08em;
    text-transform: uppercase; background: var(--cat-4); color: #fff; padding: 3px 8px; border-radius: 5px; flex: none;
  }

  .layout { display: grid; grid-template-columns: minmax(0, 1fr) 290px; gap: 22px; align-items: start; }
  @media (max-width: 760px) { .layout { grid-template-columns: 1fr; } }

  .map-card { background: var(--surface); border: 1px solid var(--hairline); border-radius: 16px; box-shadow: var(--shadow); padding: 18px 18px 8px; position: relative; }
  .map-card svg { width: 100%; height: auto; display: block; overflow: visible; }
  .land { fill: var(--land); stroke: var(--land-stroke); stroke-width: 1.4; stroke-linejoin: round; }

  .marker circle.halo, .marker rect.halo { fill: none; stroke-width: 1; opacity: 0; transition: opacity 120ms ease; }
  .marker:hover circle.halo, .marker:hover rect.halo, .marker.focus circle.halo, .marker.focus rect.halo { opacity: 0.35; }
  .marker .mark { stroke: var(--surface); stroke-width: 1.6; cursor: pointer; }

  .legend { display: flex; align-items: center; gap: 0; padding: 14px 4px 10px; flex-wrap: wrap; row-gap: 8px; }
  .legend-title { font-family: "IBM Plex Mono", ui-monospace, monospace; font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; color: var(--ink-muted); margin-right: 12px; }
  .legend-item { display: flex; align-items: center; gap: 6px; margin-right: 16px; }
  .legend-swatch { width: 12px; height: 12px; border-radius: 50%; flex: none; }
  .legend-item span { font-size: 12px; color: var(--ink-secondary); }
  .legend-shapes { display: flex; align-items: center; gap: 16px; padding: 0 4px 16px; font-size: 12px; color: var(--ink-secondary); flex-wrap: wrap; }
  .legend-shapes .shape-item { display: flex; align-items: center; gap: 7px; }
  .shape-swatch { width: 12px; height: 12px; flex: none; background: var(--ink-muted); }
  .shape-swatch.circle { border-radius: 50%; }
  .shape-swatch.diamond { transform: rotate(45deg); }

  .tooltip {
    position: fixed; pointer-events: none; background: var(--ink); color: var(--bg); font-size: 12px;
    padding: 9px 11px; border-radius: 9px; box-shadow: 0 8px 20px rgba(0,0,0,0.25); opacity: 0;
    transform: translate(-50%, -100%); transition: opacity 100ms ease; z-index: 40; max-width: 220px; line-height: 1.5;
  }
  .tooltip.visible { opacity: 1; }
  .tooltip .t-name { font-weight: 600; display: block; margin-bottom: 2px; }
  .tooltip .t-meta { font-family: "IBM Plex Mono", ui-monospace, monospace; font-size: 11px; opacity: 0.8; }

  aside.rail { display: flex; flex-direction: column; gap: 14px; }
  .panel { background: var(--surface); border: 1px solid var(--hairline); border-radius: 14px; padding: 16px 16px 6px; box-shadow: var(--shadow); }
  .panel h2 { font-family: "IBM Plex Mono", ui-monospace, monospace; font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--ink-muted); margin: 0 0 10px; display: flex; align-items: center; gap: 7px; }
  .panel h2 .shape-swatch { margin: 0; }
  .station { display: flex; justify-content: space-between; align-items: center; gap: 10px; padding: 9px 0; border-top: 1px solid var(--hairline); }
  .panel .station:first-of-type { border-top: none; }
  .station-name { font-size: 13px; font-weight: 500; }
  .station-region { font-size: 11px; color: var(--ink-muted); }
  .station-pct { font-family: "IBM Plex Mono", ui-monospace, monospace; font-variant-numeric: tabular-nums; font-size: 13px; font-weight: 600; flex: none; text-align: right; min-width: 48px; }
  .chip { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 7px; flex: none; }

  .table-section { margin-top: 26px; }
  .table-section h3 {
    font-family: "IBM Plex Mono", ui-monospace, monospace; font-size: 11px; letter-spacing: 0.07em; text-transform: uppercase;
    color: var(--ink-muted); margin: 0 0 8px; display: flex; align-items: center; gap: 8px;
  }
  table.data-table { width: 100%; border-collapse: collapse; font-size: 13px; }
  .table-wrap { overflow-x: auto; }
  table.data-table th {
    text-align: left; font-family: "IBM Plex Mono", ui-monospace, monospace; font-size: 10.5px; letter-spacing: 0.06em;
    text-transform: uppercase; color: var(--ink-muted); font-weight: 500; padding: 8px 12px; border-bottom: 1px solid var(--hairline-strong); white-space: nowrap;
  }
  table.data-table td { padding: 10px 12px; border-bottom: 1px solid var(--hairline); white-space: nowrap; }
  table.data-table td.num { font-family: "IBM Plex Mono", ui-monospace, monospace; font-variant-numeric: tabular-nums; text-align: right; }
  table.data-table tr:last-child td { border-bottom: none; }
  .cat-pill { display: inline-flex; align-items: center; gap: 6px; font-family: "IBM Plex Mono", ui-monospace, monospace; font-size: 11px; }

  footer { margin-top: 36px; padding-top: 18px; border-top: 1px solid var(--hairline); color: var(--ink-muted); font-size: 12px; line-height: 1.7; }
  footer strong { color: var(--ink-secondary); }
  footer a { color: var(--ink-secondary); }
</style>

<div class="page">
  <header class="masthead">
    <div>
      <div class="eyebrow"><span class="dot"></span>UK SNOW OUTLOOK</div>
      <h1>Where it's likely to snow</h1>
      <p class="subhead">Blended synoptic + ensemble snow-likelihood across twelve UK stations, from mountain summits to sea level.</p>
    </div>
    <div style="display:flex; flex-direction:column; align-items:flex-end; gap:10px;">
      <div class="toggle" role="group" aria-label="Data source">
        <button id="btn-live" class="active">Live forecast</button>
        <button id="btn-demo">Example scenario</button>
      </div>
      <div class="masthead-meta" id="meta-line">generated <strong>&mdash;</strong></div>
    </div>
  </header>

  <div class="status-row">
    <div class="refresh-control">
      <button class="refresh-btn" id="refresh-btn">&#8635; Refresh status &middot; <span class="quota">__QUOTA_USED__/__QUOTA_LIMIT__</span> today</button>
      <div class="refresh-pop" id="refresh-pop">
        <b>This page can't fetch live data itself</b>
        Shared pages run in a sandbox with no general internet access, so a click here can't call the weather API directly.
        Live data updates when the maintainer asks Claude to refresh it &mdash; rate-limited to <b>__QUOTA_LIMIT__ per rolling 24h</b> to stay polite to Open-Meteo's free API.
        <br><br>Used today: __QUOTA_USED__/__QUOTA_LIMIT__ &middot; last refresh __LAST_REFRESH__.
      </div>
    </div>
    <div style="font-size:12px; color: var(--ink-muted);">Sea-level threshold: &lt; __SEA_LEVEL_MAX__m</div>
  </div>

  <div class="scenario-banner" id="scenario-banner">
    <span class="tag">Illustrative</span>
    <span>This is a fabricated cold-snap scenario used to show the full likelihood range &mdash; not a real forecast.</span>
  </div>

  <div class="layout">
    <div class="map-card">
      <svg id="map" viewBox="0 0 __VBW__ __VBH__" xmlns="http://www.w3.org/2000/svg">
        <g id="coastline"></g>
        <g id="markers"></g>
      </svg>
      <div class="legend">
        <span class="legend-title">Peak likelihood</span>
        <div class="legend-item"><span class="legend-swatch" style="background:var(--cat-1)"></span><span>Very low</span></div>
        <div class="legend-item"><span class="legend-swatch" style="background:var(--cat-2)"></span><span>Low</span></div>
        <div class="legend-item"><span class="legend-swatch" style="background:var(--cat-3)"></span><span>Moderate</span></div>
        <div class="legend-item"><span class="legend-swatch" style="background:var(--cat-4)"></span><span>High</span></div>
        <div class="legend-item"><span class="legend-swatch" style="background:var(--cat-5)"></span><span>Very high</span></div>
      </div>
      <div class="legend-shapes">
        <div class="shape-item"><span class="shape-swatch circle"></span>Mountain &amp; summit station</div>
        <div class="shape-item"><span class="shape-swatch diamond"></span>Sea level &amp; lowland (&lt; __SEA_LEVEL_MAX__m)</div>
      </div>
    </div>

    <aside class="rail">
      <div class="panel">
        <h2><span class="shape-swatch circle"></span>Mountains &amp; summits</h2>
        <div id="station-list-mountain"></div>
      </div>
      <div class="panel">
        <h2><span class="shape-swatch diamond"></span>Sea level &amp; lowland</h2>
        <div id="station-list-sea"></div>
      </div>
    </aside>
  </div>

  <div class="table-section">
    <h3><span class="shape-swatch circle"></span>Mountains &amp; summits (&ge; __SEA_LEVEL_MAX__m)</h3>
    <div class="table-wrap">
      <table class="data-table">
        <thead><tr><th>Station</th><th>Region</th><th>Elev.</th><th>Peak day</th><th>Peak %</th><th>Category</th></tr></thead>
        <tbody id="table-body-mountain"></tbody>
      </table>
    </div>
  </div>

  <div class="table-section">
    <h3><span class="shape-swatch diamond"></span>Sea level &amp; lowland (&lt; __SEA_LEVEL_MAX__m)</h3>
    <div class="table-wrap">
      <table class="data-table">
        <thead><tr><th>Station</th><th>Region</th><th>Elev.</th><th>Peak day</th><th>Peak %</th><th>Category</th></tr></thead>
        <tbody id="table-body-sea"></tbody>
      </table>
    </div>
  </div>

  <footer>
    <strong>Method:</strong> each station blends a synoptic rules-based score (thickness, freezing level, wet-bulb proxy) with multi-model ensemble agreement (UK Met Office, DWD ICON, NOAA GFS, ECMWF), 40/60 weighted, via the open-source <strong>snow_likelihood</strong> model. Data from <a href="https://open-meteo.com">Open-Meteo</a>.<br>
    This is an independent hobby forecast, not an official warning service &mdash; it is not a substitute for Met Office, SAIS, or mountain safety advice.
  </footer>

  <div class="tooltip" id="tooltip"></div>
</div>

<script>
const DATA = __DATA_JSON__;
const COASTLINE = __COASTLINE_JSON__;

const CAT_VAR = { "Very low": "--cat-1", "Low": "--cat-2", "Moderate": "--cat-3", "High": "--cat-4", "Very high": "--cat-5" };
function catColor(cat) { return getComputedStyle(document.documentElement).getPropertyValue(CAT_VAR[cat] || "--cat-1").trim(); }
function radiusFor(pct) {
  const minR = 6, maxR = 17;
  const t = Math.sqrt(Math.max(0, Math.min(100, pct)) / 100);
  return minR + (maxR - minR) * t;
}

const svgNS = "http://www.w3.org/2000/svg";
const coastlineG = document.getElementById("coastline");
COASTLINE.forEach(d => {
  const p = document.createElementNS(svgNS, "path");
  p.setAttribute("d", d); p.setAttribute("class", "land");
  coastlineG.appendChild(p);
});

const tooltip = document.getElementById("tooltip");
function showTooltip(evt, loc) {
  tooltip.innerHTML =
    '<span class="t-name">' + loc.name + '</span>' +
    '<span class="t-meta">' + loc.region + ' &middot; ' + loc.elev + 'm</span><br>' +
    '<span class="t-meta">peak ' + loc.peak_pct.toFixed(1) + '% &middot; ' + loc.peak_category + ' &middot; ' + loc.peak_date + '</span>';
  tooltip.classList.add("visible");
  positionTooltip(evt);
}
function positionTooltip(evt) { tooltip.style.left = evt.clientX + "px"; tooltip.style.top = (evt.clientY - 14) + "px"; }
function hideTooltip() { tooltip.classList.remove("visible"); }

function renderMap(dataset) {
  const markersG = document.getElementById("markers");
  markersG.innerHTML = "";
  const mountains = dataset.locations.filter(l => l.elev_class === "mountain").sort((a, b) => b.peak_pct - a.peak_pct);
  const sea = dataset.locations.filter(l => l.elev_class === "sea_level").sort((a, b) => b.peak_pct - a.peak_pct);

  dataset.locations.forEach(loc => {
    const g = document.createElementNS(svgNS, "g");
    g.setAttribute("class", "marker");
    g.setAttribute("tabindex", "0");
    g.setAttribute("role", "img");
    g.setAttribute("aria-label", loc.name + ", " + (loc.elev_class === "mountain" ? "mountain station" : "sea level station") + ", peak " + loc.peak_pct.toFixed(1) + "%, " + loc.peak_category);

    const r = radiusFor(loc.peak_pct);
    const color = catColor(loc.peak_category);
    const isMountain = loc.elev_class === "mountain";

    if (isMountain) {
      const halo = document.createElementNS(svgNS, "circle");
      halo.setAttribute("class", "halo"); halo.setAttribute("cx", loc.x); halo.setAttribute("cy", loc.y);
      halo.setAttribute("r", r + 6); halo.setAttribute("stroke", color);
      g.appendChild(halo);

      const dot = document.createElementNS(svgNS, "circle");
      dot.setAttribute("class", "mark"); dot.setAttribute("cx", loc.x); dot.setAttribute("cy", loc.y);
      dot.setAttribute("r", r); dot.setAttribute("fill", color);
      g.appendChild(dot);
    } else {
      const s = r * 1.5;
      const halo = document.createElementNS(svgNS, "rect");
      halo.setAttribute("class", "halo");
      halo.setAttribute("x", loc.x - s/2 - 5); halo.setAttribute("y", loc.y - s/2 - 5);
      halo.setAttribute("width", s + 10); halo.setAttribute("height", s + 10);
      halo.setAttribute("transform", "rotate(45 " + loc.x + " " + loc.y + ")");
      halo.setAttribute("stroke", color);
      g.appendChild(halo);

      const dot = document.createElementNS(svgNS, "rect");
      dot.setAttribute("class", "mark");
      dot.setAttribute("x", loc.x - s/2); dot.setAttribute("y", loc.y - s/2);
      dot.setAttribute("width", s); dot.setAttribute("height", s);
      dot.setAttribute("transform", "rotate(45 " + loc.x + " " + loc.y + ")");
      dot.setAttribute("fill", color);
      g.appendChild(dot);
    }

    g.addEventListener("mouseenter", (e) => showTooltip(e, loc));
    g.addEventListener("mousemove", positionTooltip);
    g.addEventListener("mouseleave", hideTooltip);
    g.addEventListener("focus", (e) => {
      const rect = g.getBoundingClientRect();
      showTooltip({clientX: rect.left + rect.width/2, clientY: rect.top}, loc);
    });
    g.addEventListener("blur", hideTooltip);

    markersG.appendChild(g);
  });

  function fillList(elId, locs) {
    const list = document.getElementById(elId);
    list.innerHTML = "";
    locs.forEach(loc => {
      const row = document.createElement("div");
      row.className = "station";
      row.innerHTML =
        '<div><span class="chip" style="background:' + catColor(loc.peak_category) + '"></span>' +
        '<span class="station-name">' + loc.name + '</span><br>' +
        '<span class="station-region" style="margin-left:15px;">' + loc.region + '</span></div>' +
        '<div class="station-pct" style="color:' + catColor(loc.peak_category) + '">' + loc.peak_pct.toFixed(1) + '%</div>';
      list.appendChild(row);
    });
  }
  fillList("station-list-mountain", mountains);
  fillList("station-list-sea", sea);

  function fillTable(elId, locs) {
    const tbody = document.getElementById(elId);
    tbody.innerHTML = "";
    locs.forEach(loc => {
      const tr = document.createElement("tr");
      tr.innerHTML =
        '<td>' + loc.name + '</td>' +
        '<td style="color:var(--ink-secondary)">' + loc.region + '</td>' +
        '<td class="num">' + loc.elev + ' m</td>' +
        '<td>' + loc.peak_date + '</td>' +
        '<td class="num" style="color:' + catColor(loc.peak_category) + '; font-weight:600;">' + loc.peak_pct.toFixed(1) + '%</td>' +
        '<td><span class="cat-pill"><span class="chip" style="background:' + catColor(loc.peak_category) + '"></span>' + loc.peak_category + '</span></td>';
      tbody.appendChild(tr);
    });
  }
  fillTable("table-body-mountain", mountains);
  fillTable("table-body-sea", sea);

  document.getElementById("meta-line").innerHTML = "generated <strong>" + dataset.generated + "</strong>";
  document.getElementById("scenario-banner").classList.toggle("visible", dataset === DATA.demo);
}

document.getElementById("btn-live").addEventListener("click", () => {
  document.getElementById("btn-live").classList.add("active");
  document.getElementById("btn-demo").classList.remove("active");
  renderMap(DATA.live);
});
document.getElementById("btn-demo").addEventListener("click", () => {
  document.getElementById("btn-demo").classList.add("active");
  document.getElementById("btn-live").classList.remove("active");
  renderMap(DATA.demo);
});
document.getElementById("refresh-btn").addEventListener("click", (e) => {
  e.stopPropagation();
  document.getElementById("refresh-pop").classList.toggle("visible");
});
document.addEventListener("click", () => document.getElementById("refresh-pop").classList.remove("visible"));

renderMap(DATA.live);
</script>
"""


def render_html(live: dict, demo: dict, projection: dict, quota_used: int, quota_limit: int, last_refresh: str) -> str:
    data = {"live": live, "demo": demo}
    html = HTML_TEMPLATE
    html = html.replace("__VBW__", str(projection["viewbox"][2])).replace("__VBH__", str(projection["viewbox"][3]))
    html = html.replace("__DATA_JSON__", json.dumps(data, separators=(",", ":")))
    html = html.replace("__COASTLINE_JSON__", json.dumps(projection["coastline_paths"]))
    html = html.replace("__QUOTA_USED__", str(quota_used)).replace("__QUOTA_LIMIT__", str(quota_limit))
    html = html.replace("__LAST_REFRESH__", last_refresh)
    html = html.replace("__SEA_LEVEL_MAX__", str(SEA_LEVEL_MAX_M))
    return html


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=5, help="max live refreshes per rolling 24h (default 5)")
    ap.add_argument("--forecast-days", type=int, default=FORECAST_DAYS_DEFAULT)
    ap.add_argument("--dry-run", action="store_true", help="rebuild from cached live data, skip fetch + quota")
    args = ap.parse_args()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    projection = build_projection()
    demo = build_demo(projection["xy"])

    if args.dry_run:
        if not LIVE_CACHE_PATH.exists():
            print("No cached live data yet -- run once without --dry-run first.", file=sys.stderr)
            sys.exit(1)
        live = json.loads(LIVE_CACHE_PATH.read_text())
        allowed, used, limit, _ = rate_limit.check(args.limit)
        last_refresh = live.get("generated", "never")
    else:
        allowed, used, limit, retry_after = rate_limit.check(args.limit)
        if not allowed:
            hrs = retry_after / 3600
            print(f"Refresh limit reached ({used}/{limit} in the last 24h). Try again in {hrs:.1f}h.", file=sys.stderr)
            sys.exit(2)
        live = fetch_live(args.forecast_days, projection["xy"])
        LIVE_CACHE_PATH.write_text(json.dumps(live))
        used = rate_limit.record()
        limit = args.limit
        last_refresh = live["generated"]

    html = render_html(live, demo, projection, used, limit, last_refresh)
    OUTPUT_PATH.write_text(html)
    print(f"Wrote {OUTPUT_PATH} ({used}/{limit} refreshes used in rolling 24h)")


if __name__ == "__main__":
    main()
