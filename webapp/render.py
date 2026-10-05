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



# ---- shared page chrome (Bootstrap 5.3 + the SLM Light/Night/Dark palette) ----

# Applied in <head> so the stored theme is set before first paint (no flash
# of Light before the page script runs). No stored choice -> Dark.
_HEAD = r"""<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<script>
(function () {
  var t = null;
  try { t = localStorage.getItem("snowOutlookTheme"); } catch (e) {}
  if (["light", "night", "dark"].indexOf(t) < 0) t = "dark";
  document.documentElement.dataset.theme = t;
  document.documentElement.dataset.bsTheme = t === "light" ? "light" : "dark";
})();
</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet" integrity="sha384-QWTKZyjpPEjISv5WaRU9OFeRpok6YctnYmDr5pNlyT2bRjXh0JMhjY6hW+ALEwIH" crossorigin="anonymous">
<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css" rel="stylesheet" integrity="sha384-XGjxtQfXaH2tnPFa9x+ruJTuLE3Aa6LhHSWRr1XeTyhezb4abCG4ccI5AkVDxqC+" crossorigin="anonymous">
<style>
  /* Three themes: Light, Night (soft dark blue-grey), Dark (true black, the
     default). data-theme picks the SLM palette; data-bs-theme puts Bootstrap
     in its light/dark mode to match. */
  :root {
    --bg: #f8fafb; --surface: #fdfeff; --ink: #101d28; --ink-secondary: #47616e; --ink-muted: #7f97a2;
    --hairline: #dae5ea; --hairline-strong: #c2d3da; --accent: #104281; --accent-rgb: 16,66,129; --accent-ink: #ffffff;
    --land: #dbe7ec; --land-stroke: #aec2cb;
    --cat-1: #86b6ef; --cat-2: #5598e7; --cat-3: #2a78d6; --cat-4: #1c5cab; --cat-5: #104281;
    --locate-accent: #c9720a;
    --error: #c0392b;
    --shadow: 0 1px 2px rgba(16,29,40,0.04), 0 8px 24px rgba(16,29,40,0.06);
  }
  :root[data-theme="night"] {
    --bg: #0b141c; --surface: #101b24; --ink: #edf4f7; --ink-secondary: #a7bfca; --ink-muted: #6b8493;
    --hairline: #1f2e38; --hairline-strong: #2a3c48; --accent: #86b6ef; --accent-rgb: 134,182,239; --accent-ink: #08131c;
    --land: #16232c; --land-stroke: #26394d;
    --cat-1: #9ec5f4; --cat-2: #6da7ec; --cat-3: #3987e5; --cat-4: #256abf; --cat-5: #184f95;
    --locate-accent: #f0a94e;
    --error: #e0685a;
    --shadow: 0 1px 2px rgba(0,0,0,0.3), 0 12px 28px rgba(0,0,0,0.35);
  }
  :root[data-theme="dark"] {
    --bg: #000000; --surface: #0a0a0a; --ink: #f2f5f7; --ink-secondary: #9fb3bd; --ink-muted: #5f7078;
    --hairline: #161616; --hairline-strong: #262626; --accent: #6fa8e8; --accent-rgb: 111,168,232; --accent-ink: #05090d;
    --land: #0a0a0a; --land-stroke: #1c1c1c;
    --cat-1: #9ec5f4; --cat-2: #6da7ec; --cat-3: #3987e5; --cat-4: #256abf; --cat-5: #184f95;
    --locate-accent: #f0a94e;
    --error: #e0685a;
    --shadow: 0 1px 2px rgba(0,0,0,0.6), 0 12px 28px rgba(0,0,0,0.55);
  }

  /* Point Bootstrap's theme variables at the SLM palette. :root[data-theme]
     outranks Bootstrap's own [data-bs-theme] selectors. */
  :root[data-theme] {
    --bs-font-sans-serif: "Inter", "Segoe UI", system-ui, sans-serif;
    --bs-body-font-family: var(--bs-font-sans-serif);
    --bs-body-bg: var(--bg); --bs-body-color: var(--ink);
    --bs-emphasis-color: var(--ink); --bs-heading-color: var(--ink);
    --bs-secondary-color: var(--ink-secondary); --bs-tertiary-color: var(--ink-muted);
    --bs-secondary-bg: var(--hairline); --bs-tertiary-bg: var(--surface);
    --bs-border-color: var(--hairline-strong); --bs-border-color-translucent: var(--hairline);
    --bs-primary: var(--accent); --bs-primary-rgb: var(--accent-rgb);
    --bs-link-color: var(--accent); --bs-link-color-rgb: var(--accent-rgb);
    --bs-link-hover-color: var(--accent); --bs-link-hover-color-rgb: var(--accent-rgb);
    --bs-focus-ring-color: rgba(var(--accent-rgb), 0.35);
  }
  html, body { background: var(--bg); }
  body { -webkit-font-smoothing: antialiased; }
  .min-w-0 { min-width: 0; }

  .navbar-slm { background: var(--surface); border-bottom: 1px solid var(--hairline); }
  .navbar-slm .navbar-brand { color: var(--ink); font-weight: 600; font-size: 1rem; }
  .brand-mark {
    width: 30px; height: 30px; border-radius: 8px; display: inline-flex; align-items: center; justify-content: center;
    background: var(--accent); color: var(--accent-ink); font-size: 16px;
  }

  .eyebrow {
    font-size: 11px; letter-spacing: 0.1em; font-weight: 600; text-transform: uppercase;
    color: var(--ink-muted); display: inline-flex; align-items: center; gap: 8px;
  }
  .eyebrow.accent { color: var(--accent); }

  .card {
    --bs-card-bg: var(--surface); --bs-card-border-color: var(--hairline); --bs-card-cap-bg: transparent;
    --bs-card-border-radius: 14px; --bs-card-inner-border-radius: 13px; box-shadow: var(--shadow);
  }
  .card-header, .card-footer { border-color: var(--hairline); }

  .btn-accent {
    --bs-btn-bg: var(--accent); --bs-btn-color: var(--accent-ink); --bs-btn-border-color: var(--accent);
    --bs-btn-hover-bg: var(--accent); --bs-btn-hover-color: var(--accent-ink); --bs-btn-hover-border-color: var(--accent);
    --bs-btn-active-bg: var(--accent); --bs-btn-active-color: var(--accent-ink); --bs-btn-active-border-color: var(--accent);
    --bs-btn-disabled-bg: var(--accent); --bs-btn-disabled-color: var(--accent-ink); --bs-btn-disabled-border-color: var(--accent);
    --bs-btn-focus-shadow-rgb: var(--accent-rgb);
  }
  .btn-accent:hover { filter: brightness(1.08); }
  /* Segmented / toggle buttons: muted outline, accent fill when .active. */
  .btn-seg {
    --bs-btn-color: var(--ink-secondary); --bs-btn-bg: var(--surface); --bs-btn-border-color: var(--hairline-strong);
    --bs-btn-hover-color: var(--ink); --bs-btn-hover-bg: var(--hairline); --bs-btn-hover-border-color: var(--hairline-strong);
    --bs-btn-active-color: var(--accent-ink); --bs-btn-active-bg: var(--accent); --bs-btn-active-border-color: var(--accent);
    --bs-btn-focus-shadow-rgb: var(--accent-rgb);
  }
  .btn-seg.show { color: var(--ink); background: var(--hairline); border-color: var(--hairline-strong); }

  .dropdown-menu {
    --bs-dropdown-bg: var(--surface); --bs-dropdown-border-color: var(--hairline-strong);
    --bs-dropdown-link-color: var(--ink-secondary); --bs-dropdown-link-hover-color: var(--ink); --bs-dropdown-link-hover-bg: var(--hairline);
    --bs-dropdown-link-active-color: var(--accent-ink); --bs-dropdown-link-active-bg: var(--accent);
    box-shadow: var(--shadow);
  }

  .form-control { background-color: var(--bg); }
  .form-control:focus {
    background-color: var(--bg); color: var(--ink); border-color: var(--accent);
    box-shadow: 0 0 0 0.2rem rgba(var(--accent-rgb), 0.25);
  }
  .form-control::placeholder { color: var(--ink-muted); }

  .site-footer { border-top: 1px solid var(--hairline); color: var(--ink-muted); font-size: 12.5px; line-height: 1.7; }
  .site-footer strong { color: var(--ink-secondary); }
  .site-footer a { color: var(--ink-secondary); }
</style>"""

_NAVBAR = r"""<nav class="navbar navbar-slm sticky-top">
  <div class="container-xl">
    <a class="navbar-brand d-flex align-items-center gap-2" href="/">
      <span class="brand-mark"><i class="bi bi-snow2"></i></span>
      <span>SLM <span class="d-none d-sm-inline fw-normal text-body-secondary">&middot; Snow Likelihood Model</span></span>
    </a>
    <div class="d-flex align-items-center gap-2">
      <a class="btn btn-sm btn-seg __FAQ_ACTIVE__" href="/faq"><i class="bi bi-question-circle"></i><span class="d-none d-sm-inline ms-1">FAQ</span></a>
      <div class="dropdown">
        <button class="btn btn-sm btn-seg dropdown-toggle" type="button" data-bs-toggle="dropdown" aria-expanded="false" aria-label="Theme">
          <i class="bi" id="theme-icon"></i><span class="d-none d-sm-inline ms-1" id="theme-label"></span>
        </button>
        <ul class="dropdown-menu dropdown-menu-end">
          <li><button class="dropdown-item" type="button" id="theme-toggle-light"><i class="bi bi-sun me-2"></i>Light</button></li>
          <li><button class="dropdown-item" type="button" id="theme-toggle-night"><i class="bi bi-moon-stars me-2"></i>Night</button></li>
          <li><button class="dropdown-item" type="button" id="theme-toggle-dark"><i class="bi bi-moon-fill me-2"></i>Dark</button></li>
        </ul>
      </div>
    </div>
  </div>
</nav>"""

# Bootstrap's JS (dropdown, collapse, tabs) plus the navbar theme menu. Pages
# that need to react to a theme change (the map swapping its tile style)
# listen for the "slm:themechange" event.
_THEME_JS = r"""<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js" integrity="sha384-YvpcrYf0tY3lHB60NNkmXc5s9fDVZLESaAA55NDzOxhy9GkcIdslK1eN7N6jIeHz" crossorigin="anonymous"></script>
<script>
const THEME_KEY = "snowOutlookTheme";
const THEMES = {
  light: { icon: "bi-sun", label: "Light" },
  night: { icon: "bi-moon-stars", label: "Night" },
  dark: { icon: "bi-moon-fill", label: "Dark" },
};
let currentTheme = document.documentElement.dataset.theme;

function syncThemeMenu() {
  Object.keys(THEMES).forEach(t => {
    const el = document.getElementById("theme-toggle-" + t);
    el.classList.toggle("active", t === currentTheme);
    el.setAttribute("aria-current", String(t === currentTheme));
  });
  document.getElementById("theme-icon").className = "bi " + THEMES[currentTheme].icon;
  document.getElementById("theme-label").textContent = THEMES[currentTheme].label;
}
function setTheme(theme) {
  currentTheme = theme;
  document.documentElement.dataset.theme = theme;
  document.documentElement.dataset.bsTheme = theme === "light" ? "light" : "dark";
  try { localStorage.setItem(THEME_KEY, theme); } catch { /* ignore */ }
  syncThemeMenu();
  document.dispatchEvent(new CustomEvent("slm:themechange", { detail: theme }));
}
Object.keys(THEMES).forEach(t => document.getElementById("theme-toggle-" + t).addEventListener("click", () => setTheme(t)));
syncThemeMenu();
</script>"""


def _shell(page: str, faq_active: bool = False) -> str:
    return (page
            .replace("__HEAD__", _HEAD)
            .replace("__NAVBAR__", _NAVBAR.replace("__FAQ_ACTIVE__", "active" if faq_active else ""))
            .replace("__THEME_JS__", _THEME_JS))


_PAGE = r"""<!doctype html>
<html lang="en">
<head>
<title>Snow Watch SLM</title>
__HEAD__
<link href="https://unpkg.com/maplibre-gl@4/dist/maplibre-gl.css" rel="stylesheet">
<script src="https://unpkg.com/maplibre-gl@4/dist/maplibre-gl.js"></script>
<style>
  .hero-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--accent); flex: none; }
  .hero-sub { color: var(--ink-secondary); font-size: 15px; max-width: 56ch; }
  @media (max-width: 575.98px) {
    .hero-controls { width: 100%; }
    .hero-controls .btn-group { width: 100%; }
    .hero-controls .btn-group .btn { flex: 1; }
  }

  .scenario-banner { display: none; align-items: center; gap: 10px; font-size: 13px; }
  .scenario-banner.visible { display: flex; }
  .scenario-banner .tag {
    font-size: 10px; letter-spacing: 0.08em; text-transform: uppercase; font-weight: 600;
    background: var(--cat-4); color: #fff; padding: 3px 8px; border-radius: 5px; flex: none;
  }
  .scenario-banner {
    background: var(--surface); color: var(--ink-secondary);
    border: 1px dashed var(--hairline-strong); border-radius: 10px; padding: 10px 14px;
  }

  .locate-error { display: none; }
  .locate-error.visible { display: block; }
  .locate-result { display: none; margin-top: 16px; padding-top: 16px; border-top: 1px solid var(--hairline); }
  .locate-result.visible { display: block; }
  .r-pct { font-variant-numeric: tabular-nums; font-size: 38px; font-weight: 700; line-height: 1; }
  .cat-badge {
    display: inline-flex; align-items: center; gap: 6px; font-size: 12.5px; font-weight: 600;
    padding: 4px 11px; border-radius: 999px; border: 1.5px solid var(--hairline-strong);
  }
  .r-details { display: grid; grid-template-columns: 1fr 1fr; gap: 10px 16px; }
  .r-details dt { font-size: 10px; letter-spacing: 0.07em; text-transform: uppercase; color: var(--ink-muted); font-weight: 500; }
  .r-details dd { font-size: 13px; color: var(--ink-secondary); margin: 0; }
  .r-details #r-nearest-row { grid-column: 1 / -1; }

  .star-btn {
    font-size: 18px; line-height: 1; background: none; border: none; cursor: pointer;
    color: var(--ink-muted); padding: 2px; flex: none; transition: color 120ms ease, transform 120ms ease;
  }
  .star-btn:hover { color: var(--locate-accent); transform: scale(1.1); }
  .star-btn.starred { color: var(--locate-accent); }

  .panel-toggle {
    display: flex; align-items: center; gap: 8px; background: none; border: none; padding: 2px;
    margin: -2px; border-radius: 6px; width: 100%; text-align: left;
  }
  .panel-toggle:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
  .panel-toggle .chevron { font-size: 11px; color: var(--ink-muted); transition: transform 150ms ease; }
  .panel-toggle[aria-expanded="false"] .chevron { transform: rotate(-90deg); }

  .station-list {
    --bs-list-group-bg: transparent; --bs-list-group-border-color: var(--hairline); --bs-list-group-color: var(--ink);
    --bs-list-group-action-hover-bg: var(--hairline); --bs-list-group-action-hover-color: var(--ink);
    --bs-list-group-action-active-bg: var(--hairline); --bs-list-group-action-active-color: var(--ink);
    max-height: 360px; overflow-y: auto; scrollbar-width: thin;
  }
  .station-name { font-size: 13.5px; font-weight: 500; }
  .station-region { font-size: 11.5px; color: var(--ink-muted); }
  .station-pct { font-variant-numeric: tabular-nums; font-size: 15px; font-weight: 600; flex: none; }
  .chip { display: inline-block; width: 8px; height: 8px; border-radius: 50%; flex: none; }

  .map-card .map-body { flex: 1 1 auto; display: flex; padding: 10px; }
  #map { flex: 1; width: 100%; min-height: 560px; border-radius: 10px; overflow: hidden; background: var(--land); }
  @media (max-width: 575.98px) { #map { min-height: 420px; } .map-card .map-body { padding: 6px; } }

  .maplibregl-popup-content {
    background: var(--surface); color: var(--ink); font-family: "Inter", sans-serif; font-size: 12px;
    padding: 9px 11px; border-radius: 9px; border: 1px solid var(--hairline-strong);
    box-shadow: var(--shadow); line-height: 1.5;
  }
  .maplibregl-popup-tip { border-top-color: var(--surface) !important; border-bottom-color: var(--surface) !important; }
  .mm-name { font-weight: 600; display: block; margin-bottom: 2px; }
  .mm-meta { font-size: 11px; color: var(--ink-secondary); }
  .mm-days { display: flex; gap: 8px; margin-top: 6px; padding-top: 6px; border-top: 1px solid var(--hairline); }
  .mm-day { display: flex; flex-direction: column; align-items: center; gap: 2px; }
  .mm-day-label { font-size: 9px; letter-spacing: 0.03em; text-transform: uppercase; opacity: 0.7; }
  .mm-day-pct { font-size: 11px; font-weight: 600; }

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

  .legend, .legend-shapes { display: flex; align-items: center; flex-wrap: wrap; gap: 8px 16px; font-size: 12px; color: var(--ink-secondary); }
  .legend { margin-bottom: 10px; }
  .legend-item, .shape-item { display: flex; align-items: center; gap: 6px; }
  .legend-swatch { width: 12px; height: 12px; border-radius: 50%; flex: none; }
  .shape-swatch { display: inline-block; width: 12px; height: 12px; flex: none; background: var(--ink-muted); }
  .shape-swatch.mountain { clip-path: polygon(0% 100%, 33% 20%, 46% 55%, 63% 5%, 100% 100%); opacity: 0.7; }
  .shape-swatch.triangle { clip-path: polygon(50% 0%, 100% 100%, 0% 100%); }
  .shape-swatch.diamond { transform: rotate(45deg) scale(0.85); }
  .shape-swatch.star { background: var(--locate-accent); clip-path: polygon(50% 0%, 61% 35%, 98% 35%, 68% 57%, 79% 91%, 50% 70%, 21% 91%, 32% 57%, 2% 35%, 39% 35%); }

  .nav-underline { --bs-nav-link-color: var(--ink-secondary); --bs-nav-link-hover-color: var(--ink); --bs-nav-underline-link-active-color: var(--ink); font-size: 13.5px; }
  .nav-underline .nav-link { display: inline-flex; align-items: center; gap: 7px; }
  .data-table { --bs-table-bg: transparent; --bs-table-color: var(--ink); --bs-table-border-color: var(--hairline); --bs-table-hover-bg: var(--hairline); --bs-table-hover-color: var(--ink); font-size: 13px; }
  .data-table th {
    font-size: 10.5px; letter-spacing: 0.06em; text-transform: uppercase; color: var(--ink-muted);
    font-weight: 500; white-space: nowrap; border-bottom-color: var(--hairline-strong);
  }
  .data-table td { white-space: nowrap; padding-top: 10px; padding-bottom: 10px; }
  .data-table th:first-child, .data-table td:first-child { padding-left: 1rem; }
  .data-table th:last-child, .data-table td:last-child { padding-right: 1rem; }
  .data-table td.num { font-variant-numeric: tabular-nums; text-align: right; }
  .data-table tr:last-child td { border-bottom: none; }
  .cat-pill { display: inline-flex; align-items: center; gap: 6px; font-size: 11.5px; }
</style>
</head>
<body>
__NAVBAR__

<main class="container-xl py-4">
  <div class="d-flex flex-wrap align-items-end justify-content-between gap-3 mb-4">
    <div>
      <div class="eyebrow mb-2"><span class="hero-dot"></span>UK snow outlook &middot; next 4 days</div>
      <h1 class="h3 fw-semibold mb-2" style="letter-spacing:-0.01em">Snow likelihood across the UK</h1>
      <p class="hero-sub mb-0">Blended synoptic + ensemble snow-likelihood across thirty-nine UK stations, from mountain summits through mid-elevation uplands to sea level.</p>
    </div>
    <div class="hero-controls d-flex flex-column align-items-stretch align-items-sm-end gap-2">
      <div class="btn-group btn-group-sm" role="group" aria-label="Data source">
        <button class="btn btn-seg active" id="btn-live" type="button"><i class="bi bi-broadcast me-1"></i>Live forecast</button>
        <button class="btn btn-seg" id="btn-demo" type="button"><i class="bi bi-easel me-1"></i>Example scenario</button>
      </div>
      <div class="small text-body-tertiary" id="meta-line">Generated <strong>-</strong></div>
    </div>
  </div>

  <div class="scenario-banner mb-4" id="scenario-banner">
    <span class="tag">Illustrative</span>
    <span>This is a fabricated cold-snap scenario used to show the full likelihood range - not a real forecast.</span>
  </div>

  <div class="row g-4">
    <div class="col-lg-4 d-flex flex-column gap-4">
      <section class="card">
        <div class="card-body">
          <div class="eyebrow accent mb-1"><i class="bi bi-geo-alt-fill"></i>Check your exact location</div>
          <p class="small text-body-tertiary mb-3">Runs the live model for your real coordinates - not borrowed from the nearest station.</p>
          <form class="d-flex flex-column gap-2" id="locate-form">
            <input class="form-control" id="locate-input" type="text" placeholder="UK postcode, e.g. EH1 or SW1A 1AA" autocomplete="off" autocapitalize="characters" aria-label="UK postcode">
            <button class="btn btn-accent fw-semibold" id="locate-btn" type="submit">Check likelihood</button>
          </form>
          <div class="locate-error alert alert-danger small py-2 px-3 mt-3 mb-0" id="locate-error" role="alert"></div>
          <div class="locate-result" id="locate-result">
            <div class="d-flex align-items-center gap-2 mb-3">
              <button class="star-btn" id="r-star" type="button" title="Save to favourites" aria-pressed="false"><i class="bi bi-star"></i></button>
              <div class="fw-semibold text-truncate" id="r-station"></div>
            </div>
            <div class="d-flex align-items-center flex-wrap gap-3 mb-3">
              <span class="r-pct" id="r-pct"></span>
              <span class="cat-badge" id="r-cat-pill"><span class="chip" id="r-cat-dot"></span><span id="r-cat-text"></span></span>
            </div>
            <dl class="r-details mb-0">
              <div><dt>Peak day</dt><dd id="r-peak-date"></dd></div>
              <div><dt>Elevation</dt><dd id="r-elev"></dd></div>
              <div id="r-nearest-row"><dt>Nearest station</dt><dd id="r-nearest"></dd></div>
            </dl>
          </div>
        </div>
      </section>

      <section class="card" id="stations-panel">
        <div class="card-header py-3">
          <button class="panel-toggle" id="panel-collapse-btn" type="button" data-bs-toggle="collapse" data-bs-target="#panel-body" aria-expanded="false" aria-controls="panel-body">
            <i class="bi bi-chevron-down chevron"></i><span class="eyebrow">Reference stations</span>
          </button>
        </div>
        <div class="collapse" id="panel-body">
          <div class="card-body">
            <div class="btn-group btn-group-sm w-100 mb-3" role="group" aria-label="Elevation band">
              <button class="btn btn-seg active" id="elev-toggle-mountain" type="button" title="__MOUNTAIN_MIN__&ndash;__MAX_ELEV__m">Mountain</button>
              <button class="btn btn-seg" id="elev-toggle-mid" type="button" title="201&ndash;500m">Upland</button>
              <button class="btn btn-seg" id="elev-toggle-sea" type="button" title="&lt; __SEA_LEVEL_MAX__m">Lowland</button>
              <button class="btn btn-seg flex-grow-0" id="elev-toggle-favourites" type="button" title="Favourites" aria-label="Favourites"><i class="bi bi-star-fill"></i></button>
            </div>
            <div id="station-list" class="list-group station-list"></div>
          </div>
        </div>
      </section>
    </div>

    <div class="col-lg-8">
      <section class="card map-card h-100 d-flex flex-column">
        <div class="map-body"><div id="map"></div></div>
        <div class="card-footer py-3">
          <div class="legend">
            <span class="eyebrow">Peak likelihood</span>
            <div class="legend-item"><span class="legend-swatch" style="background:var(--cat-1)"></span>Very low</div>
            <div class="legend-item"><span class="legend-swatch" style="background:var(--cat-2)"></span>Low</div>
            <div class="legend-item"><span class="legend-swatch" style="background:var(--cat-3)"></span>Moderate</div>
            <div class="legend-item"><span class="legend-swatch" style="background:var(--cat-4)"></span>High</div>
            <div class="legend-item"><span class="legend-swatch" style="background:var(--cat-5)"></span>Very high</div>
          </div>
          <div class="legend-shapes">
            <div class="shape-item"><span class="shape-swatch mountain"></span>Mountain &amp; summit (__MOUNTAIN_MIN__&ndash;__MAX_ELEV__m)</div>
            <div class="shape-item"><span class="shape-swatch triangle"></span>Mid-elevation &amp; upland (201&ndash;500m)</div>
            <div class="shape-item"><span class="shape-swatch diamond"></span>Sea level &amp; lowland (&lt; __SEA_LEVEL_MAX__m)</div>
            <div class="shape-item"><span class="shape-swatch star"></span>Your checked location</div>
          </div>
        </div>
      </section>
    </div>

    <div class="col-12">
      <section class="card">
        <div class="card-header pt-3 pb-0">
          <span class="eyebrow">All stations</span>
          <ul class="nav nav-underline mt-2" role="tablist">
            <li class="nav-item" role="presentation">
              <button class="nav-link active" data-bs-toggle="tab" data-bs-target="#tab-mountain" type="button" role="tab" aria-controls="tab-mountain" aria-selected="true">
                <span class="shape-swatch mountain"></span>Mountains<span class="d-none d-md-inline text-body-tertiary">&amp; summits (__MOUNTAIN_MIN__&ndash;__MAX_ELEV__m)</span>
              </button>
            </li>
            <li class="nav-item" role="presentation">
              <button class="nav-link" data-bs-toggle="tab" data-bs-target="#tab-mid" type="button" role="tab" aria-controls="tab-mid" aria-selected="false">
                <span class="shape-swatch triangle"></span>Upland<span class="d-none d-md-inline text-body-tertiary">(201&ndash;500m)</span>
              </button>
            </li>
            <li class="nav-item" role="presentation">
              <button class="nav-link" data-bs-toggle="tab" data-bs-target="#tab-sea" type="button" role="tab" aria-controls="tab-sea" aria-selected="false">
                <span class="shape-swatch diamond"></span>Lowland<span class="d-none d-md-inline text-body-tertiary">(&lt; __SEA_LEVEL_MAX__m)</span>
              </button>
            </li>
          </ul>
        </div>
        <div class="tab-content">
          <div class="tab-pane fade show active" id="tab-mountain" role="tabpanel">
            <div class="table-responsive">
              <table class="table table-hover align-middle mb-0 data-table">
                <thead><tr><th>Station</th><th>Region</th><th class="text-end">Elev.</th><th>Peak day</th><th class="text-end">Peak %</th><th>Category</th></tr></thead>
                <tbody id="table-body-mountain"></tbody>
              </table>
            </div>
          </div>
          <div class="tab-pane fade" id="tab-mid" role="tabpanel">
            <div class="table-responsive">
              <table class="table table-hover align-middle mb-0 data-table">
                <thead><tr><th>Station</th><th>Region</th><th class="text-end">Elev.</th><th>Peak day</th><th class="text-end">Peak %</th><th>Category</th></tr></thead>
                <tbody id="table-body-mid"></tbody>
              </table>
            </div>
          </div>
          <div class="tab-pane fade" id="tab-sea" role="tabpanel">
            <div class="table-responsive">
              <table class="table table-hover align-middle mb-0 data-table">
                <thead><tr><th>Station</th><th>Region</th><th class="text-end">Elev.</th><th>Peak day</th><th class="text-end">Peak %</th><th>Category</th></tr></thead>
                <tbody id="table-body-sea"></tbody>
              </table>
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>

  <footer class="site-footer mt-5 pt-4">
    <strong>Method:</strong> each point blends a synoptic rules-based score (thickness, freezing level, wet-bulb proxy) with multi-model ensemble agreement (UK Met Office, DWD ICON, NOAA GFS, ECMWF), 40/60 weighted, via the open-source <strong>SLM</strong> (Snow Likelihood Model). Weather data from <a href="https://open-meteo.com">Open-Meteo</a>, postcode geocoding from <a href="https://postcodes.io">postcodes.io</a>.<br>
    This is an independent hobby forecast, not an official warning service - it is not a substitute for Met Office, SAIS, or mountain safety advice.
  </footer>
</main>

__THEME_JS__
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

// Full postcodes resolve to an exact point, so showing the postcode back
// verbatim would reveal it in a screenshot/screen-share -- mask the inward
// code (the part after the space) with asterisks. Outward-code-only
// lookups ("EH1") aren't precise enough to identify an address, so those
// are shown in full.
function maskPostcode(label, precise) {
  if (!precise) return label;
  const parts = label.split(" ");
  if (parts.length >= 2) return parts.slice(0, -1).join(" ") + " ***";
  return label.length > 3 ? label.slice(0, -3) + "***" : "***";
}

const WEEKDAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
function formatDayShort(value) {
  if (!value) return "";
  const m = value.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!m) return value;
  const [, y, mo, d] = m;
  return WEEKDAY_NAMES[new Date(Date.UTC(+y, +mo - 1, +d)).getUTCDay()];
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
        days: JSON.stringify(loc.days || []),
      },
    })),
  };
}

function popupHTML(p) {
  let daysHTML = "";
  try {
    const days = typeof p.days === "string" ? JSON.parse(p.days) : (p.days || []);
    if (days.length) {
      daysHTML = '<div class="mm-days">' + days.map(d =>
        '<div class="mm-day"><span class="mm-day-label">' + formatDayShort(d.date) + '</span>' +
        '<span class="mm-day-pct" style="color:' + catColor(d.category) + '">' + Math.round(d.peak_pct) + '%</span></div>'
      ).join("") + '</div>';
    }
  } catch { /* no daily breakdown available */ }
  return '<span class="mm-name">' + p.name + '</span>' +
    '<span class="mm-meta">' + p.region + ' &middot; ' + p.elev + 'm</span><br>' +
    '<span class="mm-meta">peak ' + p.peak_pct.toFixed(1) + '% &middot; ' + p.peak_category + ' &middot; ' + formatDate(p.peak_date) + '</span>' +
    daysHTML;
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

// 20x20 SDF triangle, tintable per-feature via icon-color.
function makeTriangleSDF() {
  const c = document.createElement("canvas");
  c.width = 20; c.height = 20;
  const ctx = c.getContext("2d");
  ctx.fillStyle = "#fff";
  ctx.beginPath();
  ctx.moveTo(10, 1); ctx.lineTo(19, 18); ctx.lineTo(1, 18);
  ctx.closePath(); ctx.fill();
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

// Shetland has no reference station of its own, so its coordinates are
// folded into the extent below to keep it in the default UK view.
const SHETLAND_BOUNDS = { lat: [59.9, 60.9], lon: [-1.7, -0.7] };

const UK_BOUNDS = (() => {
  const lats = [...DATA.live.locations.map(l => l.lat), ...SHETLAND_BOUNDS.lat];
  const lons = [...DATA.live.locations.map(l => l.lon), ...SHETLAND_BOUNDS.lon];
  return [[Math.min(...lons) - 0.8, Math.min(...lats) - 0.5], [Math.max(...lons) + 0.8, Math.max(...lats) + 0.5]];
})();

// Theme state (currentTheme) and the navbar menu live in the shared
// _THEME_JS block; the head snippet defaults new visitors to Dark.
function mapStyleUrl() {
  return "https://tiles.openfreemap.org/styles/" + (currentTheme === "light" ? "positron" : "dark");
}

const map = new maplibregl.Map({
  container: "map",
  style: mapStyleUrl(),
  bounds: UK_BOUNDS,
  fitBoundsOptions: { padding: 20 },
  attributionControl: false,
  cooperativeGestures: true,
});
// bounds fitting above runs synchronously (duration: 0), so the zoom it
// lands on is available immediately -- use it as the zoomed-out limit so
// visitors can zoom in from the full-UK view but never past it.
map.setMinZoom(map.getZoom());
map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
map.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-right");
// MapLibre's compact attribution starts expanded and only collapses to the
// small icon after the map's first drag (it's bound to the "drag" event
// internally). It also (re)opens once the style's sources report their
// attribution, so collapse it now and again when the map first goes idle.
function collapseAttribution() {
  map.getContainer().querySelectorAll(".maplibregl-ctrl-attrib.maplibregl-compact-show").forEach(el => {
    el.classList.remove("maplibregl-compact-show");
    el.removeAttribute("open");
  });
}
collapseAttribution();
map.once("idle", collapseAttribution);

// The map card stretches with the sidebar beside it, so follow container
// size changes, not just window resizes.
new ResizeObserver(() => map.resize()).observe(map.getContainer());

document.addEventListener("slm:themechange", () => {
  // diff:false forces a full style reload (and a fresh "style.load" event) --
  // MapLibre's default diff-based update strips our runtime-added
  // sources/layers/images (they're not part of either base style's JSON)
  // without ever re-firing "style.load" to let us re-add them.
  map.setStyle(mapStyleUrl(), { diff: false });
});

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

const STATION_ROW_CLASS = "list-group-item d-flex align-items-center gap-2";
const STAR_FILLED = '<i class="bi bi-star-fill"></i>';
const STAR_EMPTY = '<i class="bi bi-star"></i>';

function stationRowHTML(name, region, pct, cat) {
  return '<span class="chip" style="background:' + catColor(cat) + '"></span>' +
    '<div class="flex-grow-1 min-w-0"><div class="station-name text-truncate">' + name + '</div>' +
    '<div class="station-region text-truncate">' + region + '</div></div>' +
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
      row.className = STATION_ROW_CLASS;
      row.innerHTML = stationRowHTML(loc.name, loc.region, loc.peak_pct, loc.peak_category);
      list.appendChild(row);
    });
}

async function renderFavouritesList() {
  const list = document.getElementById("station-list");
  const favs = getFavourites();
  if (favs.length === 0) {
    list.innerHTML = '<div class="list-group-item station-region">No saved locations yet - search a postcode above and tap ' + STAR_EMPTY + ' to save it here.</div>';
    return;
  }
  list.innerHTML = favs.map(f => '<div class="list-group-item station-region"><span class="spinner-border spinner-border-sm me-2"></span>' + f.label + '&hellip;</div>').join("");

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
    row.className = STATION_ROW_CLASS;
    const removeBtn = '<button class="star-btn starred" type="button" title="Remove favourite">' + STAR_FILLED + '</button>';
    if (error || !body) {
      row.innerHTML = '<div class="flex-grow-1 min-w-0"><div class="station-name text-truncate">' + fav.label + '</div>' +
        '<div class="station-region">Couldn\'t load</div></div>' + removeBtn;
    } else {
      row.innerHTML = stationRowHTML(body.label, body.elevation_m + "m", body.peak_pct, body.peak_category) + removeBtn;
      row.classList.add("list-group-item-action");
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
const panelBody = document.getElementById("panel-body");
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
// Bootstrap's collapse plugin does the toggling; set the remembered state
// before first interaction and persist whatever the visitor picks.
if (!getStoredCollapse()) {
  panelBody.classList.add("show");
  panelCollapseBtn.setAttribute("aria-expanded", "true");
}
panelBody.addEventListener("shown.bs.collapse", () => setStoredCollapse(false));
panelBody.addEventListener("hidden.bs.collapse", () => setStoredCollapse(true));

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
  if (!map.hasImage("triangle-sdf")) map.addImage("triangle-sdf", makeTriangleSDF(), { sdf: true });
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
      layout: { "icon-image": "triangle-sdf", "icon-size": ["/", ["get", "radius"], 8], "icon-allow-overlap": true },
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
  starBtn.innerHTML = starred ? STAR_FILLED : STAR_EMPTY;
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
  const originalLabel = btn.innerHTML;
  btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>Checking…';

  try {
    const resp = await fetch("/api/postcode?pc=" + encodeURIComponent(pc));
    const body = await resp.json();
    if (!resp.ok) {
      throw new Error(body.detail || "Something went wrong.");
    }
    const color = catColor(body.peak_category);
    showYouMarker(body.lon, body.lat, color);
    map.flyTo({ center: [body.lon, body.lat], zoom: Math.max(map.getZoom(), 9), speed: 0.8 });

    document.getElementById("r-station").textContent = maskPostcode(body.label, body.precise) + (body.precise ? "" : " (district centre)");

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

    const nearestRow = document.getElementById("r-nearest-row");
    if (body.nearest_station) {
      nearestRow.style.display = "";
      document.getElementById("r-nearest").textContent = body.nearest_station + " (" + body.nearest_station_km + "km away)";
    } else {
      nearestRow.style.display = "none";
    }

    resultEl.classList.add("visible");

    lastLocateResult = { label: maskPostcode(body.label, body.precise), lat: body.lat, lon: body.lon };
    syncStarButton();
    // Clear the typed postcode once the search is done so it doesn't sit
    // visible in the field -- the masked result above is what stays on screen.
    input.value = "";
  } catch (err) {
    errorEl.textContent = err.message || "Couldn't check that location.";
    errorEl.classList.add("visible");
  } finally {
    btn.disabled = false;
    btn.innerHTML = originalLabel;
  }
}

document.getElementById("locate-form").addEventListener("submit", (e) => {
  e.preventDefault();
  runLocate();
});
</script>
</body>
</html>
"""

_FAQ_ITEMS = [
    ("Why does a station show a date days from now instead of today?",
     "Each station's headline number is the <strong>peak day within the forecast "
     "window</strong> (currently the next 4 days), not necessarily today. If "
     "conditions are forecast to get colder or wetter later in that window, the "
     "peak date shown will be a few days out rather than today &ndash; that's the "
     "model reporting when the best chance of snow actually falls, not an error."),
    ("What do the percentage and category mean?",
     "The percentage is a blended likelihood score: a synoptic rules-based score "
     "(thickness, freezing level, wet-bulb proxy) combined 40/60 with multi-model "
     "ensemble agreement (UK Met Office, DWD ICON, NOAA GFS, ECMWF). It maps to a "
     "category &ndash; Very low (&lt;10%), Low (10&ndash;29%), Moderate "
     "(30&ndash;54%), High (55&ndash;74%), Very high (75%+)."),
    ("What do the daily figures in a station's popup mean?",
     "Clicking a station shows its peak summary plus one figure per forecast day, "
     "so you can see the trend across the window rather than just the single "
     "best day."),
    ("What do the different marker shapes mean?",
     "Shape encodes elevation band: a mountain silhouette for summits, a triangle "
     "for mid-elevation and upland stations (201&ndash;500m), and a diamond for "
     "sea level and lowland stations. A pulsing star marks a location you've "
     "checked by postcode."),
    ("What's the difference between \"Live forecast\" and \"Example scenario\"?",
     "Live forecast pulls real, current data from Open-Meteo for every station. "
     "Example scenario is a fixed demo snapshot (dated 13 January 2026) kept "
     "around for trying out the interface without waiting on live data."),
    ("How often is the live data refreshed?",
     "The station snapshot refreshes automatically in the background roughly "
     "every 30 minutes."),
    ("Why can't I see snow risk beyond a few days out?",
     "Weather forecast skill drops off quickly past a few days, so SLM limits "
     "itself to a short, more reliable window rather than projecting further "
     "out with false confidence."),
    ("How do I zoom or scroll the map?",
     "Hold Ctrl (or &#8984; on Mac) while scrolling to zoom, or use the +/- "
     "controls &ndash; this stops an accidental scroll while reading the page "
     "from hijacking it. The map is also capped so you can zoom in but never "
     "scroll out past the default UK view."),
    ("Is this an official warning service?",
     "No. SLM is an independent hobby forecast, not an official warning "
     "service &ndash; it is not a substitute for Met Office, SAIS, or mountain "
     "safety advice."),
    ("Where does the data come from?",
     "Weather data from <a href=\"https://open-meteo.com\">Open-Meteo</a>, "
     "postcode geocoding from <a href=\"https://postcodes.io\">postcodes.io</a>."),
]

_FAQ_PAGE = r"""<!doctype html>
<html lang="en">
<head>
<title>FAQ &middot; Snow Watch SLM</title>
__HEAD__
<style>
  .faq-sub { color: var(--ink-secondary); font-size: 15px; }
  .accordion {
    --bs-accordion-bg: var(--surface); --bs-accordion-color: var(--ink-secondary);
    --bs-accordion-border-color: var(--hairline); --bs-accordion-border-radius: 14px; --bs-accordion-inner-border-radius: 13px;
    --bs-accordion-btn-color: var(--ink); --bs-accordion-btn-bg: var(--surface);
    --bs-accordion-active-color: var(--ink); --bs-accordion-active-bg: rgba(var(--accent-rgb), 0.08);
    --bs-accordion-btn-focus-box-shadow: 0 0 0 0.2rem rgba(var(--accent-rgb), 0.25);
    box-shadow: var(--shadow); border-radius: 14px;
  }
  .accordion-button { font-weight: 600; font-size: 14.5px; }
  .accordion-body { font-size: 13.5px; line-height: 1.65; }
</style>
</head>
<body>
__NAVBAR__

<main class="container py-4" style="max-width: 800px">
  <a class="small text-decoration-none" href="/"><i class="bi bi-arrow-left me-1"></i>Back to the map</a>
  <h1 class="h3 fw-semibold mt-3 mb-2" style="letter-spacing:-0.01em">FAQ</h1>
  <p class="faq-sub mb-4">How to read the Snow Likelihood Model map and numbers.</p>

  <div class="accordion" id="faq">
__FAQ_ITEMS__
  </div>

  <footer class="site-footer mt-5 pt-4">
    Still have a question that's not answered here? The map itself has a <strong>Method</strong> note in its
    own footer with more detail on how the score is calculated.
  </footer>
</main>

__THEME_JS__
</body>
</html>
"""


def render_faq() -> str:
    items_html = "\n".join(
        '    <div class="accordion-item">'
        '<h2 class="accordion-header"><button class="accordion-button' + ('' if i == 0 else ' collapsed') + '" type="button" '
        'data-bs-toggle="collapse" data-bs-target="#faq-' + str(i) + '" aria-expanded="' + ('true' if i == 0 else 'false') + '" '
        'aria-controls="faq-' + str(i) + '">' + q + '</button></h2>'
        '<div id="faq-' + str(i) + '" class="accordion-collapse collapse' + (' show' if i == 0 else '') + '">'
        '<div class="accordion-body">' + a + '</div></div></div>'
        for i, (q, a) in enumerate(_FAQ_ITEMS)
    )
    return _shell(_FAQ_PAGE, faq_active=True).replace("__FAQ_ITEMS__", items_html)


def HTML_TEMPLATE(live: dict, demo: dict) -> str:
    data = {"live": live, "demo": demo}
    html = _shell(_PAGE)
    html = html.replace("__DATA_JSON__", json.dumps(data, separators=(",", ":")))
    html = html.replace("__SEA_LEVEL_MAX__", str(SEA_LEVEL_MAX_M))
    html = html.replace("__MOUNTAIN_MIN__", str(MID_MAX_M))
    html = html.replace("__MAX_ELEV__", str(MAX_ELEV_M))
    return html
