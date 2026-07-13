-- 2. Asama - POST sonrasi database dogrulama sorgulari
-- DBeaver'da cbs_db veritabani uzerinde calistirin.
-- 123 degerini Swagger POST cevabinda gelen id ile degistirin.

SELECT
    id,
    malzeme,
    cap,
    isletme_durumu,
    ST_AsText(geom) AS geom_wkt,
    ST_SRID(geom) AS srid,
    GeometryType(geom) AS geometry_type
FROM cbs.vanalar
WHERE id = 123;

SELECT
    id,
    malzeme,
    cap,
    isletme_durumu,
    ST_AsText(geom) AS geom_wkt,
    ST_SRID(geom) AS srid,
    GeometryType(geom) AS geometry_type
FROM cbs.borular
WHERE id = 123;

-- Beklenen:
-- vanalar icin geometry_type = POINT ve srid = 3857
-- borular icin geometry_type = LINESTRING ve srid = 3857

