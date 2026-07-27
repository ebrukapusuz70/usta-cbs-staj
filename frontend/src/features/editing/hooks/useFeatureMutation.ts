/* POST ve DELETE isteklerinin bekleme ve iptal durumunu yönetir.
 * Aynı işlemin yanlışlıkla iki kez gönderilmesini önler. */
import { useCallback, useEffect, useRef, useState } from "react";

export function useFeatureMutation() {
  const [pending, setPending] = useState(false);
  const activeRef = useRef(false);
  const controllerRef = useRef<AbortController | null>(null);

  const run = useCallback(async <T,>(operation: (signal: AbortSignal) => Promise<T>): Promise<T> => {
    // Ref kilidi aynı render çevrimindeki çift tıklamayı da tek isteğe indirir.
    if (activeRef.current) throw new Error("Devam eden işlem tamamlanmadan yeni istek gönderilemez.");
    activeRef.current = true;
    setPending(true);
    const controller = new AbortController();
    controllerRef.current = controller;
    try { return await operation(controller.signal); }
    finally {
      if (controllerRef.current === controller) controllerRef.current = null;
      activeRef.current = false;
      setPending(false);
    }
  }, []);

  useEffect(() => () => controllerRef.current?.abort(), []);
  return { pending, run };
}
