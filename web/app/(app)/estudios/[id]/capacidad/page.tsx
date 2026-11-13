"use client";

import Link from "next/link";
import { useState } from "react";
import { DatasetSelect, InterpretationBlock, SaveAnalysis } from "@/components/analysis-parts";
import { HistogramChart } from "@/components/charts/StatCharts";
import { useStudy } from "@/components/study-context";
import { Alert, Badge, Button, Card, CheckField, EmptyState, Loading, NumberField, PageHeader, SelectField, Table, Td, Th, fmtNum } from "@/components/ui";
import { api } from "@/lib/api";
import type { components } from "@/lib/api-types";
import { getStore } from "@/lib/data";
import { isVariableDataset, variableSubgroups } from "@/lib/dataset-utils";
import { describeDepuration, findDepuration, matchingAssumptions, matchingControlAnalysis } from "@/lib/depuration";
import { SIGMA_METHOD_LABEL } from "@/lib/labels";
import { useLoad } from "@/lib/use-load";

type S = components["schemas"];
type Tri = "auto" | "unknown" | "yes" | "no";

const INDEX_ROWS: { key: keyof S["CapabilityResponse"]; name: string; what: string }[] = [
  { key: "cp", name: "Cp", what: "Potencial: ancho de la especificación frente a 6σ (corto plazo), sin considerar el centrado" },
  { key: "cpl", name: "Cpl", what: "Distancia de la media al LSL en unidades de 3σ (corto plazo)" },
  { key: "cpu", name: "Cpu", what: "Distancia de la media al USL en unidades de 3σ (corto plazo)" },
  { key: "cpk", name: "Cpk", what: "Capacidad real: el menor entre Cpl y Cpu (corto plazo)" },
  { key: "pp", name: "Pp", what: "Como Cp pero con la variación total (largo plazo)" },
  { key: "ppl", name: "Ppl", what: "Como Cpl con la variación total" },
  { key: "ppu", name: "Ppu", what: "Como Cpu con la variación total" },
  { key: "ppk", name: "Ppk", what: "Como Cpk con la variación total" },
  { key: "cpm", name: "Cpm", what: "Penaliza el alejamiento de la media respecto al objetivo (requiere objetivo)" },
];

const VERDICT = {
  inadequate: { tone: "error", icon: "×", text: "Inadecuada (Cpk < 1)" },
  marginal: { tone: "warn", icon: "!", text: "Marginal (1 ≤ Cpk < 1,33)" },
  adequate: { tone: "ok", icon: "✓", text: "Adecuada (1,33 ≤ Cpk < 1,67)" },
  excellent: { tone: "ok", icon: "★", text: "Excelente (Cpk ≥ 1,67)" },
} as const;

export default function CapabilityPage() {
  const { study } = useStudy();
  const [datasetId, setDatasetId] = useState("");
  const [lsl, setLsl] = useState<number | null>(study.lsl);
  const [usl, setUsl] = useState<number | null>(study.usl);
  const [target, setTarget] = useState<number | null>(study.target);
  const [method, setMethod] = useState("auto");
  const [confidence, setConfidence] = useState("0.95");
  const [stable, setStable] = useState<Tri>("auto");
  const [normal, setNormal] = useState<Tri>("auto");
  const [req, setReq] = useState<S["CapabilityRequest"] | null>(null);
  const [runDataset, setRunDataset] = useState<string | undefined>();
  // Descripción de los datos que se usaron en el último cálculo (se guarda junto con la petición).
  const [runUsed, setRunUsed] = useState<string>("");
  const [useAll, setUseAll] = useState(false);

  const base = useLoad(async () => {
    const s = getStore();
    const [datasets, analyses, limits] = await Promise.all([s.datasets.list(study.id), s.analyses.list(study.id), s.controlLimits.listActive(study.id)]);
    return { datasets: datasets.filter(isVariableDataset), analyses, limits };
  }, [study.id]);
  const list = base.data?.datasets ?? [];
  const dataset = list.find((d) => d.id === datasetId) ?? list.find((d) => d.phase === "I") ?? list[0];

  // Depuración de Fase I: si los límites congelados vigentes salen de este conjunto, por defecto se
  // usan solo los subgrupos retenidos y la sigma de corto plazo de Fase I.
  const dep = findDepuration(dataset, base.data?.limits ?? []);
  const depActive = !!dep && !useAll;
  const excludedIdx = depActive ? dep!.excluded.map((e) => e.index) : [];
  const dataText = dataset
    ? depActive
      ? `${describeDepuration(dep!)}; sigma de Fase I`
      : dep
        ? `${dep.total} de ${dep.total} subgrupos (todos, sin la depuración de Fase I${dep.excluded.length ? `: se incluyen el ${dep.excluded.map((e) => e.label).join(", ")}` : ""})`
        : `${dataset.rows.length} subgrupos (todos; este conjunto no tiene límites congelados)`
    : "";

  // Estabilidad: del análisis de control guardado que corresponde a estos datos (mismo conjunto, misma
  // fase y mismas exclusiones). Normalidad: del análisis de supuestos sobre las mismas observaciones.
  const nObs = dataset ? (depActive ? dep!.keptObservations : variableSubgroups(dataset).subgroups.flat().length) : 0;
  const savedStable = (matchingControlAnalysis(base.data?.analyses ?? [], dataset, excludedIdx)?.result as { in_control?: boolean } | undefined)?.in_control;
  const savedNormal = (matchingAssumptions(base.data?.analyses ?? [], dataset, nObs)?.result as { is_normal?: boolean } | undefined)?.is_normal;
  const resolve = (t: Tri, saved: boolean | undefined): boolean | null => (t === "auto" ? (saved ?? null) : t === "yes" ? true : t === "no" ? false : null);
  const effStable = resolve(stable, savedStable);
  const effNormal = resolve(normal, savedNormal);

  const res = useLoad(async () => (req ? api.capability(req) : null), [req ? JSON.stringify(req) : ""]);
  const r = req ? res.data : null;

  if (study.data_type !== "variable")
    return <Alert tone="warn" title="Este módulo es para datos de variables">La capacidad con Cp y Cpk requiere mediciones continuas.</Alert>;

  function run() {
    if (!dataset) return;
    const anyFrozen = base.data?.limits.find((l) => l.chart_type === "xbar_r" || l.chart_type === "xbar_s" || l.chart_type === "i_mr");
    // Límites congelados que fijan la sigma: los de la depuración (método automático) o los que se
    // pidieron explícitamente. Con un método explícito la sigma sale de los subgrupos retenidos.
    const frozen = method === "frozen" ? (dep?.limits ?? anyFrozen) : method === "auto" && depActive ? dep!.limits : undefined;
    const subgroups = depActive ? dep!.keptSubgroups : variableSubgroups(dataset).subgroups;
    setRunDataset(dataset.id);
    setRunUsed(dataText);
    setReq({
      subgroups,
      lsl,
      usl,
      target,
      limits: frozen?.limits ?? null,
      sigma_method: method === "auto" || method === "frozen" ? null : (method as S["CapabilityRequest"]["sigma_method"]),
      confidence: Number(confidence),
      is_stable: effStable,
      is_normal: effNormal,
    });
  }

  const triOptions = (saved: boolean | undefined) => (
    <>
      <option value="auto">
        Según mis análisis guardados ({saved == null ? "sin dato" : saved ? "sí" : "no"})
      </option>
      <option value="yes">Sí</option>
      <option value="no">No</option>
      <option value="unknown">No lo sé</option>
    </>
  );
  const verdict = r ? VERDICT[r.verdict] : null;
  const nc: [string, S["NonConforming"]][] = r
    ? [
        ["Esperada, variación dentro del subgrupo (normal)", r.expected_within],
        ["Esperada, variación total (normal)", r.expected_overall],
        ["Observada (conteo directo)", r.observed],
      ]
    : [];

  return (
    <>
      <title>{`Capacidad · ${study.name} · Sigmalena`}</title>
      <PageHeader
        title="Capacidad del proceso"
        subtitle="Módulo 5. Compara la variación natural del proceso con las especificaciones. Solo tiene sentido si el proceso es estable y, para el modelo normal, si los datos son normales."
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
          <Card title="Parámetros">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <DatasetSelect label="Conjunto de datos" datasets={list} value={dataset?.id ?? ""} onChange={setDatasetId} hint="Lo habitual es usar los datos de Fase I ya depurados." />
              <NumberField label="LSL (límite inferior)" value={lsl} onChange={setLsl} hint="Viene del estudio; puedes probar otros valores aquí." />
              <NumberField label="USL (límite superior)" value={usl} onChange={setUsl} />
              <NumberField label="Objetivo (opcional)" value={target} onChange={setTarget} />
              <SelectField label="Estimación de σ dentro del subgrupo" value={method} onChange={(e) => setMethod(e.target.value)}>
                <option value="auto">{depActive ? "Automática: sigma de Fase I (límites congelados)" : "Automática según el tamaño de subgrupo"}</option>
                <option value="rbar_d2">R-barra / d2</option>
                <option value="sbar_c4">S-barra / c4</option>
                <option value="mrbar_d2">Rango móvil / d2 (individuales)</option>
                <option value="frozen" disabled={!base.data?.limits.length}>Límites congelados de Fase I{base.data?.limits.length ? "" : " (no hay)"}</option>
              </SelectField>
              <SelectField label="Nivel de confianza" value={confidence} onChange={(e) => setConfidence(e.target.value)}>
                <option value="0.9">90 %</option>
                <option value="0.95">95 %</option>
                <option value="0.99">99 %</option>
              </SelectField>
              <SelectField label="¿El proceso es estable? (Fase I)" value={stable} onChange={(e) => setStable(e.target.value as Tri)}>
                {triOptions(savedStable)}
              </SelectField>
              <SelectField label="¿Los datos son normales? (módulo 4)" value={normal} onChange={(e) => setNormal(e.target.value as Tri)}>
                {triOptions(savedNormal)}
              </SelectField>
            </div>
            {dataset && (
              <div className="mt-4 flex flex-col gap-2">
                <Alert tone={depActive ? "info" : "warn"} title="Datos que se usarán">
                  {dataText}.
                </Alert>
                {dep && (
                  <CheckField
                    label="Calcular con todos los subgrupos"
                    hint="Ignora la depuración de Fase I: los subgrupos excluidos con causa asignable vuelven a entrar y la sigma se estima de nuevo con ellos. No es lo recomendado."
                    checked={useAll}
                    onChange={setUseAll}
                  />
                )}
              </div>
            )}
            {lsl == null && usl == null && <Alert tone="warn" className="mt-3">Indica al menos una especificación (LSL o USL).</Alert>}
            <div className="mt-4">
              <Button variant="primary" onClick={run} disabled={!dataset || (lsl == null && usl == null)} loading={res.loading && !!req}>
                Calcular capacidad
              </Button>
            </div>
          </Card>

          {!req && <EmptyState title="Aún no hay resultados">Revisa los parámetros y pulsa «Calcular capacidad».</EmptyState>}
          {req && res.loading && !r && <Loading label="Calculando índices…" />}
          {res.error && <Alert tone="error" title="La API no pudo calcular la capacidad">{res.error}</Alert>}

          {r && verdict && req && (
            <>
              {(req.is_stable !== true || req.is_normal !== true) && (
                <Alert tone="warn" title="Antes de interpretar estos índices">
                  <ul className="list-disc pl-5">
                    {req.is_stable === false && <li>El proceso <strong>no es estable</strong>: los índices no predicen su desempeño futuro. Resuelve primero las causas asignables en Fase I.</li>}
                    {req.is_stable == null && <li>No se verificó la estabilidad: no hay un análisis de control guardado para estos mismos datos (mismo conjunto y mismas exclusiones). Corre el gráfico en Variables y guarda el análisis.</li>}
                    {req.is_normal === false && <li>Los datos <strong>no son normales</strong>: la fracción no conforme esperada puede estar sesgada; confía más en la observada.</li>}
                    {req.is_normal == null && <li>No se verificó la normalidad: no hay un análisis de Supuestos guardado sobre estas mismas observaciones. Córrelo en Supuestos y guarda el análisis.</li>}
                  </ul>
                </Alert>
              )}
              <Alert tone="info" title="Datos usados en este cálculo">{runUsed}.</Alert>
              <div className="flex flex-wrap items-center gap-3">
                <Badge tone={verdict.tone}>{verdict.icon} Capacidad {verdict.text}</Badge>
                <Badge tone="neutral">n = {r.n}</Badge>
                <Badge tone="neutral">σ dentro = {fmtNum(r.sigma_within, 4)}</Badge>
                <Badge tone="neutral">σ total = {fmtNum(r.sigma_overall, 4)}</Badge>
                <Badge tone="neutral">Media = {fmtNum(r.mean, 3)}</Badge>
              </div>
              <HistogramChart
                histogram={r.histogram}
                title="Histograma con especificaciones"
                xTitle={study.unit ? `${study.characteristic ?? "Valor"} (${study.unit})` : (study.characteristic ?? "Valor")}
                specs={{ lsl: req.lsl, usl: req.usl, target: req.target }}
                fileName={`${study.name}-capacidad-histograma`}
              />
              <Card title={`Índices de capacidad (IC al ${Math.round((req.confidence ?? 0.95) * 100)} %)`}>
                <Table caption="Índices de capacidad con intervalos de confianza">
                  <thead>
                    <tr><Th>Índice</Th><Th>Valor</Th><Th>IC inferior</Th><Th>IC superior</Th><Th>Qué mide</Th></tr>
                  </thead>
                  <tbody>
                    {INDEX_ROWS.map(({ key, name, what }) => {
                      const v = r[key] as S["IndexValue"];
                      return (
                        <tr key={name}>
                          <Td className="font-semibold">{name}</Td>
                          <Td>{fmtNum(v.value, 3)}</Td>
                          <Td>{fmtNum(v.lower, 3)}</Td>
                          <Td>{fmtNum(v.upper, 3)}</Td>
                          <Td className="max-w-md text-muted">{what}</Td>
                        </tr>
                      );
                    })}
                  </tbody>
                </Table>
                <p className="mt-2 text-xs text-muted">σ dentro estimada con {r.sigma_method === "frozen_limits" ? "los límites congelados de Fase I (sigma de Fase I)" : SIGMA_METHOD_LABEL[r.sigma_method]}. «—» significa que no aplica con las especificaciones dadas.</p>
              </Card>
              <Card title="Fracción no conforme">
                <Table caption="Fracción no conforme esperada y observada">
                  <thead>
                    <tr><Th>Fuente</Th><Th>Bajo el LSL</Th><Th>Sobre el USL</Th><Th>Total</Th><Th>PPM</Th></tr>
                  </thead>
                  <tbody>
                    {nc.map(([name, v]) => (
                      <tr key={name}>
                        <Td className="font-medium">{name}</Td>
                        <Td>{v.below_lsl == null ? "—" : `${fmtNum(v.below_lsl * 100, 4)} %`}</Td>
                        <Td>{v.above_usl == null ? "—" : `${fmtNum(v.above_usl * 100, 4)} %`}</Td>
                        <Td>{fmtNum(v.total * 100, 4)} %</Td>
                        <Td>{fmtNum(v.ppm, 1)}</Td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              </Card>
              <InterpretationBlock interpretation={r.interpretation} />
              <SaveAnalysis
                studyId={study.id}
                datasetId={runDataset}
                module="capability"
                defaultTitle={`Capacidad del proceso · ${list.find((d) => d.id === runDataset)?.name ?? ""}`}
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
