"""
snow_likelihood
================

A UK-focused snow likelihood model that blends two independent forecasting
approaches:

1.  A synoptic rules-based method (1000-500 hPa thickness, freezing level
    height vs. site elevation, and wet-bulb temperature) applied to a single
    deterministic model run.
2.  A numerical-weather-prediction ensemble agreement method, which measures
    the fraction of ensemble members (across one or more forecasting
    centres, e.g. UK Met Office / ECMWF / NOAA GFS / DWD ICON) that predict
    snowfall for a given hour.

The two are combined into a single 0-100% "snow likelihood" score per hour,
aggregated to a daily summary.

See README.md for methodology notes and important caveats.
"""

__version__ = "0.1.0"
