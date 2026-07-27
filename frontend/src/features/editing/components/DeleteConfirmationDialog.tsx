/* Seçilen kaydı silmeden önce kullanıcıdan onay alır.
 * Yanlışlıkla silme işlemini önlemeye yardımcı olur. */
import { useEffect, useRef } from "react";
import type { FeatureInfo } from "../../../types/gis";

interface Props { feature: FeatureInfo; pending: boolean; onConfirm: () => void; onCancel: () => void; }

export function DeleteConfirmationDialog({ feature, pending, onConfirm, onCancel }: Props) {
  const cancelRef = useRef<HTMLButtonElement | null>(null);
  useEffect(() => { cancelRef.current?.focus(); }, []);
  return <div className="dialog-backdrop" role="presentation">
    <section className="delete-dialog" role="dialog" aria-modal="true" aria-labelledby="delete-title">
      <h2 id="delete-title">{feature.layerKey === "gasPipes" ? "Boruyu" : "Vanayı"} sil</h2>
      <p><strong>{feature.code}</strong> kodlu {feature.layerKey === "gasPipes" ? "boruyu" : "vanayı"} silmek istediğinizden emin misiniz?</p>
      <p>Bu işlem geri alınamaz.</p>
      <div className="form-actions"><button ref={cancelRef} type="button" className="secondary" disabled={pending} onClick={onCancel}>Vazgeç</button><button type="button" className="danger" disabled={pending} onClick={onConfirm} aria-label={`${feature.code} kaydını kalıcı olarak sil`}>{pending ? "Siliniyor…" : "Sil"}</button></div>
    </section>
  </div>;
}
