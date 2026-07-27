\set ON_ERROR_STOP on

BEGIN;

SET LOCAL app.backup_suffix = :'backup_suffix';

DO $$
DECLARE
    suffix text := current_setting('app.backup_suffix');
    pipe_backup text := 'gas_pipes_backup_' || suffix;
    valve_backup text := 'gas_valves_backup_' || suffix;
BEGIN
    IF to_regclass('cbs.gas_pipes_preview') IS NULL
       OR to_regclass('cbs.gas_valves_preview') IS NULL THEN
        RAISE EXCEPTION 'Preview tablolari yok. Canli aktarim durduruldu.';
    END IF;

    EXECUTE format('CREATE TABLE cbs.%I AS TABLE cbs.gas_pipes', pipe_backup);
    EXECUTE format('CREATE TABLE cbs.%I AS TABLE cbs.gas_valves', valve_backup);

    RAISE NOTICE 'Yedek tablolar olusturuldu: cbs.%, cbs.%', pipe_backup, valve_backup;
END $$;

DO $$
DECLARE
    preview_pipe_count integer;
    preview_valve_count integer;
    invalid_pipe_count integer;
    invalid_valve_count integer;
    duplicate_pipe_count integer;
    far_valve_count integer;
    source_count integer;
BEGIN
    SELECT count(*) INTO preview_pipe_count FROM cbs.gas_pipes_preview;
    SELECT count(*) INTO preview_valve_count FROM cbs.gas_valves_preview;

    IF preview_pipe_count <= 0 OR preview_valve_count <= 0 THEN
        RAISE EXCEPTION 'Preview tablolari bos. Boru=%, Vana=%', preview_pipe_count, preview_valve_count;
    END IF;

    SELECT count(*) INTO invalid_pipe_count
    FROM cbs.gas_pipes_preview
    WHERE ST_SRID(geom) <> 3857
       OR ST_GeometryType(geom) <> 'ST_MultiLineString'
       OR NOT ST_IsValid(geom);

    SELECT count(*) INTO invalid_valve_count
    FROM cbs.gas_valves_preview
    WHERE ST_SRID(geom) <> 3857
       OR ST_GeometryType(geom) <> 'ST_Point'
       OR NOT ST_IsValid(geom);

    SELECT count(*) - count(DISTINCT ST_AsBinary(ST_SnapToGrid(geom, 0.001)))
    INTO duplicate_pipe_count
    FROM cbs.gas_pipes_preview;

    SELECT count(*) INTO far_valve_count
    FROM cbs.gas_valves_preview v
    WHERE NOT EXISTS (
        SELECT 1
        FROM cbs.gas_pipes_preview p
        WHERE ST_DWithin(v.geom, p.geom, 0.5)
    );

    SELECT count(DISTINCT source) INTO source_count
    FROM (
        SELECT source FROM cbs.gas_pipes_preview
        UNION ALL
        SELECT source FROM cbs.gas_valves_preview
    ) s;

    IF invalid_pipe_count > 0 OR invalid_valve_count > 0 THEN
        RAISE EXCEPTION 'Preview geometri/SRID tipi hatali. Boru=%, Vana=%', invalid_pipe_count, invalid_valve_count;
    END IF;

    IF duplicate_pipe_count > 0 THEN
        RAISE EXCEPTION 'Preview icinde mukerrer boru geometrisi var: %', duplicate_pipe_count;
    END IF;

    IF far_valve_count > 0 THEN
        RAISE EXCEPTION 'Preview icinde borudan 0.5m uzakta vana var: %', far_valve_count;
    END IF;

    IF source_count <> 1 THEN
        RAISE EXCEPTION 'Preview source degerleri karisik. Distinct source sayisi=%', source_count;
    END IF;
END $$;

DELETE FROM cbs.gas_valves;
DELETE FROM cbs.gas_pipes;

INSERT INTO cbs.gas_pipes (
    pipe_id,
    pipe_code,
    pipe_type,
    diameter_mm,
    material,
    pressure_level,
    operating_pressure_bar,
    status,
    install_year,
    source,
    geom
)
SELECT
    pipe_id,
    pipe_code,
    pipe_type,
    diameter_mm,
    material,
    pressure_level,
    operating_pressure_bar,
    status,
    install_year,
    source,
    geom::geometry(MultiLineString, 3857)
FROM cbs.gas_pipes_preview
ORDER BY pipe_id;

INSERT INTO cbs.gas_valves (
    valve_id,
    valve_code,
    valve_type,
    diameter_mm,
    material,
    status,
    install_year,
    related_pipe_id,
    source,
    geom
)
SELECT
    valve_id,
    valve_code,
    valve_type,
    diameter_mm,
    material,
    status,
    install_year,
    related_pipe_id,
    source,
    geom::geometry(Point, 3857)
FROM cbs.gas_valves_preview
ORDER BY valve_id;

SELECT setval(pg_get_serial_sequence('cbs.gas_pipes', 'pipe_id'), COALESCE((SELECT max(pipe_id) FROM cbs.gas_pipes), 0) + 1, false);
SELECT setval(pg_get_serial_sequence('cbs.gas_valves', 'valve_id'), COALESCE((SELECT max(valve_id) FROM cbs.gas_valves), 0) + 1, false);

CREATE INDEX IF NOT EXISTS idx_gas_pipes_geom
ON cbs.gas_pipes
USING GIST (geom);

CREATE INDEX IF NOT EXISTS idx_gas_valves_geom
ON cbs.gas_valves
USING GIST (geom);

ANALYZE cbs.gas_pipes;
ANALYZE cbs.gas_valves;

DO $$
DECLARE
    preview_pipe_count integer;
    preview_valve_count integer;
    live_pipe_count integer;
    live_valve_count integer;
    invalid_pipe_count integer;
    invalid_valve_count integer;
    duplicate_pipe_count integer;
    far_valve_count integer;
BEGIN
    SELECT count(*) INTO preview_pipe_count FROM cbs.gas_pipes_preview;
    SELECT count(*) INTO preview_valve_count FROM cbs.gas_valves_preview;
    SELECT count(*) INTO live_pipe_count FROM cbs.gas_pipes;
    SELECT count(*) INTO live_valve_count FROM cbs.gas_valves;

    IF preview_pipe_count <> live_pipe_count
       OR preview_valve_count <> live_valve_count THEN
        RAISE EXCEPTION 'Canli/preview sayilari eslesmiyor. Preview boru=%, canli boru=%, preview vana=%, canli vana=%',
            preview_pipe_count, live_pipe_count, preview_valve_count, live_valve_count;
    END IF;

    SELECT count(*) INTO invalid_pipe_count
    FROM cbs.gas_pipes
    WHERE ST_SRID(geom) <> 3857
       OR ST_GeometryType(geom) <> 'ST_MultiLineString'
       OR NOT ST_IsValid(geom);

    SELECT count(*) INTO invalid_valve_count
    FROM cbs.gas_valves
    WHERE ST_SRID(geom) <> 3857
       OR ST_GeometryType(geom) <> 'ST_Point'
       OR NOT ST_IsValid(geom);

    SELECT count(*) - count(DISTINCT ST_AsBinary(ST_SnapToGrid(geom, 0.001)))
    INTO duplicate_pipe_count
    FROM cbs.gas_pipes;

    SELECT count(*) INTO far_valve_count
    FROM cbs.gas_valves v
    WHERE NOT EXISTS (
        SELECT 1
        FROM cbs.gas_pipes p
        WHERE ST_DWithin(v.geom, p.geom, 0.5)
    );

    IF invalid_pipe_count > 0 OR invalid_valve_count > 0 THEN
        RAISE EXCEPTION 'Canli geometri dogrulama hatasi. Boru=%, Vana=%', invalid_pipe_count, invalid_valve_count;
    END IF;

    IF duplicate_pipe_count > 0 THEN
        RAISE EXCEPTION 'Canli mukerrer boru geometrisi bulundu: %', duplicate_pipe_count;
    END IF;

    IF far_valve_count > 0 THEN
        RAISE EXCEPTION 'Canli borudan uzak vana bulundu: %', far_valve_count;
    END IF;

    RAISE NOTICE 'Canli aktarim dogrulandi. Boru=%, Vana=%', live_pipe_count, live_valve_count;
END $$;

COMMIT;

SELECT 'gas_pipes' AS table_name, count(*) AS count FROM cbs.gas_pipes
UNION ALL
SELECT 'gas_valves', count(*) FROM cbs.gas_valves
UNION ALL
SELECT 'gas_pipes_preview', count(*) FROM cbs.gas_pipes_preview
UNION ALL
SELECT 'gas_valves_preview', count(*) FROM cbs.gas_valves_preview;

SELECT 'gas_pipes' AS layer_name, ST_SRID(geom) AS srid, ST_GeometryType(geom) AS geometry_type, count(*)
FROM cbs.gas_pipes
GROUP BY ST_SRID(geom), ST_GeometryType(geom)
UNION ALL
SELECT 'gas_valves', ST_SRID(geom), ST_GeometryType(geom), count(*)
FROM cbs.gas_valves
GROUP BY ST_SRID(geom), ST_GeometryType(geom);

SELECT status, count(*) AS pipe_count
FROM cbs.gas_pipes
GROUP BY status
ORDER BY status;

SELECT status, count(*) AS valve_count
FROM cbs.gas_valves
GROUP BY status
ORDER BY status;
