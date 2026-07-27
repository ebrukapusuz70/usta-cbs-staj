-- ============================================================================
-- SENTETIK DEMO ONIZLEME VERISI UYARISI
-- ============================================================================
-- Bu dosyadaki veriler GERCEK DOGALGAZ ALTYAPISINI TEMSIL ETMEZ.
-- OSM yol geometrileri yalnizca sentetik demo agin seklini uretmek icin kullanilir.
-- Canli cbs.gas_pipes ve cbs.gas_valves tablolarina veri yazmaz.
-- ============================================================================

BEGIN;

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE SCHEMA IF NOT EXISTS cbs;

DO $$
DECLARE
    live_pipe_count integer;
    live_valve_count integer;
BEGIN
    SELECT count(*) INTO live_pipe_count FROM cbs.gas_pipes;
    SELECT count(*) INTO live_valve_count FROM cbs.gas_valves;
    IF live_pipe_count <> 0 OR live_valve_count <> 0 THEN
        RAISE EXCEPTION 'Canli tablolar bos degil. gas_pipes=%, gas_valves=%. Preview veri uretilmedi.', live_pipe_count, live_valve_count;
    END IF;
END $$;

DROP TABLE IF EXISTS cbs.gas_valves_preview;
DROP TABLE IF EXISTS cbs.gas_pipes_preview;

CREATE TABLE cbs.gas_pipes_preview (
    pipe_id integer primary key,
    pipe_code varchar,
    pipe_type varchar,
    diameter_mm integer,
    material varchar,
    pressure_level varchar,
    operating_pressure_bar numeric,
    status varchar,
    install_year integer,
    source varchar,
    geom geometry(MultiLineString, 3857)
);

CREATE TABLE cbs.gas_valves_preview (
    valve_id integer primary key,
    valve_code varchar,
    valve_type varchar,
    diameter_mm integer,
    material varchar,
    status varchar,
    install_year integer,
    related_pipe_id integer,
    source varchar,
    geom geometry(Point, 3857)
);

INSERT INTO cbs.gas_pipes_preview (pipe_id, pipe_code, pipe_type, diameter_mm, material, pressure_level, operating_pressure_bar, status, install_year, source, geom)
VALUES
(1, 'GP-OSM-YHM-001', 'distribution', 110, 'polietilen', 'low', 0.3, 'aktif', 2020, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649671.010 4861109.100,3649567.627 4861155.041)', 3857))::geometry(MultiLineString, 3857)),
(2, 'GP-OSM-YHM-002', 'main_line', 250, 'çelik', 'medium', 4.0, 'tamirde', 2017, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649693.697 4861190.787,3649671.010 4861109.100)', 3857))::geometry(MultiLineString, 3857)),
(3, 'GP-OSM-YHM-003', 'main_line', 160, 'PE100', 'medium', 1.0, 'aktif', 2021, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649671.010 4861109.100,3649625.669 4860945.887)', 3857))::geometry(MultiLineString, 3857)),
(4, 'GP-OSM-YHM-004', 'main_line', 200, 'çelik', 'medium', 4.0, 'tamirde', 2015, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649714.669 4861272.256,3649693.697 4861190.787)', 3857))::geometry(MultiLineString, 3857)),
(5, 'GP-OSM-YHM-005', 'distribution', 110, 'polietilen', 'low', 0.3, 'aktif', 2022, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649567.627 4861155.041,3649521.419 4860977.217)', 3857))::geometry(MultiLineString, 3857)),
(6, 'GP-OSM-YHM-006', 'distribution', 125, 'PE100', 'medium', 1.0, 'aktif', 2016, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649567.627 4861155.041,3649479.284 4861193.081)', 3857))::geometry(MultiLineString, 3857)),
(7, 'GP-OSM-YHM-007', 'distribution', 160, 'polietilen', 'medium', 1.0, 'tamirde', 2018, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649479.284 4861193.081,3649509.763 4861278.212)', 3857))::geometry(MultiLineString, 3857)),
(8, 'GP-OSM-YHM-008', 'distribution', 90, 'PE100', 'low', 0.3, 'aktif', 2017, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649509.763 4861278.212,3649538.306 4861349.224)', 3857))::geometry(MultiLineString, 3857)),
(9, 'GP-OSM-YHM-009', 'main_line', 160, 'PE100', 'medium', 1.0, 'aktif', 2024, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649402.552 4860896.650,3649479.284 4861193.081)', 3857))::geometry(MultiLineString, 3857)),
(10, 'GP-OSM-YHM-010', 'main_line', 200, 'çelik', 'medium', 4.0, 'aktif', 2018, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649729.352 4861334.568,3649714.669 4861272.256)', 3857))::geometry(MultiLineString, 3857)),
(11, 'GP-OSM-YHM-011', 'distribution', 160, 'polietilen', 'medium', 1.0, 'aktif', 2025, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649538.306 4861349.224,3649556.028 4861394.223)', 3857))::geometry(MultiLineString, 3857)),
(12, 'GP-OSM-YHM-012', 'distribution', 90, 'PE100', 'low', 0.3, 'aktif', 2019, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649645.573 4861371.389,3649729.352 4861334.568)', 3857))::geometry(MultiLineString, 3857)),
(13, 'GP-OSM-YHM-013', 'main_line', 200, 'PE100', 'medium', 4.0, 'tamirde', 2012, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649693.697 4861190.787,3649509.763 4861278.212)', 3857))::geometry(MultiLineString, 3857)),
(14, 'GP-OSM-YHM-014', 'distribution', 125, 'PE100', 'medium', 1.0, 'aktif', 2020, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649729.352 4861334.568,3649805.717 4861301.306)', 3857))::geometry(MultiLineString, 3857)),
(15, 'GP-OSM-YHM-015', 'main_line', 160, 'PE100', 'medium', 1.0, 'aktif', 2014, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649770.195 4861159.921,3649693.697 4861190.787)', 3857))::geometry(MultiLineString, 3857)),
(16, 'GP-OSM-YHM-016', 'service_line', 40, 'polietilen', 'low', 0.3, 'pasif', 2008, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649579.616 4861400.628,3649645.573 4861371.389)', 3857))::geometry(MultiLineString, 3857)),
(17, 'GP-OSM-YHM-017', 'service_line', 63, 'polietilen', 'low', 0.3, 'aktif', 2015, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649556.028 4861394.223,3649527.207 4861407.368)', 3857))::geometry(MultiLineString, 3857)),
(18, 'GP-OSM-YHM-018', 'distribution', 125, 'PE100', 'medium', 1.0, 'aktif', 2022, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649521.419 4860977.217,3649625.669 4860945.887)', 3857))::geometry(MultiLineString, 3857)),
(19, 'GP-OSM-YHM-019', 'main_line', 200, 'PE100', 'medium', 4.0, 'aktif', 2016, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649625.669 4860945.887,3649586.206 4860803.825)', 3857))::geometry(MultiLineString, 3857)),
(20, 'GP-OSM-YHM-020', 'distribution', 90, 'PE100', 'low', 0.3, 'aktif', 2023, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649770.195 4861159.921,3649717.964 4860984.058)', 3857))::geometry(MultiLineString, 3857)),
(21, 'GP-OSM-YHM-021', 'distribution', 110, 'polietilen', 'low', 0.3, 'aktif', 2017, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649805.717 4861301.306,3649880.847 4861267.696)', 3857))::geometry(MultiLineString, 3857)),
(22, 'GP-OSM-YHM-022', 'distribution', 125, 'PE100', 'medium', 1.0, 'aktif', 2024, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649479.284 4861193.081,3649396.974 4861226.227)', 3857))::geometry(MultiLineString, 3857)),
(23, 'GP-OSM-YHM-023', 'distribution', 160, 'polietilen', 'medium', 1.0, 'aktif', 2018, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649527.207 4861407.368,3649483.548 4861427.282)', 3857))::geometry(MultiLineString, 3857)),
(24, 'GP-OSM-YHM-024', 'main_line', 160, 'çelik', 'medium', 1.0, 'aktif', 2025, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649841.262 4861126.311,3649770.195 4861159.921)', 3857))::geometry(MultiLineString, 3857)),
(25, 'GP-OSM-YHM-025', 'distribution', 110, 'polietilen', 'low', 0.3, 'aktif', 2019, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649714.669 4861272.256,3649538.306 4861349.224)', 3857))::geometry(MultiLineString, 3857)),
(26, 'GP-OSM-YHM-026', 'distribution', 125, 'PE100', 'medium', 1.0, 'aktif', 2013, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649717.964 4860984.058,3649693.908 4860877.303)', 3857))::geometry(MultiLineString, 3857)),
(27, 'GP-OSM-YHM-027', 'distribution', 160, 'polietilen', 'medium', 1.0, 'aktif', 2020, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649880.847 4861267.696,3649957.780 4861235.349)', 3857))::geometry(MultiLineString, 3857)),
(28, 'GP-OSM-YHM-028', 'distribution', 90, 'PE100', 'low', 0.3, 'aktif', 2014, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649770.195 4861159.921,3649805.717 4861301.306)', 3857))::geometry(MultiLineString, 3857)),
(29, 'GP-OSM-YHM-029', 'distribution', 110, 'polietilen', 'low', 0.3, 'aktif', 2021, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649483.548 4861427.282,3649418.648 4861456.898)', 3857))::geometry(MultiLineString, 3857)),
(30, 'GP-OSM-YHM-030', 'distribution', 125, 'PE100', 'medium', 1.0, 'aktif', 2015, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649521.419 4860977.217,3649486.375 4860846.425)', 3857))::geometry(MultiLineString, 3857)),
(31, 'GP-OSM-YHM-031', 'main_line', 200, 'PE100', 'medium', 4.0, 'aktif', 2022, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649509.763 4861278.212,3649365.126 4861343.429)', 3857))::geometry(MultiLineString, 3857)),
(32, 'GP-OSM-YHM-032', 'distribution', 90, 'PE100', 'low', 0.3, 'aktif', 2016, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649841.262 4861126.311,3649778.377 4860893.309)', 3857))::geometry(MultiLineString, 3857)),
(33, 'GP-OSM-YHM-033', 'service_line', 32, 'polietilen', 'low', 0.3, 'aktif', 2023, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649418.648 4861456.898,3649388.948 4861470.596)', 3857))::geometry(MultiLineString, 3857)),
(34, 'GP-OSM-YHM-034', 'distribution', 125, 'PE100', 'medium', 1.0, 'aktif', 2017, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649396.974 4861226.227,3649317.103 4861259.489)', 3857))::geometry(MultiLineString, 3857)),
(35, 'GP-OSM-YHM-035', 'main_line', 250, 'PE100', 'medium', 4.0, 'aktif', 2024, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649782.596 4861525.850,3649729.352 4861334.568)', 3857))::geometry(MultiLineString, 3857)),
(36, 'GP-OSM-YHM-036', 'main_line', 160, 'çelik', 'medium', 1.0, 'aktif', 2018, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649919.419 4861091.655,3649841.262 4861126.311)', 3857))::geometry(MultiLineString, 3857)),
(37, 'GP-OSM-YHM-037', 'distribution', 110, 'polietilen', 'low', 0.3, 'aktif', 2025, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649693.908 4860877.303,3649769.494 4860859.003)', 3857))::geometry(MultiLineString, 3857)),
(38, 'GP-OSM-YHM-038', 'distribution', 125, 'PE100', 'medium', 1.0, 'aktif', 2019, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649880.847 4861267.696,3649841.262 4861126.311)', 3857))::geometry(MultiLineString, 3857)),
(39, 'GP-OSM-YHM-039', 'service_line', 32, 'polietilen', 'low', 0.3, 'aktif', 2013, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649778.377 4860893.309,3649769.494 4860859.003)', 3857))::geometry(MultiLineString, 3857)),
(40, 'GP-OSM-YHM-040', 'service_line', 40, 'polietilen', 'low', 0.3, 'pasif', 2008, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649486.375 4860846.425,3649413.094 4860879.017)', 3857))::geometry(MultiLineString, 3857)),
(41, 'GP-OSM-YHM-041', 'service_line', 63, 'polietilen', 'low', 0.3, 'pasif', 2011, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649957.780 4861235.349,3650047.403 4861194.171)', 3857))::geometry(MultiLineString, 3857)),
(42, 'GP-OSM-YHM-042', 'service_line', 32, 'polietilen', 'low', 0.3, 'pasif', 2005, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649388.948 4861470.596,3649346.191 4861490.306)', 3857))::geometry(MultiLineString, 3857)),
(43, 'GP-OSM-YHM-043', 'distribution', 160, 'polietilen', 'medium', 1.0, 'aktif', 2015, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649586.206 4860803.825,3649500.513 4860840.397)', 3857))::geometry(MultiLineString, 3857)),
(44, 'GP-OSM-YHM-044', 'service_line', 63, 'polietilen', 'low', 0.3, 'pasif', 2011, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649500.513 4860840.397,3649476.390 4860732.352)', 3857))::geometry(MultiLineString, 3857)),
(45, 'GP-OSM-YHM-045', 'service_line', 32, 'polietilen', 'low', 0.3, 'aktif', 2016, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649304.936 4861225.835,3649317.103 4861259.489)', 3857))::geometry(MultiLineString, 3857)),
(46, 'GP-OSM-YHM-046', 'distribution', 125, 'PE100', 'medium', 1.0, 'aktif', 2023, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649538.306 4861349.224,3649398.956 4861413.526)', 3857))::geometry(MultiLineString, 3857)),
(47, 'GP-OSM-YHM-047', 'distribution', 160, 'polietilen', 'medium', 1.0, 'aktif', 2017, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649317.103 4861259.489,3649333.901 4861303.412)', 3857))::geometry(MultiLineString, 3857)),
(48, 'GP-OSM-YHM-048', 'distribution', 90, 'PE100', 'low', 0.3, 'aktif', 2024, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649276.248 4861122.753,3649304.936 4861225.835)', 3857))::geometry(MultiLineString, 3857)),
(49, 'GP-OSM-YHM-049', 'service_line', 40, 'polietilen', 'low', 0.3, 'aktif', 2018, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649782.596 4861525.850,3649746.740 4861546.461)', 3857))::geometry(MultiLineString, 3857)),
(50, 'GP-OSM-YHM-050', 'service_line', 63, 'polietilen', 'low', 0.3, 'pasif', 2011, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649333.901 4861303.412,3649353.961 4861348.483)', 3857))::geometry(MultiLineString, 3857)),
(51, 'GP-OSM-YHM-051', 'distribution', 160, 'polietilen', 'medium', 1.0, 'aktif', 2019, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649860.932 4860869.562,3649778.377 4860893.309)', 3857))::geometry(MultiLineString, 3857)),
(52, 'GP-OSM-YHM-052', 'distribution', 90, 'PE100', 'low', 0.3, 'aktif', 2013, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649855.399 4861485.905,3649782.596 4861525.850)', 3857))::geometry(MultiLineString, 3857)),
(53, 'GP-OSM-YHM-053', 'service_line', 63, 'polietilen', 'low', 0.3, 'aktif', 2020, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649746.740 4861546.461,3649718.866 4861561.509)', 3857))::geometry(MultiLineString, 3857)),
(54, 'GP-OSM-YHM-054', 'distribution', 125, 'PE100', 'medium', 1.0, 'aktif', 2014, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649926.544 4861446.862,3649855.399 4861485.905)', 3857))::geometry(MultiLineString, 3857)),
(55, 'GP-OSM-YHM-055', 'distribution', 160, 'polietilen', 'medium', 1.0, 'aktif', 2021, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649365.126 4861343.429,3649398.956 4861413.526)', 3857))::geometry(MultiLineString, 3857)),
(56, 'GP-OSM-YHM-056', 'service_line', 63, 'polietilen', 'low', 0.3, 'pasif', 2011, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649718.866 4861561.509,3649675.418 4861583.922)', 3857))::geometry(MultiLineString, 3857)),
(57, 'GP-OSM-YHM-057', 'service_line', 32, 'polietilen', 'low', 0.3, 'pasif', 2005, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649248.508 4861023.027,3649276.248 4861122.753)', 3857))::geometry(MultiLineString, 3857)),
(58, 'GP-OSM-YHM-058', 'distribution', 125, 'PE100', 'medium', 1.0, 'aktif', 2016, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649860.932 4860869.562,3649919.419 4861091.655)', 3857))::geometry(MultiLineString, 3857)),
(59, 'GP-OSM-YHM-059', 'distribution', 160, 'polietilen', 'medium', 1.0, 'aktif', 2023, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649919.419 4861091.655,3649957.780 4861235.349)', 3857))::geometry(MultiLineString, 3857)),
(60, 'GP-OSM-YHM-060', 'service_line', 32, 'polietilen', 'low', 0.3, 'pasif', 2005, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3650001.573 4861405.683,3649926.544 4861446.862)', 3857))::geometry(MultiLineString, 3857)),
(61, 'GP-OSM-YHM-061', 'distribution', 110, 'polietilen', 'low', 0.3, 'aktif', 2024, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649398.956 4861413.526,3649418.648 4861456.898)', 3857))::geometry(MultiLineString, 3857)),
(62, 'GP-OSM-YHM-062', 'distribution', 125, 'PE100', 'medium', 1.0, 'aktif', 2018, 'synthetic_demo_yenimahalle_osm_preview', ST_Multi(ST_GeomFromText('LINESTRING(3649769.494 4860859.003,3649737.946 4860737.116)', 3857))::geometry(MultiLineString, 3857));

INSERT INTO cbs.gas_valves_preview (valve_id, valve_code, valve_type, diameter_mm, material, status, install_year, related_pipe_id, source, geom)
VALUES
(1, 'GV-OSM-YHM-001', 'isolation', 250, 'ductile_iron', 'kapalı', 2018, 2, 'synthetic_demo_yenimahalle_osm_preview', ST_GeomFromText('POINT(3649671.010 4861109.100)', 3857)::geometry(Point, 3857)),
(2, 'GV-OSM-YHM-002', 'isolation', 250, 'brass', 'kapalı', 2019, 2, 'synthetic_demo_yenimahalle_osm_preview', ST_GeomFromText('POINT(3649693.697 4861190.787)', 3857)::geometry(Point, 3857)),
(3, 'GV-OSM-YHM-003', 'isolation', 200, 'steel', 'kapalı', 2015, 4, 'synthetic_demo_yenimahalle_osm_preview', ST_GeomFromText('POINT(3649714.669 4861272.256)', 3857)::geometry(Point, 3857)),
(4, 'GV-OSM-YHM-004', 'isolation', 160, 'ductile_iron', 'kapalı', 2019, 7, 'synthetic_demo_yenimahalle_osm_preview', ST_GeomFromText('POINT(3649479.284 4861193.081)', 3857)::geometry(Point, 3857)),
(5, 'GV-OSM-YHM-005', 'isolation', 200, 'brass', 'kapalı', 2014, 13, 'synthetic_demo_yenimahalle_osm_preview', ST_GeomFromText('POINT(3649509.763 4861278.212)', 3857)::geometry(Point, 3857)),
(6, 'GV-OSM-YHM-006', 'isolation', 125, 'steel', 'bakımda', 2016, 6, 'synthetic_demo_yenimahalle_osm_preview', ST_GeomFromText('POINT(3649567.627 4861155.041)', 3857)::geometry(Point, 3857)),
(7, 'GV-OSM-YHM-007', 'control', 160, 'ductile_iron', 'açık', 2025, 11, 'synthetic_demo_yenimahalle_osm_preview', ST_GeomFromText('POINT(3649538.306 4861349.224)', 3857)::geometry(Point, 3857)),
(8, 'GV-OSM-YHM-008', 'pressure_reducing', 125, 'brass', 'açık', 2022, 14, 'synthetic_demo_yenimahalle_osm_preview', ST_GeomFromText('POINT(3649805.717 4861301.306)', 3857)::geometry(Point, 3857)),
(9, 'GV-OSM-YHM-009', 'isolation', 160, 'steel', 'açık', 2014, 15, 'synthetic_demo_yenimahalle_osm_preview', ST_GeomFromText('POINT(3649770.195 4861159.921)', 3857)::geometry(Point, 3857)),
(10, 'GV-OSM-YHM-010', 'control', 125, 'ductile_iron', 'açık', 2023, 18, 'synthetic_demo_yenimahalle_osm_preview', ST_GeomFromText('POINT(3649521.419 4860977.217)', 3857)::geometry(Point, 3857)),
(11, 'GV-OSM-YHM-011', 'pressure_reducing', 200, 'brass', 'açık', 2018, 19, 'synthetic_demo_yenimahalle_osm_preview', ST_GeomFromText('POINT(3649625.669 4860945.887)', 3857)::geometry(Point, 3857)),
(12, 'GV-OSM-YHM-012', 'isolation', 160, 'steel', 'açık', 2025, 24, 'synthetic_demo_yenimahalle_osm_preview', ST_GeomFromText('POINT(3649841.262 4861126.311)', 3857)::geometry(Point, 3857)),
(13, 'GV-OSM-YHM-013', 'control', 160, 'ductile_iron', 'açık', 2021, 27, 'synthetic_demo_yenimahalle_osm_preview', ST_GeomFromText('POINT(3649880.847 4861267.696)', 3857)::geometry(Point, 3857)),
(14, 'GV-OSM-YHM-014', 'pressure_reducing', 160, 'brass', 'açık', 2022, 27, 'synthetic_demo_yenimahalle_osm_preview', ST_GeomFromText('POINT(3649957.780 4861235.349)', 3857)::geometry(Point, 3857)),
(15, 'GV-OSM-YHM-015', 'isolation', 110, 'steel', 'açık', 2021, 29, 'synthetic_demo_yenimahalle_osm_preview', ST_GeomFromText('POINT(3649418.648 4861456.898)', 3857)::geometry(Point, 3857)),
(16, 'GV-OSM-YHM-016', 'control', 250, 'ductile_iron', 'açık', 2025, 35, 'synthetic_demo_yenimahalle_osm_preview', ST_GeomFromText('POINT(3649729.352 4861334.568)', 3857)::geometry(Point, 3857)),
(17, 'GV-OSM-YHM-017', 'pressure_reducing', 250, 'brass', 'açık', 2025, 35, 'synthetic_demo_yenimahalle_osm_preview', ST_GeomFromText('POINT(3649782.596 4861525.850)', 3857)::geometry(Point, 3857)),
(18, 'GV-OSM-YHM-018', 'isolation', 160, 'steel', 'açık', 2018, 36, 'synthetic_demo_yenimahalle_osm_preview', ST_GeomFromText('POINT(3649919.419 4861091.655)', 3857)::geometry(Point, 3857)),
(19, 'GV-OSM-YHM-019', 'control', 160, 'ductile_iron', 'açık', 2018, 47, 'synthetic_demo_yenimahalle_osm_preview', ST_GeomFromText('POINT(3649317.103 4861259.489)', 3857)::geometry(Point, 3857)),
(20, 'GV-OSM-YHM-020', 'pressure_reducing', 160, 'brass', 'açık', 2021, 51, 'synthetic_demo_yenimahalle_osm_preview', ST_GeomFromText('POINT(3649778.377 4860893.309)', 3857)::geometry(Point, 3857)),
(21, 'GV-OSM-YHM-021', 'isolation', 160, 'steel', 'açık', 2021, 55, 'synthetic_demo_yenimahalle_osm_preview', ST_GeomFromText('POINT(3649398.956 4861413.526)', 3857)::geometry(Point, 3857)),
(22, 'GV-OSM-YHM-022', 'control', 125, 'ductile_iron', 'açık', 2019, 62, 'synthetic_demo_yenimahalle_osm_preview', ST_GeomFromText('POINT(3649769.494 4860859.003)', 3857)::geometry(Point, 3857)),
(23, 'GV-OSM-YHM-023', 'pressure_reducing', 200, 'brass', 'açık', 2018, 19, 'synthetic_demo_yenimahalle_osm_preview', ST_GeomFromText('POINT(3649586.206 4860803.825)', 3857)::geometry(Point, 3857)),
(24, 'GV-OSM-YHM-024', 'isolation', 200, 'steel', 'açık', 2022, 31, 'synthetic_demo_yenimahalle_osm_preview', ST_GeomFromText('POINT(3649365.126 4861343.429)', 3857)::geometry(Point, 3857)),
(25, 'GV-OSM-YHM-025', 'isolation', 40, 'ductile_iron', 'açık', 2009, 16, 'synthetic_demo_yenimahalle_osm_preview', ST_GeomFromText('POINT(3649579.616 4861400.628)', 3857)::geometry(Point, 3857)),
(26, 'GV-OSM-YHM-026', 'isolation', 40, 'brass', 'açık', 2010, 40, 'synthetic_demo_yenimahalle_osm_preview', ST_GeomFromText('POINT(3649413.094 4860879.017)', 3857)::geometry(Point, 3857)),
(27, 'GV-OSM-YHM-027', 'isolation', 63, 'steel', 'açık', 2011, 41, 'synthetic_demo_yenimahalle_osm_preview', ST_GeomFromText('POINT(3650047.403 4861194.171)', 3857)::geometry(Point, 3857)),
(28, 'GV-OSM-YHM-028', 'isolation', 32, 'ductile_iron', 'açık', 2006, 42, 'synthetic_demo_yenimahalle_osm_preview', ST_GeomFromText('POINT(3649346.191 4861490.306)', 3857)::geometry(Point, 3857)),
(29, 'GV-OSM-YHM-029', 'isolation', 63, 'brass', 'açık', 2013, 44, 'synthetic_demo_yenimahalle_osm_preview', ST_GeomFromText('POINT(3649476.390 4860732.352)', 3857)::geometry(Point, 3857)),
(30, 'GV-OSM-YHM-030', 'isolation', 63, 'steel', 'açık', 2011, 50, 'synthetic_demo_yenimahalle_osm_preview', ST_GeomFromText('POINT(3649353.961 4861348.483)', 3857)::geometry(Point, 3857)),
(31, 'GV-OSM-YHM-031', 'isolation', 63, 'ductile_iron', 'açık', 2012, 56, 'synthetic_demo_yenimahalle_osm_preview', ST_GeomFromText('POINT(3649675.418 4861583.922)', 3857)::geometry(Point, 3857)),
(32, 'GV-OSM-YHM-032', 'isolation', 32, 'brass', 'açık', 2007, 57, 'synthetic_demo_yenimahalle_osm_preview', ST_GeomFromText('POINT(3649248.508 4861023.027)', 3857)::geometry(Point, 3857)),
(33, 'GV-OSM-YHM-033', 'isolation', 32, 'steel', 'açık', 2005, 60, 'synthetic_demo_yenimahalle_osm_preview', ST_GeomFromText('POINT(3650001.573 4861405.683)', 3857)::geometry(Point, 3857)),
(34, 'GV-OSM-YHM-034', 'isolation', 160, 'ductile_iron', 'açık', 2025, 9, 'synthetic_demo_yenimahalle_osm_preview', ST_GeomFromText('POINT(3649402.552 4860896.650)', 3857)::geometry(Point, 3857)),
(35, 'GV-OSM-YHM-035', 'isolation', 125, 'brass', 'açık', 2020, 62, 'synthetic_demo_yenimahalle_osm_preview', ST_GeomFromText('POINT(3649737.946 4860737.116)', 3857)::geometry(Point, 3857));

CREATE INDEX idx_gas_pipes_preview_geom ON cbs.gas_pipes_preview USING GIST (geom);
CREATE INDEX idx_gas_valves_preview_geom ON cbs.gas_valves_preview USING GIST (geom);
ANALYZE cbs.gas_pipes_preview;
ANALYZE cbs.gas_valves_preview;

DO $$
DECLARE
    pipe_count integer;
    valve_count integer;
    invalid_pipe_count integer;
    invalid_valve_count integer;
    duplicate_pipe_count integer;
    far_valve_count integer;
BEGIN
    SELECT count(*) INTO pipe_count FROM cbs.gas_pipes_preview;
    SELECT count(*) INTO valve_count FROM cbs.gas_valves_preview;
    SELECT count(*) INTO invalid_pipe_count FROM cbs.gas_pipes_preview WHERE NOT ST_IsValid(geom);
    SELECT count(*) INTO invalid_valve_count FROM cbs.gas_valves_preview WHERE NOT ST_IsValid(geom);
    SELECT count(*) - count(DISTINCT ST_AsBinary(ST_SnapToGrid(geom, 0.001))) INTO duplicate_pipe_count FROM cbs.gas_pipes_preview;
    SELECT count(*) INTO far_valve_count
    FROM cbs.gas_valves_preview v
    WHERE NOT EXISTS (
        SELECT 1 FROM cbs.gas_pipes_preview p WHERE ST_DWithin(v.geom, p.geom, 0.5)
    );
    IF pipe_count < 50 OR pipe_count > 80 THEN RAISE EXCEPTION 'Preview boru sayisi aralik disi: %', pipe_count; END IF;
    IF valve_count < 20 OR valve_count > 35 THEN RAISE EXCEPTION 'Preview vana sayisi aralik disi: %', valve_count; END IF;
    IF invalid_pipe_count > 0 OR invalid_valve_count > 0 THEN RAISE EXCEPTION 'Gecersiz geometri bulundu. Boru=%, Vana=%', invalid_pipe_count, invalid_valve_count; END IF;
    IF duplicate_pipe_count > 0 THEN RAISE EXCEPTION 'Mukerrer boru geometrisi bulundu: %', duplicate_pipe_count; END IF;
    IF far_valve_count > 0 THEN RAISE EXCEPTION 'Borudan 0.5 metreden uzak vana bulundu: %', far_valve_count; END IF;
    RAISE NOTICE 'Preview veri hazir. Boru=%, Vana=%', pipe_count, valve_count;
END $$;

COMMIT;

-- DOGRULAMA RAPOR SORGULARI
SELECT count(*) AS toplam_boru,
       count(*) FILTER (WHERE status = 'aktif') AS aktif_boru,
       count(*) FILTER (WHERE status = 'pasif') AS pasif_boru,
       count(*) FILTER (WHERE status = 'tamirde') AS tamirde_boru
FROM cbs.gas_pipes_preview;

SELECT pipe_type, count(*) AS boru_sayisi FROM cbs.gas_pipes_preview GROUP BY pipe_type ORDER BY pipe_type;

SELECT count(*) AS toplam_vana,
       count(*) FILTER (WHERE status = 'açık') AS acik_vana,
       count(*) FILTER (WHERE status = 'kapalı') AS kapali_vana,
       count(*) FILTER (WHERE status = 'bakımda') AS bakimda_vana
FROM cbs.gas_valves_preview;

SELECT count(*) FILTER (WHERE NOT ST_IsValid(geom)) AS gecersiz_boru_geometrisi FROM cbs.gas_pipes_preview;
SELECT count(*) FILTER (WHERE NOT ST_IsValid(geom)) AS gecersiz_vana_geometrisi FROM cbs.gas_valves_preview;
SELECT count(*) - count(DISTINCT ST_AsBinary(ST_SnapToGrid(geom, 0.001))) AS mukerrer_boru_sayisi FROM cbs.gas_pipes_preview;
SELECT count(*) AS borudan_uzak_vana_sayisi FROM cbs.gas_valves_preview v WHERE NOT EXISTS (SELECT 1 FROM cbs.gas_pipes_preview p WHERE ST_DWithin(v.geom, p.geom, 0.5));
SELECT 'gas_pipes_preview' AS layer_name, ST_SRID(geom) AS srid, ST_GeometryType(geom) AS geometry_type, count(*) FROM cbs.gas_pipes_preview GROUP BY ST_SRID(geom), ST_GeometryType(geom)
UNION ALL
SELECT 'gas_valves_preview', ST_SRID(geom), ST_GeometryType(geom), count(*) FROM cbs.gas_valves_preview GROUP BY ST_SRID(geom), ST_GeometryType(geom);
SELECT 'gas_pipes_preview' AS layer_name, ST_AsText(ST_Extent(geom)) AS extent FROM cbs.gas_pipes_preview
UNION ALL
SELECT 'gas_valves_preview', ST_AsText(ST_Extent(geom)) FROM cbs.gas_valves_preview;
SELECT 'generator_yol_uzak_boru_sayisi' AS metric, 0 AS value;
SELECT 'generator_baglantisiz_boru_ucu_sayisi' AS metric, 0 AS value;
SELECT 'canli_gas_pipes' AS table_name, count(*) AS count FROM cbs.gas_pipes UNION ALL SELECT 'canli_gas_valves', count(*) FROM cbs.gas_valves;
