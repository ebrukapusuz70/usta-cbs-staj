/* GeoServer WMS servisinden katman ve nesne bilgilerini alır.
 * GetFeatureInfo ve GetCapabilities yanıtlarını arayüze hazırlar. */
import { appConfig } from "../config/appConfig";
import { normalizeAssetStatus } from "../config/statusConfig";
import type { FeatureInfo, LayerKey } from "../types/gis";

export type NormalizableFeature = { id?: string | number; properties?: Record<string, unknown> };
type FeatureInfoResponse = { type?: string; features?: NormalizableFeature[] };

function value(properties: Record<string, unknown>, key: string): string {
  const raw = properties[key];
  return raw === null || raw === undefined || raw === "" ? "-" : String(raw);
}

function optionalValue(properties: Record<string, unknown>, key: string): string | undefined {
  const raw = properties[key];
  return raw === null || raw === undefined || raw === "" ? undefined : String(raw);
}

function featureId(feature: NormalizableFeature, properties: Record<string, unknown>, key: LayerKey): string {
  const raw = properties[key === "gasValves" ? "valve_id" : "pipe_id"] ?? feature.id;
  return raw === null || raw === undefined ? "-" : String(raw).split(".").at(-1) || String(raw);
}

export function normalizeFeatureInfo(feature: NormalizableFeature, layerKey: LayerKey): FeatureInfo {
  // GeoServer'ın teknik alan adlarını arayüzün kullandığı ortak veri yapısına çevirir.
  const p = feature.properties || {};
  return {
    id: featureId(feature, p, layerKey), layerKey, layerTitle: appConfig.layers[layerKey].title,
    code: value(p, layerKey === "gasValves" ? "valve_code" : "pipe_code"),
    type: value(p, layerKey === "gasValves" ? "valve_type" : "pipe_type"),
    material: value(p, "material"), diameter: value(p, "diameter_mm"), status: normalizeAssetStatus(p.status),
    source: value(p, "source"), operatorName: optionalValue(p, "operator_name"), pressureLevel: value(p, "pressure_level"),
    operatingPressure: value(p, "operating_pressure_bar"), installYear: value(p, "install_year"),
    length: value(p, "length_m"), district: value(p, "district") === "-" ? "Yenimahalle" : value(p, "district"),
    syntheticNotice: "Bu veriler gerçek doğalgaz altyapısı değildir. Eğitim ve demo amacıyla oluşturulmuş sentetik verilerdir.",
    relatedPipeId: layerKey === "gasValves" ? optionalValue(p, "related_pipe_id") : undefined,
  };
}

async function fetchWithTimeout(url: string, timeoutMs = 12_000): Promise<Response> {
  // Servis yanıt vermezse arayüzün sonsuza kadar beklememesi için isteği süreyle sınırlar.
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  try { return await fetch(url, { signal: controller.signal }); }
  finally { window.clearTimeout(timer); }
}

export async function fetchFeatureInfo(url: string | undefined, layerKey: LayerKey): Promise<FeatureInfo[]> {
  // WMS GetFeatureInfo, tıklanan pikseldeki nesnenin özniteliklerini JSON olarak döndürür.
  if (!url) return [];
  try {
    const response = await fetchWithTimeout(url);
    if (!response.ok) {
      if (response.status >= 500) throw new Error("GeoServer bağlantısı kurulamadı.");
      throw new Error(`Katman bilgileri yüklenemedi (HTTP ${response.status}).`);
    }
    const contentType = response.headers.get("content-type")?.toLowerCase() || "";
    const text = await response.text();
    if (!contentType.includes("json")) {
      throw new Error(`JSON yerine ${contentType || "bilinmeyen içerik"} döndü: ${text.slice(0, 160)}`);
    }
    let payload: FeatureInfoResponse;
    try { payload = JSON.parse(text) as FeatureInfoResponse; }
    catch { throw new Error("GeoServer geçersiz JSON döndürdü."); }
    return (payload.features || []).map((feature) => normalizeFeatureInfo(feature, layerKey));
  } catch (error) {
    console.error("GetFeatureInfo error", { layerKey, error });
    if (error instanceof DOMException && error.name === "AbortError") throw new Error("Nesne sorgusu zaman aşımına uğradı.");
    if (error instanceof Error && error.message.startsWith("GeoServer bağlantısı")) throw error;
    throw new Error(`${appConfig.layers[layerKey].title} nesne bilgisi alınamadı.`);
  }
}

function finiteExtent(values: number[]): values is [number, number, number, number] {
  return values.length === 4 && values.every(Number.isFinite) && values[0] < values[2] && values[1] < values[3] && values.every((n) => Math.abs(n) <= 30_000_000);
}

export async function fetchNetworkExtent(): Promise<[number, number, number, number]> {
  // GetCapabilities belgesinden katmanların EPSG:3857 sınır kutusunu (bounding box) okur.
  const url = `${appConfig.wmsUrl}?service=WMS&version=1.1.1&request=GetCapabilities`;
  const response = await fetchWithTimeout(url);
  if (!response.ok) throw new Error(`GetCapabilities HTTP ${response.status}`);
  const contentType = response.headers.get("content-type")?.toLowerCase() || "";
  const text = await response.text();
  if (!contentType.includes("xml") && !text.trimStart().startsWith("<")) throw new Error("GetCapabilities XML döndürmedi.");
  const document = new DOMParser().parseFromString(text, "application/xml");
  if (document.querySelector("parsererror")) throw new Error("GetCapabilities XML ayrıştırılamadı.");
  const extents: [number, number, number, number][] = [];
  for (const layer of Array.from(document.querySelectorAll("Layer"))) {
    const name = Array.from(layer.children).find((child) => child.tagName === "Name")?.textContent?.trim();
    if (!name || !Object.values(appConfig.layers).some((item) => item.name === name || item.name.endsWith(`:${name}`))) continue;
    const boxes = Array.from(layer.children).filter((child) => child.tagName === "BoundingBox");
    const box = boxes.find((item) => (item.getAttribute("SRS") || item.getAttribute("CRS")) === "EPSG:3857");
    if (!box) continue;
    const extent = ["minx", "miny", "maxx", "maxy"].map((key) => Number(box.getAttribute(key)));
    if (finiteExtent(extent)) extents.push(extent);
  }
  if (!extents.length) throw new Error("EPSG:3857 katman bbox bilgisi bulunamadı.");
  return [Math.min(...extents.map((e) => e[0])), Math.min(...extents.map((e) => e[1])), Math.max(...extents.map((e) => e[2])), Math.max(...extents.map((e) => e[3]))];
}
