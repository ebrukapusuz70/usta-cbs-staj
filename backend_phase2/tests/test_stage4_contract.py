from __future__ import annotations

import unittest
from datetime import date

from pydantic import ValidationError

from app.schemas import GasPipeCreate, GasPipeUpdate, GasValveCreate, GasValveUpdate


class Stage4ContractTests(unittest.TestCase):
    def test_pipe_accepts_linestring_for_server_side_multi_conversion(self) -> None:
        model = GasPipeCreate(
            pipe_code="TEST-P-1", pipe_type="distribution", diameter_mm=110,
            material="PE", pressure_level="low", operating_pressure_bar=1,
            status="aktif", install_year=2024, operator_name="Test Operatörü",
            geom_wkt="LINESTRING (1 1, 2 2)",
            start_connection_type="pipe_endpoint", start_connection_id=1,
        )
        self.assertNotIn("source", model.model_dump())

    def test_pipe_rejects_non_finite_coordinate(self) -> None:
        with self.assertRaises(ValidationError):
            GasPipeCreate(
                pipe_code="TEST-P-2", pipe_type="distribution", diameter_mm=110,
                material="PE", pressure_level="low", operating_pressure_bar=1,
                status="aktif", install_year=2024, operator_name="Test Operatörü",
                geom_wkt="LINESTRING (NaN 1, 2 2)",
                start_connection_type="pipe_endpoint", start_connection_id=1,
            )

    def test_valve_rejects_client_managed_fields(self) -> None:
        with self.assertRaises(ValidationError):
            GasValveCreate(
                valve_code="TEST-V-1", valve_type="isolation", diameter_mm=110,
                material="celik", status="open", install_year=2024,
                related_pipe_id=1, source="synthetic_demo_yenimahalle",
                operator_name="Test Operatörü", geom_wkt="POINT (1 1)",
            )

    def test_future_year_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            GasValveCreate(
                valve_code="TEST-V-2", valve_type="isolation",
                material="celik", status="open", install_year=date.today().year + 1,
                operator_name="Test Operatörü", geom_wkt="POINT (1 1)",
            )

    def test_pipe_rejects_incompatible_attributes(self) -> None:
        with self.assertRaises(ValidationError):
            GasPipeCreate(
                pipe_code="TEST-P-3", pipe_type="service_line", diameter_mm=400,
                material="çelik", pressure_level="high", operating_pressure_bar=10,
                status="aktif", install_year=2024, operator_name="Test Operatörü",
                geom_wkt="LINESTRING (1 1, 2 2)",
                start_connection_type="pipe_endpoint", start_connection_id=1,
            )

    def test_operator_name_is_trimmed(self) -> None:
        model = GasValveCreate(
            valve_code="TEST-V-3", valve_type="isolation",
            material="PE", status="aktif", install_year=2024,
            operator_name="  Ebru Kaya  ", geom_wkt="POINT (1 1)",
        )
        self.assertEqual(model.operator_name, "Ebru Kaya")

    def test_operator_name_is_required(self) -> None:
        with self.assertRaises(ValidationError):
            GasPipeCreate(
                pipe_code="TEST-P-4", pipe_type="distribution", diameter_mm=110,
                material="PE", pressure_level="low", operating_pressure_bar=1,
                status="aktif", install_year=2024,
                geom_wkt="LINESTRING (1 1, 2 2)",
                start_connection_type="pipe_endpoint", start_connection_id=1,
            )

    def test_operator_name_rejects_blank_short_and_long_values(self) -> None:
        for operator_name in ("   ", "A", "A" * 101):
            with self.subTest(operator_name=operator_name):
                with self.assertRaises(ValidationError):
                    GasValveCreate(
                        valve_code="TEST-V-4", valve_type="isolation",
                        material="PE", status="aktif", install_year=2024,
                        operator_name=operator_name, geom_wkt="POINT (1 1)",
                    )

    def test_pipe_code_rejects_unsafe_characters(self) -> None:
        with self.assertRaises(ValidationError):
            GasPipeCreate(
                pipe_code="<script>", pipe_type="distribution", diameter_mm=110,
                material="PE", pressure_level="low", operating_pressure_bar=1,
                status="aktif", install_year=2024, operator_name="Test Operatörü",
                geom_wkt="LINESTRING (1 1, 2 2)",
                start_connection_type="pipe_endpoint", start_connection_id=1,
            )

    def test_valve_code_rejects_unsafe_characters(self) -> None:
        with self.assertRaises(ValidationError):
            GasValveCreate(
                valve_code="<script>", valve_type="isolation",
                material="PE", status="aktif", install_year=2024,
                operator_name="Test Operatörü", geom_wkt="POINT (1 1)",
            )

    def test_patch_models_require_at_least_one_allowlisted_field(self) -> None:
        with self.assertRaises(ValidationError):
            GasPipeUpdate()
        with self.assertRaises(ValidationError):
            GasValveUpdate()
        with self.assertRaises(ValidationError):
            GasValveUpdate(source="user_created_stage4")

    def test_pipe_geometry_patch_requires_connection_fields(self) -> None:
        with self.assertRaises(ValidationError):
            GasPipeUpdate(geom_wkt="LINESTRING (1 1, 2 2)")
        model = GasPipeUpdate(
            geom_wkt="LINESTRING (1 1, 2 2)",
            start_connection_type="pipe_endpoint",
            start_connection_id=1,
        )
        self.assertEqual(model.start_connection_id, 1)

    def test_valve_patch_cannot_change_derived_or_system_fields(self) -> None:
        for forbidden in (
            {"related_pipe_id": 1},
            {"diameter_mm": 110},
            {"source": "user_created_stage4"},
            {"valve_id": 1},
        ):
            with self.subTest(forbidden=forbidden):
                with self.assertRaises(ValidationError):
                    GasValveUpdate(**forbidden)

    def test_update_operator_and_codes_are_trimmed(self) -> None:
        pipe = GasPipeUpdate(pipe_code="  TEST-P-9  ", operator_name="  Ebru Kaya  ")
        valve = GasValveUpdate(valve_code="  TEST-V-9  ", operator_name="  Ebru Kaya  ")
        self.assertEqual(pipe.pipe_code, "TEST-P-9")
        self.assertEqual(valve.valve_code, "TEST-V-9")
        self.assertEqual(pipe.operator_name, "Ebru Kaya")
        self.assertEqual(valve.operator_name, "Ebru Kaya")


if __name__ == "__main__":
    unittest.main()
