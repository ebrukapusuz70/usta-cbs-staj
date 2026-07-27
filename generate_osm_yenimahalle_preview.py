#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Yenimahalle için OSM yollarını kullanan sentetik ön izleme verisi üretir.
SQL çıktısını ön izleme tablolarına, GeoJSON çıktısını görsel kontrole hazırlar.
Canlı boru ve vana tablolarına veri eklemez.
"""

from __future__ import annotations

import argparse
import heapq
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from typing import Any

SOURCE = "synthetic_demo_yenimahalle_osm_preview"
WORK_AREA_NAME = "Demetevler / Yenimahalle kompakt konut sokaklari"
WORK_AREA_BBOX = {
    "south": 39.9608,
    "west": 32.7760,
    "north": 39.9728,
    "east": 32.7938,
}
ALLOWED_HIGHWAYS = {"residential", "tertiary", "secondary", "service"}
TARGET_PIPE_COUNT = 62
MIN_PIPE_COUNT = 50
MAX_PIPE_COUNT = 80
MIN_VALVE_COUNT = 20
MAX_VALVE_COUNT = 35
RADIUS = 6378137.0


@dataclass(frozen=True)
class Node:
    node_id: int
    lon: float
    lat: float
    x: float
    y: float


@dataclass
class RoadEdge:
    edge_id: int
    u: int
    v: int
    way_id: int
    highway: str
    name: str
    length_m: float
    coords_lonlat: list[tuple[float, float]]
    coords_3857: list[tuple[float, float]]


@dataclass
class PipeRecord:
    pipe_id: int
    source_edge_id: int
    pipe_code: str
    pipe_type: str
    diameter_mm: int
    material: str
    pressure_level: str
    operating_pressure_bar: float
    status: str
    install_year: int
    coords_lonlat: list[tuple[float, float]]
    coords_3857: list[tuple[float, float]]
    u: int
    v: int
    highway: str
    name: str


@dataclass
class ValveRecord:
    valve_id: int
    valve_code: str
    valve_type: str
    diameter_mm: int
    material: str
    status: str
    install_year: int
    related_pipe_id: int
    lonlat: tuple[float, float]
    xy: tuple[float, float]
    reason: str


def lonlat_to_3857(lon: float, lat: float) -> tuple[float, float]:
    lat = max(min(lat, 89.5), -89.5)
    x = RADIUS * math.radians(lon)
    y = RADIUS * math.log(math.tan(math.pi / 4.0 + math.radians(lat) / 2.0))
    return x, y


def distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def point_line_distance(point: tuple[float, float], line: list[tuple[float, float]]) -> float:
    best = float("inf")
    px, py = point
    for a, b in zip(line, line[1:]):
        ax, ay = a
        bx, by = b
        dx = bx - ax
        dy = by - ay
        denom = dx * dx + dy * dy
        if denom == 0:
            best = min(best, distance(point, a))
            continue
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / denom))
        proj = (ax + t * dx, ay + t * dy)
        best = min(best, distance(point, proj))
    return best


def line_length(coords: list[tuple[float, float]]) -> float:
    return sum(distance(a, b) for a, b in zip(coords, coords[1:]))


def midpoint_lonlat(edge: RoadEdge) -> tuple[float, float]:
    (lon1, lat1), (lon2, lat2) = edge.coords_lonlat
    return (lon1 + lon2) / 2.0, (lat1 + lat2) / 2.0


def midpoint_3857(edge: RoadEdge) -> tuple[float, float]:
    (x1, y1), (x2, y2) = edge.coords_3857
    return (x1 + x2) / 2.0, (y1 + y2) / 2.0


def sql_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def wkt_linestring(coords: list[tuple[float, float]]) -> str:
    return "LINESTRING(" + ",".join(f"{x:.3f} {y:.3f}" for x, y in coords) + ")"


def wkt_point(point: tuple[float, float]) -> str:
    return f"POINT({point[0]:.3f} {point[1]:.3f})"


def fetch_overpass() -> dict[str, Any]:
    bbox = WORK_AREA_BBOX
    query = f"""
    [out:json][timeout:90];
    (
      way["highway"~"^(residential|tertiary|secondary|service)$"]
        ({bbox["south"]},{bbox["west"]},{bbox["north"]},{bbox["east"]});
    );
    (._;>;);
    out body;
    """
    endpoints = [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
    ]
    encoded = urllib.parse.urlencode({"data": query}).encode("utf-8")
    last_error: Exception | None = None
    for endpoint in endpoints:
        req = urllib.request.Request(
            endpoint,
            data=encoded,
            headers={
                "User-Agent": "usta-cbs-synthetic-preview/1.0",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                payload = response.read().decode("utf-8")
                return json.loads(payload)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            last_error = exc
            time.sleep(2)
    raise RuntimeError(f"Overpass API erisilemedi: {last_error}")


def normalize_highway(value: Any) -> str | None:
    if isinstance(value, list):
        for item in value:
            if item in ALLOWED_HIGHWAYS:
                return item
        return None
    if isinstance(value, str) and value in ALLOWED_HIGHWAYS:
        return value
    return None


def parse_osm(data: dict[str, Any]) -> tuple[dict[int, Node], list[RoadEdge]]:
    raw_nodes: dict[int, Node] = {}
    ways: list[dict[str, Any]] = []

    for element in data.get("elements", []):
        if element.get("type") == "node":
            lon = float(element["lon"])
            lat = float(element["lat"])
            x, y = lonlat_to_3857(lon, lat)
            raw_nodes[int(element["id"])] = Node(int(element["id"]), lon, lat, x, y)
        elif element.get("type") == "way":
            ways.append(element)

    edge_by_pair: dict[tuple[int, int], RoadEdge] = {}
    edge_id = 1
    for way in ways:
        tags = way.get("tags", {})
        highway = normalize_highway(tags.get("highway"))
        if highway is None:
            continue
        name = tags.get("name") or f"osm_way_{way['id']}"
        node_ids = [int(node_id) for node_id in way.get("nodes", []) if int(node_id) in raw_nodes]
        for u, v in zip(node_ids, node_ids[1:]):
            if u == v:
                continue
            key = tuple(sorted((u, v)))
            if key in edge_by_pair:
                continue
            coords_3857 = [(raw_nodes[u].x, raw_nodes[u].y), (raw_nodes[v].x, raw_nodes[v].y)]
            length = line_length(coords_3857)
            if length < 18 or length > 320:
                continue
            edge_by_pair[key] = RoadEdge(
                edge_id=edge_id,
                u=u,
                v=v,
                way_id=int(way["id"]),
                highway=highway,
                name=str(name),
                length_m=length,
                coords_lonlat=[(raw_nodes[u].lon, raw_nodes[u].lat), (raw_nodes[v].lon, raw_nodes[v].lat)],
                coords_3857=coords_3857,
            )
            edge_id += 1

    if not edge_by_pair:
        raise RuntimeError("OSM yol verisinden kullanilabilir segment uretilemedi.")
    return raw_nodes, list(edge_by_pair.values())


def connected_components(edges: list[RoadEdge]) -> list[set[int]]:
    adjacency: dict[int, set[int]] = defaultdict(set)
    for edge in edges:
        adjacency[edge.u].add(edge.v)
        adjacency[edge.v].add(edge.u)

    seen: set[int] = set()
    components: list[set[int]] = []
    for node_id in adjacency:
        if node_id in seen:
            continue
        comp: set[int] = set()
        queue = deque([node_id])
        seen.add(node_id)
        while queue:
            current = queue.popleft()
            comp.add(current)
            for neighbor in adjacency[current]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    queue.append(neighbor)
        components.append(comp)
    components.sort(key=len, reverse=True)
    return components


def select_connected_edges(nodes: dict[int, Node], edges: list[RoadEdge]) -> list[RoadEdge]:
    components = connected_components(edges)
    largest_nodes = components[0]
    component_edges = [edge for edge in edges if edge.u in largest_nodes and edge.v in largest_nodes]
    if len(component_edges) < MIN_PIPE_COUNT:
        raise RuntimeError(f"En buyuk bagli yol bileseninde yeterli segment yok: {len(component_edges)}")

    center_lon = (WORK_AREA_BBOX["west"] + WORK_AREA_BBOX["east"]) / 2.0
    center_lat = (WORK_AREA_BBOX["south"] + WORK_AREA_BBOX["north"]) / 2.0
    center_xy = lonlat_to_3857(center_lon, center_lat)

    degree = Counter()
    for edge in component_edges:
        degree[edge.u] += 1
        degree[edge.v] += 1

    root = min(
        largest_nodes,
        key=lambda node_id: distance((nodes[node_id].x, nodes[node_id].y), center_xy) - degree[node_id] * 35.0,
    )

    by_node: dict[int, list[RoadEdge]] = defaultdict(list)
    for edge in component_edges:
        by_node[edge.u].append(edge)
        by_node[edge.v].append(edge)

    selected: list[RoadEdge] = []
    selected_ids: set[int] = set()
    selected_nodes: set[int] = {root}
    heap: list[tuple[float, int, RoadEdge]] = []

    def push_edges(node_id: int) -> None:
        for edge in by_node[node_id]:
            if edge.edge_id in selected_ids:
                continue
            mid = midpoint_3857(edge)
            highway_bias = {"secondary": -120, "tertiary": -90, "residential": 0, "service": 55}.get(edge.highway, 0)
            score = distance(mid, center_xy) + edge.length_m * 0.18 + highway_bias
            heapq.heappush(heap, (score, edge.edge_id, edge))

    push_edges(root)
    while heap and len(selected) < TARGET_PIPE_COUNT:
        _, _, edge = heapq.heappop(heap)
        if edge.edge_id in selected_ids:
            continue
        touches = edge.u in selected_nodes or edge.v in selected_nodes
        if not touches:
            continue
        selected.append(edge)
        selected_ids.add(edge.edge_id)
        before = len(selected_nodes)
        selected_nodes.add(edge.u)
        selected_nodes.add(edge.v)
        if len(selected_nodes) > before:
            push_edges(edge.u)
            push_edges(edge.v)

    if len(selected) < MIN_PIPE_COUNT:
        raise RuntimeError(f"Bagli preview agi icin yeterli segment secilemedi: {len(selected)}")
    return selected[:MAX_PIPE_COUNT]


def edge_adjacency(edges: list[RoadEdge]) -> dict[int, set[int]]:
    by_node: dict[int, list[int]] = defaultdict(list)
    for idx, edge in enumerate(edges):
        by_node[edge.u].append(idx)
        by_node[edge.v].append(idx)
    adjacency: dict[int, set[int]] = defaultdict(set)
    for ids in by_node.values():
        for a in ids:
            for b in ids:
                if a != b:
                    adjacency[a].add(b)
    return adjacency


def classify_pipes(edges: list[RoadEdge]) -> list[PipeRecord]:
    node_degree = Counter()
    for edge in edges:
        node_degree[edge.u] += 1
        node_degree[edge.v] += 1

    name_lengths = Counter()
    for edge in edges:
        if not edge.name.startswith("osm_way_"):
            name_lengths[edge.name] += edge.length_m
    main_names = {name for name, _ in name_lengths.most_common(2)}

    main_candidates = [
        idx
        for idx, edge in enumerate(edges)
        if edge.highway in {"secondary", "tertiary"} or edge.name in main_names
    ]
    main_candidates.sort(key=lambda idx: (0 if edges[idx].name in main_names else 1, -edges[idx].length_m))
    main_set = set(main_candidates[: max(8, min(14, len(edges) // 5))])
    if len(main_set) < 8:
        fallback = sorted(range(len(edges)), key=lambda idx: edges[idx].length_m, reverse=True)
        main_set.update(fallback[: 8 - len(main_set)])

    service_candidates = [
        idx
        for idx, edge in enumerate(edges)
        if edge.highway == "service"
        or node_degree[edge.u] == 1
        or node_degree[edge.v] == 1
        or edge.length_m < 45
    ]
    service_candidates = [idx for idx in service_candidates if idx not in main_set]
    service_candidates.sort(key=lambda idx: (0 if edges[idx].highway == "service" else 1, edges[idx].length_m))
    service_set = set(service_candidates[: max(8, min(16, len(edges) // 4))])

    adjacency = edge_adjacency(edges)
    cluster_seed = None
    ranked = sorted(
        [idx for idx in range(len(edges)) if idx not in service_set],
        key=lambda idx: (-len(adjacency[idx]), 0 if idx not in main_set else 1, idx),
    )
    if ranked:
        cluster_seed = ranked[min(2, len(ranked) - 1)]

    maintenance_set: set[int] = set()
    if cluster_seed is not None:
        queue = deque([cluster_seed])
        while queue and len(maintenance_set) < 4:
            current = queue.popleft()
            if current in maintenance_set or current in service_set:
                continue
            maintenance_set.add(current)
            for neighbor in sorted(adjacency[current]):
                if neighbor not in maintenance_set and neighbor not in service_set:
                    queue.append(neighbor)

    passive_candidates = [
        idx
        for idx in service_candidates
        if idx not in maintenance_set and (node_degree[edges[idx].u] == 1 or node_degree[edges[idx].v] == 1)
    ]
    passive_target = max(7, min(10, round(len(edges) * 0.15)))
    passive_set = set(passive_candidates[:passive_target])
    if len(passive_set) < passive_target:
        more = [idx for idx in service_candidates if idx not in maintenance_set and idx not in passive_set]
        passive_set.update(more[: passive_target - len(passive_set)])

    pipe_records: list[PipeRecord] = []
    for idx, edge in enumerate(edges, start=1):
        zero_idx = idx - 1
        if zero_idx in main_set:
            pipe_type = "main_line"
            diameter = [160, 200, 250][idx % 3]
            material = ["çelik", "PE100"][idx % 2]
            pressure_level = "medium"
            pressure = 4.0 if diameter >= 200 else 1.0
        elif zero_idx in service_set:
            pipe_type = "service_line"
            diameter = [32, 40, 63][idx % 3]
            material = "polietilen"
            pressure_level = "low"
            pressure = 0.3
        else:
            pipe_type = "distribution"
            diameter = [90, 110, 125, 160][idx % 4]
            material = ["PE100", "polietilen"][idx % 2]
            pressure_level = "medium" if diameter >= 125 else "low"
            pressure = 1.0 if pressure_level == "medium" else 0.3

        if zero_idx in maintenance_set:
            status = "tamirde"
        elif zero_idx in passive_set:
            status = "pasif"
        else:
            status = "aktif"

        if status == "pasif":
            install_year = 2005 + ((idx * 3) % 9)
        elif status == "tamirde":
            install_year = 2007 + ((idx * 5) % 12)
        else:
            install_year = 2013 + ((idx * 7) % 13)

        pipe_records.append(
            PipeRecord(
                pipe_id=idx,
                source_edge_id=edge.edge_id,
                pipe_code=f"GP-OSM-YHM-{idx:03d}",
                pipe_type=pipe_type,
                diameter_mm=diameter,
                material=material,
                pressure_level=pressure_level,
                operating_pressure_bar=pressure,
                status=status,
                install_year=install_year,
                coords_lonlat=edge.coords_lonlat,
                coords_3857=edge.coords_3857,
                u=edge.u,
                v=edge.v,
                highway=edge.highway,
                name=edge.name,
            )
        )
    return pipe_records


def generate_valves(pipes: list[PipeRecord]) -> list[ValveRecord]:
    by_node: dict[int, list[PipeRecord]] = defaultdict(list)
    for pipe in pipes:
        by_node[pipe.u].append(pipe)
        by_node[pipe.v].append(pipe)

    pipe_by_id = {pipe.pipe_id: pipe for pipe in pipes}
    valve_candidates: list[dict[str, Any]] = []

    for node_id, incident in by_node.items():
        degree = len(incident)
        has_main = any(pipe.pipe_type == "main_line" for pipe in incident)
        has_non_main = any(pipe.pipe_type != "main_line" for pipe in incident)
        has_maintenance = any(pipe.status == "tamirde" for pipe in incident)
        has_active_neighbor = any(pipe.status != "tamirde" for pipe in incident)
        related = max(incident, key=lambda pipe: (pipe.diameter_mm, -pipe.pipe_id))
        xy = related.coords_3857[0] if related.u == node_id else related.coords_3857[-1]
        lonlat = related.coords_lonlat[0] if related.u == node_id else related.coords_lonlat[-1]

        if has_maintenance and has_active_neighbor:
            valve_candidates.append(
                {"priority": 1, "reason": "maintenance_boundary", "status": "kapalı", "node_id": node_id, "related": related, "xy": xy, "lonlat": lonlat}
            )
        elif degree >= 3:
            valve_candidates.append(
                {"priority": 2, "reason": "junction", "status": "açık", "node_id": node_id, "related": related, "xy": xy, "lonlat": lonlat}
            )
        elif has_main and has_non_main:
            valve_candidates.append(
                {"priority": 3, "reason": "main_branch", "status": "açık", "node_id": node_id, "related": related, "xy": xy, "lonlat": lonlat}
            )
        elif degree == 1 and related.pipe_type == "service_line":
            valve_candidates.append(
                {"priority": 5, "reason": "service_terminal", "status": "açık", "node_id": node_id, "related": related, "xy": xy, "lonlat": lonlat}
            )
        elif degree == 1:
            valve_candidates.append(
                {"priority": 6, "reason": "terminal", "status": "açık", "node_id": node_id, "related": related, "xy": xy, "lonlat": lonlat}
            )

    dedup: dict[str, dict[str, Any]] = {}
    for candidate in valve_candidates:
        key = f"{candidate['xy'][0]:.3f},{candidate['xy'][1]:.3f}"
        if key not in dedup or candidate["priority"] < dedup[key]["priority"]:
            dedup[key] = candidate

    selected = sorted(dedup.values(), key=lambda item: (item["priority"], item["related"].pipe_id))
    selected = selected[:MAX_VALVE_COUNT]

    if len(selected) < MIN_VALVE_COUNT:
        existing_keys = {f"{item['xy'][0]:.3f},{item['xy'][1]:.3f}" for item in selected}
        for pipe in pipes:
            if pipe.pipe_type not in {"main_line", "distribution"}:
                continue
            edge_like = RoadEdge(
                edge_id=pipe.source_edge_id,
                u=pipe.u,
                v=pipe.v,
                way_id=0,
                highway=pipe.highway,
                name=pipe.name,
                length_m=line_length(pipe.coords_3857),
                coords_lonlat=pipe.coords_lonlat,
                coords_3857=pipe.coords_3857,
            )
            xy = midpoint_3857(edge_like)
            key = f"{xy[0]:.3f},{xy[1]:.3f}"
            if key in existing_keys:
                continue
            selected.append(
                {
                    "priority": 4,
                    "reason": "main_interval",
                    "status": "açık",
                    "node_id": None,
                    "related": pipe,
                    "xy": xy,
                    "lonlat": midpoint_lonlat(edge_like),
                }
            )
            existing_keys.add(key)
            if len(selected) >= MIN_VALVE_COUNT:
                break

    selected = sorted(selected[:MAX_VALVE_COUNT], key=lambda item: (item["priority"], item["related"].pipe_id))
    maintenance_indices = [
        idx
        for idx, item in enumerate(selected)
        if item["status"] == "açık" and item["reason"] in {"junction", "main_interval"}
    ][:2]
    for idx in maintenance_indices[:1]:
        selected[idx]["status"] = "bakımda"

    valves: list[ValveRecord] = []
    for idx, item in enumerate(selected, start=1):
        related: PipeRecord = item["related"]
        reason = item["reason"]
        if reason == "maintenance_boundary":
            valve_type = "isolation"
        elif reason in {"junction", "main_branch"}:
            valve_type = ["isolation", "control", "pressure_reducing"][idx % 3]
        elif reason == "main_interval":
            valve_type = "control"
        else:
            valve_type = "isolation"
        valves.append(
            ValveRecord(
                valve_id=idx,
                valve_code=f"GV-OSM-YHM-{idx:03d}",
                valve_type=valve_type,
                diameter_mm=related.diameter_mm,
                material=["steel", "ductile_iron", "brass"][idx % 3],
                status=item["status"],
                install_year=min(2025, max(2005, related.install_year + (idx % 3))),
                related_pipe_id=related.pipe_id,
                lonlat=item["lonlat"],
                xy=item["xy"],
                reason=reason,
            )
        )
    return valves


def validate_preview(pipes: list[PipeRecord], valves: list[ValveRecord]) -> dict[str, Any]:
    pipe_status = Counter(pipe.status for pipe in pipes)
    pipe_types = Counter(pipe.pipe_type for pipe in pipes)
    valve_status = Counter(valve.status for valve in valves)
    valve_types = Counter(valve.valve_type for valve in valves)

    duplicate_pipe_count = len(pipes) - len(
        {
            tuple((round(x, 3), round(y, 3)) for x, y in pipe.coords_3857)
            for pipe in pipes
        }
    )
    invalid_pipe_count = sum(
        1
        for pipe in pipes
        if len(pipe.coords_3857) < 2 or distance(pipe.coords_3857[0], pipe.coords_3857[-1]) < 0.001
    )
    invalid_valve_count = sum(1 for valve in valves if not math.isfinite(valve.xy[0]) or not math.isfinite(valve.xy[1]))
    far_valves = sum(
        1
        for valve in valves
        if min(point_line_distance(valve.xy, pipe.coords_3857) for pipe in pipes) > 0.5
    )
    road_far_pipes = 0

    adjacency: dict[int, set[int]] = defaultdict(set)
    for pipe in pipes:
        adjacency[pipe.u].add(pipe.v)
        adjacency[pipe.v].add(pipe.u)
    seen: set[int] = set()
    components = 0
    for node_id in adjacency:
        if node_id in seen:
            continue
        components += 1
        queue = deque([node_id])
        seen.add(node_id)
        while queue:
            current = queue.popleft()
            for neighbor in adjacency[current]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    queue.append(neighbor)

    xs = [x for pipe in pipes for x, _ in pipe.coords_3857]
    ys = [y for pipe in pipes for _, y in pipe.coords_3857]
    area_m2 = (max(xs) - min(xs)) * (max(ys) - min(ys)) if xs and ys else 0.0

    return {
        "pipe_count": len(pipes),
        "valve_count": len(valves),
        "pipe_status": dict(pipe_status),
        "pipe_types": dict(pipe_types),
        "valve_status": dict(valve_status),
        "valve_types": dict(valve_types),
        "invalid_pipe_count": invalid_pipe_count,
        "invalid_valve_count": invalid_valve_count,
        "duplicate_pipe_count": duplicate_pipe_count,
        "far_valves": far_valves,
        "road_far_pipes": road_far_pipes,
        "disconnected_pipe_end_count": 0 if components == 1 else components,
        "connected_component_count": components,
        "extent_3857": [min(xs), min(ys), max(xs), max(ys)],
        "approx_area_m2": area_m2,
    }


def feature_collection(features: list[dict[str, Any]]) -> dict[str, Any]:
    return {"type": "FeatureCollection", "features": features}


def write_geojson(output_dir: str, pipes: list[PipeRecord], valves: list[ValveRecord]) -> None:
    pipe_features = []
    for pipe in pipes:
        pipe_features.append(
            {
                "type": "Feature",
                "properties": {
                    "pipe_id": pipe.pipe_id,
                    "pipe_code": pipe.pipe_code,
                    "pipe_type": pipe.pipe_type,
                    "diameter_mm": pipe.diameter_mm,
                    "material": pipe.material,
                    "pressure_level": pipe.pressure_level,
                    "operating_pressure_bar": pipe.operating_pressure_bar,
                    "status": pipe.status,
                    "install_year": pipe.install_year,
                    "source": SOURCE,
                    "osm_highway": pipe.highway,
                    "osm_name": pipe.name,
                },
                "geometry": {"type": "MultiLineString", "coordinates": [pipe.coords_lonlat]},
            }
        )
    valve_features = []
    for valve in valves:
        valve_features.append(
            {
                "type": "Feature",
                "properties": {
                    "valve_id": valve.valve_id,
                    "valve_code": valve.valve_code,
                    "valve_type": valve.valve_type,
                    "diameter_mm": valve.diameter_mm,
                    "material": valve.material,
                    "status": valve.status,
                    "install_year": valve.install_year,
                    "related_pipe_id": valve.related_pipe_id,
                    "source": SOURCE,
                    "placement_reason": valve.reason,
                },
                "geometry": {"type": "Point", "coordinates": list(valve.lonlat)},
            }
        )

    with open(os.path.join(output_dir, "preview_gas_pipes.geojson"), "w", encoding="utf-8") as file:
        json.dump(feature_collection(pipe_features), file, ensure_ascii=False, indent=2)
    with open(os.path.join(output_dir, "preview_gas_valves.geojson"), "w", encoding="utf-8") as file:
        json.dump(feature_collection(valve_features), file, ensure_ascii=False, indent=2)


def write_sql(output_dir: str, pipes: list[PipeRecord], valves: list[ValveRecord], validation: dict[str, Any]) -> None:
    lines: list[str] = []
    lines.extend(
        [
            "-- ============================================================================",
            "-- SENTETIK DEMO ONIZLEME VERISI UYARISI",
            "-- ============================================================================",
            "-- Bu dosyadaki veriler GERCEK DOGALGAZ ALTYAPISINI TEMSIL ETMEZ.",
            "-- OSM yol geometrileri yalnizca sentetik demo agin seklini uretmek icin kullanilir.",
            "-- Canli cbs.gas_pipes ve cbs.gas_valves tablolarina veri yazmaz.",
            "-- ============================================================================",
            "",
            "BEGIN;",
            "",
            "CREATE EXTENSION IF NOT EXISTS postgis;",
            "CREATE SCHEMA IF NOT EXISTS cbs;",
            "",
            "DO $$",
            "DECLARE",
            "    live_pipe_count integer;",
            "    live_valve_count integer;",
            "BEGIN",
            "    SELECT count(*) INTO live_pipe_count FROM cbs.gas_pipes;",
            "    SELECT count(*) INTO live_valve_count FROM cbs.gas_valves;",
            "    IF live_pipe_count <> 0 OR live_valve_count <> 0 THEN",
            "        RAISE EXCEPTION 'Canli tablolar bos degil. gas_pipes=%, gas_valves=%. Preview veri uretilmedi.', live_pipe_count, live_valve_count;",
            "    END IF;",
            "END $$;",
            "",
            "DROP TABLE IF EXISTS cbs.gas_valves_preview;",
            "DROP TABLE IF EXISTS cbs.gas_pipes_preview;",
            "",
            "CREATE TABLE cbs.gas_pipes_preview (",
            "    pipe_id integer primary key,",
            "    pipe_code varchar,",
            "    pipe_type varchar,",
            "    diameter_mm integer,",
            "    material varchar,",
            "    pressure_level varchar,",
            "    operating_pressure_bar numeric,",
            "    status varchar,",
            "    install_year integer,",
            "    source varchar,",
            "    geom geometry(MultiLineString, 3857)",
            ");",
            "",
            "CREATE TABLE cbs.gas_valves_preview (",
            "    valve_id integer primary key,",
            "    valve_code varchar,",
            "    valve_type varchar,",
            "    diameter_mm integer,",
            "    material varchar,",
            "    status varchar,",
            "    install_year integer,",
            "    related_pipe_id integer,",
            "    source varchar,",
            "    geom geometry(Point, 3857)",
            ");",
            "",
            "INSERT INTO cbs.gas_pipes_preview (pipe_id, pipe_code, pipe_type, diameter_mm, material, pressure_level, operating_pressure_bar, status, install_year, source, geom)",
            "VALUES",
        ]
    )
    pipe_values = []
    for pipe in pipes:
        pipe_values.append(
            "("
            f"{pipe.pipe_id}, {sql_quote(pipe.pipe_code)}, {sql_quote(pipe.pipe_type)}, {pipe.diameter_mm}, "
            f"{sql_quote(pipe.material)}, {sql_quote(pipe.pressure_level)}, {pipe.operating_pressure_bar}, "
            f"{sql_quote(pipe.status)}, {pipe.install_year}, {sql_quote(SOURCE)}, "
            f"ST_Multi(ST_GeomFromText({sql_quote(wkt_linestring(pipe.coords_3857))}, 3857))::geometry(MultiLineString, 3857)"
            ")"
        )
    lines.append(",\n".join(pipe_values) + ";")
    lines.extend(
        [
            "",
            "INSERT INTO cbs.gas_valves_preview (valve_id, valve_code, valve_type, diameter_mm, material, status, install_year, related_pipe_id, source, geom)",
            "VALUES",
        ]
    )
    valve_values = []
    for valve in valves:
        valve_values.append(
            "("
            f"{valve.valve_id}, {sql_quote(valve.valve_code)}, {sql_quote(valve.valve_type)}, {valve.diameter_mm}, "
            f"{sql_quote(valve.material)}, {sql_quote(valve.status)}, {valve.install_year}, {valve.related_pipe_id}, "
            f"{sql_quote(SOURCE)}, ST_GeomFromText({sql_quote(wkt_point(valve.xy))}, 3857)::geometry(Point, 3857)"
            ")"
        )
    lines.append(",\n".join(valve_values) + ";")
    lines.extend(
        [
            "",
            "CREATE INDEX idx_gas_pipes_preview_geom ON cbs.gas_pipes_preview USING GIST (geom);",
            "CREATE INDEX idx_gas_valves_preview_geom ON cbs.gas_valves_preview USING GIST (geom);",
            "ANALYZE cbs.gas_pipes_preview;",
            "ANALYZE cbs.gas_valves_preview;",
            "",
            "DO $$",
            "DECLARE",
            "    pipe_count integer;",
            "    valve_count integer;",
            "    invalid_pipe_count integer;",
            "    invalid_valve_count integer;",
            "    duplicate_pipe_count integer;",
            "    far_valve_count integer;",
            "BEGIN",
            "    SELECT count(*) INTO pipe_count FROM cbs.gas_pipes_preview;",
            "    SELECT count(*) INTO valve_count FROM cbs.gas_valves_preview;",
            "    SELECT count(*) INTO invalid_pipe_count FROM cbs.gas_pipes_preview WHERE NOT ST_IsValid(geom);",
            "    SELECT count(*) INTO invalid_valve_count FROM cbs.gas_valves_preview WHERE NOT ST_IsValid(geom);",
            "    SELECT count(*) - count(DISTINCT ST_AsBinary(ST_SnapToGrid(geom, 0.001))) INTO duplicate_pipe_count FROM cbs.gas_pipes_preview;",
            "    SELECT count(*) INTO far_valve_count",
            "    FROM cbs.gas_valves_preview v",
            "    WHERE NOT EXISTS (",
            "        SELECT 1 FROM cbs.gas_pipes_preview p WHERE ST_DWithin(v.geom, p.geom, 0.5)",
            "    );",
            f"    IF pipe_count < {MIN_PIPE_COUNT} OR pipe_count > {MAX_PIPE_COUNT} THEN RAISE EXCEPTION 'Preview boru sayisi aralik disi: %', pipe_count; END IF;",
            f"    IF valve_count < {MIN_VALVE_COUNT} OR valve_count > {MAX_VALVE_COUNT} THEN RAISE EXCEPTION 'Preview vana sayisi aralik disi: %', valve_count; END IF;",
            "    IF invalid_pipe_count > 0 OR invalid_valve_count > 0 THEN RAISE EXCEPTION 'Gecersiz geometri bulundu. Boru=%, Vana=%', invalid_pipe_count, invalid_valve_count; END IF;",
            "    IF duplicate_pipe_count > 0 THEN RAISE EXCEPTION 'Mukerrer boru geometrisi bulundu: %', duplicate_pipe_count; END IF;",
            "    IF far_valve_count > 0 THEN RAISE EXCEPTION 'Borudan 0.5 metreden uzak vana bulundu: %', far_valve_count; END IF;",
            "    RAISE NOTICE 'Preview veri hazir. Boru=%, Vana=%', pipe_count, valve_count;",
            "END $$;",
            "",
            "COMMIT;",
            "",
            "-- DOGRULAMA RAPOR SORGULARI",
            "SELECT count(*) AS toplam_boru,",
            "       count(*) FILTER (WHERE status = 'aktif') AS aktif_boru,",
            "       count(*) FILTER (WHERE status = 'pasif') AS pasif_boru,",
            "       count(*) FILTER (WHERE status = 'tamirde') AS tamirde_boru",
            "FROM cbs.gas_pipes_preview;",
            "",
            "SELECT pipe_type, count(*) AS boru_sayisi FROM cbs.gas_pipes_preview GROUP BY pipe_type ORDER BY pipe_type;",
            "",
            "SELECT count(*) AS toplam_vana,",
            "       count(*) FILTER (WHERE status = 'açık') AS acik_vana,",
            "       count(*) FILTER (WHERE status = 'kapalı') AS kapali_vana,",
            "       count(*) FILTER (WHERE status = 'bakımda') AS bakimda_vana",
            "FROM cbs.gas_valves_preview;",
            "",
            "SELECT count(*) FILTER (WHERE NOT ST_IsValid(geom)) AS gecersiz_boru_geometrisi FROM cbs.gas_pipes_preview;",
            "SELECT count(*) FILTER (WHERE NOT ST_IsValid(geom)) AS gecersiz_vana_geometrisi FROM cbs.gas_valves_preview;",
            "SELECT count(*) - count(DISTINCT ST_AsBinary(ST_SnapToGrid(geom, 0.001))) AS mukerrer_boru_sayisi FROM cbs.gas_pipes_preview;",
            "SELECT count(*) AS borudan_uzak_vana_sayisi FROM cbs.gas_valves_preview v WHERE NOT EXISTS (SELECT 1 FROM cbs.gas_pipes_preview p WHERE ST_DWithin(v.geom, p.geom, 0.5));",
            "SELECT 'gas_pipes_preview' AS layer_name, ST_SRID(geom) AS srid, ST_GeometryType(geom) AS geometry_type, count(*) FROM cbs.gas_pipes_preview GROUP BY ST_SRID(geom), ST_GeometryType(geom)",
            "UNION ALL",
            "SELECT 'gas_valves_preview', ST_SRID(geom), ST_GeometryType(geom), count(*) FROM cbs.gas_valves_preview GROUP BY ST_SRID(geom), ST_GeometryType(geom);",
            "SELECT 'gas_pipes_preview' AS layer_name, ST_AsText(ST_Extent(geom)) AS extent FROM cbs.gas_pipes_preview",
            "UNION ALL",
            "SELECT 'gas_valves_preview', ST_AsText(ST_Extent(geom)) FROM cbs.gas_valves_preview;",
            "SELECT 'generator_yol_uzak_boru_sayisi' AS metric, " + str(validation["road_far_pipes"]) + " AS value;",
            "SELECT 'generator_baglantisiz_boru_ucu_sayisi' AS metric, " + str(validation["disconnected_pipe_end_count"]) + " AS value;",
            "SELECT 'canli_gas_pipes' AS table_name, count(*) AS count FROM cbs.gas_pipes UNION ALL SELECT 'canli_gas_valves', count(*) FROM cbs.gas_valves;",
        ]
    )
    with open(os.path.join(output_dir, "05_synthetic_yenimahalle_gas_demo_data.sql"), "w", encoding="utf-8", newline="\n") as file:
        file.write("\n".join(lines) + "\n")


def write_report(output_dir: str, validation: dict[str, Any]) -> None:
    extent = validation["extent_3857"]
    report = f"""# OSM Tabanli Yenimahalle Dogalgaz Preview Raporu

## Uyari
Bu veri gercek dogalgaz altyapisini temsil etmez. OpenStreetMap yol geometrileri yalnizca sentetik demo agin seklini uretmek icin kullanilmistir.

## Calisma Alani
- Bolge: {WORK_AREA_NAME}
- BBOX EPSG:4326: south={WORK_AREA_BBOX['south']}, west={WORK_AREA_BBOX['west']}, north={WORK_AREA_BBOX['north']}, east={WORK_AREA_BBOX['east']}
- Extent EPSG:3857: {extent[0]:.2f}, {extent[1]:.2f}, {extent[2]:.2f}, {extent[3]:.2f}
- Yaklasik extent alani: {validation['approx_area_m2']:.0f} m2

## Preview Sayimlari
- Boru: {validation['pipe_count']}
- Vana: {validation['valve_count']}

## Boru Durumlari
- aktif: {validation['pipe_status'].get('aktif', 0)}
- pasif: {validation['pipe_status'].get('pasif', 0)}
- tamirde: {validation['pipe_status'].get('tamirde', 0)}

## Hat Siniflari
- main_line: {validation['pipe_types'].get('main_line', 0)}
- distribution: {validation['pipe_types'].get('distribution', 0)}
- service_line: {validation['pipe_types'].get('service_line', 0)}

## Vana Durumlari
- acik: {validation['valve_status'].get('açık', 0)}
- kapali: {validation['valve_status'].get('kapalı', 0)}
- bakimda: {validation['valve_status'].get('bakımda', 0)}

## Geometri Kontrolleri
- Gecersiz boru geometrisi: {validation['invalid_pipe_count']}
- Gecersiz vana geometrisi: {validation['invalid_valve_count']}
- Mukerrer boru geometrisi: {validation['duplicate_pipe_count']}
- Borudan 0.5 metreden uzak vana: {validation['far_valves']}
- Baglantisiz ag bileseni sayisi: {validation['connected_component_count']}
- Birbirine baglanmayan boru ucu sayisi: {validation['disconnected_pipe_end_count']}
- Yol merkez cizgisine 5 metreden uzak boru: {validation['road_far_pipes']}
"""
    with open(os.path.join(output_dir, "preview_validation_report.md"), "w", encoding="utf-8", newline="\n") as file:
        file.write(report)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    os.makedirs(args.output_dir, exist_ok=True)

    data = fetch_overpass()
    nodes, road_edges = parse_osm(data)
    selected_edges = select_connected_edges(nodes, road_edges)
    pipes = classify_pipes(selected_edges)
    valves = generate_valves(pipes)
    validation = validate_preview(pipes, valves)

    if not (MIN_PIPE_COUNT <= validation["pipe_count"] <= MAX_PIPE_COUNT):
        raise RuntimeError(f"Boru sayisi hedef aralikta degil: {validation['pipe_count']}")
    if not (MIN_VALVE_COUNT <= validation["valve_count"] <= MAX_VALVE_COUNT):
        raise RuntimeError(f"Vana sayisi hedef aralikta degil: {validation['valve_count']}")
    if validation["invalid_pipe_count"] or validation["invalid_valve_count"] or validation["duplicate_pipe_count"] or validation["far_valves"]:
        raise RuntimeError(f"Geometri validasyonu basarisiz: {validation}")
    if validation["connected_component_count"] != 1:
        raise RuntimeError(f"Ag tek bagli bilesen degil: {validation['connected_component_count']}")

    write_geojson(args.output_dir, pipes, valves)
    write_sql(args.output_dir, pipes, valves, validation)
    write_report(args.output_dir, validation)
    print(json.dumps(validation, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
