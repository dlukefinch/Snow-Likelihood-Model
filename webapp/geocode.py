"""UK postcode -> (lat, lon, label) via postcodes.io (free, no API key).

Full postcodes get exact coordinates; a bare outward code (e.g. "EH1") gets
that district's centroid -- still real geocoding, just coarser, since a
partial postcode has no exact point to resolve to.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import httpx

POSTCODES_IO = "https://api.postcodes.io"
REQUEST_TIMEOUT_S = 8

FULL_RE = re.compile(r"^[A-Z]{1,2}[0-9][0-9A-Z]?\s*[0-9][A-Z]{2}$")
OUTCODE_RE = re.compile(r"^[A-Z]{1,2}[0-9][0-9A-Z]?$")


class GeocodeError(Exception):
    pass


@dataclass
class GeocodeResult:
    lat: float
    lon: float
    label: str
    precise: bool  # True for a full postcode match, False for outcode-centroid


def normalize(raw: str) -> str:
    return re.sub(r"\s+", "", raw.strip().upper())


def geocode_postcode(raw: str) -> GeocodeResult:
    s = normalize(raw)
    if not s:
        raise GeocodeError("Enter a UK postcode.")

    if FULL_RE.match(s):
        r = httpx.get(f"{POSTCODES_IO}/postcodes/{s}", timeout=REQUEST_TIMEOUT_S)
        if r.status_code == 200:
            result = r.json()["result"]
            return GeocodeResult(lat=result["latitude"], lon=result["longitude"], label=result["postcode"], precise=True)
        if r.status_code != 404:
            raise GeocodeError(f"Postcode lookup failed ({r.status_code}).")
        # Fall through to outcode lookup below -- full postcode not found,
        # but its outward part might still resolve (e.g. a very new postcode).
        s = s[:-3] if len(s) > 3 else s

    if OUTCODE_RE.match(s):
        r = httpx.get(f"{POSTCODES_IO}/outcodes/{s}", timeout=REQUEST_TIMEOUT_S)
        if r.status_code == 200:
            result = r.json()["result"]
            return GeocodeResult(lat=result["latitude"], lon=result["longitude"], label=result["outcode"], precise=False)
        if r.status_code == 404:
            raise GeocodeError(f"\"{raw}\" doesn't look like a real UK postcode or district.")
        raise GeocodeError(f"Postcode lookup failed ({r.status_code}).")

    raise GeocodeError(f"\"{raw}\" doesn't look like a UK postcode. Try a full postcode or just the outward part, e.g. \"EH1\".")
