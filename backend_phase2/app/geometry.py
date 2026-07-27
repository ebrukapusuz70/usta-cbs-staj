"""WKT geometrisinin türünü ve koordinatlarını kontrol eder.
Vana için POINT, boru için LINESTRING türünü doğrular.
Geçersiz geometri metinlerini veritabanına ulaşmadan durdurur.
"""

from __future__ import annotations

import re


_WKT_TYPE_RE = re.compile(r"^\s*([A-Za-z]+)\s*(?:\(|EMPTY\b)", re.IGNORECASE)
_NON_FINITE_RE = re.compile(r"(?:^|[^A-Za-z])(?:NaN|Inf|Infinity)(?:$|[^A-Za-z])", re.IGNORECASE)


class GeometryValidationError(ValueError):
    """Raised when incoming WKT does not match the required geometry rule."""


def get_wkt_type(geom_wkt: str) -> str:
    # Düzenli ifade (regular expression), metnin başındaki POINT veya
    # LINESTRING gibi teknik geometri türünü bulur.
    value = geom_wkt.strip()
    if not value:
        raise GeometryValidationError("geom_wkt is required.")
    if value.upper().startswith("SRID="):
        raise GeometryValidationError("geom_wkt alanı SRID ön eki içermemelidir.")

    match = _WKT_TYPE_RE.match(value)
    if not match:
        raise GeometryValidationError("geom_wkt geçerli bir WKT metni olmalıdır.")
    return match.group(1).upper()


def ensure_wkt_type(geom_wkt: str, expected_type: str) -> str:
    # Tür uyuşmazlığını kayıt veritabanına gitmeden önce anlaşılır hataya çevirir.
    actual_type = get_wkt_type(geom_wkt)
    expected = expected_type.upper()
    if actual_type != expected:
        raise GeometryValidationError(
            f"geom_wkt {expected} geometrisi olmalıdır; gelen tür {actual_type}."
        )
    return geom_wkt.strip()


def ensure_finite_wkt(geom_wkt: str) -> str:
    """NaN ve sonsuz koordinatların PostGIS'e ulaşmasını engeller."""
    value = geom_wkt.strip()
    if _NON_FINITE_RE.search(value):
        raise GeometryValidationError("geom_wkt yalnızca sonlu koordinatlar içermelidir.")
    return value
