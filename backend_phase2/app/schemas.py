"""API'ye gelen ve API'den dönen verileri doğrular.
Pydantic modelleri zorunlu alanları ve değer sınırlarını kontrol eder.
Geometri kontrolleri için geometry.py dosyasını kullanır.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .geometry import ensure_finite_wkt, ensure_wkt_type, get_wkt_type
from .statuses import (
    AssetStatus,
    CreatableAssetStatus,
    normalize_asset_status,
    normalize_creatable_status,
)

PipeConnectionType = Literal["pipe_endpoint", "valve", "junction"]


# BaseModel JSON gövdesini doğrulanmış Python nesnesine çevirir. Field içindeki
# ... zorunlu alanı, min_length/max_length metin sınırını, gt=0 pozitif sayıyı anlatır.
class FeatureCreateBase(BaseModel):
    malzeme: str = Field(..., min_length=1, max_length=100)
    cap: Decimal = Field(..., gt=0, max_digits=10, decimal_places=2)
    isletme_durumu: str = Field(..., min_length=1, max_length=50)
    geom_wkt: str = Field(..., min_length=1)

    # field_validator seçili alanları tek tek kontrol edip baş/son boşlukları temizler.
    @field_validator("malzeme", "isletme_durumu", "geom_wkt")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Değer boş olamaz.")
        return stripped


# VanaCreate ortak alanlara ek olarak POINT geometrisini zorunlu tutar.
class VanaCreate(FeatureCreateBase):
    @field_validator("geom_wkt")
    @classmethod
    def validate_point(cls, value: str) -> str:
        return ensure_wkt_type(value, "POINT")


# BoruCreate ortak alanlara ek olarak LINESTRING geometrisini zorunlu tutar.
class BoruCreate(FeatureCreateBase):
    @field_validator("geom_wkt")
    @classmethod
    def validate_linestring(cls, value: str) -> str:
        return ensure_wkt_type(value, "LINESTRING")


# FeatureResponse, veritabanından istemciye dönen ortak yanıt modelidir.
class FeatureResponse(BaseModel):
    id: int
    malzeme: str
    cap: Decimal
    isletme_durumu: str
    geom_wkt: str
    srid: int


# Bu modeller veritabanından dönen boru ve vana cevaplarının yapısını belirler.
class GasPipeResponse(BaseModel):
    pipe_id: int
    pipe_code: str
    pipe_type: str
    diameter_mm: int
    material: str
    pressure_level: str
    operating_pressure_bar: Decimal
    status: AssetStatus
    install_year: int
    source: str
    operator_name: str | None = None
    geom_wkt: str
    srid: int

    @field_validator("status", mode="before")
    @classmethod
    def normalize_pipe_status(cls, value: object) -> AssetStatus:
        return normalize_asset_status(value)


class GasValveResponse(BaseModel):
    valve_id: int
    valve_code: str
    valve_type: str
    diameter_mm: int
    material: str
    status: AssetStatus
    install_year: int
    related_pipe_id: int
    source: str
    operator_name: str | None = None
    geom_wkt: str
    srid: int

    @field_validator("status", mode="before")
    @classmethod
    def normalize_valve_status(cls, value: object) -> AssetStatus:
        return normalize_asset_status(value)


class GasStatusCounts(BaseModel):
    total: int
    aktif: int
    pasif: int
    bakimda: int
    bilinmeyen: int
    # Eski istemciler için geçici, geriye uyumlu sayaç adlarıdır.
    tamirde: int | None = None
    acik: int | None = None
    kapali: int | None = None


class GasSummaryResponse(BaseModel):
    pipes: GasStatusCounts
    valves: GasStatusCounts


class PipeCodeSuggestionResponse(BaseModel):
    suggested_code: str | None
    prefix: str | None
    basis: Literal["connected_pipe", "connected_valve", "junction_pipe", "dominant_network", "none"]
    message: str | None = None


class ValveCodeSuggestionResponse(BaseModel):
    suggested_code: str | None
    region_prefix: str | None
    related_pipe_id: int
    basis: Literal["related_pipe", "dominant_network", "none"]
    message: str | None = None


# POST ve PATCH aynı çap/malzeme/basınç uyumunu kullanır; ortak kontrol iki
# sözleşmenin zamanla birbirinden farklı davranmasını önler.
def validate_pipe_attribute_compatibility(
    pipe_type: str,
    diameter_mm: int,
    material: str,
    pressure_level: str,
    operating_pressure_bar: Decimal,
) -> None:
    rules = {
        "main_line": ({250, 315, 400}, {"çelik", "celik"}, {"medium", "high"}, (2.0, 20.0)),
        "distribution": ({90, 110, 125, 160}, {"pe"}, {"low"}, (0.1, 4.0)),
        "service_line": ({32, 40, 63}, {"pe"}, {"low"}, (0.1, 1.0)),
    }
    diameters, materials, pressure_levels, pressure_range = rules[pipe_type]
    pressure = float(operating_pressure_bar)
    if diameter_mm not in diameters:
        raise ValueError(f"diameter_mm değeri {pipe_type} boru türüyle uyumlu değil.")
    if material.casefold() not in materials:
        raise ValueError(f"material değeri {pipe_type} boru türüyle uyumlu değil.")
    if pressure_level not in pressure_levels or not pressure_range[0] <= pressure <= pressure_range[1]:
        raise ValueError(f"Basınç değerleri {pipe_type} boru türüyle uyumlu değil.")


# 4. aşama borusunun zorunlu alan ve birbiriyle uyumlu çap/basınç kurallarıdır.
class GasPipeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    """Mevcut cbs.gas_pipes kolonlarına yazılabilen stage4 boru isteği."""

    pipe_code: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$",
    )
    operator_name: str = Field(..., min_length=2, max_length=100)
    pipe_type: Literal["main_line", "distribution", "service_line"]
    diameter_mm: int = Field(..., gt=0, le=2000)
    material: str = Field(..., min_length=1, max_length=100)
    pressure_level: Literal["low", "medium", "high"]
    operating_pressure_bar: Decimal = Field(..., gt=0, le=100)
    status: CreatableAssetStatus
    install_year: int = Field(..., ge=1900)
    geom_wkt: str = Field(..., min_length=1)
    start_connection_type: PipeConnectionType
    start_connection_id: int = Field(..., gt=0)

    @field_validator("pipe_code", "material", "geom_wkt", mode="before")
    @classmethod
    def strip_pipe_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Değer boş olamaz.")
        return value

    @field_validator("operator_name", mode="before")
    @classmethod
    def strip_pipe_operator_name(cls, value: object) -> object:
        # Dış boşluklar Field içindeki 2–100 karakter kontrolünden önce temizlenir.
        return value.strip() if isinstance(value, str) else value

    @field_validator("install_year")
    @classmethod
    def validate_pipe_year(cls, value: int) -> int:
        if value > date.today().year:
            raise ValueError("install_year gelecek bir yıl olamaz.")
        return value

    @field_validator("geom_wkt")
    @classmethod
    def validate_pipe_geometry(cls, value: str) -> str:
        value = ensure_finite_wkt(value)
        # Harita LineString çizer; tablo MultiLineString olduğu için dönüşüm DB katmanında yapılır.
        if get_wkt_type(value) != "LINESTRING":
            raise ValueError("geom_wkt tek parçalı bir LINESTRING geometrisi olmalıdır.")
        return value

    @field_validator("status", mode="before")
    @classmethod
    def normalize_pipe_create_status(cls, value: object) -> CreatableAssetStatus:
        return normalize_creatable_status(value)

    @model_validator(mode="after")
    def validate_compatible_pipe_attributes(self) -> "GasPipeCreate":
        validate_pipe_attribute_compatibility(
            self.pipe_type,
            self.diameter_mm,
            self.material,
            self.pressure_level,
            self.operating_pressure_bar,
        )
        return self


# 4. aşama vanasının zorunlu alanlarını ve POINT geometrisini doğrular.
class GasValveCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    """Mevcut cbs.gas_valves kolonlarına yazılabilen stage4 vana isteği."""

    valve_code: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$",
    )
    operator_name: str = Field(..., min_length=2, max_length=100)
    valve_type: Literal["isolation", "control", "pressure_reducing", "emergency"]
    material: str = Field(..., min_length=1, max_length=100)
    status: CreatableAssetStatus
    install_year: int = Field(..., ge=1900)
    geom_wkt: str = Field(..., min_length=1)

    @field_validator("valve_code", "material", "geom_wkt", mode="before")
    @classmethod
    def strip_valve_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Değer boş olamaz.")
        return value

    @field_validator("operator_name", mode="before")
    @classmethod
    def strip_valve_operator_name(cls, value: object) -> object:
        # Yalnız boşluk içeren operatör adı temizlendikten sonra kısa değer olarak reddedilir.
        return value.strip() if isinstance(value, str) else value

    @field_validator("install_year")
    @classmethod
    def validate_valve_year(cls, value: int) -> int:
        if value > date.today().year:
            raise ValueError("install_year gelecek bir yıl olamaz.")
        return value

    @field_validator("geom_wkt")
    @classmethod
    def validate_valve_geometry(cls, value: str) -> str:
        return ensure_wkt_type(ensure_finite_wkt(value), "POINT")

    @field_validator("status", mode="before")
    @classmethod
    def normalize_valve_create_status(cls, value: object) -> CreatableAssetStatus:
        return normalize_creatable_status(value)


class GasPipeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pipe_code: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$",
    )
    pipe_type: Literal["main_line", "distribution", "service_line"] | None = None
    diameter_mm: int | None = Field(default=None, gt=0, le=2000)
    material: str | None = Field(default=None, min_length=1, max_length=100)
    pressure_level: Literal["low", "medium", "high"] | None = None
    operating_pressure_bar: Decimal | None = Field(default=None, gt=0, le=100)
    status: CreatableAssetStatus | None = None
    install_year: int | None = Field(default=None, ge=1900)
    operator_name: str | None = Field(default=None, min_length=2, max_length=100)
    geom_wkt: str | None = Field(default=None, min_length=1)
    start_connection_type: PipeConnectionType | None = None
    start_connection_id: int | None = Field(default=None, gt=0)

    @field_validator("pipe_code", "material", "geom_wkt", mode="before")
    @classmethod
    def strip_optional_pipe_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("operator_name", mode="before")
    @classmethod
    def strip_optional_pipe_operator(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("install_year")
    @classmethod
    def validate_optional_pipe_year(cls, value: int | None) -> int | None:
        if value is not None and value > date.today().year:
            raise ValueError("install_year gelecek bir yıl olamaz.")
        return value

    @field_validator("geom_wkt")
    @classmethod
    def validate_optional_pipe_geometry(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = ensure_finite_wkt(value)
        if get_wkt_type(value) != "LINESTRING":
            raise ValueError("geom_wkt tek parçalı bir LINESTRING geometrisi olmalıdır.")
        return value

    @field_validator("status", mode="before")
    @classmethod
    def normalize_optional_pipe_status(cls, value: object) -> object:
        return None if value is None else normalize_creatable_status(value)

    @model_validator(mode="after")
    def validate_partial_pipe_update(self) -> "GasPipeUpdate":
        provided = self.model_fields_set
        if not provided:
            raise ValueError("En az bir düzenlenebilir alan gönderilmelidir.")
        # Başlangıç kimliği tek başına değiştirilirse topoloji denetimi atlanabilir;
        # bu nedenle bağlantı alanları yalnız yeni geometriyle birlikte kabul edilir.
        geometry_fields = {"start_connection_type", "start_connection_id"}
        if "geom_wkt" in provided and not geometry_fields.issubset(provided):
            raise ValueError("Boru geometrisi değişirken başlangıç bağlantısı birlikte gönderilmelidir.")
        if "geom_wkt" not in provided and provided.intersection(geometry_fields):
            raise ValueError("Başlangıç bağlantısı yalnız boru geometrisiyle birlikte değiştirilebilir.")
        return self


class GasValveUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valve_code: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$",
    )
    valve_type: Literal["isolation", "control", "pressure_reducing", "emergency"] | None = None
    material: str | None = Field(default=None, min_length=1, max_length=100)
    status: CreatableAssetStatus | None = None
    install_year: int | None = Field(default=None, ge=1900)
    operator_name: str | None = Field(default=None, min_length=2, max_length=100)
    geom_wkt: str | None = Field(default=None, min_length=1)

    @field_validator("valve_code", "material", "geom_wkt", mode="before")
    @classmethod
    def strip_optional_valve_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("operator_name", mode="before")
    @classmethod
    def strip_optional_valve_operator(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("install_year")
    @classmethod
    def validate_optional_valve_year(cls, value: int | None) -> int | None:
        if value is not None and value > date.today().year:
            raise ValueError("install_year gelecek bir yıl olamaz.")
        return value

    @field_validator("geom_wkt")
    @classmethod
    def validate_optional_valve_geometry(cls, value: str | None) -> str | None:
        return None if value is None else ensure_wkt_type(ensure_finite_wkt(value), "POINT")

    @field_validator("status", mode="before")
    @classmethod
    def normalize_optional_valve_status(cls, value: object) -> object:
        return None if value is None else normalize_creatable_status(value)

    @model_validator(mode="after")
    def validate_partial_valve_update(self) -> "GasValveUpdate":
        if not self.model_fields_set:
            raise ValueError("En az bir düzenlenebilir alan gönderilmelidir.")
        return self
