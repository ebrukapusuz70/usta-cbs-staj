/* Boru ve vana durumlarının kullanıcı etiketi, rengi ve alias dönüşümünü tek yerde tutar. */
import type { AssetStatus, CreatableAssetStatus } from "../types/gis";

export const STATUS_ORDER: AssetStatus[] = ["aktif", "pasif", "bakımda", "bilinmeyen"];

export const STATUS_PRESENTATION: Record<AssetStatus, { label: string; color: string }> = {
  aktif: { label: "Aktif", color: "#16a34a" },
  pasif: { label: "Pasif", color: "#dc2626" },
  bakımda: { label: "Bakımda", color: "#f97316" },
  bilinmeyen: { label: "Bilinmeyen", color: "#6b7280" },
};

function statusKey(value: unknown): string {
  return String(value ?? "")
    .trim()
    .toLocaleLowerCase("tr-TR")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replaceAll("ı", "i");
}

const STATUS_BY_ALIAS: Record<string, CreatableAssetStatus> = {
  aktif: "aktif",
  active: "aktif",
  open: "aktif",
  acik: "aktif",
  pasif: "pasif",
  inactive: "pasif",
  closed: "pasif",
  kapali: "pasif",
  bakimda: "bakımda",
  maintenance: "bakımda",
  tamirde: "bakımda",
};

export function normalizeAssetStatus(value: unknown): AssetStatus {
  return STATUS_BY_ALIAS[statusKey(value)] ?? "bilinmeyen";
}

export function statusLabel(value: unknown): string {
  return STATUS_PRESENTATION[normalizeAssetStatus(value)].label;
}
