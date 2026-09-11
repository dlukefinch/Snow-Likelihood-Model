"""Renders the UK Snow Outlook page: same visual design as the earlier
Artifact snapshot, but the postcode panel now calls a live backend endpoint
(/api/postcode) that runs the real model for the caller's exact coordinates,
instead of approximating from the nearest fixed station.
"""

from __future__ import annotations

import json

from snow_likelihood.stations import MAX_ELEV_M, MID_MAX_M, SEA_LEVEL_MAX_M, elev_class

CATEGORY_THRESHOLDS = [(10, "Very low"), (30, "Low"), (55, "Moderate"), (75, "High"), (101, "Very high")]


def categorise(pct):
    for upper, label in CATEGORY_THRESHOLDS:
        if pct < upper:
            return label
    return "Very high"


PEAK_BY_NAME = {
    "Ben Nevis Summit": 96, "Cairn Gorm Summit": 93, "Nevis Range (Aonach Mor)": 89,
    "The Lecht": 79, "Glenshee": 73, "Glencoe Mountain": 68, "Cross Fell": 59,
    "Scafell Pike": 53, "Yr Wyddfa (Snowdon)": 47, "Kinder Scout": 26,
    "Edinburgh": 16, "London": 3, "Cardiff": 4, "Belfast": 9,
    "Aviemore": 34, "Alston": 38, "Buxton": 41,
    "Newcastle upon Tyne": 12, "Bristol": 3, "Southampton": 2,
    "Aberdeen": 18, "Norwich": 4, "Nottingham": 6,
    "Brighton": 5, "St Ives": 3, "Margate": 6, "Corby": 11,
    "Whitby": 9, "Alnwick": 13,
    "Tomintoul": 42, "Malham": 24, "Princetown": 33, "Storey Arms": 36, "Glenshane Pass": 44,
    "Pen y Fan": 62, "Slieve Donard": 58, "High Willhays": 45, "Helvellyn": 84, "The Cheviot": 55,
}
DEMO_DATES = ["2026-01-14", "2026-01-15", "2026-01-16", "2026-01-17"]
DEMO_DAY_FACTORS = [0.72, 1.0, 0.86, 0.55]


def build_demo() -> dict:
    from snow_likelihood.stations import LOCATIONS
    out_locations = []
    for loc in LOCATIONS:
        peak = PEAK_BY_NAME[loc["name"]]
        days = []
        for date, factor in zip(DEMO_DATES, DEMO_DAY_FACTORS):
            p = round(min(99.0, peak * factor), 1)
            days.append({"date": date, "peak_pct": p, "category": categorise(p)})
        best = max(days, key=lambda d: d["peak_pct"])
        out_locations.append({
            "name": loc["name"], "region": loc["region"], "elev": loc["elev"],
            "elev_class": elev_class(loc["elev"]),
            "lat": loc["lat"], "lon": loc["lon"], "days": days,
            "peak_pct": best["peak_pct"], "peak_category": best["category"], "peak_date": best["date"],
        })
    return {"generated": "2026-01-13 (example)", "locations": out_locations}


_PAGE = r"""<!doctype html>
<title>Snow Watch SLM</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<link href="https://unpkg.com/maplibre-gl@4/dist/maplibre-gl.css" rel="stylesheet">
<script src="https://unpkg.com/maplibre-gl@4/dist/maplibre-gl.js"></script>

<style>
  :root {
    --bg: #f8fafb; --surface: #fdfeff; --ink: #101d28; --ink-secondary: #47616e; --ink-muted: #7f97a2;
    --hairline: #dae5ea; --hairline-strong: #c2d3da; --accent: #104281; --accent-ink: #ffffff;
    --land: #dbe7ec; --land-stroke: #aec2cb;
    --cat-1: #86b6ef; --cat-2: #5598e7; --cat-3: #2a78d6; --cat-4: #1c5cab; --cat-5: #104281;
    --locate-accent: #c9720a;
    --error: #c0392b;
    --shadow: 0 1px 2px rgba(16,29,40,0.04), 0 8px 24px rgba(16,29,40,0.06);
  }
  /* Three themes: Light (default), Night (soft dark blue-grey), Dark (true black).
     data-theme is set by the theme toggle JS and persisted to localStorage;
     with no explicit choice, Night follows the OS dark-mode preference. */
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]):not([data-theme="dark"]) {
      --bg: #0b141c; --surface: #101b24; --ink: #edf4f7; --ink-secondary: #a7bfca; --ink-muted: #6b8493;
      --hairline: #1f2e38; --hairline-strong: #2a3c48; --accent: #86b6ef; --accent-ink: #08131c;
      --land: #16232c; --land-stroke: #263944;
      --cat-1: #9ec5f4; --cat-2: #6da7ec; --cat-3: #3987e5; --cat-4: #256abf; --cat-5: #184f95;
      --locate-accent: #f0a94e;
      --error: #e0685a;
      --shadow: 0 1px 2px rgba(0,0,0,0.3), 0 12px 28px rgba(0,0,0,0.35);
    }
  }
  :root[data-theme="night"] {
    --bg: #0b141c; --surface: #101b24; --ink: #edf4f7; --ink-secondary: #a7bfca; --ink-muted: #6b8493;
    --hairline: #1f2e38; --hairline-strong: #2a3c48; --accent: #86b6ef; --accent-ink: #08131c;
    --land: #16232c; --land-stroke: #26394d;
    --cat-1: #9ec5f4; --cat-2: #6da7ec; --cat-3: #3987e5; --cat-4: #256abf; --cat-5: #184f95;
    --locate-accent: #f0a94e;
    --error: #e0685a;
    --shadow: 0 1px 2px rgba(0,0,0,0.3), 0 12px 28px rgba(0,0,0,0.35);
  }
  :root[data-theme="dark"] {
    --bg: #000000; --surface: #0a0a0a; --ink: #f2f5f7; --ink-secondary: #9fb3bd; --ink-muted: #5f7078;
    --hairline: #161616; --hairline-strong: #262626; --accent: #6fa8e8; --accent-ink: #05090d;
    --land: #0a0a0a; --land-stroke: #1c1c1c;
    --cat-1: #9ec5f4; --cat-2: #6da7ec; --cat-3: #3987e5; --cat-4: #256abf; --cat-5: #184f95;
    --locate-accent: #f0a94e;
    --error: #e0685a;
    --shadow: 0 1px 2px rgba(0,0,0,0.6), 0 12px 28px rgba(0,0,0,0.55);
  }

  * { box-sizing: border-box; }
  html, body { background: var(--bg); }
  body {
    margin: 0; background: var(--bg); color: var(--ink);
    font-family: "Inter", "Segoe UI", system-ui, sans-serif;
    -webkit-font-smoothing: antialiased; padding: 40px 20px 64px;
  }
  .page { max-width: 980px; margin: 0 auto; }

  .eyebrow {
    font-family: "Inter", "Segoe UI", system-ui, sans-serif; font-size: 12px; letter-spacing: 0.14em;
    text-transform: uppercase; color: var(--ink-muted); display: flex; align-items: center; gap: 10px;
  }
  .eyebrow .dot { width: 6px; height: 6px; border-radius: 50%; background: var(--accent); flex: none; }

  header.masthead {
    display: flex; justify-content: space-between; align-items: flex-end; gap: 24px;
    border-bottom: 1px solid var(--hairline-strong); padding-bottom: 22px; margin-bottom: 16px; flex-wrap: wrap;
  }
  h1 {
    font-family: "Inter", "Segoe UI", system-ui, sans-serif; font-weight: 600; font-size: clamp(20px, 2.6vw, 26px);
    line-height: 1.05; margin: 6px 0 0; text-wrap: balance; letter-spacing: -0.01em;
  }
  .subhead { margin: 10px 0 0; color: var(--ink-secondary); font-size: 15px; max-width: 46ch; }
  .masthead-meta { text-align: right; font-family: "Inter", "Segoe UI", system-ui, sans-serif; font-size: 12px; color: var(--ink-muted); line-height: 1.7; }
  .masthead-meta strong { color: var(--ink-secondary); font-weight: 500; }

  .toggle { display: inline-flex; border: 1px solid var(--hairline-strong); border-radius: 999px; padding: 3px; gap: 2px; background: var(--surface); }
  .toggle button {
    font-family: "Inter", "Segoe UI", system-ui, sans-serif; font-size: 12px; letter-spacing: 0.04em;
    border: none; background: transparent; color: var(--ink-secondary); padding: 7px 14px; border-radius: 999px; cursor: pointer;
  }
  .toggle button.active { background: var(--accent); color: var(--accent-ink); }
  .toggle button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }

  .locate-card {
    background: var(--surface); border: 1px solid var(--hairline-strong); border-radius: 14px;
    box-shadow: var(--shadow); padding: 16px 18px; margin-bottom: 18px;
  }
  .locate-label {
    font-family: "Inter", "Segoe UI", system-ui, sans-serif; font-size: 11px; letter-spacing: 0.08em; font-weight: 700;
    text-transform: uppercase; color: var(--accent); margin-bottom: 3px;
  }
  .locate-sub { font-size: 12px; color: var(--ink-muted); margin-bottom: 10px; }
  .locate-row { display: flex; gap: 8px; flex-wrap: wrap; }
  .locate-input {
    flex: 1 1 200px; font-family: "Inter", "Segoe UI", system-ui, sans-serif; font-size: 14px;
    background: var(--bg); color: var(--ink); border: 1px solid var(--hairline-strong); border-radius: 8px;
    padding: 9px 12px; min-width: 0;
  }
  .locate-input:focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; }
  .locate-btn {
    font-family: "Inter", sans-serif; font-size: 13.5px; font-weight: 600;
    background: var(--accent); color: var(--accent-ink); border: none; border-radius: 8px;
    padding: 9px 18px; cursor: pointer; flex: none; min-width: 140px;
  }
  .locate-btn:hover { opacity: 0.9; }
  .locate-btn:disabled { opacity: 0.6; cursor: default; }
  .locate-error { display: none; color: var(--error); font-size: 12.5px; margin-top: 9px; }
  .locate-error.visible { display: block; }
  .locate-result { display: none; margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--hairline); flex-direction: column; gap: 12px; }
  .locate-result.visible { display: flex; }
  .locate-result .r-head { display: flex; align-items: center; gap: 8px; }
  .locate-result .r-station { font-size: 15px; font-weight: 600; }
  .locate-result .r-stat { display: flex; align-items: center; gap: 18px; flex-wrap: wrap; row-gap: 10px; }
  .locate-result .r-pct {
    font-family: "Inter", sans-serif; font-variant-numeric: tabular-nums;
    font-size: 34px; font-weight: 700; line-height: 1;
  }
  .locate-result .r-cat-pill {
    display: inline-flex; align-items: center; gap: 6px; font-size: 12.5px; font-weight: 600;
    padding: 4px 11px; border-radius: 999px; border: 1.5px solid var(--hairline-strong);
  }
  .locate-result .r-detail { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
  .locate-result .r-detail-label {
    font-family: "Inter", sans-serif; font-size: 10px; letter-spacing: 0.07em;
    text-transform: uppercase; color: var(--ink-muted);
  }
  .locate-result .r-detail-value { font-size: 13px; color: var(--ink-secondary); }

  .star-btn {
    font-size: 20px; line-height: 1; background: none; border: none; cursor: pointer;
    color: var(--ink-muted); padding: 2px; flex: none; transition: color 120ms ease, transform 120ms ease;
  }
  .star-btn:hover { color: var(--locate-accent); transform: scale(1.1); }
  .star-btn.starred { color: var(--locate-accent); }
  .station .star-btn { font-size: 16px; }

  .scenario-banner {
    display: none; align-items: center; gap: 10px; font-size: 13px; color: var(--ink-secondary);
    background: var(--surface); border: 1px dashed var(--hairline-strong); border-radius: 10px;
    padding: 10px 14px; margin-bottom: 20px;
  }
  .scenario-banner.visible { display: flex; }
  .scenario-banner .tag {
    font-family: "Inter", "Segoe UI", system-ui, sans-serif; font-size: 10px; letter-spacing: 0.08em;
    text-transform: uppercase; background: var(--cat-4); color: #fff; padding: 3px 8px; border-radius: 5px; flex: none;
  }

  .map-card { background: var(--surface); border: 1px solid var(--hairline); border-radius: 16px; box-shadow: var(--shadow); padding: 18px 18px 8px; position: relative; margin-bottom: 18px; }
  .map-card #map { width: 100%; height: 560px; border-radius: 10px; overflow: hidden; background: var(--land); }
  @media (max-width: 560px) { .map-card #map { height: 420px; } }

  .maplibregl-popup-content {
    background: var(--ink); color: var(--bg); font-family: "Inter", sans-serif; font-size: 12px;
    padding: 9px 11px; border-radius: 9px; box-shadow: 0 8px 20px rgba(0,0,0,0.25); line-height: 1.5;
  }
  .maplibregl-popup-tip { border-top-color: var(--ink) !important; border-bottom-color: var(--ink) !important; }
  .mm-name { font-weight: 600; display: block; margin-bottom: 2px; }
  .mm-meta { font-family: "Inter", "Segoe UI", system-ui, sans-serif; font-size: 11px; opacity: 0.8; }

  /* Muted, theme-matched map attribution -- OpenFreeMap/OSM's terms require
     it stay present and reachable, so it's dimmed rather than removed. */
  .maplibregl-ctrl-attrib.maplibregl-compact,
  .maplibregl-ctrl-attrib.maplibregl-compact-show {
    background-color: var(--surface) !important; color: var(--ink-secondary); box-shadow: var(--shadow);
  }
  .maplibregl-ctrl-attrib.maplibregl-compact { opacity: 0.35; transition: opacity 150ms ease; }
  .maplibregl-ctrl-attrib.maplibregl-compact:hover, .maplibregl-ctrl-attrib.maplibregl-compact-show { opacity: 1; }
  .maplibregl-ctrl-attrib.maplibregl-compact:after { background-image: none !important; }
  .maplibregl-ctrl-attrib-button { background-color: transparent !important; background-image: none !important; }
  .maplibregl-ctrl-attrib-button:after {
    content: ""; position: absolute; inset: 0; margin: auto;
    width: 4px; height: 4px; border-radius: 50%; background: var(--ink-muted);
  }
  .maplibregl-ctrl-attrib a { color: var(--ink-secondary) !important; }

  @keyframes locate-pulse { 0%, 100% { opacity: 0.85; transform: scale(1); } 50% { opacity: 0.25; transform: scale(1.35); } }
  .you-marker { position: relative; width: 22px; height: 22px; }
  .you-marker .ring {
    position: absolute; inset: 0; border-radius: 50%; border: 2px solid var(--locate-accent);
    animation: locate-pulse 1.8s ease-in-out infinite;
  }
  @media (prefers-reduced-motion: reduce) { .you-marker .ring { animation: none; } }
  .you-marker .star {
    position: absolute; left: 50%; top: 50%; width: 14px; height: 14px; transform: translate(-50%, -50%);
    background: var(--locate-accent); clip-path: polygon(50% 0%, 61% 35%, 98% 35%, 68% 57%, 79% 91%, 50% 70%, 21% 91%, 32% 57%, 2% 35%, 39% 35%);
    border: 1.4px solid var(--surface);
  }

  .legend { display: flex; align-items: center; gap: 0; padding: 14px 4px 10px; flex-wrap: wrap; row-gap: 8px; }
  .legend-title { font-family: "Inter", "Segoe UI", system-ui, sans-serif; font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; color: var(--ink-muted); margin-right: 12px; }
  .legend-item { display: flex; align-items: center; gap: 6px; margin-right: 16px; }
  .legend-swatch { width: 12px; height: 12px; border-radius: 50%; flex: none; }
  .legend-item span { font-size: 12px; color: var(--ink-secondary); }
  .legend-shapes { display: flex; align-items: center; gap: 16px; padding: 0 4px 16px; font-size: 12px; color: var(--ink-secondary); flex-wrap: wrap; }
  .legend-shapes .shape-item { display: flex; align-items: center; gap: 7px; }
  .shape-swatch { width: 12px; height: 12px; flex: none; background: var(--ink-muted); }
  .shape-swatch.circle { border-radius: 50%; }
  .shape-swatch.mountain { clip-path: polygon(0% 100%, 33% 20%, 46% 55%, 63% 5%, 100% 100%); opacity: 0.7; }
  .shape-swatch.square { border-radius: 2px; }
  .shape-swatch.diamond { transform: rotate(45deg); }
  .shape-swatch.star { background: var(--locate-accent); clip-path: polygon(50% 0%, 61% 35%, 98% 35%, 68% 57%, 79% 91%, 50% 70%, 21% 91%, 32% 57%, 2% 35%, 39% 35%); }

  .panel { background: var(--surface); border: 1px solid var(--hairline); border-radius: 14px; padding: 16px 16px 14px; box-shadow: var(--shadow); margin-bottom: 18px; }
  .panel h2 { font-family: "Inter", "Segoe UI", system-ui, sans-serif; font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--ink-muted); margin: 0; display: flex; align-items: center; gap: 7px; }
  .panel h2 .shape-swatch { margin: 0; }
  .panel-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 10px; flex-wrap: wrap; }
  .panel-collapse-btn {
    display: flex; align-items: center; gap: 8px; background: none; border: none; padding: 2px;
    margin: -2px; cursor: pointer; border-radius: 6px;
  }
  .panel-collapse-btn:hover { background: var(--bg); }
  .panel-collapse-btn:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
  .panel-collapse-btn .chevron { font-size: 9px; color: var(--ink-muted); transition: transform 150ms ease; }
  .panel.collapsed .panel-collapse-btn .chevron { transform: rotate(-90deg); }
  .panel.collapsed #panel-body { display: none; }
  .panel.collapsed .panel-head { margin-bottom: 0; }
  .toggle.compact { padding: 2px; flex-wrap: wrap; row-gap: 2px; }
  .toggle.compact button { padding: 5px 10px; font-size: 11px; }
  .station-list-scroll {
    display: flex; gap: 10px; overflow-x: auto; overflow-y: hidden; padding: 2px 2px 10px;
    scrollbar-width: thin; -webkit-overflow-scrolling: touch;
  }
  .station {
    display: flex; flex-direction: column; align-items: flex-start; gap: 8px; position: relative;
    flex: none; width: 168px; padding: 12px 13px; border: 1px solid var(--hairline);
    border-radius: 10px; background: var(--bg);
  }
  .station .star-btn.starred { position: absolute; top: 6px; right: 6px; font-size: 15px; }
  .station-name { font-size: 13px; font-weight: 500; }
  .station-region { font-size: 11px; color: var(--ink-muted); }
  .station-pct { font-family: "Inter", "Segoe UI", system-ui, sans-serif; font-variant-numeric: tabular-nums; font-size: 16px; font-weight: 600; }
  .chip { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 7px; flex: none; }

  .table-section { margin-top: 26px; }
  .table-section h3 {
    font-family: "Inter", "Segoe UI", system-ui, sans-serif; font-size: 11px; letter-spacing: 0.07em; text-transform: uppercase;
    color: var(--ink-muted); margin: 0 0 8px; display: flex; align-items: center; gap: 8px;
  }
  table.data-table { width: 100%; border-collapse: collapse; font-size: 13px; }
  .table-wrap { overflow-x: auto; }
  table.data-table th {
    text-align: left; font-family: "Inter", "Segoe UI", system-ui, sans-serif; font-size: 10.5px; letter-spacing: 0.06em;
    text-transform: uppercase; color: var(--ink-muted); font-weight: 500; padding: 8px 12px; border-bottom: 1px solid var(--hairline-strong); white-space: nowrap;
  }
  table.data-table td { padding: 10px 12px; border-bottom: 1px solid var(--hairline); white-space: nowrap; }
  table.data-table td.num { font-family: "Inter", "Segoe UI", system-ui, sans-serif; font-variant-numeric: tabular-nums; text-align: right; }
  table.data-table tr:last-child td { border-bottom: none; }
  .cat-pill { display: inline-flex; align-items: center; gap: 6px; font-family: "Inter", "Segoe UI", system-ui, sans-serif; font-size: 11px; }

  footer { margin-top: 36px; padding-top: 18px; border-top: 1px solid var(--hairline); color: var(--ink-muted); font-size: 12px; line-height: 1.7; }
  footer strong { color: var(--ink-secondary); }
  footer a { color: var(--ink-secondary); }
</style>

<div class="page">
  <header class="masthead">
    <div>
      <h1>SLM &middot; Snow Likelihood Model</h1>
      <p class="subhead">Blended synoptic + ensemble snow-likelihood across thirty-nine UK stations, from mountain summits through mid-elevation uplands to sea level.</p>
    </div>
    <div style="display:flex; flex-direction:column; align-items:flex-end; gap:10px;">
      <div class="toggle compact" role="group" aria-label="Theme">
        <button id="theme-toggle-light">Light</button>
        <button id="theme-toggle-night">Night</button>
        <button id="theme-toggle-dark">Dark</button>
      </div>
      <div class="toggle" role="group" aria-label="Data source">
        <button id="btn-live" class="active">Live forecast</button>
        <button id="btn-demo">Example scenario</button>
      </div>
      <div class="masthead-meta" id="meta-line">Generated <strong>-</strong></div>
    </div>
  </header>

  <div class="locate-card">
    <div class="locate-label">Check your exact location</div>
    <div class="locate-sub">Runs the live model for your real coordinates - not borrowed from the nearest station.</div>
    <div class="locate-row">
      <input class="locate-input" id="locate-input" type="text" placeholder="Enter a UK postcode, e.g. EH1 or SW1A 1AA" autocomplete="off">
      <button class="locate-btn" id="locate-btn">Check likelihood</button>
    </div>
    <div class="locate-error" id="locate-error"></div>
    <div class="locate-result" id="locate-result">
      <div class="r-head">
        <button class="star-btn" id="r-star" title="Save to favourites" aria-pressed="false">&#9734;</button>
        <div class="r-station" id="r-station"></div>
      </div>
      <div class="r-stat">
        <span class="r-pct" id="r-pct"></span>
        <span class="r-cat-pill" id="r-cat-pill"><span class="chip" id="r-cat-dot"></span><span id="r-cat-text"></span></span>
        <div class="r-detail"><span class="r-detail-label">Peak day</span><span class="r-detail-value" id="r-peak-date"></span></div>
        <div class="r-detail"><span class="r-detail-label">Elevation</span><span class="r-detail-value" id="r-elev"></span></div>
        <div class="r-detail"><span class="r-detail-label">Coordinates</span><span class="r-detail-value" id="r-coords"></span></div>
        <div class="r-detail" id="r-nearest-row"><span class="r-detail-label">Nearest station</span><span class="r-detail-value" id="r-nearest"></span></div>
      </div>
    </div>
  </div>

  <div class="panel collapsed" id="stations-panel">
    <div class="panel-head">
      <button class="panel-collapse-btn" id="panel-collapse-btn" aria-expanded="false" aria-controls="panel-body">
        <span class="chevron">&#9660;</span>
        <h2>Reference stations</h2>
      </button>
      <div class="toggle compact" role="group" aria-label="Elevation band">
        <button id="elev-toggle-sea">&lt;__SEA_LEVEL_MAX__m</button>
        <button id="elev-toggle-mid">201&ndash;500m</button>
        <button id="elev-toggle-mountain" class="active">__MOUNTAIN_MIN__&ndash;__MAX_ELEV__m</button>
        <button id="elev-toggle-favourites">Favourites</button>
      </div>
    </div>
    <div id="panel-body">
      <div id="station-list" class="station-list-scroll"></div>
    </div>
  </div>

  <div class="scenario-banner" id="scenario-banner">
    <span class="tag">Illustrative</span>
    <span>This is a fabricated cold-snap scenario used to show the full likelihood range - not a real forecast.</span>
  </div>

  <div class="map-card">
    <div id="map"></div>
    <div class="legend">
      <span class="legend-title">Peak likelihood</span>
      <div class="legend-item"><span class="legend-swatch" style="background:var(--cat-1)"></span><span>Very low</span></div>
      <div class="legend-item"><span class="legend-swatch" style="background:var(--cat-2)"></span><span>Low</span></div>
      <div class="legend-item"><span class="legend-swatch" style="background:var(--cat-3)"></span><span>Moderate</span></div>
      <div class="legend-item"><span class="legend-swatch" style="background:var(--cat-4)"></span><span>High</span></div>
      <div class="legend-item"><span class="legend-swatch" style="background:var(--cat-5)"></span><span>Very high</span></div>
    </div>
    <div class="legend-shapes">
      <div class="shape-item"><span class="shape-swatch mountain"></span>Mountain &amp; summit station (__MOUNTAIN_MIN__&ndash;__MAX_ELEV__m)</div>
      <div class="shape-item"><span class="shape-swatch square"></span>Mid-elevation &amp; upland (201&ndash;500m)</div>
      <div class="shape-item"><span class="shape-swatch diamond"></span>Sea level &amp; lowland (&lt; __SEA_LEVEL_MAX__m)</div>
      <div class="shape-item"><span class="shape-swatch star"></span>Your checked location</div>
    </div>
  </div>

  <div class="table-section">
    <h3><span class="shape-swatch mountain"></span>Mountains &amp; summits (__MOUNTAIN_MIN__&ndash;__MAX_ELEV__m)</h3>
    <div class="table-wrap">
      <table class="data-table">
        <thead><tr><th>Station</th><th>Region</th><th>Elev.</th><th>Peak day</th><th>Peak %</th><th>Category</th></tr></thead>
        <tbody id="table-body-mountain"></tbody>
      </table>
    </div>
  </div>

  <div class="table-section">
    <h3><span class="shape-swatch square"></span>Mid-elevation &amp; upland (201&ndash;500m)</h3>
    <div class="table-wrap">
      <table class="data-table">
        <thead><tr><th>Station</th><th>Region</th><th>Elev.</th><th>Peak day</th><th>Peak %</th><th>Category</th></tr></thead>
        <tbody id="table-body-mid"></tbody>
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
    <strong>Method:</strong> each point blends a synoptic rules-based score (thickness, freezing level, wet-bulb proxy) with multi-model ensemble agreement (UK Met Office, DWD ICON, NOAA GFS, ECMWF), 40/60 weighted, via the open-source <strong>SLM</strong> (Snow Likelihood Model). Weather data from <a href="https://open-meteo.com">Open-Meteo</a>, postcode geocoding from <a href="https://postcodes.io">postcodes.io</a>.<br>
    This is an independent hobby forecast, not an official warning service - it is not a substitute for Met Office, SAIS, or mountain safety advice.
  </footer>

</div>

<script>
const DATA = __DATA_JSON__;

const CAT_VAR = { "Very low": "--cat-1", "Low": "--cat-2", "Moderate": "--cat-3", "High": "--cat-4", "Very high": "--cat-5" };
function catColor(cat) { return getComputedStyle(document.documentElement).getPropertyValue(CAT_VAR[cat] || "--cat-1").trim(); }

// Renders any "YYYY-MM-DD..." string as "D Month YYYY", preserving whatever
// follows the date (a time/UTC suffix, or the demo's "(example)" marker).
const MONTH_NAMES = ["January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December"];
function formatDate(value) {
  if (!value) return value;
  const m = value.match(/^(\d{4})-(\d{2})-(\d{2})(.*)$/);
  if (!m) return value;
  const [, y, mo, d, rest] = m;
  return parseInt(d, 10) + " " + MONTH_NAMES[parseInt(mo, 10) - 1] + " " + y + rest;
}
function radiusFor(pct) {
  const minR = 6, maxR = 17;
  const t = Math.sqrt(Math.max(0, Math.min(100, pct)) / 100);
  return minR + (maxR - minR) * t;
}

function toGeoJSON(dataset) {
  return {
    type: "FeatureCollection",
    features: dataset.locations.map(loc => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: [loc.lon, loc.lat] },
      properties: {
        name: loc.name, region: loc.region, elev: loc.elev, elev_class: loc.elev_class,
        peak_pct: loc.peak_pct, peak_category: loc.peak_category, peak_date: loc.peak_date,
        color: catColor(loc.peak_category), radius: radiusFor(loc.peak_pct),
      },
    })),
  };
}

function popupHTML(p) {
  return '<span class="mm-name">' + p.name + '</span>' +
    '<span class="mm-meta">' + p.region + ' &middot; ' + p.elev + 'm</span><br>' +
    '<span class="mm-meta">peak ' + p.peak_pct.toFixed(1) + '% &middot; ' + p.peak_category + ' &middot; ' + formatDate(p.peak_date) + '</span>';
}

// 20x20 SDF diamond, tintable per-feature via icon-color.
function makeDiamondSDF() {
  const c = document.createElement("canvas");
  c.width = 20; c.height = 20;
  const ctx = c.getContext("2d");
  ctx.fillStyle = "#fff";
  ctx.beginPath();
  ctx.moveTo(10, 1); ctx.lineTo(19, 10); ctx.lineTo(10, 19); ctx.lineTo(1, 10);
  ctx.closePath(); ctx.fill();
  return ctx.getImageData(0, 0, 20, 20);
}

// 20x20 SDF square, tintable per-feature via icon-color.
function makeSquareSDF() {
  const c = document.createElement("canvas");
  c.width = 20; c.height = 20;
  const ctx = c.getContext("2d");
  ctx.fillStyle = "#fff";
  ctx.fillRect(2, 2, 16, 16);
  return ctx.getImageData(0, 0, 20, 20);
}

// 20x20 SDF twin-peak mountain silhouette, tintable per-feature via icon-color.
function makeMountainSDF() {
  const c = document.createElement("canvas");
  c.width = 20; c.height = 20;
  const ctx = c.getContext("2d");
  ctx.fillStyle = "#fff";
  ctx.beginPath();
  ctx.moveTo(2, 18);
  ctx.lineTo(8, 5);
  ctx.lineTo(11, 10);
  ctx.lineTo(15, 2);
  ctx.lineTo(19, 18);
  ctx.closePath();
  ctx.fill();
  return ctx.getImageData(0, 0, 20, 20);
}

const UK_BOUNDS = (() => {
  const lats = DATA.live.locations.map(l => l.lat), lons = DATA.live.locations.map(l => l.lon);
  return [[Math.min(...lons) - 0.8, Math.min(...lats) - 0.5], [Math.max(...lons) + 0.8, Math.max(...lats) + 0.5]];
})();

// ---- theme (Light / Night / Dark) ----
const THEME_KEY = "snowOutlookTheme";
const THEMES = ["light", "night", "dark"];

function getStoredTheme() {
  try { return localStorage.getItem(THEME_KEY); } catch { return null; }
}
function setStoredTheme(theme) {
  try { localStorage.setItem(THEME_KEY, theme); } catch { /* ignore */ }
}

// No stored choice yet -> default to Dark (true black) regardless of OS
// preference. Visitors can still switch to Light/Night manually.
let currentTheme = getStoredTheme() || "dark";
document.documentElement.dataset.theme = currentTheme;

function mapStyleUrl() {
  return "https://tiles.openfreemap.org/styles/" + (currentTheme === "light" ? "positron" : "dark");
}

const map = new maplibregl.Map({
  container: "map",
  style: mapStyleUrl(),
  bounds: UK_BOUNDS,
  fitBoundsOptions: { padding: 20 },
  attributionControl: false,
});
map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
map.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-right");
// MapLibre's compact attribution starts expanded and only collapses to the
// small icon after the map's first drag (it's bound to the "drag" event
// internally) -- collapse it immediately instead of waiting for that.
map.getContainer().querySelectorAll(".maplibregl-ctrl-attrib.maplibregl-compact-show")
  .forEach(el => el.classList.remove("maplibregl-compact-show"));

function syncThemeButtons() {
  THEMES.forEach(t => document.getElementById("theme-toggle-" + t).classList.toggle("active", t === currentTheme));
}
syncThemeButtons();

function setTheme(theme, persist = true) {
  currentTheme = theme;
  document.documentElement.dataset.theme = theme;
  syncThemeButtons();
  if (persist) setStoredTheme(theme);
  // diff:false forces a full style reload (and a fresh "style.load" event) --
  // MapLibre's default diff-based update strips our runtime-added
  // sources/layers/images (they're not part of either base style's JSON)
  // without ever re-firing "style.load" to let us re-add them.
  map.setStyle(mapStyleUrl(), { diff: false });
}
THEMES.forEach(t => document.getElementById("theme-toggle-" + t).addEventListener("click", () => setTheme(t)));

let currentDataset = null;
let youMarker = null;
let listMode = "mountain"; // "mountain" (>500m), "mid" (201-500m), "sea_level" (<200m), or "favourites"

// ---- favourites (saved to this browser, no account system) ----

const FAV_KEY = "snowOutlookFavourites";

function getFavourites() {
  try { return JSON.parse(localStorage.getItem(FAV_KEY)) || []; }
  catch { return []; }
}
function setFavourites(favs) {
  localStorage.setItem(FAV_KEY, JSON.stringify(favs));
}
function favKey(lat, lon) { return lat.toFixed(3) + "," + lon.toFixed(3); }
function isFavourited(lat, lon) {
  const k = favKey(lat, lon);
  return getFavourites().some(f => favKey(f.lat, f.lon) === k);
}
function addFavourite(fav) {
  const favs = getFavourites();
  const k = favKey(fav.lat, fav.lon);
  if (!favs.some(f => favKey(f.lat, f.lon) === k)) {
    favs.push(fav);
    setFavourites(favs);
  }
}
function removeFavourite(lat, lon) {
  const k = favKey(lat, lon);
  setFavourites(getFavourites().filter(f => favKey(f.lat, f.lon) !== k));
}

function stationRowHTML(name, region, pct, cat) {
  return '<div><span class="chip" style="background:' + catColor(cat) + '"></span>' +
    '<span class="station-name">' + name + '</span><br>' +
    '<span class="station-region" style="margin-left:15px;">' + region + '</span></div>' +
    '<div class="station-pct" style="color:' + catColor(cat) + '">' + pct.toFixed(1) + '%</div>';
}

function renderStationList() {
  if (listMode === "favourites") { renderFavouritesList(); return; }
  if (!currentDataset) return;
  const list = document.getElementById("station-list");
  list.innerHTML = "";
  currentDataset.locations
    .filter(l => l.elev_class === listMode)
    .sort((a, b) => b.peak_pct - a.peak_pct)
    .forEach(loc => {
      const row = document.createElement("div");
      row.className = "station";
      row.innerHTML = stationRowHTML(loc.name, loc.region, loc.peak_pct, loc.peak_category);
      list.appendChild(row);
    });
}

async function renderFavouritesList() {
  const list = document.getElementById("station-list");
  const favs = getFavourites();
  if (favs.length === 0) {
    list.innerHTML = '<div class="station-region" style="padding:12px 0;">No saved locations yet - search a postcode above and tap &#9734; to save it here.</div>';
    return;
  }
  list.innerHTML = favs.map(f => '<div class="station-region" style="padding:9px 0;">' + f.label + '&hellip;</div>').join("");

  const results = await Promise.all(favs.map(async f => {
    try {
      const resp = await fetch("/api/location?lat=" + f.lat + "&lon=" + f.lon + "&label=" + encodeURIComponent(f.label));
      if (!resp.ok) return { fav: f, error: true };
      return { fav: f, body: await resp.json() };
    } catch {
      return { fav: f, error: true };
    }
  }));

  if (listMode !== "favourites") return; // user switched tabs while this was in flight
  list.innerHTML = "";
  results.forEach(({ fav, body, error }) => {
    const row = document.createElement("div");
    row.className = "station";
    if (error || !body) {
      row.innerHTML = '<div><span class="station-name">' + fav.label + '</span><br>' +
        '<span class="station-region">Couldn\'t load</span></div>' +
        '<button class="star-btn starred" title="Remove favourite">&#9733;</button>';
    } else {
      row.innerHTML = stationRowHTML(body.label, body.elevation_m + "m", body.peak_pct, body.peak_category) +
        '<button class="star-btn starred" title="Remove favourite">&#9733;</button>';
      row.style.cursor = "pointer";
      row.addEventListener("click", (e) => {
        if (e.target.closest(".star-btn")) return;
        map.flyTo({ center: [fav.lon, fav.lat], zoom: 9, speed: 0.8 });
        showYouMarker(fav.lon, fav.lat, catColor(body.peak_category));
      });
    }
    row.querySelector(".star-btn").addEventListener("click", (e) => {
      e.stopPropagation();
      removeFavourite(fav.lat, fav.lon);
      renderFavouritesList();
      syncStarButton();
    });
    list.appendChild(row);
  });
}

function setListMode(mode) {
  listMode = mode;
  ["mountain", "mid", "sea_level", "favourites"].forEach(m => {
    document.getElementById("elev-toggle-" + (m === "sea_level" ? "sea" : m)).classList.toggle("active", m === mode);
  });
  renderStationList();
}

document.getElementById("elev-toggle-sea").addEventListener("click", () => setListMode("sea_level"));
document.getElementById("elev-toggle-mid").addEventListener("click", () => setListMode("mid"));
document.getElementById("elev-toggle-mountain").addEventListener("click", () => setListMode("mountain"));
document.getElementById("elev-toggle-favourites").addEventListener("click", () => setListMode("favourites"));

// ---- reference-stations panel collapse (remembered per browser) ----
const PANEL_COLLAPSE_KEY = "snowOutlookStationsCollapsed";
const stationsPanel = document.getElementById("stations-panel");
const panelCollapseBtn = document.getElementById("panel-collapse-btn");

function getStoredCollapse() {
  try {
    const v = localStorage.getItem(PANEL_COLLAPSE_KEY);
    return v === null ? true : v === "1"; // collapsed by default until the visitor opens it
  } catch { return true; }
}
function setStoredCollapse(collapsed) {
  try { localStorage.setItem(PANEL_COLLAPSE_KEY, collapsed ? "1" : "0"); } catch { /* ignore */ }
}
function setPanelCollapsed(collapsed) {
  stationsPanel.classList.toggle("collapsed", collapsed);
  panelCollapseBtn.setAttribute("aria-expanded", String(!collapsed));
  setStoredCollapse(collapsed);
}
panelCollapseBtn.addEventListener("click", () => setPanelCollapsed(!stationsPanel.classList.contains("collapsed")));
setPanelCollapsed(getStoredCollapse());

function renderMap(dataset) {
  currentDataset = dataset;
  const geojson = toGeoJSON(dataset);
  const src = map.getSource("stations");
  if (src) {
    src.setData(geojson);
  }

  const mountains = dataset.locations.filter(l => l.elev_class === "mountain").sort((a, b) => b.peak_pct - a.peak_pct);
  const mid = dataset.locations.filter(l => l.elev_class === "mid").sort((a, b) => b.peak_pct - a.peak_pct);
  const sea = dataset.locations.filter(l => l.elev_class === "sea_level").sort((a, b) => b.peak_pct - a.peak_pct);

  renderStationList();

  function fillTable(elId, locs) {
    const tbody = document.getElementById(elId);
    tbody.innerHTML = "";
    locs.forEach(loc => {
      const tr = document.createElement("tr");
      tr.innerHTML =
        '<td>' + loc.name + '</td>' +
        '<td style="color:var(--ink-secondary)">' + loc.region + '</td>' +
        '<td class="num">' + loc.elev + ' m</td>' +
        '<td>' + formatDate(loc.peak_date) + '</td>' +
        '<td class="num" style="color:' + catColor(loc.peak_category) + '; font-weight:600;">' + loc.peak_pct.toFixed(1) + '%</td>' +
        '<td><span class="cat-pill"><span class="chip" style="background:' + catColor(loc.peak_category) + '"></span>' + loc.peak_category + '</span></td>';
      tbody.appendChild(tr);
    });
  }
  fillTable("table-body-mountain", mountains);
  fillTable("table-body-mid", mid);
  fillTable("table-body-sea", sea);

  document.getElementById("meta-line").innerHTML = "Generated <strong>" + formatDate(dataset.generated) + "</strong>";
  document.getElementById("scenario-banner").classList.toggle("visible", dataset === DATA.demo);
}

// Re-runs on initial load AND after setStyle() (theme switch), since a new
// style wipes custom sources/layers/images but not map-level event listeners.
map.on("style.load", () => {
  // Guard every add* call: some browsers/style-reload timings re-fire
  // "style.load" for a style that already has our runtime images/sources/
  // layers still attached, and an "already exists" exception here would
  // abort the rest of this handler -- silently dropping every layer after
  // the failure point, including the station icon layers.
  if (!map.hasImage("diamond-sdf")) map.addImage("diamond-sdf", makeDiamondSDF(), { sdf: true });
  if (!map.hasImage("square-sdf")) map.addImage("square-sdf", makeSquareSDF(), { sdf: true });
  if (!map.hasImage("mountain-sdf")) map.addImage("mountain-sdf", makeMountainSDF(), { sdf: true });

  if (!map.getSource("stations")) {
    map.addSource("stations", { type: "geojson", data: toGeoJSON(DATA.live) });
  }

  // Subtle hillshade for terrain texture, inserted just below labels.
  if (!map.getSource("terrain-dem")) {
    map.addSource("terrain-dem", {
      type: "raster-dem",
      tiles: ["https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"],
      encoding: "terrarium",
      tileSize: 256,
      maxzoom: 15,
    });
  }
  if (!map.getLayer("hillshade")) {
    const firstSymbolId = map.getStyle().layers.find(l => l.type === "symbol")?.id;
    map.addLayer({
      id: "hillshade", type: "hillshade", source: "terrain-dem",
      paint: { "hillshade-exaggeration": 0.5, "hillshade-shadow-color": "#7c95a1", "hillshade-highlight-color": "#ffffff" },
    }, firstSymbolId);
  }

  if (!map.getLayer("stations-mountain")) {
    map.addLayer({
      id: "stations-mountain", type: "symbol", source: "stations",
      filter: ["==", ["get", "elev_class"], "mountain"],
      layout: { "icon-image": "mountain-sdf", "icon-size": ["/", ["get", "radius"], 11], "icon-allow-overlap": true },
      paint: { "icon-color": ["get", "color"], "icon-opacity": 0.7 },
    });
  }
  if (!map.getLayer("stations-mid")) {
    map.addLayer({
      id: "stations-mid", type: "symbol", source: "stations",
      filter: ["==", ["get", "elev_class"], "mid"],
      layout: { "icon-image": "square-sdf", "icon-size": ["/", ["get", "radius"], 8], "icon-allow-overlap": true },
      paint: { "icon-color": ["get", "color"] },
    });
  }
  if (!map.getLayer("stations-sea")) {
    map.addLayer({
      id: "stations-sea", type: "symbol", source: "stations",
      filter: ["==", ["get", "elev_class"], "sea_level"],
      layout: { "icon-image": "diamond-sdf", "icon-size": ["/", ["get", "radius"], 8], "icon-allow-overlap": true },
      paint: { "icon-color": ["get", "color"] },
    });
  }

  renderMap(currentDataset || DATA.live);
});

// Registered once (not per style reload) -- MapLibre re-fires these for the
// new style's re-added layers of the same id automatically.
const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 12 });
["stations-mountain", "stations-mid", "stations-sea"].forEach(layerId => {
  map.on("mouseenter", layerId, (e) => {
    map.getCanvas().style.cursor = "pointer";
    const f = e.features[0];
    popup.setLngLat(f.geometry.coordinates).setHTML(popupHTML(f.properties)).addTo(map);
  });
  map.on("mouseleave", layerId, () => {
    map.getCanvas().style.cursor = "";
    popup.remove();
  });
});

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

// ---- exact-location postcode lookup (live backend call) ----

function showYouMarker(lon, lat, color) {
  if (youMarker) youMarker.remove();
  const el = document.createElement("div");
  el.className = "you-marker";
  el.innerHTML = '<div class="ring"></div><div class="star" style="background:' + color + '"></div>';
  youMarker = new maplibregl.Marker({ element: el }).setLngLat([lon, lat]).addTo(map);
}

let lastLocateResult = null;

function syncStarButton() {
  const starBtn = document.getElementById("r-star");
  if (!lastLocateResult) return;
  const starred = isFavourited(lastLocateResult.lat, lastLocateResult.lon);
  starBtn.classList.toggle("starred", starred);
  starBtn.innerHTML = starred ? "&#9733;" : "&#9734;";
  starBtn.setAttribute("aria-pressed", String(starred));
  starBtn.title = starred ? "Remove from favourites" : "Save to favourites";
}

document.getElementById("r-star").addEventListener("click", () => {
  if (!lastLocateResult) return;
  if (isFavourited(lastLocateResult.lat, lastLocateResult.lon)) {
    removeFavourite(lastLocateResult.lat, lastLocateResult.lon);
  } else {
    addFavourite(lastLocateResult);
  }
  syncStarButton();
  if (listMode === "favourites") renderFavouritesList();
});

async function runLocate() {
  const input = document.getElementById("locate-input");
  const btn = document.getElementById("locate-btn");
  const errorEl = document.getElementById("locate-error");
  const resultEl = document.getElementById("locate-result");
  errorEl.classList.remove("visible");
  resultEl.classList.remove("visible");

  const pc = input.value.trim();
  if (!pc) return;

  btn.disabled = true;
  const originalLabel = btn.textContent;
  btn.textContent = "Checking…";

  try {
    const resp = await fetch("/api/postcode?pc=" + encodeURIComponent(pc));
    const body = await resp.json();
    if (!resp.ok) {
      throw new Error(body.detail || "Something went wrong.");
    }
    const color = catColor(body.peak_category);
    showYouMarker(body.lon, body.lat, color);
    map.flyTo({ center: [body.lon, body.lat], zoom: Math.max(map.getZoom(), 9), speed: 0.8 });

    document.getElementById("r-station").textContent = body.label + (body.precise ? "" : " (district centre)");

    const pctEl = document.getElementById("r-pct");
    pctEl.textContent = body.peak_pct.toFixed(1) + "%";
    pctEl.style.color = color;

    const pillEl = document.getElementById("r-cat-pill");
    pillEl.style.borderColor = color;
    pillEl.style.color = color;
    document.getElementById("r-cat-dot").style.background = color;
    document.getElementById("r-cat-text").textContent = body.peak_category;

    document.getElementById("r-peak-date").textContent = formatDate(body.peak_date);
    document.getElementById("r-elev").textContent = body.elevation_m + "m (model grid)";
    document.getElementById("r-coords").textContent = body.lat.toFixed(3) + ", " + body.lon.toFixed(3);

    const nearestRow = document.getElementById("r-nearest-row");
    if (body.nearest_station) {
      nearestRow.style.display = "";
      document.getElementById("r-nearest").textContent = body.nearest_station + " (" + body.nearest_station_km + "km away)";
    } else {
      nearestRow.style.display = "none";
    }

    resultEl.classList.add("visible");

    lastLocateResult = { label: body.label, lat: body.lat, lon: body.lon };
    syncStarButton();
  } catch (err) {
    errorEl.textContent = err.message || "Couldn't check that location.";
    errorEl.classList.add("visible");
  } finally {
    btn.disabled = false;
    btn.textContent = originalLabel;
  }
}

document.getElementById("locate-btn").addEventListener("click", runLocate);
document.getElementById("locate-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter") runLocate();
});
</script>
"""


def HTML_TEMPLATE(live: dict, demo: dict) -> str:
    data = {"live": live, "demo": demo}
    html = _PAGE
    html = html.replace("__DATA_JSON__", json.dumps(data, separators=(",", ":")))
    html = html.replace("__SEA_LEVEL_MAX__", str(SEA_LEVEL_MAX_M))
    html = html.replace("__MOUNTAIN_MIN__", str(MID_MAX_M))
    html = html.replace("__MAX_ELEV__", str(MAX_ELEV_M))
    return html
