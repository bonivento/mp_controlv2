"use client";

import { createContext, useContext, useSyncExternalStore } from "react";

// Paleta de gráficos (skill dataviz, paleta de referencia): serie 1 azul para los
// datos; el rojo de estado (crítico) solo para señales; grises de tinta para
// límites y líneas centrales. El modo oscuro usa los pasos de ese modo.
const light = {
  ink: "#14171c",
  muted: "#566070",
  grid: "#e3e6ec",
  surface: "#ffffff",
  series: ["#2a78d6", "#eb6834", "#1baf7a", "#6250d6", "#eda100", "#e87ba4"],
  signal: "#d03b3b",
  excluded: "#6b7280",
  limit: "#4b5563",
  band: "rgba(42,120,214,0.10)",
  spec: "#b45309",
};
const dark = {
  ink: "#eceef1",
  muted: "#a3abb8",
  grid: "#2a2f38",
  surface: "#171a20",
  series: ["#3987e5", "#d95926", "#199e70", "#9085e9", "#c98500", "#d55181"],
  signal: "#e66767",
  excluded: "#9ca3af",
  limit: "#b4bcc8",
  band: "rgba(57,135,229,0.16)",
  spec: "#e0a24a",
};

export type ChartTheme = typeof light;

function subscribe(cb: () => void) {
  const mq = window.matchMedia("(prefers-color-scheme: dark)");
  mq.addEventListener("change", cb);
  return () => mq.removeEventListener("change", cb);
}

/**
 * Opciones que un contenedor (la página de reporte) impone a todos los gráficos
 * que lleva dentro: tema claro aunque el sistema esté en oscuro (el reporte es un
 * documento para papel) y título solo en el pie APA, no dentro de la figura.
 */
export interface ChartMode {
  forceLight: boolean;
  titleInFigure: boolean;
}
export const ChartModeContext = createContext<ChartMode>({ forceLight: false, titleInFigure: true });
export const useChartMode = () => useContext(ChartModeContext);

export function useChartTheme(): ChartTheme {
  const { forceLight } = useChartMode();
  const isDark = useSyncExternalStore(
    subscribe,
    () => window.matchMedia("(prefers-color-scheme: dark)").matches,
    () => false,
  );
  return isDark && !forceLight ? dark : light;
}

const narrowQuery = "(max-width: 640px)";
function subscribeNarrow(cb: () => void) {
  const mq = window.matchMedia(narrowQuery);
  mq.addEventListener("change", cb);
  return () => mq.removeEventListener("change", cb);
}
/** Pantalla estrecha (móvil): los gráficos ceden margen lateral al área de trazado. */
export function useNarrow(): boolean {
  return useSyncExternalStore(subscribeNarrow, () => window.matchMedia(narrowQuery).matches, () => false);
}
