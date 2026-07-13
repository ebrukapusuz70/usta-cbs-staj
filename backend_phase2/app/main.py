from __future__ import annotations

from fastapi import FastAPI, HTTPException, Response, status

from .database import (
    DatabaseOperationError,
    FeatureNotFoundError,
    InvalidFeatureInputError,
    create_feature,
    delete_feature,
    get_feature,
    list_features,
)
from .schemas import BoruCreate, FeatureResponse, VanaCreate


app = FastAPI(
    title="USTA CBS Mini Altyapi Envanter Sistemi - Backend API",
    version="2.0.0",
    description="2. Asama FastAPI REST katmani. EPSG:3857 WKT kullanir.",
)


def _handle_error(exc: Exception) -> None:
    if isinstance(exc, FeatureNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, InvalidFeatureInputError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if isinstance(exc, DatabaseOperationError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    raise exc


@app.get("/api/vanalar", response_model=list[FeatureResponse])
def read_vanalar() -> list[dict]:
    try:
        return list_features("vanalar")
    except Exception as exc:
        _handle_error(exc)
        raise


@app.get("/api/vanalar/{feature_id}", response_model=FeatureResponse)
def read_vana(feature_id: int) -> dict:
    try:
        return get_feature("vanalar", feature_id)
    except Exception as exc:
        _handle_error(exc)
        raise


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


@app.delete("/api/vanalar/{feature_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_vana(feature_id: int) -> Response:
    try:
        delete_feature("vanalar", feature_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as exc:
        _handle_error(exc)
        raise


@app.get("/api/borular", response_model=list[FeatureResponse])
def read_borular() -> list[dict]:
    try:
        return list_features("borular")
    except Exception as exc:
        _handle_error(exc)
        raise


@app.get("/api/borular/{feature_id}", response_model=FeatureResponse)
def read_boru(feature_id: int) -> dict:
    try:
        return get_feature("borular", feature_id)
    except Exception as exc:
        _handle_error(exc)
        raise


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


@app.delete("/api/borular/{feature_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_boru(feature_id: int) -> Response:
    try:
        delete_feature("borular", feature_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as exc:
        _handle_error(exc)
        raise
