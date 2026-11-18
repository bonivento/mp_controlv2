"use client";

import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api";
import type { components } from "@/lib/api-types";
import { getStore } from "@/lib/data";
import {
  attributeArrays,
  isAttributeDataset,
  isVariableDataset,
  sizeIssueList,
  sizeIssues,
  variableSubgroups,
} from "@/lib/dataset-utils";
import { isVariableRow, type ChartType, type Dataset, type Phase } from "@/lib/db";
import { CHART_TYPE_LABEL, PARAM_LABEL } from "@/lib/labels";
import { useLoad } from "@/lib/use-load";
import { DatasetSelect, InterpretationBlock, RuleSelector, SaveAnalysis } from "../analysis-parts";
import { useAssistantScreen } from "../assistant/assistant-provider";
import { useStudy } from "../study-context";
import { Alert, Badge, Button, Card, EmptyState, Loading, Modal, NumberField, PageHeader, SelectField, Table, Td, TextAreaField, Th, errMsg, fmtNum } from "../ui";
import type { ReactNode } from "react";
import { ControlChart } from "./ControlChart";

type S = components["schemas"];
type RuleId = NonNullable<S["RuleConfig"]["enabled"]>[number];
type Kind = "variables" | "attributes";

const TYPE_LABEL = CHART_TYPE_LABEL;

const fmtDate = (s: string) => new Date(s).toLocaleString("es-CO", { dateStyle: "medium", timeStyle: "short" });

export function ChartWorkbench({ kind }: { kind: Kind }) {
  const { study } = useStudy();
  const isVar = kind === "variables";
  const types: ChartType[] = isVar ? ["xbar_r", "xbar_s", "i_mr"] : ["p", "np", "c", "u"];

  const [phase, setPhase] = useState<Phase>("I");
  const [datasetId, setDatasetId] = useState("");
  const [typeState, setTypeState] = useState<ChartType | null>(null);
  const [limitWidth, setLimitWidth] = useState<number | null>(3);
  const [rules, setRules] = useState<RuleId[]>(["WE1"]);
  const [excluded, setExcluded] = useState<S["ExcludedPoint"][]>([]);
  const [pending, setPending] = useState<number | null>(null);
  const [cause, setCause] = useState("");
  const [causeError, setCauseError] = useState<string | null>(null);
  const [freezeOpen, setFreezeOpen] = useState(false);
  const [freezing, setFreezing] = useState(false);
  const [freezeMsg, setFreezeMsg] = useState<{ tone: "ok" | "error"; text: string } | null>(null);

  const base = useLoad(async () => {
    const s = getStore();
    const [datasets, limits] = await Promise.all([s.datasets.list(study.id), s.controlLimits.listActive(study.id)]);
    return { datasets: datasets.filter((d) => (isVar ? isVariableDataset(d) : isAttributeDataset(d))), limits };
  }, [study.id, kind]);

  const pool = (base.data?.datasets ?? []).filter((d) => d.phase === phase);
  const dataset: Dataset | undefined = pool.find((d) => d.id === datasetId) ?? pool[0];
  const defaultType: ChartType = isVar
    ? dataset && variableSubgroups(dataset).subgroups.every((s) => s.length === 1)
      ? "i_mr"
      : "xbar_r"
    : "p";
  const chartType = typeState ?? defaultType;
  const frozen = base.data?.limits.find((l) => l.chart_type === chartType) ?? null;
  const L = limitWidth ?? 3;
  const enabled = rules.includes("WE1") ? rules : (["WE1", ...rules] as RuleId[]);

  // Petición a la API, o el motivo por el que todavía no se puede hacer.
  let request: { kind: Kind; body: S["VariablesChartRequest"] | S["AttributesChartRequest"] } | null = null;
  let blocker: ReactNode = null;
  if (dataset) {
    if (phase === "II" && !frozen) blocker = "no-limits";
    else if (isVar) {
      const { subgroups, labels } = variableSubgroups(dataset);
      const sizes = new Set(subgroups.map((s) => s.length));
      if (chartType === "i_mr" && !(sizes.size === 1 && sizes.has(1)))
        blocker = "Este conjunto tiene más de una observación por subgrupo. El gráfico I-MR necesita observaciones individuales: elige X-barra y R o X-barra y S.";
      else if (chartType !== "i_mr" && (sizes.size !== 1 || sizes.has(1)))
        blocker = sizes.has(1) && sizes.size === 1
          ? "Este conjunto son observaciones individuales (n = 1): usa el gráfico I-MR."
          : (() => {
              const issue = sizeIssues(dataset.rows.filter(isVariableRow));
              return (
                <>
                  X-barra necesita subgrupos del mismo tamaño.
                  {issue && (
                    <>
                      {" "}El tamaño predominante es n = {issue.predominant} y tienen otro tamaño los subgrupos: {sizeIssueList(issue)}.
                    </>
                  )}{" "}
                  Retira esos subgrupos al cargar el archivo en{" "}
                  <Link className="font-medium underline" href={`/estudios/${study.id}/datos`}>Datos</Link>{" "}
                  (sección «Subgrupos incompletos»; un conjunto ya guardado no se modifica: elimínalo y vuelve a cargarlo) o elige otro gráfico.
                </>
              );
            })();
      else
        request = {
          kind,
          body: {
            chart_type: chartType as S["VariablesChartRequest"]["chart_type"],
            phase,
            subgroups,
            labels,
            excluded: phase === "I" ? excluded : [],
            limits: phase === "II" ? frozen!.limits : null,
            limit_width: L,
            rules: { enabled },
          },
        };
    } else {
      const { counts, sizes, labels } = attributeArrays(dataset);
      if (chartType === "np" && new Set(sizes).size !== 1)
        blocker = "El gráfico np exige tamaño de muestra constante. Este conjunto tiene tamaños variables: usa p.";
      else
        request = {
          kind,
          body: {
            chart_type: chartType as S["AttributesChartRequest"]["chart_type"],
            phase,
            counts,
            sizes: chartType === "c" ? null : sizes,
            labels,
            excluded: phase === "I" ? excluded : [],
            limits: phase === "II" ? frozen!.limits : null,
            limit_width: L,
            rules: { enabled },
          },
        };
    }
  }

  const calc = useLoad(
    async () => {
      if (!request) return null;
      return isVar
        ? api.variablesChart(request.body as S["VariablesChartRequest"])
        : api.attributesChart(request.body as S["AttributesChartRequest"]);
    },
    [dataset?.id, chartType, phase, L, enabled.join(","), JSON.stringify(excluded), frozen?.id, request ? 1 : 0],
  );

  const result = request ? calc.data : null;
  const labelOf = (i: number) => result?.charts[0]?.labels[i] ?? String(i + 1);

  function resetFor(nextPhase: Phase | null = null) {
    setExcluded([]);
    setFreezeMsg(null);
    if (nextPhase) {
      setPhase(nextPhase);
      setDatasetId("");
    }
  }

  function askExclude(i: number) {
    setPending(i);
    setCause("");
    setCauseError(null);
  }
  function confirmExclude() {
    if (pending == null) return;
    if (cause.trim().length < 3) {
      setCauseError("La causa asignable es obligatoria: describe qué pasó (p. ej. cambio de lote de materia prima).");
      return;
    }
    setExcluded((p) => [...p.filter((e) => e.index !== pending), { index: pending, label: labelOf(pending), cause: cause.trim() }]);
    setPending(null);
  }

  async function freeze() {
    if (!result || !dataset) return;
    setFreezing(true);
    try {
      await getStore().controlLimits.freeze({
        study_id: study.id,
        dataset_id: dataset.id,
        chart_type: result.limits.chart_type,
        limits: result.limits,
      });
      setFreezeMsg({ tone: "ok", text: `Límites ${TYPE_LABEL[result.limits.chart_type]} congelados. Ya puedes pasar a la Fase II.` });
      setFreezeOpen(false);
      base.reload();
    } catch (e) {
      setFreezeMsg({ tone: "error", text: errMsg(e) });
      setFreezeOpen(false);
    } finally {
      setFreezing(false);
    }
  }

  // Señales por subgrupo para la tabla accesible.
  const signals = new Map<number, { rules: Set<string>; texts: string[] }>();
  result?.charts.forEach((c) =>
    c.violations.forEach((v) => {
      const s = signals.get(v.index) ?? { rules: new Set<string>(), texts: [] };
      s.rules.add(v.rule);
      if (!s.texts.includes(v.description)) s.texts.push(v.description);
      signals.set(v.index, s);
    }),
  );
  const exSet = new Set(excluded.map((e) => e.index));
  const clickable = phase === "I" ? [...signals.keys()].filter((i) => !exSet.has(i)) : [];
  const signalRows = [...signals.entries()].sort((a, b) => a[0] - b[0]);

  // Lo que el asistente ve: fase, gráfico, conjunto, reglas, exclusiones y, si ya se calculó, el resultado.
  useAssistantScreen({
    screen: kind,
    label: `${isVar ? "Variables" : "Atributos"} · Fase ${phase} · ${TYPE_LABEL[chartType]}`,
    hasResult: !!result,
    empty: !!base.data && base.data.datasets.length === 0,
    view: {
      fase: phase === "I" ? "Fase I (límites de prueba, se recalculan al excluir)" : "Fase II (límites congelados, no se recalculan)",
      grafico: chartType,
      conjunto_de_datos: dataset ? { name: dataset.name, phase: dataset.phase, n_subgroups: dataset.rows.length } : null,
      ancho_de_limites_L: L,
      reglas_activas: enabled,
      puntos_excluidos_con_causa: phase === "I" ? excluded : [],
      limites_congelados_vigentes: frozen ? { created_at: frozen.created_at, limits: frozen.limits } : null,
      bloqueo:
        blocker === "no-limits"
          ? "Fase II sin límites congelados para este gráfico"
          : typeof blocker === "string"
            ? blocker
            : blocker
              ? "X-barra necesita subgrupos del mismo tamaño y este conjunto tiene subgrupos de otro tamaño"
              : null,
      resultado: result ?? null,
    },
  });

  const phaseTabs = (
    <div role="tablist" aria-label="Fase del análisis" className="grid max-w-xl grid-cols-2 gap-1 rounded-md bg-surface-2 p-1">
      {(["I", "II"] as const).map((p) => (
        <button
          key={p}
          type="button"
          role="tab"
          aria-selected={phase === p}
          onClick={() => resetFor(p)}
          className={`min-h-10 rounded border-b-[3px] px-3 text-sm font-medium ${phase === p ? "border-accent bg-brand text-brand-ink shadow-sm" : "border-transparent text-muted hover:text-ink"}`}
        >
          {p === "I" ? "Fase I · estimar y congelar límites" : "Fase II · monitorear"}
        </button>
      ))}
    </div>
  );

  return (
    <>
      <title>{`${isVar ? "Variables" : "Atributos"} · ${study.name} · Sigmalena`}</title>
      <PageHeader
        title={isVar ? "Gráficos de control por variables" : "Gráficos de control por atributos"}
        subtitle={
          isVar
            ? "Módulo 2. En Fase I los límites son de prueba: investiga cada señal, exclúyela si hay causa asignable y congela los límites. En Fase II monitoreas datos nuevos contra los límites congelados."
            : "Módulo 3. Elige el gráfico con el asistente, estima los límites en Fase I, congélalos y monitorea en Fase II."
        }
      />
      {base.loading && !base.data && <Loading label="Cargando conjuntos de datos…" />}
      {base.error && <Alert tone="error" title="No se pudieron cargar los datos">{base.error}</Alert>}
      {base.data && base.data.datasets.length === 0 && (
        <EmptyState
          title="Primero carga datos"
          action={<Link href={`/estudios/${study.id}/datos`} className="rounded-md bg-brand px-4 py-2 text-sm font-medium text-brand-ink">Ir a Datos</Link>}
        >
          Este módulo necesita al menos un conjunto de datos {isVar ? "de variables" : "de atributos"} guardado.
        </EmptyState>
      )}

      {base.data && base.data.datasets.length > 0 && (
        <div className="flex flex-col gap-4">
          {phaseTabs}

          {phase === "I" ? (
            <Alert tone="info" title="FASE I — límites de prueba">
              Los límites se calculan con los datos y <strong>se recalculan</strong> cada vez que excluyes un punto. Cuando el proceso esté bajo control, congela los límites.
            </Alert>
          ) : (
            <Alert tone="ok" title={frozen ? `FASE II — límites congelados el ${fmtDate(frozen.created_at)}` : "FASE II — faltan límites congelados"}>
              {frozen ? (
                <>Los datos nuevos se comparan contra los límites de la Fase I. <strong>Los límites no se recalculan</strong>.</>
              ) : (
                <>Todavía no hay límites congelados para este tipo de gráfico. Congélalos primero en la Fase I.</>
              )}
            </Alert>
          )}

          {!isVar && <AttributeAssistant dataset={dataset} onUse={(t) => { setTypeState(t); resetFor(); }} />}

          <Card title="Configuración">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <DatasetSelect
                label={`Conjunto de datos de Fase ${phase}`}
                datasets={pool}
                value={dataset?.id ?? ""}
                onChange={(id) => { setDatasetId(id); setExcluded([]); setFreezeMsg(null); }}
              />
              <SelectField
                label="Tipo de gráfico"
                value={chartType}
                onChange={(e) => { setTypeState(e.target.value as ChartType); resetFor(); }}
              >
                {types.map((t) => <option key={t} value={t}>{TYPE_LABEL[t]}</option>)}
              </SelectField>
              <NumberField
                label="Ancho de los límites (L, en sigmas)"
                value={limitWidth}
                onChange={setLimitWidth}
                disabled={phase === "II"}
                hint={phase === "II" ? "En Fase II se usa el L congelado." : "3 es el valor habitual."}
              />
            </div>
            <div className="mt-4">
              <RuleSelector value={enabled} onChange={setRules} />
            </div>
          </Card>

          {pool.length === 0 && (
            <EmptyState title={`No hay conjuntos de Fase ${phase}`}>
              Guarda un conjunto como Fase {phase} en <Link className="underline" href={`/estudios/${study.id}/datos`}>Datos</Link>.
            </EmptyState>
          )}
          {blocker && blocker !== "no-limits" && <Alert tone="warn" title="Revisa la configuración">{blocker}</Alert>}
          {blocker === "no-limits" && (
            <EmptyState title="Sin límites congelados para este gráfico">
              Ve a la Fase I, trabaja el conjunto de entrenamiento y pulsa «Congelar límites» para el tipo {TYPE_LABEL[chartType]}.
            </EmptyState>
          )}

          {request && calc.loading && !result && <Loading label="Calculando gráfico…" />}
          {request && calc.error && <Alert tone="error" title="La API no pudo calcular el gráfico">{calc.error}</Alert>}

          {result && (
            <div className={`flex flex-col gap-4 transition-opacity ${calc.loading ? "opacity-60" : ""}`} aria-busy={calc.loading}>
              <div className="flex flex-wrap items-center gap-3">
                {result.in_control ? <Badge tone="ok">✓ Proceso bajo control</Badge> : <Badge tone="error">◆ {result.out_of_control_points.length} punto(s) con señal</Badge>}
                <Badge tone="neutral">{result.limits.points_used} subgrupos usados en los límites</Badge>
                {phase === "I" && <Badge tone="info">Límites de prueba</Badge>}
                {phase === "II" && <Badge tone="ok">Límites congelados</Badge>}
                {calc.loading && <span role="status" className="text-sm text-muted">Recalculando…</span>}
              </div>

              {result.charts.map((c) => (
                <ControlChart
                  key={`${c.name}-${phase}`}
                  series={c}
                  phase={phase}
                  clickableIndices={clickable}
                  onPointClick={phase === "I" ? askExclude : undefined}
                  fileName={`${study.name}-${c.name}-fase-${phase}`.replace(/\s+/g, "_")}
                />
              ))}
              {phase === "I" && clickable.length > 0 && (
                <p className="text-sm text-muted">Haz clic en un punto con señal (rombo) para excluirlo con su causa asignable, o usa la tabla de abajo.</p>
              )}

              <Card title="Parámetros del proceso">
                <dl className="grid gap-3 text-sm sm:grid-cols-3 lg:grid-cols-5">
                  {Object.entries(result.limits.params).map(([k, v]) => (
                    <div key={k}>
                      <dt className="text-xs text-muted">{PARAM_LABEL[k] ?? k}</dt>
                      <dd className="num font-medium">{fmtNum(v, 4)}</dd>
                    </div>
                  ))}
                  <div>
                    <dt className="text-xs text-muted">Ancho de límites (L)</dt>
                    <dd className="num font-medium">{fmtNum(result.limits.limit_width, 1)}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-muted">Subgrupos usados</dt>
                    <dd className="num font-medium">{result.limits.points_used}</dd>
                  </div>
                </dl>
              </Card>

              <Card title="Señales detectadas">
                {signalRows.length === 0 ? (
                  <p className="text-sm text-muted">Ningún punto activa las reglas elegidas.</p>
                ) : (
                  <Table caption="Puntos con señal">
                    <thead>
                      <tr>
                        <Th>Subgrupo</Th>
                        <Th>Reglas</Th>
                        <Th>Descripción</Th>
                        {phase === "I" && <Th>Acción</Th>}
                      </tr>
                    </thead>
                    <tbody>
                      {signalRows.map(([i, s]) => (
                        <tr key={i}>
                          <Td className="font-medium">{labelOf(i)}</Td>
                          <Td>{[...s.rules].join(", ")}</Td>
                          <Td>{s.texts.join(" · ")}</Td>
                          {phase === "I" && (
                            <Td>
                              {exSet.has(i) ? <Badge tone="neutral">Excluido</Badge> : <Button onClick={() => askExclude(i)}>Excluir con causa…</Button>}
                            </Td>
                          )}
                        </tr>
                      ))}
                    </tbody>
                  </Table>
                )}
              </Card>

              {phase === "I" && excluded.length > 0 && (
                <Card title={`Puntos excluidos (${excluded.length})`}>
                  <p className="mb-2 text-sm text-muted">Se retiran del cálculo de los límites, pero siguen visibles en el gráfico (cruz gris).</p>
                  <Table caption="Puntos excluidos con su causa asignable">
                    <thead><tr><Th>Subgrupo</Th><Th>Causa asignable</Th><Th>Acción</Th></tr></thead>
                    <tbody>
                      {excluded.map((e) => (
                        <tr key={e.index}>
                          <Td className="font-medium">{e.label ?? labelOf(e.index)}</Td>
                          <Td>{e.cause}</Td>
                          <Td><Button onClick={() => setExcluded((p) => p.filter((x) => x.index !== e.index))}>Restaurar</Button></Td>
                        </tr>
                      ))}
                    </tbody>
                  </Table>
                </Card>
              )}

              {phase === "I" && (
                <Card title="Congelar límites" className="no-print">
                  <p className="text-sm text-muted">
                    Guarda los parámetros actuales como los límites de referencia de este estudio. La Fase II los usará sin recalcular. Congelar de nuevo el mismo gráfico reemplaza los límites vigentes.
                  </p>
                  {frozen && (
                    <Alert tone="info" className="mt-3">
                      Hay límites vigentes congelados el {fmtDate(frozen.created_at)} ({frozen.limits.points_used} subgrupos).
                    </Alert>
                  )}
                  {freezeMsg && <Alert tone={freezeMsg.tone} className="mt-3">{freezeMsg.text}</Alert>}
                  <div className="mt-3">
                    <Button variant="primary" onClick={() => setFreezeOpen(true)} disabled={calc.loading}>
                      Congelar límites
                    </Button>
                  </div>
                </Card>
              )}

              <InterpretationBlock interpretation={result.interpretation} />
              <SaveAnalysis
                studyId={study.id}
                datasetId={dataset?.id}
                module={isVar ? "variables" : "attributes"}
                defaultTitle={`Gráfico ${TYPE_LABEL[chartType]} · Fase ${phase} · ${dataset?.name ?? ""}`}
                params={request!.body as unknown as Record<string, unknown>}
                result={result as unknown as Record<string, unknown>}
              />
            </div>
          )}
        </div>
      )}

      <Modal open={pending != null} title="Excluir punto del cálculo de límites" onClose={() => setPending(null)}>
        {pending != null && (
          <div className="flex flex-col gap-3 text-sm">
            <p>
              Subgrupo <strong>{labelOf(pending)}</strong>
              {signals.get(pending) ? ` — señal de ${[...signals.get(pending)!.rules].join(", ")}` : ""}.
            </p>
            <p className="text-muted">
              Solo excluye un punto si identificaste una causa asignable (algo concreto que ocurrió). Los límites se recalcularán sin él.
            </p>
            <TextAreaField
              label="Causa asignable (obligatoria)"
              value={cause}
              error={causeError ?? undefined}
              onChange={(e) => setCause(e.target.value)}
              autoFocus
            />
            <div className="flex justify-end gap-2">
              <Button onClick={() => setPending(null)}>Cancelar</Button>
              <Button variant="primary" onClick={confirmExclude}>Excluir y recalcular</Button>
            </div>
          </div>
        )}
      </Modal>

      <Modal open={freezeOpen} title="Congelar límites de control" onClose={() => setFreezeOpen(false)}>
        <div className="flex flex-col gap-3 text-sm">
          <p>
            Se guardarán los parámetros de <strong>{result ? TYPE_LABEL[result.limits.chart_type] : ""}</strong> calculados con {result?.limits.points_used} subgrupos
            {excluded.length ? ` (${excluded.length} excluido(s) con causa asignable)` : ""}.
          </p>
          {result && !result.in_control && (
            <Alert tone="warn">
              Todavía hay puntos con señal sin explicar. Congelar ahora fija límites de un proceso que quizá no es estable.
            </Alert>
          )}
          <div className="flex justify-end gap-2">
            <Button onClick={() => setFreezeOpen(false)}>Cancelar</Button>
            <Button variant="primary" loading={freezing} onClick={freeze}>Congelar</Button>
          </div>
        </div>
      </Modal>
    </>
  );
}

/** Asistente de selección del gráfico por atributos (módulo 3). */
function AttributeAssistant({ dataset, onUse }: { dataset?: Dataset; onUse: (t: ChartType) => void }) {
  const sizes = dataset ? attributeArrays(dataset).sizes : [];
  const counting = dataset?.subgrouping && "counting" in dataset.subgrouping ? dataset.subgrouping.counting : undefined;
  const [count, setCount] = useState<"defectives" | "defects" | null>(null);
  const [constant, setConstant] = useState<boolean | null>(null);
  const [asked, setAsked] = useState<{ counting: string; constant_size: boolean } | null>(null);
  const eff = count ?? counting ?? "defectives";
  const effConst = constant ?? (sizes.length > 0 && new Set(sizes).size === 1);

  const rec = useLoad(async () => (asked ? api.recommendAttributes(asked) : null), [asked?.counting, asked?.constant_size]);
  useAssistantScreen({
    view: {
      asistente_de_seleccion: asked ? { pregunta: asked, recomendacion: !rec.loading ? (rec.data ?? null) : null } : null,
    },
  });

  return (
    <Card title="Asistente: ¿qué gráfico necesito?">
      <div className="grid gap-4 sm:grid-cols-2">
        <fieldset>
          <legend className="mb-1 text-sm font-medium">¿Qué cuentas?</legend>
          {(
            [
              ["defectives", "Unidades defectuosas: cada unidad es conforme o no (p, np)"],
              ["defects", "Defectos: varios por unidad, como rayones o soldaduras malas (c, u)"],
            ] as const
          ).map(([v, t]) => (
            <label key={v} className="mb-1 flex items-start gap-2 text-sm">
              <input type="radio" name="counting" className="mt-1 accent-brand-text" checked={eff === v} onChange={() => setCount(v)} />
              <span>{t}</span>
            </label>
          ))}
        </fieldset>
        <fieldset>
          <legend className="mb-1 text-sm font-medium">¿El tamaño de muestra es constante?</legend>
          {(
            [
              [true, "Sí, siempre inspecciono lo mismo"],
              [false, "No, cambia de un subgrupo a otro"],
            ] as const
          ).map(([v, t]) => (
            <label key={String(v)} className="mb-1 flex items-start gap-2 text-sm">
              <input type="radio" name="constant" className="mt-1 accent-brand-text" checked={effConst === v} onChange={() => setConstant(v)} />
              <span>{t}</span>
            </label>
          ))}
          {dataset && <p className="text-xs text-muted">Según el conjunto elegido: {new Set(sizes).size === 1 ? "tamaño constante" : "tamaño variable"}.</p>}
        </fieldset>
      </div>
      <div className="mt-3">
        <Button variant="primary" onClick={() => setAsked({ counting: eff, constant_size: effConst })}>Recomendar gráfico</Button>
      </div>
      {asked && rec.loading && <Loading label="Consultando…" />}
      {rec.error && <Alert tone="error" className="mt-3">{rec.error}</Alert>}
      {asked && !rec.loading && rec.data && (
        <Alert tone="ok" title={`Gráfico recomendado: ${TYPE_LABEL[rec.data.chart_type]}`} className="mt-3">
          <p>{rec.data.justification}</p>
          {rec.data.alternatives.length > 0 && <p className="mt-1">Alternativa(s): {rec.data.alternatives.map((a) => TYPE_LABEL[a]).join(", ")}.</p>}
          <div className="mt-2">
            <Button onClick={() => onUse(rec.data!.chart_type)}>Usar {rec.data.chart_type}</Button>
          </div>
        </Alert>
      )}
    </Card>
  );
}
