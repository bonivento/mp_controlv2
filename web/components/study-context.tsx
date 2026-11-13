"use client";

import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import { createContext, useContext, type ReactNode } from "react";
import { getStore } from "@/lib/data";
import type { Study } from "@/lib/db";
import { useLoad } from "@/lib/use-load";
import { Alert, Badge, EmptyState, Loading } from "./ui";

interface Ctx {
  study: Study;
  refresh: () => void;
}
const StudyContext = createContext<Ctx | null>(null);

export function useStudy(): Ctx {
  const c = useContext(StudyContext);
  if (!c) throw new Error("useStudy debe usarse dentro de un estudio");
  return c;
}

const TABS_VARIABLE = [
  ["", "Resumen"],
  ["datos", "Datos"],
  ["variables", "Variables"],
  ["supuestos", "Supuestos"],
  ["capacidad", "Capacidad"],
  ["diseno", "Diseño"],
  ["muestreo", "Muestreo"],
  ["reporte", "Reporte"],
] as const;
const TABS_ATTRIBUTE = [
  ["", "Resumen"],
  ["datos", "Datos"],
  ["atributos", "Atributos"],
  ["diseno", "Diseño"],
  ["muestreo", "Muestreo"],
  ["reporte", "Reporte"],
] as const;

/** Carga el estudio de la URL, muestra su encabezado y la navegación por módulos. */
export function StudyShell({ children }: { children: ReactNode }) {
  const { id } = useParams<{ id: string }>();
  const pathname = usePathname();
  const { data: study, loading, error, reload } = useLoad(() => getStore().studies.get(id), [id]);

  if (loading && !study) return <Loading label="Cargando estudio…" />;
  if (error) return <Alert tone="error" title="No se pudo cargar el estudio">{error}</Alert>;
  if (!study)
    return (
      <EmptyState
        title="Estudio no encontrado"
        action={
          <Link href="/estudios" className="rounded-md bg-brand px-4 py-2 text-sm font-medium text-brand-ink">
            Volver a estudios
          </Link>
        }
      >
        Puede que se haya eliminado o que no pertenezca a tu cuenta.
      </EmptyState>
    );

  const tabs = study.data_type === "variable" ? TABS_VARIABLE : TABS_ATTRIBUTE;
  const base = `/estudios/${study.id}`;
  return (
    <StudyContext value={{ study, refresh: reload }}>
      <div className="no-print mb-5">
        <p className="text-sm">
          <Link href="/estudios" className="text-brand-text hover:underline">
            ← Estudios
          </Link>
        </p>
        <div className="mt-1 flex flex-wrap items-center gap-2">
          <h1 className="text-xl font-semibold">{study.name}</h1>
          <Badge tone="info">{study.data_type === "variable" ? "Variable" : "Atributo"}</Badge>
          {study.is_synthetic && <Badge tone="warn">Datos sintéticos</Badge>}
        </div>
        <nav aria-label="Módulos del estudio" className="mt-3 overflow-x-auto border-b border-line">
          <ul className="flex min-w-max gap-1">
            {tabs.map(([seg, label]) => {
              const href = seg ? `${base}/${seg}` : base;
              const active = seg ? pathname.startsWith(href) : pathname === base;
              return (
                <li key={label}>
                  <Link
                    href={href}
                    aria-current={active ? "page" : undefined}
                    className={`inline-block border-b-2 px-3 py-2 text-sm font-medium ${
                      active ? "border-accent font-semibold text-brand-text" : "border-transparent text-muted hover:text-ink"
                    }`}
                  >
                    {label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
      </div>
      {children}
    </StudyContext>
  );
}
