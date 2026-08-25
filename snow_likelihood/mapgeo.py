"""Shared map-projection helpers: an equirectangular projection of the GB
coastline plus the fixed reference stations, all into one consistent SVG
coordinate space, and the great-circle distance used for postcode matching.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List


def build_projection(coastline_geojson_path: Path, locations: List[Dict[str, Any]],
                      pad: int = 28, width: int = 640, height: int = 780) -> Dict[str, Any]:
    geo = json.loads(Path(coastline_geojson_path).read_text())
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
    for loc in locations:
        all_lonlat.append((loc["lon"], loc["lat"]))

    lons = [p[0] for p in all_lonlat]
    lats = [p[1] for p in all_lonlat]
    lat_mean = (min(lats) + max(lats)) / 2
    cos_lat = math.cos(math.radians(lat_mean))
    raw_x_min, raw_x_max = min(lons) * cos_lat, max(lons) * cos_lat
    raw_y_min, raw_y_max = -max(lats), -min(lats)

    scale = min((width - 2 * pad) / (raw_x_max - raw_x_min), (height - 2 * pad) / (raw_y_max - raw_y_min))

    def project(lon, lat):
        x = (lon * cos_lat - raw_x_min) * scale + pad
        y = (-lat - raw_y_min) * scale + pad
        return round(x, 2), round(y, 2)

    paths = []
    for rings in polygons:
        for ring in rings:
            pts = [project(lon, lat) for lon, lat in ring]
            paths.append("M " + " L ".join(f"{x},{y}" for x, y in pts) + " Z")

    xy_by_name = {loc["name"]: project(loc["lon"], loc["lat"]) for loc in locations}
    return {
        "viewbox": [0, 0, width, height],
        "coastline_paths": paths,
        "xy": xy_by_name,
        "project": project,
        "proj_params": {"cos_lat": cos_lat, "raw_x_min": raw_x_min, "raw_y_min": raw_y_min, "scale": scale, "pad": pad},
    }


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))
