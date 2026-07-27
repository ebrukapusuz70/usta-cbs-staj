/* OpenLayers haritasını ve WMS katmanlarını yönetir.
 * Nesne sorgulama, çizim, kayıt ve silme işlemlerini birleştirir.
 * GeoServer servisleri ve backend API ile iletişim kurar. */
import { useEffect, useRef, useState } from "react";
import Map from "ol/Map";
import Overlay from "ol/Overlay";
import View from "ol/View";
import { defaults as defaultControls, ScaleLine } from "ol/control";
import { getCenter } from "ol/extent";
import WKT from "ol/format/WKT";
import TileLayer from "ol/layer/Tile";
import OSM from "ol/source/OSM";
import TileWMS from "ol/source/TileWMS";
import type { EventsKey } from "ol/events";
import { unByKey } from "ol/Observable";
import { appConfig } from "../config/appConfig";
import { fetchFeatureInfo, fetchNetworkExtent, normalizeFeatureInfo } from "../services/geoserverService";
import type { FeatureInfo, LayerKey, LayerState } from "../types/gis";
import { FeatureInfoPanel } from "./FeatureInfoPanel";
import { LayerControl } from "./LayerControl";
import { DeleteConfirmationDialog } from "../features/editing/components/DeleteConfirmationDialog";
import { EditToolbar } from "../features/editing/components/EditToolbar";
import { FeatureEditPanel } from "../features/editing/components/FeatureEditPanel";
import { FeatureFormPanel } from "../features/editing/components/FeatureFormPanel";
import { OperationStatus } from "../features/editing/components/OperationStatus";
import { useFeatureMutation } from "../features/editing/hooks/useFeatureMutation";
import { useMapDrawing } from "../features/editing/hooks/useMapDrawing";
import { createPipe, createValve, deletePipe, deleteValve, getPipe, getValve, updatePipe, updateValve } from "../features/editing/services/featureMutationService";
import { verifyCreatedFeature, verifyDeletedFeature } from "../features/editing/services/topologyService";
import type {
  GasPipeCreatePayload,
  GasPipeMutationResponse,
  GasPipeUpdatePayload,
  GasValveCreatePayload,
  GasValveMutationResponse,
  GasValveUpdatePayload,
  OperationNotice,
} from "../features/editing/types/editing";

type WmsLayerMap = Record<LayerKey, TileLayer<TileWMS>>;

// === React state ve ref değişkenleri için başlangıç değerleri ===
const initialLayerState: LayerState = {
  gasPipes: true,
  gasValves: true,
};

// === WMS katmanlarının oluşturulması ===
// TileWMS, GeoServer'dan harita görüntüsünü küçük karo parçaları (tile) halinde alır.
function makeWmsLayer(layerName: string, visible: boolean, zIndex: number): TileLayer<TileWMS> {
  return new TileLayer({
    visible,
    zIndex,
    source: new TileWMS({
      url: appConfig.wmsUrl,
      params: {
        LAYERS: layerName,
        TILED: true,
        FORMAT: "image/png",
        TRANSPARENT: true,
        VERSION: "1.1.1",
      },
      serverType: "geoserver",
      transition: 120,
    }),
  });
}

function waitForRetry(signal: AbortSignal, milliseconds: number): Promise<void> {
  return new Promise((resolve, reject) => {
    // WFS gecikme zamanlayıcısı tamamlanınca veya istek iptal edilince listener kaldırılır.
    const complete = () => {
      signal.removeEventListener("abort", abort);
      resolve();
    };
    const timer = window.setTimeout(complete, milliseconds);
    const abort = () => {
      window.clearTimeout(timer);
      signal.removeEventListener("abort", abort);
      reject(new DOMException("İşlem iptal edildi.", "AbortError"));
    };
    signal.addEventListener("abort", abort, { once: true });
  });
}

async function verifyCreatedFeatureWithRetry(
  layerKey: LayerKey,
  id: number,
  signal: AbortSignal,
): Promise<void> {
  let lastError: unknown;
  for (let attempt = 0; attempt < 5; attempt += 1) {
    try {
      await verifyCreatedFeature(layerKey, id, signal);
      return;
    } catch (error) {
      if (signal.aborted) throw error;
      lastError = error;
      if (attempt < 4) await waitForRetry(signal, 800);
    }
  }
  throw lastError instanceof Error
    ? lastError
    : new Error("Kayıt API/WFS üzerinden doğrulanamadı.");
}

async function verifyDeletedFeatureWithRetry(
  layerKey: LayerKey,
  id: number,
  signal: AbortSignal,
): Promise<void> {
  let lastError: unknown;
  for (let attempt = 0; attempt < 5; attempt += 1) {
    try {
      await verifyDeletedFeature(layerKey, id, signal);
      return;
    } catch (error) {
      if (signal.aborted) throw error;
      lastError = error;
      if (attempt < 4) await waitForRetry(signal, 800);
    }
  }
  throw lastError instanceof Error
    ? lastError
    : new Error("Silinen kayıt API/WFS üzerinden doğrulanamadı.");
}

// === Zoom kontrolü ===
// Katmanların gerçek kapsamını okuyup haritayı bütün ağa sığdırır.
async function fitMapToNetwork(map: Map): Promise<void> {
  const extent = await fetchNetworkExtent();
  map.getView().fit(extent, { padding: [88, 36, 52, 320], maxZoom: 17, duration: 320 });
}

export function MapView() {
  // === React state ve ref değişkenleri ===
  // state ekrana yansıyan bilgiyi, ref ise render dışında yaşayan harita nesnelerini tutar.
  const mapElementRef = useRef<HTMLDivElement | null>(null);
  const popupElementRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<Map | null>(null);
  const overlayRef = useRef<Overlay | null>(null);
  const wmsLayersRef = useRef<Partial<WmsLayerMap>>({});
  const [layerState, setLayerState] = useState<LayerState>(initialLayerState);
  const [loadingLayers, setLoadingLayers] = useState<LayerState>({ gasPipes: false, gasValves: false });
  const [layerErrors, setLayerErrors] = useState<Partial<Record<LayerKey, string>>>({});
  const [feature, setFeature] = useState<FeatureInfo | null>(null);
  const [message, setMessage] = useState("Haritada boru veya vana seçin.");
  const [mapInstance, setMapInstance] = useState<Map | null>(null);
  const [notice, setNotice] = useState<OperationNotice | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<FeatureInfo | null>(null);
  const [editTarget, setEditTarget] = useState<{
    feature: FeatureInfo;
    record: GasPipeMutationResponse | GasValveMutationResponse;
  } | null>(null);
  const mutation = useFeatureMutation();
  const drawing = useMapDrawing(mapInstance);
  const editingActiveRef = useRef(false);
  editingActiveRef.current = drawing.editingActive || mutation.pending || editTarget !== null;

  // === OpenStreetMap altlığının eklenmesi ve OpenLayers Map nesnesinin kurulması ===
  useEffect(() => {
    if (!mapElementRef.current || mapRef.current) {
      return undefined;
    }

    // === WMS katmanlarının oluşturulması ===
    const gasPipes = makeWmsLayer(appConfig.layers.gasPipes.name, true, appConfig.layers.gasPipes.zIndex);
    const gasValves = makeWmsLayer(appConfig.layers.gasValves.name, true, appConfig.layers.gasValves.zIndex);
    wmsLayersRef.current = { gasPipes, gasValves };

    const sourceEventKeys: EventsKey[] = [];
    (Object.keys(wmsLayersRef.current) as LayerKey[]).forEach((key) => {
      const source = wmsLayersRef.current[key]?.getSource();
      if (!source) return;
      sourceEventKeys.push(source.on("tileloadstart", () => {
        setLoadingLayers((current) => ({ ...current, [key]: true }));
      }));
      sourceEventKeys.push(source.on("tileloadend", () => {
        setLoadingLayers((current) => ({ ...current, [key]: false }));
        setLayerErrors((current) => ({ ...current, [key]: undefined }));
      }));
      sourceEventKeys.push(source.on("tileloaderror", () => {
        setLoadingLayers((current) => ({ ...current, [key]: false }));
        setLayerErrors((current) => ({ ...current, [key]: "GeoServer katmanı yüklenemedi." }));
      }));
    });

    const overlay = new Overlay({
      element: popupElementRef.current || undefined,
      autoPan: { animation: { duration: 180 } },
      positioning: "bottom-center",
      offset: [0, -10],
      stopEvent: true,
    });
    overlayRef.current = overlay;

    // OSM() açık sokak haritasını altlık (basemap) olarak, WMS katmanları üst veri olarak ekler.
    const map = new Map({
      target: mapElementRef.current,
      layers: [new TileLayer({ source: new OSM() }), gasPipes, gasValves],
      overlays: [overlay],
      view: new View({
        center: [(appConfig.fallbackExtent[0] + appConfig.fallbackExtent[2]) / 2, (appConfig.fallbackExtent[1] + appConfig.fallbackExtent[3]) / 2],
        zoom: 12,
        projection: "EPSG:3857",
      }),
      controls: defaultControls({ attribution: false }).extend([new ScaleLine()]),
    });

    fitMapToNetwork(map).catch((error) => {
      console.error("WMS extent error", error);
      map.getView().fit(appConfig.fallbackExtent, { padding: [88, 36, 52, 320], maxZoom: 17 });
      setMessage("GeoServer bbox alınamadı; doğrulanmış Yenimahalle kapsamı kullanıldı.");
    });

    // === Harita tıklaması ve WMS GetFeatureInfo ===
    // Düzenleme kapalıyken tıklanan konumu görünür katmanlarda ayrı ayrı sorgular.
    const clickKey: EventsKey = map.on("singleclick", async (event) => {
      if (editingActiveRef.current) return;
      const view = map.getView();
      const resolution = view.getResolution();
      const projection = view.getProjection();
      if (!resolution) {
        return;
      }

      setFeature(null);
      setMessage("Nesne sorgulanıyor...");
      overlay.setPosition(event.coordinate);

      try {
        const queryOrder: LayerKey[] = ["gasValves", "gasPipes"];
        const visibleKeys = queryOrder.filter(
          (key) => wmsLayersRef.current[key]?.getVisible(),
        );
        const results = await Promise.allSettled(
          visibleKeys.map((key) => {
            const layerName = appConfig.layers[key].name;
            const url = wmsLayersRef.current[key]?.getSource()?.getFeatureInfoUrl(event.coordinate, resolution, projection, {
              INFO_FORMAT: "application/json",
              FEATURE_COUNT: 8,
              QUERY_LAYERS: layerName,
            });
            return fetchFeatureInfo(url, key);
          }),
        );
        const rejected = results.filter((result) => result.status === "rejected");
        const selected = results.flatMap((result) => result.status === "fulfilled" ? result.value : []).at(0) || null;
        rejected.forEach((result) => console.error("Layer GetFeatureInfo error", result.reason));
        if (results.length > 0 && rejected.length === results.length) {
          throw new Error("Katman bilgileri yüklenemedi. GeoServer bağlantısını kontrol edin.");
        }
        setFeature(selected);
        setMessage(selected ? "" : "Bu konumda nesne bulunamadı.");
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "Nesne bilgisi alınamadı.");
      }
    });

    const handleResize = () => {
      map.updateSize();
      if (window.innerWidth <= 720) {
        overlay.setPosition(undefined);
        setFeature(null);
        setMessage("Haritada boru veya vana seçin.");
      }
    };
    window.addEventListener("resize", handleResize);

    mapRef.current = map;
    setMapInstance(map);
    return () => {
      unByKey(clickKey);
      unByKey(sourceEventKeys);
      window.removeEventListener("resize", handleResize);
      map.setTarget(undefined);
      mapRef.current = null;
    };
  }, []);

  // === Katman açma/kapatma ===
  function toggleLayer(key: LayerKey) {
    setLayerState((current) => {
      const next = { ...current, [key]: !current[key] };
      wmsLayersRef.current[key]?.setVisible(next[key]);
      return next;
    });
  }

  function closeInfo() {
    setFeature(null);
    setMessage("Haritada boru veya vana seçin.");
    overlayRef.current?.setPosition(undefined);
  }

  function showCreatedFeature(record: object, layerKey: LayerKey) {
    const properties = record as Record<string, unknown>;
    setFeature(normalizeFeatureInfo({ properties }, layerKey));
    setMessage("");
    const wkt = properties.geom_wkt;
    if (typeof wkt !== "string" || !wkt.trim()) {
      overlayRef.current?.setPosition(undefined);
      return;
    }
    try {
      const geometry = new WKT().readGeometry(wkt, {
        dataProjection: "EPSG:3857",
        featureProjection: "EPSG:3857",
      });
      overlayRef.current?.setPosition(getCenter(geometry.getExtent()));
    } catch (error) {
      console.error("Created feature WKT could not be displayed", { layerKey, error });
      overlayRef.current?.setPosition(undefined);
    }
  }

  // === WMS katmanını yenileme ===
  function refreshLayer(key: LayerKey) {
    const source = wmsLayersRef.current[key]?.getSource();
    if (!source) throw new Error("WMS katmanı yenilenemedi.");
    // Yalnız ilgili WMS kaynağının tile cache anahtarı değiştirilir.
    // Yalnız ilgili WMS kaynağının cache anahtarı değişir; diğer katmanlar korunur.
    source.updateParams({ ...source.getParams(), STAGE4_CACHE_BUST: Date.now() });
    source.refresh();
  }

  // === Vana ve boru çizimi ile form açılması ===
  // Asıl çizim ve WKT dönüşümü useMapDrawing.ts içindedir; geçerli taslak formu açar.
  function startEditing(mode: "valve" | "pipe") {
    closeInfo();
    setEditTarget(null);
    setNotice(null);
    drawing.start(mode);
  }

  async function requestEdit(selected: FeatureInfo) {
    const id = Number(selected.id);
    if (!Number.isInteger(id) || id <= 0) {
      setNotice({ kind: "error", message: "Düzenlenecek kayıt ID’si geçersiz." });
      return;
    }
    try {
      drawing.clearDraft();
      const record: GasPipeMutationResponse | GasValveMutationResponse = selected.layerKey === "gasPipes"
        ? await mutation.run((signal) => getPipe(id, signal))
        : await mutation.run((signal) => getValve(id, signal));
      setEditTarget({ feature: selected, record });
      setNotice({ kind: "info", message: `${selected.code} kaydının güncel bilgileri yüklendi.` });
    } catch (error) {
      setNotice({ kind: "error", message: error instanceof Error ? error.message : "Kayıt bilgileri alınamadı." });
    }
  }

  function startGeometryEdit(mode: "pipe" | "valve") {
    if (!editTarget) return;
    const id = Number(editTarget.feature.id);
    drawing.start(
      mode,
      mode === "pipe" ? { pipeId: id } : { valveId: id },
    );
  }

  function cancelFeatureEdit() {
    drawing.clearDraft();
    setEditTarget(null);
    setNotice(null);
  }

  // === Backend'e POST gönderilmesi ===
  // Form verisini API'ye yollar, WFS ile kaydı doğrular ve ilgili WMS katmanını yeniler.
  async function submitPipe(payload: GasPipeCreatePayload) {
    let createdId = 0;
    try {
      const created = await mutation.run(async (signal) => {
        const result = await createPipe(payload, signal);
        createdId = result.pipe_id;
        drawing.showSavedGeometry(result.geom_wkt);
        refreshLayer("gasPipes");
        showCreatedFeature(result, "gasPipes");
        setNotice({ kind: "info", message: `Boru kaydedildi (ID ${result.pipe_id}, Operatör: ${result.operator_name}). Harita servisi doğrulanıyor…` });
        await verifyCreatedFeatureWithRetry("gasPipes", result.pipe_id, signal);
        return result;
      });
      await drawing.refreshNetwork();
      drawing.clearDraft();
      refreshLayer("gasPipes");
      showCreatedFeature(created, "gasPipes");
      setNotice({ kind: "success", message: `Boru kaydedildi (ID ${created.pipe_id}, Operatör: ${created.operator_name}).` });
    } catch (error) {
      setNotice({
        kind: "error",
        message: createdId > 0
          ? `Boru kaydedildi (ID ${createdId}); harita servisi doğrulaması tamamlanamadı. ${error instanceof Error ? error.message : ""}`.trim()
          : error instanceof Error ? error.message : "Boru kaydedilemedi.",
      });
    }
  }

  // Vana akışı da boru akışı gibi POST, doğrulama ve WMS yenileme adımlarını izler.
  async function submitValve(payload: GasValveCreatePayload) {
    let createdId = 0;
    try {
      const created = await mutation.run(async (signal) => {
        const result = await createValve(payload, signal);
        createdId = result.valve_id;
        drawing.showSavedGeometry(result.geom_wkt);
        refreshLayer("gasValves");
        showCreatedFeature(result, "gasValves");
        setNotice({ kind: "info", message: `Vana kaydedildi (ID ${result.valve_id}, Operatör: ${result.operator_name}). Harita servisi doğrulanıyor…` });
        await verifyCreatedFeatureWithRetry("gasValves", result.valve_id, signal);
        return result;
      });
      await drawing.refreshNetwork();
      drawing.clearDraft();
      refreshLayer("gasValves");
      showCreatedFeature(created, "gasValves");
      setNotice({ kind: "success", message: `Vana kaydedildi (ID ${created.valve_id}, Operatör: ${created.operator_name}).` });
    } catch (error) {
      setNotice({
        kind: "error",
        message: createdId > 0
          ? `Vana kaydedildi (ID ${createdId}); harita servisi doğrulaması tamamlanamadı. ${error instanceof Error ? error.message : ""}`.trim()
          : error instanceof Error ? error.message : "Vana kaydedilemedi.",
      });
    }
  }

  async function submitPipeUpdate(payload: GasPipeUpdatePayload) {
    if (!editTarget || editTarget.feature.layerKey !== "gasPipes") return;
    const id = Number(editTarget.feature.id);
    let updated: GasPipeMutationResponse | null = null;
    try {
      updated = await mutation.run(async (signal) => {
        const result = await updatePipe(id, payload, signal);
        updated = result;
        // PATCH'in kanonik geometrisi WFS beklenirken geçici vektörde gösterilir;
        // ilgili WMS cache anahtarı diğer katmanlara dokunmadan yenilenir.
        drawing.showSavedGeometry(result.geom_wkt);
        refreshLayer("gasPipes");
        showCreatedFeature(result, "gasPipes");
        setNotice({ kind: "info", message: `${result.pipe_code} güncellendi. WFS doğrulanıyor…` });
        await verifyCreatedFeatureWithRetry("gasPipes", id, signal);
        return result;
      });
      await drawing.refreshNetwork();
      drawing.removeSavedGeometry();
      refreshLayer("gasPipes");
      showCreatedFeature(updated, "gasPipes");
      setEditTarget(null);
      setNotice({ kind: "success", message: `${updated.pipe_code} boru kaydı güncellendi.` });
    } catch (error) {
      if (updated) {
        // Veritabanı PATCH'i başarılıysa WFS hatasında aynı mutasyon yeniden
        // gönderilmez; form kapatılır ve yalnız senkronizasyon uyarısı verilir.
        drawing.removeSavedGeometry();
        setEditTarget(null);
        setNotice({ kind: "error", message: `${updated.pipe_code} güncellendi; harita servisi doğrulaması tamamlanamadı.` });
        return;
      }
      setNotice({ kind: "error", message: error instanceof Error ? error.message : "Boru kaydı güncellenemedi." });
    }
  }

  async function submitValveUpdate(payload: GasValveUpdatePayload) {
    if (!editTarget || editTarget.feature.layerKey !== "gasValves") return;
    const id = Number(editTarget.feature.id);
    let updated: GasValveMutationResponse | null = null;
    try {
      updated = await mutation.run(async (signal) => {
        const result = await updateValve(id, payload, signal);
        updated = result;
        drawing.showSavedGeometry(result.geom_wkt);
        refreshLayer("gasValves");
        showCreatedFeature(result, "gasValves");
        setNotice({ kind: "info", message: `${result.valve_code} güncellendi. WFS doğrulanıyor…` });
        await verifyCreatedFeatureWithRetry("gasValves", id, signal);
        return result;
      });
      await drawing.refreshNetwork();
      drawing.removeSavedGeometry();
      refreshLayer("gasValves");
      showCreatedFeature(updated, "gasValves");
      setEditTarget(null);
      setNotice({ kind: "success", message: `${updated.valve_code} vana kaydı güncellendi.` });
    } catch (error) {
      if (updated) {
        drawing.removeSavedGeometry();
        setEditTarget(null);
        setNotice({ kind: "error", message: `${updated.valve_code} güncellendi; harita servisi doğrulaması tamamlanamadı.` });
        return;
      }
      setNotice({ kind: "error", message: error instanceof Error ? error.message : "Vana kaydı güncellenemedi." });
    }
  }

  // === Nesne silme ===
  // Onaylanan kaydı backend'e DELETE ile iletir; ardından harita verisini tazeler.
  async function confirmDelete() {
    if (!deleteTarget) return;
    const target = deleteTarget;
    const id = Number(target.id);
    if (!Number.isInteger(id) || id <= 0) {
      setNotice({ kind: "error", message: "Silinecek kayıt ID’si geçersiz." });
      return;
    }
    let deleted = false;
    try {
      await mutation.run(async (signal) => {
        await (target.layerKey === "gasPipes" ? deletePipe(id, signal) : deleteValve(id, signal));
        deleted = true;
        // Yerel görünüm ancak 204 alındıktan sonra temizlenir; ardından aynı
        // resourceId'nin API ve WFS'de yokluğu sınırlı sayıda doğrulanır.
        drawing.removeSavedGeometry();
        refreshLayer(target.layerKey);
        setDeleteTarget(null);
        closeInfo();
        setNotice({ kind: "info", message: `${target.code} silindi. WFS doğrulanıyor…` });
        await verifyDeletedFeatureWithRetry(target.layerKey, id, signal);
      });
      await drawing.refreshNetwork();
      refreshLayer(target.layerKey);
      setNotice({ kind: "success", message: `${target.code} kaydı silindi.` });
    } catch (error) {
      if (deleted) {
        // DELETE tamamlandıktan sonraki WFS gecikmesi ikinci bir DELETE isteğine
        // dönüşmez; kimlik artık yeniden silinmeye sunulmaz.
        setDeleteTarget(null);
        closeInfo();
        setNotice({ kind: "error", message: `${target.code} silindi; API/WFS doğrulaması tamamlanamadı. Silme isteği tekrarlanmadı.` });
        return;
      }
      setNotice({ kind: "error", message: error instanceof Error ? error.message : "Kayıt silinemedi." });
    }
  }

  // === Bileşenin ekrana çizilmesi ===
  return (
    <div className="map-page">
      <div ref={mapElementRef} className="map-canvas" aria-label="Yenimahalle sentetik gaz haritası" />
      <header className="top-bar">
        <div>
          <span className="eyebrow">Sentetik Demo Verisi</span>
          <h1>Yenimahalle Doğalgaz Ağı</h1>
        </div>
        <div className="service-state">
          <span className="pulse" />
          <span>WMS: {appConfig.workspace}</span>
        </div>
      </header>
      <LayerControl layerState={layerState} loadingLayers={loadingLayers} errors={layerErrors} onToggle={toggleLayer} />
      <EditToolbar mode={drawing.mode} disabled={mutation.pending || drawing.topologyStatus !== "ready" || editTarget !== null} hasDraft={Boolean(drawing.draft)} onStart={startEditing} onCancel={drawing.clearDraft} />
      {drawing.draft && !editTarget && <FeatureFormPanel draft={drawing.draft} pending={mutation.pending} onPipeSubmit={(payload) => void submitPipe(payload)} onValveSubmit={(payload) => void submitValve(payload)} onCancel={drawing.clearDraft} />}
      {editTarget && <FeatureEditPanel feature={editTarget.feature} record={editTarget.record} geometryDraft={drawing.draft} pending={mutation.pending} onPipeSubmit={(payload) => void submitPipeUpdate(payload)} onValveSubmit={(payload) => void submitValveUpdate(payload)} onStartGeometry={startGeometryEdit} onCancelGeometry={drawing.clearDraft} onCancel={cancelFeatureEdit} />}
      <OperationStatus notice={notice || drawing.feedback} />
      <div className="popup-react-host">
        <div ref={popupElementRef} className="popup-anchor">
          <FeatureInfoPanel feature={feature} message={message} onClose={closeInfo} onRequestEdit={(selected) => void requestEdit(selected)} onRequestDelete={setDeleteTarget} />
        </div>
      </div>
      {deleteTarget && <DeleteConfirmationDialog feature={deleteTarget} pending={mutation.pending} onConfirm={() => void confirmDelete()} onCancel={() => setDeleteTarget(null)} />}
    </div>
  );
}
