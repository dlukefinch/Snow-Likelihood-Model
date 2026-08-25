"""
Unit tests for the pure scoring logic in snow_likelihood.methods. These
need no network access -- run with:

    python3 -m pytest tests/  (if pytest is installed)
    python3 -m unittest discover -s tests   (stdlib-only fallback)
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from snow_likelihood import methods


class TestThicknessScore(unittest.TestCase):
    def test_none_passthrough(self):
        self.assertIsNone(methods.thickness_score(None))

    def test_very_cold_thickness_is_high_score(self):
        self.assertAlmostEqual(methods.thickness_score(500), 1.0)
        self.assertGreater(methods.thickness_score(510), 0.9)

    def test_classic_528_line_is_moderate(self):
        score = methods.thickness_score(528)
        self.assertAlmostEqual(score, 0.45, places=2)

    def test_mild_thickness_is_zero(self):
        self.assertEqual(methods.thickness_score(550), 0.0)
        self.assertEqual(methods.thickness_score(546), 0.0)

    def test_monotonically_decreasing(self):
        values = [500, 510, 520, 528, 535, 540, 546]
        scores = [methods.thickness_score(v) for v in values]
        for a, b in zip(scores, scores[1:]):
            self.assertGreaterEqual(a, b)


class TestFreezingLevelScore(unittest.TestCase):
    def test_freezing_level_at_ground_is_max(self):
        self.assertAlmostEqual(methods.freezing_level_score(200, 200), 1.0)

    def test_freezing_level_below_ground_is_still_capped_at_max(self):
        # freezing level well below the site elevation -> diff negative,
        # should clamp to the top of the interpolation range (1.0), not
        # extrapolate above it.
        self.assertAlmostEqual(methods.freezing_level_score(-500, 200), 1.0)

    def test_freezing_level_far_above_ground_is_zero(self):
        self.assertEqual(methods.freezing_level_score(1200, 200), 0.0)

    def test_none_passthrough(self):
        self.assertIsNone(methods.freezing_level_score(None, 200))


class TestWetBulb(unittest.TestCase):
    def test_known_reference_point(self):
        # Published reference value for the Stull (2011) approximation:
        # T=20 degC, RH=50% -> Tw ~= 13.7 degC. Locks in the radians-not-
        # degrees implementation detail.
        wb = methods.wet_bulb_temperature_c(20.0, 50.0)
        self.assertAlmostEqual(wb, 13.7, delta=0.2)

    def test_saturated_air_wet_bulb_equals_dry_bulb(self):
        # At 100% RH, wet-bulb temperature should equal (or be extremely
        # close to) dry-bulb temperature -- clamped RH of 99% used
        # internally, so allow a small tolerance.
        wb = methods.wet_bulb_temperature_c(5.0, 99.0)
        self.assertAlmostEqual(wb, 5.0, delta=0.3)

    def test_dry_air_wet_bulb_is_below_dry_bulb(self):
        wb = methods.wet_bulb_temperature_c(10.0, 30.0)
        self.assertLess(wb, 10.0)

    def test_wet_bulb_score_boundaries(self):
        self.assertAlmostEqual(methods.wet_bulb_score(-1.0), 1.0)
        self.assertAlmostEqual(methods.wet_bulb_score(0.0), 1.0)
        self.assertEqual(methods.wet_bulb_score(5.0), 0.0)

    def test_wet_bulb_never_nan(self):
        for t in range(-20, 30, 5):
            for rh in range(5, 100, 10):
                wb = methods.wet_bulb_temperature_c(float(t), float(rh))
                self.assertFalse(math.isnan(wb))


class TestPrecipitationGate(unittest.TestCase):
    def test_model_already_shows_snow(self):
        self.assertEqual(methods.precipitation_gate(2.0, 1.0), 1.0)

    def test_precip_present_type_unknown(self):
        self.assertEqual(methods.precipitation_gate(1.0, 0.0), 0.85)

    def test_no_precip_signal_at_all(self):
        self.assertEqual(methods.precipitation_gate(0.0, 0.0, 0), 0.15)

    def test_probability_only_signal(self):
        self.assertEqual(methods.precipitation_gate(0.0, 0.0, 40), 0.5)


class TestSynopticHourScore(unittest.TestCase):
    def test_cold_wet_snowy_hour_scores_high(self):
        result = methods.synoptic_hour_score(
            thickness_dam=510,
            freezing_level_m=50,
            elevation_m=200,
            temp_c=-1.0,
            relative_humidity_pct=90,
            precipitation_mm=1.5,
            snowfall_cm=1.2,
        )
        self.assertGreater(result["synoptic_score"], 0.8)

    def test_mild_dry_hour_scores_low(self):
        result = methods.synoptic_hour_score(
            thickness_dam=548,
            freezing_level_m=1500,
            elevation_m=50,
            temp_c=12.0,
            relative_humidity_pct=60,
            precipitation_mm=0.0,
            snowfall_cm=0.0,
        )
        self.assertLess(result["synoptic_score"], 0.1)

    def test_missing_pressure_level_data_falls_back_gracefully(self):
        result = methods.synoptic_hour_score(
            thickness_dam=None,
            freezing_level_m=100,
            elevation_m=200,
            temp_c=-1.0,
            relative_humidity_pct=90,
            precipitation_mm=1.0,
            snowfall_cm=0.5,
        )
        self.assertIsNone(result["thickness_score"])
        self.assertIsNotNone(result["synoptic_score"])
        self.assertGreater(result["synoptic_score"], 0.0)


class TestEnsembleProbability(unittest.TestCase):
    def test_all_members_snow(self):
        self.assertEqual(methods.ensemble_probability([True, True, True]), 1.0)

    def test_no_members_snow(self):
        self.assertEqual(methods.ensemble_probability([False, False]), 0.0)

    def test_mixed(self):
        self.assertAlmostEqual(methods.ensemble_probability([True, False, True, False]), 0.5)

    def test_empty_returns_none(self):
        self.assertIsNone(methods.ensemble_probability([]))

    def test_member_is_snow_by_snowfall_amount(self):
        self.assertTrue(methods.ensemble_member_is_snow(0.5, None))
        self.assertFalse(methods.ensemble_member_is_snow(0.0, None))

    def test_member_is_snow_by_weather_code(self):
        self.assertTrue(methods.ensemble_member_is_snow(None, 73))
        self.assertFalse(methods.ensemble_member_is_snow(None, 61))


class TestCategorise(unittest.TestCase):
    def test_boundaries(self):
        self.assertEqual(methods.categorise(0), "Very low")
        self.assertEqual(methods.categorise(9.9), "Very low")
        self.assertEqual(methods.categorise(10), "Low")
        self.assertEqual(methods.categorise(29.9), "Low")
        self.assertEqual(methods.categorise(30), "Moderate")
        self.assertEqual(methods.categorise(55), "High")
        self.assertEqual(methods.categorise(75), "Very high")
        self.assertEqual(methods.categorise(100), "Very high")


if __name__ == "__main__":
    unittest.main()
