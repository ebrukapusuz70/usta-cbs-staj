/* API, GeoServer ve katman ayarlarını tek yerde toplar.
 * Değerleri Vite ortam değişkenlerinden veya varsayılanlardan alır. */
import type { LayerKey } from "../types/gis";

const env = import.meta.env;
const workspace = env.VITE_GEOSERVER_WORKSPACE || "usta_cbs";
const geoserverBaseUrl = env.VITE_GEOSERVER_BASE_URL || "/geoserver";

function layerName(value: string | undefined, fallback: string): string {
  // Katman adı workspace içermiyorsa güvenli biçimde "workspace:layer" biçimine getirir.
  const raw = value || fallback;
  return raw.includes(":") ? raw : `${workspace}:${raw}`;
}

export const appConfig = {
  apiBaseUrl: env.VITE_API_BASE_URL || "/api",
  geoserverBaseUrl,
  workspace,
  wmsUrl: `${geoserverBaseUrl}/${workspace}/wms`,
  wfsUrl: `${geoserverBaseUrl}/${workspace}/wfs`,
  // Verified 2026-07-21 from the live PostGIS geometries; only used if
  // GetCapabilities is temporarily unavailable.
  fallbackExtent: [3_635_115.229, 4_856_130.193, 3_655_946.401, 4_884_927.446] as [number, number, number, number],
  layers: {
    gasPipes: {
      key: "gasPipes" as LayerKey,
      title: "Sentetik Gaz Boruları",
      name: layerName(env.VITE_GAS_PIPES_LAYER, "gas_pipes"),
      color: "#2563eb",
      zIndex: 10,
    },
    gasValves: {
      key: "gasValves" as LayerKey,
      title: "Sentetik Gaz Vanaları",
      name: layerName(env.VITE_GAS_VALVES_LAYER, "gas_valves"),
      color: "#16a34a",
      zIndex: 20,
    },
  },
};
