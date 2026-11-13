"use client";

import { palette } from "@/lib/brand";
import { createContext, useContext, useSyncExternalStore } from "react";

// Paleta de gráficos: la de la Universidad del Magdalena (lib/brand.ts), validada con el
// script de la habilidad dataviz.
//  - serie 1 = azul base, para los datos; las demás series (curvas OC, ARL…) siguen un orden
//    fijo azul, naranja, violeta, verde, amarillo, y además se distinguen por el trazo.
//  - el rojo de la paleta es solo para señales fuera de control (rombo con la regla escrita).
//  - límites en naranja oscuro (discontinuos en Fase I, continuos y más gruesos en Fase II);
//    línea central en gris azulado continuo y fino; excluidos como cruz gris.
//  Nada depende solo del color: forma (rombo, cruz), trazo y texto acompañan a cada uno.
//  Notas de validación: el azul #004A87 es deliberadamente más oscuro que la banda de
//  luminosidad de la habilidad (L 0,41 frente a 0,43); es la identidad de marca. En el modo
//  oscuro se usan pasos más claros de la misma paleta para llegar a ≥ 3:1 sobre la superficie.
const { azul, naranja, violeta, verde, amarillo, rojo } = palette;
export interface ChartTheme {
  ink: string;
  muted: string;
  grid: string;
  surface: string;
  series: string[];
  signal: string;
  excluded: string;
  limit: string;
  center: string;
  band: string;
  spec: string;
}
const light: ChartTheme = {
  ink: "#0b1b2b",
  muted: "#475a6e",
  grid: "#e1e8f0",
  surface: "#ffffff",
  series: [azul.base, naranja.medio, violeta.brillante, verde.oscuro, amarillo.medio],
  signal: rojo.base,
  excluded: "#5b6b7d",
  limit: naranja.oscuro,
  center: "#475a6e",
  band: "rgba(0,74,135,0.10)",
  spec: naranja.oscuro,
};
const dark: ChartTheme = {
  ink: "#e8eff7",
  muted: "#9db0c4",
  grid: "#223a52",
  surface: "#0f1e2e",
  series: [azul.claro, naranja.base, "#9d86ff", verde.medio, amarillo.brillante],
  signal: "#ff6a64",
  excluded: "#9db0c4",
  limit: naranja.base,
  center: "#9db0c4",
  band: "rgba(1,131,239,0.18)",
  spec: naranja.base,
};


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
