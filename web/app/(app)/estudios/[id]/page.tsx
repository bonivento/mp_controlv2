"use client";

import Link from "next/link";
import { useStudy } from "@/components/study-context";
import { Alert, Badge, Card, Loading, PageHeader, fmtNum } from "@/components/ui";
import { getStore } from "@/lib/data";
import { useLoad } from "@/lib/use-load";

export default function StudyOverviewPage() {
  const { study } = useStudy();
  const base = `/estudios/${study.id}`;
  const { data, loading, error } = useLoad(async () => {
    const s = getStore();
    const [datasets, limits, analyses] = await Promise.all([
      s.datasets.list(study.id),
      s.controlLimits.listActive(study.id),
      s.analyses.list(study.id),
    ]);
    return { datasets, limits, analyses };
  }, [study.id]);

  const isVar = study.data_type === "variable";
  const steps: { href: string; title: string; text: string }[] = [
    { href: `${base}/datos`, title: "1. Datos", text: "Carga el archivo, define los subgrupos racionales y guarda un conjunto de Fase I y otro de Fase II." },
    isVar
      ? { href: `${base}/variables`, title: "2. Gráficos por variables", text: "Fase I: límites de prueba, causas asignables y congelado. Fase II: monitoreo." }
      : { href: `${base}/atributos`, title: "2. Gráficos por atributos", text: "El asistente recomienda p, np, c o u; luego Fase I y Fase II." },
    ...(isVar
      ? [
          { href: `${base}/supuestos`, title: "3. Supuestos", text: "Normalidad, independencia y autocorrelación." },
          { href: `${base}/capacidad`, title: "4. Capacidad", text: "Cp, Cpk, Pp, Ppk y fracción no conforme." },
        ]
      : []),
    { href: `${base}/diseno`, title: isVar ? "5. Diseño de gráficos" : "3. Diseño de gráficos", text: "ARL0, ARL1, ATS y curvas OC según n, L y h." },
    { href: `${base}/muestreo`, title: isVar ? "6. Muestreo de aceptación" : "4. Muestreo de aceptación", text: "Planes simple y doble, curvas OC, AOQ, ATI y ASN." },
    { href: `${base}/reporte`, title: "Reporte", text: "Reúne los análisis guardados para imprimir o exportar." },
  ];

  return (
    <>
      <title>{`${study.name} · CEP`}</title>
      <PageHeader
        title="Resumen del estudio"
        actions={
          <Link href={`${base}/editar`} className="inline-flex min-h-10 items-center rounded-md border border-line px-3.5 py-2 text-sm font-medium hover:bg-surface-2">
            Editar estudio
          </Link>
        }
      />
      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Datos del estudio" className="lg:col-span-2">
          <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
            {[
              ["Empresa", study.company],
              ["Proceso", study.process],
              ["Producto", study.product],
              ["Característica", study.characteristic],
              ["Unidad", study.unit],
              ["LSL", study.lsl != null ? fmtNum(study.lsl, 2) : null],
              ["USL", study.usl != null ? fmtNum(study.usl, 2) : null],
              ["Objetivo", study.target != null ? fmtNum(study.target, 2) : null],
            ].map(([k, v]) => (
              <div key={k} className="flex justify-between gap-3 border-b border-line py-1">
                <dt className="text-muted">{k}</dt>
                <dd className="text-right">{v || "—"}</dd>
              </div>
            ))}
          </dl>
          {study.notes && <p className="mt-3 text-sm text-muted">{study.notes}</p>}
          {study.is_synthetic && (
            <Alert tone="warn" className="mt-3">
              Este estudio usa datos sintéticos: sirve para probar el software, no describe un proceso real.
            </Alert>
          )}
        </Card>
        <Card title="Avance">
          {loading && <Loading />}
          {error && <Alert tone="error">{error}</Alert>}
          {data && (
            <ul className="flex flex-col gap-2 text-sm">
              <li className="flex justify-between">
                <span>Conjuntos de Fase I</span> <Badge tone="neutral">{data.datasets.filter((d) => d.phase === "I").length}</Badge>
              </li>
              <li className="flex justify-between">
                <span>Conjuntos de Fase II</span> <Badge tone="neutral">{data.datasets.filter((d) => d.phase === "II").length}</Badge>
              </li>
              <li className="flex justify-between">
                <span>Límites congelados</span> <Badge tone={data.limits.length ? "ok" : "neutral"}>{data.limits.length}</Badge>
              </li>
              <li className="flex justify-between">
                <span>Análisis guardados</span> <Badge tone="neutral">{data.analyses.length}</Badge>
              </li>
            </ul>
          )}
        </Card>
      </div>
      <h2 className="mb-3 mt-8 text-lg font-semibold">Flujo de trabajo</h2>
      <ol className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {steps.map((s) => (
          <li key={s.href}>
            <Link href={s.href} className="block h-full rounded-lg border border-line bg-surface p-4 shadow-sm hover:border-brand">
              <p className="font-semibold">{s.title}</p>
              <p className="mt-1 text-sm text-muted">{s.text}</p>
            </Link>
          </li>
        ))}
      </ol>
    </>
  );
}
