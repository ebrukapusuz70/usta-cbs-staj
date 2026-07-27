/* Haritadaki vana noktası ve boru rotası çizimini yönetir.
 * Kullanıcı tıklamalarını topolojiye uygun taslağa dönüştürür.
 * Topoloji ve rota yardımcılarını kullanır. */
import { useCallback, useEffect, useRef, useState } from "react";
import Feature, { type FeatureLike } from "ol/Feature";
import GeoJSON from "ol/format/GeoJSON";
import WKT from "ol/format/WKT";
import type Geometry from "ol/geom/Geometry";
import LineString from "ol/geom/LineString";
import MultiLineString from "ol/geom/MultiLineString";
import Point from "ol/geom/Point";
import Snap from "ol/interaction/Snap";
import VectorLayer from "ol/layer/Vector";
import type Map from "ol/Map";
import { getPointResolution } from "ol/proj";
import VectorSource from "ol/source/Vector";
import { unByKey } from "ol/Observable";
import { Circle as CircleStyle, Fill, Stroke, Style } from "ol/style";
import { loadNetworkFeatures, loadStage4Topology } from "../services/topologyService";
import type { DraftFeature, EditMode, OperationNotice, Stage4TopologyPayload } from "../types/editing";
import { geometryToWkt } from "../utils/geometryPayload";
import {
  buildRouteGraph,
  distanceMeters,
  findPipeJunctions,
  findNetworkStart,
  nearestNetworkPoint,
  nearestPipe,
  nearestValveDistance,
  numericProperty,
  shortestRoute,
  type GraphNode,
  type NetworkConnection,
  type PipeSnap,
  type RouteGraph,
} from "../utils/routeGraph";

type TopologyStatus = "loading" | "ready" | "error";

function draftStyle(feature: FeatureLike): Style {
  const state = String(feature.get("state") || "valid");
  const color = state === "invalid" ? "#dc2626" : state === "start" ? "#f59e0b" : state === "saved" ? "#2563eb" : "#16a34a";
  return new Style({
    stroke: new Stroke({ color, width: state === "valid" ? 5 : 3, lineDash: state === "invalid" ? [7, 6] : undefined }),
    image: new CircleStyle({ radius: state === "start" ? 7 : 8, fill: new Fill({ color }), stroke: new Stroke({ color: "#ffffff", width: 2 }) }),
  });
}

const allowedAreaStyle = new Style({
  fill: new Fill({ color: "rgba(22, 163, 74, 0.07)" }),
  stroke: new Stroke({ color: "rgba(22, 163, 74, 0.85)", width: 2 }),
});

const restrictedAreaStyle = new Style({
  fill: new Fill({ color: "rgba(220, 38, 38, 0.20)" }),
  stroke: new Stroke({ color: "rgba(220, 38, 38, 0.90)", width: 2 }),
});

function readFeatures(payload: object, dataProjection: string): Feature<Geometry>[] {
  return new GeoJSON().readFeatures(payload, { dataProjection, featureProjection: "EPSG:3857" }) as Feature<Geometry>[];
}

export function useMapDrawing(map: Map | null) {
  // Hook (özel React fonksiyonu), çizim durumu ve geçici vektör katmanını tek yerde tutar.
  const [mode, setMode] = useState<EditMode>("none");
  const [draft, setDraft] = useState<DraftFeature | null>(null);
  const [feedback, setFeedback] = useState<OperationNotice | null>({ kind: "info", message: "Yerel vektör topolojisi hazırlanıyor…" });
  const [topologyStatus, setTopologyStatus] = useState<TopologyStatus>("loading");
  const sourceRef = useRef(new VectorSource<Feature<Geometry>>());
  const pipeSourceRef = useRef(new VectorSource<Feature<Geometry>>());
  const valveSourceRef = useRef(new VectorSource<Feature<Geometry>>());
  const connectionSourceRef = useRef(new VectorSource<Feature<Geometry>>());
  const restrictedSourceRef = useRef(new VectorSource<Feature<Geometry>>());
  const boundarySourceRef = useRef(new VectorSource<Feature<Geometry>>());
  const roadsRef = useRef<Feature<Geometry>[]>([]);
  const topologyRef = useRef<Stage4TopologyPayload | null>(null);
  const graphRef = useRef<RouteGraph | null>(null);
  const modeRef = useRef<EditMode>("none");
  const startRef = useRef<{ node: GraphNode; pipe: PipeSnap; connection: NetworkConnection } | null>(null);
  const editExclusionRef = useRef<{ pipeId?: number; valveId?: number }>({});
  const disconnectedValveCoordinatesRef = useRef<number[][]>([]);
  const loadAbortRef = useRef<AbortController | null>(null);
  const refreshAbortRef = useRef<AbortController | null>(null);
  const snapInteractionRef = useRef<Snap | null>(null);
  const layerRef = useRef(new VectorLayer({ source: sourceRef.current, zIndex: 50, style: draftStyle }));
  const boundaryLayerRef = useRef(new VectorLayer({
    source: boundarySourceRef.current,
    zIndex: 5,
    style: allowedAreaStyle,
    visible: false,
  }));
  const restrictedLayerRef = useRef(new VectorLayer({
    source: restrictedSourceRef.current,
    zIndex: 6,
    style: restrictedAreaStyle,
    visible: false,
  }));

  const setEditMode = useCallback((nextMode: EditMode) => {
    modeRef.current = nextMode;
    setMode(nextMode);
    boundaryLayerRef.current.setVisible(nextMode !== "none");
    restrictedLayerRef.current.setVisible(nextMode !== "none");
    snapInteractionRef.current?.setActive(nextMode !== "none");
  }, []);

  const clearDraft = useCallback(() => {
    sourceRef.current.clear();
    startRef.current = null;
    editExclusionRef.current = {};
    setDraft(null);
    setEditMode("none");
    setFeedback(null);
  }, [setEditMode]);

  const markDraftSaved = useCallback(() => {
    // POST tamamlanınca taslak sunucu doğrulaması beklenmeden kaydedildi stiliyle görünür kalır.
    sourceRef.current.getFeatures().forEach((feature) => feature.set("state", "saved"));
    startRef.current = null;
    editExclusionRef.current = {};
    setDraft(null);
    setEditMode("none");
  }, [setEditMode]);

  const showSavedGeometry = useCallback((geomWkt: string) => {
    // POST/PATCH response'undaki kanonik WKT, servis karosu yenilenene kadar
    // kaydedildi stiliyle aynı geçici vektör katmanında tutulur.
    const geometry = new WKT().readGeometry(geomWkt, {
      dataProjection: "EPSG:3857",
      featureProjection: "EPSG:3857",
    });
    sourceRef.current.clear();
    sourceRef.current.addFeature(new Feature({ geometry, state: "saved" }));
    startRef.current = null;
    editExclusionRef.current = {};
    setDraft(null);
    setEditMode("none");
  }, [setEditMode]);

  const removeSavedGeometry = useCallback(() => {
    sourceRef.current.clear();
  }, []);

  // Boru uçları ve vanaları Snap etkileşiminin kullanacağı nokta kaynağına ekler.
  const rebuildConnectionSource = useCallback(() => {
    const connectionSource = connectionSourceRef.current;
    connectionSource.clear();
    disconnectedValveCoordinatesRef.current = [];
    const pipeById = new globalThis.Map<number, Feature<Geometry>>();
    for (const feature of pipeSourceRef.current.getFeatures()) {
      const pipeId = numericProperty(feature, "pipe_id");
      if (!Number.isInteger(pipeId) || pipeId <= 0) continue;
      pipeById.set(pipeId, feature);
      const geometry = feature.getGeometry();
      const lines = geometry instanceof LineString
        ? [geometry.getCoordinates()]
        : geometry instanceof MultiLineString
          ? geometry.getCoordinates()
          : [];
      for (const line of lines) {
        if (line.length < 2) continue;
        connectionSource.addFeature(new Feature({
          geometry: new Point(line[0].slice(0, 2)),
          connectionType: "pipe_endpoint",
          connectionId: pipeId,
          pipeId,
        }));
        connectionSource.addFeature(new Feature({
          geometry: new Point(line[line.length - 1].slice(0, 2)),
          connectionType: "pipe_endpoint",
          connectionId: pipeId,
          pipeId,
        }));
      }
    }
    for (const junction of findPipeJunctions(pipeSourceRef.current)) {
      connectionSource.addFeature(new Feature({
        geometry: new Point(junction.coordinate),
        connectionType: "junction",
        connectionId: junction.pipeId,
        pipeId: junction.pipeId,
      }));
    }
    const touchToleranceM = topologyRef.current?.rules.pipe_network_touch_m ?? 0.10;
    for (const feature of valveSourceRef.current.getFeatures()) {
      const geometry = feature.getGeometry();
      if (geometry instanceof Point) {
        const coordinate = geometry.getCoordinates().slice(0, 2);
        const valveId = numericProperty(feature, "valve_id");
        const relatedPipeId = Number(feature.get("related_pipe_id"));
        const relatedPipeGeometry = pipeById.get(relatedPipeId)?.getGeometry();
        const closest = relatedPipeGeometry?.getClosestPoint(coordinate);
        const linked = (
          Number.isInteger(valveId)
          && valveId > 0
          && Number.isInteger(relatedPipeId)
          && relatedPipeId > 0
          && closest
          && distanceMeters(coordinate, closest) <= touchToleranceM
        );
        if (!linked) {
          disconnectedValveCoordinatesRef.current.push(coordinate);
          continue;
        }
        connectionSource.addFeature(new Feature({
          geometry: new Point(coordinate),
          connectionType: "valve",
          connectionId: valveId,
          pipeId: relatedPipeId,
        }));
      }
    }
  }, []);

  // Metre cinsindeki toleransı mevcut zoom seviyesinde piksele çevirir.
  const configureSnapInteraction = useCallback((targetMap: Map, toleranceM: number) => {
    if (snapInteractionRef.current) targetMap.removeInteraction(snapInteractionRef.current);
    const view = targetMap.getView();
    const resolution = view.getResolution() || 1;
    const center = view.getCenter() || [0, 0];
    const metersPerPixel = getPointResolution(view.getProjection(), resolution, center, "m");
    const pixelTolerance = Math.max(1, Math.min(50, Math.ceil(toleranceM / metersPerPixel)));
    const interaction = new Snap({
      source: connectionSourceRef.current,
      edge: false,
      vertex: true,
      intersection: false,
      pixelTolerance,
    });
    snapInteractionRef.current = interaction;
    interaction.setActive(modeRef.current !== "none");
    targetMap.addInteraction(interaction);
  }, []);

  const rebuildGraph = useCallback((excludedPipeId?: number) => {
    if (!roadsRef.current.length || !pipeSourceRef.current.getFeatures().length) {
      graphRef.current = null;
      throw new Error("Yol grafiği veya gaz borusu vektörleri boş; düzenleme durduruldu.");
    }
    graphRef.current = buildRouteGraph(roadsRef.current, pipeSourceRef.current, excludedPipeId);
    if (!graphRef.current.nodes.size) throw new Error("Mevcut ağa bağlanabilen boş yol koridoru bulunamadı.");
  }, []);

  const refreshNetwork = useCallback(async () => {
    refreshAbortRef.current?.abort();
    const controller = new AbortController();
    refreshAbortRef.current = controller;
    try {
      const network = await loadNetworkFeatures(controller.signal);
      pipeSourceRef.current.clear();
      valveSourceRef.current.clear();
      pipeSourceRef.current.addFeatures(readFeatures(network.pipes, "EPSG:3857"));
      valveSourceRef.current.addFeatures(readFeatures(network.valves, "EPSG:3857"));
      rebuildConnectionSource();
      rebuildGraph();
    } finally {
      if (refreshAbortRef.current === controller) refreshAbortRef.current = null;
    }
  }, [rebuildConnectionSource, rebuildGraph]);

  useEffect(() => {
    if (!map) return undefined;
    map.addLayer(boundaryLayerRef.current);
    map.addLayer(restrictedLayerRef.current);
    map.addLayer(layerRef.current);
    const moveKey = map.on("moveend", () => {
      const topology = topologyRef.current;
      if (topology) configureSnapInteraction(map, topology.rules.snap_tolerance_m);
    });
    const controller = new AbortController();
    loadAbortRef.current = controller;
    setTopologyStatus("loading");
    setFeedback({ kind: "info", message: "Yerel OSM yolları, yasak alanlar ve WFS gaz ağı yükleniyor…" });
    Promise.all([loadStage4Topology(controller.signal), loadNetworkFeatures(controller.signal)])
      .then(([topology, network]) => {
        topologyRef.current = topology;
        roadsRef.current = readFeatures(topology.roads, topology.data_crs);
        restrictedSourceRef.current.clear();
        boundarySourceRef.current.clear();
        pipeSourceRef.current.clear();
        valveSourceRef.current.clear();
        restrictedSourceRef.current.addFeatures(readFeatures(topology.restricted_areas, topology.data_crs));
        boundarySourceRef.current.addFeatures(readFeatures(topology.boundary, topology.data_crs));
        pipeSourceRef.current.addFeatures(readFeatures(network.pipes, "EPSG:3857"));
        valveSourceRef.current.addFeatures(readFeatures(network.valves, "EPSG:3857"));
        rebuildConnectionSource();
        rebuildGraph();
        configureSnapInteraction(map, topology.rules.snap_tolerance_m);
        setTopologyStatus("ready");
        setFeedback({ kind: "success", message: "Çalışma alanı ve ağ bağlantı kuralları hazır." });
      })
      .catch((error) => {
        if (controller.signal.aborted) return;
        console.error("Stage4 topology loading error", error);
        setTopologyStatus("error");
        setFeedback({ kind: "error", message: error instanceof Error ? error.message : "Stage 4 topolojisi yüklenemedi; düzenleme durduruldu." });
      });
    return () => {
      // Bileşen kapanırken dinleyici, Snap interaction ve geçici OpenLayers kaynakları temizlenir.
      controller.abort();
      refreshAbortRef.current?.abort();
      refreshAbortRef.current = null;
      loadAbortRef.current = null;
      unByKey(moveKey);
      if (snapInteractionRef.current) {
        map.removeInteraction(snapInteractionRef.current);
        snapInteractionRef.current = null;
      }
      map.removeLayer(boundaryLayerRef.current);
      map.removeLayer(restrictedLayerRef.current);
      map.removeLayer(layerRef.current);
      sourceRef.current.clear();
      restrictedSourceRef.current.clear();
      boundarySourceRef.current.clear();
      pipeSourceRef.current.clear();
      valveSourceRef.current.clear();
      connectionSourceRef.current.clear();
      disconnectedValveCoordinatesRef.current = [];
      roadsRef.current = [];
      graphRef.current = null;
      topologyRef.current = null;
    };
  }, [configureSnapInteraction, map, rebuildConnectionSource, rebuildGraph]);

  const start = useCallback((
    nextMode: Exclude<EditMode, "none">,
    exclusion: { pipeId?: number; valveId?: number } = {},
  ) => {
    if (!map || topologyStatus !== "ready" || !topologyRef.current || !graphRef.current) {
      setFeedback({ kind: "error", message: "Vektör katmanı henüz hazır değil. Lütfen haritanın yüklenmesini bekleyin." });
      return;
    }
    const rules = topologyRef.current.rules;
    // Geometri düzenlenirken nesnenin eski hali duplicate ve vana aralığı
    // kontrollerinden çıkarılır; diğer bütün ağ elemanları korunur.
    editExclusionRef.current = exclusion;
    if (nextMode === "pipe") {
      try {
        rebuildGraph(exclusion.pipeId);
      } catch (error) {
        setFeedback({ kind: "error", message: error instanceof Error ? error.message : "Yol grafiği hazırlanamadı." });
        return;
      }
    }
    configureSnapInteraction(map, rules.snap_tolerance_m);
    sourceRef.current.clear();
    startRef.current = null;
    setDraft(null);
    setEditMode(nextMode);
    setFeedback({
      kind: "info",
      message: nextMode === "valve"
        ? `Mevcut boruya en fazla ${rules.valve_max_snap_m.toFixed(0)} m uzaktaki vana konumunu seçin.`
        : `Bağlı vana, boru ucu veya kavşağa en fazla ${rules.snap_tolerance_m.toFixed(0)} m uzakta bir başlangıç seçin.`,
    });
  }, [configureSnapInteraction, map, rebuildGraph, setEditMode, topologyStatus]);

  useEffect(() => {
    if (!map) return undefined;
    const clickKey = map.on("singleclick", (event) => {
      const activeMode = modeRef.current;
      const topology = topologyRef.current;
      if (activeMode === "none" || !topology || !graphRef.current) return;
      const rules = topology.rules;
      const click = event.coordinate.slice(0, 2);

      const addInvalidPoint = (message: string) => {
        sourceRef.current.getFeatures().filter((feature) => feature.get("state") === "invalid").forEach((feature) => sourceRef.current.removeFeature(feature));
        sourceRef.current.addFeature(new Feature({ geometry: new Point(click), state: "invalid" }));
        setFeedback({ kind: "error", message });
      };
      const pointIsAllowed = (coordinate: number[]) => {
        const insideBoundary = boundarySourceRef.current.getFeatures().some((feature) => feature.getGeometry()?.intersectsCoordinate(coordinate));
        const inRestricted = restrictedSourceRef.current.getFeaturesInExtent([coordinate[0], coordinate[1], coordinate[0], coordinate[1]])
          .some((feature) => feature.getGeometry()?.intersectsCoordinate(coordinate));
        return insideBoundary && !inRestricted;
      };
      const routeIsAllowed = (coordinates: number[][]) => coordinates.slice(0, -1).every((start, index) => {
        const end = coordinates[index + 1];
        const sampleCount = Math.max(1, Math.ceil(distanceMeters(start, end) / 2));
        return Array.from({ length: sampleCount + 1 }, (_, sampleIndex) => {
          const fraction = sampleIndex / sampleCount;
          return [
            start[0] + (end[0] - start[0]) * fraction,
            start[1] + (end[1] - start[1]) * fraction,
          ];
        }).every(pointIsAllowed);
      });

      if (!pointIsAllowed(click)) {
        addInvalidPoint("Seçilen konum çalışma alanı dışında veya yasak alanda.");
        return;
      }

      if (activeMode === "valve") {
        const snap = nearestPipe(pipeSourceRef.current, click, rules.valve_max_snap_m);
        if (!snap) {
          addInvalidPoint("Vana yalnızca mevcut boru üzerine eklenebilir.");
          return;
        }
        if (!pointIsAllowed(snap.coordinate)) {
          addInvalidPoint("Seçilen konum çalışma alanı dışında veya yasak alanda.");
          return;
        }
        const valveDistance = nearestValveDistance(
          valveSourceRef.current,
          snap.coordinate,
          rules.valve_min_spacing_m,
          editExclusionRef.current.valveId,
        );
        if (valveDistance !== null && valveDistance < rules.valve_min_spacing_m) {
          addInvalidPoint(`Mevcut vanaya mesafe ${valveDistance.toFixed(1)} m; en az ${rules.valve_min_spacing_m.toFixed(0)} m olmalı.`);
          return;
        }
        const feature = new Feature({ geometry: new Point(snap.coordinate), state: "valid" });
        sourceRef.current.clear();
        sourceRef.current.addFeature(feature);
        setDraft({
          layerKey: "gasValves",
          geomWkt: geometryToWkt(feature.getGeometry()!),
          relatedPipeId: snap.pipeId,
          relatedPipeCode: snap.pipeCode,
          diameterMm: snap.diameterMm,
          snapDistanceM: snap.distanceM,
        });
        setEditMode("none");
        setFeedback({
          kind: snap.distanceM <= rules.valve_preferred_snap_m ? "success" : "info",
          message: `Vana ${snap.pipeCode} hattına ${snap.distanceM.toFixed(1)} m mesafeden yakalandı; backend konumu yeniden doğrulayacak.`,
        });
        return;
      }

      if (!startRef.current) {
        const connection = nearestNetworkPoint(
          connectionSourceRef.current,
          click,
          rules.snap_tolerance_m,
          editExclusionRef.current.pipeId,
        );
        if (!connection) {
          const disconnectedValveSelected = disconnectedValveCoordinatesRef.current.some(
            (coordinate) => distanceMeters(click, coordinate) <= rules.snap_tolerance_m,
          );
          addInvalidPoint(disconnectedValveSelected
            ? "Seçilen vana mevcut bir boru hattına bağlı değil"
            : "Yeni boru mevcut şebekeye bağlı olmalıdır.");
          return;
        }
        const startMatch = findNetworkStart(
          graphRef.current,
          connection,
          pipeSourceRef.current,
          rules.route_click_snap_m,
        );
        if (!startMatch) {
          addInvalidPoint(connection.connectionType === "valve"
            ? "Seçilen vana mevcut bir boru hattına bağlı değil"
            : "Bağlantı noktasından çıkılabilen boş bir izinli yol kolu bulunamadı.");
          return;
        }
        sourceRef.current.clear();
        sourceRef.current.addFeature(new Feature({ geometry: new Point(connection.coordinate), state: "start" }));
        startRef.current = { node: startMatch.node, pipe: startMatch.pipe, connection };
        setFeedback({ kind: "info", message: "Başlangıç şebekeye bağlandı. Çalışma alanı içindeki bitiş konumunu seçin." });
        return;
      }

      if (distanceMeters(startRef.current.connection.coordinate, click) < 0.01) {
        addInvalidPoint("Borunun başlangıç ve bitiş noktası aynı olamaz.");
        return;
      }
      const route = shortestRoute(
        graphRef.current,
        startRef.current.node,
        click,
        rules.route_click_snap_m,
        rules.pipe_max_length_m,
      );
      if (!route) {
        const longerRoute = shortestRoute(
          graphRef.current,
          startRef.current.node,
          click,
          rules.route_click_snap_m,
          Number.POSITIVE_INFINITY,
        );
        if (longerRoute && longerRoute.lengthM > rules.pipe_max_length_m) {
          addInvalidPoint(`Boru çok uzun. En fazla ${rules.pipe_max_length_m.toFixed(0)} m çizilebilir.`);
          return;
        }
        addInvalidPoint("Bu bitişe boş ve bağlantılı izinli yol grafiği üzerinden geçerli rota üretilemedi.");
        return;
      }
      const connectionLegM = distanceMeters(startRef.current.connection.coordinate, startRef.current.node.coordinate);
      let routeCoordinates = connectionLegM > 0.01
        ? [startRef.current.connection.coordinate, ...route.coordinates]
        : route.coordinates;
      const totalLengthM = route.lengthM + connectionLegM;
      if (totalLengthM < rules.pipe_min_length_m) {
        addInvalidPoint(`Boru çok kısa. En az ${rules.pipe_min_length_m.toFixed(0)} m olmalıdır.`);
        return;
      }
      if (totalLengthM > rules.pipe_max_length_m) {
        addInvalidPoint(`Boru çok uzun. En fazla ${rules.pipe_max_length_m.toFixed(0)} m çizilebilir.`);
        return;
      }
      if (!routeIsAllowed(routeCoordinates)) {
        addInvalidPoint("Üretilen rota çalışma alanı dışına veya yasak alana taşıyor.");
        return;
      }
      const feature = new Feature({ geometry: new LineString(routeCoordinates), state: "valid" });
      sourceRef.current.clear();
      sourceRef.current.addFeature(feature);
      setDraft({
        layerKey: "gasPipes",
        geomWkt: geometryToWkt(feature.getGeometry()!),
        routeLengthM: totalLengthM,
        roadRatio: 1,
        startPipeId: startRef.current.pipe.pipeId,
        startConnectionType: startRef.current.connection.connectionType,
        startConnectionId: startRef.current.connection.connectionId,
      });
      setEditMode("none");
      setFeedback({ kind: "success", message: `${totalLengthM.toFixed(1)} m şebekeye bağlı rota hazır.` });
    });
    return () => unByKey(clickKey);
  }, [map, setEditMode]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === "Escape") clearDraft(); };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [clearDraft]);

  return {
    mode,
    draft,
    start,
    clearDraft,
    markDraftSaved,
    showSavedGeometry,
    removeSavedGeometry,
    feedback,
    topologyStatus,
    refreshNetwork,
    editingActive: mode !== "none" || draft !== null,
  };
}
