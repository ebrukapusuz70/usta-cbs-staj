-- 1. Asama - PostGIS schema ve tablo tasarimi
-- Bu dosyayi DBeaver'da cbs_db veritabani baglantisi uzerinden calistirin.
-- Tum geometriler EPSG:3857 SRID ile olusturulur.

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE SCHEMA IF NOT EXISTS cbs;

CREATE TABLE IF NOT EXISTS cbs.vanalar (
    id BIGINT PRIMARY KEY,
    malzeme VARCHAR(100) NOT NULL,
    cap NUMERIC(10,2) NOT NULL,
    isletme_durumu VARCHAR(50) NOT NULL,
    geom geometry(Point,3857) NOT NULL,
    CONSTRAINT vanalar_cap_positive CHECK (cap > 0)
);

CREATE INDEX IF NOT EXISTS vanalar_geom_gix
    ON cbs.vanalar
    USING GIST (geom);

CREATE TABLE IF NOT EXISTS cbs.borular (
    id BIGINT PRIMARY KEY,
    malzeme VARCHAR(100) NOT NULL,
    cap NUMERIC(10,2) NOT NULL,
    isletme_durumu VARCHAR(50) NOT NULL,
    geom geometry(LineString,3857) NOT NULL,
    CONSTRAINT borular_cap_positive CHECK (cap > 0)
);

CREATE INDEX IF NOT EXISTS borular_geom_gix
    ON cbs.borular
    USING GIST (geom);

