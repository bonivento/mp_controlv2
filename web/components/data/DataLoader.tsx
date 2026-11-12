"use client";

import Link from "next/link";
import { useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { components } from "@/lib/api-types";
import { getStore } from "@/lib/data";
import type { CleaningEntry, Dataset, Phase, Study, Subgrouping } from "@/lib/db";
import { sizeIssues } from "@/lib/dataset-utils";
import { buildAttributeRows, buildVariableSubgroups, type VariableConfig } from "@/lib/subgroups";
import { Alert, Button, Card, CheckField, NumberField, SelectField, Table, Td, TextAreaField, TextField, Th, errMsg, numEs } from "../ui";
import { AttributeSummaryPanel } from "./AttributeSummaryPanel";
import { IncompleteSubgroups, type IncompleteDecision } from "./IncompleteSubgroups";
import { SummaryPanel, type OutlierDecision } from "./SummaryPanel";

type Parsed = components["schemas"]["ParsedFile"];
type Sheet = components["schemas"]["ParsedSheet"];
type Decision = OutlierDecision | IncompleteDecision;

interface Config {
  layout: "long" | "wide";
  valueColumn: string;
  valueColumns: string[];
  method: VariableConfig["method"];
  groupColumn: string;
  size: number | null;
  timeColumn: string;
  timeUnit: NonNullable<VariableConfig["timeUnit"]>;
  counting: "defectives" | "defects";
  countColumn: string;
  sizeColumn: string;
  constantSize: number | null;
  labelColumn: string;
}

function defaultsFor(sheet: Sheet, attribute: boolean): Config {
  const numeric = sheet.columns.filter((c) => c.kind === "numeric").map((c) => c.name);
  const find = (re: RegExp, pool = sheet.columns.map((c) => c.name)) => pool.find((n) => re.test(n)) ?? "";
  const wide = numeric.filter((n) => /^(x|obs|m|v)\d+$/i.test(n));
  const datetime = sheet.columns.find((c) => c.kind === "datetime")?.name ?? "";
  const label = find(/^(subgrupo|muestra|lote|id|sample|subgroup)$/i);
  return {
    layout: !attribute && wide.length >= 2 ? "wide" : "long",
    valueColumn: find(/valor|value|medici|volumen|peso|dimens/i, numeric) || numeric[numeric.length - 1] || "",
    valueColumns: wide,
    method: !attribute && wide.length < 2 && label ? "column" : "fixed_size",
    groupColumn: label,
    size: 5,
    timeColumn: datetime,
    timeUnit: "day",
    counting: "defectives",
    countColumn: find(/defect|conteo|count|no_conf|nc/i, numeric) || numeric[0] || "",
    sizeColumn: find(/tama|size|inspec|^n$/i, numeric),
    constantSize: null,
    labelColumn: label,
  };
}

export function DataLoader({ study, onSaved }: { study: Study; onSaved: () => void }) {
  const attribute = study.data_type === "attribute";
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [parsing, setParsing] = useState(false);
  const [parseError, setParseError] = useState<string | null>(null);
  const [parsed, setParsed] = useState<Parsed | null>(null);
  const [sheetIdx, setSheetIdx] = useState(0);
  const [cfg, setCfg] = useState<Config | null>(null);
  const [justification, setJustification] = useState("");
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [name, setName] = useState("");
  const [phase, setPhase] = useState<Phase>("I");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [savedMsg, setSavedMsg] = useState<Dataset | null>(null);
  const [showErrors, setShowErrors] = useState(false);

  const sheet = parsed?.sheets[sheetIdx] ?? null;
  const set = <K extends keyof Config>(k: K, v: Config[K]) => setCfg((c) => (c ? { ...c, [k]: v } : c));

  async function onFile(f: File | null) {
    setFile(f);
    setParsed(null);
    setCfg(null);
    setDecisions([]);
    setSavedMsg(null);
    setParseError(null);
    if (!f) return;
    setParsing(true);
    try {
      const p = await api.parseFile(f);
      setParsed(p);
      setSheetIdx(0);
      setCfg(defaultsFor(p.sheets[0], attribute));
      setName(f.name.replace(/\.[^.]+$/, ""));
    } catch (e) {
      setParseError(errMsg(e));
    } finally {
      setParsing(false);
    }
  }

  const built = useMemo(() => {
    if (!sheet || !cfg) return null;
    if (attribute)
      return {
        kind: "attribute" as const,
        ...buildAttributeRows(sheet, {
          countColumn: cfg.countColumn,
          sizeColumn: cfg.sizeColumn || undefined,
          constantSize: cfg.constantSize,
          labelColumn: cfg.labelColumn || undefined,
          counting: cfg.counting,
        }),
      };
    return {
      kind: "variable" as const,
      ...buildVariableSubgroups(sheet, {
        layout: cfg.layout,
        valueColumn: cfg.valueColumn,
        valueColumns: cfg.valueColumns,
        method: cfg.layout === "wide" ? "column" : cfg.method,
        groupColumn: cfg.groupColumn || undefined,
        size: cfg.size ?? 1,
        timeColumn: cfg.timeColumn,
        timeUnit: cfg.timeUnit,
      }),
    };
  }, [sheet, cfg, attribute]);

  const removed = new Set(decisions.filter((d) => d.kind !== "keep").map((d) => d.label));
  const rows = built && built.kind === "variable" ? built.rows.filter((r) => !removed.has(r.label)) : [];
  const issue = sizeIssues(rows);
  const attrRows = built && built.kind === "attribute" ? built.rows : [];
  const count = attribute ? attrRows.length : rows.length;
  const justOk = justification.trim().length >= 10;

  async function save() {
    setShowErrors(true);
    if (!sheet || !cfg || !built || !file) return;
    if (!justOk || count < 2 || !name.trim()) return;
    setSaving(true);
    setSaveError(null);
    const now = new Date().toISOString();
    const log: CleaningEntry[] = [
      { action: "Carga", detail: `Archivo ${file.name}, hoja ${sheet.name}: ${sheet.rows.length} filas, ${sheet.columns.length} columnas.`, at: now },
      // Avisos de la lectura del archivo (los genera la API) y de la formación de subgrupos (la web).
      ...[...new Set([...sheet.warnings, ...built.warnings])].map((w) => ({ action: "Limpieza", detail: w, at: now })),
      ...decisions.map((d) =>
        d.kind === "incomplete"
          ? {
              action: "Subgrupo incompleto retirado",
              detail: `Subgrupo ${d.label} (n = ${d.n}; el tamaño predominante es ${d.expected}): ${d.justification}`,
              at: now,
            }
          : {
              action: d.kind === "keep" ? "Atípico conservado" : "Subgrupo retirado",
              detail: `Subgrupo ${d.label}, valor ${numEs(d.value)}: ${d.justification}`,
              at: now,
            },
      ),
    ];
    const subgrouping: Subgrouping = attribute
      ? {
          method: "column",
          layout: "attribute",
          count_column: cfg.countColumn,
          size_column: cfg.sizeColumn || undefined,
          size: cfg.constantSize ?? undefined,
          column: cfg.labelColumn || undefined,
          counting: cfg.counting,
          justification: justification.trim(),
        }
      : {
          method: cfg.layout === "wide" ? "column" : cfg.method,
          layout: cfg.layout,
          column: cfg.method === "time" ? undefined : cfg.groupColumn || undefined,
          value_columns: cfg.layout === "wide" ? cfg.valueColumns : [cfg.valueColumn],
          size: cfg.method === "fixed_size" ? (cfg.size ?? undefined) : undefined,
          time_column: cfg.method === "time" ? cfg.timeColumn : undefined,
          time_unit: cfg.method === "time" ? cfg.timeUnit : undefined,
          justification: justification.trim(),
        };
    try {
      const ds = await getStore().datasets.create({
        study_id: study.id,
        name: name.trim(),
        phase,
        source_file: file.name,
        subgrouping,
        rows: attribute ? attrRows : rows,
        cleaning_log: log,
      });
      setSavedMsg(ds);
      setFile(null);
      setParsed(null);
      setCfg(null);
      setDecisions([]);
      setJustification("");
      setShowErrors(false);
      if (inputRef.current) inputRef.current.value = "";
      onSaved();
    } catch (e) {
      setSaveError(errMsg(e));
    } finally {
      setSaving(false);
    }
  }

  const colNames = sheet?.columns.map((c) => c.name) ?? [];
  const numericCols = sheet?.columns.filter((c) => c.kind === "numeric").map((c) => c.name) ?? [];
  const dateCols = sheet?.columns.filter((c) => c.kind === "datetime").map((c) => c.name) ?? [];

  return (
    <div className="flex flex-col gap-4">
      <Card title="1. Archivo">
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <label htmlFor="archivo-datos" className="text-sm font-medium">
              Archivo CSV o Excel (.xlsx)
            </label>
            <input
              id="archivo-datos"
              ref={inputRef}
              type="file"
              accept=".csv,.xlsx,.xls,text/csv"
              className="block w-full text-sm file:mr-3 file:min-h-10 file:cursor-pointer file:rounded-md file:border file:border-line file:bg-surface file:px-3.5 file:py-2 file:text-sm file:font-medium"
              onChange={(e) => onFile(e.target.files?.[0] ?? null)}
            />
            <p className="text-xs text-muted">Hasta 4 MB y 20 000 filas. La primera fila debe tener los nombres de las columnas.</p>
          </div>
          {parsing && (
            <p role="status" className="text-sm text-muted">
              Leyendo archivo…
            </p>
          )}
          {parseError && <Alert tone="error" title="No se pudo leer el archivo">{parseError}</Alert>}
          {savedMsg && (
            <Alert tone="ok" title="Conjunto de datos guardado">
              «{savedMsg.name}» se guardó como Fase {savedMsg.phase}. Sigue con{" "}
              <Link className="font-medium underline" href={`/estudios/${study.id}/${attribute ? "atributos" : "variables"}`}>
                los gráficos de control
              </Link>
              .
            </Alert>
          )}
          {parsed && parsed.sheets.length > 1 && (
            <SelectField
              label="Hoja"
              value={String(sheetIdx)}
              onChange={(e) => {
                const i = Number(e.target.value);
                setSheetIdx(i);
                setCfg(defaultsFor(parsed.sheets[i], attribute));
                setDecisions([]);
              }}
            >
              {parsed.sheets.map((s, i) => (
                <option key={s.name} value={i}>
                  {s.name} ({s.rows.length} filas)
                </option>
              ))}
            </SelectField>
          )}
          {sheet && sheet.warnings.length > 0 && (
            <Alert tone="warn" title={`Avisos al leer el archivo (${sheet.warnings.length})`}>
              <p>Estas conversiones se hicieron al leer la hoja; quedarán registradas en la bitácora de limpieza al guardar.</p>
              <ul className="mt-1 list-disc space-y-0.5 pl-5">
                {sheet.warnings.map((w, i) => <li key={i}>{w}</li>)}
              </ul>
            </Alert>
          )}
          {sheet && (
            <div>
              <p className="mb-1 text-sm font-medium">Columnas detectadas</p>
              <Table caption="Columnas detectadas en la hoja">
                <thead>
                  <tr>
                    <Th>Columna</Th>
                    <Th>Tipo</Th>
                    <Th>Vacías o no numéricas</Th>
                    <Th>Primeros valores</Th>
                  </tr>
                </thead>
                <tbody>
                  {sheet.columns.map((c, i) => (
                    <tr key={c.name}>
                      <Td>{c.name}</Td>
                      <Td>{{ numeric: "Numérica", text: "Texto", datetime: "Fecha y hora", empty: "Vacía" }[c.kind]}</Td>
                      <Td>{c.missing}</Td>
                      <Td className="text-muted">{sheet.rows.slice(0, 3).map((r) => String(r[i] ?? "—")).join(" · ")}</Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </div>
          )}
        </div>
      </Card>

      {sheet && cfg && (
        <Card title={attribute ? "2. Columnas y subgrupos" : "2. Columnas y subgrupos racionales"}>
          {attribute ? (
            <div className="grid gap-4 sm:grid-cols-2">
              <SelectField label="Qué cuentas" value={cfg.counting} onChange={(e) => set("counting", e.target.value as Config["counting"])}>
                <option value="defectives">Unidades defectuosas (no conformes)</option>
                <option value="defects">Defectos (no conformidades) por unidad</option>
              </SelectField>
              <SelectField label="Columna del conteo" value={cfg.countColumn} onChange={(e) => set("countColumn", e.target.value)}>
                {numericCols.map((c) => <option key={c}>{c}</option>)}
              </SelectField>
              <SelectField label="Columna del tamaño de muestra" value={cfg.sizeColumn} onChange={(e) => set("sizeColumn", e.target.value)} hint="Déjala vacía si el tamaño es el mismo en todos los subgrupos.">
                <option value="">(tamaño constante)</option>
                {numericCols.map((c) => <option key={c}>{c}</option>)}
              </SelectField>
              {!cfg.sizeColumn && <NumberField label="Tamaño constante" value={cfg.constantSize} onChange={(v) => set("constantSize", v)} />}
              <SelectField label="Columna de etiqueta (opcional)" value={cfg.labelColumn} onChange={(e) => set("labelColumn", e.target.value)}>
                <option value="">(numerar filas)</option>
                {colNames.map((c) => <option key={c}>{c}</option>)}
              </SelectField>
            </div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2">
              <SelectField
                label="Formato de los datos"
                value={cfg.layout}
                onChange={(e) => set("layout", e.target.value as Config["layout"])}
                className="sm:col-span-2"
              >
                <option value="long">Una columna con los valores (varias filas por subgrupo)</option>
                <option value="wide">Varias columnas por fila (cada fila es un subgrupo, p. ej. x1…x5)</option>
              </SelectField>
              {cfg.layout === "wide" ? (
                <>
                  <fieldset className="sm:col-span-2">
                    <legend className="mb-1 text-sm font-medium">Columnas con las observaciones</legend>
                    <div className="flex flex-wrap gap-x-5 gap-y-2">
                      {numericCols.map((c) => (
                        <CheckField
                          key={c}
                          label={c}
                          checked={cfg.valueColumns.includes(c)}
                          onChange={(on) => set("valueColumns", on ? [...cfg.valueColumns, c] : cfg.valueColumns.filter((x) => x !== c))}
                        />
                      ))}
                    </div>
                  </fieldset>
                  <SelectField label="Columna de etiqueta del subgrupo" value={cfg.groupColumn} onChange={(e) => set("groupColumn", e.target.value)}>
                    <option value="">(numerar filas)</option>
                    {colNames.map((c) => <option key={c}>{c}</option>)}
                  </SelectField>
                </>
              ) : (
                <>
                  <SelectField label="Columna del valor medido" value={cfg.valueColumn} onChange={(e) => set("valueColumn", e.target.value)}>
                    {numericCols.map((c) => <option key={c}>{c}</option>)}
                  </SelectField>
                  <SelectField label="Cómo se forman los subgrupos" value={cfg.method} onChange={(e) => set("method", e.target.value as Config["method"])}>
                    <option value="column">Por columna (un identificador por subgrupo)</option>
                    <option value="fixed_size">Por tamaño fijo (cada n observaciones seguidas)</option>
                    <option value="time">Por tiempo (hora, día, semana o mes)</option>
                  </SelectField>
                  {cfg.method === "column" && (
                    <SelectField label="Columna que identifica el subgrupo" value={cfg.groupColumn} onChange={(e) => set("groupColumn", e.target.value)}>
                      <option value="">(elige una columna)</option>
                      {colNames.map((c) => <option key={c}>{c}</option>)}
                    </SelectField>
                  )}
                  {cfg.method === "fixed_size" && (
                    <NumberField label="Tamaño del subgrupo (n)" value={cfg.size} onChange={(v) => set("size", v)} hint="Usa 1 para datos individuales (gráfico I-MR)." />
                  )}
                  {cfg.method === "time" && (
                    <>
                      <SelectField label="Columna de fecha y hora" value={cfg.timeColumn} onChange={(e) => set("timeColumn", e.target.value)}>
                        <option value="">(elige una columna)</option>
                        {dateCols.map((c) => <option key={c}>{c}</option>)}
                      </SelectField>
                      <SelectField label="Agrupar por" value={cfg.timeUnit} onChange={(e) => set("timeUnit", e.target.value as Config["timeUnit"])}>
                        <option value="hour">Hora</option>
                        <option value="day">Día</option>
                        <option value="week">Semana</option>
                        <option value="month">Mes</option>
                      </SelectField>
                    </>
                  )}
                </>
              )}
            </div>
          )}
          <TextAreaField
            className="mt-4"
            label="Justificación del subgrupo racional (obligatoria)"
            value={justification}
            onChange={(e) => setJustification(e.target.value)}
            error={showErrors && !justOk ? "Explica en al menos 10 caracteres por qué estas observaciones forman un subgrupo." : undefined}
            hint="Un subgrupo racional reúne observaciones tomadas en condiciones similares para que la variación dentro sea solo la de causas comunes. Ejemplo: cinco piezas consecutivas de la misma máquina y turno."
          />
          {built && built.warnings.length > 0 && (
            <Alert tone="warn" className="mt-3" title="Avisos al formar los subgrupos">
              <ul className="list-disc pl-5">
                {built.warnings.map((w) => <li key={w}>{w}</li>)}
              </ul>
            </Alert>
          )}
        </Card>
      )}

      {sheet && cfg && built && (
        <>
          <h2 className="mt-2 text-lg font-semibold">3. Resumen y limpieza</h2>
          {count === 0 ? (
            <Alert tone="info">Todavía no hay subgrupos con esta configuración. Revisa las columnas elegidas.</Alert>
          ) : attribute ? (
            <AttributeSummaryPanel
              rows={attrRows}
              studyId={study.id}
              title={name || "datos cargados"}
              counting={cfg.counting}
            />
          ) : (
            <>
              {issue && <IncompleteSubgroups issue={issue} onRetire={(ds) => setDecisions((p) => [...p, ...ds])} />}
              <SummaryPanel
                rows={rows}
                studyId={study.id}
                title={name || "datos cargados"}
                decided={decisions.map((d) => d.label)}
                onDecision={(d) => setDecisions((p) => [...p, d])}
              />
            </>
          )}

          {decisions.length > 0 && (
            <Card title="Bitácora de limpieza (de esta carga)">
              <ul className="list-disc space-y-1 pl-5 text-sm">
                {decisions.map((d, i) => (
                  <li key={i}>
                    {d.kind === "incomplete" ? (
                      <>
                        <strong>Subgrupo incompleto retirado</strong> · subgrupo {d.label} (n = {d.n}; el tamaño predominante es {d.expected}): {d.justification}
                      </>
                    ) : (
                      <>
                        <strong>{d.kind === "keep" ? "Atípico conservado" : "Subgrupo retirado"}</strong> · subgrupo {d.label}, valor {numEs(d.value)}: {d.justification}
                      </>
                    )}
                  </li>
                ))}
              </ul>
            </Card>
          )}

          <Card title="4. Guardar como conjunto de datos">
            <div className="grid gap-4 sm:grid-cols-2">
              <TextField label="Nombre del conjunto" value={name} onChange={(e) => setName(e.target.value)} error={showErrors && !name.trim() ? "Escribe un nombre." : undefined} />
              <fieldset>
                <legend className="mb-1 text-sm font-medium">Fase</legend>
                <div className="flex flex-col gap-1.5 text-sm">
                  {(
                    [
                      ["I", "Fase I: datos para estimar y congelar los límites de control"],
                      ["II", "Fase II: datos nuevos para monitorear contra límites congelados"],
                    ] as const
                  ).map(([v, t]) => (
                    <label key={v} className="flex items-start gap-2">
                      <input type="radio" name="fase" className="mt-1 accent-[var(--brand)]" checked={phase === v} onChange={() => setPhase(v)} />
                      <span>{t}</span>
                    </label>
                  ))}
                </div>
              </fieldset>
            </div>
            {showErrors && count < 2 && <Alert tone="error" className="mt-3">Se necesitan al menos 2 subgrupos para guardar.</Alert>}
            {showErrors && !justOk && <Alert tone="error" className="mt-3">Falta la justificación del subgrupo racional (paso 2).</Alert>}
            {saveError && <Alert tone="error" className="mt-3">{saveError}</Alert>}
            <div className="mt-4">
              <Button variant="primary" loading={saving} onClick={save}>
                Guardar conjunto de datos
              </Button>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
