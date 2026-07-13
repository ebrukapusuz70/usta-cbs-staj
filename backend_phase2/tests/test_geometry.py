import unittest

from app.geometry import GeometryValidationError, ensure_wkt_type, get_wkt_type


class GeometryValidationTests(unittest.TestCase):
    def test_get_wkt_type_reads_point(self):
        self.assertEqual(get_wkt_type("POINT (1 2)"), "POINT")

    def test_get_wkt_type_reads_linestring(self):
        self.assertEqual(get_wkt_type("LINESTRING (1 2, 3 4)"), "LINESTRING")

    def test_ensure_wkt_type_accepts_expected_type(self):
        self.assertEqual(ensure_wkt_type(" POINT (1 2) ", "POINT"), "POINT (1 2)")

    def test_ensure_wkt_type_rejects_wrong_type(self):
        with self.assertRaises(GeometryValidationError):
            ensure_wkt_type("LINESTRING (1 2, 3 4)", "POINT")

    def test_rejects_srid_prefix(self):
        with self.assertRaises(GeometryValidationError):
            get_wkt_type("SRID=4326;POINT (1 2)")


if __name__ == "__main__":
    unittest.main()
