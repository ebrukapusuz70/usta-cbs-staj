"""Yol, sınır ve ağ topolojisi kurallarını doğrular.
Yerel GeoJSON dosyalarından yol ve yasak alan verilerini okur.
Geçerli topoloji bilgisini backend ve frontend için hazırlar.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

from .config import get_network_rule_settings


# Topoloji verisi okunamadığında veya çizim kurala uymadığında özel hata üretir.
class TopologyUnavailableError(RuntimeError):
    """Yerel ve doğrulanmış Stage 4 topoloji kaynakları kullanılamadığında oluşur."""


class TopologyValidationError(ValueError):
    """Bir düzenleme geometrisi yerel topoloji kurallarını ihlal ettiğinde oluşur."""


ALLOWED_HIGHWAYS = {
    "primary",
    "secondary",
    "tertiary",
    "residential",
    "unclassified",
    "living_street",
    "service",
}
FORBIDDEN_KEYS = {
    ("leisure", "park"),
    ("leisure", "playground"),
    ("leisure", "pitch"),
    ("landuse", "cemetery"),
    ("landuse", "military"),
    ("landuse", "farmland"),
    ("landuse", "grass"),
    ("natural", "water"),
    ("natural", "wood"),
}

_NETWORK_RULES = get_network_rule_settings()
SNAP_TOLERANCE_M = _NETWORK_RULES.snap_tolerance_m
VALVE_PREFERRED_SNAP_M = 10.0
VALVE_MAX_SNAP_M = 15.0
VALVE_MIN_SPACING_M = 10.0
PIPE_ROAD_CORRIDOR_M = 5.0
PIPE_MIN_ROAD_RATIO = 0.98
PIPE_MIN_LENGTH_M = _NETWORK_RULES.pipe_min_length_m
PIPE_MAX_LENGTH_M = _NETWORK_RULES.pipe_max_length_m
PIPE_NETWORK_TOUCH_M = 0.10
ROUTE_CLICK_SNAP_M = SNAP_TOLERANCE_M

_WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
_OSM_SOURCE = _WORKSPACE_ROOT / "outputs" / "data" / "yenimahalle_osm_source.json"
_BOUNDARY_SOURCE = _WORKSPACE_ROOT / "outputs" / "data" / "yenimahalle_boundary_osm.geojson"
_LINESTRING_RE = re.compile(r"^\s*LINESTRING\s*\((.*)\)\s*$", re.IGNORECASE | re.DOTALL)
_POINT_RE = re.compile(r"^\s*POINT\s*\((.*)\)\s*$", re.IGNORECASE | re.DOTALL)


@dataclass(frozen=True)
class PolygonData:
    rings_lonlat: tuple[tuple[tuple[float, float], ...], ...]
    rings_metric: tuple[tuple[tuple[float, float], ...], ...]
    bbox_lonlat: tuple[float, float, float, float]


@dataclass(frozen=True)
class TopologyDataset:
    public_payload: dict[str, Any]
    road_segments_metric: tuple[tuple[float, float, float, float], ...]
    road_grid: dict[tuple[int, int], tuple[int, ...]]
    restricted: tuple[PolygonData, ...]
    restricted_grid: dict[tuple[int, int], tuple[int, ...]]
    boundary: tuple[PolygonData, ...]


# Yerel topoloji dosyasını okur ve temel JSON yapısını kontrol eder.
def _read_json(path: Path) -> dict[str, Any]:
    try:
        if not path.is_file() or path.stat().st_size == 0:
            raise TopologyUnavailableError(f"Zorunlu yerel topoloji dosyası bulunamadı: {path.name}")
        return json.loads(path.read_text(encoding="utf-8"))
    except TopologyUnavailableError:
        raise
    except (OSError, json.JSONDecodeError) as exc:
        raise TopologyUnavailableError(f"Yerel topoloji dosyası okunamadı: {path.name}") from exc


def _point_in_ring(point: tuple[float, float], ring: tuple[tuple[float, float], ...]) -> bool:
    x, y = point
    inside = False
    j = len(ring) - 1
    for i, (xi, yi) in enumerate(ring):
        xj, yj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-15) + xi:
            inside = not inside
        j = i
    return inside


def _point_in_polygon(point: tuple[float, float], polygon: PolygonData, *, metric: bool = False) -> bool:
    rings = polygon.rings_metric if metric else polygon.rings_lonlat
    return bool(rings and _point_in_ring(point, rings[0]) and not any(_point_in_ring(point, hole) for hole in rings[1:]))


def _boundary_polygons(feature: dict[str, Any]) -> list[list[list[tuple[float, float]]]]:
    geometry = feature.get("geometry") or {}
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates") or []
    if geometry_type == "Polygon":
        polygons = [coordinates]
    elif geometry_type == "MultiPolygon":
        polygons = coordinates
    else:
        raise TopologyUnavailableError("Yenimahalle sınırı Polygon veya MultiPolygon olmalıdır.")
    return [
        [[(float(x), float(y)) for x, y in ring] for ring in polygon if len(ring) >= 4]
        for polygon in polygons
    ]


def _mercator_to_lonlat(coordinate: tuple[float, float]) -> tuple[float, float]:
    radius = 6_378_137.0
    lon = math.degrees(coordinate[0] / radius)
    lat = math.degrees(2.0 * math.atan(math.exp(coordinate[1] / radius)) - math.pi / 2.0)
    return lon, lat


def _lonlat_to_utm36(coordinate: tuple[float, float]) -> tuple[float, float]:
    """WGS84 coğrafi koordinatını EPSG:32636 metre koordinatına dönüştürür."""
    lon, lat = coordinate
    semi_major = 6_378_137.0
    eccentricity_sq = 0.00669438
    scale = 0.9996
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    origin_rad = math.radians(33.0)
    eccentric_prime_sq = eccentricity_sq / (1.0 - eccentricity_sq)
    n = semi_major / math.sqrt(1.0 - eccentricity_sq * math.sin(lat_rad) ** 2)
    t = math.tan(lat_rad) ** 2
    c = eccentric_prime_sq * math.cos(lat_rad) ** 2
    a = math.cos(lat_rad) * (lon_rad - origin_rad)
    m = semi_major * (
        (1 - eccentricity_sq / 4 - 3 * eccentricity_sq**2 / 64 - 5 * eccentricity_sq**3 / 256) * lat_rad
        - (3 * eccentricity_sq / 8 + 3 * eccentricity_sq**2 / 32 + 45 * eccentricity_sq**3 / 1024) * math.sin(2 * lat_rad)
        + (15 * eccentricity_sq**2 / 256 + 45 * eccentricity_sq**3 / 1024) * math.sin(4 * lat_rad)
        - (35 * eccentricity_sq**3 / 3072) * math.sin(6 * lat_rad)
    )
    easting = scale * n * (
        a + (1 - t + c) * a**3 / 6 + (5 - 18 * t + t**2 + 72 * c - 58 * eccentric_prime_sq) * a**5 / 120
    ) + 500_000.0
    northing = scale * (
        m + n * math.tan(lat_rad) * (
            a**2 / 2 + (5 - t + 9 * c + 4 * c**2) * a**4 / 24
            + (61 - 58 * t + t**2 + 600 * c - 330 * eccentric_prime_sq) * a**6 / 720
        )
    )
    return easting, northing


def _polygon_data(rings: Iterable[Iterable[tuple[float, float]]]) -> PolygonData:
    lonlat = tuple(tuple(ring) for ring in rings)
    metric = tuple(tuple(_lonlat_to_utm36(point) for point in ring) for ring in lonlat)
    xs = [point[0] for ring in lonlat for point in ring]
    ys = [point[1] for ring in lonlat for point in ring]
    return PolygonData(lonlat, metric, (min(xs), min(ys), max(xs), max(ys)))


def _line_inside_boundary(coords: tuple[tuple[float, float], ...], boundary: tuple[PolygonData, ...]) -> bool:
    samples = list(coords)
    for a, b in zip(coords, coords[1:]):
        samples.extend((a[0] + (b[0] - a[0]) * fraction, a[1] + (b[1] - a[1]) * fraction) for fraction in (0.25, 0.5, 0.75))
    return all(any(_point_in_polygon(point, polygon) for polygon in boundary) for point in samples)


def _line_hits_restricted(
    coords: tuple[tuple[float, float], ...],
    restricted: tuple[PolygonData, ...],
    restricted_grid: dict[tuple[int, int], tuple[int, ...]],
) -> bool:
    samples = list(coords)
    for a, b in zip(coords, coords[1:]):
        samples.extend((a[0] + (b[0] - a[0]) * fraction, a[1] + (b[1] - a[1]) * fraction) for fraction in (0.25, 0.5, 0.75))
    for point in samples:
        metric = _lonlat_to_utm36(point)
        cell = (math.floor(metric[0] / 100.0), math.floor(metric[1] / 100.0))
        for index in restricted_grid.get(cell, ()):
            polygon = restricted[index]
            minx, miny, maxx, maxy = polygon.bbox_lonlat
            if minx <= point[0] <= maxx and miny <= point[1] <= maxy and _point_in_polygon(point, polygon):
                return True
    return False


def _grid_cells_for_bbox(minx: float, miny: float, maxx: float, maxy: float, size: float = 100.0) -> Iterable[tuple[int, int]]:
    for gx in range(math.floor(minx / size), math.floor(maxx / size) + 1):
        for gy in range(math.floor(miny / size), math.floor(maxy / size) + 1):
            yield gx, gy


def _freeze_grid(grid: dict[tuple[int, int], list[int]]) -> dict[tuple[int, int], tuple[int, ...]]:
    return {cell: tuple(indices) for cell, indices in grid.items()}


def _extract_restricted(osm: dict[str, Any]) -> tuple[tuple[PolygonData, ...], list[dict[str, Any]]]:
    polygons: list[PolygonData] = []
    features: list[dict[str, Any]] = []
    for element in osm.get("elements", []):
        tags = element.get("tags") or {}
        if not any(tags.get(key) == value for key, value in FORBIDDEN_KEYS):
            continue
        coords = tuple((float(point["lon"]), float(point["lat"])) for point in (element.get("geometry") or []))
        if len(coords) < 4 or coords[0] != coords[-1]:
            continue
        polygons.append(_polygon_data((coords,)))
        features.append({
            "type": "Feature",
            "id": f"osm-restricted-{element.get('type', 'way')}-{element.get('id')}",
            "properties": {"osm_id": element.get("id"), "restriction": next((f"{key}={value}" for key, value in FORBIDDEN_KEYS if tags.get(key) == value), "restricted")},
            "geometry": {"type": "Polygon", "coordinates": [coords]},
        })
    return tuple(polygons), features


@lru_cache(maxsize=1)
def get_topology_dataset() -> TopologyDataset:
    osm = _read_json(_OSM_SOURCE)
    boundary_feature = _read_json(_BOUNDARY_SOURCE)
    boundary = tuple(_polygon_data(polygon) for polygon in _boundary_polygons(boundary_feature))
    restricted, restricted_features = _extract_restricted(osm)

    restricted_grid_mutable: dict[tuple[int, int], list[int]] = {}
    for index, polygon in enumerate(restricted):
        xs = [point[0] for ring in polygon.rings_metric for point in ring]
        ys = [point[1] for ring in polygon.rings_metric for point in ring]
        for cell in _grid_cells_for_bbox(min(xs), min(ys), max(xs), max(ys)):
            restricted_grid_mutable.setdefault(cell, []).append(index)
    restricted_grid = _freeze_grid(restricted_grid_mutable)

    roads: list[dict[str, Any]] = []
    metric_segments: list[tuple[float, float, float, float]] = []
    seen: set[tuple[tuple[float, float], ...]] = set()
    for element in osm.get("elements", []):
        tags = element.get("tags") or {}
        highway = tags.get("highway")
        if highway not in ALLOWED_HIGHWAYS:
            continue
        if highway == "service" and (tags.get("access") in {"private", "no"} or tags.get("service") in {"parking_aisle", "driveway"}):
            continue
        coords = tuple((round(float(point["lon"]), 7), round(float(point["lat"]), 7)) for point in (element.get("geometry") or []))
        # Kaynak Overpass sorgusu OSM relation 1812356 alanıyla sınırlandırılmış ve önceden
        # doğrulanmıştır. Burada yasak alan filtresi tekrar uygulanır; kesin sınır kontrolü
        # her yazma isteğinde ara örnekler dahil ayrıca yapılır.
        if len(coords) < 2 or _line_hits_restricted(coords, restricted, restricted_grid):
            continue
        canonical = min(coords, tuple(reversed(coords)))
        if canonical in seen:
            continue
        seen.add(canonical)
        roads.append({
            "type": "Feature",
            "id": f"osm-road-way-{element.get('id')}",
            "properties": {"osm_id": element.get("id"), "highway": highway, "name": tags.get("name") or "Adsız yol"},
            "geometry": {"type": "LineString", "coordinates": coords},
        })
        metric = tuple(_lonlat_to_utm36(point) for point in coords)
        metric_segments.extend((a[0], a[1], b[0], b[1]) for a, b in zip(metric, metric[1:]) if a != b)

    if not roads or not metric_segments or not restricted or not boundary:
        raise TopologyUnavailableError("Yerel yol, yasak alan veya sınır topolojisi boş; Stage 4 düzenleme durduruldu.")

    road_grid_mutable: dict[tuple[int, int], list[int]] = {}
    for index, (x1, y1, x2, y2) in enumerate(metric_segments):
        for cell in _grid_cells_for_bbox(min(x1, x2) - PIPE_ROAD_CORRIDOR_M, min(y1, y2) - PIPE_ROAD_CORRIDOR_M, max(x1, x2) + PIPE_ROAD_CORRIDOR_M, max(y1, y2) + PIPE_ROAD_CORRIDOR_M):
            road_grid_mutable.setdefault(cell, []).append(index)

    payload = {
        "source": "verified_local_osm_cache",
        "data_crs": "EPSG:4326",
        "analysis_crs": "EPSG:32636",
        "roads": {"type": "FeatureCollection", "features": roads},
        "restricted_areas": {"type": "FeatureCollection", "features": restricted_features},
        "boundary": boundary_feature,
        "rules": {
            "snap_tolerance_m": SNAP_TOLERANCE_M,
            "valve_preferred_snap_m": VALVE_PREFERRED_SNAP_M,
            "valve_max_snap_m": VALVE_MAX_SNAP_M,
            "valve_min_spacing_m": VALVE_MIN_SPACING_M,
            "pipe_road_corridor_m": PIPE_ROAD_CORRIDOR_M,
            "pipe_min_road_ratio": PIPE_MIN_ROAD_RATIO,
            "pipe_min_length_m": PIPE_MIN_LENGTH_M,
            "pipe_max_length_m": PIPE_MAX_LENGTH_M,
            "pipe_network_touch_m": PIPE_NETWORK_TOUCH_M,
            "route_click_snap_m": ROUTE_CLICK_SNAP_M,
        },
    }
    return TopologyDataset(
        public_payload=payload,
        road_segments_metric=tuple(metric_segments),
        road_grid=_freeze_grid(road_grid_mutable),
        restricted=restricted,
        restricted_grid=restricted_grid,
        boundary=boundary,
    )


# Frontend'in kullanacağı yol, yasak alan ve kural verilerini sözlük olarak döndürür.
def get_topology_payload() -> dict[str, Any]:
    return get_topology_dataset().public_payload


def _orientation(
    first: tuple[float, float],
    second: tuple[float, float],
    third: tuple[float, float],
) -> float:
    return (second[0] - first[0]) * (third[1] - first[1]) - (second[1] - first[1]) * (third[0] - first[0])


def _on_segment(
    first: tuple[float, float],
    point: tuple[float, float],
    second: tuple[float, float],
) -> bool:
    epsilon = 1e-9
    return (
        min(first[0], second[0]) - epsilon <= point[0] <= max(first[0], second[0]) + epsilon
        and min(first[1], second[1]) - epsilon <= point[1] <= max(first[1], second[1]) + epsilon
    )


# Komşu olmayan iki parçanın kesişip kesişmediğini kontrol eder.
def _segments_intersect(
    first_start: tuple[float, float],
    first_end: tuple[float, float],
    second_start: tuple[float, float],
    second_end: tuple[float, float],
) -> bool:
    first_orientation = _orientation(first_start, first_end, second_start)
    second_orientation = _orientation(first_start, first_end, second_end)
    third_orientation = _orientation(second_start, second_end, first_start)
    fourth_orientation = _orientation(second_start, second_end, first_end)
    epsilon = 1e-9
    if first_orientation * second_orientation < -epsilon and third_orientation * fourth_orientation < -epsilon:
        return True
    return (
        (abs(first_orientation) <= epsilon and _on_segment(first_start, second_start, first_end))
        or (abs(second_orientation) <= epsilon and _on_segment(first_start, second_end, first_end))
        or (abs(third_orientation) <= epsilon and _on_segment(second_start, first_start, second_end))
        or (abs(fourth_orientation) <= epsilon and _on_segment(second_start, first_end, second_end))
    )


def parse_linestring_wkt(geom_wkt: str) -> tuple[tuple[float, float], ...]:
    match = _LINESTRING_RE.match(geom_wkt)
    if not match or "(" in match.group(1) or ")" in match.group(1):
        raise TopologyValidationError("Boru geometrisi tek parçalı LINESTRING olmalıdır.")
    coordinates: list[tuple[float, float]] = []
    try:
        for part in match.group(1).split(","):
            values = part.split()
            if len(values) != 2:
                raise ValueError
            point = (float(values[0]), float(values[1]))
            if not all(math.isfinite(value) for value in point):
                raise ValueError
            coordinates.append(point)
    except ValueError as exc:
        raise TopologyValidationError("Boru WKT koordinatları geçersiz.") from exc
    if len(coordinates) < 2 or len(set(coordinates)) < 2:
        raise TopologyValidationError("Boru en az iki farklı koordinat içermelidir.")
    if coordinates[0] == coordinates[-1]:
        raise TopologyValidationError("Borunun başlangıç ve bitiş noktası aynı olamaz.")
    if len(set(coordinates)) != len(coordinates):
        raise TopologyValidationError("Boru kendi üzerine dönemez.")
    segments = list(zip(coordinates, coordinates[1:]))
    for first_index, (first_start, first_end) in enumerate(segments):
        for second_index in range(first_index + 2, len(segments)):
            second_start, second_end = segments[second_index]
            if _segments_intersect(first_start, first_end, second_start, second_end):
                raise TopologyValidationError("Boru kendi kendini kesemez.")
    return tuple(coordinates)


def parse_point_wkt(geom_wkt: str) -> tuple[float, float]:
    match = _POINT_RE.match(geom_wkt)
    if not match or "(" in match.group(1) or ")" in match.group(1):
        raise TopologyValidationError("Vana geometrisi POINT olmalıdır.")
    try:
        values = match.group(1).split()
        if len(values) != 2:
            raise ValueError
        point = (float(values[0]), float(values[1]))
        if not all(math.isfinite(value) for value in point):
            raise ValueError
        return point
    except ValueError as exc:
        raise TopologyValidationError("Vana WKT koordinatı geçersiz.") from exc


def _point_segment_distance(point: tuple[float, float], segment: tuple[float, float, float, float]) -> float:
    px, py = point
    x1, y1, x2, y2 = segment
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    fraction = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (x1 + fraction * dx), py - (y1 + fraction * dy))


def _road_distance(point: tuple[float, float], dataset: TopologyDataset) -> float:
    cell = (math.floor(point[0] / 100.0), math.floor(point[1] / 100.0))
    indices = dataset.road_grid.get(cell, ())
    return min((_point_segment_distance(point, dataset.road_segments_metric[index]) for index in indices), default=math.inf)


def _is_restricted(point: tuple[float, float], dataset: TopologyDataset) -> bool:
    cell = (math.floor(point[0] / 100.0), math.floor(point[1] / 100.0))
    return any(_point_in_polygon(point, dataset.restricted[index], metric=True) for index in dataset.restricted_grid.get(cell, ()))


def _metric_samples(points: tuple[tuple[float, float], ...], spacing: float = 2.0) -> Iterable[tuple[tuple[float, float], float]]:
    for start, end in zip(points, points[1:]):
        length = math.dist(start, end)
        if length == 0:
            continue
        count = max(1, math.ceil(length / spacing))
        piece_length = length / count
        for index in range(count):
            fraction = (index + 0.5) / count
            yield (start[0] + (end[0] - start[0]) * fraction, start[1] + (end[1] - start[1]) * fraction), piece_length


def validate_point_topology(point_3857: tuple[float, float]) -> None:
    dataset = get_topology_dataset()
    lonlat = _mercator_to_lonlat(point_3857)
    metric = _lonlat_to_utm36(lonlat)
    if not any(_point_in_polygon(lonlat, polygon) for polygon in dataset.boundary):
        raise TopologyValidationError("Vana Yenimahalle idari sınırı içinde olmalıdır.")
    if _is_restricted(metric, dataset):
        raise TopologyValidationError("Vana park, su, mezarlık veya başka bir yasak alan içinde olamaz.")


def validate_pipe_topology(coordinates_3857: tuple[tuple[float, float], ...]) -> dict[str, float]:
    dataset = get_topology_dataset()
    lonlat = tuple(_mercator_to_lonlat(point) for point in coordinates_3857)
    metric = tuple(_lonlat_to_utm36(point) for point in lonlat)
    total_length = sum(math.dist(start, end) for start, end in zip(metric, metric[1:]))
    if total_length < PIPE_MIN_LENGTH_M:
        raise TopologyValidationError(f"Boru uzunluğu en az {PIPE_MIN_LENGTH_M:.0f} m olmalıdır.")
    if total_length > PIPE_MAX_LENGTH_M:
        raise TopologyValidationError(f"Boru uzunluğu {PIPE_MAX_LENGTH_M:.0f} m sınırını aşamaz.")

    covered_length = 0.0
    for metric_start, metric_end, geo_start, geo_end in zip(metric, metric[1:], lonlat, lonlat[1:]):
        segment_length = math.dist(metric_start, metric_end)
        if segment_length == 0:
            continue
        count = max(1, math.ceil(segment_length / 2.0))
        piece_length = segment_length / count
        for index in range(count):
            fraction = (index + 0.5) / count
            sample = (
                metric_start[0] + (metric_end[0] - metric_start[0]) * fraction,
                metric_start[1] + (metric_end[1] - metric_start[1]) * fraction,
            )
            sample_lonlat = (
                geo_start[0] + (geo_end[0] - geo_start[0]) * fraction,
                geo_start[1] + (geo_end[1] - geo_start[1]) * fraction,
            )
            if not any(_point_in_polygon(sample_lonlat, polygon) for polygon in dataset.boundary):
                raise TopologyValidationError("Boru Yenimahalle idari sınırı dışına çıkamaz.")
            if _is_restricted(sample, dataset):
                raise TopologyValidationError("Boru rotası yasak alanla çakışıyor.")
            if _road_distance(sample, dataset) <= PIPE_ROAD_CORRIDOR_M:
                covered_length += piece_length
    road_ratio = covered_length / total_length if total_length else 0.0
    if road_ratio < PIPE_MIN_ROAD_RATIO:
        raise TopologyValidationError(f"Boru yol koridoru uyumu en az %{PIPE_MIN_ROAD_RATIO * 100:.0f} olmalıdır; ölçülen %{road_ratio * 100:.1f}.")
    return {"length_m": total_length, "road_ratio": road_ratio}
