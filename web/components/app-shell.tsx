"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { useAuth } from "./auth-provider";
import { AssistantButton, AssistantPanel } from "./assistant/assistant-panel";
import { AssistantProvider } from "./assistant/assistant-provider";
import { GuestBanner, GuestSignOutConfirm } from "./guest";
import { SigmalenaLogo } from "./logo";
import { Button, Loading } from "./ui";
import { getStore } from "@/lib/data";

/** Marco de las pantallas protegidas: exige sesión y muestra la barra superior. */
export function AppShell({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const router = useRouter();
  const [leaving, setLeaving] = useState(false);
  const [confirmLeave, setConfirmLeave] = useState(false);

  useEffect(() => {
    if (user === null) router.replace("/login");
  }, [user, router]);

  if (!user) return <Loading label={user === null ? "Redirigiendo al acceso…" : "Verificando sesión…"} />;

  async function signOut() {
    setLeaving(true);
    try {
      await getStore().auth.signOut();
      router.replace("/login");
    } finally {
      setLeaving(false);
      setConfirmLeave(false);
    }
  }

  const demo = getStore().mode === "demo";
  return (
    <AssistantProvider user={user}>
      <header className="no-print on-brand border-b-[3px] border-accent bg-header text-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-2.5">
          <Link href="/estudios" className="flex items-center gap-3 rounded-md" aria-label="Sigmalena, ir a estudios">
            <SigmalenaLogo size={34} variant="onDark" />
            <span className="hidden border-l border-white/30 pl-3 text-xs leading-tight text-white/85 md:inline">
              Control estadístico
              <br />
              de procesos
            </span>
          </Link>
          <div className="flex items-center gap-3 text-sm">
            {demo && (
              <span className="rounded-full border border-warn/50 bg-warn-soft px-2 py-0.5 text-xs text-ink">
                Modo de demostración (datos en este navegador)
              </span>
            )}
            <span className={`${user.isGuest ? "" : "hidden "}text-white/85 sm:inline`}>{user.isGuest ? "Invitado" : user.email}</span>
            <AssistantButton />
            <Button variant="onBrand" loading={leaving} onClick={() => (user.isGuest ? setConfirmLeave(true) : signOut())}>
              Cerrar sesión
            </Button>
          </div>
        </div>
      </header>
      {user.isGuest && <GuestBanner />}
      <GuestSignOutConfirm open={confirmLeave} busy={leaving} onConfirm={signOut} onCancel={() => setConfirmLeave(false)} />
      <main id="contenido" className="mx-auto w-full max-w-7xl flex-1 px-4 py-6">
        {children}
      </main>
      <AssistantPanel />
    </AssistantProvider>
  );
}
