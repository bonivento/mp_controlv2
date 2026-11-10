"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { useAuth } from "./auth-provider";
import { Button, Loading } from "./ui";
import { getStore } from "@/lib/data";

/** Marco de las pantallas protegidas: exige sesión y muestra la barra superior. */
export function AppShell({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const router = useRouter();
  const [leaving, setLeaving] = useState(false);

  useEffect(() => {
    if (user === null) router.replace("/login");
  }, [user, router]);

  if (!user) return <Loading label={user === null ? "Redirigiendo al acceso…" : "Verificando sesión…"} />;

  const demo = getStore().mode === "demo";
  return (
    <>
      <header className="no-print border-b border-line bg-surface">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-2.5">
          <Link href="/estudios" className="flex items-center gap-2 font-semibold">
            <span aria-hidden className="flex size-8 items-center justify-center rounded-md bg-brand text-sm font-bold text-brand-ink">
              CEP
            </span>
            <span className="hidden sm:inline">Control Estadístico de Procesos</span>
          </Link>
          <div className="flex items-center gap-3 text-sm">
            {demo && (
              <span className="rounded-full border border-warn/50 bg-warn-soft px-2 py-0.5 text-xs">
                Modo de demostración (datos en este navegador)
              </span>
            )}
            <span className="hidden text-muted sm:inline">{user.email}</span>
            <Button
              loading={leaving}
              onClick={async () => {
                setLeaving(true);
                try {
                  await getStore().auth.signOut();
                  router.replace("/login");
                } finally {
                  setLeaving(false);
                }
              }}
            >
              Cerrar sesión
            </Button>
          </div>
        </div>
      </header>
      <main id="contenido" className="mx-auto w-full max-w-7xl flex-1 px-4 py-6">
        {children}
      </main>
    </>
  );
}
