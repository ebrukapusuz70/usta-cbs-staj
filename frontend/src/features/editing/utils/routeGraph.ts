/* Yol geometrisinden bağlantı grafiği oluşturur.
 * Boru çizimi için ağ üzerindeki en kısa uygun rotayı bulur.
 * OpenLayers vektör verileriyle çalışır. */
import Feature from "ol/Feature";
import { getPointResolution } from "ol/proj";
import type { Coordinate } from "ol/coordinate";
import type Geometry from "ol/geom/Geometry";
import LineString from "ol/geom/LineString";
import MultiLineString from "ol/geom/MultiLineString";
import Point from "ol/geom/Point";
import type VectorSource from "ol/source/Vector";

interface GraphEdge {
  to: string;
  lengthM: number;
}

interface GraphSegment {
  startKey: string;
  endKey: string;
}

export interface GraphNode {
  key: string;
  coordinate: Coordinate;
  edges: GraphEdge[];
}

export interface RouteGraph {
  nodes: Map<string, GraphNode>;
  nodeGrid: Map<string, string[]>;
  gridSize: number;
  segments: GraphSegment[];
  temporarySequence: number;
}

export interface PipeSnap {
  coordinate: Coordinate;
  distanceM: number;
  pipeId: number;
  pipeCode: string;
  diameterMm: number;
}

export interface RouteResult {
  coordinates: Coordinate[];
  lengthM: number;
  endClickDistanceM: number;
}

export interface NetworkConnection {
  coordinate: Coordinate;
  distanceM: number;
  connectionType: "pipe_endpoint" | "valve" | "junction";
  connectionId: number;
  pipeId: number;
}

export interface PipeJunction {
  coordinate: Coordinate;
  pipeId: number;
}

function metersPerMapUnit(coordinate: Coordinate): number {
  return getPointResolution("EPSG:3857", 1, coordinate, "m");
}

export function distanceMeters(a: Coordinate, b: Coordinate): number {
  const midpoint: Coordinate = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
  return Math.hypot(a[0] - b[0], a[1] - b[1]) * metersPerMapUnit(midpoint);
}

function coordinatesFromGeometry(geometry: Geometry): Coordinate[][] {
  if (geometry instanceof LineString) return [geometry.getCoordinates()];
  if (geometry instanceof MultiLineString) return geometry.getCoordinates();
  return [];
}

export function numericProperty(feature: Feature<Geometry>, name: string): number {
  const propertyValue = Number(feature.get(name));
  if (Number.isFinite(propertyValue)) return propertyValue;
  // GeoServer birincil anahtarı bazı WFS GeoJSON yanıtlarında properties
  // içine koymak yerine "gas_pipes.2612" biçimindeki feature.id alanında taşır.
  if (name.endsWith("_id")) {
    const match = String(feature.getId() || "").match(/\.(\d+)$/);
    if (match) return Number(match[1]);
  }
  return Number.NaN;
}

export function findPipeJunctions(
  source: VectorSource<Feature<Geometry>>,
): PipeJunction[] {
  const segments: Array<{ start: Coordinate; end: Coordinate; pipeId: number }> = [];
  for (const feature of source.getFeatures()) {
    const geometry = feature.getGeometry();
    if (!geometry) continue;
    const pipeId = numericProperty(feature, "pipe_id");
    if (!Number.isInteger(pipeId) || pipeId <= 0) continue;
    for (const line of coordinatesFromGeometry(geometry)) {
      for (let index = 0; index < line.length - 1; index += 1) {
        segments.push({
          start: line[index].slice(0, 2),
          end: line[index + 1].slice(0, 2),
          pipeId,
        });
      }
    }
  }

  const gridSize = 200;
  const buckets = new Map<string, number[]>();
  segments.forEach((segment, index) => {
    const minX = Math.floor(Math.min(segment.start[0], segment.end[0]) / gridSize);
    const maxX = Math.floor(Math.max(segment.start[0], segment.end[0]) / gridSize);
    const minY = Math.floor(Math.min(segment.start[1], segment.end[1]) / gridSize);
    const maxY = Math.floor(Math.max(segment.start[1], segment.end[1]) / gridSize);
    for (let x = minX; x <= maxX; x += 1) {
      for (let y = minY; y <= maxY; y += 1) {
        const key = `${x}:${y}`;
        buckets.set(key, [...(buckets.get(key) || []), index]);
      }
    }
  });

  const pairKeys = new Set<string>();
  const pointKeys = new Set<string>();
  const junctions: PipeJunction[] = [];
  for (const indices of buckets.values()) {
    for (let firstIndex = 0; firstIndex < indices.length; firstIndex += 1) {
      for (let secondIndex = firstIndex + 1; secondIndex < indices.length; secondIndex += 1) {
        const leftIndex = Math.min(indices[firstIndex], indices[secondIndex]);
        const rightIndex = Math.max(indices[firstIndex], indices[secondIndex]);
        const pairKey = `${leftIndex}:${rightIndex}`;
        if (pairKeys.has(pairKey)) continue;
        pairKeys.add(pairKey);
        const left = segments[leftIndex];
        const right = segments[rightIndex];
        if (left.pipeId === right.pipeId) continue;

        const denominator = (
          (left.start[0] - left.end[0]) * (right.start[1] - right.end[1])
          - (left.start[1] - left.end[1]) * (right.start[0] - right.end[0])
        );
        if (Math.abs(denominator) < 1e-9) continue;
        const leftCross = left.start[0] * left.end[1] - left.start[1] * left.end[0];
        const rightCross = right.start[0] * right.end[1] - right.start[1] * right.end[0];
        const coordinate: Coordinate = [
          (leftCross * (right.start[0] - right.end[0]) - (left.start[0] - left.end[0]) * rightCross) / denominator,
          (leftCross * (right.start[1] - right.end[1]) - (left.start[1] - left.end[1]) * rightCross) / denominator,
        ];
        const epsilon = 0.001;
        const onBothSegments = [left, right].every((segment) => (
          coordinate[0] >= Math.min(segment.start[0], segment.end[0]) - epsilon
          && coordinate[0] <= Math.max(segment.start[0], segment.end[0]) + epsilon
          && coordinate[1] >= Math.min(segment.start[1], segment.end[1]) - epsilon
          && coordinate[1] <= Math.max(segment.start[1], segment.end[1]) + epsilon
        ));
        if (!onBothSegments) continue;
        const pointKey = `${coordinate[0].toFixed(3)}:${coordinate[1].toFixed(3)}`;
        if (pointKeys.has(pointKey)) continue;
        pointKeys.add(pointKey);
        junctions.push({ coordinate, pipeId: Math.min(left.pipeId, right.pipeId) });
      }
    }
  }
  return junctions;
}

function pipeSnapById(
  source: VectorSource<Feature<Geometry>>,
  pipeId: number,
  coordinate: Coordinate,
  maxDistanceM: number,
): PipeSnap | null {
  const feature = source.getFeatures().find((candidate) => numericProperty(candidate, "pipe_id") === pipeId);
  const geometry = feature?.getGeometry();
  if (!feature || !geometry) return null;
  const result = distanceToGeometryMeters(geometry, coordinate);
  if (result.distanceM > maxDistanceM) return null;
  return {
    coordinate: result.closest.slice(0, 2),
    distanceM: result.distanceM,
    pipeId,
    pipeCode: String(feature.get("pipe_code") || `ID ${pipeId}`),
    diameterMm: numericProperty(feature, "diameter_mm"),
  };
}

function distanceToGeometryMeters(geometry: Geometry, coordinate: Coordinate): { distanceM: number; closest: Coordinate } {
  const closest = geometry.getClosestPoint(coordinate);
  return { closest, distanceM: distanceMeters(coordinate, closest) };
}

export function nearestPipe(
  source: VectorSource<Feature<Geometry>>,
  coordinate: Coordinate,
  maxDistanceM: number,
  excludedPipeId?: number,
): PipeSnap | null {
  const mapRadius = maxDistanceM / metersPerMapUnit(coordinate);
  const candidates = source.getFeaturesInExtent([
    coordinate[0] - mapRadius,
    coordinate[1] - mapRadius,
    coordinate[0] + mapRadius,
    coordinate[1] + mapRadius,
  ]);
  let best: PipeSnap | null = null;
  for (const feature of candidates) {
    const geometry = feature.getGeometry();
    if (!geometry) continue;
    const pipeId = numericProperty(feature, "pipe_id");
    if (pipeId === excludedPipeId) continue;
    const result = distanceToGeometryMeters(geometry, coordinate);
    if (result.distanceM > maxDistanceM || (best && result.distanceM >= best.distanceM)) continue;
    if (!Number.isInteger(pipeId) || pipeId <= 0) continue;
    best = {
      coordinate: result.closest.slice(0, 2),
      distanceM: result.distanceM,
      pipeId,
      pipeCode: String(feature.get("pipe_code") || `ID ${pipeId}`),
      diameterMm: numericProperty(feature, "diameter_mm"),
    };
  }
  return best;
}

export function nearestValveDistance(
  source: VectorSource<Feature<Geometry>>,
  coordinate: Coordinate,
  maxDistanceM: number,
  excludedValveId?: number,
): number | null {
  const mapRadius = maxDistanceM / metersPerMapUnit(coordinate);
  const candidates = source.getFeaturesInExtent([
    coordinate[0] - mapRadius,
    coordinate[1] - mapRadius,
    coordinate[0] + mapRadius,
    coordinate[1] + mapRadius,
  ]);
  let best = Number.POSITIVE_INFINITY;
  for (const feature of candidates) {
    if (numericProperty(feature, "valve_id") === excludedValveId) continue;
    const geometry = feature.getGeometry();
    if (!(geometry instanceof Point)) continue;
    best = Math.min(best, distanceMeters(coordinate, geometry.getCoordinates()));
  }
  return Number.isFinite(best) ? best : null;
}

// Nokta kaynağındaki en yakın ağ bağlantısını metre toleransıyla bulur.
export function nearestNetworkPoint(
  source: VectorSource<Feature<Geometry>>,
  coordinate: Coordinate,
  maxDistanceM: number,
  excludedPipeId?: number,
): NetworkConnection | null {
  const mapRadius = maxDistanceM / metersPerMapUnit(coordinate);
  const candidates = source.getFeaturesInExtent([
    coordinate[0] - mapRadius,
    coordinate[1] - mapRadius,
    coordinate[0] + mapRadius,
    coordinate[1] + mapRadius,
  ]);
  let best: NetworkConnection | null = null;
  const priority = { valve: 0, junction: 1, pipe_endpoint: 2 };
  for (const feature of candidates) {
    const geometry = feature.getGeometry();
    if (!(geometry instanceof Point)) continue;
    const point = geometry.getCoordinates().slice(0, 2);
    const distanceM = distanceMeters(coordinate, point);
    const connectionType = feature.get("connectionType") as NetworkConnection["connectionType"];
    const connectionId = Number(feature.get("connectionId"));
    const pipeId = Number(feature.get("pipeId"));
    if (pipeId === excludedPipeId) continue;
    if (
      !["pipe_endpoint", "valve", "junction"].includes(connectionType)
      || !Number.isInteger(connectionId)
      || !Number.isInteger(pipeId)
    ) {
      continue;
    }
    if (
      distanceM <= maxDistanceM
      && (
        !best
        || distanceM < best.distanceM - 0.001
        || (
          Math.abs(distanceM - best.distanceM) <= 0.001
          && priority[connectionType] < priority[best.connectionType]
        )
      )
    ) {
      best = { coordinate: point, distanceM, connectionType, connectionId, pipeId };
    }
  }
  return best;
}

function nodeKey(coordinate: Coordinate): string {
  return `${coordinate[0].toFixed(3)}:${coordinate[1].toFixed(3)}`;
}

function gridKey(coordinate: Coordinate, gridSize: number): string {
  return `${Math.floor(coordinate[0] / gridSize)}:${Math.floor(coordinate[1] / gridSize)}`;
}

function edgeIsOccupied(
  start: Coordinate,
  end: Coordinate,
  pipeSource: VectorSource<Feature<Geometry>>,
  excludedPipeId?: number,
): boolean {
  const midpoint: Coordinate = [(start[0] + end[0]) / 2, (start[1] + end[1]) / 2];
  // Yeniden çizilen borunun eski geometrisi yol kenarını kendisine kapatmasın;
  // diğer borularla doğrusal çakışan kenarlar kullanılmaya devam etmez.
  return nearestPipe(pipeSource, midpoint, 0.25, excludedPipeId) !== null;
}

export function buildRouteGraph(
  roadFeatures: Feature<Geometry>[],
  pipeSource: VectorSource<Feature<Geometry>>,
  excludedPipeId?: number,
): RouteGraph {
  // İzinli OSM yol parçaları uzunluk ağırlıklı, çift yönlü Dijkstra grafiğine çevrilir.
  const nodes = new Map<string, GraphNode>();
  const segments: GraphSegment[] = [];
  for (const feature of roadFeatures) {
    const geometry = feature.getGeometry();
    if (!geometry) continue;
    for (const line of coordinatesFromGeometry(geometry)) {
      for (let index = 0; index < line.length - 1; index += 1) {
        const start = line[index].slice(0, 2);
        const end = line[index + 1].slice(0, 2);
        const lengthM = distanceMeters(start, end);
        if (lengthM <= 0.01 || edgeIsOccupied(start, end, pipeSource, excludedPipeId)) continue;
        const startKey = nodeKey(start);
        const endKey = nodeKey(end);
        const startNode = nodes.get(startKey) || { key: startKey, coordinate: start, edges: [] };
        const endNode = nodes.get(endKey) || { key: endKey, coordinate: end, edges: [] };
        startNode.edges.push({ to: endKey, lengthM });
        endNode.edges.push({ to: startKey, lengthM });
        nodes.set(startKey, startNode);
        nodes.set(endKey, endNode);
        segments.push({ startKey, endKey });
      }
    }
  }
  const gridSize = 50;
  const nodeGrid = new Map<string, string[]>();
  nodes.forEach((node) => {
    const key = gridKey(node.coordinate, gridSize);
    nodeGrid.set(key, [...(nodeGrid.get(key) || []), node.key]);
  });
  return { nodes, nodeGrid, gridSize, segments, temporarySequence: 0 };
}

function closestPointOnSegment(point: Coordinate, start: Coordinate, end: Coordinate): Coordinate {
  const dx = end[0] - start[0];
  const dy = end[1] - start[1];
  if (dx === 0 && dy === 0) return start.slice(0, 2);
  const fraction = Math.max(0, Math.min(
    1,
    ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / (dx * dx + dy * dy),
  ));
  return [start[0] + fraction * dx, start[1] + fraction * dy];
}

function addEdge(node: GraphNode, to: GraphNode): void {
  node.edges.push({ to: to.key, lengthM: distanceMeters(node.coordinate, to.coordinate) });
}

function insertTemporaryNode(
  graph: RouteGraph,
  coordinate: Coordinate,
  maxDistanceM: number,
  prefix: string,
): { node: GraphNode; distanceM: number } | null {
  // Tıklama yol segmentinin ortasındaysa kenar ikiye bölünerek geçici düğüm oluşturulur.
  let best: { index: number; closest: Coordinate; distanceM: number } | null = null;
  for (let index = 0; index < graph.segments.length; index += 1) {
    const segment = graph.segments[index];
    const start = graph.nodes.get(segment.startKey);
    const end = graph.nodes.get(segment.endKey);
    if (!start || !end) continue;
    const closest = closestPointOnSegment(coordinate, start.coordinate, end.coordinate);
    const distanceM = distanceMeters(coordinate, closest);
    if (distanceM <= maxDistanceM && (!best || distanceM < best.distanceM)) {
      best = { index, closest, distanceM };
    }
  }
  if (!best) return null;

  const segment = graph.segments[best.index];
  const start = graph.nodes.get(segment.startKey)!;
  const end = graph.nodes.get(segment.endKey)!;
  if (distanceMeters(best.closest, start.coordinate) <= 0.01) {
    return { node: start, distanceM: best.distanceM };
  }
  if (distanceMeters(best.closest, end.coordinate) <= 0.01) {
    return { node: end, distanceM: best.distanceM };
  }

  const key = `temporary:${prefix}:${graph.temporarySequence += 1}`;
  const node: GraphNode = { key, coordinate: best.closest, edges: [] };
  start.edges = start.edges.filter((edge) => edge.to !== end.key);
  end.edges = end.edges.filter((edge) => edge.to !== start.key);
  addEdge(start, node);
  addEdge(node, start);
  addEdge(node, end);
  addEdge(end, node);
  graph.nodes.set(key, node);
  graph.segments.splice(
    best.index,
    1,
    { startKey: start.key, endKey: key },
    { startKey: key, endKey: end.key },
  );
  const cell = gridKey(node.coordinate, graph.gridSize);
  graph.nodeGrid.set(cell, [...(graph.nodeGrid.get(cell) || []), key]);
  return { node, distanceM: best.distanceM };
}

function cloneGraph(graph: RouteGraph): RouteGraph {
  return {
    nodes: new Map(Array.from(graph.nodes, ([key, node]) => [
      key,
      { key, coordinate: node.coordinate.slice(0, 2), edges: node.edges.map((edge) => ({ ...edge })) },
    ])),
    nodeGrid: new Map(Array.from(graph.nodeGrid, ([key, values]) => [key, [...values]])),
    gridSize: graph.gridSize,
    segments: graph.segments.map((segment) => ({ ...segment })),
    temporarySequence: graph.temporarySequence,
  };
}

function nearbyNodes(graph: RouteGraph, coordinate: Coordinate, maxDistanceM: number): GraphNode[] {
  const mapRadius = maxDistanceM / metersPerMapUnit(coordinate);
  const minX = Math.floor((coordinate[0] - mapRadius) / graph.gridSize);
  const maxX = Math.floor((coordinate[0] + mapRadius) / graph.gridSize);
  const minY = Math.floor((coordinate[1] - mapRadius) / graph.gridSize);
  const maxY = Math.floor((coordinate[1] + mapRadius) / graph.gridSize);
  const found: GraphNode[] = [];
  for (let x = minX; x <= maxX; x += 1) {
    for (let y = minY; y <= maxY; y += 1) {
      for (const key of graph.nodeGrid.get(`${x}:${y}`) || []) {
        const node = graph.nodes.get(key);
        if (node && distanceMeters(node.coordinate, coordinate) <= maxDistanceM) found.push(node);
      }
    }
  }
  return found;
}

export function findNetworkStart(
  graph: RouteGraph,
  connection: NetworkConnection,
  pipeSource: VectorSource<Feature<Geometry>>,
  maxRoadDistanceM: number,
): { node: GraphNode; pipe: PipeSnap; clickDistanceM: number } | null {
  // Tıklama bu fonksiyona gelmeden önce boru ucu/vanadan oluşan bağlantı
  // kaynağına snap edilmiştir. Şebeke temasını bu gerçek bağlantı noktasında
  // doğrula; yol düğümü yalnızca yeni rotanın başlayacağı koridoru seçer.
  // Bağlantı bir vana olduğunda backend başlangıcın vanaya temasını da kabul
  // eder. Formda gösterilecek ilişkili boruyu, vana ekleme kuralıyla aynı olan
  // genel snap toleransı içinde bulmak yeterlidir.
  const pipe = pipeSnapById(
    pipeSource,
    connection.pipeId,
    connection.coordinate,
    maxRoadDistanceM,
  );
  if (!pipe) return null;
  const roadStart = insertTemporaryNode(
    graph,
    connection.coordinate,
    maxRoadDistanceM,
    "start",
  );
  return roadStart ? { node: roadStart.node, pipe, clickDistanceM: roadStart.distanceM } : null;
}

class MinHeap {
  private values: Array<{ key: string; distance: number }> = [];

  push(value: { key: string; distance: number }) {
    this.values.push(value);
    let index = this.values.length - 1;
    while (index > 0) {
      const parent = Math.floor((index - 1) / 2);
      if (this.values[parent].distance <= value.distance) break;
      this.values[index] = this.values[parent];
      index = parent;
    }
    this.values[index] = value;
  }

  pop(): { key: string; distance: number } | undefined {
    const first = this.values[0];
    const last = this.values.pop();
    if (!first || !last || this.values.length === 0) return first;
    let index = 0;
    this.values[0] = last;
    while (true) {
      const left = index * 2 + 1;
      const right = left + 1;
      if (left >= this.values.length) break;
      const child = right < this.values.length && this.values[right].distance < this.values[left].distance ? right : left;
      if (this.values[index].distance <= this.values[child].distance) break;
      [this.values[index], this.values[child]] = [this.values[child], this.values[index]];
      index = child;
    }
    return first;
  }

  get size(): number { return this.values.length; }
}

export function shortestRoute(
  graph: RouteGraph,
  start: GraphNode,
  endClick: Coordinate,
  maxEndSnapM: number,
  maxRouteLengthM: number,
): RouteResult | null {
  // Bitiş için kopya grafik kullanılır; geçici düğümler sonraki çizimlere taşınmaz.
  const workingGraph = cloneGraph(graph);
  const targetMatch = insertTemporaryNode(workingGraph, endClick, maxEndSnapM, "end");
  const target = targetMatch?.node;
  if (!target || target.key === start.key) return null;

  const distances = new Map<string, number>([[start.key, 0]]);
  const previous = new Map<string, string>();
  const heap = new MinHeap();
  heap.push({ key: start.key, distance: 0 });
  while (heap.size) {
    const current = heap.pop();
    if (!current || current.distance !== distances.get(current.key) || current.distance > maxRouteLengthM) continue;
    const node = workingGraph.nodes.get(current.key);
    if (!node) continue;
    for (const edge of node.edges) {
      const distance = current.distance + edge.lengthM;
      if (distance > maxRouteLengthM || distance >= (distances.get(edge.to) ?? Number.POSITIVE_INFINITY)) continue;
      distances.set(edge.to, distance);
      previous.set(edge.to, current.key);
      heap.push({ key: edge.to, distance });
    }
  }

  if ((distances.get(target.key) ?? 0) < 5) return null;
  const keys = [target.key];
  while (keys[0] !== start.key) {
    const parent = previous.get(keys[0]);
    if (!parent) return null;
    keys.unshift(parent);
  }
  return {
    coordinates: keys.map((key) => workingGraph.nodes.get(key)!.coordinate.slice(0, 2)),
    lengthM: distances.get(target.key)!,
    endClickDistanceM: targetMatch.distanceM,
  };
}
