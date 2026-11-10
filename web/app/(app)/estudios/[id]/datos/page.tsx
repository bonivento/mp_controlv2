"use client";

import { useState } from "react";
import { DataLoader } from "@/components/data/DataLoader";
import { SummaryPanel } from "@/components/data/SummaryPanel";
import { useStudy } from "@/components/study-context";
import { Alert, Badge, Button, Card, ConfirmDialog, EmptyState, Loading, PageHeader, Table, Td, Th, errMsg } from "@/components/ui";
import { getStore } from "@/lib/data";
import { isVariableDataset, sizeLabel } from "@/lib/dataset-utils";
import { isVariableRow, type Dataset } from "@/lib/db-provisional";
import { useLoad } from "@/lib/use-load";

const fmtDate = (s: string) => new Date(s).toLocaleString("es-CO", { dateStyle: "medium", timeStyle: "short" });

export default function DataPage() {
  const { study } = useStudy();
  const { data: datasets, loading, error, reload } = useLoad(() => getStore().datasets.list(study.id), [study.id]);
  const [viewId, setViewId] = useState<string | null>(null);
  const [toDelete, setToDelete] = useState<Dataset | null>(null);
  const [busy, setBusy] = useState(false);
  const [delError, setDelError] = useState<string | null>(null);
  const viewing = datasets?.find((d) => d.id === viewId) ?? null;

  async function remove() {
    if (!toDelete) return;
    setBusy(true);
    try {
      await getStore().datasets.remove(toDelete.id);
      if (viewId === toDelete.id) setViewId(null);
      setToDelete(null);
      setDelError(null);
      reload();
    } catch (e) {
      setDelError(errMsg(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <title>{`Datos · ${study.name} · CEP`}</title>
      <PageHeader
        title="Datos"
        subtitle="Módulo 1: carga el archivo, forma los subgrupos racionales, revisa el resumen y los atípicos, y guarda el conjunto como Fase I o Fase II."
      />
      <div className="flex flex-col gap-6">
        <Card title="Conjuntos de datos guardados">
          {loading && !datasets && <Loading />}
          {error && <Alert tone="error">{error}</Alert>}
          {delError && <Alert tone="error" className="mb-3">{delError}</Alert>}
          {datasets && datasets.length === 0 && (
            <EmptyState title="Este estudio aún no tiene datos">Carga un archivo más abajo y guárdalo como Fase I.</EmptyState>
          )}
          {datasets && datasets.length > 0 && (
            <Table caption="Conjuntos de datos guardados">
              <thead>
                <tr>
                  <Th>Nombre</Th>
                  <Th>Fase</Th>
                  <Th>Subgrupos</Th>
                  <Th>Tamaño</Th>
                  <Th>Archivo</Th>
                  <Th>Guardado</Th>
                  <Th>Acciones</Th>
                </tr>
              </thead>
              <tbody>
                {datasets.map((d) => (
                  <tr key={d.id}>
                    <Td className="font-medium">{d.name}</Td>
                    <Td><Badge tone={d.phase === "I" ? "info" : "ok"}>Fase {d.phase}</Badge></Td>
                    <Td>{d.rows.length}</Td>
                    <Td>{sizeLabel(d)}</Td>
                    <Td>{d.source_file ?? "—"}</Td>
                    <Td>{fmtDate(d.created_at)}</Td>
                    <Td>
                      <div className="flex gap-2">
                        <Button aria-pressed={viewId === d.id} onClick={() => setViewId(viewId === d.id ? null : d.id)}>
                          {viewId === d.id ? "Ocultar" : "Ver resumen"}
                        </Button>
                        <Button variant="ghost" onClick={() => setToDelete(d)} aria-label={`Eliminar ${d.name}`}>
                          Eliminar
                        </Button>
                      </div>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Card>

        {viewing && (
          <section aria-label={`Detalle de ${viewing.name}`} className="flex flex-col gap-4">
            <h2 className="text-lg font-semibold">{viewing.name}</h2>
            {viewing.subgrouping && "justification" in viewing.subgrouping && (
              <Alert tone="info" title="Justificación del subgrupo racional">
                {viewing.subgrouping.justification}
              </Alert>
            )}
            <Card title="Bitácora de limpieza">
              {viewing.cleaning_log.length === 0 ? (
                <p className="text-sm text-muted">Sin registros.</p>
              ) : (
                <Table caption="Bitácora de limpieza">
                  <thead>
                    <tr><Th>Acción</Th><Th>Detalle</Th><Th>Fecha</Th></tr>
                  </thead>
                  <tbody>
                    {viewing.cleaning_log.map((l, i) => (
                      <tr key={i}><Td className="font-medium">{l.action}</Td><Td>{l.detail}</Td><Td>{fmtDate(l.at)}</Td></tr>
                    ))}
                  </tbody>
                </Table>
              )}
            </Card>
            {isVariableDataset(viewing) ? (
              <SummaryPanel
                rows={viewing.rows.filter(isVariableRow)}
                studyId={study.id}
                datasetId={viewing.id}
                title={viewing.name}
              />
            ) : (
              <Card title="Subgrupos">
                <Table caption="Subgrupos de atributos">
                  <thead><tr><Th>Subgrupo</Th><Th>Conteo</Th><Th>Tamaño de muestra</Th></tr></thead>
                  <tbody>
                    {viewing.rows.map((r, i) => (
                      <tr key={i}>
                        <Td>{r.label}</Td>
                        <Td>{"count" in r ? r.count : "—"}</Td>
                        <Td>{"size" in r ? r.size : "—"}</Td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              </Card>
            )}
          </section>
        )}

        <div>
          <h2 className="mb-3 text-lg font-semibold">Cargar datos nuevos</h2>
          <DataLoader study={study} onSaved={reload} />
        </div>
      </div>
      <ConfirmDialog
        open={!!toDelete}
        title="Eliminar conjunto de datos"
        busy={busy}
        onCancel={() => setToDelete(null)}
        onConfirm={remove}
        message={<>Se eliminará <strong className="text-ink">{toDelete?.name}</strong>. Los límites congelados y análisis guardados con él conservan su resultado.</>}
      />
    </>
  );
}
