from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping

import psycopg
from psycopg.rows import dict_row

from .config import get_settings
from .geometry import ensure_wkt_type


class FeatureNotFoundError(LookupError):
    pass


class InvalidFeatureInputError(ValueError):
    pass


class DatabaseOperationError(RuntimeError):
    pass


@dataclass(frozen=True)
class FeatureSpec:
    table: str
    lock_key: str
    expected_type: str


SPECS = {
    "vanalar": FeatureSpec(
        table="cbs.vanalar",
        lock_key="cbs.vanalar.id",
        expected_type="POINT",
    ),
    "borular": FeatureSpec(
        table="cbs.borular",
        lock_key="cbs.borular.id",
        expected_type="LINESTRING",
    ),
}


def _connect() -> psycopg.Connection:
    settings = get_settings()
    return psycopg.connect(**settings.db_params(), row_factory=dict_row)


def _select_columns() -> str:
    return (
        "id, malzeme, cap, isletme_durumu, "
        "ST_AsText(geom) AS geom_wkt, ST_SRID(geom) AS srid"
    )


def list_features(kind: str) -> list[dict[str, Any]]:
    spec = SPECS[kind]
    query = f"SELECT {_select_columns()} FROM {spec.table} ORDER BY id;"

    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                return list(cur.fetchall())
    except psycopg.Error as exc:
        raise DatabaseOperationError("Database read failed.") from exc


def get_feature(kind: str, feature_id: int) -> dict[str, Any]:
    spec = SPECS[kind]
    query = f"SELECT {_select_columns()} FROM {spec.table} WHERE id = %s;"

    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (feature_id,))
                row = cur.fetchone()
    except psycopg.Error as exc:
        raise DatabaseOperationError("Database read failed.") from exc

    if row is None:
        raise FeatureNotFoundError(f"{kind} record was not found.")
    return dict(row)


def create_feature(kind: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    spec = SPECS[kind]
    try:
        geom_wkt = ensure_wkt_type(str(payload["geom_wkt"]), spec.expected_type)
    except ValueError as exc:
        raise InvalidFeatureInputError(str(exc)) from exc

    query = f"""
WITH new_geom AS (
    SELECT ST_SetSRID(ST_GeomFromText(%(geom_wkt)s), 3857) AS geom
),
next_id AS (
    SELECT COALESCE(MAX(id), 0) + 1 AS id
    FROM {spec.table}
)
INSERT INTO {spec.table} (id, malzeme, cap, isletme_durumu, geom)
SELECT
    next_id.id,
    %(malzeme)s,
    %(cap)s,
    %(isletme_durumu)s,
    new_geom.geom
FROM next_id, new_geom
WHERE GeometryType(new_geom.geom) = %(expected_type)s
RETURNING {_select_columns()};
"""

    params = {
        "malzeme": str(payload["malzeme"]).strip(),
        "cap": Decimal(str(payload["cap"])),
        "isletme_durumu": str(payload["isletme_durumu"]).strip(),
        "geom_wkt": geom_wkt,
        "expected_type": spec.expected_type,
    }

    try:
        with _connect() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT pg_advisory_xact_lock(hashtext(%s));",
                        (spec.lock_key,),
                    )
                    cur.execute(query, params)
                    row = cur.fetchone()
                    if row is None:
                        raise InvalidFeatureInputError(
                            f"geom_wkt must be {spec.expected_type} geometry."
                        )
                    return dict(row)
    except InvalidFeatureInputError:
        raise
    except psycopg.errors.CheckViolation as exc:
        raise InvalidFeatureInputError("cap must be greater than zero.") from exc
    except psycopg.OperationalError as exc:
        raise DatabaseOperationError("Database connection failed.") from exc
    except psycopg.Error as exc:
        raise InvalidFeatureInputError(
            f"geom_wkt must be valid {spec.expected_type} WKT in EPSG:3857."
        ) from exc


def delete_feature(kind: str, feature_id: int) -> None:
    spec = SPECS[kind]
    query = f"DELETE FROM {spec.table} WHERE id = %s RETURNING id;"

    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (feature_id,))
                row = cur.fetchone()
                conn.commit()
    except psycopg.Error as exc:
        raise DatabaseOperationError("Database delete failed.") from exc

    if row is None:
        raise FeatureNotFoundError(f"{kind} record was not found.")
