import { useState } from "react";
import type { FormEvent } from "react";
import type { FeatureInfo } from "../../../types/gis";
import type {
  DraftFeature,
  FormErrors,
  GasPipeMutationResponse,
  GasPipeUpdatePayload,
  GasValveMutationResponse,
  GasValveUpdatePayload,
} from "../types/editing";
import {
  operatorName,
  pipeCode,
  positiveNumber,
  requiredText,
  validInstallYear,
  valveCode,
} from "../utils/formValidation";

interface Props {
  feature: FeatureInfo;
  record: GasPipeMutationResponse | GasValveMutationResponse;
  geometryDraft: DraftFeature | null;
  pending: boolean;
  onPipeSubmit: (payload: GasPipeUpdatePayload) => void;
  onValveSubmit: (payload: GasValveUpdatePayload) => void;
  onStartGeometry: (mode: "pipe" | "valve") => void;
  onCancelGeometry: () => void;
  onCancel: () => void;
}

function PipeEditForm(props: Props & { record: GasPipeMutationResponse }) {
  const { record, geometryDraft, pending } = props;
  const [values, setValues] = useState({
    pipe_code: record.pipe_code,
    operator_name: record.operator_name || "",
    pipe_type: record.pipe_type,
    diameter_mm: String(record.diameter_mm),
    material: record.material,
    pressure_level: record.pressure_level,
    operating_pressure_bar: String(record.operating_pressure_bar),
    status: record.status,
    install_year: String(record.install_year),
  });
  const [errors, setErrors] = useState<FormErrors>({});
  const update = (key: string, value: string) => {
    setValues((current) => ({ ...current, [key]: value }));
  };

  function submit(event: FormEvent) {
    event.preventDefault();
    if (pending) return;
    const next: FormErrors = {};
    const payload: GasPipeUpdatePayload = {
      pipe_code: pipeCode(values.pipe_code, next),
      operator_name: operatorName(values.operator_name, next),
      pipe_type: values.pipe_type,
      diameter_mm: positiveNumber(values.diameter_mm, "Çap", next, "diameter_mm"),
      material: requiredText(values.material, "Malzeme", next, "material"),
      pressure_level: values.pressure_level,
      operating_pressure_bar: positiveNumber(values.operating_pressure_bar, "İşletme basıncı", next, "operating_pressure_bar"),
      status: values.status,
      install_year: validInstallYear(values.install_year, next),
    };
    if (geometryDraft?.layerKey === "gasPipes") {
      // Yeniden çizim serbest sürükleme değildir; useMapDrawing tarafından yol
      // ağı ve bağlantı kurallarıyla üretilen taslak PATCH'e eklenir.
      payload.geom_wkt = geometryDraft.geomWkt;
      payload.start_connection_type = geometryDraft.startConnectionType;
      payload.start_connection_id = geometryDraft.startConnectionId;
    }
    setErrors(next);
    if (!Object.keys(next).length) props.onPipeSubmit(payload);
  }

  return <form className="stage4-form" onSubmit={submit} noValidate>
    <h2>Boru Kaydını Düzenle</h2>
    <label>Boru kodu<input autoFocus value={values.pipe_code} onChange={(event) => update("pipe_code", event.target.value)} disabled={pending} />{errors.pipe_code && <small className="error-text">{errors.pipe_code}</small>}</label>
    <label>İşlemi Yapan Operatör<input value={values.operator_name} onChange={(event) => update("operator_name", event.target.value)} disabled={pending} />{errors.operator_name && <small className="error-text">{errors.operator_name}</small>}</label>
    <label>Hat türü<select value={values.pipe_type} onChange={(event) => update("pipe_type", event.target.value)} disabled={pending}><option value="main_line">Ana hat</option><option value="distribution">Dağıtım</option><option value="service_line">Servis</option></select></label>
    <label>Çap (mm)<input type="number" min="1" value={values.diameter_mm} onChange={(event) => update("diameter_mm", event.target.value)} disabled={pending} />{errors.diameter_mm && <small className="error-text">{errors.diameter_mm}</small>}</label>
    <label>Malzeme<input value={values.material} onChange={(event) => update("material", event.target.value)} disabled={pending} />{errors.material && <small className="error-text">{errors.material}</small>}</label>
    <label>Basınç sınıfı<select value={values.pressure_level} onChange={(event) => update("pressure_level", event.target.value)} disabled={pending}><option value="low">Düşük</option><option value="medium">Orta</option><option value="high">Yüksek</option></select></label>
    <label>İşletme basıncı (bar)<input type="number" min="0.1" step="0.1" value={values.operating_pressure_bar} onChange={(event) => update("operating_pressure_bar", event.target.value)} disabled={pending} />{errors.operating_pressure_bar && <small className="error-text">{errors.operating_pressure_bar}</small>}</label>
    <label>Durum<select value={values.status} onChange={(event) => update("status", event.target.value)} disabled={pending}><option value="aktif">Aktif</option><option value="pasif">Pasif</option><option value="bakımda">Bakımda</option></select></label>
    <label>Döşeme yılı<input type="number" min="1900" max={new Date().getFullYear()} value={values.install_year} onChange={(event) => update("install_year", event.target.value)} disabled={pending} />{errors.install_year && <small className="error-text">{errors.install_year}</small>}</label>
    <div className="geometry-edit-box">
      <strong>Geometri</strong>
      <span>{geometryDraft?.layerKey === "gasPipes" ? `${geometryDraft.routeLengthM.toFixed(1)} m yeni yol rotası hazır.` : "Mevcut güzergâh korunacak."}</span>
      <button type="button" className="secondary" disabled={pending} onClick={() => props.onStartGeometry("pipe")}>Güzergâhı Yeniden Çiz</button>
      {geometryDraft?.layerKey === "gasPipes" && <button type="button" className="secondary" disabled={pending} onClick={props.onCancelGeometry}>Yeni Güzergâhı İptal Et</button>}
    </div>
    <div className="form-actions"><button type="submit" disabled={pending}>{pending ? "Kaydediliyor…" : "Kaydet"}</button><button type="button" className="secondary" disabled={pending} onClick={props.onCancel}>İptal</button></div>
  </form>;
}

function ValveEditForm(props: Props & { record: GasValveMutationResponse }) {
  const { record, geometryDraft, pending } = props;
  const [values, setValues] = useState({
    valve_code: record.valve_code,
    operator_name: record.operator_name || "",
    valve_type: record.valve_type,
    material: record.material,
    status: record.status === "bilinmeyen" ? "aktif" : record.status,
    install_year: String(record.install_year),
  });
  const [errors, setErrors] = useState<FormErrors>({});
  const update = (key: string, value: string) => {
    setValues((current) => ({ ...current, [key]: value }));
  };

  function submit(event: FormEvent) {
    event.preventDefault();
    if (pending) return;
    const next: FormErrors = {};
    const payload: GasValveUpdatePayload = {
      valve_code: valveCode(values.valve_code, next),
      operator_name: operatorName(values.operator_name, next),
      valve_type: values.valve_type,
      material: requiredText(values.material, "Malzeme", next, "material"),
      status: values.status,
      install_year: validInstallYear(values.install_year, next),
    };
    if (geometryDraft?.layerKey === "gasValves") {
      // Form yalnız yaklaşık noktayı gönderir; bağlı boru ve çap backend
      // snapping sonucundan yeniden türetilir.
      payload.geom_wkt = geometryDraft.geomWkt;
    }
    setErrors(next);
    if (!Object.keys(next).length) props.onValveSubmit(payload);
  }

  return <form className="stage4-form" onSubmit={submit} noValidate>
    <h2>Vana Kaydını Düzenle</h2>
    <label>Vana kodu<input autoFocus value={values.valve_code} onChange={(event) => update("valve_code", event.target.value)} disabled={pending} />{errors.valve_code && <small className="error-text">{errors.valve_code}</small>}</label>
    <label>İşlemi Yapan Operatör<input value={values.operator_name} onChange={(event) => update("operator_name", event.target.value)} disabled={pending} />{errors.operator_name && <small className="error-text">{errors.operator_name}</small>}</label>
    <label>Vana türü<select value={values.valve_type} onChange={(event) => update("valve_type", event.target.value)} disabled={pending}><option value="isolation">İzolasyon</option><option value="control">Kontrol</option><option value="pressure_reducing">Basınç düşürücü</option><option value="emergency">Acil durum</option></select></label>
    <label>Malzeme<input value={values.material} onChange={(event) => update("material", event.target.value)} disabled={pending} />{errors.material && <small className="error-text">{errors.material}</small>}</label>
    <label>Durum<select value={values.status} onChange={(event) => update("status", event.target.value)} disabled={pending}><option value="aktif">Aktif</option><option value="pasif">Pasif</option><option value="bakımda">Bakımda</option></select></label>
    <label>Döşeme yılı<input type="number" min="1900" max={new Date().getFullYear()} value={values.install_year} onChange={(event) => update("install_year", event.target.value)} disabled={pending} />{errors.install_year && <small className="error-text">{errors.install_year}</small>}</label>
    <div className="geometry-edit-box">
      <strong>Bağlı boru ve çap</strong>
      <span>{geometryDraft?.layerKey === "gasValves" ? `${geometryDraft.relatedPipeCode} / ${geometryDraft.diameterMm} mm yeni konum hazır.` : `Boru ${record.related_pipe_id} / ${record.diameter_mm} mm korunacak.`}</span>
      <button type="button" className="secondary" disabled={pending} onClick={() => props.onStartGeometry("valve")}>Konumu Değiştir</button>
      {geometryDraft?.layerKey === "gasValves" && <button type="button" className="secondary" disabled={pending} onClick={props.onCancelGeometry}>Yeni Konumu İptal Et</button>}
    </div>
    <div className="form-actions"><button type="submit" disabled={pending}>{pending ? "Kaydediliyor…" : "Kaydet"}</button><button type="button" className="secondary" disabled={pending} onClick={props.onCancel}>İptal</button></div>
  </form>;
}

export function FeatureEditPanel(props: Props) {
  return <aside className="panel feature-form-panel" aria-label="Kayıt düzenleme formu">
    {props.feature.layerKey === "gasPipes"
      ? <PipeEditForm {...props} record={props.record as GasPipeMutationResponse} />
      : <ValveEditForm {...props} record={props.record as GasValveMutationResponse} />}
  </aside>;
}
