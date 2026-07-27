-- UYARI:
-- Bu dosyadaki gas_pipes ve gas_valves verileri tamamen sentetiktir.
-- Gerçek doğalgaz altyapısını, gerçek boru hatlarını, gerçek vana konumlarını veya herhangi bir resmi altyapı kaydını temsil etmez.
-- Yalnızca eğitim, demo ve yazılım geliştirme/test amacıyla oluşturulmuştur.

/*
  Dosya: database/04_create_synthetic_gas_yenimahalle.sql
  Amaç: Ankara/Yenimahalle çalışma alanı için EPSG:3857 sentetik doğalgaz demo verisi üretmek.

  Önemli güvenlik stratejisi:
  - DROP TABLE veya TRUNCATE kullanılmaz.
  - Mevcut cbs.vanalar ve cbs.borular tablolarına dokunulmaz.
  - cbs.gas_pipes veya cbs.gas_valves tablolarında veri varsa işlem durdurulur.
  - Bu dosya boş/yeni ortamda DBeaver üzerinden doğrudan çalıştırılmak üzere hazırlanmıştır.

  Schema kararı:
  - Bu proje genelinde PostGIS çalışma schema'sı cbs olduğu için tablolar cbs altında oluşturulur.
  - Farklı schema istenirse dosyadaki cbs. nitelemeleri bilinçli şekilde değiştirilmelidir.

  Geometri üretimi:
  - 4326 kullanılmaz.
  - ST_Transform kullanılmaz.
  - Tüm koordinatlar doğrudan EPSG:3857 demo koordinatlarıdır.
*/

BEGIN;

-- 1. Schema kontrolü
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE SCHEMA IF NOT EXISTS cbs;
SET search_path TO cbs, public;

-- 2. Eski demo tablolarını yönetme stratejisi
-- Tablolar varsa ve içinde veri varsa işlem durur. Silme/truncate kullanıcı onayı olmadan yapılmaz.
DO $$
DECLARE
    pipe_count integer := 0;
    valve_count integer := 0;
BEGIN
    IF to_regclass('cbs.gas_pipes') IS NOT NULL THEN
        EXECUTE 'SELECT COUNT(*) FROM cbs.gas_pipes' INTO pipe_count;
    END IF;

    IF to_regclass('cbs.gas_valves') IS NOT NULL THEN
        EXECUTE 'SELECT COUNT(*) FROM cbs.gas_valves' INTO valve_count;
    END IF;

    IF pipe_count > 0 OR valve_count > 0 THEN
        RAISE EXCEPTION
            'Güvenlik nedeniyle işlem durduruldu. Mevcut veri var: cbs.gas_pipes=%, cbs.gas_valves=%. DROP/TRUNCATE yapılmadı. Değiştirme için açık kullanıcı onayı gerekir.',
            pipe_count,
            valve_count;
    END IF;
END $$;

-- 3. gas_pipes tablo oluşturma
CREATE TABLE IF NOT EXISTS cbs.gas_pipes (
    pipe_id serial PRIMARY KEY,
    pipe_code varchar NOT NULL,
    pipe_type varchar NOT NULL,
    diameter_mm integer NOT NULL,
    material varchar NOT NULL,
    pressure_level varchar NOT NULL,
    operating_pressure_bar numeric NOT NULL,
    status varchar NOT NULL,
    install_year integer NOT NULL,
    source varchar NOT NULL,
    geom geometry(MultiLineString, 3857) NOT NULL
);

-- 4. gas_valves tablo oluşturma
CREATE TABLE IF NOT EXISTS cbs.gas_valves (
    valve_id serial PRIMARY KEY,
    valve_code varchar NOT NULL,
    valve_type varchar NOT NULL,
    diameter_mm integer NOT NULL,
    material varchar NOT NULL,
    status varchar NOT NULL,
    install_year integer NOT NULL,
    related_pipe_id integer,
    source varchar NOT NULL,
    geom geometry(Point, 3857) NOT NULL
);

-- 5. Constraint / kalite kuralları
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'gas_pipes_pipe_code_uq'
          AND conrelid = 'cbs.gas_pipes'::regclass
    ) THEN
        ALTER TABLE cbs.gas_pipes
            ADD CONSTRAINT gas_pipes_pipe_code_uq UNIQUE (pipe_code);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'gas_pipes_pipe_type_chk'
          AND conrelid = 'cbs.gas_pipes'::regclass
    ) THEN
        ALTER TABLE cbs.gas_pipes
            ADD CONSTRAINT gas_pipes_pipe_type_chk
            CHECK (pipe_type IN ('main_line', 'distribution', 'service_line'));
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'gas_pipes_diameter_chk'
          AND conrelid = 'cbs.gas_pipes'::regclass
    ) THEN
        ALTER TABLE cbs.gas_pipes
            ADD CONSTRAINT gas_pipes_diameter_chk
            CHECK (diameter_mm IN (63, 90, 110, 125, 160, 200, 250));
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'gas_pipes_material_chk'
          AND conrelid = 'cbs.gas_pipes'::regclass
    ) THEN
        ALTER TABLE cbs.gas_pipes
            ADD CONSTRAINT gas_pipes_material_chk
            CHECK (material IN ('PE', 'Steel', 'Ductile Iron'));
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'gas_pipes_pressure_level_chk'
          AND conrelid = 'cbs.gas_pipes'::regclass
    ) THEN
        ALTER TABLE cbs.gas_pipes
            ADD CONSTRAINT gas_pipes_pressure_level_chk
            CHECK (pressure_level IN ('low', 'medium'));
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'gas_pipes_operating_pressure_chk'
          AND conrelid = 'cbs.gas_pipes'::regclass
    ) THEN
        ALTER TABLE cbs.gas_pipes
            ADD CONSTRAINT gas_pipes_operating_pressure_chk
            CHECK (operating_pressure_bar IN (0.3, 1, 4));
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'gas_pipes_status_chk'
          AND conrelid = 'cbs.gas_pipes'::regclass
    ) THEN
        ALTER TABLE cbs.gas_pipes
            ADD CONSTRAINT gas_pipes_status_chk
            CHECK (status IN ('aktif', 'bakımda', 'pasif'));
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'gas_pipes_install_year_chk'
          AND conrelid = 'cbs.gas_pipes'::regclass
    ) THEN
        ALTER TABLE cbs.gas_pipes
            ADD CONSTRAINT gas_pipes_install_year_chk
            CHECK (install_year BETWEEN 1995 AND 2024);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'gas_pipes_source_chk'
          AND conrelid = 'cbs.gas_pipes'::regclass
    ) THEN
        ALTER TABLE cbs.gas_pipes
            ADD CONSTRAINT gas_pipes_source_chk
            CHECK (source = 'synthetic_demo_yenimahalle');
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'gas_pipes_geom_quality_chk'
          AND conrelid = 'cbs.gas_pipes'::regclass
    ) THEN
        ALTER TABLE cbs.gas_pipes
            ADD CONSTRAINT gas_pipes_geom_quality_chk
            CHECK (
                geom IS NOT NULL
                AND ST_SRID(geom) = 3857
                AND GeometryType(geom) = 'MULTILINESTRING'
            );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'gas_valves_valve_code_uq'
          AND conrelid = 'cbs.gas_valves'::regclass
    ) THEN
        ALTER TABLE cbs.gas_valves
            ADD CONSTRAINT gas_valves_valve_code_uq UNIQUE (valve_code);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'gas_valves_valve_type_chk'
          AND conrelid = 'cbs.gas_valves'::regclass
    ) THEN
        ALTER TABLE cbs.gas_valves
            ADD CONSTRAINT gas_valves_valve_type_chk
            CHECK (valve_type IN ('isolation', 'control', 'pressure_reducing', 'emergency'));
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'gas_valves_diameter_chk'
          AND conrelid = 'cbs.gas_valves'::regclass
    ) THEN
        ALTER TABLE cbs.gas_valves
            ADD CONSTRAINT gas_valves_diameter_chk
            CHECK (diameter_mm IN (63, 90, 110, 125, 160, 200, 250));
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'gas_valves_material_chk'
          AND conrelid = 'cbs.gas_valves'::regclass
    ) THEN
        ALTER TABLE cbs.gas_valves
            ADD CONSTRAINT gas_valves_material_chk
            CHECK (material IN ('steel', 'ductile_iron', 'brass'));
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'gas_valves_status_chk'
          AND conrelid = 'cbs.gas_valves'::regclass
    ) THEN
        ALTER TABLE cbs.gas_valves
            ADD CONSTRAINT gas_valves_status_chk
            CHECK (status IN ('open', 'closed', 'maintenance'));
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'gas_valves_install_year_chk'
          AND conrelid = 'cbs.gas_valves'::regclass
    ) THEN
        ALTER TABLE cbs.gas_valves
            ADD CONSTRAINT gas_valves_install_year_chk
            CHECK (install_year BETWEEN 1995 AND 2024);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'gas_valves_source_chk'
          AND conrelid = 'cbs.gas_valves'::regclass
    ) THEN
        ALTER TABLE cbs.gas_valves
            ADD CONSTRAINT gas_valves_source_chk
            CHECK (source = 'synthetic_demo_yenimahalle');
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'gas_valves_geom_quality_chk'
          AND conrelid = 'cbs.gas_valves'::regclass
    ) THEN
        ALTER TABLE cbs.gas_valves
            ADD CONSTRAINT gas_valves_geom_quality_chk
            CHECK (
                geom IS NOT NULL
                AND ST_SRID(geom) = 3857
                AND GeometryType(geom) = 'POINT'
            );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'gas_valves_related_pipe_fk'
          AND conrelid = 'cbs.gas_valves'::regclass
    ) THEN
        ALTER TABLE cbs.gas_valves
            ADD CONSTRAINT gas_valves_related_pipe_fk
            FOREIGN KEY (related_pipe_id)
            REFERENCES cbs.gas_pipes (pipe_id)
            ON DELETE SET NULL;
    END IF;
END $$;

-- 6. Sentetik boru verisi ekleme
WITH params AS (
    SELECT
        3649100.0::double precision AS x0,
        4860750.0::double precision AS y0,
        95.0::double precision AS dx,
        88.0::double precision AS dy
),
nodes AS (
    SELECT
        row_idx,
        col_idx,
        ST_SetSRID(
            ST_MakePoint(
                x0 + (col_idx * dx)
                    + CASE ((row_idx + col_idx) % 4)
                        WHEN 0 THEN 7.0
                        WHEN 1 THEN -4.0
                        WHEN 2 THEN 3.0
                        ELSE -6.0
                      END,
                y0 + (row_idx * dy)
                    + CASE ((row_idx * 2 + col_idx) % 5)
                        WHEN 0 THEN -5.0
                        WHEN 1 THEN 4.0
                        WHEN 2 THEN 8.0
                        WHEN 3 THEN -3.0
                        ELSE 2.0
                      END
            ),
            3857
        ) AS geom
    FROM params
    CROSS JOIN generate_series(0, 6) AS row_idx
    CROSS JOIN generate_series(0, 8) AS col_idx
),
main_lines AS (
    SELECT
        1000 + row_idx AS sort_key,
        'main_line'::varchar AS pipe_type,
        ST_Multi(ST_MakeLine(geom ORDER BY col_idx))::geometry(MultiLineString, 3857) AS geom
    FROM nodes
    WHERE row_idx IN (1, 3, 5)
    GROUP BY row_idx
),
distribution_lines AS (
    SELECT
        2000 + (a.col_idx * 10) + a.row_idx AS sort_key,
        'distribution'::varchar AS pipe_type,
        ST_Multi(ST_MakeLine(a.geom, b.geom))::geometry(MultiLineString, 3857) AS geom
    FROM nodes a
    JOIN nodes b
      ON b.row_idx = a.row_idx + 1
     AND b.col_idx = a.col_idx
    WHERE a.row_idx < 6
),
service_lines AS (
    SELECT
        3000 + (row_idx * 20) + col_idx AS sort_key,
        'service_line'::varchar AS pipe_type,
        ST_Multi(
            ST_MakeLine(
                geom,
                ST_SetSRID(
                    ST_MakePoint(
                        ST_X(geom)
                            + CASE WHEN col_idx IN (1, 5) THEN -42.0 ELSE 46.0 END,
                        ST_Y(geom)
                            + CASE WHEN row_idx IN (0, 4) THEN 28.0 ELSE -31.0 END
                    ),
                    3857
                )
            )
        )::geometry(MultiLineString, 3857) AS geom
    FROM nodes
    WHERE row_idx IN (0, 2, 4, 6)
      AND col_idx IN (1, 3, 5, 7)
),
pipe_rows AS (
    SELECT
        row_number() OVER (ORDER BY sort_key) AS rn,
        pipe_type,
        geom
    FROM (
        SELECT sort_key, pipe_type, geom FROM main_lines
        UNION ALL
        SELECT sort_key, pipe_type, geom FROM distribution_lines
        UNION ALL
        SELECT sort_key, pipe_type, geom FROM service_lines
    ) pipes
)
INSERT INTO cbs.gas_pipes (
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
    'GP-YMH-' || lpad(rn::text, 3, '0') AS pipe_code,
    pipe_type,
    CASE
        WHEN pipe_type = 'main_line' THEN (ARRAY[160, 200, 250])[((rn % 3) + 1)::int]
        WHEN pipe_type = 'distribution' THEN (ARRAY[90, 110, 125, 160])[((rn % 4) + 1)::int]
        ELSE (ARRAY[63, 90])[((rn % 2) + 1)::int]
    END AS diameter_mm,
    CASE
        WHEN pipe_type = 'main_line' THEN (ARRAY['Steel', 'PE', 'Ductile Iron'])[((rn % 3) + 1)::int]
        WHEN pipe_type = 'distribution' THEN (ARRAY['PE', 'Ductile Iron', 'Steel'])[((rn % 3) + 1)::int]
        ELSE 'PE'
    END AS material,
    CASE
        WHEN pipe_type = 'main_line' THEN 'medium'
        WHEN pipe_type = 'distribution' AND rn % 4 = 0 THEN 'medium'
        ELSE 'low'
    END AS pressure_level,
    CASE
        WHEN pipe_type = 'main_line' THEN 4::numeric
        WHEN pipe_type = 'distribution' AND rn % 4 = 0 THEN 1::numeric
        ELSE 0.3::numeric
    END AS operating_pressure_bar,
    CASE
        WHEN rn % 17 = 0 THEN 'bakımda'
        WHEN rn % 19 = 0 THEN 'pasif'
        ELSE 'aktif'
    END AS status,
    (1995 + ((rn * 7) % 30))::integer AS install_year,
    'synthetic_demo_yenimahalle' AS source,
    geom
FROM pipe_rows
ORDER BY rn;

-- 7. Sentetik vana verisi ekleme
WITH pipe_lines AS (
    SELECT
        pipe_id,
        pipe_code,
        pipe_type,
        diameter_mm,
        ST_GeometryN(geom, 1) AS line_geom
    FROM cbs.gas_pipes
    WHERE source = 'synthetic_demo_yenimahalle'
),
valve_candidates AS (
    SELECT
        pipe_id,
        pipe_type,
        diameter_mm,
        1 AS priority,
        'pipe_start' AS placement_role,
        ST_StartPoint(line_geom) AS geom
    FROM pipe_lines

    UNION ALL

    SELECT
        pipe_id,
        pipe_type,
        diameter_mm,
        1 AS priority,
        'pipe_end' AS placement_role,
        ST_EndPoint(line_geom) AS geom
    FROM pipe_lines

    UNION ALL

    SELECT
        pipe_id,
        pipe_type,
        diameter_mm,
        2 AS priority,
        'main_interval' AS placement_role,
        ST_LineInterpolatePoint(line_geom, fraction) AS geom
    FROM pipe_lines
    CROSS JOIN (VALUES (0.25::double precision), (0.50::double precision), (0.75::double precision)) AS fractions(fraction)
    WHERE pipe_type = 'main_line'

    UNION ALL

    SELECT
        pipe_id,
        pipe_type,
        diameter_mm,
        3 AS priority,
        'distribution_midpoint' AS placement_role,
        ST_LineInterpolatePoint(line_geom, 0.50) AS geom
    FROM pipe_lines
    WHERE pipe_type = 'distribution'
      AND pipe_id % 3 = 0
),
deduped_candidates AS (
    SELECT DISTINCT ON (snap_key)
        pipe_id,
        pipe_type,
        diameter_mm,
        priority,
        placement_role,
        geom
    FROM (
        SELECT
            pipe_id,
            pipe_type,
            diameter_mm,
            priority,
            placement_role,
            geom,
            ST_AsText(ST_SnapToGrid(geom, 0.5)) AS snap_key
        FROM valve_candidates
    ) snapped
    ORDER BY snap_key, priority, pipe_id
),
numbered_valves AS (
    SELECT
        row_number() OVER (
            ORDER BY priority, pipe_id, ST_X(geom), ST_Y(geom)
        ) AS rn,
        pipe_id,
        pipe_type,
        diameter_mm,
        placement_role,
        geom
    FROM deduped_candidates
)
INSERT INTO cbs.gas_valves (
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
    'GV-YMH-' || lpad(rn::text, 3, '0') AS valve_code,
    CASE
        WHEN rn % 17 = 0 THEN 'emergency'
        WHEN pipe_type = 'main_line' AND rn % 4 = 0 THEN 'pressure_reducing'
        WHEN placement_role IN ('main_interval', 'distribution_midpoint') AND rn % 5 = 0 THEN 'control'
        ELSE 'isolation'
    END AS valve_type,
    diameter_mm,
    CASE
        WHEN diameter_mm >= 160 AND rn % 2 = 0 THEN 'steel'
        WHEN diameter_mm >= 110 THEN 'ductile_iron'
        ELSE 'brass'
    END AS material,
    CASE
        WHEN rn % 31 = 0 THEN 'maintenance'
        WHEN rn % 13 = 0 THEN 'closed'
        ELSE 'open'
    END AS status,
    (1995 + ((rn * 5) % 30))::integer AS install_year,
    pipe_id AS related_pipe_id,
    'synthetic_demo_yenimahalle' AS source,
    geom::geometry(Point, 3857)
FROM numbered_valves
WHERE rn <= 96
ORDER BY rn;

-- 8. Spatial index oluşturma
CREATE INDEX IF NOT EXISTS gas_pipes_geom_gix
    ON cbs.gas_pipes
    USING GIST (geom);

CREATE INDEX IF NOT EXISTS gas_valves_geom_gix
    ON cbs.gas_valves
    USING GIST (geom);

COMMIT;

-- 9. Constraint / kalite kontrol sorguları
SET search_path TO cbs, public;

SELECT COUNT(*) AS gas_pipes_count FROM gas_pipes;
SELECT COUNT(*) AS gas_valves_count FROM gas_valves;

SELECT DISTINCT ST_SRID(geom) AS gas_pipes_srid FROM gas_pipes;
SELECT DISTINCT ST_SRID(geom) AS gas_valves_srid FROM gas_valves;

SELECT DISTINCT GeometryType(geom) AS gas_pipes_geometry_type FROM gas_pipes;
SELECT DISTINCT GeometryType(geom) AS gas_valves_geometry_type FROM gas_valves;

SELECT source, COUNT(*) AS pipe_count FROM gas_pipes GROUP BY source;
SELECT source, COUNT(*) AS valve_count FROM gas_valves GROUP BY source;

SELECT COUNT(*) AS gas_pipes_null_geom_count FROM gas_pipes WHERE geom IS NULL;
SELECT COUNT(*) AS gas_valves_null_geom_count FROM gas_valves WHERE geom IS NULL;

SELECT COUNT(*) AS gas_pipes_invalid_geom_count FROM gas_pipes WHERE NOT ST_IsValid(geom);
SELECT COUNT(*) AS gas_valves_invalid_geom_count FROM gas_valves WHERE NOT ST_IsValid(geom);

SELECT COUNT(*) AS valves_with_related_pipe_id
FROM gas_valves
WHERE related_pipe_id IS NOT NULL;

SELECT COUNT(*) AS valves_with_missing_related_pipe
FROM gas_valves v
LEFT JOIN gas_pipes p
  ON p.pipe_id = v.related_pipe_id
WHERE v.related_pipe_id IS NOT NULL
  AND p.pipe_id IS NULL;

SELECT COUNT(*) AS valves_farther_than_half_meter_from_any_pipe
FROM gas_valves v
WHERE NOT EXISTS (
    SELECT 1
    FROM gas_pipes p
    WHERE ST_DWithin(v.geom, p.geom, 0.5)
);

SELECT diameter_mm, COUNT(*) AS pipe_count
FROM gas_pipes
GROUP BY diameter_mm
ORDER BY diameter_mm;

SELECT diameter_mm, COUNT(*) AS valve_count
FROM gas_valves
GROUP BY diameter_mm
ORDER BY diameter_mm;

-- 10. Özet doğrulama sorguları
SELECT
    'minimum_pipe_count' AS check_name,
    COUNT(*) >= 50 AS passed,
    COUNT(*) AS actual_count
FROM gas_pipes;

SELECT
    'minimum_valve_count' AS check_name,
    COUNT(*) >= 80 AS passed,
    COUNT(*) AS actual_count
FROM gas_valves;

SELECT pipe_type, COUNT(*) AS count_by_pipe_type
FROM gas_pipes
GROUP BY pipe_type
ORDER BY pipe_type;

SELECT status, COUNT(*) AS count_by_pipe_status
FROM gas_pipes
GROUP BY status
ORDER BY status;

SELECT valve_type, COUNT(*) AS count_by_valve_type
FROM gas_valves
GROUP BY valve_type
ORDER BY valve_type;

SELECT status, COUNT(*) AS count_by_valve_status
FROM gas_valves
GROUP BY status
ORDER BY status;

SELECT
    ST_XMin(ST_Extent(geom)) AS min_x,
    ST_YMin(ST_Extent(geom)) AS min_y,
    ST_XMax(ST_Extent(geom)) AS max_x,
    ST_YMax(ST_Extent(geom)) AS max_y
FROM gas_pipes;

-- GeoServer yayınlama notu:
-- Bu tablolar GeoServer üzerinde yeni layer olarak yayınlanmalıdır.
-- Önerilen layer adları:
-- usta_cbs:gas_pipes
-- usta_cbs:gas_valves
-- Mevcut usta_cbs:vanalar ve usta_cbs:borular layerları değiştirilmemelidir.
