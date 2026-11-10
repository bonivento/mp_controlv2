"use client";

import { useCallback, useEffect, useState } from "react";
import { errMsg } from "@/components/ui";

/**
 * Carga asíncrona con estados de carga y error. Se vuelve a ejecutar cuando
 * cambia alguna dependencia (valores primitivos) o al llamar a `reload`.
 */
export function useLoad<T>(fn: () => Promise<T>, deps: (string | number | boolean | null | undefined)[]) {
  const [version, setVersion] = useState(0);
  const key = `${JSON.stringify(deps)}#${version}`;
  const [res, setRes] = useState<{ key: string; data?: T; error?: string }>({ key: "" });

  useEffect(() => {
    let alive = true;
    fn().then(
      (data) => alive && setRes({ key, data }),
      (e) => alive && setRes({ key, error: errMsg(e) }),
    );
    return () => {
      alive = false;
    };
    // `fn` cambia en cada render; la clave resume cuándo hay que recargar.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const reload = useCallback(() => setVersion((v) => v + 1), []);
  const loading = res.key !== key;
  return { data: res.data, loading, error: loading ? null : (res.error ?? null), reload };
}
