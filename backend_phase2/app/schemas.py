from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from .geometry import ensure_wkt_type


class FeatureCreateBase(BaseModel):
    malzeme: str = Field(..., min_length=1, max_length=100)
    cap: Decimal = Field(..., gt=0, max_digits=10, decimal_places=2)
    isletme_durumu: str = Field(..., min_length=1, max_length=50)
    geom_wkt: str = Field(..., min_length=1)

    @field_validator("malzeme", "isletme_durumu", "geom_wkt")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value must not be empty.")
        return stripped


class VanaCreate(FeatureCreateBase):
    @field_validator("geom_wkt")
    @classmethod
    def validate_point(cls, value: str) -> str:
        return ensure_wkt_type(value, "POINT")


class BoruCreate(FeatureCreateBase):
    @field_validator("geom_wkt")
    @classmethod
    def validate_linestring(cls, value: str) -> str:
        return ensure_wkt_type(value, "LINESTRING")


class FeatureResponse(BaseModel):
    id: int
    malzeme: str
    cap: Decimal
    isletme_durumu: str
    geom_wkt: str
    srid: int
