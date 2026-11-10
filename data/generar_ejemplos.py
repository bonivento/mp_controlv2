#!/usr/bin/env python3
"""Genera los datos sintéticos de prueba del software CEP.

Ambientación: llenado de envases de 500 g de salsa en una línea manufacturera.
Especificaciones: nominal 500 g, LIE 495 g, LSE 505 g (tolerancia ±5 g).
Proceso estable: media 500 g, desviación individual sigma = 1,2 g (Cp = 1,39).

Todos los archivos llevan el prefijo `sintetico_` y se escriben en CSV y en XLSX
dentro de `data/ejemplos/`. La semilla es fija: ejecutar el script dos veces
produce archivos idénticos.

Uso (desde la raíz del proyecto):
    "api/.venv/bin/python" data/generar_ejemplos.py

Solo usa la biblioteca estándar y openpyxl.
"""

from __future__ import annotations

import csv
import datetime as dt
import math
import random
from pathlib import Path

from openpyxl import Workbook

SEMILLA = "CEP-2026"
DESTINO = Path(__file__).resolve().parent / "ejemplos"

MEDIA = 500.0       # g, media del proceso estable
SIGMA = 1.2         # g, desviación estándar individual del proceso estable
LIE, LSE = 495.0, 505.0
TURNOS = ["Mañana", "Tarde", "Noche"]
FECHA_BASE = dt.date(2026, 3, 2)  # lunes; cada tres subgrupos avanza un día


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def generador(nombre: str) -> random.Random:
    """Generador con semilla estable por caso (no depende del orden de ejecución)."""
    return random.Random(f"{SEMILLA}-{nombre}")


def fecha_de(i: int) -> dt.date:
    """Fecha del subgrupo i (base 0)."""
    return FECHA_BASE + dt.timedelta(days=i // 3)


def turno_de(i: int) -> str:
    return TURNOS[i % 3]


def poisson(rng: random.Random, lam: float) -> int:
    """Muestra de Poisson por el método de Knuth (lambda pequeña)."""
    limite, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limite:
            return k
        k += 1


def binomial(rng: random.Random, n: int, p: float) -> int:
    return sum(1 for _ in range(n) if rng.random() < p)


def normal_matriz(rng: random.Random, filas: int, columnas: int,
                  media: float = MEDIA, sigma: float = SIGMA) -> list[list[float]]:
    return [[round(rng.gauss(media, sigma), 2) for _ in range(columnas)]
            for _ in range(filas)]


def filas_subgrupos(matriz: list[list]) -> list[list]:
    """Fila de variables: fecha, turno, subgrupo y x1..xn."""
    return [[fecha_de(i), turno_de(i), i + 1, *fila] for i, fila in enumerate(matriz)]


def cabecera_subgrupos(n: int) -> list[str]:
    return ["fecha", "turno", "subgrupo", *[f"x{j}" for j in range(1, n + 1)]]


def escribir(nombre: str, cabecera: list[str], filas: list[list], formato_fecha: bool = True) -> None:
    """Escribe el mismo contenido en CSV (UTF-8, coma, punto decimal) y en XLSX."""
    DESTINO.mkdir(parents=True, exist_ok=True)

    with open(DESTINO / f"{nombre}.csv", "w", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f)
        escritor.writerow(cabecera)
        for fila in filas:
            escritor.writerow([v.isoformat() if isinstance(v, dt.date) else v for v in fila])

    libro = Workbook()
    hoja = libro.active
    hoja.title = "datos"
    hoja.append(cabecera)
    for fila in filas:
        hoja.append(fila)
    if formato_fecha:
        for celda in hoja["A"][1:]:
            celda.number_format = "yyyy-mm-dd"
    for columna in hoja.columns:
        ancho = max(len(str(c.value)) if c.value is not None else 0 for c in columna)
        hoja.column_dimensions[columna[0].column_letter].width = max(10, ancho + 2)
    libro.save(DESTINO / f"{nombre}.xlsx")


# ---------------------------------------------------------------------------
# Casos
# ---------------------------------------------------------------------------

def caso_xbar_r() -> None:
    rng = generador("xbar_r")
    base = normal_matriz(rng, 25, 5)
    escribir("sintetico_xbar_r_en_control", cabecera_subgrupos(5), filas_subgrupos(base))

    # Salto de media de 1,5 sigma desde el subgrupo 16 (base 1). Los primeros 15 son idénticos.
    desplazado = [fila[:] for fila in base]
    for i in range(15, 25):
        desplazado[i] = [round(v + 1.5 * SIGMA, 2) for v in desplazado[i]]
    escribir("sintetico_xbar_r_desplazamiento", cabecera_subgrupos(5), filas_subgrupos(desplazado))


def caso_xbar_s() -> None:
    rng = generador("xbar_s")
    matriz = normal_matriz(rng, 25, 10)
    escribir("sintetico_xbar_s_n10", cabecera_subgrupos(10), filas_subgrupos(matriz))


def caso_i_mr() -> None:
    rng = generador("i_mr")
    valores = []
    for i in range(60):
        v = rng.gauss(MEDIA, SIGMA)
        if i >= 45:  # tendencia ascendente en las últimas 15 observaciones
            v += 0.2 * (i - 44)
        valores.append([round(v, 2)])
    escribir("sintetico_i_mr", ["fecha", "turno", "subgrupo", "valor"], filas_subgrupos(valores))


def caso_p() -> None:
    rng = generador("p")
    filas = []
    for i in range(30):
        n = rng.randint(80, 120)
        if i in (7, 19):  # dos muestras con fracción defectuosa alta
            d = round(0.14 * n)
        else:
            d = binomial(rng, n, 0.04)
        filas.append([fecha_de(i), turno_de(i), i + 1, d, n])
    escribir("sintetico_p_n_variable",
             ["fecha", "turno", "subgrupo", "defectuosos", "tamano_muestra"], filas)


def caso_np() -> None:
    rng = generador("np")
    filas = [[fecha_de(i), turno_de(i), i + 1, binomial(rng, 100, 0.03), 100] for i in range(30)]
    escribir("sintetico_np", ["fecha", "turno", "subgrupo", "defectuosos", "tamano_muestra"], filas)


def caso_c() -> None:
    rng = generador("c")
    conteos = [poisson(rng, 2.5) for _ in range(30)]
    conteos[17] = 9  # una unidad con nueve defectos (causa asignable: boquilla obstruida)
    filas = [[fecha_de(i), turno_de(i), i + 1, c] for i, c in enumerate(conteos)]
    escribir("sintetico_c", ["fecha", "turno", "subgrupo", "defectos"], filas)


def caso_u() -> None:
    rng = generador("u")
    filas = []
    for i in range(30):
        unidades = rng.randint(4, 10)
        if i in (9, 22):  # dos muestras con tasa de defectos alta
            d = round(2.2 * unidades)
        else:
            d = poisson(rng, 0.6 * unidades)
        filas.append([fecha_de(i), turno_de(i), i + 1, d, unidades])
    escribir("sintetico_u_n_variable",
             ["fecha", "turno", "subgrupo", "defectos", "unidades_inspeccion"], filas)


def caso_fase() -> None:
    """Mismo proceso en dos fases. Fase I: 25 subgrupos con un punto de causa asignable.
    Fase II: 15 subgrupos posteriores con desplazamiento de 1,5 sigma."""
    rng = generador("fase")
    matriz = normal_matriz(rng, 40, 5)

    fase1 = [fila[:] for fila in matriz[:25]]
    # Causa asignable documentada: subgrupo 12 con +3 g en todas las medidas (boquilla parcialmente obstruida).
    fase1[11] = [round(v + 3.0, 2) for v in fase1[11]]

    fase2 = [[round(v + 1.5 * SIGMA, 2) for v in fila] for fila in matriz[25:40]]

    escribir("sintetico_fase1", cabecera_subgrupos(5), filas_subgrupos(fase1))
    escribir("sintetico_fase2", cabecera_subgrupos(5),
             [[fecha_de(25 + i), turno_de(25 + i), 26 + i, *fila] for i, fila in enumerate(fase2)])


def caso_no_normal() -> None:
    """Tiempo de llenado de cada envase en segundos: distribución lognormal (sesgada a la derecha)."""
    rng = generador("no_normal")
    valores = [[round(rng.lognormvariate(math.log(3.0), 0.45), 2)] for _ in range(80)]
    escribir("sintetico_no_normal", ["fecha", "turno", "subgrupo", "valor"], filas_subgrupos(valores))


def caso_autocorrelado() -> None:
    """AR(1) con phi = 0,7 y desviación marginal sigma."""
    rng = generador("autocorrelado")
    phi = 0.7
    sigma_eps = SIGMA * math.sqrt(1 - phi ** 2)
    x = MEDIA + rng.gauss(0, SIGMA)
    valores = []
    for _ in range(60):
        x = MEDIA + phi * (x - MEDIA) + rng.gauss(0, sigma_eps)
        valores.append([round(x, 2)])
    escribir("sintetico_autocorrelado", ["fecha", "turno", "subgrupo", "valor"],
             filas_subgrupos(valores))


def caso_sucio() -> None:
    """Mismo proceso que los xbar, con problemas típicos de captura en planta."""
    rng = generador("sucio")
    matriz = normal_matriz(rng, 20, 5)
    filas = []
    for i, fila in enumerate(matriz):
        celdas: list = [fecha_de(i), turno_de(i), i + 1, *fila]
        filas.append(celdas)

    def coma(v: float) -> str:
        return f"{v:.1f}".replace(".", ",")

    filas[2][4] = ""                      # subgrupo 3, x2 vacía
    filas[6][6] = ""                      # subgrupo 7, x4 vacía
    filas[10][3] = "N/D"                  # subgrupo 11, x1 con texto
    filas[13][5] = coma(matriz[13][2])    # subgrupo 14, x3 con coma decimal
    filas[16][7] = coma(matriz[16][4])    # subgrupo 17, x5 con coma decimal
    filas[8][7] = 5050.0                  # subgrupo 9, x5: valor absurdo (decimal mal capturado)
    filas[4][1] = " Tarde "               # subgrupo 5, turno con espacios
    filas[15][1] = ""                     # subgrupo 16, turno vacío
    filas[11][0] = fecha_de(11).strftime("%d/%m/%Y")  # subgrupo 12, fecha como texto

    escribir("sintetico_sucio", cabecera_subgrupos(5), filas, formato_fecha=False)


def main() -> None:
    caso_xbar_r()
    caso_xbar_s()
    caso_i_mr()
    caso_p()
    caso_np()
    caso_c()
    caso_u()
    caso_fase()
    caso_no_normal()
    caso_autocorrelado()
    caso_sucio()
    print(f"Archivos escritos en {DESTINO}")


if __name__ == "__main__":
    main()
