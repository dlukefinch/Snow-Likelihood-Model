"""
The individual scoring methods, each returning a value on a continuous
0.0-1.0 scale so they can be blended together. Every method is a scoring
heuristic used in real operational UK snow forecasting -- this module does
not invent new meteorology, it encodes existing rules of thumb as
continuous, blendable functions instead of the hard yes/no cutoffs
forecasters use by eye.

References for the thresholds used below:
  - 1000-500 hPa thickness ("the 528 line"): a long-standing UK/Ireland
    forecasting heuristic. Thickness below ~528 dam indicates an airmass
    cold enough, aloft, for snow to be plausible at low levels; below
    ~516 dam snow becomes likely even against weak surface warming.
    Thickness above ~540 dam essentially rules snow out.
  - Freezing level height vs. site elevation: when the freezing level
    (0 degC isotherm height) sits at or below the ground, snow reaching the
    surface is far more likely than when it sits several hundred metres
    above it.
  - Wet-bulb temperature threshold (~1 degC): operationally, precipitation
    can still fall and settle as snow even when the dry-bulb air
    temperature is a degree or two above freezing, because evaporative
    cooling of falling precipitation drags the near-surface wet-bulb
    temperature down. Wet-bulb temperature is a better discriminator
    between rain and snow than dry-bulb temperature alone.
"""

from __future__ import annotations

import math
from typing import Iterable, Optional, Sequence

SNOW_WMO_CODES = {71, 73, 75, 77, 85, 86}


def _interp_piecewise(x: float, points: Sequence[tuple]) -> float:
    """Piecewise-linear interpolation over `points` (sorted by x ascending),
    clamped to the first/last y value outside the given x range.
    """
    if x <= points[0][0]:
        return points[0][1]
    if x >= points[-1][0]:
        return points[-1][1]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x0 <= x <= x1:
            if x1 == x0:
                return y0
            frac = (x - x0) / (x1 - x0)
            return y0 + frac * (y1 - y0)
    return points[-1][1]


def thickness_score(thickness_dam: Optional[float]) -> Optional[float]:
    """Score from the 1000-500 hPa thickness, in decametres.
    None in, None out (lets callers detect missing pressure-level data).
    """
    if thickness_dam is None:
        return None
    points = [
        (500.0, 1.00),
        (516.0, 0.90),
        (522.0, 0.70),
        (528.0, 0.45),
        (534.0, 0.20),
        (540.0, 0.05),
        (546.0, 0.00),
    ]
    return _interp_piecewise(thickness_dam, points)


def freezing_level_score(freezing_level_m: Optional[float], elevation_m: float) -> Optional[float]:
    """Score from how far above (or below) the site's elevation the
    freezing level sits. A freezing level at or below the ground scores
    highest.
    """
    if freezing_level_m is None:
        return None
    diff = freezing_level_m - elevation_m
    points = [
        (0.0, 1.00),
        (150.0, 0.70),
        (300.0, 0.40),
        (600.0, 0.10),
        (900.0, 0.00),
    ]
    return _interp_piecewise(diff, points)


def wet_bulb_temperature_c(temp_c: float, relative_humidity_pct: float) -> float:
    """Stull (2011) empirical approximation of wet-bulb temperature from
    dry-bulb temperature and relative humidity. Valid roughly for
    -20 to 50 degC and 5-99% RH; inputs are clamped into that RH range for
    numerical stability at the extremes.
    """
    rh = max(5.0, min(99.0, relative_humidity_pct))
    t = temp_c

    # NB: math.atan here returns radians, and that is correct for this
    # formula as published -- it is *not* the degrees-form some inaccurate
    # re-implementations online use, which blows the result up to hundreds
    # of degrees C. Sanity check: T=20 degC, RH=50% should give Tw ~ 13.7
    # degC (see tests/test_methods.py).
    return (
        t * math.atan(0.151977 * math.sqrt(rh + 8.313659))
        + math.atan(t + rh)
        - math.atan(rh - 1.676331)
        + 0.00391838 * (rh ** 1.5) * math.atan(0.023101 * rh)
        - 4.686035
    )


def wet_bulb_score(wet_bulb_c: float) -> float:
    points = [
        (-2.0, 1.00),
        (0.0, 1.00),
        (1.5, 0.30),
        (3.0, 0.00),
    ]
    return _interp_piecewise(wet_bulb_c, points)


def precipitation_gate(
    precipitation_mm: Optional[float],
    snowfall_cm: Optional[float],
    precipitation_probability_pct: Optional[float] = None,
) -> float:
    """A 0-1 multiplier reflecting how confident we are that *something* is
    going to fall in this window at all. Temperature-based scores are
    meaningless if there's no precipitation to change phase.
    """
    if snowfall_cm is not None and snowfall_cm > 0.0:
        return 1.0
    if precipitation_mm is not None and precipitation_mm > 0.1:
        return 0.85
    if precipitation_probability_pct is not None and precipitation_probability_pct >= 30:
        return 0.5
    return 0.15


def synoptic_hour_score(
    *,
    thickness_dam: Optional[float],
    freezing_level_m: Optional[float],
    elevation_m: float,
    temp_c: Optional[float],
    relative_humidity_pct: Optional[float],
    precipitation_mm: Optional[float],
    snowfall_cm: Optional[float],
    precipitation_probability_pct: Optional[float] = None,
) -> dict:
    """Combine the three synoptic sub-scores for a single hour/timestep into
    one gated score, plus the raw sub-scores and derived values for
    transparency in output.
    """
    t_score = thickness_score(thickness_dam)
    fl_score = freezing_level_score(freezing_level_m, elevation_m)

    wb_c = None
    wb_score = None
    if temp_c is not None and relative_humidity_pct is not None:
        wb_c = wet_bulb_temperature_c(temp_c, relative_humidity_pct)
        wb_score = wet_bulb_score(wb_c)

    weighted_parts = []
    if t_score is not None:
        weighted_parts.append((t_score, 0.35))
    if fl_score is not None:
        weighted_parts.append((fl_score, 0.35))
    if wb_score is not None:
        weighted_parts.append((wb_score, 0.30))

    if not weighted_parts:
        core = 0.0
    else:
        total_weight = sum(w for _, w in weighted_parts)
        core = sum(s * w for s, w in weighted_parts) / total_weight

    gate = precipitation_gate(precipitation_mm, snowfall_cm, precipitation_probability_pct)
    final = core * gate

    return {
        "thickness_dam": thickness_dam,
        "thickness_score": t_score,
        "freezing_level_m": freezing_level_m,
        "freezing_level_score": fl_score,
        "wet_bulb_c": wb_c,
        "wet_bulb_score": wb_score,
        "precipitation_gate": gate,
        "synoptic_core_score": core,
        "synoptic_score": final,
    }


def ensemble_member_is_snow(snowfall_cm: Optional[float], weather_code: Optional[int], threshold_cm: float = 0.1) -> bool:
    if snowfall_cm is not None and snowfall_cm >= threshold_cm:
        return True
    if weather_code is not None and int(weather_code) in SNOW_WMO_CODES:
        return True
    return False


def ensemble_probability(member_flags: Iterable[bool]) -> Optional[float]:
    """Fraction of ensemble members (bool: did-this-member-show-snow) that
    predicted snow. None if there were no members to evaluate.
    """
    flags = list(member_flags)
    if not flags:
        return None
    return sum(1 for f in flags if f) / len(flags)


CATEGORY_THRESHOLDS = [
    (10, "Very low"),
    (30, "Low"),
    (55, "Moderate"),
    (75, "High"),
    (101, "Very high"),
]


def categorise(score_pct: float) -> str:
    for upper, label in CATEGORY_THRESHOLDS:
        if score_pct < upper:
            return label
    return "Very high"
