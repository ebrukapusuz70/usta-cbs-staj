"""PostgreSQL/PostGIS bağlantısını ve SQL işlemlerini yönetir.
Verileri okur, yeni kayıt ekler ve izin verilen kayıtları siler.
Bağlantı ayarlarını config.py dosyasından alır.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
import re
from typing import Any, Mapping

import psycopg
from psycopg.rows import dict_row

from .config import get_settings
from .geometry import ensure_finite_wkt, ensure_wkt_type, get_wkt_type
from .schemas import validate_pipe_attribute_compatibility
from .statuses import DATABASE_STATUS_ALIASES, to_storage_status
from .topology import (
    PIPE_NETWORK_TOUCH_M,
    VALVE_MAX_SNAP_M,
    VALVE_MIN_SPACING_M,
    TopologyValidationError,
    parse_linestring_wkt,
    parse_point_wkt,
    validate_pipe_topology,
    validate_point_topology,
)


# Veritabanı işlemlerindeki farklı hata durumlarını API katmanına bildirir.
class FeatureNotFoundError(LookupError):
    code = "FEATURE_NOT_FOUND"


class InvalidFeatureInputError(ValueError):
    code = "UPDATE_VALIDATION_FAILED"


class DatabaseOperationError(RuntimeError):
    code = "DATABASE_OPERATION_FAILED"


class CodeConflictError(ValueError):
    def __init__(self, message: str, code: str = "CODE_CONFLICT", **details: Any) -> None:
        super().__init__(message)
        self.code = code
        self.details = details


class TopologyConflictError(ValueError):
    code = "UPDATE_VALIDATION_FAILED"


class UnsafeFeatureDeleteError(PermissionError):
    code = "FEATURE_READ_ONLY"


class FeatureInUseError(ValueError):
    code = "PIPE_HAS_CONNECTED_VALVES"

    def __init__(self, message: str, connected_valve_count: int) -> None:
        super().__init__(message)
        self.details = {"connected_valve_count": connected_valve_count}


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

_REGIONAL_PIPE_CODE_RE = re.compile(
    r"^(?P<prefix>[A-Za-z0-9]+(?:-[A-Za-z0-9]+)+)-(?P<number>\d+)$"
)
_NETWORK_PIPE_CODE_RE = re.compile(
    r"^(?P<region>[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*)-P-(?P<number>\d+)$"
)
_NETWORK_VALVE_CODE_RE = re.compile(
    r"^(?P<region>[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*)-V-(?P<number>\d+)$"
)
# Kaynak allowlist'i hem PATCH hem DELETE sorgularında tekrar uygulanır; arayüzde
# düğmenin gizlenmesi sentetik kayıtları korumak için tek başına yeterli değildir.
_STAGE4_SOURCES = {"user_created_stage4", "user_created_stage4_e2e"}
_PROTECTED_PIPE_IDS = {3464, 3465}


# psycopg, Python ile PostgreSQL arasında bağlantı kurar. Bilgiler doğrudan
# kodda değil, config.py aracılığıyla .env dosyasından alınır.
def _connect() -> psycopg.Connection:
    settings = get_settings()
    return psycopg.connect(**settings.db_params(), row_factory=dict_row)


def _select_columns() -> str:
    # ST_AsText geometrinin WKT metnini, ST_SRID koordinat sisteminin kodunu döndürür.
    return (
        "id, malzeme, cap, isletme_durumu, "
        "ST_AsText(geom) AS geom_wkt, ST_SRID(geom) AS srid"
    )


def _gas_pipe_columns() -> str:
    return (
        "pipe_id, pipe_code, pipe_type, diameter_mm, material, pressure_level, "
        "operating_pressure_bar, status, install_year, source, operator_name, "
        "ST_AsText(geom) AS geom_wkt, ST_SRID(geom) AS srid"
    )


def _gas_valve_columns() -> str:
    return (
        "valve_id, valve_code, valve_type, diameter_mm, material, status, "
        "install_year, related_pipe_id, source, operator_name, "
        "ST_AsText(geom) AS geom_wkt, ST_SRID(geom) AS srid"
    )


def list_features(kind: str) -> list[dict[str, Any]]:
    spec = SPECS[kind]
    query = f"SELECT {_select_columns()} FROM {spec.table} ORDER BY id;"

    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                # SELECT veriyi değiştirmeden okur. Tablo adı yalnızca sabit SPECS
                # listesinden geldiğinden kullanıcı girdisi tablo adına dönüşmez.
                cur.execute(query)
                return list(cur.fetchall())
    except psycopg.Error as exc:
        raise DatabaseOperationError("Veritabanı kayıtları okunamadı.") from exc


def list_gas_pipes() -> list[dict[str, Any]]:
    query = f"SELECT {_gas_pipe_columns()} FROM cbs.gas_pipes ORDER BY pipe_id;"

    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                return list(cur.fetchall())
    except psycopg.Error as exc:
        raise DatabaseOperationError("Boru bilgileri alınamadı.") from exc


def list_gas_valves() -> list[dict[str, Any]]:
    query = f"SELECT {_gas_valve_columns()} FROM cbs.gas_valves ORDER BY valve_id;"

    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                return list(cur.fetchall())
    except psycopg.Error as exc:
        raise DatabaseOperationError("Vana bilgileri alınamadı.") from exc


def get_gas_pipe(feature_id: int) -> dict[str, Any]:
    return _get_gas_feature("cbs.gas_pipes", "pipe_id", _gas_pipe_columns(), feature_id)


def get_gas_valve(feature_id: int) -> dict[str, Any]:
    return _get_gas_feature("cbs.gas_valves", "valve_id", _gas_valve_columns(), feature_id)


def _regional_pipe_code_parts(code: str) -> tuple[str, int, int] | None:
    match = _REGIONAL_PIPE_CODE_RE.fullmatch(code.strip())
    if not match:
        return None
    sequence_text = match.group("number")
    return match.group("prefix"), int(sequence_text), len(sequence_text)


def _next_pipe_code(
    cur: psycopg.Cursor,
    prefix: str,
    minimum_width: int,
) -> str:
    cur.execute(
        "SELECT pipe_code FROM cbs.gas_pipes WHERE pipe_code LIKE %s;",
        (f"{prefix}-%",),
    )
    sequences = [
        parts[1]
        for row in cur.fetchall()
        if (parts := _regional_pipe_code_parts(str(row["pipe_code"]))) is not None
        and parts[0] == prefix
    ]
    sequence = max(sequences, default=0) + 1
    return f"{prefix}-{sequence:0{minimum_width}d}"


def suggest_gas_pipe_code(
    start_connection_type: str,
    start_connection_id: int,
) -> dict[str, Any]:
    basis_by_type = {
        "pipe_endpoint": "connected_pipe",
        "valve": "connected_valve",
        "junction": "junction_pipe",
    }
    if start_connection_type not in basis_by_type:
        raise InvalidFeatureInputError("Boru başlangıç bağlantı türü geçersiz.")

    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                if start_connection_type == "valve":
                    cur.execute(
                        """
SELECT p.pipe_code
FROM cbs.gas_valves v
JOIN cbs.gas_pipes p ON p.pipe_id = v.related_pipe_id
WHERE v.valve_id = %s
  AND v.related_pipe_id IS NOT NULL
  AND ST_DWithin(
      ST_Transform(v.geom, 32636),
      ST_Transform(p.geom, 32636),
      %s
  );
""",
                        (start_connection_id, PIPE_NETWORK_TOUCH_M),
                    )
                    row = cur.fetchone()
                    if row is None:
                        raise InvalidFeatureInputError(
                            "Seçilen vana mevcut bir boru hattına bağlı değil"
                        )
                else:
                    cur.execute(
                        "SELECT pipe_code FROM cbs.gas_pipes WHERE pipe_id = %s;",
                        (start_connection_id,),
                    )
                    row = cur.fetchone()
                    if row is None:
                        raise FeatureNotFoundError("Başlangıç bağlantısındaki boru bulunamadı.")

                connected_parts = _regional_pipe_code_parts(str(row["pipe_code"]))
                if connected_parts is not None:
                    # Bağlanılan hattın bölgesel prefix'i ve sayı genişliği yeni öneride korunur.
                    prefix, _, width = connected_parts
                    return {
                        "suggested_code": _next_pipe_code(cur, prefix, width),
                        "prefix": prefix,
                        "basis": basis_by_type[start_connection_type],
                        "message": None,
                    }

                cur.execute("SELECT pipe_code FROM cbs.gas_pipes;")
                candidates = [
                    parts
                    for code_row in cur.fetchall()
                    if (parts := _regional_pipe_code_parts(str(code_row["pipe_code"]))) is not None
                ]
                if not candidates:
                    return {
                        "suggested_code": None,
                        "prefix": None,
                        "basis": "none",
                        "message": "Otomatik bölgesel kod oluşturulamadı; geçerli bir boru kodu girin.",
                    }
                counts = Counter((prefix, width) for prefix, _, width in candidates)
                # Bağlantı kodu bölgesel değilse mevcut ağdaki en yaygın güvenli biçim yalnız öneri olur.
                prefix, width = sorted(
                    counts,
                    key=lambda item: (-counts[item], item[0], -item[1]),
                )[0]
                return {
                    "suggested_code": _next_pipe_code(cur, prefix, width),
                    "prefix": prefix,
                    "basis": "dominant_network",
                    "message": "Bağlantı kodundan bölge belirlenemedi; ağdaki baskın biçim önerildi.",
                }
    except (FeatureNotFoundError, InvalidFeatureInputError):
        raise
    except psycopg.Error as exc:
        raise DatabaseOperationError("Boru kodu önerisi oluşturulamadı.") from exc


def _valve_code_parts(code: str) -> tuple[str, int, int] | None:
    match = _NETWORK_VALVE_CODE_RE.fullmatch(code.strip())
    if not match:
        return None
    sequence_text = match.group("number")
    return match.group("region"), int(sequence_text), len(sequence_text)


def _next_valve_code(
    cur: psycopg.Cursor,
    region_prefix: str,
    minimum_width: int,
) -> str:
    cur.execute(
        "SELECT valve_code FROM cbs.gas_valves WHERE valve_code LIKE %s;",
        (f"{region_prefix}-V-%",),
    )
    sequences = [
        parts[1]
        for row in cur.fetchall()
        if (parts := _valve_code_parts(str(row["valve_code"]))) is not None
        and parts[0] == region_prefix
    ]
    sequence = max(sequences, default=0) + 1
    return f"{region_prefix}-V-{sequence:0{minimum_width}d}"


def suggest_gas_valve_code(related_pipe_id: int) -> dict[str, Any]:
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT pipe_code FROM cbs.gas_pipes WHERE pipe_id = %s;",
                    (related_pipe_id,),
                )
                pipe = cur.fetchone()
                if pipe is None:
                    raise FeatureNotFoundError("Bağlı boru bulunamadı.")

                pipe_match = _NETWORK_PIPE_CODE_RE.fullmatch(str(pipe["pipe_code"]).strip())
                cur.execute("SELECT valve_code FROM cbs.gas_valves;")
                candidates = [
                    parts
                    for row in cur.fetchall()
                    if (parts := _valve_code_parts(str(row["valve_code"]))) is not None
                ]
                if pipe_match is not None:
                    region_prefix = pipe_match.group("region")
                    regional_candidates = [
                        parts for parts in candidates if parts[0] == region_prefix
                    ]
                    if regional_candidates:
                        # P→V dönüşümü tahminle yapılmaz; yalnız aynı bölgedeki gerçek
                        # vana kodları bu ilişkiyi doğruluyorsa bağlı boru dayanak olur.
                        widths = Counter(parts[2] for parts in regional_candidates)
                        width = sorted(widths, key=lambda item: (-widths[item], -item))[0]
                        return {
                            "suggested_code": _next_valve_code(cur, region_prefix, width),
                            "region_prefix": region_prefix,
                            "related_pipe_id": related_pipe_id,
                            "basis": "related_pipe",
                            "message": None,
                        }

                if not candidates:
                    return {
                        "suggested_code": None,
                        "region_prefix": None,
                        "related_pipe_id": related_pipe_id,
                        "basis": "none",
                        "message": (
                            "Otomatik vana kodu oluşturulamadı. "
                            "Geçerli ve benzersiz bir vana kodu girin."
                        ),
                    }
                counts = Counter((region, width) for region, _, width in candidates)
                region_prefix, width = sorted(
                    counts,
                    key=lambda item: (-counts[item], item[0], -item[1]),
                )[0]
                return {
                    "suggested_code": _next_valve_code(cur, region_prefix, width),
                    "region_prefix": region_prefix,
                    "related_pipe_id": related_pipe_id,
                    "basis": "dominant_network",
                    "message": (
                        "Bağlı boru kodundan bölge belirlenemedi; "
                        "ağdaki baskın vana biçimi yalnız öneri olarak kullanıldı."
                    ),
                }
    except FeatureNotFoundError:
        raise
    except psycopg.Error as exc:
        raise DatabaseOperationError("Vana kodu önerisi oluşturulamadı.") from exc


def _get_gas_feature(table: str, id_column: str, columns: str, feature_id: int) -> dict[str, Any]:
    query = f"SELECT {columns} FROM {table} WHERE {id_column} = %s;"
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (feature_id,))
                row = cur.fetchone()
    except psycopg.Error as exc:
        raise DatabaseOperationError("Gaz altyapı kaydı okunamadı.") from exc
    if row is None:
        raise FeatureNotFoundError("Gaz altyapı kaydı bulunamadı.")
    return dict(row)


def create_gas_pipe(
    payload: Mapping[str, Any],
    *,
    source: str = "user_created_stage4",
) -> dict[str, Any]:
    """Yol tabanlı, ağa bağlı EPSG:3857 rotayı doğrulayıp tek transaction'da ekler."""
    if source not in _STAGE4_SOURCES:
        raise InvalidFeatureInputError("Stage 4 kayıt kaynağı geçersiz.")
    geom_wkt = ensure_finite_wkt(str(payload["geom_wkt"]))
    if get_wkt_type(geom_wkt) != "LINESTRING":
        raise InvalidFeatureInputError("Boru geometrisi tek parçalı LINESTRING olmalıdır.")
    try:
        validate_pipe_topology(parse_linestring_wkt(geom_wkt))
    except TopologyValidationError as exc:
        raise InvalidFeatureInputError(str(exc)) from exc

    params = dict(payload)
    params["status"] = to_storage_status("pipe", params["status"])
    code = str(payload["pipe_code"]).strip()
    params.update({
        "geom_wkt": geom_wkt,
        "source": source,
        "pipe_code": code,
        "pipe_network_touch_m": PIPE_NETWORK_TOUCH_M,
    })
    # ST_GeomFromText WKT'yi PostGIS geometrisine çevirir; sorgu LINESTRING'in
    # geçerliliğini, uzunluğunu ve mevcut ağla çakışmasını inceler.
    analysis_query = """
WITH raw AS (
    SELECT ST_GeomFromText(%(geom_wkt)s, 3857)::geometry(LineString, 3857) AS geom
), metric AS (
    SELECT geom, ST_Transform(geom, 32636) AS geom_metric FROM raw
)
SELECT
    ST_IsValid(geom) AS is_valid,
    ST_IsSimple(geom) AS is_simple,
    ST_NPoints(geom) AS point_count,
    ST_Length(geom_metric) AS length_m,
    CASE %(start_connection_type)s
        WHEN 'pipe_endpoint' THEN EXISTS (
            SELECT 1
            FROM cbs.gas_pipes p
            WHERE p.pipe_id = %(start_connection_id)s
              AND ST_DWithin(
                  ST_StartPoint(metric.geom_metric),
                  ST_Transform(ST_Boundary(p.geom), 32636),
                  %(pipe_network_touch_m)s
              )
        )
        WHEN 'valve' THEN EXISTS (
            SELECT 1
            FROM cbs.gas_valves v
            JOIN cbs.gas_pipes p ON p.pipe_id = v.related_pipe_id
            WHERE v.valve_id = %(start_connection_id)s
              AND v.related_pipe_id IS NOT NULL
              AND ST_DWithin(
                  ST_Transform(v.geom, 32636),
                  ST_Transform(p.geom, 32636),
                  %(pipe_network_touch_m)s
              )
              AND ST_DWithin(
                  ST_StartPoint(metric.geom_metric),
                  ST_Transform(v.geom, 32636),
                  %(pipe_network_touch_m)s
              )
        )
        WHEN 'junction' THEN EXISTS (
            SELECT 1
            FROM cbs.gas_pipes first_pipe
            JOIN cbs.gas_pipes second_pipe
              ON second_pipe.pipe_id <> first_pipe.pipe_id
             AND ST_Intersects(first_pipe.geom, second_pipe.geom)
            WHERE first_pipe.pipe_id = %(start_connection_id)s
              AND NOT ST_IsEmpty(
                  ST_CollectionExtract(
                      ST_Intersection(first_pipe.geom, second_pipe.geom),
                      1
                  )
              )
              AND ST_DWithin(
                  ST_StartPoint(metric.geom_metric),
                  ST_Transform(
                      ST_CollectionExtract(
                          ST_Intersection(first_pipe.geom, second_pipe.geom),
                          1
                      ),
                      32636
                  ),
                  %(pipe_network_touch_m)s
              )
        )
        ELSE FALSE
    END AS has_valid_start,
    EXISTS (
        SELECT 1
        FROM cbs.gas_pipes p
        WHERE p.geom && metric.geom
          AND ST_Equals(p.geom, metric.geom)
    ) AS has_duplicate,
    EXISTS (
        SELECT 1
        FROM cbs.gas_pipes p
        WHERE p.geom && ST_Expand(metric.geom, 3)
          AND ST_Length(
              ST_CollectionExtract(
                  ST_Intersection(metric.geom_metric, ST_Transform(p.geom, 32636)), 2
              )
          ) > 0.50
    ) AS has_linear_overlap
FROM metric;
"""
    # INSERT yeni kaydı ekler. İsimli parametreler değerleri SQL metninden ayrı
    # taşıyarak SQL enjeksiyonu riskini azaltır.
    insert_query = f"""
WITH new_geom AS (
    SELECT ST_Multi(ST_GeomFromText(%(geom_wkt)s, 3857))::geometry(MultiLineString, 3857) AS geom
)
INSERT INTO cbs.gas_pipes (
    pipe_code, pipe_type, diameter_mm, material, pressure_level,
    operating_pressure_bar, status, install_year, source, operator_name, geom
)
-- operator_name ayrı kolonda kalıcı saklanır; source veri kökeni anlamını korur.
SELECT
    %(pipe_code)s, %(pipe_type)s, %(diameter_mm)s, %(material)s, %(pressure_level)s,
    %(operating_pressure_bar)s, %(status)s, %(install_year)s, %(source)s, %(operator_name)s, geom
FROM new_geom
RETURNING {_gas_pipe_columns()};
"""
    try:
        with _connect() as conn:
            # Transaction: adımların tamamı başarılı olur veya hiçbiri kalıcı olmaz.
            # Advisory lock: eşzamanlı isteklerin aynı kodu üretmesini önler.
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s));", (f"cbs.gas_pipes:{code}",))
                    cur.execute("SELECT 1 FROM cbs.gas_pipes WHERE pipe_code = %s;", (code,))
                    if cur.fetchone() is not None:
                        raise CodeConflictError(
                            "Bu boru kodu başka bir kayıtta kullanılıyor.",
                            code="PIPE_CODE_CONFLICT",
                        )
                    cur.execute("SELECT pg_advisory_xact_lock(hashtext('cbs.gas_pipes:stage4_topology'));" )
                    cur.execute(analysis_query, params)
                    analysis = cur.fetchone()
                    if not analysis or not analysis["is_valid"]:
                        raise InvalidFeatureInputError("Boru geometrisi geçersiz.")
                    if not analysis["is_simple"]:
                        raise InvalidFeatureInputError("Boru kendi kendini kesemez.")
                    if analysis["point_count"] < 2:
                        raise InvalidFeatureInputError("Boru en az iki koordinat içermelidir.")
                    if not analysis["has_valid_start"]:
                        if params["start_connection_type"] == "valve":
                            raise InvalidFeatureInputError(
                                "Seçilen vana mevcut bir boru hattına bağlı değil"
                            )
                        raise InvalidFeatureInputError(
                            "Yeni boru mevcut bir boru ucuna veya gerçek kavşağa bağlı başlamalıdır."
                        )
                    if analysis["has_duplicate"]:
                        raise TopologyConflictError("Aynı boru tekrar oluşturulamaz.")
                    if analysis["has_linear_overlap"]:
                        raise TopologyConflictError("Boru mevcut bir hatla yinelenemez veya doğrusal çakışamaz.")
                    cur.execute(insert_query, params)
                    row = cur.fetchone()
                    if row is None:
                        raise InvalidFeatureInputError("Boru kaydı oluşturulamadı.")
                    return dict(row)
    except (CodeConflictError, InvalidFeatureInputError, TopologyConflictError):
        raise
    except psycopg.OperationalError as exc:
        raise DatabaseOperationError("Veritabanı bağlantısı kurulamadı.") from exc
    except psycopg.Error as exc:
        raise InvalidFeatureInputError("Boru geometrisi veya öznitelikleri veritabanı sözleşmesine uymuyor.") from exc


def create_gas_valve(
    payload: Mapping[str, Any],
    *,
    source: str = "user_created_stage4",
) -> dict[str, Any]:
    """Yaklaşık tıklamayı en yakın boruya sunucu tarafında yakalayıp vana ekler."""
    if source not in _STAGE4_SOURCES:
        raise InvalidFeatureInputError("Stage 4 kayıt kaynağı geçersiz.")
    geom_wkt = ensure_wkt_type(ensure_finite_wkt(str(payload["geom_wkt"])), "POINT")
    try:
        parse_point_wkt(geom_wkt)
    except TopologyValidationError as exc:
        raise InvalidFeatureInputError(str(exc)) from exc

    params = dict(payload)
    params["status"] = to_storage_status("valve", params["status"])
    code = str(payload["valve_code"]).strip()
    params.update({
        "geom_wkt": geom_wkt,
        "source": source,
        "valve_code": code,
    })
    # Vana POINT, boru LINESTRING/MULTILINESTRING türündedir. Bu sorgu noktayı
    # en yakın borunun üzerine yaklaştırılacak (snap) konuma hesaplar.
    nearest_query = """
WITH input AS (
    SELECT ST_Transform(ST_GeomFromText(%(geom_wkt)s, 3857), 32636) AS geom_metric
), candidates AS (
    SELECT
        p.pipe_id, p.pipe_code, p.diameter_mm,
        ST_Distance(input.geom_metric, ST_Transform(p.geom, 32636)) AS distance_m,
        ST_ClosestPoint(ST_Transform(p.geom, 32636), input.geom_metric) AS snapped_metric
    FROM cbs.gas_pipes p, input
)
SELECT pipe_id, pipe_code, diameter_mm, distance_m,
       ST_AsText(ST_Transform(snapped_metric, 3857)) AS snapped_wkt
FROM candidates
ORDER BY distance_m, pipe_id
LIMIT 1;
"""
    # Yaklaşık tıklama en yakın boruda ST_ClosestPoint ile tam geometri üzerine taşınır.
    spacing_query = """
WITH snapped AS (
    SELECT ST_Transform(ST_GeomFromText(%(snapped_wkt)s, 3857), 32636) AS geom_metric
)
SELECT v.valve_id, ST_Distance(ST_Transform(v.geom, 32636), snapped.geom_metric) AS distance_m
FROM cbs.gas_valves v, snapped
ORDER BY distance_m, v.valve_id
LIMIT 1;
"""
    insert_query = f"""
WITH new_geom AS (
    SELECT ST_GeomFromText(%(snapped_wkt)s, 3857)::geometry(Point, 3857) AS geom
)
INSERT INTO cbs.gas_valves (
    valve_code, valve_type, diameter_mm, material, status,
    install_year, related_pipe_id, source, operator_name, geom
)
SELECT
    %(valve_code)s, %(valve_type)s, %(diameter_mm)s, %(material)s, %(status)s,
    %(install_year)s, %(related_pipe_id)s, %(source)s, %(operator_name)s, geom
FROM new_geom
RETURNING {_gas_valve_columns()};
"""
    try:
        with _connect() as conn:
            # Transaction ve advisory lock, eşzamanlı isteklerde kod ve vana
            # aralığı kurallarının birlikte güvenli biçimde uygulanmasını sağlar.
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s));", (f"cbs.gas_valves:{code}",))
                    cur.execute("SELECT 1 FROM cbs.gas_valves WHERE valve_code = %s;", (code,))
                    if cur.fetchone() is not None:
                        raise CodeConflictError(
                            "Bu vana kodu başka bir kayıtta kullanılıyor.",
                            code="VALVE_CODE_CONFLICT",
                        )
                    cur.execute("SELECT pg_advisory_xact_lock(hashtext('cbs.gas_valves:stage4_spacing'));" )
                    cur.execute(nearest_query, params)
                    nearest = cur.fetchone()
                    if nearest is None or nearest["distance_m"] > VALVE_MAX_SNAP_M:
                        raise InvalidFeatureInputError(
                            f"Vana mevcut bir gaz borusuna en fazla {VALVE_MAX_SNAP_M:.0f} m uzakta olabilir."
                        )
                    try:
                        validate_point_topology(parse_point_wkt(nearest["snapped_wkt"]))
                    except TopologyValidationError as exc:
                        raise InvalidFeatureInputError(str(exc)) from exc
                    params.update({
                        "snapped_wkt": nearest["snapped_wkt"],
                        "related_pipe_id": nearest["pipe_id"],
                        "diameter_mm": nearest["diameter_mm"],
                    })
                    cur.execute(spacing_query, params)
                    closest_valve = cur.fetchone()
                    if closest_valve is not None and closest_valve["distance_m"] < VALVE_MIN_SPACING_M:
                        raise TopologyConflictError(
                            f"Yeni vana mevcut vana {closest_valve['valve_id']} kaydına en az {VALVE_MIN_SPACING_M:.0f} m uzakta olmalıdır."
                        )
                    cur.execute(insert_query, params)
                    row = cur.fetchone()
                    if row is None:
                        raise InvalidFeatureInputError("Vana kaydı oluşturulamadı.")
                    return dict(row)
    except (CodeConflictError, InvalidFeatureInputError, TopologyConflictError):
        raise
    except psycopg.OperationalError as exc:
        raise DatabaseOperationError("Veritabanı bağlantısı kurulamadı.") from exc
    except psycopg.Error as exc:
        raise InvalidFeatureInputError("Vana geometrisi veya öznitelikleri veritabanı sözleşmesine uymuyor.") from exc


def _create_gas_feature(
    table: str,
    code_column: str,
    payload: Mapping[str, Any],
    geom_wkt: str,
    query: str,
) -> dict[str, Any]:
    params = dict(payload)
    params["geom_wkt"] = geom_wkt
    code = str(payload[code_column]).strip()
    try:
        with _connect() as conn:
            # Kod kontrolü ve INSERT aynı advisory lock altında yarış koşuluna kapatılır.
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s));", (f"{table}:{code}",))
                    cur.execute(f"SELECT 1 FROM {table} WHERE {code_column} = %s;", (code,))
                    if cur.fetchone() is not None:
                        raise CodeConflictError(f"{code_column} değeri zaten kullanılıyor.")
                    cur.execute(query, params)
                    row = cur.fetchone()
                    if row is None:
                        raise InvalidFeatureInputError("Geometri veya bağlı boru geçersiz.")
                    return dict(row)
    except (CodeConflictError, InvalidFeatureInputError):
        raise
    except psycopg.OperationalError as exc:
        raise DatabaseOperationError("Veritabanı bağlantısı kurulamadı.") from exc
    except psycopg.Error as exc:
        raise InvalidFeatureInputError("Gaz altyapı kaydı veritabanı sözleşmesine uymuyor.") from exc


def _ensure_mutable_source(source: object) -> None:
    if source not in _STAGE4_SOURCES:
        raise UnsafeFeatureDeleteError(
            "Bu kayıt temel demo verisine aittir ve değiştirilemez."
        )


def update_gas_pipe(feature_id: int, payload: Mapping[str, Any]) -> dict[str, Any]:
    if feature_id in _PROTECTED_PIPE_IDS:
        raise UnsafeFeatureDeleteError("Korunan Stage 4 boru kaydı değiştirilemez.")
    changes = dict(payload)
    replace_geometry = "geom_wkt" in changes

    try:
        with _connect() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
SELECT {_gas_pipe_columns()}
FROM cbs.gas_pipes
WHERE pipe_id = %s
FOR UPDATE;
""",
                        (feature_id,),
                    )
                    current = cur.fetchone()
                    if current is None:
                        raise FeatureNotFoundError("Düzenlenmek istenen boru bulunamadı.")
                    _ensure_mutable_source(current["source"])

                    params = dict(current)
                    params.update(changes)
                    params["feature_id"] = feature_id
                    params["allowed_sources"] = list(_STAGE4_SOURCES)
                    params["pipe_code"] = str(params["pipe_code"]).strip()
                    params["operator_name"] = (
                        str(params["operator_name"]).strip()
                        if params["operator_name"] is not None
                        else None
                    )
                    params["status"] = (
                        to_storage_status("pipe", changes["status"])
                        if "status" in changes
                        else current["status"]
                    )
                    try:
                        validate_pipe_attribute_compatibility(
                            str(params["pipe_type"]),
                            int(params["diameter_mm"]),
                            str(params["material"]),
                            str(params["pressure_level"]),
                            Decimal(params["operating_pressure_bar"]),
                        )
                    except (TypeError, ValueError) as exc:
                        raise InvalidFeatureInputError(str(exc)) from exc

                    if "pipe_code" in changes:
                        # Önerilen veya manuel bütün kodlar transaction kilidi altında
                        # yeniden aranır; iki eşzamanlı PATCH aynı kodu alamaz.
                        cur.execute(
                            "SELECT pg_advisory_xact_lock(hashtext(%s));",
                            (f"cbs.gas_pipes:{params['pipe_code']}",),
                        )
                        cur.execute(
                            """
SELECT 1
FROM cbs.gas_pipes
WHERE pipe_code = %s AND pipe_id <> %s;
""",
                            (params["pipe_code"], feature_id),
                        )
                        if cur.fetchone() is not None:
                            raise CodeConflictError(
                                "Bu boru kodu başka bir kayıtta kullanılıyor.",
                                code="PIPE_CODE_CONFLICT",
                            )

                    if replace_geometry:
                        geom_wkt = ensure_finite_wkt(str(params["geom_wkt"]))
                        if get_wkt_type(geom_wkt) != "LINESTRING":
                            raise InvalidFeatureInputError(
                                "Boru geometrisi tek parçalı LINESTRING olmalıdır."
                            )
                        try:
                            validate_pipe_topology(parse_linestring_wkt(geom_wkt))
                        except TopologyValidationError as exc:
                            raise InvalidFeatureInputError(str(exc)) from exc
                        params["geom_wkt"] = geom_wkt
                        params["pipe_network_touch_m"] = PIPE_NETWORK_TOUCH_M
                        cur.execute(
                            "SELECT pg_advisory_xact_lock(hashtext('cbs.gas_pipes:stage4_topology'));"
                        )
                        # Düzenlenen borunun eski geometrisi duplicate/çakışma hesabından
                        # çıkarılır; yeni rota diğer bütün ağ elemanlarına karşı denetlenir.
                        cur.execute(
                            """
WITH raw AS (
    SELECT ST_GeomFromText(%(geom_wkt)s, 3857)::geometry(LineString, 3857) AS geom
), metric AS (
    SELECT geom, ST_Transform(geom, 32636) AS geom_metric FROM raw
)
SELECT
    ST_IsValid(geom) AS is_valid,
    ST_IsSimple(geom) AS is_simple,
    ST_NPoints(geom) AS point_count,
    CASE %(start_connection_type)s
        WHEN 'pipe_endpoint' THEN EXISTS (
            SELECT 1
            FROM cbs.gas_pipes p
            WHERE p.pipe_id = %(start_connection_id)s
              AND p.pipe_id <> %(feature_id)s
              AND ST_DWithin(
                  ST_StartPoint(metric.geom_metric),
                  ST_Transform(ST_Boundary(p.geom), 32636),
                  %(pipe_network_touch_m)s
              )
        )
        WHEN 'valve' THEN EXISTS (
            SELECT 1
            FROM cbs.gas_valves v
            JOIN cbs.gas_pipes p ON p.pipe_id = v.related_pipe_id
            WHERE v.valve_id = %(start_connection_id)s
              AND p.pipe_id <> %(feature_id)s
              AND ST_DWithin(
                  ST_Transform(v.geom, 32636),
                  ST_Transform(p.geom, 32636),
                  %(pipe_network_touch_m)s
              )
              AND ST_DWithin(
                  ST_StartPoint(metric.geom_metric),
                  ST_Transform(v.geom, 32636),
                  %(pipe_network_touch_m)s
              )
        )
        WHEN 'junction' THEN EXISTS (
            SELECT 1
            FROM cbs.gas_pipes first_pipe
            JOIN cbs.gas_pipes second_pipe
              ON second_pipe.pipe_id <> first_pipe.pipe_id
             AND ST_Intersects(first_pipe.geom, second_pipe.geom)
            WHERE first_pipe.pipe_id = %(start_connection_id)s
              AND first_pipe.pipe_id <> %(feature_id)s
              AND second_pipe.pipe_id <> %(feature_id)s
              AND ST_DWithin(
                  ST_StartPoint(metric.geom_metric),
                  ST_Transform(
                      ST_CollectionExtract(
                          ST_Intersection(first_pipe.geom, second_pipe.geom), 1
                      ),
                      32636
                  ),
                  %(pipe_network_touch_m)s
              )
        )
        ELSE FALSE
    END AS has_valid_start,
    EXISTS (
        SELECT 1 FROM cbs.gas_pipes p
        WHERE p.pipe_id <> %(feature_id)s
          AND p.geom && metric.geom
          AND ST_Equals(p.geom, metric.geom)
    ) AS has_duplicate,
    EXISTS (
        SELECT 1 FROM cbs.gas_pipes p
        WHERE p.pipe_id <> %(feature_id)s
          AND p.geom && ST_Expand(metric.geom, 3)
          AND ST_Length(
              ST_CollectionExtract(
                  ST_Intersection(metric.geom_metric, ST_Transform(p.geom, 32636)), 2
              )
          ) > 0.50
    ) AS has_linear_overlap
FROM metric;
""",
                            params,
                        )
                        analysis = cur.fetchone()
                        if not analysis or not analysis["is_valid"]:
                            raise InvalidFeatureInputError("Boru geometrisi geçersiz.")
                        if not analysis["is_simple"] or analysis["point_count"] < 2:
                            raise InvalidFeatureInputError(
                                "Boru geometrisi basit ve en az iki koordinatlı olmalıdır."
                            )
                        if not analysis["has_valid_start"]:
                            raise InvalidFeatureInputError(
                                "Yeni güzergâh başka bir bağlı vana, boru ucu veya kavşaktan başlamalıdır."
                            )
                        if analysis["has_duplicate"] or analysis["has_linear_overlap"]:
                            raise TopologyConflictError(
                                "Yeni güzergâh mevcut bir boruyla yinelenemez veya doğrusal çakışamaz."
                            )

                    geometry_assignment = (
                        """
geom = ST_Multi(
    ST_GeomFromText(%(geom_wkt)s, 3857)
)::geometry(MultiLineString, 3857),
"""
                        if replace_geometry
                        else ""
                    )
                    cur.execute(
                        # Sabit alan allowlist'i ID, source ve teknik kolonların PATCH
                        # gövdesiyle değiştirilmesini engeller.
                        f"""
UPDATE cbs.gas_pipes
SET
    pipe_code = %(pipe_code)s,
    pipe_type = %(pipe_type)s,
    diameter_mm = %(diameter_mm)s,
    material = %(material)s,
    pressure_level = %(pressure_level)s,
    operating_pressure_bar = %(operating_pressure_bar)s,
    status = %(status)s,
    install_year = %(install_year)s,
    operator_name = %(operator_name)s,
    {geometry_assignment}
    source = source
WHERE pipe_id = %(feature_id)s
  AND source = ANY(%(allowed_sources)s)
RETURNING {_gas_pipe_columns()};
""",
                        params,
                    )
                    row = cur.fetchone()
                    if row is None:
                        raise UnsafeFeatureDeleteError(
                            "Stage 4 kaynak doğrulaması başarısız oldu."
                        )
                    return dict(row)
    except (
        CodeConflictError,
        FeatureNotFoundError,
        InvalidFeatureInputError,
        TopologyConflictError,
        UnsafeFeatureDeleteError,
    ):
        raise
    except psycopg.OperationalError as exc:
        raise DatabaseOperationError("Veritabanı bağlantısı kurulamadı.") from exc
    except psycopg.Error as exc:
        raise InvalidFeatureInputError(
            "Boru değişiklikleri veritabanı sözleşmesine uymuyor."
        ) from exc


def update_gas_valve(feature_id: int, payload: Mapping[str, Any]) -> dict[str, Any]:
    changes = dict(payload)
    replace_geometry = "geom_wkt" in changes

    try:
        with _connect() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
SELECT {_gas_valve_columns()}
FROM cbs.gas_valves
WHERE valve_id = %s
FOR UPDATE;
""",
                        (feature_id,),
                    )
                    current = cur.fetchone()
                    if current is None:
                        raise FeatureNotFoundError("Düzenlenmek istenen vana bulunamadı.")
                    _ensure_mutable_source(current["source"])

                    params = dict(current)
                    params.update(changes)
                    params["feature_id"] = feature_id
                    params["allowed_sources"] = list(_STAGE4_SOURCES)
                    params["valve_code"] = str(params["valve_code"]).strip()
                    params["operator_name"] = (
                        str(params["operator_name"]).strip()
                        if params["operator_name"] is not None
                        else None
                    )
                    params["status"] = (
                        to_storage_status("valve", changes["status"])
                        if "status" in changes
                        else current["status"]
                    )

                    if "valve_code" in changes:
                        # Vana kodu önerisi yalnız kullanıcı kolaylığıdır; kesin
                        # benzersizlik kararı her zaman bu backend kilidinde verilir.
                        cur.execute(
                            "SELECT pg_advisory_xact_lock(hashtext(%s));",
                            (f"cbs.gas_valves:{params['valve_code']}",),
                        )
                        cur.execute(
                            """
SELECT 1
FROM cbs.gas_valves
WHERE valve_code = %s AND valve_id <> %s;
""",
                            (params["valve_code"], feature_id),
                        )
                        if cur.fetchone() is not None:
                            suggestion = suggest_gas_valve_code(
                                int(current["related_pipe_id"])
                            )
                            raise CodeConflictError(
                                "Bu vana kodu başka bir kayıtta kullanılıyor.",
                                code="VALVE_CODE_CONFLICT",
                                suggested_code=suggestion["suggested_code"],
                            )

                    if replace_geometry:
                        geom_wkt = ensure_wkt_type(
                            ensure_finite_wkt(str(params["geom_wkt"])),
                            "POINT",
                        )
                        try:
                            parse_point_wkt(geom_wkt)
                        except TopologyValidationError as exc:
                            raise InvalidFeatureInputError(str(exc)) from exc
                        params["geom_wkt"] = geom_wkt
                        cur.execute(
                            "SELECT pg_advisory_xact_lock(hashtext('cbs.gas_valves:stage4_spacing'));"
                        )
                        cur.execute(
                            """
WITH input AS (
    SELECT ST_Transform(
        ST_GeomFromText(%(geom_wkt)s, 3857), 32636
    ) AS geom_metric
)
SELECT
    p.pipe_id,
    p.diameter_mm,
    ST_Distance(input.geom_metric, ST_Transform(p.geom, 32636)) AS distance_m,
    ST_AsText(
        ST_Transform(
            ST_ClosestPoint(ST_Transform(p.geom, 32636), input.geom_metric),
            3857
        )
    ) AS snapped_wkt
FROM cbs.gas_pipes p, input
ORDER BY distance_m, p.pipe_id
LIMIT 1;
""",
                            params,
                        )
                        nearest = cur.fetchone()
                        if nearest is None or nearest["distance_m"] > VALVE_MAX_SNAP_M:
                            raise InvalidFeatureInputError(
                                "Vana mevcut bir boru hattının üzerinde olmalıdır."
                            )
                        try:
                            validate_point_topology(
                                parse_point_wkt(nearest["snapped_wkt"])
                            )
                        except TopologyValidationError as exc:
                            raise InvalidFeatureInputError(str(exc)) from exc
                        params.update(
                            {
                                "snapped_wkt": nearest["snapped_wkt"],
                                "related_pipe_id": nearest["pipe_id"],
                                "diameter_mm": nearest["diameter_mm"],
                            }
                        )
                        cur.execute(
                            # Mevcut vana aralık hesabından çıkarılır; aksi hâlde kendi
                            # eski konumu her geometri düzenlemesini 10 m kuralında reddeder.
                            """
WITH snapped AS (
    SELECT ST_Transform(
        ST_GeomFromText(%(snapped_wkt)s, 3857), 32636
    ) AS geom_metric
)
SELECT
    v.valve_id,
    ST_Distance(
        ST_Transform(v.geom, 32636), snapped.geom_metric
    ) AS distance_m
FROM cbs.gas_valves v, snapped
WHERE v.valve_id <> %(feature_id)s
ORDER BY distance_m, v.valve_id
LIMIT 1;
""",
                            params,
                        )
                        closest_valve = cur.fetchone()
                        if (
                            closest_valve is not None
                            and closest_valve["distance_m"] < VALVE_MIN_SPACING_M
                        ):
                            raise TopologyConflictError(
                                f"Vana mevcut vana {closest_valve['valve_id']} kaydına "
                                f"en az {VALVE_MIN_SPACING_M:.0f} m uzakta olmalıdır."
                            )

                    geometry_assignment = (
                        """
geom = ST_GeomFromText(
    %(snapped_wkt)s, 3857
)::geometry(Point, 3857),
diameter_mm = %(diameter_mm)s,
related_pipe_id = %(related_pipe_id)s,
"""
                        if replace_geometry
                        else ""
                    )
                    cur.execute(
                        f"""
UPDATE cbs.gas_valves
SET
    valve_code = %(valve_code)s,
    valve_type = %(valve_type)s,
    material = %(material)s,
    status = %(status)s,
    install_year = %(install_year)s,
    operator_name = %(operator_name)s,
    {geometry_assignment}
    source = source
WHERE valve_id = %(feature_id)s
  AND source = ANY(%(allowed_sources)s)
RETURNING {_gas_valve_columns()};
""",
                        params,
                    )
                    row = cur.fetchone()
                    if row is None:
                        raise UnsafeFeatureDeleteError(
                            "Stage 4 kaynak doğrulaması başarısız oldu."
                        )
                    return dict(row)
    except (
        CodeConflictError,
        FeatureNotFoundError,
        InvalidFeatureInputError,
        TopologyConflictError,
        UnsafeFeatureDeleteError,
    ):
        raise
    except psycopg.OperationalError as exc:
        raise DatabaseOperationError("Veritabanı bağlantısı kurulamadı.") from exc
    except psycopg.Error as exc:
        raise InvalidFeatureInputError(
            "Vana değişiklikleri veritabanı sözleşmesine uymuyor."
        ) from exc


def delete_gas_pipe(feature_id: int) -> None:
    if feature_id in _PROTECTED_PIPE_IDS:
        raise UnsafeFeatureDeleteError("Korunan Stage 4 boru kaydı silinemez.")
    _delete_gas_feature("cbs.gas_pipes", "pipe_id", feature_id, check_valves=True)


def delete_gas_valve(feature_id: int) -> None:
    _delete_gas_feature("cbs.gas_valves", "valve_id", feature_id, check_valves=False)


def _delete_gas_feature(table: str, id_column: str, feature_id: int, check_valves: bool) -> None:
    # DELETE yalnızca izin verilen kullanıcı kaydını kaldırır. %s yer tutucusu,
    # kimliği parametreli SQL olarak sorgu metninden ayrı gönderir.
    allowed_sources = ("user_created_stage4", "user_created_stage4_e2e")
    try:
        with _connect() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(f"SELECT source FROM {table} WHERE {id_column} = %s FOR UPDATE;", (feature_id,))
                    row = cur.fetchone()
                    if row is None:
                        raise FeatureNotFoundError("Gaz altyapı kaydı bulunamadı.")
                    if row["source"] not in allowed_sources:
                        # Hem ön kontrol hem DELETE koşulu, sentetik demo kayıtlarını iki kat korur.
                        raise UnsafeFeatureDeleteError("Yalnızca kullanıcı tarafından oluşturulan Stage 4 kayıtları silinebilir.")
                    if check_valves:
                        cur.execute(
                            "SELECT count(*) AS count FROM cbs.gas_valves WHERE related_pipe_id = %s;",
                            (feature_id,),
                        )
                        connected_valve_count = int(cur.fetchone()["count"])
                        if connected_valve_count:
                            # Cascade uygulanmaz; güvenli sıra önce bağlı vana, sonra
                            # borudur ve istemciye yalnız toplam bağlı kayıt sayısı verilir.
                            raise FeatureInUseError(
                                "Bu boruya bağlı vanalar bulunduğu için boru silinemez.",
                                connected_valve_count,
                            )
                    cur.execute(
                        f"DELETE FROM {table} WHERE {id_column} = %s AND source = ANY(%s) RETURNING {id_column};",
                        (feature_id, list(allowed_sources)),
                    )
                    if cur.fetchone() is None:
                        raise UnsafeFeatureDeleteError("Stage 4 kaynak doğrulaması başarısız oldu.")
    except (FeatureNotFoundError, UnsafeFeatureDeleteError, FeatureInUseError):
        raise
    except psycopg.Error as exc:
        raise DatabaseOperationError("Gaz altyapı kaydı silinemedi.") from exc


def get_gas_summary() -> dict[str, Any]:
    query = """
WITH pipe_counts AS (
    SELECT
        count(*) AS total,
        count(*) FILTER (WHERE lower(btrim(status)) = ANY(%(active_aliases)s)) AS aktif,
        count(*) FILTER (WHERE lower(btrim(status)) = ANY(%(inactive_aliases)s)) AS pasif,
        count(*) FILTER (WHERE lower(btrim(status)) = ANY(%(maintenance_aliases)s)) AS bakimda,
        count(*) FILTER (
            WHERE lower(btrim(status)) <> ALL(%(known_aliases)s)
               OR status IS NULL
               OR btrim(status) = ''
        ) AS bilinmeyen
    FROM cbs.gas_pipes
),
valve_counts AS (
    SELECT
        count(*) AS total,
        count(*) FILTER (WHERE lower(btrim(status)) = ANY(%(active_aliases)s)) AS aktif,
        count(*) FILTER (WHERE lower(btrim(status)) = ANY(%(inactive_aliases)s)) AS pasif,
        count(*) FILTER (WHERE lower(btrim(status)) = ANY(%(maintenance_aliases)s)) AS bakimda,
        count(*) FILTER (
            WHERE lower(btrim(status)) <> ALL(%(known_aliases)s)
               OR status IS NULL
               OR btrim(status) = ''
        ) AS bilinmeyen
    FROM cbs.gas_valves
)
SELECT
    pipe_counts.total AS pipe_total,
    pipe_counts.aktif AS pipe_aktif,
    pipe_counts.pasif AS pipe_pasif,
    pipe_counts.bakimda AS pipe_bakimda,
    pipe_counts.bilinmeyen AS pipe_bilinmeyen,
    valve_counts.total AS valve_total,
    valve_counts.aktif AS valve_aktif,
    valve_counts.pasif AS valve_pasif,
    valve_counts.bakimda AS valve_bakimda,
    valve_counts.bilinmeyen AS valve_bilinmeyen
FROM pipe_counts, valve_counts;
"""

    aliases = {
        "active_aliases": list(DATABASE_STATUS_ALIASES["aktif"]),
        "inactive_aliases": list(DATABASE_STATUS_ALIASES["pasif"]),
        "maintenance_aliases": list(DATABASE_STATUS_ALIASES["bakımda"]),
        "known_aliases": [
            alias
            for values in DATABASE_STATUS_ALIASES.values()
            for alias in values
        ],
    }
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query, aliases)
                row = cur.fetchone()
    except psycopg.Error as exc:
        raise DatabaseOperationError("Gaz altyapı özeti okunamadı.") from exc

    return {
        "pipes": {
            "total": row["pipe_total"],
            "aktif": row["pipe_aktif"],
            "pasif": row["pipe_pasif"],
            "bakimda": row["pipe_bakimda"],
            "bilinmeyen": row["pipe_bilinmeyen"],
            "tamirde": row["pipe_bakimda"],
        },
        "valves": {
            "total": row["valve_total"],
            "aktif": row["valve_aktif"],
            "pasif": row["valve_pasif"],
            "bakimda": row["valve_bakimda"],
            "bilinmeyen": row["valve_bilinmeyen"],
            "acik": row["valve_aktif"],
            "kapali": row["valve_pasif"],
        },
    }


def get_feature(kind: str, feature_id: int) -> dict[str, Any]:
    spec = SPECS[kind]
    query = f"SELECT {_select_columns()} FROM {spec.table} WHERE id = %s;"

    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (feature_id,))
                row = cur.fetchone()
    except psycopg.Error as exc:
        raise DatabaseOperationError("Veritabanı kaydı okunamadı.") from exc

    if row is None:
        raise FeatureNotFoundError(f"{kind} kaydı bulunamadı.")
    return dict(row)


def create_feature(kind: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    spec = SPECS[kind]
    try:
        geom_wkt = ensure_wkt_type(str(payload["geom_wkt"]), spec.expected_type)
    except ValueError as exc:
        raise InvalidFeatureInputError(str(exc)) from exc

    # ST_GeomFromText WKT'yi geometriye çevirir; ST_SetSRID EPSG:3857 bilgisini
    # atar. GeometryType, POINT ve LINESTRING ayrımının doğru olduğunu kontrol eder.
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
                            f"geom_wkt alanı {spec.expected_type} geometrisi olmalıdır."
                        )
                    return dict(row)
    except InvalidFeatureInputError:
        raise
    except psycopg.errors.CheckViolation as exc:
        raise InvalidFeatureInputError("cap sıfırdan büyük olmalıdır.") from exc
    except psycopg.OperationalError as exc:
        raise DatabaseOperationError("Veritabanı bağlantısı kurulamadı.") from exc
    except psycopg.Error as exc:
        raise InvalidFeatureInputError(
            f"geom_wkt EPSG:3857 içinde geçerli bir {spec.expected_type} WKT olmalıdır."
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
        raise DatabaseOperationError("Veritabanı kaydı silinemedi.") from exc

    if row is None:
        raise FeatureNotFoundError(f"{kind} kaydı bulunamadı.")
