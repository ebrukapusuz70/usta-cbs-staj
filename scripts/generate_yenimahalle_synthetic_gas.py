"""Yenimahalle için yolları izleyen sentetik gaz demo verisi üretir.
OSM verisini yalnızca geometrik yol iskeleti olarak kullanır.
Üretilen veriler gerçek doğalgaz altyapısını temsil etmez.
"""

from __future__ import annotations

import argparse
import heapq
import json
import math
import urllib.parse
import urllib.request
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_SQL = ROOT / "outputs" / "sql" / "yenimahalle_synthetic_gas.sql"
OUTPUT_DATA = ROOT / "outputs" / "data"
OUTPUT_REPORT = ROOT / "outputs" / "reports" / "synthetic_data_validation.md"
CACHE = ROOT / "outputs" / "data" / "yenimahalle_osm_source.json"
BOUNDARY_CACHE = ROOT / "outputs" / "data" / "yenimahalle_boundary_osm.geojson"
SOURCE = "synthetic_demo_yenimahalle_osm_20260721"
OSM_RELATION_ID = 1812356
TARGET_PIPES = 850
TARGET_VALVES = 620
ALLOWED = {"primary", "secondary", "tertiary", "residential", "unclassified", "living_street", "service"}
FORBIDDEN_KEYS = {
    ("leisure", "park"), ("leisure", "playground"), ("leisure", "pitch"),
    ("landuse", "cemetery"), ("landuse", "military"), ("landuse", "farmland"),
    ("natural", "water"), ("natural", "wood"), ("landuse", "grass"),
}
USER_AGENT = "usta-cbs-stage3-training-project/1.0"
SQL_TEMPLATE = r'''-- Wholly synthetic demo data; OSM roads are only a geometric skeleton.
BEGIN;
SET LOCAL statement_timeout='180s';
CREATE TEMP TABLE stage_pipes_raw(pipe_code text,pipe_type text,diameter_mm integer,material text,pressure_level text,operating_pressure_bar numeric,status text,install_year integer,source text,geom_wkt text) ON COMMIT DROP;
INSERT INTO stage_pipes_raw VALUES
__PIPE_VALUES__;
CREATE TEMP TABLE stage_pipes AS SELECT row_number() over()::integer stage_id,r.*,ST_Multi(ST_Transform(ST_GeomFromText(geom_wkt,4326),3857))::geometry(MultiLineString,3857) geom,ST_Transform(ST_GeomFromText(geom_wkt,4326),32636)::geometry(LineString,32636) geom_metric FROM stage_pipes_raw r;
CREATE INDEX ON stage_pipes USING gist(geom_metric);
CREATE TEMP TABLE stage_valves_raw(valve_code text,valve_type text,diameter_mm integer,material text,status text,install_year integer,related_pipe_code text,source text,geom_wkt text) ON COMMIT DROP;
INSERT INTO stage_valves_raw VALUES
__VALVE_VALUES__;
CREATE TEMP TABLE stage_valves AS SELECT r.*,ST_Transform(ST_GeomFromText(geom_wkt,4326),3857)::geometry(Point,3857) geom,ST_Transform(ST_GeomFromText(geom_wkt,4326),32636)::geometry(Point,32636) geom_metric FROM stage_valves_raw r;
CREATE INDEX ON stage_valves USING gist(geom_metric);
CREATE TEMP TABLE stage_boundary AS SELECT ST_Transform(ST_SetSRID(ST_GeomFromGeoJSON('__BOUNDARY_GEOJSON__'),4326),32636) geom;
DO $$ DECLARE bad integer; max_distance double precision; BEGIN
 IF (SELECT count(*) FROM stage_pipes) NOT BETWEEN 500 AND 1000 THEN RAISE EXCEPTION 'staging pipe count'; END IF;
 IF (SELECT count(*) FROM stage_valves) NOT BETWEEN 500 AND 1000 THEN RAISE EXCEPTION 'staging valve count'; END IF;
 SELECT count(*) INTO bad FROM stage_pipes WHERE geom IS NULL OR ST_IsEmpty(geom) OR NOT ST_IsValid(geom) OR ST_Length(geom_metric)<=0 OR ST_SRID(geom)<>3857 OR GeometryType(geom)<>'MULTILINESTRING'; IF bad<>0 THEN RAISE EXCEPTION 'invalid staging pipes: %',bad; END IF;
 SELECT count(*) INTO bad FROM stage_valves WHERE geom IS NULL OR ST_IsEmpty(geom) OR NOT ST_IsValid(geom) OR ST_SRID(geom)<>3857 OR GeometryType(geom)<>'POINT'; IF bad<>0 THEN RAISE EXCEPTION 'invalid staging valves: %',bad; END IF;
 SELECT count(*)-count(DISTINCT ST_AsEWKB(ST_Normalize(geom))) INTO bad FROM stage_pipes; IF bad<>0 THEN RAISE EXCEPTION 'duplicate pipes: %',bad; END IF;
 SELECT count(*)-count(DISTINCT ST_AsEWKB(geom)) INTO bad FROM stage_valves; IF bad<>0 THEN RAISE EXCEPTION 'duplicate valves: %',bad; END IF;
 SELECT count(*)-count(DISTINCT pipe_code) INTO bad FROM stage_pipes; IF bad<>0 THEN RAISE EXCEPTION 'duplicate pipe codes'; END IF;
 SELECT count(*)-count(DISTINCT valve_code) INTO bad FROM stage_valves; IF bad<>0 THEN RAISE EXCEPTION 'duplicate valve codes'; END IF;
 SELECT count(*) INTO bad FROM stage_valves v LEFT JOIN stage_pipes p ON p.pipe_code=v.related_pipe_code WHERE p.pipe_code IS NULL; IF bad<>0 THEN RAISE EXCEPTION 'unlinked valves: %',bad; END IF;
 SELECT count(*) INTO bad FROM stage_pipes p,stage_boundary b WHERE NOT ST_CoveredBy(p.geom_metric,b.geom); IF bad<>0 THEN RAISE EXCEPTION 'pipes outside boundary: %',bad; END IF;
 SELECT count(*) INTO bad FROM stage_valves v,stage_boundary b WHERE NOT ST_CoveredBy(v.geom_metric,b.geom); IF bad<>0 THEN RAISE EXCEPTION 'valves outside boundary: %',bad; END IF;
 SELECT max(ST_Distance(v.geom_metric,p.geom_metric)) INTO max_distance FROM stage_valves v JOIN stage_pipes p ON p.pipe_code=v.related_pipe_code; IF max_distance>0.10 THEN RAISE EXCEPTION 'valve distance: %',max_distance; END IF;
END $$;
DELETE FROM cbs.gas_valves WHERE COALESCE(source,'') LIKE 'synthetic_demo_yenimahalle%';
DELETE FROM cbs.gas_pipes WHERE COALESCE(source,'') LIKE 'synthetic_demo_yenimahalle%';
INSERT INTO cbs.gas_pipes(pipe_code,pipe_type,diameter_mm,material,pressure_level,operating_pressure_bar,status,install_year,source,geom) SELECT pipe_code,pipe_type,diameter_mm,material,pressure_level,operating_pressure_bar,status,install_year,source,geom FROM stage_pipes ORDER BY stage_id;
INSERT INTO cbs.gas_valves(valve_code,valve_type,diameter_mm,material,status,install_year,related_pipe_id,source,geom) SELECT v.valve_code,v.valve_type,v.diameter_mm,v.material,v.status,v.install_year,p.pipe_id,v.source,v.geom FROM stage_valves v JOIN cbs.gas_pipes p ON p.pipe_code=v.related_pipe_code AND p.source=v.source;
DO $$ DECLARE bad integer; max_distance double precision; BEGIN
 SELECT count(*) INTO bad FROM cbs.gas_valves v LEFT JOIN cbs.gas_pipes p ON p.pipe_id=v.related_pipe_id WHERE v.source='__SOURCE__' AND p.pipe_id IS NULL; IF bad<>0 THEN RAISE EXCEPTION 'live unlinked valves: %',bad; END IF;
 SELECT max(ST_Distance(ST_Transform(v.geom,32636),ST_Transform(p.geom,32636))) INTO max_distance FROM cbs.gas_valves v JOIN cbs.gas_pipes p ON p.pipe_id=v.related_pipe_id WHERE v.source='__SOURCE__'; IF max_distance>0.10 THEN RAISE EXCEPTION 'live valve distance: %',max_distance; END IF;
 IF (SELECT count(*) FROM cbs.gas_pipes WHERE source='__SOURCE__')<>(SELECT count(*) FROM stage_pipes) THEN RAISE EXCEPTION 'live pipe count mismatch'; END IF;
 IF (SELECT count(*) FROM cbs.gas_valves WHERE source='__SOURCE__')<>(SELECT count(*) FROM stage_valves) THEN RAISE EXCEPTION 'live valve count mismatch'; END IF;
END $$;
COMMIT;
'''


@dataclass(frozen=True)
class Edge:
    way_id: int
    u: int
    v: int
    highway: str
    name: str
    coords: tuple[tuple[float, float], ...]  # lon, lat (EPSG:4326)
    length_m: float


def request_json(url: str, data: bytes | None = None, timeout: int = 180) -> Any:
    req = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def fetch_osm(refresh: bool) -> dict[str, Any]:
    if CACHE.exists() and not refresh:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    query = f"""[out:json][timeout:240];
rel({OSM_RELATION_ID}); map_to_area->.district;
(
  way(area.district)[highway~\"^(primary|secondary|tertiary|residential|unclassified|living_street|service)$\"];
  nwr(area.district)[leisure~\"^(park|playground|pitch)$\"];
  nwr(area.district)[landuse~\"^(cemetery|military|farmland|grass)$\"];
  nwr(area.district)[natural~\"^(water|wood)$\"];
);
out tags geom;"""
    payload = urllib.parse.urlencode({"data": query}).encode("utf-8")
    errors: list[str] = []
    for endpoint in ("https://overpass.kumi.systems/api/interpreter", "https://overpass-api.de/api/interpreter"):
        try:
            result = request_json(endpoint, payload)
            CACHE.parent.mkdir(parents=True, exist_ok=True)
            CACHE.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
            return result
        except Exception as exc:  # network endpoints fail independently
            errors.append(f"{endpoint}: {exc}")
    raise RuntimeError("Overpass verisi alınamadı: " + " | ".join(errors))


def fetch_boundary(refresh: bool) -> dict[str, Any]:
    if BOUNDARY_CACHE.exists() and not refresh:
        return json.loads(BOUNDARY_CACHE.read_text(encoding="utf-8"))
    url = f"https://nominatim.openstreetmap.org/lookup?osm_ids=R{OSM_RELATION_ID}&format=jsonv2&polygon_geojson=1"
    rows = request_json(url, timeout=120)
    if not rows or rows[0].get("osm_id") != OSM_RELATION_ID or not rows[0].get("geojson"):
        raise RuntimeError("Yenimahalle idari sınır geometrisi doğrulanamadı")
    feature = {"type": "Feature", "properties": {"name": rows[0].get("display_name"), "osm_relation": OSM_RELATION_ID, "licence": rows[0].get("licence")}, "geometry": rows[0]["geojson"]}
    BOUNDARY_CACHE.parent.mkdir(parents=True, exist_ok=True)
    BOUNDARY_CACHE.write_text(json.dumps(feature, ensure_ascii=False), encoding="utf-8")
    return feature


def boundary_rings(feature: dict[str, Any]) -> list[list[tuple[float, float]]]:
    geometry = feature["geometry"]
    polygons = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
    return [[(float(x), float(y)) for x, y in polygon[0]] for polygon in polygons]


def line_inside_boundary(coords: tuple[tuple[float, float], ...], rings: list[list[tuple[float, float]]]) -> bool:
    samples = list(coords)
    for a, b in zip(coords, coords[1:]):
        samples.extend((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t) for t in (0.25, 0.5, 0.75))
    return all(any(point_in_ring(point, ring) for ring in rings) for point in samples)


def haversine(a: tuple[float, float], b: tuple[float, float]) -> float:
    lon1, lat1, lon2, lat2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    dlon, dlat = lon2 - lon1, lat2 - lat1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 12_742_000 * math.asin(math.sqrt(h))


def line_length(coords: Iterable[tuple[float, float]]) -> float:
    pts = list(coords)
    return sum(haversine(a, b) for a, b in zip(pts, pts[1:]))


def point_in_ring(point: tuple[float, float], ring: list[tuple[float, float]]) -> bool:
    x, y = point
    inside = False
    j = len(ring) - 1
    for i, (xi, yi) in enumerate(ring):
        xj, yj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-15) + xi:
            inside = not inside
        j = i
    return inside


def forbidden_polygons(data: dict[str, Any]) -> list[tuple[tuple[float, float, float, float], list[tuple[float, float]]]]:
    result = []
    for element in data.get("elements", []):
        tags = element.get("tags", {})
        if not any(tags.get(k) == v for k, v in FORBIDDEN_KEYS):
            continue
        geom = element.get("geometry") or []
        ring = [(float(p["lon"]), float(p["lat"])) for p in geom]
        if len(ring) >= 4 and ring[0] == ring[-1]:
            xs = [p[0] for p in ring]; ys = [p[1] for p in ring]
            result.append(((min(xs), min(ys), max(xs), max(ys)), ring))
    return result


def line_hits_forbidden(coords: tuple[tuple[float, float], ...], polygons: list[tuple[tuple[float, float, float, float], list[tuple[float, float]]]]) -> bool:
    samples = list(coords)
    for a, b in zip(coords, coords[1:]):
        samples.extend((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t) for t in (0.25, 0.5, 0.75))
    for x, y in samples:
        for (minx, miny, maxx, maxy), polygon in polygons:
            if minx <= x <= maxx and miny <= y <= maxy and point_in_ring((x, y), polygon):
                return True
    return False


def parse_edges(data: dict[str, Any], boundary: dict[str, Any]) -> tuple[list[Edge], int]:
    polygons = forbidden_polygons(data)
    rings = boundary_rings(boundary)
    node_key: dict[tuple[float, float], int] = {}
    edges: list[Edge] = []
    seen: set[tuple[tuple[float, float], ...]] = set()
    for element in data.get("elements", []):
        tags = element.get("tags", {})
        highway = tags.get("highway")
        if highway not in ALLOWED:
            continue
        if highway == "service" and (tags.get("access") in {"private", "no"} or tags.get("service") in {"parking_aisle", "driveway"}):
            continue
        geom = element.get("geometry") or []
        coords = tuple((round(float(p["lon"]), 7), round(float(p["lat"]), 7)) for p in geom)
        if len(coords) < 2 or not line_inside_boundary(coords, rings) or line_hits_forbidden(coords, polygons):
            continue
        canonical = min(coords, tuple(reversed(coords)))
        if canonical in seen:
            continue
        seen.add(canonical)
        for coord in (coords[0], coords[-1]):
            node_key.setdefault(coord, len(node_key) + 1)
        length = line_length(coords)
        if length < 3:
            continue
        edges.append(Edge(int(element["id"]), node_key[coords[0]], node_key[coords[-1]], highway, tags.get("name", "Adsız yol"), coords, length))
    return edges, len(polygons)


def select_connected(edges: list[Edge]) -> list[Edge]:
    by_node: dict[int, list[int]] = defaultdict(list)
    for i, edge in enumerate(edges):
        by_node[edge.u].append(i); by_node[edge.v].append(i)
    unseen = set(range(len(edges)))
    components: list[list[int]] = []
    while unseen:
        seed = unseen.pop(); component = [seed]; queue = deque([seed])
        while queue:
            idx = queue.popleft(); edge = edges[idx]
            for node in (edge.u, edge.v):
                for other in by_node[node]:
                    if other in unseen:
                        unseen.remove(other); component.append(other); queue.append(other)
        components.append(component)
    largest = max(components, key=len, default=[])
    if len(largest) < TARGET_PIPES:
        raise RuntimeError(f"En büyük bağlı yol bileşeninde yalnızca {len(largest)} segment var")
    candidates = set(largest)
    priority = {"primary": 0, "secondary": 1, "tertiary": 2, "residential": 3, "unclassified": 4, "living_street": 5, "service": 6}
    seed = min(candidates, key=lambda i: (priority[edges[i].highway], -edges[i].length_m, edges[i].way_id))
    chosen: list[int] = []
    frontier: list[tuple[int, float, int]] = []
    queued: set[int] = set()
    def push(idx: int) -> None:
        if idx in candidates and idx not in queued:
            queued.add(idx); heapq.heappush(frontier, (priority[edges[idx].highway], -edges[idx].length_m, idx))
    push(seed)
    while frontier and len(chosen) < TARGET_PIPES:
        _, _, idx = heapq.heappop(frontier)
        if idx not in candidates:
            continue
        candidates.remove(idx); chosen.append(idx)
        edge = edges[idx]
        for node in (edge.u, edge.v):
            for other in by_node[node]: push(other)
    if len(chosen) != TARGET_PIPES:
        raise RuntimeError(f"Bağlı seçim hedefe ulaşmadı: {len(chosen)}")
    return [edges[i] for i in chosen]


def classify(edge: Edge, index: int) -> tuple[str, int, str, str, float]:
    if edge.highway in {"primary", "secondary"}:
        return "main_line", (250, 315, 400)[index % 3], "çelik", "medium", 4.0
    if edge.highway in {"tertiary", "residential"}:
        return "distribution", (90, 110, 125, 160)[index % 4], "PE", "low", 1.0
    return "service_line", (32, 40, 63)[index % 3], "PE", "low", 0.3


def make_valves(edges: list[Edge]) -> list[tuple[int, float, float]]:
    by_node: dict[int, list[int]] = defaultdict(list)
    node_coord: dict[int, tuple[float, float]] = {}
    for i, edge in enumerate(edges):
        by_node[edge.u].append(i); by_node[edge.v].append(i)
        node_coord[edge.u] = edge.coords[0]; node_coord[edge.v] = edge.coords[-1]
    valves: list[tuple[int, float, float]] = []
    used: set[tuple[float, float]] = set()
    for node, incident in sorted(by_node.items(), key=lambda item: (-len(item[1]), item[0])):
        if len(incident) < 2: continue
        coord = node_coord[node]
        if coord not in used:
            used.add(coord); valves.append((incident[0], *coord))
        if len(valves) == TARGET_VALVES: return valves
    for i, edge in enumerate(edges):
        for fraction in (0.5, 0.33, 0.67):
            lengths = [haversine(a, b) for a, b in zip(edge.coords, edge.coords[1:])]
            target = sum(lengths) * fraction
            walked = 0.0
            coord = edge.coords[-1]
            for (a, b), segment_length in zip(zip(edge.coords, edge.coords[1:]), lengths):
                if walked + segment_length >= target:
                    local = (target - walked) / segment_length
                    coord = (round(a[0] + (b[0] - a[0]) * local, 7), round(a[1] + (b[1] - a[1]) * local, 7))
                    break
                walked += segment_length
            if coord not in used:
                used.add(coord); valves.append((i, *coord))
            if len(valves) == TARGET_VALVES: return valves
    raise RuntimeError(f"Vana hedefi üretilemedi: {len(valves)}")


def wkt_line(coords: tuple[tuple[float, float], ...]) -> str:
    return "LINESTRING(" + ",".join(f"{x:.7f} {y:.7f}" for x, y in coords) + ")"


def sql_text(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def write_outputs(edges: list[Edge], valves: list[tuple[int, float, float]], forbidden_count: int, boundary: dict[str, Any]) -> None:
    pipe_rows = []
    pipe_features = []
    for i, edge in enumerate(edges, 1):
        pipe_type, diameter, material, pressure_level, pressure = classify(edge, i)
        code = f"YMH-OSM-P-{i:04d}"; year = 1998 + (i * 7 % 28)
        status = "bakımda" if i % 41 == 0 else ("pasif" if i % 67 == 0 else "aktif")
        pipe_rows.append(f"({sql_text(code)},{sql_text(pipe_type)},{diameter},{sql_text(material)},{sql_text(pressure_level)},{pressure},{sql_text(status)},{year},{sql_text(SOURCE)},{sql_text(wkt_line(edge.coords))})")
        pipe_features.append({"type":"Feature","properties":{"pipe_code":code,"pipe_type":pipe_type,"diameter_mm":diameter,"material":material,"pressure_level":pressure_level,"operating_pressure_bar":pressure,"status":status,"install_year":year,"district":"Yenimahalle","source":SOURCE,"osm_highway":edge.highway,"road_name":edge.name,"synthetic_notice":"Gerçek altyapı değildir; eğitim ve demo amaçlı sentetik veridir."},"geometry":{"type":"MultiLineString","coordinates":[edge.coords]}})
    valve_rows = []
    valve_features = []
    for i, (pipe_idx, lon, lat) in enumerate(valves, 1):
        pipe_type, diameter, _, _, _ = classify(edges[pipe_idx], pipe_idx + 1)
        code=f"YMH-OSM-V-{i:04d}"; pipe_code=f"YMH-OSM-P-{pipe_idx+1:04d}"; year=2000+(i*5%26)
        status="maintenance" if i%97==0 else ("closed" if i%17==0 else "open")
        valve_type="pressure_reducing" if pipe_type=="main_line" else ("control" if i%5==0 else "isolation")
        material="çelik" if diameter>=160 else ("dökme demir" if diameter>=90 else "pirinç")
        valve_rows.append(f"({sql_text(code)},{sql_text(valve_type)},{diameter},{sql_text(material)},{sql_text(status)},{year},{sql_text(pipe_code)},{sql_text(SOURCE)},{sql_text(f'POINT({lon:.7f} {lat:.7f})')})")
        valve_features.append({"type":"Feature","properties":{"valve_code":code,"valve_type":valve_type,"diameter_mm":diameter,"material":material,"status":status,"install_year":year,"related_pipe_code":pipe_code,"district":"Yenimahalle","source":SOURCE,"synthetic_notice":"Gerçek altyapı değildir; eğitim ve demo amaçlı sentetik veridir."},"geometry":{"type":"Point","coordinates":[lon,lat]}})
    boundary_json=json.dumps(boundary["geometry"],separators=(",",":"))
    sql = SQL_TEMPLATE.replace("__SOURCE__", SOURCE).replace("__BOUNDARY_GEOJSON__", boundary_json.replace("'","''")).replace("__PIPE_VALUES__", ",\n".join(pipe_rows)).replace("__VALVE_VALUES__", ",\n".join(valve_rows))
    OUTPUT_SQL.parent.mkdir(parents=True, exist_ok=True); OUTPUT_SQL.write_text(sql, encoding="utf-8")
    OUTPUT_DATA.mkdir(parents=True, exist_ok=True)
    collection=lambda features:{"type":"FeatureCollection","name":"Tamamen sentetik Yenimahalle demo ağı","crs":{"type":"name","properties":{"name":"EPSG:4326"}},"features":features}
    (OUTPUT_DATA/"yenimahalle_gas_pipes.geojson").write_text(json.dumps(collection(pipe_features),ensure_ascii=False),encoding="utf-8")
    (OUTPUT_DATA/"yenimahalle_gas_valves.geojson").write_text(json.dumps(collection(valve_features),ensure_ascii=False),encoding="utf-8")
    counts=Counter(e.highway for e in edges)
    OUTPUT_REPORT.write_text(f"""# Sentetik Veri Staging Raporu\n\n> Bu veriler gerçek doğalgaz altyapısı değildir. Eğitim ve demo amacıyla oluşturulmuş sentetik verilerdir.\n\n- Kaynak: `{SOURCE}`\n- Sınır: OpenStreetMap relation `{OSM_RELATION_ID}` (Yenimahalle idari sınırı)\n- Yol kaynağı: OpenStreetMap/Overpass, sınır içindeki izinli taşıt yolları\n- Boru: `{len(edges)}`\n- Vana: `{len(valves)}`\n- Analiz CRS: `EPSG:32636` (SQL staging testleri)\n- Nihai CRS: `EPSG:3857`\n- Bağlı bileşen: `%100` (tek bağlı yol bileşeninden seçim)\n- Yol koridoru uyumu: `%100` (borular doğrudan seçilen OSM merkez çizgileridir)\n- Yakalanan yasak alan geometrisi: `{forbidden_count}`\n- Yasak alan ihlali: `0` (üretim öncesi örnekleme filtresi; SQL staging testleri ayrıca çalışır)\n- Maksimum vana-boru mesafesi: `0 m` (vanalar boru düğümü/segmenti üzerinde üretilir)\n- Yol sınıfları: `{json.dumps(counts,ensure_ascii=False)}`\n\nCanlı DB ve WFS sonuçları SQL uygulanıp servis testleri tamamlandıktan sonra bu rapora işlenecektir.\n""",encoding="utf-8")


def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("--refresh",action="store_true"); args=parser.parse_args()
    data=fetch_osm(args.refresh); boundary=fetch_boundary(args.refresh); candidates, forbidden_count=parse_edges(data,boundary); edges=select_connected(candidates); valves=make_valves(edges)
    if not 500 <= len(edges) <= 1000 or not 500 <= len(valves) <= 1000: raise RuntimeError("Kayıt hedefleri karşılanmadı")
    write_outputs(edges,valves,forbidden_count,boundary)
    print(json.dumps({"relation":OSM_RELATION_ID,"road_candidates":len(candidates),"forbidden_polygons":forbidden_count,"pipes":len(edges),"valves":len(valves),"source":SOURCE},ensure_ascii=False,indent=2))
    return 0


if __name__ == "__main__": raise SystemExit(main())
