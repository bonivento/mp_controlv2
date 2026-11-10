"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "@/components/auth-provider";
import { Alert, Button, Loading, TextField, errMsg } from "@/components/ui";
import { getStore } from "@/lib/data";
import { DEMO_EMAIL, DEMO_PASSWORD } from "@/lib/data/demo-store";
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
    <main id="contenido" className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-4 py-10">
      <div className="mb-6 text-center">
        <span aria-hidden className="mx-auto mb-3 flex size-12 items-center justify-center rounded-lg bg-brand text-lg font-bold text-brand-ink">
          CEP
        </span>
        <h1 className="text-2xl font-semibold">Control Estadístico de Procesos</h1>
        <p className="mt-1 text-sm text-muted">Inicia sesión para ver tus estudios.</p>
      </div>

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
              className={`min-h-9 rounded text-sm font-medium ${mode === m ? "bg-surface shadow-sm" : "text-muted"}`}
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
    </main>
  );
}
