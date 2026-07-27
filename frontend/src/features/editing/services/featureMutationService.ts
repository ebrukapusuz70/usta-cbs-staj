/* Yeni kayıt ekleme ve silme isteklerini backend'e gönderir.
 * HTTP hatalarını kullanıcıya uygun mesajlara dönüştürür. */
import { appConfig } from "../../../config/appConfig";
import type {
  GasPipeCreatePayload,
  GasPipeMutationResponse,
  GasPipeUpdatePayload,
  GasValveCreatePayload,
  GasValveMutationResponse,
  GasValveUpdatePayload,
} from "../types/editing";

interface BackendErrorDetail {
  code?: string;
  message?: string;
  connected_valve_count?: number;
  suggested_code?: string | null;
}

const friendlyErrors: Record<string, string> = {
  FEATURE_READ_ONLY: "Bu kayıt temel demo verisine aittir ve değiştirilemez.",
  FEATURE_NOT_FOUND: "Düzenlenmek veya silinmek istenen kayıt bulunamadı.",
  PIPE_HAS_CONNECTED_VALVES: "Bu boruya bağlı vanalar bulunduğu için boru silinemez. Önce kullanıcı tarafından oluşturulmuş bağlı vanaları silin.",
  PIPE_CODE_CONFLICT: "Bu boru kodu başka bir kayıtta kullanılıyor.",
  VALVE_CODE_CONFLICT: "Bu vana kodu başka bir kayıtta kullanılıyor.",
  INVALID_VALVE_CODE: "Geçerli bir vana kodu girin.",
  VALVE_NOT_ON_PIPE: "Vana mevcut bir boru hattının üzerinde olmalıdır.",
  UPDATE_VALIDATION_FAILED: "Değişiklikler doğrulama kurallarını karşılamıyor.",
};

function parseErrorPayload(text: string, contentType: string): string {
  if (!text || !contentType.includes("json")) return "";
  try {
    const payload = JSON.parse(text) as {
      detail?: string | BackendErrorDetail | Array<{ msg?: string }>;
    };
    if (typeof payload.detail === "string") return payload.detail;
    if (Array.isArray(payload.detail)) {
      return "Gönderilen alanlardan biri veya birkaçı geçerli değil.";
    }
    if (payload.detail && typeof payload.detail === "object") {
      const detail = payload.detail;
      // Backend'in kararlı hata kodu kullanıcı metnine çevrilir; bilinmeyen
      // teknik ayrıntı ham biçimde ekrana taşınmaz.
      const friendly = detail.code ? friendlyErrors[detail.code] : undefined;
      if (friendly) {
        return detail.code === "PIPE_HAS_CONNECTED_VALVES" && detail.connected_valve_count
          ? `${friendly} Bağlı vana sayısı: ${detail.connected_valve_count}.`
          : detail.code === "VALVE_CODE_CONFLICT" && detail.suggested_code
            ? `${friendly} Yeni öneri: ${detail.suggested_code}.`
            : friendly;
      }
    }
  } catch {
    return "";
  }
  return "";
}

async function apiRequest<T>(path: string, options: RequestInit, externalSignal: AbortSignal): Promise<T> {
  // Ortak istek yardımcısı zaman aşımını, HTTP hatasını ve JSON yanıtını tek yerde işler.
  const timeout = new AbortController();
  const timer = window.setTimeout(() => timeout.abort(), 12_000);
  const abort = () => timeout.abort();
  externalSignal.addEventListener("abort", abort, { once: true });
  try {
    const response = await fetch(`${appConfig.apiBaseUrl}${path}`, { ...options, signal: timeout.signal });
    const contentType = response.headers.get("content-type")?.toLowerCase() || "";
    const text = await response.text();
    const detail = parseErrorPayload(text, contentType);
    if (!response.ok) {
      throw new Error(detail || `API isteği başarısız oldu (HTTP ${response.status}).`);
    }
    if (response.status === 204) return undefined as T;
    if (!contentType.includes("json")) throw new Error("API beklenen JSON yanıtını döndürmedi.");
    if (!text) throw new Error("API boş yanıt döndürdü.");
    return JSON.parse(text) as T;
  } catch (error) {
    console.error("Stage4 API request error", { path, error });
    if (timeout.signal.aborted) throw new Error(externalSignal.aborted ? "İşlem iptal edildi." : "API isteği zaman aşımına uğradı.");
    throw error instanceof Error ? error : new Error("API isteği tamamlanamadı.");
  } finally {
    window.clearTimeout(timer);
    externalSignal.removeEventListener("abort", abort);
  }
}

export const createPipe = (payload: GasPipeCreatePayload, signal: AbortSignal) =>
  apiRequest<GasPipeMutationResponse>("/gas-pipes", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }, signal);

export const createValve = (payload: GasValveCreatePayload, signal: AbortSignal) =>
  apiRequest<GasValveMutationResponse>("/gas-valves", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }, signal);

export const getPipe = (id: number, signal: AbortSignal) =>
  apiRequest<GasPipeMutationResponse>(`/gas-pipes/${id}`, { method: "GET" }, signal);

export const getValve = (id: number, signal: AbortSignal) =>
  apiRequest<GasValveMutationResponse>(`/gas-valves/${id}`, { method: "GET" }, signal);

export const updatePipe = (id: number, payload: GasPipeUpdatePayload, signal: AbortSignal) =>
  apiRequest<GasPipeMutationResponse>(`/gas-pipes/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }, signal);

export const updateValve = (id: number, payload: GasValveUpdatePayload, signal: AbortSignal) =>
  apiRequest<GasValveMutationResponse>(`/gas-valves/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }, signal);

export const deletePipe = (id: number, signal: AbortSignal) =>
  apiRequest<void>(`/gas-pipes/${id}`, { method: "DELETE" }, signal);

export const deleteValve = (id: number, signal: AbortSignal) =>
  apiRequest<void>(`/gas-valves/${id}`, { method: "DELETE" }, signal);
