/* Yeni vananın kod, tür, malzeme ve durum bilgilerini toplar.
 * Form alanlarını göndermeden önce kontrol eder. */
import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import type { FormErrors, GasValveCreatePayload, ValveDraftFeature } from "../types/editing";
import { suggestValveCode } from "../services/topologyService";
import { operatorName, requiredText, validInstallYear, valveCode } from "../utils/formValidation";

interface Props { draft: ValveDraftFeature; pending: boolean; onSubmit: (payload: GasValveCreatePayload) => void; onCancel: () => void; }

export function ValveForm({ draft, pending, onSubmit, onCancel }: Props) {
  // useState form alanlarını ve doğrulama hatalarını yeniden çizimler arasında korur.
  const defaultMaterial = draft.diameterMm >= 160 ? "çelik" : draft.diameterMm >= 90 ? "dökme demir" : "pirinç";
  const [values, setValues] = useState({ valve_code: "", operator_name: "", valve_type: "isolation", material: defaultMaterial, status: "aktif", install_year: String(new Date().getFullYear()) });
  const [errors, setErrors] = useState<FormErrors>({});
  const [codeMode, setCodeMode] = useState<"loading" | "automatic" | "manual" | "unavailable">("loading");
  const [suggestionMessage, setSuggestionMessage] = useState("Otomatik vana kodu hazırlanıyor…");
  const manualCodeRef = useRef(false);
  const update = (key: string, value: string) => setValues((current) => ({ ...current, [key]: value }));

  useEffect(() => {
    // Öneri yalnız bağlı boru kesinleştikten sonra istenir; kullanıcı yazmaya
    // başladıysa geciken response manuel kodu ezmez.
    const controller = new AbortController();
    manualCodeRef.current = false;
    setCodeMode("loading");
    suggestValveCode(draft.relatedPipeId, controller.signal)
      .then((suggestion) => {
        if (manualCodeRef.current) return;
        if (suggestion.suggested_code) {
          setValues((current) => ({ ...current, valve_code: suggestion.suggested_code || "" }));
          setCodeMode("automatic");
          setSuggestionMessage(suggestion.message || `Otomatik öneri: ${suggestion.suggested_code}`);
          return;
        }
        setCodeMode("unavailable");
        setSuggestionMessage("Otomatik vana kodu oluşturulamadı. Geçerli ve benzersiz bir vana kodu girin.");
      })
      .catch((error) => {
        if (controller.signal.aborted) return;
        console.error("Valve code suggestion error", error);
        setCodeMode("unavailable");
        setSuggestionMessage("Otomatik vana kodu oluşturulamadı. Geçerli ve benzersiz bir vana kodu girin.");
      });
    return () => controller.abort();
  }, [draft.relatedPipeId]);

  const updateValveCode = (value: string) => {
    // İlk kullanıcı değişikliği otomatik öneriyi manuel moda geçirir; boşaltılan
    // alan da yeniden otomatik doldurulmaz.
    manualCodeRef.current = true;
    setCodeMode("manual");
    update("valve_code", value);
  };

  function submit(event: FormEvent) {
    event.preventDefault();
    if (pending) return;
    const next: FormErrors = {};
    const valve_code = valveCode(values.valve_code, next);
    const operator_name = operatorName(values.operator_name, next);
    const material = requiredText(values.material, "Malzeme", next, "material");
    const install_year = validInstallYear(values.install_year, next);
    setErrors(next);
    if (Object.keys(next).length) return;
    onSubmit({ valve_code, operator_name, valve_type: values.valve_type as GasValveCreatePayload["valve_type"], material, status: values.status as GasValveCreatePayload["status"], install_year, geom_wkt: draft.geomWkt });
  }

  return <form className="stage4-form" onSubmit={submit} noValidate>
    <h2>Yeni Boruya Yakalanmış Vana</h2>
    <label>Bağlı boru kodu<input value={draft.relatedPipeCode} readOnly aria-readonly="true" /></label>
    <label>Bağlı boru ID<input value={draft.relatedPipeId} readOnly aria-readonly="true" /></label>
    <label>Boru/vana çapı<input value={`${draft.diameterMm} mm`} readOnly aria-readonly="true" /></label>
    <label>Tıklama-yakalama mesafesi<input value={`${draft.snapDistanceM.toFixed(1)} m`} readOnly aria-readonly="true" /></label>
    <label>Vana kodu <span className={`code-mode ${codeMode}`}>{codeMode === "automatic" ? "Otomatik öneri" : codeMode === "manual" ? "Manuel kod" : codeMode === "loading" ? "Hazırlanıyor" : "Manuel giriş gerekli"}</span><input autoFocus value={values.valve_code} onChange={(event) => updateValveCode(event.target.value)} disabled={pending}/>{errors.valve_code && <small className="error-text">{errors.valve_code}</small>}</label>
    <small className="form-hint">{suggestionMessage}</small>
    <label>İşlemi Yapan Operatör<input value={values.operator_name} onChange={(event) => update("operator_name", event.target.value)} disabled={pending}/>{errors.operator_name && <small className="error-text">{errors.operator_name}</small>}</label>
    <label>Vana türü<select value={values.valve_type} onChange={(event) => update("valve_type", event.target.value)} disabled={pending}><option value="isolation">İzolasyon</option><option value="control">Kontrol</option><option value="pressure_reducing">Basınç düşürücü</option><option value="emergency">Acil durum</option></select></label>
    <label>Malzeme<input value={values.material} onChange={(event) => update("material", event.target.value)} disabled={pending}/>{errors.material && <small className="error-text">{errors.material}</small>}</label>
    <label>Durum<select value={values.status} onChange={(event) => update("status", event.target.value)} disabled={pending}><option value="aktif">Aktif</option><option value="pasif">Pasif</option><option value="bakımda">Bakımda</option></select></label>
    <label>Döşeme yılı<input type="number" min="1900" max={new Date().getFullYear()} value={values.install_year} onChange={(event) => update("install_year", event.target.value)} disabled={pending}/>{errors.install_year && <small className="error-text">{errors.install_year}</small>}</label>
    <p className="form-disclaimer">Boru ID ve çap elle girilemez. Backend en yakın boruyu yeniden bulur, noktayı hatta taşır ve 10 m vana aralığını doğrular.</p>
    <div className="form-actions"><button type="submit" disabled={pending}>{pending ? "Kaydediliyor…" : "Kaydet ve Doğrula"}</button><button type="button" className="secondary" onClick={onCancel} disabled={pending}>İptal</button></div>
  </form>;
}
