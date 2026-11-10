"use client";

import Link from "next/link";
import { useState } from "react";
import { DatasetSelect, InterpretationBlock, SaveAnalysis } from "@/components/analysis-parts";
import { AcfChart, HistogramChart, QQChart } from "@/components/charts/StatCharts";
import { useStudy } from "@/components/study-context";
import { Alert, Badge, Button, Card, EmptyState, Loading, PageHeader, SelectField, Table, Td, Th, fmtNum } from "@/components/ui";
import { api } from "@/lib/api";
import type { components } from "@/lib/api-types";
import { getStore } from "@/lib/data";
import { flatValues, isVariableDataset } from "@/lib/dataset-utils";
import { useLoad } from "@/lib/use-load";

type S = components["schemas"];

function TestsTable({ title, tests }: { title: string; tests: S["TestResult"][] }) {
  return (
    <Card title={title}>
      <Table caption={title}>
        <thead>
          <tr>
            <Th>Prueba</Th>
            <Th>Hipótesis nula (H0)</Th>
            <Th>Estadístico</Th>
            <Th>Valor p</Th>
            <Th>Valor crítico</Th>
            <Th>Decisión</Th>
          </tr>
        </thead>
        <tbody>
          {tests.map((t) => (
            <tr key={t.name}>
              <Td className="font-medium">{t.name}</Td>
              <Td className="max-w-xs">{t.null_hypothesis}</Td>
              <Td>{fmtNum(t.statistic, 4)}</Td>
              <Td>{fmtNum(t.p_value, 4)}</Td>
              <Td>{fmtNum(t.critical_value, 3)}</Td>
              <Td>{t.reject ? <Badge tone="error">× Se rechaza H0</Badge> : <Badge tone="ok">✓ No se rechaza H0</Badge>}</Td>
            </tr>
          ))}
        </tbody>
      </Table>
      <ul className="mt-3 list-disc space-y-1 pl-5 text-sm">
        {tests.map((t) => (
          <li key={t.name}>
            <strong>{t.name}:</strong> {t.conclusion}
          </li>
        ))}
      </ul>
    </Card>
  );
}

export default function AssumptionsPage() {
  const { study } = useStudy();
  const [datasetId, setDatasetId] = useState("");
  const [alpha, setAlpha] = useState("0.05");
  const [run, setRun] = useState<{ id: string; alpha: number } | null>(null);

  const base = useLoad(async () => (await getStore().datasets.list(study.id)).filter(isVariableDataset), [study.id]);
  const list = base.data ?? [];
  const dataset = list.find((d) => d.id === datasetId) ?? list[0];
  const runDataset = list.find((d) => d.id === run?.id);

  const req: S["AssumptionsRequest"] | null = runDataset && run ? { values: flatValues(runDataset), alpha: run.alpha } : null;
  const res = useLoad(async () => (req ? api.assumptions(req) : null), [run?.id, run?.alpha]);
  const r = req ? res.data : null;

  if (study.data_type !== "variable")
    return <Alert tone="warn" title="Este módulo es para datos de variables">Los supuestos de normalidad e independencia aplican a mediciones continuas.</Alert>;

  return (
    <>
      <title>{`Supuestos · ${study.name} · CEP`}</title>
      <PageHeader
        title="Validación de supuestos"
        subtitle="Módulo 4. Los gráficos de Shewhart y los índices de capacidad suponen datos normales e independientes. Verifícalo antes de interpretar."
      />
      {base.loading && !base.data && <Loading />}
      {base.error && <Alert tone="error">{base.error}</Alert>}
      {base.data && list.length === 0 && (
        <EmptyState title="Primero carga datos" action={<Link href={`/estudios/${study.id}/datos`} className="rounded-md bg-brand px-4 py-2 text-sm font-medium text-brand-ink">Ir a Datos</Link>}>
          Necesitas un conjunto de datos de variables guardado.
        </EmptyState>
      )}
      {list.length > 0 && (
        <div className="flex flex-col gap-4">
          <Card title="Datos a analizar">
            <div className="grid gap-4 sm:grid-cols-3">
              <DatasetSelect label="Conjunto de datos" datasets={list} value={dataset?.id ?? ""} onChange={setDatasetId} hint="Se usan todas las observaciones en el orden en que se tomaron." />
              <SelectField label="Nivel de significancia (α)" value={alpha} onChange={(e) => setAlpha(e.target.value)}>
                <option value="0.1">0,10</option>
                <option value="0.05">0,05</option>
                <option value="0.01">0,01</option>
              </SelectField>
              <div className="flex items-end">
                <Button variant="primary" loading={res.loading && !!req} disabled={!dataset} onClick={() => setRun({ id: dataset!.id, alpha: Number(alpha) })}>
                  Validar supuestos
                </Button>
              </div>
            </div>
            <p className="mt-3 text-sm text-muted">
              Estabilidad y patrones no aleatorios: las reglas de Western Electric y Nelson se configuran en{" "}
              <Link className="underline" href={`/estudios/${study.id}/variables`}>Variables</Link>, donde se ven sobre el gráfico de control.
            </p>
          </Card>

          {!run && <EmptyState title="Aún no hay resultados">Elige el conjunto de datos y pulsa «Validar supuestos».</EmptyState>}
          {run && res.loading && !r && <Loading label="Ejecutando pruebas…" />}
          {res.error && <Alert tone="error" title="La API no pudo validar los supuestos">{res.error}</Alert>}
          {r && (
            <>
              <div className="grid gap-3 sm:grid-cols-2">
                <Alert tone={r.is_normal ? "ok" : "warn"} title={r.is_normal ? "Normalidad: se sostiene" : "Normalidad: no se sostiene"}>
                  {r.is_normal ? "Ninguna prueba rechaza la normalidad." : "Al menos una prueba rechaza la normalidad."}
                </Alert>
                <Alert tone={r.is_independent ? "ok" : "warn"} title={r.is_independent ? "Independencia: se sostiene" : "Independencia: no se sostiene"}>
                  {r.is_independent ? "No hay evidencia de autocorrelación." : "Hay evidencia de autocorrelación o de falta de aleatoriedad."}
                </Alert>
              </div>
              <TestsTable title="Pruebas de normalidad" tests={r.normality} />
              <div className="grid gap-4 lg:grid-cols-2">
                <QQChart points={r.qq} title="Gráfico Q-Q normal" fileName={`${study.name}-qq`} />
                <HistogramChart histogram={r.histogram} title="Histograma con curva normal" xTitle={study.unit ?? "Valor"} fileName={`${study.name}-histograma`} />
              </div>
              <TestsTable title="Pruebas de independencia" tests={r.independence} />
              <AcfChart acf={r.autocorrelation} title="Función de autocorrelación (ACF)" fileName={`${study.name}-acf`} />
              <Card title="Estadística descriptiva">
                <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-5">
                  {(
                    [
                      ["n", r.descriptive.count, 0],
                      ["Media", r.descriptive.mean, 4],
                      ["Desv. estándar", r.descriptive.std, 4],
                      ["Mínimo", r.descriptive.min, 3],
                      ["Q1", r.descriptive.q1, 3],
                      ["Mediana", r.descriptive.median, 3],
                      ["Q3", r.descriptive.q3, 3],
                      ["Máximo", r.descriptive.max, 3],
                      ["Asimetría", r.descriptive.skewness, 3],
                      ["Curtosis (exceso)", r.descriptive.kurtosis, 3],
                    ] as const
                  ).map(([k, v, d]) => (
                    <div key={k}>
                      <dt className="text-xs text-muted">{k}</dt>
                      <dd className="num font-medium">{fmtNum(v, d)}</dd>
                    </div>
                  ))}
                </dl>
              </Card>
              <InterpretationBlock interpretation={r.interpretation} />
              <SaveAnalysis
                studyId={study.id}
                datasetId={runDataset?.id}
                module="assumptions"
                defaultTitle={`Supuestos · ${runDataset?.name ?? ""}`}
                params={req as unknown as Record<string, unknown>}
                result={r as unknown as Record<string, unknown>}
              />
            </>
          )}
        </div>
      )}
    </>
  );
}
