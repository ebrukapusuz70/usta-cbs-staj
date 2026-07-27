"""Veritabanı ayarlarını .env ve ortam değişkenlerinden okur.
Gizli bilgilerin doğrudan kaynak kodda tutulmasını önler.
database.py için bağlantı ayarlarını hazırlar.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_ROOT / ".env"


# .env dosyasındaki değerleri mevcut ortam ayarlarını ezmeden yükler.
def _load_env_file() -> None:
    if not ENV_FILE.exists():
        return

    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


# Veritabanı bağlantı ayarlarını tek bir nesnede toplar.
@dataclass(frozen=True)
class Settings:
    postgres_host: str
    postgres_port: int
    postgres_db: str
    postgres_user: str
    postgres_password: str

    def db_params(self) -> dict[str, object]:
        return {
            "host": self.postgres_host,
            "port": self.postgres_port,
            "dbname": self.postgres_db,
            "user": self.postgres_user,
            "password": self.postgres_password,
        }


# Ağ kurallarını ortam değişkenlerinden okunabilir bir yapıda tutar.
@dataclass(frozen=True)
class NetworkRuleSettings:
    snap_tolerance_m: float
    pipe_min_length_m: float
    pipe_max_length_m: float


def _positive_float(name: str, default: float) -> float:
    raw_value = os.getenv(name, str(default))
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise RuntimeError(f"{name} sayısal bir değer olmalıdır.") from exc
    if not math.isfinite(value) or value <= 0:
        raise RuntimeError(f"{name} sıfırdan büyük olmalıdır.")
    return value


# Çizim toleransı ve boru uzunluk sınırlarını .env dosyasından okur.
def get_network_rule_settings() -> NetworkRuleSettings:
    _load_env_file()
    minimum = _positive_float("PIPE_MIN_LENGTH_M", 5.0)
    maximum = _positive_float("PIPE_MAX_LENGTH_M", 5_000.0)
    if maximum <= minimum:
        raise RuntimeError("PIPE_MAX_LENGTH_M, PIPE_MIN_LENGTH_M değerinden büyük olmalıdır.")
    return NetworkRuleSettings(
        snap_tolerance_m=_positive_float("SNAP_TOLERANCE", 15.0),
        pipe_min_length_m=minimum,
        pipe_max_length_m=maximum,
    )


# Eksik ayarlar için varsayılan değerleri kullanır; şifrenin verilmesini zorunlu tutar.
def get_settings() -> Settings:
    _load_env_file()

    password = os.getenv("POSTGRES_PASSWORD", "")
    if not password:
        raise RuntimeError("POSTGRES_PASSWORD is required in environment or .env file.")

    return Settings(
        postgres_host=os.getenv("POSTGRES_HOST", "localhost"),
        postgres_port=int(os.getenv("POSTGRES_PORT", "5432")),
        postgres_db=os.getenv("POSTGRES_DB", "cbs_db"),
        postgres_user=os.getenv("POSTGRES_USER", "usta_admin"),
        postgres_password=password,
    )


def get_stage4_e2e_token() -> str | None:
    _load_env_file()
    token = os.getenv("STAGE4_E2E_TOKEN", "").strip()
    return token or None
