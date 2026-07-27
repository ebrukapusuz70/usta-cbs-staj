"""FastAPI uygulamasının ana dosyasıdır.
API adreslerini ve HTTP işlemlerini tanımlar.
Veritabanı işlemleri için database.py dosyasını kullanır.
"""

from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import FastAPI, Header, HTTPException, Query, Response, status
from fastapi.middleware.gzip import GZipMiddleware

from .config import get_stage4_e2e_token
from .database import (
    CodeConflictError,
    DatabaseOperationError,
    FeatureInUseError,
    FeatureNotFoundError,
    InvalidFeatureInputError,
    TopologyConflictError,
    UnsafeFeatureDeleteError,
    create_gas_pipe,
    create_gas_valve,
    create_feature,
    delete_gas_pipe,
    delete_gas_valve,
    delete_feature,
    get_gas_summary,
    get_gas_pipe,
    get_gas_valve,
    get_feature,
    list_gas_pipes,
    list_gas_valves,
    list_features,
    suggest_gas_pipe_code,
    suggest_gas_valve_code,
    update_gas_pipe,
    update_gas_valve,
)
from .schemas import (
    BoruCreate,
    FeatureResponse,
    GasPipeCreate,
    GasPipeResponse,
    GasPipeUpdate,
    GasSummaryResponse,
    GasValveCreate,
    GasValveResponse,
    GasValveUpdate,
    PipeCodeSuggestionResponse,
    PipeConnectionType,
    ValveCodeSuggestionResponse,
    VanaCreate,
)
from .topology import TopologyUnavailableError, get_topology_payload


# FastAPI uygulamasını oluşturur ve Swagger belgesinde görünecek bilgileri tanımlar.
app = FastAPI(
    title="USTA CBS Mini Altyapi Envanter Sistemi - Backend API",
    version="2.0.0",
    description="2. Asama FastAPI REST katmani. EPSG:3857 WKT kullanir.",
)
# Büyük cevapları sıkıştırarak ağ üzerinden daha küçük boyutta gönderir.
app.add_middleware(GZipMiddleware, minimum_size=1_000)


# Alt katman hatalarını anlamlı HTTP durum kodlarına çevirir; veritabanı
# ayrıntılarının doğrudan kullanıcıya sızmasını da önler.
def _handle_error(exc: Exception) -> None:
    # Kararlı hata kodu arayüzde Türkçe mesaja çevrilir; veritabanı/SQL ayrıntısı
    # response içine taşınmadan yalnız güvenli ek bilgiler (ör. bağlı sayı) döner.
    detail = {
        "code": getattr(exc, "code", "UNKNOWN_ERROR"),
        "message": str(exc),
        **getattr(exc, "details", {}),
    }
    if isinstance(exc, FeatureNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    if isinstance(exc, InvalidFeatureInputError):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)
    if isinstance(exc, UnsafeFeatureDeleteError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
    if isinstance(exc, (CodeConflictError, FeatureInUseError, TopologyConflictError)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
    if isinstance(exc, DatabaseOperationError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
        )
    if isinstance(exc, TopologyUnavailableError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    raise exc


def _stage4_source(test_token: str | None) -> str:
    if test_token is None:
        return "user_created_stage4"
    expected = get_stage4_e2e_token()
    if expected is None or not hmac.compare_digest(test_token, expected):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Test isteği yetkilendirilemedi.",
        )
    return "user_created_stage4_e2e"


# GET: Yerel topoloji verisini get_topology_payload ile getirir; başarı kodu 200'dür.
@app.get("/api/stage4/topology")
def read_stage4_topology() -> dict:
    """Yalnız yerel, önceden doğrulanmış OSM yol/yasak alan vektörlerini sunar."""
    try:
        return get_topology_payload()
    except Exception as exc:
        _handle_error(exc)
        raise


# GET: Tüm 4. aşama borularını list_gas_pipes ile listeler; başarı kodu 200'dür.
@app.get("/api/gas-pipes", response_model=list[GasPipeResponse])
def read_gas_pipes() -> list[dict]:
    try:
        return list_gas_pipes()
    except Exception as exc:
        _handle_error(exc)
        raise


@app.get("/api/gas-pipes/suggest-code", response_model=PipeCodeSuggestionResponse)
def read_gas_pipe_code_suggestion(
    start_connection_type: PipeConnectionType,
    start_connection_id: int = Query(..., gt=0),
) -> dict:
    try:
        return suggest_gas_pipe_code(start_connection_type, start_connection_id)
    except Exception as exc:
        _handle_error(exc)
        raise


# GET: Kimliği verilen boruyu get_gas_pipe ile getirir; başarı kodu 200'dür.
@app.get("/api/gas-pipes/{feature_id}", response_model=GasPipeResponse)
def read_gas_pipe(feature_id: int) -> dict:
    try:
        return get_gas_pipe(feature_id)
    except Exception as exc:
        _handle_error(exc)
        raise


# POST: Yeni boruyu create_gas_pipe ile kaydeder; başarılı oluşturmada 201 döndürür.
@app.post(
    "/api/gas-pipes",
    response_model=GasPipeResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_stage4_gas_pipe(
    payload: GasPipeCreate,
    test_token: Annotated[str | None, Header(alias="X-Stage4-E2E-Token")] = None,
) -> dict:
    try:
        # Pydantic modelini veritabanı fonksiyonunun kullanacağı sözlüğe çevirir.
        return create_gas_pipe(payload.model_dump(), source=_stage4_source(test_token))
    except Exception as exc:
        _handle_error(exc)
        raise


@app.patch("/api/gas-pipes/{feature_id}", response_model=GasPipeResponse)
def update_stage4_gas_pipe(feature_id: int, payload: GasPipeUpdate) -> dict:
    try:
        return update_gas_pipe(
            feature_id,
            payload.model_dump(exclude_unset=True),
        )
    except Exception as exc:
        _handle_error(exc)
        raise


# DELETE: Boruyu delete_gas_pipe ile siler; başarılı gövdesiz yanıtta 204 döndürür.
@app.delete("/api/gas-pipes/{feature_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_stage4_gas_pipe(feature_id: int) -> Response:
    try:
        delete_gas_pipe(feature_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as exc:
        _handle_error(exc)
        raise


# GET: Tüm 4. aşama vanalarını list_gas_valves ile listeler; başarı kodu 200'dür.
@app.get("/api/gas-valves", response_model=list[GasValveResponse])
def read_gas_valves() -> list[dict]:
    try:
        return list_gas_valves()
    except Exception as exc:
        _handle_error(exc)
        raise


@app.get("/api/gas-valves/suggest-code", response_model=ValveCodeSuggestionResponse)
def read_gas_valve_code_suggestion(
    related_pipe_id: int = Query(..., gt=0),
) -> dict:
    try:
        return suggest_gas_valve_code(related_pipe_id)
    except Exception as exc:
        _handle_error(exc)
        raise


# GET: Kimliği verilen vanayı get_gas_valve ile getirir; başarı kodu 200'dür.
@app.get("/api/gas-valves/{feature_id}", response_model=GasValveResponse)
def read_gas_valve(feature_id: int) -> dict:
    try:
        return get_gas_valve(feature_id)
    except Exception as exc:
        _handle_error(exc)
        raise


# POST: Yeni vanayı create_gas_valve ile kaydeder; başarılı oluşturmada 201 döndürür.
@app.post(
    "/api/gas-valves",
    response_model=GasValveResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_stage4_gas_valve(
    payload: GasValveCreate,
    test_token: Annotated[str | None, Header(alias="X-Stage4-E2E-Token")] = None,
) -> dict:
    try:
        return create_gas_valve(payload.model_dump(), source=_stage4_source(test_token))
    except Exception as exc:
        _handle_error(exc)
        raise


@app.patch("/api/gas-valves/{feature_id}", response_model=GasValveResponse)
def update_stage4_gas_valve(feature_id: int, payload: GasValveUpdate) -> dict:
    try:
        return update_gas_valve(
            feature_id,
            payload.model_dump(exclude_unset=True),
        )
    except Exception as exc:
        _handle_error(exc)
        raise


# DELETE: Vanayı delete_gas_valve ile siler; başarılı gövdesiz yanıtta 204 döndürür.
@app.delete("/api/gas-valves/{feature_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_stage4_gas_valve(feature_id: int) -> Response:
    try:
        delete_gas_valve(feature_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as exc:
        _handle_error(exc)
        raise


# GET: Boru/vana özetini get_gas_summary ile getirir; başarı kodu 200'dür.
@app.get("/api/gas-summary", response_model=GasSummaryResponse)
def read_gas_summary() -> dict:
    try:
        return get_gas_summary()
    except Exception as exc:
        _handle_error(exc)
        raise


# GET /api/vanalar: list_features("vanalar") ile tüm vanaları döndürür; başarı 200.
@app.get("/api/vanalar", response_model=list[FeatureResponse])
def read_vanalar() -> list[dict]:
    try:
        return list_features("vanalar")
    except Exception as exc:
        _handle_error(exc)
        raise


# GET /api/vanalar/{id}: get_feature ile tek vanayı getirir; başarı kodu 200'dür.
@app.get("/api/vanalar/{feature_id}", response_model=FeatureResponse)
def read_vana(feature_id: int) -> dict:
    try:
        return get_feature("vanalar", feature_id)
    except Exception as exc:
        _handle_error(exc)
        raise


# POST /api/vanalar: create_feature ile doğrulanmış vana ekler; başarı kodu 201'dir.
@app.post(
    "/api/vanalar",
    response_model=FeatureResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_vana(payload: VanaCreate) -> dict:
    try:
        return create_feature("vanalar", payload.model_dump())
    except Exception as exc:
        _handle_error(exc)
        raise


# DELETE /api/vanalar/{id}: delete_feature ile vanayı siler; başarı kodu 204'tür.
@app.delete("/api/vanalar/{feature_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_vana(feature_id: int) -> Response:
    try:
        delete_feature("vanalar", feature_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as exc:
        _handle_error(exc)
        raise


# GET /api/borular: list_features("borular") ile tüm boruları döndürür; başarı 200.
@app.get("/api/borular", response_model=list[FeatureResponse])
def read_borular() -> list[dict]:
    try:
        return list_features("borular")
    except Exception as exc:
        _handle_error(exc)
        raise


# GET /api/borular/{id}: get_feature ile tek boruyu getirir; başarı kodu 200'dür.
@app.get("/api/borular/{feature_id}", response_model=FeatureResponse)
def read_boru(feature_id: int) -> dict:
    try:
        return get_feature("borular", feature_id)
    except Exception as exc:
        _handle_error(exc)
        raise


# POST /api/borular: create_feature ile doğrulanmış boru ekler; başarı kodu 201'dir.
@app.post(
    "/api/borular",
    response_model=FeatureResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_boru(payload: BoruCreate) -> dict:
    try:
        return create_feature("borular", payload.model_dump())
    except Exception as exc:
        _handle_error(exc)
        raise


# DELETE /api/borular/{id}: delete_feature ile boruyu siler; başarı kodu 204'tür.
@app.delete("/api/borular/{feature_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_boru(feature_id: int) -> Response:
    try:
        delete_feature("borular", feature_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as exc:
        _handle_error(exc)
        raise
