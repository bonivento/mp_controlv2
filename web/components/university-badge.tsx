/* eslint-disable @next/next/no-img-element -- el escudo es un PNG estático servido desde /public (también para imprimir a PDF). */
import { UNIVERSITY_NAME } from "@/lib/brand";

/**
 * Escudo de la Universidad del Magdalena como afiliación institucional. Se sirve copiado en
 * /public/brand (no desde el CDN) para que cargue sin red y salga en el PDF. Va sin deformar
 * ni recolorear: la versión «light» para fondos claros y la «dark» para fondos oscuros.
 * `tone="auto"` cambia según el tema del sistema; "light"/"dark" la fijan (el reporte es
 * siempre claro; el panel azul del acceso siempre usa la versión para fondo oscuro).
 */
export function UniversityShield({
  height = 28,
  tone = "auto",
  src = 128,
  className = "",
}: {
  height?: number;
  tone?: "auto" | "light" | "dark";
  src?: 128 | 192;
  className?: string;
}) {
  const path = (t: "light" | "dark") => `/brand/escudo-unimagdalena-${t}-${src}.png`;
  const width = Math.round(height * (src === 128 ? 132 / 128 : 198 / 192));
  const img = (
    <img
      src={path(tone === "dark" ? "dark" : "light")}
      alt={`Escudo de la ${UNIVERSITY_NAME}`}
      width={width}
      height={height}
      className={className}
      decoding="async"
    />
  );
  if (tone !== "auto") return img;
  return (
    <picture>
      <source media="(prefers-color-scheme: dark)" srcSet={path("dark")} />
      {img}
    </picture>
  );
}
