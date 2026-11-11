"use client";

import Link from "next/link";
import { useState } from "react";
import type { components } from "@/lib/api-types";
import { getStore } from "@/lib/data";
import type { AnalysisModule, Dataset } from "@/lib/db";
import { datasetOptionLabel } from "@/lib/dataset-utils";
import { Alert, Button, Card, CheckField, SelectField, TextField, errMsg } from "./ui";

type Interp = components["schemas"]["Interpretation"];
type RuleId = NonNullable<components["schemas"]["RuleConfig"]["enabled"]>[number];

/** Bloque de interpretación común: resumen, hallazgos y advertencias de la API. */
export function InterpretationBlock({ interpretation }: { interpretation: Interp }) {
  return (
    <Card title="Interpretación" className="print-break">
      <p className="text-base font-medium">{interpretation.summary}</p>
      {interpretation.findings.length > 0 && (
        <div className="mt-3">
          <h3 className="text-sm font-semibold">Hallazgos</h3>
          <ul className="mt-1 list-disc space-y-1 pl-5 text-sm">
            {interpretation.findings.map((f, i) => (
              <li key={i}>{f}</li>
            ))}
          </ul>
        </div>
      )}
      {interpretation.warnings.length > 0 && (
        <Alert tone="warn" title="Advertencias" className="mt-3">
          <ul className="list-disc space-y-1 pl-5">
            {interpretation.warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </Alert>
      )}
    </Card>
  );
}

/** Guarda el análisis actual en `analyses` (fuente del reporte). */
export function SaveAnalysis({
  studyId,
  datasetId,
  module,
  defaultTitle,
  params,
  result,
  disabled,
}: {
  studyId: string;
  datasetId?: string | null;
  module: AnalysisModule;
  defaultTitle: string;
  params: Record<string, unknown>;
  result: Record<string, unknown> | null;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState(defaultTitle);
  const [inReport, setInReport] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);

  async function save() {
    if (!result) return;
    if (!title.trim()) {
      setError("Escribe un título para el análisis.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await getStore().analyses.create({
        study_id: studyId,
        dataset_id: datasetId ?? null,
        module,
        title: title.trim(),
        params,
        result,
        in_report: inReport,
      });
      setSaved(title.trim());
      setOpen(false);
    } catch (e) {
      setError(errMsg(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="no-print">
      <div className="flex flex-wrap items-center gap-3">
        <Button
          variant="primary"
          disabled={disabled || !result}
          onClick={() => {
            setTitle(defaultTitle);
            setSaved(null);
            setOpen((o) => !o);
          }}
          aria-expanded={open}
        >
          Guardar análisis
        </Button>
        <span className="text-sm text-muted">Queda guardado con sus parámetros y resultado para armar el reporte.</span>
      </div>
      {open && (
        <div className="mt-4 grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end">
          <TextField label="Título del análisis" value={title} onChange={(e) => setTitle(e.target.value)} />
          <CheckField label="Incluir en el reporte" checked={inReport} onChange={setInReport} />
          <div className="flex gap-2 sm:col-span-2">
            <Button variant="primary" loading={busy} onClick={save}>
              Confirmar y guardar
            </Button>
            <Button onClick={() => setOpen(false)}>Cancelar</Button>
          </div>
        </div>
      )}
      {error && <Alert tone="error" className="mt-3">{error}</Alert>}
      {saved && (
        <Alert tone="ok" className="mt-3">
          Análisis «{saved}» guardado.{" "}
          <Link href={`/estudios/${studyId}/reporte`} className="font-medium underline">
            Ver el reporte
          </Link>
        </Alert>
      )}
    </Card>
  );
}

const RULES: { id: RuleId; text: string }[] = [
  { id: "WE1", text: "1. Un punto fuera de los límites de 3 sigma" },
  { id: "WE2", text: "2. Dos de tres puntos a más de 2 sigma del mismo lado" },
  { id: "WE3", text: "3. Cuatro de cinco puntos a más de 1 sigma del mismo lado" },
  { id: "WE4", text: "4. Ocho puntos seguidos del mismo lado de la línea central" },
  { id: "N2", text: "2. Nueve puntos seguidos del mismo lado de la línea central" },
  { id: "N3", text: "3. Seis puntos seguidos en aumento o en descenso" },
  { id: "N4", text: "4. Catorce puntos seguidos alternando arriba y abajo" },
  { id: "N5", text: "5. Dos de tres puntos a más de 2 sigma (Nelson)" },
  { id: "N6", text: "6. Cuatro de cinco puntos a más de 1 sigma (Nelson)" },
  { id: "N7", text: "7. Quince puntos seguidos dentro de 1 sigma (estratificación)" },
  { id: "N8", text: "8. Ocho puntos seguidos a más de 1 sigma de ambos lados (mezcla)" },
];

/** Selector de reglas de corrida (Western Electric y Nelson). La regla 1 va siempre activa. */
export function RuleSelector({ value, onChange }: { value: RuleId[]; onChange: (v: RuleId[]) => void }) {
  const has = (r: RuleId) => value.includes(r);
  const toggle = (r: RuleId, on: boolean) => onChange(on ? [...value, r] : value.filter((x) => x !== r));
  const we = RULES.filter((r) => r.id.startsWith("WE"));
  const nelson = RULES.filter((r) => r.id.startsWith("N"));
  return (
    <fieldset className="rounded-md border border-line p-3">
      <legend className="px-1 text-sm font-medium">Reglas de corrida</legend>
      <div className="mb-2 flex flex-wrap gap-2">
        <Button onClick={() => onChange(["WE1"])}>Solo punto fuera de límites</Button>
        <Button onClick={() => onChange(["WE1", "WE2", "WE3", "WE4"])}>Western Electric</Button>
        <Button onClick={() => onChange(["WE1", "N2", "N3", "N4", "N5", "N6", "N7", "N8"])}>Nelson</Button>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="flex flex-col gap-1.5">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted">Western Electric</p>
          <CheckField label="1. Un punto fuera de los límites de control" checked disabled onChange={() => {}} />
          {we.slice(1).map((r) => (
            <CheckField key={r.id} label={r.text} checked={has(r.id)} onChange={(on) => toggle(r.id, on)} />
          ))}
        </div>
        <div className="flex flex-col gap-1.5">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted">Nelson</p>
          {nelson.map((r) => (
            <CheckField key={r.id} label={r.text} checked={has(r.id)} onChange={(on) => toggle(r.id, on)} />
          ))}
        </div>
      </div>
      <p className="mt-2 text-xs text-muted">
        En los gráficos de dispersión (R, S, MR) y de atributos solo se aplican las reglas válidas para límites asimétricos: punto
        fuera de límites y las de posición (rachas, tendencia y alternancia).
      </p>
    </fieldset>
  );
}

export function DatasetSelect({
  label,
  datasets,
  value,
  onChange,
  hint,
}: {
  label: string;
  datasets: Dataset[];
  value: string;
  onChange: (id: string) => void;
  hint?: string;
}) {
  return (
    <SelectField label={label} value={value} onChange={(e) => onChange(e.target.value)} hint={hint}>
      {datasets.length === 0 && <option value="">Sin conjuntos de datos</option>}
      {datasets.map((d) => (
        <option key={d.id} value={d.id}>
          {datasetOptionLabel(d)}
        </option>
      ))}
    </SelectField>
  );
}
