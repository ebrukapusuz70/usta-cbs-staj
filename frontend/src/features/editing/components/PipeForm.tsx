/* Yeni borunun kod, tür, çap ve basınç bilgilerini toplar.
 * Form alanlarını göndermeden önce kontrol eder. */
import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import type { FormErrors, GasPipeCreatePayload, PipeDraftFeature } from "../types/editing";
import { suggestPipeCode } from "../services/topologyService";
import { operatorName, pipeCode, positiveNumber, requiredText, validInstallYear } from "../utils/formValidation";

interface Props { draft: PipeDraftFeature; pending: boolean; onSubmit: (payload: GasPipeCreatePayload) => void; onCancel: () => void; }

const presets = {
  main_line: { diameters: [250, 315, 400], material: "çelik", pressureLevel: "medium", pressure: "4" },
  distribution: { diameters: [90, 110, 125, 160], material: "PE", pressureLevel: "low", pressure: "1" },
  service_line: { diameters: [32, 40, 63], material: "PE", pressureLevel: "low", pressure: "0.3" },
} as const;

export function PipeForm({ draft, pending, onSubmit, onCancel }: Props) {
  // useState form değerlerini ve kullanıcıya gösterilecek doğrulama hatalarını saklar.
  const [values, setValues] = useState({ pipe_code: "", operator_name: "", pipe_type: "distribution" as keyof typeof presets, diameter_mm: "110", material: "PE", pressure_level: "low", operating_pressure_bar: "1", status: "aktif", install_year: String(new Date().getFullYear()) });
  const [errors, setErrors] = useState<FormErrors>({});
  const [suggestionMessage, setSuggestionMessage] = useState("Bölgesel boru kodu önerisi hazırlanıyor…");
  const update = (key: string, value: string) => setValues((current) => ({ ...current, [key]: value }));
  const updateType = (pipeType: keyof typeof presets) => {
    const preset = presets[pipeType];
    setValues((current) => ({ ...current, pipe_type: pipeType, diameter_mm: String(preset.diameters[0]), material: preset.material, pressure_level: preset.pressureLevel, operating_pressure_bar: preset.pressure }));
  };

  useEffect(() => {
    const controller = new AbortController();
    suggestPipeCode(draft.startConnectionType, draft.startConnectionId, controller.signal)
      .then((suggestion) => {
        if (suggestion.suggested_code) {
          setValues((current) => current.pipe_code.trim()
            ? current
            : { ...current, pipe_code: suggestion.suggested_code || "" });
          setSuggestionMessage(suggestion.message || `Otomatik öneri: ${suggestion.suggested_code}`);
          return;
        }
        setSuggestionMessage("Otomatik bölgesel kod oluşturulamadı; geçerli bir boru kodu girin.");
      })
      .catch((error) => {
        if (controller.signal.aborted) return;
        console.error("Pipe code suggestion error", error);
        setSuggestionMessage("Otomatik bölgesel kod oluşturulamadı; geçerli bir boru kodu girin.");
      });
    return () => controller.abort();
  }, [draft.startConnectionId, draft.startConnectionType]);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (pending) return;
    const next: FormErrors = {};
    const pipe_code = pipeCode(values.pipe_code, next);
    const operator_name = operatorName(values.operator_name, next);
    const material = requiredText(values.material, "Malzeme", next, "material");
    const diameter_mm = positiveNumber(values.diameter_mm, "Çap", next, "diameter_mm");
    const operating_pressure_bar = positiveNumber(values.operating_pressure_bar, "İşletme basıncı", next, "operating_pressure_bar");
    const install_year = validInstallYear(values.install_year, next);
    setErrors(next);
    if (Object.keys(next).length) return;
    onSubmit({
      pipe_code,
      operator_name,
      pipe_type: values.pipe_type,
      diameter_mm,
      material,
      pressure_level: values.pressure_level as GasPipeCreatePayload["pressure_level"],
      operating_pressure_bar,
      status: values.status as GasPipeCreatePayload["status"],
      install_year,
      geom_wkt: draft.geomWkt,
      start_connection_type: draft.startConnectionType,
      start_connection_id: draft.startConnectionId,
    });
  }

  const preset = presets[values.pipe_type];
  return <form className="stage4-form" onSubmit={submit} noValidate>
    <h2>Yeni Yol Tabanlı Boru</h2>
    <label>Başlangıç ağ borusu ID<input value={draft.startPipeId} readOnly aria-readonly="true" /></label>
    <label>Rota uzunluğu<input value={`${draft.routeLengthM.toFixed(1)} m`} readOnly aria-readonly="true" /></label>
    <label>Yol koridoru uyumu<input value={`%${(draft.roadRatio * 100).toFixed(0)}`} readOnly aria-readonly="true" /></label>
    <label>Boru kodu<input autoFocus value={values.pipe_code} onChange={(event) => update("pipe_code", event.target.value)} disabled={pending}/>{errors.pipe_code && <small className="error-text">{errors.pipe_code}</small>}</label>
    <small className="form-hint">{suggestionMessage}</small>
    <label>İşlemi Yapan Operatör<input value={values.operator_name} onChange={(event) => update("operator_name", event.target.value)} disabled={pending}/>{errors.operator_name && <small className="error-text">{errors.operator_name}</small>}</label>
    <label>Hat türü<select value={values.pipe_type} onChange={(event) => updateType(event.target.value as keyof typeof presets)} disabled={pending}><option value="main_line">Ana hat</option><option value="distribution">Dağıtım</option><option value="service_line">Servis</option></select></label>
    <label>Çap (uyumlu seri)<select value={values.diameter_mm} onChange={(event) => update("diameter_mm", event.target.value)} disabled={pending}>{preset.diameters.map((diameter) => <option key={diameter} value={diameter}>{diameter} mm</option>)}</select></label>
    <label>Malzeme<input value={values.material} readOnly aria-readonly="true" /></label>
    <label>Basınç sınıfı<select value={values.pressure_level} onChange={(event) => update("pressure_level", event.target.value)} disabled={pending || values.pipe_type !== "main_line"}><option value="low">Düşük</option><option value="medium">Orta</option>{values.pipe_type === "main_line" && <option value="high">Yüksek</option>}</select></label>
    <label>İşletme basıncı (bar)<input type="number" min="0.1" step="0.1" value={values.operating_pressure_bar} onChange={(event) => update("operating_pressure_bar", event.target.value)} disabled={pending}/>{errors.operating_pressure_bar && <small className="error-text">{errors.operating_pressure_bar}</small>}</label>
    <label>Durum<select value={values.status} onChange={(event) => update("status", event.target.value)} disabled={pending}><option value="aktif">Aktif</option><option value="pasif">Pasif</option><option value="bakımda">Bakımda</option></select></label>
    <label>Döşeme yılı<input type="number" min="1900" max={new Date().getFullYear()} value={values.install_year} onChange={(event) => update("install_year", event.target.value)} disabled={pending}/>{errors.install_year && <small className="error-text">{errors.install_year}</small>}</label>
    <p className="form-disclaimer">Geometri izinli OSM yol grafiğinin en kısa rotasıdır. Backend ağ teması, %98 yol koridoru, yasak alan ve çakışma kurallarını yeniden doğrular.</p>
    <div className="form-actions"><button type="submit" disabled={pending}>{pending ? "Kaydediliyor…" : "Kaydet ve Doğrula"}</button><button type="button" className="secondary" onClick={onCancel} disabled={pending}>İptal</button></div>
  </form>;
}
