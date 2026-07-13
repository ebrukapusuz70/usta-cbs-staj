from __future__ import annotations

import re


_WKT_TYPE_RE = re.compile(r"^\s*([A-Za-z]+)\s*(?:\(|EMPTY\b)", re.IGNORECASE)


class GeometryValidationError(ValueError):
    """Raised when incoming WKT does not match the required geometry rule."""


def get_wkt_type(geom_wkt: str) -> str:
    value = geom_wkt.strip()
    if not value:
        raise GeometryValidationError("geom_wkt is required.")
    if value.upper().startswith("SRID="):
        raise GeometryValidationError("geom_wkt must not include an SRID prefix.")

    match = _WKT_TYPE_RE.match(value)
    if not match:
        raise GeometryValidationError("geom_wkt must be valid WKT text.")
    return match.group(1).upper()


def ensure_wkt_type(geom_wkt: str, expected_type: str) -> str:
    actual_type = get_wkt_type(geom_wkt)
    expected = expected_type.upper()
    if actual_type != expected:
        raise GeometryValidationError(
            f"geom_wkt must be {expected} geometry, got {actual_type}."
        )
    return geom_wkt.strip()
