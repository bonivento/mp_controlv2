"use client";

import { useState } from "react";
import { InterpretationBlock } from "@/components/analysis-parts";
import { CurveChart } from "@/components/charts/StatCharts";
import { useStudy } from "@/components/study-context";
import { Alert, Badge, Button, Card, ConfirmDialog, EmptyState, Loading, NumberField, PageHeader, SelectField, Table, Td, TextField, Th, errMsg, fmtNum } from "@/components/ui";
import { api } from "@/lib/api";
import type { components } from "@/lib/api-types";
import { getStore } from "@/lib/data";
import type { SamplingPlan } from "@/lib/db-provisional";
import { useLoad } from "@/lib/use-load";

type S = components["schemas"];
type Dist = S["SingleDesignRequest"]["distribution"];

const DIST = [
  ["binomial", "Binomial (lote grande)"],
  ["poisson", "Poisson (aproximación, p pequeña)"],
  ["hypergeometric", "Hipergeométrica (lote finito, exige N)"],
] as const;

const pct = (x: number | null | undefined, d = 2) => (x == null ? "—" : `${fmtNum(x * 100, d)} %`);

/** Guarda el plan en `sampling_plans` y el análisis en `analyses` (fuente del reporte). */
function SavePlan({ studyId, planType, defaultName, params, result, onSaved }: {
  studyId: string;
  planType: "single" | "double";
  defaultName: string;
  params: Record<string, unknown>;
  result: Record<string, unknown>;
  onSaved: () => void;
}) {
  const [name, setName] = useState(defaultName);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ tone: "ok" | "error"; text: string } | null>(null);
  async function save() {
    if (!name.trim()) return setMsg({ tone: "error", text: "Escribe un nombre para el plan." });
    setBusy(true);
    try {
      const s = getStore();
      await s.samplingPlans.create({ study_id: studyId, name: name.trim(), plan_type: planType, params, result });
      await s.analyses.create({ study_id: studyId, dataset_id: null, module: "sampling", title: name.trim(), params, result, in_report: true });
      setMsg({ tone: "ok", text: `Plan «${name.trim()}» guardado y añadido al reporte.` });
      onSaved();
    } catch (e) {
      setMsg({ tone: "error", text: errMsg(e) });
    } finally {
      setBusy(false);
    }
  }
  return (
    <Card title="Guardar plan" className="no-print">
      <div className="grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end">
        <TextField label="Nombre del plan" value={name} onChange={(e) => setName(e.target.value)} />
        <Button variant="primary" loading={busy} onClick={save}>Guardar plan y análisis</Button>
      </div>
      {msg && <Alert tone={msg.tone} className="mt-3">{msg.text}</Alert>}
    </Card>
  );
}

function SingleResult({ r, aql, ltpd, name }: { r: S["SinglePlanResponse"]; aql?: number | null; ltpd?: number | null; name: string }) {
  const v = [aql != null ? { x: aql, label: "AQL" } : null, ltpd != null ? { x: ltpd, label: "LTPD" } : null].filter(Boolean) as { x: number; label: string }[];
  return (
    <>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {[
          ["Tamaño de muestra n", String(r.n)],
          ["Número de aceptación c", String(r.c)],
          ["Riesgo del productor α real", pct(r.alpha_actual, 2)],
          ["Riesgo del consumidor β real", pct(r.beta_actual, 2)],
          ["AOQL", `${pct(r.aoql, 3)} en p = ${pct(r.aoql_at, 2)}`],
        ].map(([k, val]) => (
          <Card key={k}><p className="text-xs text-muted">{k}</p><p className="num text-xl font-semibold">{val}</p></Card>
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <CurveChart title="Curva OC: probabilidad de aceptar el lote" fileName={`${name}-oc`} series={[{ name: "Pa", points: r.oc_curve }]} xTitle="Fracción defectuosa del lote (p)" yTitle="Probabilidad de aceptación (Pa)" yRange={[0, 1.02]} vlines={v} />
        <CurveChart title="Calidad promedio de salida (AOQ)" fileName={`${name}-aoq`} series={[{ name: "AOQ", points: r.aoq_curve }]} xTitle="Fracción defectuosa de entrada (p)" yTitle="AOQ" vlines={v} />
      </div>
      {r.ati_curve ? (
        <CurveChart title="Inspección total promedio (ATI)" fileName={`${name}-ati`} series={[{ name: "ATI", points: r.ati_curve }]} xTitle="Fracción defectuosa del lote (p)" yTitle="Unidades inspeccionadas por lote" />
      ) : (
        <Alert tone="info">Indica el tamaño del lote (N) para ver la inspección total promedio (ATI).</Alert>
      )}
      <InterpretationBlock interpretation={r.interpretation} />
    </>
  );
}

function SingleDesign({ studyId, onSaved }: { studyId: string; onSaved: () => void }) {
  const [aql, setAql] = useState<number | null>(0.01);
  const [alpha, setAlpha] = useState<number | null>(0.05);
  const [ltpd, setLtpd] = useState<number | null>(0.06);
  const [beta, setBeta] = useState<number | null>(0.1);
  const [lot, setLot] = useState<number | null>(2000);
  const [dist, setDist] = useState<Dist>("binomial");
  const [req, setReq] = useState<S["SingleDesignRequest"] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const res = useLoad(async () => (req ? api.singleDesign(req) : null), [req ? JSON.stringify(req) : ""]);
  const r = req ? res.data : null;
  function run() {
    setErr(null);
    if (!aql || !ltpd || !alpha || !beta) return setErr("AQL, LTPD, α y β son obligatorios.");
    if (aql >= ltpd) return setErr("El AQL debe ser menor que el LTPD.");
    if (dist === "hypergeometric" && !lot) return setErr("La distribución hipergeométrica necesita el tamaño del lote.");
    setReq({ aql, alpha, ltpd, beta, lot_size: lot, distribution: dist });
  }
  return (
    <div className="flex flex-col gap-4">
      <Card title="Requisitos del plan">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <NumberField label="AQL (fracción defectuosa aceptable)" value={aql} onChange={setAql} hint="Ej.: 0,01 = 1 %." />
          <NumberField label="α (riesgo del productor)" value={alpha} onChange={setAlpha} hint="Prob. de rechazar un lote con calidad AQL." />
          <NumberField label="LTPD (fracción defectuosa límite)" value={ltpd} onChange={setLtpd} hint="Ej.: 0,06 = 6 %." />
          <NumberField label="β (riesgo del consumidor)" value={beta} onChange={setBeta} hint="Prob. de aceptar un lote con calidad LTPD." />
          <NumberField label="Tamaño del lote N (opcional)" value={lot} onChange={setLot} hint="Necesario para ATI y la hipergeométrica." />
          <SelectField label="Distribución" value={dist} onChange={(e) => setDist(e.target.value as Dist)}>
            {DIST.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
          </SelectField>
        </div>
        {err && <Alert tone="error" className="mt-3">{err}</Alert>}
        <div className="mt-4"><Button variant="primary" onClick={run} loading={res.loading && !!req}>Diseñar plan</Button></div>
      </Card>
      {!req && <EmptyState title="Sin plan todavía">Indica AQL, LTPD y los riesgos, y pulsa «Diseñar plan».</EmptyState>}
      {req && res.loading && !r && <Loading label="Buscando el plan…" />}
      {res.error && <Alert tone="error" title="La API no pudo diseñar el plan">{res.error}</Alert>}
      {r && req && (
        <>
          <SingleResult r={r} aql={req.aql} ltpd={req.ltpd} name="plan-simple" />
          <SavePlan studyId={studyId} planType="single" defaultName={`Plan simple n=${r.n}, c=${r.c} (AQL ${req.aql}, LTPD ${req.ltpd})`} params={req as unknown as Record<string, unknown>} result={r as unknown as Record<string, unknown>} onSaved={onSaved} />
        </>
      )}
    </div>
  );
}

function SingleEvaluate({ studyId, onSaved }: { studyId: string; onSaved: () => void }) {
  const [n, setN] = useState<number | null>(80);
  const [c, setC] = useState<number | null>(2);
  const [lot, setLot] = useState<number | null>(2000);
  const [dist, setDist] = useState<Dist>("binomial");
  const [aql, setAql] = useState<number | null>(0.01);
  const [ltpd, setLtpd] = useState<number | null>(0.06);
  const [req, setReq] = useState<S["SingleEvaluateRequest"] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const res = useLoad(async () => (req ? api.singleEvaluate(req) : null), [req ? JSON.stringify(req) : ""]);
  const r = req ? res.data : null;
  function run() {
    setErr(null);
    if (!n || n < 1 || c == null || c < 0) return setErr("n debe ser positivo y c no puede ser negativo.");
    if (c >= n) return setErr("c debe ser menor que n.");
    if (dist === "hypergeometric" && !lot) return setErr("La distribución hipergeométrica necesita el tamaño del lote.");
    setReq({ n, c, lot_size: lot, distribution: dist, aql, ltpd });
  }
  return (
    <div className="flex flex-col gap-4">
      <Card title="Plan existente">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <NumberField label="n (tamaño de muestra)" value={n} onChange={setN} />
          <NumberField label="c (número de aceptación)" value={c} onChange={setC} />
          <NumberField label="Tamaño del lote N (opcional)" value={lot} onChange={setLot} />
          <SelectField label="Distribución" value={dist} onChange={(e) => setDist(e.target.value as Dist)}>
            {DIST.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
          </SelectField>
          <NumberField label="AQL (opcional)" value={aql} onChange={setAql} hint="Para calcular α real." />
          <NumberField label="LTPD (opcional)" value={ltpd} onChange={setLtpd} hint="Para calcular β real." />
        </div>
        {err && <Alert tone="error" className="mt-3">{err}</Alert>}
        <div className="mt-4"><Button variant="primary" onClick={run} loading={res.loading && !!req}>Evaluar plan</Button></div>
      </Card>
      {!req && <EmptyState title="Sin evaluación todavía">Escribe n y c y pulsa «Evaluar plan».</EmptyState>}
      {req && res.loading && !r && <Loading label="Evaluando…" />}
      {res.error && <Alert tone="error" title="La API no pudo evaluar el plan">{res.error}</Alert>}
      {r && req && (
        <>
          <SingleResult r={r} aql={req.aql} ltpd={req.ltpd} name="plan-simple-eval" />
          <SavePlan studyId={studyId} planType="single" defaultName={`Evaluación plan simple n=${r.n}, c=${r.c}`} params={req as unknown as Record<string, unknown>} result={r as unknown as Record<string, unknown>} onSaved={onSaved} />
        </>
      )}
    </div>
  );
}

function DoubleEvaluate({ studyId, onSaved }: { studyId: string; onSaved: () => void }) {
  const [n1, setN1] = useState<number | null>(50);
  const [c1, setC1] = useState<number | null>(1);
  const [r1, setR1] = useState<number | null>(4);
  const [n2, setN2] = useState<number | null>(100);
  const [c2, setC2] = useState<number | null>(4);
  const [lot, setLot] = useState<number | null>(2000);
  const [aql, setAql] = useState<number | null>(0.01);
  const [ltpd, setLtpd] = useState<number | null>(0.06);
  const [req, setReq] = useState<S["DoubleEvaluateRequest"] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const res = useLoad(async () => (req ? api.doubleEvaluate(req) : null), [req ? JSON.stringify(req) : ""]);
  const r = req ? res.data : null;
  function run() {
    setErr(null);
    if (!n1 || !n2 || c1 == null || c2 == null || r1 == null) return setErr("Completa n1, c1, r1, n2 y c2.");
    if (c2 < c1) return setErr("c2 no puede ser menor que c1.");
    if (r1 <= c1) return setErr("r1 debe ser mayor que c1.");
    setReq({ n1, c1, r1, n2, c2, lot_size: lot, aql, ltpd });
  }
  const v = req ? [req.aql != null ? { x: req.aql, label: "AQL" } : null, req.ltpd != null ? { x: req.ltpd, label: "LTPD" } : null].filter(Boolean) as { x: number; label: string }[] : [];
  return (
    <div className="flex flex-col gap-4">
      <Card title="Plan doble">
        <p className="mb-3 text-sm text-muted">Se acepta con la primera muestra si d1 ≤ c1 y se rechaza si d1 ≥ r1; en otro caso se toma la segunda y se acepta si d1 + d2 ≤ c2.</p>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <NumberField label="n1 (primera muestra)" value={n1} onChange={setN1} />
          <NumberField label="c1 (aceptación 1)" value={c1} onChange={setC1} />
          <NumberField label="r1 (rechazo 1)" value={r1} onChange={setR1} />
          <NumberField label="n2 (segunda muestra)" value={n2} onChange={setN2} />
          <NumberField label="c2 (aceptación acumulada)" value={c2} onChange={setC2} />
          <NumberField label="Tamaño del lote N (opcional)" value={lot} onChange={setLot} />
          <NumberField label="AQL (opcional)" value={aql} onChange={setAql} />
          <NumberField label="LTPD (opcional)" value={ltpd} onChange={setLtpd} />
        </div>
        {err && <Alert tone="error" className="mt-3">{err}</Alert>}
        <div className="mt-4"><Button variant="primary" onClick={run} loading={res.loading && !!req}>Evaluar plan doble</Button></div>
      </Card>
      {!req && <EmptyState title="Sin evaluación todavía">Define el plan y pulsa «Evaluar plan doble».</EmptyState>}
      {req && res.loading && !r && <Loading label="Evaluando…" />}
      {res.error && <Alert tone="error" title="La API no pudo evaluar el plan">{res.error}</Alert>}
      {r && req && (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            {[["α real", pct(r.alpha_actual)], ["β real", pct(r.beta_actual)], ["AOQL", pct(r.aoql, 3)]].map(([k, val]) => (
              <Card key={k}><p className="text-xs text-muted">{k}</p><p className="num text-xl font-semibold">{val}</p></Card>
            ))}
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <CurveChart
              title="Curva OC del plan doble"
              fileName="plan-doble-oc"
              series={[{ name: "Pa total", points: r.oc_curve }, { name: "Aceptar con la 1.ª muestra", points: r.first_sample_accept_curve, dash: "dash" }]}
              xTitle="Fracción defectuosa del lote (p)"
              yTitle="Probabilidad de aceptación"
              yRange={[0, 1.02]}
              vlines={v}
            />
            <CurveChart title="Tamaño de muestra promedio (ASN)" fileName="plan-doble-asn" series={[{ name: "ASN", points: r.asn_curve }]} xTitle="Fracción defectuosa del lote (p)" yTitle="Unidades inspeccionadas por lote" vlines={v} />
            <CurveChart title="Calidad promedio de salida (AOQ)" fileName="plan-doble-aoq" series={[{ name: "AOQ", points: r.aoq_curve }]} xTitle="Fracción defectuosa de entrada (p)" yTitle="AOQ" vlines={v} />
            {r.ati_curve ? (
              <CurveChart title="Inspección total promedio (ATI)" fileName="plan-doble-ati" series={[{ name: "ATI", points: r.ati_curve }]} xTitle="Fracción defectuosa del lote (p)" yTitle="Unidades inspeccionadas por lote" />
            ) : (
              <Alert tone="info">Indica el tamaño del lote (N) para ver la ATI.</Alert>
            )}
          </div>
          <InterpretationBlock interpretation={r.interpretation} />
          <SavePlan studyId={studyId} planType="double" defaultName={`Plan doble n1=${req.n1}, c1=${req.c1}, r1=${req.r1}, n2=${req.n2}, c2=${req.c2}`} params={req as unknown as Record<string, unknown>} result={r as unknown as Record<string, unknown>} onSaved={onSaved} />
        </>
      )}
    </div>
  );
}

export default function SamplingPage() {
  const { study } = useStudy();
  const [tab, setTab] = useState<"design" | "eval" | "double">("design");
  const plans = useLoad(() => getStore().samplingPlans.list(study.id), [study.id]);
  const [toDelete, setToDelete] = useState<SamplingPlan | null>(null);
  const [busy, setBusy] = useState(false);
  const tabs = [
    ["design", "Diseñar plan simple"],
    ["eval", "Evaluar plan simple"],
    ["double", "Evaluar plan doble"],
  ] as const;
  return (
    <>
      <title>{`Muestreo · ${study.name} · CEP`}</title>
      <PageHeader
        title="Muestreo de aceptación"
        subtitle="Módulo 7. Decide si aceptar o rechazar un lote a partir de una muestra. Diseña un plan por atributos o evalúa uno que ya tengas; la curva OC muestra qué tan bien discrimina."
      />
      <div role="tablist" aria-label="Tipo de plan" className="mb-4 grid max-w-3xl grid-cols-3 gap-1 rounded-md bg-surface-2 p-1">
        {tabs.map(([k, t]) => (
          <button key={k} type="button" role="tab" aria-selected={tab === k} onClick={() => setTab(k)} className={`min-h-10 rounded px-2 text-sm font-medium ${tab === k ? "bg-brand text-brand-ink shadow-sm" : "text-muted hover:text-ink"}`}>
            {t}
          </button>
        ))}
      </div>
      {tab === "design" && <SingleDesign studyId={study.id} onSaved={plans.reload} />}
      {tab === "eval" && <SingleEvaluate studyId={study.id} onSaved={plans.reload} />}
      {tab === "double" && <DoubleEvaluate studyId={study.id} onSaved={plans.reload} />}

      <h2 className="mb-3 mt-10 text-lg font-semibold">Planes guardados</h2>
      {plans.loading && !plans.data && <Loading />}
      {plans.error && <Alert tone="error">{plans.error}</Alert>}
      {plans.data && plans.data.length === 0 && <EmptyState title="Aún no hay planes guardados" />}
      {plans.data && plans.data.length > 0 && (
        <Table caption="Planes de muestreo guardados">
          <thead><tr><Th>Nombre</Th><Th>Tipo</Th><Th>Guardado</Th><Th>Acciones</Th></tr></thead>
          <tbody>
            {plans.data.map((p) => (
              <tr key={p.id}>
                <Td className="font-medium">{p.name}</Td>
                <Td><Badge tone="info">{p.plan_type === "single" ? "Simple" : "Doble"}</Badge></Td>
                <Td>{new Date(p.created_at).toLocaleString("es-CO", { dateStyle: "medium", timeStyle: "short" })}</Td>
                <Td><Button variant="ghost" onClick={() => setToDelete(p)} aria-label={`Eliminar ${p.name}`}>Eliminar</Button></Td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
      <ConfirmDialog
        open={!!toDelete}
        title="Eliminar plan"
        busy={busy}
        onCancel={() => setToDelete(null)}
        onConfirm={async () => {
          if (!toDelete) return;
          setBusy(true);
          try {
            await getStore().samplingPlans.remove(toDelete.id);
            setToDelete(null);
            plans.reload();
          } finally {
            setBusy(false);
          }
        }}
        message={<>Se eliminará el plan <strong className="text-ink">{toDelete?.name}</strong>. El análisis ya guardado para el reporte no se borra.</>}
      />
    </>
  );
}
