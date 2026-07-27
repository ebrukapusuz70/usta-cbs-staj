/* Kayıt ve silme işlemlerinin başarı veya hata mesajını gösterir. */
import { useEffect, useState } from "react";
import type { OperationNotice } from "../types/editing";

export function OperationStatus({ notice }: { notice: OperationNotice | null }) {
  const [visible, setVisible] = useState(Boolean(notice));

  useEffect(() => {
    setVisible(Boolean(notice));
    if (!notice || notice.kind !== "error") return undefined;
    // Yeni hata veya unmount, 30 saniyelik geçersiz alan zamanlayıcısını temizler.
    const timer = window.setTimeout(() => setVisible(false), 30_000);
    return () => window.clearTimeout(timer);
  }, [notice]);

  if (!notice || !visible) return null;
  return (
    <div className={`operation-status ${notice.kind}`} role={notice.kind === "error" ? "alert" : "status"}>
      <span>{notice.message}</span>
      <button type="button" onClick={() => setVisible(false)} aria-label="Bildirimi kapat">×</button>
    </div>
  );
}
