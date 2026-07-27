/* Vana ekleme ve boru çizme düğmelerini gösterir.
 * Kullanıcının seçtiği çizim modunu MapView bileşenine iletir. */
import { useEffect, useState } from "react";
import type { EditMode } from "../types/editing";

interface Props {
  mode: EditMode;
  disabled: boolean;
  hasDraft: boolean;
  onStart: (mode: "valve" | "pipe") => void;
  onCancel: () => void;
}

export function EditToolbar({ mode, disabled, hasDraft, onStart, onCancel }: Props) {
  const [showGuide, setShowGuide] = useState(false);

  useEffect(() => {
    if (mode === "none") {
      setShowGuide(false);
      return undefined;
    }
    setShowGuide(true);
    // Mod değişir veya bileşen kapanırsa 15 saniyelik açıklama zamanlayıcısı temizlenir.
    const timer = window.setTimeout(() => setShowGuide(false), 15_000);
    return () => window.clearTimeout(timer);
  }, [mode]);

  return (
    <section className="panel edit-toolbar" aria-label="Harita düzenleme araçları">
      <span className="edit-mode">{mode === "valve" ? "Boruya yakın vana konumunu seçin" : mode === "pipe" ? "Ağ başlangıcı ve yol bitişini seçin" : hasDraft ? "Doğrulanmış taslak form bekliyor" : disabled ? "Vektör topolojisi hazırlanıyor" : "Görüntüleme modu"}</span>
      {showGuide && (
        <p className="edit-guide">
          {mode === "valve"
            ? "Boruya yakın yaklaşık konumu seçin; vana en yakın uygun boruya taşınır."
            : "Bağlı vana, boru ucu veya kavşaktan başlayın; ikinci tıklamayı izinli yol üzerine yapın."}
        </p>
      )}
      <div className="edit-actions">
        <button type="button" className={mode === "valve" ? "active" : ""} disabled={disabled} onClick={() => onStart("valve")}>Vana Ekle</button>
        <button type="button" className={mode === "pipe" ? "active" : ""} disabled={disabled} onClick={() => onStart("pipe")}>Boru Çiz</button>
        <button type="button" className="secondary" disabled={disabled || (mode === "none" && !hasDraft)} onClick={onCancel}>İptal</button>
      </div>
    </section>
  );
}
