// Reglas de corrida (Western Electric y Nelson) para el motor de ejemplo.
// La detección se hace en el punto donde se completa la señal.

import type { components } from "../api-types";

type S = components["schemas"];
export type RuleId = NonNullable<S["RuleConfig"]["enabled"]>[number];

export const RULE_TEXT: Record<RuleId, string> = {
  WE1: "Un punto fuera de los límites de 3 sigma",
  WE2: "Dos de tres puntos consecutivos a más de 2 sigma del mismo lado",
  WE3: "Cuatro de cinco puntos consecutivos a más de 1 sigma del mismo lado",
  WE4: "Ocho puntos consecutivos del mismo lado de la línea central",
  N1: "Un punto a más de 3 sigma de la línea central",
  N2: "Nueve puntos consecutivos del mismo lado de la línea central",
  N3: "Seis puntos consecutivos en aumento o en descenso",
  N4: "Catorce puntos consecutivos alternando arriba y abajo",
  N5: "Dos de tres puntos consecutivos a más de 2 sigma del mismo lado",
  N6: "Cuatro de cinco puntos consecutivos a más de 1 sigma del mismo lado",
  N7: "Quince puntos consecutivos dentro de 1 sigma (estratificación)",
  N8: "Ocho puntos consecutivos a más de 1 sigma de ambos lados (mezcla)",
};

/**
 * ¿Se completa la regla `rule` en el punto i? `z` son los valores estandarizados
 * ((x - centro) / sigma del estadístico). `ucl`/`lcl` se usan en la regla 1 para
 * paneles con límites asimétricos o sigma variable.
 */
export function ruleFires(rule: RuleId, z: number[], i: number): boolean {
  const win = (len: number) => (i + 1 >= len ? z.slice(i + 1 - len, i + 1) : null);
  switch (rule) {
    case "WE1":
    case "N1":
      return Math.abs(z[i]) > 3;
    case "WE2":
    case "N5": {
      const w = win(3);
      return !!w && (w.filter((v) => v > 2).length >= 2 || w.filter((v) => v < -2).length >= 2) && Math.abs(z[i]) > 2;
    }
    case "WE3":
    case "N6": {
      const w = win(5);
      return !!w && (w.filter((v) => v > 1).length >= 4 || w.filter((v) => v < -1).length >= 4) && Math.abs(z[i]) > 1;
    }
    case "WE4": {
      const w = win(8);
      return !!w && (w.every((v) => v > 0) || w.every((v) => v < 0));
    }
    case "N2": {
      const w = win(9);
      return !!w && (w.every((v) => v > 0) || w.every((v) => v < 0));
    }
    case "N3": {
      const w = win(6);
      if (!w) return false;
      let up = true;
      let down = true;
      for (let k = 1; k < 6; k++) {
        if (!(w[k] > w[k - 1])) up = false;
        if (!(w[k] < w[k - 1])) down = false;
      }
      return up || down;
    }
    case "N4": {
      const w = win(14);
      if (!w) return false;
      for (let k = 2; k < 14; k++) if ((w[k] - w[k - 1]) * (w[k - 1] - w[k - 2]) >= 0) return false;
      return (w[1] - w[0]) * (w[2] - w[1]) < 0;
    }
    case "N7": {
      const w = win(15);
      return !!w && w.every((v) => Math.abs(v) < 1);
    }
    case "N8": {
      const w = win(8);
      return !!w && w.every((v) => Math.abs(v) > 1) && w.some((v) => v > 0) && w.some((v) => v < 0);
    }
    default:
      return false;
  }
}

/** Reglas válidas en paneles con límites asimétricos (R, S, MR, atributos): solo la 1. */
export const ONLY_BEYOND_LIMITS: RuleId[] = ["WE1", "N1"];
