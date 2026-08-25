"""Fixed reference station list for the UK snow-likelihood map.

Elevation decides which panel a station appears in (`SEA_LEVEL_MAX_M`, default
200m, matches UK convention for what counts as "lowland"): mountain/summit
stations vs. sea-level/lowland stations.
"""

LOCATIONS = [
    {"name": "Cairn Gorm Summit", "region": "Scottish Highlands", "lat": 57.1173, "lon": -3.6438, "elev": 1245},
    {"name": "Nevis Range (Aonach Mor)", "region": "Scottish Highlands", "lat": 56.8175, "lon": -4.9808, "elev": 1221},
    {"name": "Glenshee", "region": "Scottish Highlands", "lat": 56.8817, "lon": -3.4728, "elev": 640},
    {"name": "Glencoe Mountain", "region": "Scottish Highlands", "lat": 56.6403, "lon": -4.9070, "elev": 610},
    {"name": "The Lecht", "region": "Scottish Highlands", "lat": 57.1352, "lon": -3.2333, "elev": 640},
    {"name": "Ben Nevis Summit", "region": "Scottish Highlands", "lat": 56.7969, "lon": -5.0036, "elev": 1345},
    {"name": "Cross Fell", "region": "Pennines", "lat": 54.7011, "lon": -2.4881, "elev": 893},
    {"name": "Scafell Pike", "region": "Lake District", "lat": 54.4542, "lon": -3.2100, "elev": 978},
    {"name": "Yr Wyddfa (Snowdon)", "region": "Snowdonia", "lat": 53.0685, "lon": -4.0763, "elev": 1085},
    {"name": "Kinder Scout", "region": "Peak District", "lat": 53.3833, "lon": -1.8744, "elev": 636},
    {"name": "Edinburgh", "region": "City", "lat": 55.9533, "lon": -3.1883, "elev": 47},
    {"name": "London", "region": "City", "lat": 51.5074, "lon": -0.1278, "elev": 11},
]

SEA_LEVEL_MAX_M = 200


def elev_class(elev_m: float) -> str:
    return "sea_level" if elev_m < SEA_LEVEL_MAX_M else "mountain"
