"use client";

import Link from "next/link";
import { useState } from "react";
import { ReportDocument } from "@/components/report/ReportDocument";
import { useStudy } from "@/components/study-context";
import { Alert, Button, Card, CheckField, ConfirmDialog, EmptyState, Loading, PageHeader, Table, Td, Th, errMsg } from "@/components/ui";
import { api } from "@/lib/api";
import { getStore } from "@/lib/data";
import type { Analysis } from "@/lib/db";
import { API_MOCK } from "@/lib/env";
import { MODULE_LABEL, MODULE_ORDER, fmtDateTime, slug } from "@/lib/labels";
import { useLoad } from "@/lib/use-load";

/**
 * Reporte (módulo 8): reúne los análisis guardados con «En el reporte», con su
 * detalle completo (tablas y figuras numeradas al estilo APA). Imprime a PDF con
 * el diálogo del navegador y exporta a Excel con la API.
 */
export default function ReportPage() {
  const { study } = useStudy();
  const { data, loading, error, reload } = useLoad(async () => {
    const s = getStore();
    const [analyses, datasets] = await Promise.all([s.analyses.list(study.id), s.datasets.list(study.id)]);
    return { analyses, datasets };
  }, [study.id]);
  const [excelBusy, setExcelBusy] = useState(false);
  const [msg, setMsg] = useState<{ tone: "ok" | "error"; text: string } | null>(null);
  const [toDelete, setToDelete] = useState<Analysis | null>(null);
  const [delBusy, setDelBusy] = useState(false);

  const all = data?.analyses ?? [];
  // Orden del documento: por módulo y, dentro de cada uno, por fecha de guardado.
  const included = all
    .filter((a) => a.in_report)
    .sort((a, b) => MODULE_ORDER.indexOf(a.module) - MODULE_ORDER.indexOf(b.module) || a.created_at.localeCompare(b.created_at));

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
      link.download = `reporte-${slug(study.name)}.${API_MOCK ? "csv" : "xlsx"}`;
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
      <title>{`Reporte · ${study.name} · Sigmalena`}</title>
      <div className="no-print">
        <PageHeader
          title="Reporte"
          subtitle="Módulo 8. Reúne los análisis que guardaste con «En el reporte»: tablas y figuras numeradas, interpretación y datos del estudio. Para el PDF, usa «Imprimir / guardar PDF» y elige «Guardar como PDF»."
          actions={
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => window.print()} disabled={included.length === 0}>
                Imprimir / guardar PDF
              </Button>
              <Button variant="primary" onClick={excel} loading={excelBusy} disabled={included.length === 0}>
                Exportar a Excel
              </Button>
            </div>
          }
        />
        {msg && <Alert tone={msg.tone} className="mb-4">{msg.text}</Alert>}
        {loading && !data && <Loading label="Cargando análisis…" />}
        {error && <Alert tone="error" title="No se pudieron cargar los análisis">{error}</Alert>}
        {data && all.length === 0 && (
          <EmptyState title="Todavía no hay análisis guardados">
            En cada módulo usa «Guardar análisis». Empieza por{" "}
            <Link className="underline" href={`/estudios/${study.id}/${study.data_type === "variable" ? "variables" : "atributos"}`}>
              los gráficos de control
            </Link>
            .
          </EmptyState>
        )}
        {all.length > 0 && (
          <Card title={`Análisis guardados (${included.length} de ${all.length} en el reporte)`} className="mb-6">
            <Table caption="Análisis guardados">
              <thead>
                <tr>
                  <Th>Análisis</Th>
                  <Th>Módulo</Th>
                  <Th>Guardado</Th>
                  <Th>En el reporte</Th>
                  <Th>Acciones</Th>
                </tr>
              </thead>
              <tbody>
                {all.map((a) => (
                  <tr key={a.id}>
                    <Td className="max-w-md font-medium">{a.title}</Td>
                    <Td>{MODULE_LABEL[a.module] ?? a.module}</Td>
                    <Td>{fmtDateTime(a.created_at)}</Td>
                    <Td>
                      <CheckField label="Incluir" checked={a.in_report} onChange={(on) => toggle(a, on)} />
                    </Td>
                    <Td>
                      <Button variant="ghost" onClick={() => setToDelete(a)} aria-label={`Eliminar análisis ${a.title}`}>
                        Eliminar
                      </Button>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </Card>
        )}
        {data && all.length > 0 && included.length === 0 && (
          <EmptyState title="Ningún análisis está en el reporte">Marca «Incluir» en al menos uno de la tabla de arriba.</EmptyState>
        )}
      </div>

      {data && included.length > 0 && <ReportDocument study={study} analyses={included} datasets={data.datasets} />}

      <ConfirmDialog
        open={!!toDelete}
        title="Eliminar análisis"
        busy={delBusy}
        onCancel={() => setToDelete(null)}
        onConfirm={async () => {
          if (!toDelete) return;
          setDelBusy(true);
          try {
            await getStore().analyses.remove(toDelete.id);
            setToDelete(null);
            reload();
          } catch (e) {
            setMsg({ tone: "error", text: errMsg(e) });
            setToDelete(null);
          } finally {
            setDelBusy(false);
          }
        }}
        message={<>Se eliminará <strong className="text-ink">{toDelete?.title}</strong> del estudio.</>}
      />
    </>
  );
}
