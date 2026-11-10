"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { VariableRow } from "@/lib/db-provisional";
import { useLoad } from "@/lib/use-load";
import { SaveAnalysis } from "../analysis-parts";
import { Alert, Badge, Button, Card, Loading, Modal, Table, Td, TextAreaField, Th, fmtNum } from "../ui";
import type { components } from "@/lib/api-types";

type Outlier = components["schemas"]["OutlierFlag"];

export interface OutlierDecision {
  kind: "keep" | "remove";
  label: string;
  value: number;
  justification: string;
}

function signature(rows: VariableRow[]) {
  let h = 0;
  const s = rows.map((r) => `${r.label}:${r.values.join(",")}`).join("|");
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return `${rows.length}-${h}`;
}

/**
 * Tabla resumen por subgrupo, estadística global y atípicos marcados (módulo 1).
 * Los atípicos no se borran: cada decisión (conservar o retirar el subgrupo) exige
 * una justificación y queda en la bitácora.
 */
export function SummaryPanel({
  rows,
  studyId,
  datasetId,
  title,
  decided,
  onDecision,
}: {
  rows: VariableRow[];
  studyId: string;
  datasetId?: string | null;
  title: string;
  /** Etiquetas de subgrupos cuyo atípico ya tiene decisión. */
  decided?: string[];
  onDecision?: (d: OutlierDecision) => void;
}) {
  const req = { subgroups: rows.map((r) => r.values), labels: rows.map((r) => r.label) };
  const { data, loading, error } = useLoad(() => api.summary(req), [signature(rows)]);
  const [target, setTarget] = useState<Outlier | null>(null);
  const [kind, setKind] = useState<"keep" | "remove">("keep");
  const [why, setWhy] = useState("");
  const [whyError, setWhyError] = useState<string | null>(null);

  if (loading && !data) return <Loading label="Calculando resumen…" />;
  if (error) return <Alert tone="error" title="No se pudo calcular el resumen">{error}</Alert>;
  if (!data) return null;

  const outlierBySub = new Map<number, Outlier[]>();
  data.outliers.forEach((o) => outlierBySub.set(o.subgroup_index, [...(outlierBySub.get(o.subgroup_index) ?? []), o]));
  const o = data.overall;

  function confirm() {
    if (!target) return;
    if (why.trim().length < 5) {
      setWhyError("Escribe la justificación (al menos 5 caracteres).");
      return;
    }
    onDecision?.({ kind, label: data!.subgroups[target.subgroup_index].label, value: target.value, justification: why.trim() });
    setTarget(null);
    setWhy("");
    setWhyError(null);
  }

  return (
    <div className="flex flex-col gap-4">
      <Card title="Estadística descriptiva global">
        <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4 lg:grid-cols-6">
          {[
            ["Observaciones", String(o.count)],
            ["Subgrupos", String(data.subgroups.length)],
            ["Media", fmtNum(o.mean)],
            ["Desv. estándar", fmtNum(o.std)],
            ["Mínimo", fmtNum(o.min)],
            ["Q1", fmtNum(o.q1)],
            ["Mediana", fmtNum(o.median)],
            ["Q3", fmtNum(o.q3)],
            ["Máximo", fmtNum(o.max)],
            ["Asimetría", fmtNum(o.skewness)],
            ["Curtosis (exceso)", fmtNum(o.kurtosis)],
            ["Tamaño de subgrupo", data.constant_size ? "Constante" : "Variable"],
          ].map(([k, v]) => (
            <div key={k}>
              <dt className="text-xs text-muted">{k}</dt>
              <dd className="font-medium num">{v}</dd>
            </div>
          ))}
        </dl>
        {!data.constant_size && (
          <Alert tone="warn" className="mt-3">
            Los subgrupos no tienen el mismo tamaño: X-barra y np exigen tamaño constante.
          </Alert>
        )}
      </Card>

      <Card title={`Atípicos marcados (${data.outliers.length})`}>
        {data.outliers.length === 0 ? (
          <p className="text-sm text-muted">Ninguna observación sale del criterio 1,5·IQR.</p>
        ) : (
          <>
            <p className="mb-2 text-sm text-muted">
              No se eliminan solos: elige qué hacer con cada uno y escribe por qué. Un valor atípico puede ser una señal real del proceso.
            </p>
            <Table caption="Observaciones atípicas">
              <thead>
                <tr>
                  <Th>Subgrupo</Th>
                  <Th>Posición</Th>
                  <Th>Valor</Th>
                  <Th>Motivo</Th>
                  {onDecision && <Th>Decisión</Th>}
                </tr>
              </thead>
              <tbody>
                {data.outliers.map((x, i) => {
                  const label = data.subgroups[x.subgroup_index].label;
                  const done = decided?.includes(label);
                  return (
                    <tr key={i}>
                      <Td>{label}</Td>
                      <Td>{x.position + 1}</Td>
                      <Td>{fmtNum(x.value, 2)}</Td>
                      <Td>{x.reason}</Td>
                      {onDecision && (
                        <Td>
                          {done ? (
                            <Badge tone="ok">Decisión registrada</Badge>
                          ) : (
                            <Button onClick={() => { setTarget(x); setKind("keep"); setWhy(""); setWhyError(null); }}>
                              Decidir…
                            </Button>
                          )}
                        </Td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </Table>
          </>
        )}
      </Card>

      <Card title="Resumen por subgrupo">
        <div className="max-h-96 overflow-auto">
          <Table caption="Resumen por subgrupo">
            <thead>
              <tr>
                {["Subgrupo", "n", "Media", "Rango", "Desv. est.", "Mín.", "Máx.", "Atípico"].map((h) => (
                  <Th key={h}>{h}</Th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.subgroups.map((s, i) => (
                <tr key={`${s.label}-${i}`}>
                  <Td>{s.label}</Td>
                  <Td>{s.n}</Td>
                  <Td>{fmtNum(s.mean)}</Td>
                  <Td>{fmtNum(s.range)}</Td>
                  <Td>{fmtNum(s.std)}</Td>
                  <Td>{fmtNum(s.min, 2)}</Td>
                  <Td>{fmtNum(s.max, 2)}</Td>
                  <Td>{outlierBySub.has(i) ? <Badge tone="warn">Sí ({outlierBySub.get(i)!.length})</Badge> : "—"}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </div>
      </Card>

      <SaveAnalysis
        studyId={studyId}
        datasetId={datasetId}
        module="data"
        defaultTitle={`Resumen de datos: ${title}`}
        params={req}
        result={data as unknown as Record<string, unknown>}
      />

      <Modal open={!!target} title="Decisión sobre un valor atípico" onClose={() => setTarget(null)}>
        {target && (
          <div className="flex flex-col gap-3 text-sm">
            <p>
              Subgrupo <strong>{data.subgroups[target.subgroup_index].label}</strong>, valor <strong>{fmtNum(target.value, 2)}</strong>. {target.reason}
            </p>
            <fieldset className="flex flex-col gap-2">
              <legend className="mb-1 font-medium">¿Qué haces con este dato?</legend>
              <label className="flex items-start gap-2">
                <input type="radio" name="outlier-kind" className="mt-1 accent-[var(--brand)]" checked={kind === "keep"} onChange={() => setKind("keep")} />
                <span>Conservarlo: es variación real del proceso y debe verse en los gráficos.</span>
              </label>
              <label className="flex items-start gap-2">
                <input type="radio" name="outlier-kind" className="mt-1 accent-[var(--brand)]" checked={kind === "remove"} onChange={() => setKind("remove")} />
                <span>Retirar el subgrupo completo: hay un error de medición o de captura comprobado.</span>
              </label>
            </fieldset>
            <TextAreaField
              label="Justificación (obligatoria)"
              value={why}
              error={whyError ?? undefined}
              onChange={(e) => setWhy(e.target.value)}
              hint="Queda en la bitácora de limpieza del conjunto de datos."
            />
            <div className="flex justify-end gap-2">
              <Button onClick={() => setTarget(null)}>Cancelar</Button>
              <Button variant="primary" onClick={confirm}>
                Registrar decisión
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
