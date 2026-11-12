"use client";

import { useState } from "react";
import { getStore } from "@/lib/data";
import { Alert, Button, ConfirmDialog, Modal, TextField, errMsg } from "./ui";

/** Aviso discreto y persistente de sesión de invitado, con la acción de crear cuenta. */
export function GuestBanner() {
  const [open, setOpen] = useState(false);
  return (
    <div role="note" className="no-print border-b border-warn/40 bg-warn-soft">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-x-4 gap-y-1 px-4 py-1.5 text-sm">
        <p>
          <strong>Sesión de invitado.</strong> Tus datos solo existen en este navegador y se pierden si cierras la sesión o
          borras los datos del sitio.
        </p>
        <button type="button" onClick={() => setOpen(true)} className="min-h-8 font-medium underline underline-offset-2">
          Crear cuenta para conservar mis datos
        </button>
      </div>
      <UpgradeDialog open={open} onClose={() => setOpen(false)} />
    </div>
  );
}

function UpgradeDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<string | null>(null);

  function close() {
    setError(null);
    setPassword("");
    setPending(null);
    onClose();
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) return setError("Escribe un correo electrónico válido.");
    if (password.length < 6) return setError("La contraseña debe tener al menos 6 caracteres.");
    setBusy(true);
    try {
      const r = await getStore().auth.upgradeGuest(email.trim(), password);
      if (r.needsConfirmation) setPending(email.trim());
      else close(); // el cambio de sesión llega por onChange y el aviso desaparece
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal open={open} title="Crear cuenta para conservar mis datos" onClose={close}>
      {pending ? (
        <div className="flex flex-col gap-3">
          <Alert tone="ok" title="Revisa tu correo">
            Enviamos un enlace de confirmación a {pending}. Hasta que lo abras sigues como invitado; tus estudios no se pierden
            ni cambian.
          </Alert>
          <div className="flex justify-end">
            <Button variant="primary" onClick={close}>
              Entendido
            </Button>
          </div>
        </div>
      ) : (
        <form onSubmit={submit} noValidate className="flex flex-col gap-4">
          <p className="text-sm text-muted">Tus estudios y datos actuales pasan a la cuenta nueva; no tendrás que cargarlos otra vez.</p>
          <TextField label="Correo electrónico" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          <TextField
            label="Contraseña"
            type="password"
            autoComplete="new-password"
            required
            hint="Mínimo 6 caracteres."
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          {error && <Alert tone="error">{error}</Alert>}
          <div className="flex justify-end gap-2">
            <Button onClick={close}>Cancelar</Button>
            <Button type="submit" variant="primary" loading={busy}>
              Crear cuenta
            </Button>
          </div>
        </form>
      )}
    </Modal>
  );
}

/** Confirmación previa al cierre de sesión de un invitado. */
export function GuestSignOutConfirm({
  open,
  busy,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  busy: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <ConfirmDialog
      open={open}
      busy={busy}
      title="¿Cerrar la sesión de invitado?"
      confirmLabel="Cerrar sesión y perder mis datos"
      message="Al cerrar la sesión perderás el acceso a tus estudios y conjuntos de datos: un invitado no puede volver a entrar. Si quieres conservarlos, cancela y usa «Crear cuenta para conservar mis datos»."
      onConfirm={onConfirm}
      onCancel={onCancel}
    />
  );
}
