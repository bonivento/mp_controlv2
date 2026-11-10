"use client";

import { useState } from "react";
import type { Study, StudyInput } from "@/lib/db-provisional";
import { Alert, Button, CheckField, NumberField, SelectField, TextAreaField, TextField } from "./ui";

const blank: StudyInput = {
  name: "",
  company: "",
  process: "",
  product: "",
  characteristic: "",
  unit: "",
  data_type: "variable",
  lsl: null,
  usl: null,
  target: null,
  notes: "",
  is_synthetic: false,
};

export function StudyForm({
  initial,
  submitLabel,
  onSubmit,
  onCancel,
}: {
  initial?: Study;
  submitLabel: string;
  onSubmit: (v: StudyInput) => Promise<void>;
  onCancel: () => void;
}) {
  const [v, setV] = useState<StudyInput>(
    initial
      ? {
          name: initial.name,
          company: initial.company ?? "",
          process: initial.process ?? "",
          product: initial.product ?? "",
          characteristic: initial.characteristic ?? "",
          unit: initial.unit ?? "",
          data_type: initial.data_type,
          lsl: initial.lsl,
          usl: initial.usl,
          target: initial.target,
          notes: initial.notes ?? "",
          is_synthetic: initial.is_synthetic,
        }
      : blank,
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const set = <K extends keyof StudyInput>(k: K, val: StudyInput[K]) => setV((p) => ({ ...p, [k]: val }));
  const variable = v.data_type === "variable";

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const errs: Record<string, string> = {};
    if (!v.name.trim()) errs.name = "Escribe un nombre para el estudio.";
    if (v.lsl != null && v.usl != null && v.lsl >= v.usl) errs.usl = "El USL debe ser mayor que el LSL.";
    if (v.target != null && ((v.lsl != null && v.target < v.lsl) || (v.usl != null && v.target > v.usl)))
      errs.target = "El objetivo debe estar entre el LSL y el USL.";
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setBusy(true);
    setError(null);
    try {
      const clean = (s: string | null) => (s && s.trim() ? s.trim() : null);
      await onSubmit({
        ...v,
        name: v.name.trim(),
        company: clean(v.company),
        process: clean(v.process),
        product: clean(v.product),
        characteristic: clean(v.characteristic),
        unit: clean(v.unit),
        notes: clean(v.notes),
        // Los atributos no llevan especificaciones.
        lsl: variable ? v.lsl : null,
        usl: variable ? v.usl : null,
        target: variable ? v.target : null,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo guardar.");
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-5">
      <div className="grid gap-4 sm:grid-cols-2">
        <TextField
          className="sm:col-span-2"
          label="Nombre del estudio *"
          required
          value={v.name}
          error={errors.name}
          onChange={(e) => set("name", e.target.value)}
        />
        <TextField label="Empresa" value={v.company ?? ""} onChange={(e) => set("company", e.target.value)} />
        <TextField label="Proceso" value={v.process ?? ""} onChange={(e) => set("process", e.target.value)} />
        <TextField label="Producto" value={v.product ?? ""} onChange={(e) => set("product", e.target.value)} />
        <TextField
          label="Característica de calidad"
          value={v.characteristic ?? ""}
          onChange={(e) => set("characteristic", e.target.value)}
        />
        <TextField label="Unidad de medida" value={v.unit ?? ""} onChange={(e) => set("unit", e.target.value)} />
        <SelectField
          label="Tipo de dato"
          value={v.data_type}
          onChange={(e) => set("data_type", e.target.value as StudyInput["data_type"])}
          hint="Variable: mediciones (mL, mm). Atributo: conteos de defectuosos o defectos."
        >
          <option value="variable">Variable (medición continua)</option>
          <option value="attribute">Atributo (conteo)</option>
        </SelectField>
      </div>

      {variable ? (
        <fieldset className="grid gap-4 rounded-md border border-line p-4 sm:grid-cols-3">
          <legend className="px-1 text-sm font-medium">Especificaciones</legend>
          <NumberField label="LSL (límite inferior)" value={v.lsl} onChange={(x) => set("lsl", x)} />
          <NumberField label="USL (límite superior)" value={v.usl} error={errors.usl} onChange={(x) => set("usl", x)} />
          <NumberField label="Objetivo" value={v.target} error={errors.target} onChange={(x) => set("target", x)} />
          <p className="text-xs text-muted sm:col-span-3">
            Se usan en el módulo de capacidad. Puedes dejar una en blanco si la especificación es unilateral.
          </p>
        </fieldset>
      ) : (
        <Alert tone="info">Los estudios por atributos no usan LSL, USL ni objetivo.</Alert>
      )}

      <TextAreaField label="Notas" value={v.notes ?? ""} onChange={(e) => set("notes", e.target.value)} />
      <CheckField
        label="Datos sintéticos"
        hint="Márcalo si los datos son de ejemplo y no de una empresa real."
        checked={v.is_synthetic}
        onChange={(x) => set("is_synthetic", x)}
      />

      {error && <Alert tone="error">{error}</Alert>}
      <div className="flex justify-end gap-2">
        <Button onClick={onCancel}>Cancelar</Button>
        <Button type="submit" variant="primary" loading={busy}>
          {submitLabel}
        </Button>
      </div>
    </form>
  );
}
