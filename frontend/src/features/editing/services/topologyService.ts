/* Çizimden önce topoloji kurallarını ve mevcut ağı yükler.
 * Backend ve GeoServer WFS servisleriyle iletişim kurar. */
import { appConfig } from "../../../config/appConfig";
import type { LayerKey } from "../../../types/gis";
import type {
  PipeCodeSuggestion,
  Stage4TopologyPayload,
  ValveCodeSuggestion,
} from "../types/editing";

interface FeatureCollectionPayload {
  type: "FeatureCollection";
  features: unknown[];
}

async function fetchJson<T>(url: string, signal: AbortSignal): Promise<T> {
  const response = await fetch(url, { signal, headers: { Accept: "application/json" } });
  const contentType = response.headers.get("content-type")?.toLowerCase() || "";
  const text = await response.text();
  const isGeoServerRequest = url.startsWith(appConfig.geoserverBaseUrl);
  if (!response.ok) {
    let detail = "";
    try {
      const parsed = JSON.parse(text) as { detail?: string };
      detail = parsed.detail || "";
    } catch {
      detail = "";
    }
    // GeoServer JSON yerine XML ExceptionReport döndürebilir; teknik ayrıntı
    // kullanıcıya ham XML olarak gösterilmeden sınırlı biçimde konsola yazılır.
    if (
      isGeoServerRequest
      && (contentType.includes("xml") || text.trimStart().startsWith("<"))
    ) {
      const document = new DOMParser().parseFromString(text, "application/xml");
      const exceptionText = document.querySelector("ExceptionText")?.textContent?.trim();
      console.error("GeoServer WFS ExceptionReport", {
        url,
        status: response.status,
        detail: (exceptionText || "ExceptionReport ayrıntısı okunamadı.").slice(0, 300),
      });
    }
    if (isGeoServerRequest && response.status >= 500) {
      throw new Error("GeoServer bağlantısı kurulamadı. Katman bilgileri yüklenemedi.");
    }
    throw new Error(detail || `Vektör katmanı yüklenemedi (HTTP ${response.status}).`);
  }
  if (!text) throw new Error("Vektör kaynağı boş yanıt döndürdü.");
  if (!contentType.includes("json")) {
    throw new Error(isGeoServerRequest
      ? "GeoServer JSON olmayan bir katman yanıtı döndürdü."
      : "Sunucu JSON olmayan bir yanıt döndürdü.");
  }
  try {
    return JSON.parse(text) as T;
  } catch (error) {
    console.error("JSON response parsing error", { url, error });
    throw new Error(isGeoServerRequest
      ? "GeoServer geçersiz katman verisi döndürdü."
      : "Sunucu geçersiz JSON yanıtı döndürdü.");
  }
}

function ensureFeatureCollection(payload: unknown, label: string): FeatureCollectionPayload {
  if (
    typeof payload !== "object"
    || payload === null
    || (payload as { type?: unknown }).type !== "FeatureCollection"
    || !Array.isArray((payload as { features?: unknown }).features)
  ) {
    throw new Error(`${label} geçerli bir GeoJSON FeatureCollection değil.`);
  }
  return payload as FeatureCollectionPayload;
}

function wfsUrl(layerKey: LayerKey, resourceId?: string): string {
  const config = appConfig.layers[layerKey];
  const params = new URLSearchParams({
    service: "WFS",
    version: "2.0.0",
    request: "GetFeature",
    typeNames: config.name,
    outputFormat: "application/json",
    srsName: "EPSG:3857",
  });
  // WFS 2.0 resourceId, tabloda öznitelik olarak yayımlanmayan primary key
  // yerine GeoServer'ın "gas_pipes.3464" biçimindeki feature ID değerini süzer.
  if (resourceId) params.set("resourceId", resourceId);
  return `${appConfig.wfsUrl}?${params.toString()}`;
}

export async function loadStage4Topology(signal: AbortSignal): Promise<Stage4TopologyPayload> {
  const payload = await fetchJson<Stage4TopologyPayload>(`${appConfig.apiBaseUrl}/stage4/topology`, signal);
  if (payload.source !== "verified_local_osm_cache" || payload.analysis_crs !== "EPSG:32636") {
    throw new Error("Stage 4 için doğrulanmış yerel OSM/EPSG:32636 topolojisi bulunamadı.");
  }
  const { snap_tolerance_m, pipe_min_length_m, pipe_max_length_m } = payload.rules;
  if (
    !Number.isFinite(snap_tolerance_m)
    || snap_tolerance_m <= 0
    || !Number.isFinite(pipe_min_length_m)
    || !Number.isFinite(pipe_max_length_m)
    || pipe_min_length_m <= 0
    || pipe_max_length_m <= pipe_min_length_m
  ) {
    throw new Error("Backend geçersiz ağ kuralı değerleri döndürdü.");
  }
  return payload;
}

export async function loadNetworkFeatures(signal: AbortSignal): Promise<{
  pipes: FeatureCollectionPayload;
  valves: FeatureCollectionPayload;
}> {
  const [rawPipes, rawValves] = await Promise.all([
    fetchJson<FeatureCollectionPayload>(wfsUrl("gasPipes"), signal),
    fetchJson<FeatureCollectionPayload>(wfsUrl("gasValves"), signal),
  ]);
  const pipes = ensureFeatureCollection(rawPipes, "Boru katmanı");
  const valves = ensureFeatureCollection(rawValves, "Vana katmanı");
  return { pipes, valves };
}

export async function suggestPipeCode(
  connectionType: "pipe_endpoint" | "valve" | "junction",
  connectionId: number,
  signal: AbortSignal,
): Promise<PipeCodeSuggestion> {
  const params = new URLSearchParams({
    start_connection_type: connectionType,
    start_connection_id: String(connectionId),
  });
  return fetchJson<PipeCodeSuggestion>(
    `${appConfig.apiBaseUrl}/gas-pipes/suggest-code?${params.toString()}`,
    signal,
  );
}

export async function suggestValveCode(
  relatedPipeId: number,
  signal: AbortSignal,
): Promise<ValveCodeSuggestion> {
  const params = new URLSearchParams({
    related_pipe_id: String(relatedPipeId),
  });
  return fetchJson<ValveCodeSuggestion>(
    `${appConfig.apiBaseUrl}/gas-valves/suggest-code?${params.toString()}`,
    signal,
  );
}

export async function verifyCreatedFeature(layerKey: LayerKey, id: number, signal: AbortSignal): Promise<void> {
  const idField = layerKey === "gasPipes" ? "pipe_id" : "valve_id";
  const resourceName = layerKey === "gasPipes" ? "gas_pipes" : "gas_valves";
  const apiPath = layerKey === "gasPipes" ? "gas-pipes" : "gas-valves";
  // API primary key'i ile WFS feature ID aynı kaydı temsil eder; iki servis
  // birlikte doğrulanarak POST sonrasında yanlış veya gecikmiş kayıt önlenir.
  const [apiRecord, wfsRecord] = await Promise.all([
    fetchJson<Record<string, unknown>>(`${appConfig.apiBaseUrl}/${apiPath}/${id}`, signal),
    fetchJson<FeatureCollectionPayload>(wfsUrl(layerKey, `${resourceName}.${id}`), signal),
  ]);
  const verifiedWfsRecord = ensureFeatureCollection(wfsRecord, "Doğrulama katmanı");
  if (Number(apiRecord[idField]) !== id || verifiedWfsRecord.features.length !== 1) {
    throw new Error("Kayıt POST sonrasında API/WFS üzerinden doğrulanamadı.");
  }
}

export async function verifyDeletedFeature(
  layerKey: LayerKey,
  id: number,
  signal: AbortSignal,
): Promise<void> {
  const resourceName = layerKey === "gasPipes" ? "gas_pipes" : "gas_valves";
  const apiPath = layerKey === "gasPipes" ? "gas-pipes" : "gas-valves";
  const [apiResponse, wfsRecord] = await Promise.all([
    fetch(`${appConfig.apiBaseUrl}/${apiPath}/${id}`, {
      signal,
      headers: { Accept: "application/json" },
    }),
    fetchJson<FeatureCollectionPayload>(
      wfsUrl(layerKey, `${resourceName}.${id}`),
      signal,
    ),
  ]);
  const verifiedWfsRecord = ensureFeatureCollection(wfsRecord, "Silme doğrulama katmanı");
  if (apiResponse.status !== 404 || verifiedWfsRecord.features.length !== 0) {
    throw new Error("Silinen kayıt API/WFS üzerinde hâlâ görünüyor.");
  }
}
