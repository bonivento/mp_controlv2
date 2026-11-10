"use client";

import Link from "next/link";
import { useState } from "react";
import { useStudy } from "@/components/study-context";
import { Alert, Badge, Button, Card, CheckField, ConfirmDialog, EmptyState, Loading, PageHeader, errMsg } from "@/components/ui";
import { api } from "@/lib/api";
import type { components } from "@/lib/api-types";
import { getStore } from "@/lib/data";
import { API_MOCK } from "@/lib/env";
import type { Analysis } from "@/lib/db-provisional";
import { useLoad } from "@/lib/use-load";

type Interp = components["schemas"]["Interpretation"];

const MODULE_LABEL: Record<Analysis["module"], string> = {
  data: "Datos",
  variables: "Gráficos por variables",
  attributes: "Gráficos por atributos",
  assumptions: "Supuestos",
  capability: "Capacidad",
  design: "Diseño de gráficos",
  sampling: "Muestreo de aceptación",
};

const fmtDate = (s: string) => new Date(s).toLocaleString("es-CO", { dateStyle: "medium", timeStyle: "short" });

/**
 * Reporte (módulo 8). En la Ola 1 reúne los análisis guardados con su interpretación;
 * las tablas y figuras numeradas con el contenido completo de cada módulo se terminan en la Ola 2.
 */
export default function ReportPage() {
  const { study } = useStudy();
  const { data, loading, error, reload } = useLoad(() => getStore().analyses.list(study.id), [study.id]);
  const [excelBusy, setExcelBusy] = useState(false);
  const [msg, setMsg] = useState<{ tone: "ok" | "error"; text: string } | null>(null);
  const [toDelete, setToDelete] = useState<Analysis | null>(null);

  const included = (data ?? []).filter((a) => a.in_report);

  async function toggle(a: Analysis, on: boolean) {
    try {
      await getStore().analyses.setInReport(a.id, on);
      reload();
    } catch (e) {
      setMsg({ tone: "error", text: errMsg(e) });
    }
  }

  async function excel() {
    setExcelBusy(true);
    setMsg(null);
    try {
      const blob = await api.excelReport({
        study: {
          name: study.name,
          company: study.company,
          process: study.process,
          product: study.product,
          characteristic: study.characteristic,
          unit: study.unit,
          lsl: study.lsl,
          usl: study.usl,
          target: study.target,
        },
        sections: included.map((a) => ({ module: a.module, title: a.title, created_at: a.created_at, result: a.result })),
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `reporte-${study.name.replace(/\s+/g, "_")}.${API_MOCK ? "csv" : "xlsx"}`;
      link.click();
      URL.revokeObjectURL(url);
      setMsg({ tone: "ok", text: "Descarga iniciada." });
    } catch (e) {
      setMsg({ tone: "error", text: errMsg(e) });
    } finally {
      setExcelBusy(false);
    }
  }

  return (
    <>
      <title>{`Reporte · ${study.name} · CEP`}</title>
      <PageHeader
        title="Reporte"
        subtitle="Módulo 8. Reúne los análisis que guardaste con «Incluir en el reporte»."
        actions={
          <div className="no-print flex gap-2">
            <Button onClick={() => window.print()} disabled={included.length === 0}>Imprimir / guardar PDF</Button>
            <Button variant="primary" onClick={excel} loading={excelBusy} disabled={included.length === 0}>Exportar a Excel</Button>
          </div>
        }
      />
      <Alert tone="info" className="no-print mb-4" title="Vista preliminar">
        Esta versión lista los análisis guardados y su interpretación. Las tablas y figuras numeradas con el detalle de cada módulo se completan en la siguiente etapa.
      </Alert>
      {msg && <Alert tone={msg.tone} className="no-print mb-4">{msg.text}</Alert>}
      {loading && !data && <Loading label="Cargando análisis…" />}
      {error && <Alert tone="error" title="No se pudieron cargar los análisis">{error}</Alert>}
      {data && data.length === 0 && (
        <EmptyState title="Todavía no hay análisis guardados">
          En cada módulo usa «Guardar análisis». Empieza por <Link className="underline" href={`/estudios/${study.id}/${study.data_type === "variable" ? "variables" : "atributos"}`}>los gráficos de control</Link>.
        </EmptyState>
      )}

      {data && data.length > 0 && (
        <div className="flex flex-col gap-4">
          <header className="hidden print:block">
            <h1 className="text-2xl font-semibold">Reporte: {study.name}</h1>
            <p className="text-sm">{[study.company, study.process, study.characteristic].filter(Boolean).join(" · ")}</p>
          </header>
          {data.map((a, i) => {
            const interp = (a.result as { interpretation?: Interp }).interpretation;
            return (
              <Card key={a.id} className={`print-break ${a.in_report ? "" : "no-print opacity-70"}`}>
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <p className="text-xs uppercase tracking-wide text-muted">Análisis {i + 1} · {MODULE_LABEL[a.module]} · {fmtDate(a.created_at)}</p>
                    <h2 className="text-base font-semibold">{a.title}</h2>
                  </div>
                  <div className="no-print flex flex-wrap items-center gap-3">
                    <CheckField label="En el reporte" checked={a.in_report} onChange={(on) => toggle(a, on)} />
                    <Button variant="ghost" onClick={() => setToDelete(a)} aria-label={`Eliminar análisis ${a.title}`}>Eliminar</Button>
                  </div>
                </div>
                {interp ? (
                  <div className="mt-3 text-sm">
                    <p className="font-medium">{interp.summary}</p>
                    {interp.findings.length > 0 && (
                      <ul className="mt-2 list-disc space-y-1 pl-5">{interp.findings.map((f, k) => <li key={k}>{f}</li>)}</ul>
                    )}
                    {interp.warnings.length > 0 && (
                      <div className="mt-2">
                        <Badge tone="warn">Advertencias</Badge>
                        <ul className="mt-1 list-disc space-y-1 pl-5 text-muted">{interp.warnings.map((w, k) => <li key={k}>{w}</li>)}</ul>
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="mt-3 text-sm text-muted">Este análisis no trae interpretación.</p>
                )}
              </Card>
            );
          })}
        </div>
      )}
      <ConfirmDialog
        open={!!toDelete}
        title="Eliminar análisis"
        onCancel={() => setToDelete(null)}
        onConfirm={async () => {
          if (!toDelete) return;
          try {
            await getStore().analyses.remove(toDelete.id);
            setToDelete(null);
            reload();
          } catch (e) {
            setMsg({ tone: "error", text: errMsg(e) });
            setToDelete(null);
          }
        }}
        message={<>Se eliminará <strong className="text-ink">{toDelete?.title}</strong> del estudio.</>}
      />
    </>
  );
}
