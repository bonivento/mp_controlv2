"use client";

import Link from "next/link";
import { useState } from "react";
import { SigmalenaMark } from "@/components/logo";
import { Alert, Badge, Button, Card, ConfirmDialog, EmptyState, Loading, PageHeader, errMsg } from "@/components/ui";
import { getStore } from "@/lib/data";
import type { Study } from "@/lib/db";
import { useLoad } from "@/lib/use-load";

const fmtDate = (s: string) => new Date(s).toLocaleDateString("es-CO", { day: "2-digit", month: "short", year: "numeric" });

export default function StudiesPage() {
  const { data: studies, loading, error, reload } = useLoad(() => getStore().studies.list(), []);
  const [toDelete, setToDelete] = useState<Study | null>(null);
  const [busy, setBusy] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  async function confirmDelete() {
    if (!toDelete) return;
    setBusy(true);
    try {
      await getStore().studies.remove(toDelete.id);
      setToDelete(null);
      setDeleteError(null);
      reload();
    } catch (e) {
      setDeleteError(errMsg(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <title>Estudios · Sigmalena</title>
      <PageHeader
        title="Estudios"
        subtitle="Cada estudio es un proceso y una característica de calidad. Dentro de él cargas datos, construyes gráficos de control y generas el reporte."
        actions={
          <Link
            href="/estudios/nuevo"
            className="inline-flex min-h-10 items-center rounded-md bg-brand px-4 py-2 text-sm font-medium text-brand-ink hover:bg-brand-strong"
          >
            Nuevo estudio
          </Link>
        }
      />
      {deleteError && <Alert tone="error" className="mb-4">{deleteError}</Alert>}
      {loading && !studies && <Loading label="Cargando estudios…" />}
      {error && <Alert tone="error" title="No se pudieron cargar los estudios">{error}</Alert>}
      {studies && studies.length === 0 && (
        <EmptyState
          icon={<SigmalenaMark size={56} />}
          title="Aún no tienes estudios"
          action={
            <Link
              href="/estudios/nuevo"
              className="inline-flex min-h-10 items-center rounded-md bg-accent px-4 py-2 text-sm font-semibold text-accent-ink hover:bg-accent-strong"
            >
              Crear el primer estudio
            </Link>
          }
        >
          Crea un estudio con la empresa, el proceso y las especificaciones, y después carga los datos.
        </EmptyState>
      )}
      {studies && studies.length > 0 && (
        <ul className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {studies.map((s) => (
            <li key={s.id}>
              <Card className="h-full">
                <div className="flex h-full flex-col gap-3">
                  <div>
                    <h2 className="text-base font-semibold leading-snug">
                      <Link href={`/estudios/${s.id}`} className="hover:underline">
                        {s.name}
                      </Link>
                    </h2>
                    <div className="mt-1.5 flex flex-wrap gap-1.5">
                      <Badge tone="info">{s.data_type === "variable" ? "Variable" : "Atributo"}</Badge>
                      {s.is_synthetic && <Badge tone="warn">Datos sintéticos</Badge>}
                    </div>
                  </div>
                  <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
                    {[
                      ["Empresa", s.company],
                      ["Proceso", s.process],
                      ["Característica", s.characteristic ? `${s.characteristic}${s.unit ? ` (${s.unit})` : ""}` : null],
                      ["Creado", fmtDate(s.created_at)],
                    ].map(([k, v]) => (
                      <div key={k} className="contents">
                        <dt className="text-muted">{k}</dt>
                        <dd>{v || "—"}</dd>
                      </div>
                    ))}
                  </dl>
                  <div className="mt-auto flex flex-wrap gap-2 pt-1">
                    <Link
                      href={`/estudios/${s.id}`}
                      className="inline-flex min-h-10 items-center rounded-md bg-brand px-3.5 py-2 text-sm font-medium text-brand-ink hover:bg-brand-strong"
                    >
                      Abrir
                    </Link>
                    <Link
                      href={`/estudios/${s.id}/editar`}
                      className="inline-flex min-h-10 items-center rounded-md border border-line px-3.5 py-2 text-sm font-medium hover:bg-surface-2"
                    >
                      Editar
                    </Link>
                    <Button variant="ghost" onClick={() => setToDelete(s)} aria-label={`Eliminar ${s.name}`}>
                      Eliminar
                    </Button>
                  </div>
                </div>
              </Card>
            </li>
          ))}
        </ul>
      )}
      <ConfirmDialog
        open={!!toDelete}
        title="Eliminar estudio"
        busy={busy}
        onCancel={() => setToDelete(null)}
        onConfirm={confirmDelete}
        message={
          <>
            Se eliminará <strong className="text-ink">{toDelete?.name}</strong> junto con sus datos, límites congelados, análisis y
            planes de muestreo. Esta acción no se puede deshacer.
          </>
        }
      />
    </>
  );
}
