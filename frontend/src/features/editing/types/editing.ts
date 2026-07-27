/* Çizim taslakları, API verileri ve bildirimler için ortak türleri tanımlar. */
import type { AssetStatus, CreatableAssetStatus } from "../../../types/gis";

export type EditMode = "none" | "valve" | "pipe";

export interface PipeDraftFeature {
  layerKey: "gasPipes";
  geomWkt: string;
  routeLengthM: number;
  roadRatio: number;
  startPipeId: number;
  startConnectionType: "pipe_endpoint" | "valve" | "junction";
  startConnectionId: number;
}

export interface ValveDraftFeature {
  layerKey: "gasValves";
  geomWkt: string;
  relatedPipeId: number;
  relatedPipeCode: string;
  diameterMm: number;
  snapDistanceM: number;
}

export type DraftFeature = PipeDraftFeature | ValveDraftFeature;

export interface GasPipeCreatePayload {
  pipe_code: string;
  operator_name: string;
  pipe_type: "main_line" | "distribution" | "service_line";
  diameter_mm: number;
  material: string;
  pressure_level: "low" | "medium" | "high";
  operating_pressure_bar: number;
  status: CreatableAssetStatus;
  install_year: number;
  geom_wkt: string;
  start_connection_type: "pipe_endpoint" | "valve" | "junction";
  start_connection_id: number;
}

export interface GasValveCreatePayload {
  valve_code: string;
  operator_name: string;
  valve_type: "isolation" | "control" | "pressure_reducing" | "emergency";
  material: string;
  status: CreatableAssetStatus;
  install_year: number;
  geom_wkt: string;
}

export interface GasPipeUpdatePayload {
  pipe_code?: string;
  operator_name?: string;
  pipe_type?: GasPipeCreatePayload["pipe_type"];
  diameter_mm?: number;
  material?: string;
  pressure_level?: GasPipeCreatePayload["pressure_level"];
  operating_pressure_bar?: number;
  status?: CreatableAssetStatus;
  install_year?: number;
  geom_wkt?: string;
  start_connection_type?: GasPipeCreatePayload["start_connection_type"];
  start_connection_id?: number;
}

export interface GasValveUpdatePayload {
  valve_code?: string;
  operator_name?: string;
  valve_type?: GasValveCreatePayload["valve_type"];
  material?: string;
  status?: CreatableAssetStatus;
  install_year?: number;
  geom_wkt?: string;
}

export interface GasPipeMutationResponse extends Omit<GasPipeCreatePayload, "start_connection_type" | "start_connection_id" | "operator_name"> {
  pipe_id: number;
  operator_name: string | null;
  source: "user_created_stage4" | "user_created_stage4_e2e";
  srid: number;
}

export interface GasValveMutationResponse extends Omit<GasValveCreatePayload, "status" | "operator_name"> {
  valve_id: number;
  diameter_mm: number;
  related_pipe_id: number;
  operator_name: string | null;
  status: AssetStatus;
  source: "user_created_stage4" | "user_created_stage4_e2e";
  srid: number;
}

export type FormErrors = Record<string, string>;

export interface OperationNotice {
  kind: "success" | "error" | "info";
  message: string;
}

export interface PipeCodeSuggestion {
  suggested_code: string | null;
  prefix: string | null;
  basis: "connected_pipe" | "connected_valve" | "junction_pipe" | "dominant_network" | "none";
  message: string | null;
}

export interface ValveCodeSuggestion {
  suggested_code: string | null;
  region_prefix: string | null;
  related_pipe_id: number;
  basis: "related_pipe" | "dominant_network" | "none";
  message: string | null;
}

export interface Stage4TopologyRules {
  snap_tolerance_m: number;
  valve_preferred_snap_m: number;
  valve_max_snap_m: number;
  valve_min_spacing_m: number;
  pipe_road_corridor_m: number;
  pipe_min_road_ratio: number;
  pipe_min_length_m: number;
  pipe_max_length_m: number;
  pipe_network_touch_m: number;
  route_click_snap_m: number;
}

export interface Stage4TopologyPayload {
  source: "verified_local_osm_cache";
  data_crs: "EPSG:4326";
  analysis_crs: "EPSG:32636";
  roads: object;
  restricted_areas: object;
  boundary: object;
  rules: Stage4TopologyRules;
}
