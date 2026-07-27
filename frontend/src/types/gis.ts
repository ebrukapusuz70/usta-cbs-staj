/* Katman ve seçilen nesne için ortak veri türlerini tanımlar.
 * Harita, servis ve bilgi panelinin aynı yapıyı kullanmasını sağlar. */
export type LayerKey = "gasPipes" | "gasValves";
export type AssetStatus = "aktif" | "pasif" | "bakımda" | "bilinmeyen";
export type CreatableAssetStatus = Exclude<AssetStatus, "bilinmeyen">;

export type LayerState = Record<LayerKey, boolean>;

export interface FeatureInfo {
  id: string;
  layerKey: LayerKey;
  layerTitle: string;
  code: string;
  type: string;
  material: string;
  diameter: string;
  status: AssetStatus;
  source: string;
  operatorName?: string;
  pressureLevel: string;
  operatingPressure: string;
  installYear: string;
  length: string;
  district: string;
  syntheticNotice: string;
  relatedPipeId?: string;
}
