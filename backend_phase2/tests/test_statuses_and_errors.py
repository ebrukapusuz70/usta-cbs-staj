"""Durum standardı ve HTTP hata sözleşmesi için veritabanına yazmayan testler."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi import HTTPException
from pydantic import ValidationError

from app.database import CodeConflictError, FeatureInUseError, TopologyConflictError
from app.main import (
    _stage4_source,
    _handle_error,
    create_stage4_gas_pipe,
    create_stage4_gas_valve,
    remove_stage4_gas_pipe,
    remove_stage4_gas_valve,
    update_stage4_gas_pipe,
    update_stage4_gas_valve,
)
from app.schemas import (
    GasPipeCreate,
    GasPipeResponse,
    GasPipeUpdate,
    GasValveCreate,
    GasValveResponse,
    GasValveUpdate,
)
from app.statuses import normalize_asset_status, to_storage_status


PIPE_RESPONSE = {
    "pipe_id": 1,
    "pipe_code": "P-1",
    "pipe_type": "distribution",
    "diameter_mm": 110,
    "material": "PE",
    "pressure_level": "low",
    "operating_pressure_bar": 1,
    "status": "ACTIVE",
    "install_year": 2024,
    "source": "synthetic_demo_yenimahalle",
    "geom_wkt": "MULTILINESTRING ((1 1, 2 2))",
    "srid": 3857,
}

VALVE_RESPONSE = {
    "valve_id": 1,
    "valve_code": "V-1",
    "valve_type": "isolation",
    "diameter_mm": 110,
    "material": "celik",
    "status": "closed",
    "install_year": 2024,
    "related_pipe_id": 1,
    "source": "synthetic_demo_yenimahalle",
    "geom_wkt": "POINT (1 1)",
    "srid": 3857,
}


class StatusNormalizationTests(unittest.TestCase):
    def test_aliases_are_normalized_to_canonical_turkish_values(self) -> None:
        cases = {
            "ACTIVE": "aktif",
            "Açık": "aktif",
            "open": "aktif",
            "INACTIVE": "pasif",
            "Kapalı": "pasif",
            "closed": "pasif",
            "MAINTENANCE": "bakımda",
            "Bakimda": "bakımda",
            "tamirde": "bakımda",
            None: "bilinmeyen",
            "unexpected": "bilinmeyen",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(normalize_asset_status(raw), expected)

    def test_response_models_never_expose_raw_storage_status(self) -> None:
        self.assertEqual(GasPipeResponse.model_validate(PIPE_RESPONSE).status, "aktif")
        self.assertEqual(GasValveResponse.model_validate(VALVE_RESPONSE).status, "pasif")
        unknown = GasPipeResponse.model_validate({**PIPE_RESPONSE, "status": ""})
        self.assertEqual(unknown.status, "bilinmeyen")

    def test_create_models_accept_legacy_aliases_but_store_canonical_values(self) -> None:
        pipe = GasPipeCreate(
            pipe_code="P-2", pipe_type="distribution", diameter_mm=110,
            material="PE", pressure_level="low", operating_pressure_bar=1,
            status="active", install_year=2024, operator_name="Test Operatörü",
            geom_wkt="LINESTRING (1 1, 2 2)",
            start_connection_type="pipe_endpoint", start_connection_id=1,
        )
        valve = GasValveCreate(
            valve_code="V-2", valve_type="isolation", material="celik",
            status="open", install_year=2024, operator_name="Test Operatörü",
            geom_wkt="POINT (1 1)",
        )
        self.assertEqual(pipe.status, "aktif")
        self.assertEqual(valve.status, "aktif")
        self.assertEqual(to_storage_status("pipe", pipe.status), "aktif")
        self.assertEqual(to_storage_status("valve", valve.status), "open")

    def test_unknown_create_status_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            GasValveCreate(
                valve_code="V-3", valve_type="isolation", material="celik",
                status="unknown", install_year=2024, operator_name="Test Operatörü",
                geom_wkt="POINT (1 1)",
            )


class ErrorContractTests(unittest.TestCase):
    def test_topology_conflict_maps_to_http_409(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            _handle_error(TopologyConflictError("Aynı boru tekrar oluşturulamaz."))
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(raised.exception.detail["code"], "UPDATE_VALIDATION_FAILED")
        self.assertEqual(
            raised.exception.detail["message"],
            "Aynı boru tekrar oluşturulamaz.",
        )

    def test_pipe_code_conflict_maps_to_http_409(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            _handle_error(
                CodeConflictError(
                    "pipe_code zaten kullanılıyor.",
                    code="PIPE_CODE_CONFLICT",
                )
            )
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(raised.exception.detail["code"], "PIPE_CODE_CONFLICT")

    def test_connected_valve_count_is_exposed_without_record_details(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            _handle_error(
                FeatureInUseError(
                    "Bu boruya bağlı vanalar bulunduğu için boru silinemez.",
                    3,
                )
            )
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(
            raised.exception.detail,
            {
                "code": "PIPE_HAS_CONNECTED_VALVES",
                "message": "Bu boruya bağlı vanalar bulunduğu için boru silinemez.",
                "connected_valve_count": 3,
            },
        )

    def test_e2e_source_requires_a_configured_constant_time_token(self) -> None:
        self.assertEqual(_stage4_source(None), "user_created_stage4")
        with patch("app.main.get_stage4_e2e_token", return_value="expected-token"):
            self.assertEqual(_stage4_source("expected-token"), "user_created_stage4_e2e")
            with self.assertRaises(HTTPException) as raised:
                _stage4_source("wrong-token")
        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(raised.exception.detail, "Test isteği yetkilendirilemedi.")

    def test_e2e_source_is_disabled_when_environment_token_is_missing(self) -> None:
        with patch("app.main.get_stage4_e2e_token", return_value=None):
            with self.assertRaises(HTTPException) as raised:
                _stage4_source("unexpected-token")
        self.assertEqual(raised.exception.status_code, 403)

    def test_successful_pipe_create_and_delete_routes_use_mock_database(self) -> None:
        payload = GasPipeCreate(
            pipe_code="P-2", pipe_type="distribution", diameter_mm=110,
            material="PE", pressure_level="low", operating_pressure_bar=1,
            status="aktif", install_year=2024, operator_name="Test Operatörü",
            geom_wkt="LINESTRING (1 1, 2 2)",
            start_connection_type="pipe_endpoint", start_connection_id=1,
        )
        with patch("app.main.create_gas_pipe", return_value=PIPE_RESPONSE) as create_mock:
            self.assertEqual(create_stage4_gas_pipe(payload)["pipe_id"], 1)
            create_mock.assert_called_once()
        with patch("app.main.delete_gas_pipe") as delete_mock:
            response = remove_stage4_gas_pipe(1)
            self.assertEqual(response.status_code, 204)
            delete_mock.assert_called_once_with(1)

    def test_successful_valve_create_and_delete_routes_use_mock_database(self) -> None:
        payload = GasValveCreate(
            valve_code="V-2", valve_type="isolation", material="celik",
            status="aktif", install_year=2024, operator_name="Test Operatörü",
            geom_wkt="POINT (1 1)",
        )
        with patch("app.main.create_gas_valve", return_value=VALVE_RESPONSE) as create_mock:
            self.assertEqual(create_stage4_gas_valve(payload)["valve_id"], 1)
            create_mock.assert_called_once()
        with patch("app.main.delete_gas_valve") as delete_mock:
            response = remove_stage4_gas_valve(1)
            self.assertEqual(response.status_code, 204)
            delete_mock.assert_called_once_with(1)

    def test_successful_patch_routes_pass_only_set_fields(self) -> None:
        pipe_payload = GasPipeUpdate(material="PE")
        with patch("app.main.update_gas_pipe", return_value=PIPE_RESPONSE) as update_mock:
            self.assertEqual(
                update_stage4_gas_pipe(1, pipe_payload)["pipe_id"],
                1,
            )
            update_mock.assert_called_once_with(1, {"material": "PE"})

        valve_payload = GasValveUpdate(valve_code="V-9")
        with patch("app.main.update_gas_valve", return_value=VALVE_RESPONSE) as update_mock:
            self.assertEqual(
                update_stage4_gas_valve(1, valve_payload)["valve_id"],
                1,
            )
            update_mock.assert_called_once_with(1, {"valve_code": "V-9"})


if __name__ == "__main__":
    unittest.main()
