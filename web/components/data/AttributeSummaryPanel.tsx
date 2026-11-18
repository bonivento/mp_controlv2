"use client";

import { api } from "@/lib/api";
import type { AttributeRow } from "@/lib/db";
import { useLoad } from "@/lib/use-load";
import { SaveAnalysis } from "../analysis-parts";
import { useAssistantScreen } from "../assistant/assistant-provider";
import { Alert, Badge, Card, Loading, Table, Td, Th, fmtNum } from "../ui";

function signature(rows: AttributeRow[]) {
  let h = 0;
  const s = rows.map((r) => `${r.label}:${r.count}:${r.size}`).join("|");
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return `${rows.length}-${h}`;
}

/** Resumen de datos por atributos (módulo 1): totales, tasa global y avisos, calculados por la API. */
export function AttributeSummaryPanel({
  rows,
  studyId,
  datasetId,
  title,
  counting,
}: {
  rows: AttributeRow[];
  studyId: string;
  datasetId?: string | null;
  title: string;
  counting?: "defectives" | "defects";
}) {
  const req = { counts: rows.map((r) => r.count), sizes: rows.map((r) => r.size), labels: rows.map((r) => r.label) };
  const { data, loading, error } = useLoad(() => api.attributeSummary(req), [signature(rows)]);
  useAssistantScreen({ view: { [datasetId ? "resumen_del_conjunto_guardado" : "resumen_de_la_carga"]: data ? { titulo: title, conteo: counting, ...data } : null } });
  if (loading && !data) return <Loading label="Calculando resumen…" />;
  if (error) return <Alert tone="error" title="No se pudo calcular el resumen">{error}</Alert>;
  if (!data) return null;
  const what = counting === "defects" ? "Defectos" : "Defectuosas";
  const rate = (x: number | null) => (x == null ? "—" : fmtNum(x, 4));

  return (
    <div className="flex flex-col gap-4">
      <Card title="Resumen global">
        <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4 lg:grid-cols-6">
          {[
            ["Subgrupos", String(data.subgroups)],
            [`${what} (total)`, fmtNum(data.total_count, 0)],
            ["Unidades inspeccionadas", data.total_size == null ? "—" : fmtNum(data.total_size, 0)],
            ["Tasa global", rate(data.overall_rate)],
            ["Conteo medio por subgrupo", fmtNum(data.mean_count, 3)],
            ["Tamaño mínimo", data.min_size == null ? "—" : fmtNum(data.min_size, 0)],
            ["Tamaño máximo", data.max_size == null ? "—" : fmtNum(data.max_size, 0)],
            ["Tamaño de muestra", data.constant_size == null ? "—" : data.constant_size ? "Constante" : "Variable"],
          ].map(([k, v]) => (
            <div key={k}>
              <dt className="text-xs text-muted">{k}</dt>
              <dd className="num font-medium">{v}</dd>
            </div>
          ))}
        </dl>
        {data.warnings.length > 0 && (
          <Alert tone="warn" title="Avisos" className="mt-3">
            <ul className="list-disc pl-5">
              {data.warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          </Alert>
        )}
        {data.constant_size === false && (
          <Alert tone="info" className="mt-3">
            El tamaño de muestra varía: usa los gráficos p o u, que ajustan los límites a cada subgrupo (np y c lo exigen constante).
          </Alert>
        )}
      </Card>
      <Card title="Resumen por subgrupo">
        <div className="max-h-96 overflow-auto">
          <Table caption="Resumen de atributos por subgrupo">
            <thead>
              <tr>
                <Th>Subgrupo</Th>
                <Th>{what}</Th>
                <Th>Tamaño de muestra</Th>
                <Th>Tasa</Th>
                <Th>Aviso</Th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((r, i) => (
                <tr key={`${r.label}-${i}`}>
                  <Td>{r.label}</Td>
                  <Td>{fmtNum(r.count, 0)}</Td>
                  <Td>{r.size == null ? "—" : fmtNum(r.size, 0)}</Td>
                  <Td>{rate(r.rate)}</Td>
                  <Td>{r.size != null && r.count > r.size ? <Badge tone="warn">Conteo mayor que n</Badge> : "—"}</Td>
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
    </div>
  );
}
