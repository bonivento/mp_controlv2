/**
 * Identidad de marca de Sigmalena.
 *
 * La paleta es la de la Universidad del Magdalena (https://cdn.unimagdalena.edu.co/, sección
 * Colores). Los tokens de interfaz viven en app/globals.css como variables CSS; este archivo
 * repite los mismos valores para el código que no puede leer CSS (los gráficos de Plotly) y
 * para los metadatos. Si cambias un color, cámbialo en los dos sitios.
 */

export const BRAND_NAME = "Sigmalena";
export const BRAND_DESCRIPTOR = "Control estadístico de procesos";
export const BRAND_TITLE = `${BRAND_NAME} · ${BRAND_DESCRIPTOR}`;
export const BRAND_DESCRIPTION =
  "Gráficos de control, capacidad de proceso, diseño de cartas y muestreo de aceptación para ingeniería de calidad.";
export const UNIVERSITY_NAME = "Universidad del Magdalena";

/** Pasos de la paleta institucional (nombre → hexadecimal). */
export const palette = {
  azul: { base: "#004A87", claro: "#0183EF", medio: "#005CAB", oscuro: "#003A6B", profundo: "#00294B" },
  naranja: { base: "#FF9400", medio: "#D17900", oscuro: "#A56000", profundo: "#744300" },
  lima: { base: "#A5CA00", brillante: "#CFFD00", medio: "#829F00", oscuro: "#5C7000" },
  verde: { base: "#00A50B", brillante: "#00F510", medio: "#00CB0D", oscuro: "#008209", profundo: "#005C06" },
  violeta: { base: "#240090", brillante: "#3D01F1", medio: "#2D00B2", oscuro: "#1D0072", profundo: "#140050" },
  amarillo: { base: "#D1AE00", brillante: "#FFD500", medio: "#A58A00", oscuro: "#746100" },
  rojo: { base: "#D10500", brillante: "#FF0700", medio: "#A50400", oscuro: "#740300" },
} as const;
