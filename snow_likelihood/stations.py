"""Fixed reference station list for the UK snow-likelihood map.

Elevation decides which panel a station appears in (`SEA_LEVEL_MAX_M` /
`MID_MAX_M`): sea-level/lowland, mid-elevation/upland, or mountain/summit
stations.
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
    {"name": "Cardiff", "region": "City", "lat": 51.4816, "lon": -3.1791, "elev": 10},
    {"name": "Belfast", "region": "City", "lat": 54.5973, "lon": -5.9301, "elev": 15},
    {"name": "Aviemore", "region": "Scottish Highlands", "lat": 57.1929, "lon": -3.8272, "elev": 220},
    {"name": "Alston", "region": "Pennines", "lat": 54.8144, "lon": -2.4318, "elev": 300},
    {"name": "Buxton", "region": "Peak District", "lat": 53.2591, "lon": -1.9111, "elev": 307},
    {"name": "Newcastle upon Tyne", "region": "City", "lat": 54.9783, "lon": -1.6178, "elev": 47},
    {"name": "Bristol", "region": "City", "lat": 51.4545, "lon": -2.5879, "elev": 11},
    {"name": "Southampton", "region": "City", "lat": 50.9097, "lon": -1.4044, "elev": 15},
    {"name": "Aberdeen", "region": "City", "lat": 57.1497, "lon": -2.0943, "elev": 65},
    {"name": "Norwich", "region": "City", "lat": 52.6309, "lon": 1.2974, "elev": 15},
    {"name": "Nottingham", "region": "City", "lat": 52.9548, "lon": -1.1581, "elev": 42},
    {"name": "Brighton", "region": "City", "lat": 50.8225, "lon": -0.1372, "elev": 15},
    {"name": "St Ives", "region": "City", "lat": 50.2108, "lon": -5.4802, "elev": 20},
    {"name": "Margate", "region": "City", "lat": 51.3813, "lon": 1.3862, "elev": 10},
    {"name": "Corby", "region": "City", "lat": 52.4909, "lon": -0.6961, "elev": 110},
    {"name": "Whitby", "region": "City", "lat": 54.4858, "lon": -0.6206, "elev": 15},
    {"name": "Alnwick", "region": "City", "lat": 55.4149, "lon": -1.7059, "elev": 55},
    {"name": "Tomintoul", "region": "Scottish Highlands", "lat": 57.2028, "lon": -3.3778, "elev": 345},
    {"name": "Malham", "region": "Yorkshire Dales", "lat": 54.0614, "lon": -2.1508, "elev": 235},
    {"name": "Princetown", "region": "Dartmoor", "lat": 50.5766, "lon": -3.9997, "elev": 430},
    {"name": "Storey Arms", "region": "Brecon Beacons", "lat": 51.8697, "lon": -3.4980, "elev": 430},
    {"name": "Glenshane Pass", "region": "Sperrin Mountains", "lat": 54.9333, "lon": -6.7667, "elev": 325},
    {"name": "Pen y Fan", "region": "Brecon Beacons", "lat": 51.8837, "lon": -3.4374, "elev": 886},
    {"name": "Slieve Donard", "region": "Mourne Mountains", "lat": 54.1808, "lon": -5.9183, "elev": 850},
    {"name": "High Willhays", "region": "Dartmoor", "lat": 50.6870, "lon": -3.9968, "elev": 621},
    {"name": "Helvellyn", "region": "Lake District", "lat": 54.5271, "lon": -3.0166, "elev": 950},
    {"name": "The Cheviot", "region": "Cheviot Hills", "lat": 55.4784, "lon": -2.1457, "elev": 815},
]

SEA_LEVEL_MAX_M = 200
MID_MAX_M = 501
MAX_ELEV_M = max(loc["elev"] for loc in LOCATIONS)


def elev_class(elev_m: float) -> str:
    if elev_m < SEA_LEVEL_MAX_M:
        return "sea_level"
    if elev_m < MID_MAX_M:
        return "mid"
    return "mountain"
