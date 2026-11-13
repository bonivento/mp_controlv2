import { BRAND_NAME, UNIVERSITY_NAME } from "@/lib/brand";
import { UniversityShield } from "./university-badge";

/** Pie de página discreto de toda la aplicación. No sale al imprimir (el reporte lleva su portada). */
export function SiteFooter() {
  return (
    <footer className="no-print border-t border-line bg-surface">
      <div className="mx-auto flex max-w-7xl items-center justify-center gap-2.5 px-4 py-3 text-xs text-muted sm:justify-between">
        <span className="flex items-center gap-2">
          <UniversityShield height={22} />
          <span>
            {BRAND_NAME} · {UNIVERSITY_NAME}
          </span>
        </span>
        <span className="hidden sm:inline">Control estadístico de procesos</span>
      </div>
    </footer>
  );
}
