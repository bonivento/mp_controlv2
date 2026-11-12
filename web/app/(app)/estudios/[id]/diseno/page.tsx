"use client";

import { useState } from "react";
import { InterpretationBlock, RuleSelector, SaveAnalysis } from "@/components/analysis-parts";
import { CurveChart, TradeoffChart } from "@/components/charts/StatCharts";
import { useStudy } from "@/components/study-context";
import { Alert, Badge, Button, Card, EmptyState, Loading, NumberField, PageHeader, SelectField, Table, Td, TextField, Th, fmtNum, numEs } from "@/components/ui";
import { api } from "@/lib/api";
import type { components } from "@/lib/api-types";
import { useLoad } from "@/lib/use-load";

type S = components["schemas"];
type RuleId = NonNullable<S["RuleConfig"]["enabled"]>[number];

/** "0.5; 1 2" -> [0.5, 1, 2]. Una sola coma dentro de un número es decimal; null si algo no es positivo. */
function parseList(text: string): number[] | null {
  const parts = text
    .split(/[;\s]+/)
    .map((p) => p.replace(/^,+|,+$/g, ""))
    .filter(Boolean)
    .flatMap((p) => ((p.match(/,/g)?.length ?? 0) > 1 ? p.split(",") : [p]));
  const nums = parts.map((p) => Number(p.replace(",", ".")));
  return nums.length > 0 && nums.every((x) => Number.isFinite(x) && x > 0) ? nums : null;
}

const CHARTS = [
  ["xbar", "X-barra (media del subgrupo)"],
  ["individuals", "Individuales (I)"],
  ["p", "p (fracción defectuosa)"],
  ["c", "c (defectos por unidad)"],
] as const;

export default function DesignPage() {
  const { study } = useStudy();
  // --- Formulario ARL
  const [chart, setChart] = useState<S["ArlRequest"]["chart"]>("xbar");
  const [n, setN] = useState<number | null>(5);
  const [L, setL] = useState<number | null>(3);
  const [h, setH] = useState<number | null>(1);
  const [shifts, setShifts] = useState("0.5, 1, 1.5, 2, 3");
  const [p0, setP0] = useState<number | null>(0.05);
  const [c0, setC0] = useState<number | null>(8);
  const [rules, setRules] = useState<RuleId[]>(["WE1"]);
  const [runs, setRuns] = useState<number | null>(500);
  const [arlReq, setArlReq] = useState<S["ArlRequest"] | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  // --- Comparador
  const [cmpN, setCmpN] = useState("3, 5, 7, 10");
  const [cmpL, setCmpL] = useState("2.5, 3");
  const [cmpH, setCmpH] = useState("0.5, 1, 2");
  const [cmpShift, setCmpShift] = useState<number | null>(1);
  const [cmpReq, setCmpReq] = useState<S["CompareRequest"] | null>(null);
  const [cmpError, setCmpError] = useState<string | null>(null);

  const arl = useLoad(async () => (arlReq ? api.arl(arlReq) : null), [arlReq ? JSON.stringify(arlReq) : ""]);
  const cmp = useLoad(async () => (cmpReq ? api.compareDesigns(cmpReq) : null), [cmpReq ? JSON.stringify(cmpReq) : ""]);
  const a = arlReq ? arl.data : null;
  const c = cmpReq ? cmp.data : null;

  const usesN = chart === "xbar" || chart === "p";
  const shiftLabel = chart === "p" ? "Valores de p1 (fracción defectuosa fuera de control)" : chart === "c" ? "Valores de c1 (defectos fuera de control)" : "Desplazamientos δ (en sigmas)";

  function submitArl() {
    setFormError(null);
    const list = parseList(shifts);
    if (!list) return setFormError("Escribe los desplazamientos como números positivos separados por espacios o punto y coma. Ej.: 0.5; 1; 2.");
    if (!L || !h || (usesN && !n)) return setFormError("n, L y h deben ser números positivos.");
    const req: S["ArlRequest"] = {
      chart,
      n: usesN ? n! : 1,
      limit_width: L,
      sampling_interval: h,
      shifts: chart === "xbar" || chart === "individuals" ? list : [0.5, 1, 1.5, 2, 3],
      p0: chart === "p" ? p0 : null,
      p1: chart === "p" ? list : null,
      c0: chart === "c" ? c0 : null,
      c1: chart === "c" ? list : null,
      rules: { enabled: rules.includes("WE1") ? rules : ["WE1", ...rules] },
      max_runs: runs ?? 500,
      max_length: 20000,
      seed: 12345,
    };
    setArlReq(req);
  }

  function submitCmp() {
    setCmpError(null);
    const ns = parseList(cmpN);
    const ls = parseList(cmpL);
    const hs = parseList(cmpH);
    if (!ns || !ls || !hs || !cmpShift) return setCmpError("Revisa las listas: solo números positivos separados por espacios o punto y coma.");
    if (ns.length * ls.length * hs.length > 60) return setCmpError("Son demasiadas combinaciones (máximo 60). Reduce las listas.");
    setCmpReq({ n_values: ns, limit_widths: ls, sampling_intervals: hs, shift: cmpShift });
  }

  return (
    <>
      <title>{`Diseño · ${study.name} · CEP`}</title>
      <PageHeader
        title="Diseño de gráficos de control"
        subtitle="Módulo 6. Evalúa qué tan rápido detecta un gráfico un cambio (ARL1, ATS) frente a cuántas falsas alarmas da (ARL0), según el tamaño de muestra n, el ancho de límites L y el intervalo h."
      />
      <div className="flex flex-col gap-8">
        <section aria-labelledby="arl-h" className="flex flex-col gap-4">
          <h2 id="arl-h" className="text-lg font-semibold">ARL0, ARL1 y ATS de un diseño</h2>
          <Card title="Parámetros del diseño">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <SelectField label="Tipo de gráfico" value={chart} onChange={(e) => setChart(e.target.value as S["ArlRequest"]["chart"])}>
                {CHARTS.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
              </SelectField>
              <NumberField label="Tamaño de muestra n" value={usesN ? n : 1} onChange={setN} disabled={!usesN} />
              <NumberField label="Ancho de límites L (sigmas)" value={L} onChange={setL} />
              <NumberField label="Intervalo de muestreo h (horas)" value={h} onChange={setH} />
              {chart === "p" && <NumberField label="p0 (fracción defectuosa en control)" value={p0} onChange={setP0} />}
              {chart === "c" && <NumberField label="c0 (defectos en control)" value={c0} onChange={setC0} />}
              <TextField className="sm:col-span-2" label={shiftLabel} value={shifts} onChange={(e) => setShifts(e.target.value)} hint="Separa con espacios o punto y coma. Se usa el punto como decimal." />
            </div>
            <div className="mt-4">
              <RuleSelector value={rules.includes("WE1") ? rules : ["WE1", ...rules]} onChange={setRules} />
              <p className="mt-2 text-xs text-muted">Con reglas adicionales (solo X-barra e individuales) la API simula el ARL; con la regla 1 sola lo calcula de forma exacta.</p>
            </div>
            {rules.some((r) => r !== "WE1" && r !== "N1") && (
              <div className="mt-3 max-w-xs">
                <NumberField label="Corridas de simulación" value={runs} onChange={setRuns} hint="Más corridas, menor error y más tiempo." />
              </div>
            )}
            {formError && <Alert tone="error" className="mt-3">{formError}</Alert>}
            <div className="mt-4">
              <Button variant="primary" onClick={submitArl} loading={arl.loading && !!arlReq}>Calcular</Button>
            </div>
          </Card>

          {!arlReq && <EmptyState title="Aún no hay resultados">Define el diseño y pulsa «Calcular».</EmptyState>}
          {arlReq && arl.loading && !a && <Loading label="Calculando…" />}
          {arl.error && <Alert tone="error" title="La API no pudo calcular el diseño">{arl.error}</Alert>}
          {a && arlReq && (
            <>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {[
                  ["ARL0", fmtNum(a.arl0, 1), a.arl0_std_error != null ? `muestras entre falsas alarmas (± ${fmtNum(a.arl0_std_error, 1)} error estándar)` : "muestras entre falsas alarmas"],
                  ["ATS0", `${fmtNum(a.ats0, 1)} h`, "tiempo entre falsas alarmas"],
                  ["Carga muestral", `${fmtNum(a.sampling_load, 2)} u/h`, "n / h"],
                  ["Método", a.method === "exact" ? "Exacto" : "Simulación", a.alpha != null ? `α = ${fmtNum(a.alpha, 5)}` : "sin α exacto"],
                ].map(([k, v, s]) => (
                  <Card key={k}>
                    <p className="text-xs text-muted">{k}</p>
                    <p className="num text-2xl font-semibold">{v}</p>
                    <p className="text-xs text-muted">{s}</p>
                  </Card>
                ))}
              </div>
              <Card title={`Desempeño ante cambios (${a.method === "exact" ? "cálculo exacto" : "simulación"})`}>
                <Table caption="ARL1 y ATS1 por desplazamiento">
                  <thead>
                    <tr>
                      <Th>{arlReq.chart === "p" ? "p1" : arlReq.chart === "c" ? "c1" : "Desplazamiento δ (σ)"}</Th>
                      <Th>β (no detectar)</Th>
                      <Th>ARL1</Th>
                      <Th>ATS1 (h)</Th>
                      <Th>Unidades hasta detectar</Th>
                      {a.method === "simulation" && <Th>Error estándar</Th>}
                    </tr>
                  </thead>
                  <tbody>
                    {a.rows.map((r) => (
                      <tr key={r.shift}>
                        <Td className="font-medium">{fmtNum(r.shift, 3)}</Td>
                        <Td>{fmtNum(r.beta, 4)}</Td>
                        <Td>{fmtNum(r.arl1, 2)}</Td>
                        <Td>{fmtNum(r.ats1, 2)}</Td>
                        <Td>{fmtNum(r.units_to_detect, 1)}</Td>
                        {a.method === "simulation" && <Td>{fmtNum(r.std_error, 2)}</Td>}
                      </tr>
                    ))}
                  </tbody>
                </Table>
              </Card>
              <div className="grid gap-4 lg:grid-cols-2">
                <CurveChart
                  title="Curva característica de operación (OC)"
                  fileName={`${study.name}-curva-oc-diseno`}
                  series={[{ name: "β (prob. de no detectar)", points: a.oc_curve }]}
                  xTitle={arlReq.chart === "p" ? "p" : arlReq.chart === "c" ? "c" : "Desplazamiento δ (σ)"}
                  yTitle="β"
                  yRange={[0, 1.02]}
                />
                <CurveChart
                  title="ARL según el tamaño del cambio"
                  fileName={`${study.name}-curva-arl`}
                  series={[{ name: "ARL", points: a.arl_curve }]}
                  xTitle={arlReq.chart === "p" ? "p" : arlReq.chart === "c" ? "c" : "Desplazamiento δ (σ)"}
                  yTitle="ARL (muestras)"
                  logY
                />
              </div>
              <InterpretationBlock interpretation={a.interpretation} />
              <SaveAnalysis
                studyId={study.id}
                module="design"
                defaultTitle={`ARL/ATS · ${CHARTS.find((x) => x[0] === arlReq.chart)?.[1]} · n=${arlReq.n}, L=${numEs(arlReq.limit_width)}, h=${numEs(arlReq.sampling_interval)}`}
                params={arlReq as unknown as Record<string, unknown>}
                result={a as unknown as Record<string, unknown>}
              />
            </>
          )}
        </section>

        <section aria-labelledby="cmp-h" className="flex flex-col gap-4">
          <h2 id="cmp-h" className="text-lg font-semibold">Comparador de diseños</h2>
          <Card title="Alternativas a comparar (gráfico X-barra)">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <TextField label="Tamaños de muestra n" value={cmpN} onChange={(e) => setCmpN(e.target.value)} />
              <TextField label="Anchos L" value={cmpL} onChange={(e) => setCmpL(e.target.value)} />
              <TextField label="Intervalos h (horas)" value={cmpH} onChange={(e) => setCmpH(e.target.value)} />
              <NumberField label="Desplazamiento a detectar (σ)" value={cmpShift} onChange={setCmpShift} />
            </div>
            {cmpError && <Alert tone="error" className="mt-3">{cmpError}</Alert>}
            <div className="mt-4">
              <Button variant="primary" onClick={submitCmp} loading={cmp.loading && !!cmpReq}>Comparar</Button>
            </div>
          </Card>
          {!cmpReq && <EmptyState title="Sin comparación todavía">Define las listas y pulsa «Comparar».</EmptyState>}
          {cmpReq && cmp.loading && !c && <Loading label="Comparando…" />}
          {cmp.error && <Alert tone="error" title="La API no pudo comparar los diseños">{cmp.error}</Alert>}
          {c && cmpReq && (
            <>
              <Card title={`Diseños para detectar un desplazamiento de ${fmtNum(c.shift, 2)} σ`}>
                <Table caption="Comparación de diseños">
                  <thead>
                    <tr><Th>n</Th><Th>L</Th><Th>h (h)</Th><Th>ARL0</Th><Th>ATS0 (h)</Th><Th>ARL1</Th><Th>ATS1 (h)</Th><Th>Carga muestral (u/h)</Th></tr>
                  </thead>
                  <tbody>
                    {c.rows.map((r, i) => (
                      <tr key={i}>
                        <Td className="font-medium">{r.n}</Td>
                        <Td>{fmtNum(r.limit_width, 2)}</Td>
                        <Td>{fmtNum(r.sampling_interval, 2)}</Td>
                        <Td>{fmtNum(r.arl0, 1)}</Td>
                        <Td>{fmtNum(r.ats0, 1)}</Td>
                        <Td>{fmtNum(r.arl1, 2)}</Td>
                        <Td>{fmtNum(r.ats1, 2)}</Td>
                        <Td><Badge tone="neutral">{fmtNum(r.sampling_load, 2)}</Badge></Td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              </Card>
              <TradeoffChart rows={c.rows} title="Detección frente a carga de inspección" fileName={`${study.name}-comparador`} />
              <InterpretationBlock interpretation={c.interpretation} />
              <SaveAnalysis
                studyId={study.id}
                module="design"
                defaultTitle={`Comparación de diseños para δ = ${numEs(cmpReq.shift)} σ`}
                params={cmpReq as unknown as Record<string, unknown>}
                result={c as unknown as Record<string, unknown>}
              />
            </>
          )}
        </section>
      </div>
    </>
  );
}
