"use client";

import { useSyncExternalStore } from "react";

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

export function useChartTheme(): ChartTheme {
  const isDark = useSyncExternalStore(
    subscribe,
    () => window.matchMedia("(prefers-color-scheme: dark)").matches,
    () => false,
  );
  return isDark ? dark : light;
}
