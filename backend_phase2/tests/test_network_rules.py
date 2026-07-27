"""Yazma işleminden önce uygulanan saf ağ kurallarını test eder."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from app.config import get_network_rule_settings
from app.topology import TopologyValidationError, parse_linestring_wkt


class NetworkRuleConfigTests(unittest.TestCase):
    def test_default_stage4_limits_match_the_approved_contract(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SNAP_TOLERANCE": "",
                "PIPE_MIN_LENGTH_M": "",
                "PIPE_MAX_LENGTH_M": "",
            },
            clear=False,
        ):
            for name in ("SNAP_TOLERANCE", "PIPE_MIN_LENGTH_M", "PIPE_MAX_LENGTH_M"):
                os.environ.pop(name, None)
            settings = get_network_rule_settings()
        self.assertEqual(settings.snap_tolerance_m, 15.0)
        self.assertEqual(settings.pipe_min_length_m, 5.0)
        self.assertEqual(settings.pipe_max_length_m, 5_000.0)

    def test_network_rules_are_read_from_environment(self) -> None:
        values = {
            "SNAP_TOLERANCE": "7.5",
            "PIPE_MIN_LENGTH_M": "6",
            "PIPE_MAX_LENGTH_M": "850",
        }
        with patch.dict(os.environ, values):
            settings = get_network_rule_settings()
        self.assertEqual(settings.snap_tolerance_m, 7.5)
        self.assertEqual(settings.pipe_min_length_m, 6.0)
        self.assertEqual(settings.pipe_max_length_m, 850.0)

    def test_maximum_length_must_exceed_minimum(self) -> None:
        values = {"PIPE_MIN_LENGTH_M": "10", "PIPE_MAX_LENGTH_M": "10"}
        with patch.dict(os.environ, values):
            with self.assertRaises(RuntimeError):
                get_network_rule_settings()

    def test_non_finite_tolerance_is_rejected(self) -> None:
        with patch.dict(os.environ, {"SNAP_TOLERANCE": "NaN"}):
            with self.assertRaises(RuntimeError):
                get_network_rule_settings()


class PipeStructureTests(unittest.TestCase):
    def test_empty_linestring_is_rejected(self) -> None:
        with self.assertRaises(TopologyValidationError):
            parse_linestring_wkt("LINESTRING EMPTY")

    def test_same_start_and_end_is_rejected(self) -> None:
        with self.assertRaises(TopologyValidationError):
            parse_linestring_wkt("LINESTRING (0 0, 10 0, 0 0)")

    def test_repeated_coordinate_is_rejected(self) -> None:
        with self.assertRaises(TopologyValidationError):
            parse_linestring_wkt("LINESTRING (0 0, 10 0, 10 10, 10 0, 20 0)")

    def test_self_intersection_is_rejected(self) -> None:
        with self.assertRaises(TopologyValidationError):
            parse_linestring_wkt("LINESTRING (0 0, 10 10, 0 10, 10 0)")

    def test_simple_linestring_is_accepted(self) -> None:
        coordinates = parse_linestring_wkt("LINESTRING (0 0, 10 0, 20 5)")
        self.assertEqual(len(coordinates), 3)


if __name__ == "__main__":
    unittest.main()
