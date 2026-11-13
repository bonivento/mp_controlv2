"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "@/components/auth-provider";
import { SigmalenaMark } from "@/components/logo";
import { Alert, Button, Loading, TextField, errMsg } from "@/components/ui";
import { UniversityShield } from "@/components/university-badge";
import { getStore } from "@/lib/data";
import { DEMO_EMAIL, DEMO_PASSWORD } from "@/lib/data/demo-store";
import { BRAND_DESCRIPTOR, BRAND_NAME, UNIVERSITY_NAME } from "@/lib/brand";
import { DEMO_MODE, NOT_CONFIGURED } from "@/lib/env";

export default function LoginPage() {
  const { user } = useAuth();
  const router = useRouter();
  const [mode, setMode] = useState<"in" | "up">("in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (user) router.replace("/estudios");
  }, [user, router]);

  if (user === undefined) return <Loading label="Verificando sesión…" />;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setNotice(null);
    if (password.length < 6) {
      setError("La contraseña debe tener al menos 6 caracteres.");
      return;
    }
    setBusy(true);
    try {
      const auth = getStore().auth;
      if (mode === "up") {
        const r = await auth.signUp(email, password);
        if (r.needsConfirmation) {
          setNotice("Cuenta creada. Revisa tu correo para confirmarla y luego inicia sesión.");
          setMode("in");
          return;
        }
      } else await auth.signIn(email, password);
      router.replace("/estudios");
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setBusy(false);
    }
  }

  async function guestLogin() {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await getStore().auth.signInAsGuest();
      router.replace("/estudios");
    } catch (err) {
      setError(errMsg(err));
      setBusy(false);
    }
  }

  async function demoLogin() {
    setBusy(true);
    setError(null);
    try {
      await getStore().auth.signIn(DEMO_EMAIL, DEMO_PASSWORD);
      router.replace("/estudios");
    } catch (err) {
      setError(errMsg(err));
      setBusy(false);
    }
  }

  return (
    <main id="contenido" className="flex flex-1 flex-col lg:grid lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
      <section className="on-brand relative flex flex-col justify-between overflow-hidden bg-gradient-to-br from-hero-from to-hero-to px-6 py-8 text-white sm:px-10 lg:px-14 lg:py-16">
        {/* Gráfico de control de fondo: límites punteados y una serie, muy tenues. Solo adorno. */}
        <svg aria-hidden viewBox="0 0 400 300" preserveAspectRatio="xMidYMid slice" className="pointer-events-none absolute inset-0 size-full opacity-[0.14]">
          <path d="M0 90H400M0 220H400" stroke="#fff" strokeWidth="1.5" strokeDasharray="5 6" fill="none" />
          <path d="M0 160H400" stroke="#fff" strokeWidth="1" fill="none" />
          <path d="M0 170L40 140L80 185L120 150L160 175L200 135L240 180L280 145L320 170L360 120L400 100" stroke="#fff" strokeWidth="2" fill="none" strokeLinejoin="round" />
          <circle cx="400" cy="100" r="6" fill="#FF9400" />
        </svg>
        <div className="relative">
          <SigmalenaMark variant="onDark" size={64} />
          <h1 className="mt-4 text-4xl font-bold tracking-tight sm:text-5xl">
            {BRAND_NAME}
            <span className="mt-1.5 block text-lg font-normal tracking-normal text-white/90 sm:text-xl">{BRAND_DESCRIPTOR}</span>
          </h1>
          <p className="mt-4 hidden max-w-sm text-sm leading-relaxed text-white/85 lg:block">
            Gráficos de control por variables y atributos, capacidad de proceso, diseño de cartas y muestreo de aceptación, con
            reporte listo para imprimir.
          </p>
        </div>
        <div className="relative mt-8 hidden items-center gap-3 text-sm text-white/90 lg:flex">
          <UniversityShield tone="dark" height={52} src={192} />
          <span className="max-w-[8rem] leading-tight">{UNIVERSITY_NAME}</span>
        </div>
      </section>

      <section className="flex flex-1 items-center justify-center px-4 py-8 sm:py-10">
        <div className="w-full max-w-md">
          <p className="mb-5 text-sm text-muted">Inicia sesión para ver tus estudios.</p>

      {NOT_CONFIGURED && (
        <Alert tone="error" title="Falta configurar el acceso" className="mb-4">
          Define NEXT_PUBLIC_SUPABASE_URL y NEXT_PUBLIC_SUPABASE_ANON_KEY, o activa NEXT_PUBLIC_DEMO_MODE=1 en web/.env.local
          (ver web/.env.example) y reinicia el servidor.
        </Alert>
      )}
      {DEMO_MODE && (
        <Alert tone="warn" title="Modo de demostración" className="mb-4">
          Las cuentas y los datos se guardan solo en este navegador. Puedes entrar con la cuenta de ejemplo, que ya trae dos
          estudios con datos sintéticos.
          <div className="mt-2">
            <Button onClick={demoLogin} loading={busy} variant="primary">
              Entrar con la cuenta de demostración
            </Button>
          </div>
        </Alert>
      )}

      <form onSubmit={submit} className="flex flex-col gap-4 rounded-lg border border-line bg-surface p-5 shadow-sm" noValidate>
        <div role="tablist" aria-label="Acceso" className="grid grid-cols-2 gap-1 rounded-md bg-surface-2 p-1">
          {(["in", "up"] as const).map((m) => (
            <button
              key={m}
              type="button"
              role="tab"
              aria-selected={mode === m}
              onClick={() => {
                setMode(m);
                setError(null);
              }}
              className={`min-h-9 rounded border-b-[3px] text-sm font-medium ${mode === m ? "border-accent bg-surface font-semibold text-brand-text shadow-sm" : "border-transparent text-muted"}`}
            >
              {m === "in" ? "Iniciar sesión" : "Crear cuenta"}
            </button>
          ))}
        </div>
        <TextField
          label="Correo electrónico"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <TextField
          label="Contraseña"
          type="password"
          autoComplete={mode === "in" ? "current-password" : "new-password"}
          required
          hint={mode === "up" ? "Mínimo 6 caracteres." : undefined}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        {error && <Alert tone="error">{error}</Alert>}
        {notice && <Alert tone="ok">{notice}</Alert>}
        <Button type="submit" variant="primary" loading={busy} disabled={NOT_CONFIGURED}>
          {mode === "in" ? "Entrar" : "Crear cuenta"}
        </Button>
      </form>

      <div className="mt-4 flex flex-col gap-2 rounded-lg border border-line bg-surface p-5 shadow-sm">
        <Button onClick={guestLogin} loading={busy} disabled={NOT_CONFIGURED}>
          Continuar como invitado
        </Button>
        <p className="text-xs text-muted">
          No pide correo. Tus estudios y datos quedan ligados a este navegador: se pierden si cierras la sesión, borras la
          sesión o los datos del sitio. Después puedes crear una cuenta para conservarlos.
        </p>
      </div>
        </div>
      </section>
    </main>
  );
}
