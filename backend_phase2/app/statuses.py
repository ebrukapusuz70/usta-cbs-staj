"""Gaz varlıklarının durum değerlerini API genelinde tek biçime çevirir.

Canlı veritabanında borular Türkçe, vanalar ise tarihsel olarak İngilizce
durum değerleri kullanır. Bu modül depolama biçimini değiştirmeden dış API'nin
aynı Türkçe sözleşmeyi sunmasını sağlar.
"""

from __future__ import annotations

import unicodedata
from typing import Literal


AssetStatus = Literal["aktif", "pasif", "bakımda", "bilinmeyen"]
CreatableAssetStatus = Literal["aktif", "pasif", "bakımda"]
AssetKind = Literal["pipe", "valve"]


def _status_key(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").strip().casefold())
    without_marks = "".join(character for character in text if not unicodedata.combining(character))
    return without_marks.replace("ı", "i")


_STATUS_BY_ALIAS: dict[str, CreatableAssetStatus] = {
    "aktif": "aktif",
    "active": "aktif",
    "open": "aktif",
    "acik": "aktif",
    "pasif": "pasif",
    "inactive": "pasif",
    "closed": "pasif",
    "kapali": "pasif",
    "bakimda": "bakımda",
    "maintenance": "bakımda",
    "tamirde": "bakımda",
}


# PostgreSQL özet sorgusu lower(trim(status)) kullandığı için aksanlı ve
# aksansız depolama karşılıkları ayrı ayrı listelenir.
DATABASE_STATUS_ALIASES: dict[CreatableAssetStatus, tuple[str, ...]] = {
    "aktif": ("aktif", "active", "open", "açık", "acik"),
    "pasif": ("pasif", "inactive", "closed", "kapalı", "kapali"),
    "bakımda": ("bakımda", "bakimda", "maintenance", "tamirde"),
}


def normalize_asset_status(value: object) -> AssetStatus:
    """Bilinmeyen/boş değerleri güvenli gri fallback durumuna çevirir."""

    return _STATUS_BY_ALIAS.get(_status_key(value), "bilinmeyen")


def normalize_creatable_status(value: object) -> CreatableAssetStatus:
    """Yeni kayıtlar için yalnız desteklenen üç durumu kabul eder."""

    normalized = normalize_asset_status(value)
    if normalized == "bilinmeyen":
        raise ValueError("Durum aktif, pasif veya bakımda olmalıdır.")
    return normalized


def to_storage_status(kind: AssetKind, status: object) -> str:
    """Canonical API durumunu mevcut tablo sözleşmesine dönüştürür."""

    normalized = normalize_creatable_status(status)
    if kind == "pipe":
        return normalized
    return {
        "aktif": "open",
        "pasif": "closed",
        "bakımda": "maintenance",
    }[normalized]
