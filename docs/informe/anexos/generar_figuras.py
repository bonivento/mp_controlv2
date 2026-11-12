"""Genera las figuras del informe a partir de las respuestas guardadas en salidas/.

Requiere matplotlib (entorno aparte, no api/.venv):
    uv venv /ruta/figenv && uv pip install --python /ruta/figenv/bin/python matplotlib
    /ruta/figenv/bin/python docs/informe/anexos/generar_figuras.py

No calcula nada estadístico: solo dibuja lo que devolvió la API. Datos sintéticos.
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

AQUI = Path(__file__).resolve().parent
SAL = AQUI / "salidas"
OUT = AQUI.parent / "figuras"
OUT.mkdir(exist_ok=True)

AZUL, ROJO, GRIS, VERDE, NARANJA = "#2B6CB0", "#B42318", "#6B7280", "#2F7D4F", "#B45309"
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": "#E5E7EB", "grid.linewidth": 0.6, "axes.titlesize": 10, "axes.titleweight": "bold",
    "figure.dpi": 100, "savefig.dpi": 200,
})


def L(n):
    return json.loads((SAL / f"{n}.json").read_text(encoding="utf-8"))["respuesta"]


def panel(ax, s, titulo, ylabel, excl=(), marcar=True):
    x = s["indices"]
    pos = [i + 1 for i in x]
    lab = [int(l) for l in s["labels"]]
    ax.step(lab, s["ucl"], where="mid", color=ROJO, lw=1.2, ls="--", label="Límites de control (LCS, LCI)")
    ax.step(lab, s["lcl"], where="mid", color=ROJO, lw=1.2, ls="--")
    ax.step(lab, s["center"], where="mid", color=GRIS, lw=1.2, label="Línea central")
    ax.plot(lab, s["values"], color=AZUL, lw=1.4, marker="o", ms=4, label="Subgrupo")
    viol = {v["index"] for v in s["violations"]}
    pts = [(l, v) for i, l, v in zip(x, lab, s["values"]) if i in viol]
    if pts:
        ax.plot(*zip(*pts), ls="none", marker="D", ms=8, mfc="none", mec=ROJO, mew=1.8, label="Señal")
    ex = [(l, v) for i, l, v in zip(x, lab, s["values"]) if i in set(excl)]
    if ex:
        ax.plot(*zip(*ex), ls="none", marker="x", ms=9, color="#111827", mew=1.8, label="Excluido")
    ax.set_title(titulo, loc="left")
    ax.set_ylabel(ylabel)
    return ax


def guardar(fig, nombre):
    fig.tight_layout()
    fig.savefig(OUT / f"{nombre}.png")
    plt.close(fig)


# Figura 1: Fase I inicial
r = L("fase1_xbar_r_inicial")
fig, ax = plt.subplots(2, 1, figsize=(7.5, 5.6), sharex=True)
panel(ax[0], r["charts"][0], "Gráfico X-barra, Fase I (límites de prueba)", "Media del subgrupo (g)")
panel(ax[1], r["charts"][1], "Gráfico R, Fase I", "Rango (g)")
ax[1].set_xlabel("Subgrupo")
ax[0].legend(ncol=5, fontsize=7.5, loc="upper center", bbox_to_anchor=(0.5, 1.28), frameon=False)
guardar(fig, "fig01_fase1_inicial")

# Figura 2: Fase I depurada
r = L("fase1_xbar_r_depurada")
fig, ax = plt.subplots(2, 1, figsize=(7.5, 5.6), sharex=True)
panel(ax[0], r["charts"][0], "Gráfico X-barra, Fase I tras excluir el subgrupo 12", "Media del subgrupo (g)", excl=[11])
panel(ax[1], r["charts"][1], "Gráfico R, Fase I tras excluir el subgrupo 12", "Rango (g)", excl=[11])
ax[1].set_xlabel("Subgrupo")
ax[0].legend(ncol=5, fontsize=7.5, loc="upper center", bbox_to_anchor=(0.5, 1.28), frameon=False)
guardar(fig, "fig02_fase1_depurada")

# Figura 3: Fase II
r = L("fase2_xbar_r")
fig, ax = plt.subplots(2, 1, figsize=(7.5, 5.6), sharex=True)
panel(ax[0], r["charts"][0], "Gráfico X-barra, Fase II con límites congelados (reglas: un punto fuera)", "Media del subgrupo (g)")
panel(ax[1], r["charts"][1], "Gráfico R, Fase II con límites congelados", "Rango (g)")
ax[1].set_xlabel("Subgrupo")
ax[0].legend(ncol=5, fontsize=7.5, loc="upper center", bbox_to_anchor=(0.5, 1.28), frameon=False)
guardar(fig, "fig03_fase2")

# Figura 4: normalidad (histograma y Q-Q)
a = L("supuestos_fase1_depurada")
h = a["histogram"]
fig, ax = plt.subplots(1, 2, figsize=(7.5, 3.2))
anchos = [h["edges"][i + 1] - h["edges"][i] for i in range(len(h["counts"]))]
ax[0].bar(h["edges"][:-1], h["counts"], width=anchos, align="edge", color=AZUL, alpha=0.6, edgecolor="white")
ax[0].plot(h["normal_curve_x"], h["normal_curve_y"], color=NARANJA, lw=2, label="Normal ajustada")
ax[0].set_title("Histograma", loc="left"); ax[0].set_xlabel("Llenado (g)"); ax[0].set_ylabel("Frecuencia"); ax[0].legend(frameon=False)
t = [p["theoretical"] for p in a["qq"]]; o = [p["observed"] for p in a["qq"]]
ax[1].plot(t, o, "o", ms=3.5, color=AZUL, label="Observaciones")
lo, hi = min(t), max(t)
import statistics as st
m, sd = a["descriptive"]["mean"], a["descriptive"]["std"]
ax[1].plot([lo, hi], [m + sd * lo, m + sd * hi], color=NARANJA, lw=1.6, label="Recta normal (media y desviación)")
ax[1].set_title("Gráfico Q-Q normal", loc="left"); ax[1].set_xlabel("Cuantil teórico"); ax[1].set_ylabel("Cuantil observado (g)"); ax[1].legend(frameon=False, fontsize=7.5)
guardar(fig, "fig04_normalidad")

# Figura 5: ACF
ac = a["autocorrelation"]
fig, ax = plt.subplots(figsize=(7.5, 2.8))
cols = [ROJO if l in ac["significant_lags"] else AZUL for l in ac["lags"]]
ax.bar(ac["lags"], ac["values"], color=cols, width=0.6)
ax.axhline(ac["band"], color=GRIS, ls="--", lw=1); ax.axhline(-ac["band"], color=GRIS, ls="--", lw=1, label=f"Banda ±{ac['band']:.3f}")
ax.axhline(0, color="#111827", lw=0.8)
ax.set_xlabel("Rezago"); ax.set_ylabel("Autocorrelación"); ax.set_title("Función de autocorrelación, Fase I depurada (120 observaciones)", loc="left"); ax.legend(frameon=False)
ax.set_xticks(ac["lags"])
guardar(fig, "fig05_acf")

# Figura 6: capacidad
c = L("capacidad_fase1_depurada")
h = c["histogram"]
anchos = [h["edges"][i + 1] - h["edges"][i] for i in range(len(h["counts"]))]
fig, ax = plt.subplots(figsize=(7.5, 3.2))
ax.bar(h["edges"][:-1], h["counts"], width=anchos, align="edge", color=AZUL, alpha=0.6, edgecolor="white", label="Observaciones")
ax.plot(h["normal_curve_x"], h["normal_curve_y"], color=NARANJA, lw=2, label="Normal ajustada")
for v, nm in ((495, "LIE = 495"), (500, "Nominal = 500"), (505, "LSE = 505")):
    ax.axvline(v, color=ROJO if v != 500 else VERDE, ls="--" if v != 500 else ":", lw=1.5)
    ax.text(v, ax.get_ylim()[1] * 1.02, nm, va="bottom", ha="center", fontsize=8)
ax.set_xlim(493.5, 506.5)
ax.set_xlabel("Llenado (g)"); ax.set_ylabel("Frecuencia"); ax.set_title("Histograma con especificaciones, Fase I depurada", loc="left", pad=22); ax.legend(frameon=False, loc="upper left", bbox_to_anchor=(0.12, 0.98), fontsize=8)
guardar(fig, "fig06_capacidad")

# Figura 7: ARL1 frente al desplazamiento
fig, ax = plt.subplots(figsize=(7.5, 3.6))
estilos = {"arl_xbar_n3_h8": ("n = 3", GRIS, "s", "-"), "arl_xbar_n5_h8": ("n = 5", AZUL, "o", "-"), "arl_xbar_n10_h8": ("n = 10", VERDE, "^", "-"),
           "arl_xbar_n5_h8_we": ("n = 5, reglas WE1 a WE4 (simulación)", ROJO, "D", "--")}
for k, (nm, col, mk, ls) in estilos.items():
    d = L(k)
    ax.plot([x["shift"] for x in d["rows"]], [x["arl1"] for x in d["rows"]], color=col, marker=mk, ls=ls, label=nm)
ax.set_yscale("log"); ax.set_xlabel("Desplazamiento de la media (múltiplos de σ)"); ax.set_ylabel("ARL1 (muestras, escala log)")
ax.set_title("ARL1 del gráfico X-barra con L = 3", loc="left"); ax.legend(frameon=False, fontsize=8)
guardar(fig, "fig07_arl1")

# Figura 8: ATS1 frente a la carga muestral
d = L("comparar_disenos_1_5_sigma")
fig, ax = plt.subplots(figsize=(7.5, 3.6))
for n, col, mk in ((3, GRIS, "s"), (5, AZUL, "o"), (8, NARANJA, "v"), (10, VERDE, "^")):
    rows = sorted([r for r in d["rows"] if r["n"] == n], key=lambda r: r["sampling_load"])
    ax.plot([r["sampling_load"] for r in rows], [r["ats1"] for r in rows], color=col, marker=mk, label=f"n = {n}")
    for r in rows:
        ax.annotate(f"h={r['sampling_interval']:g}", (r["sampling_load"], r["ats1"]), fontsize=6.5, xytext=(3, 3), textcoords="offset points")
ax.set_yscale("log"); ax.set_xlabel("Carga muestral n/h (unidades por hora)"); ax.set_ylabel("ATS1 (h, escala log)")
ax.set_title("Detección de un desplazamiento de 1,5 σ frente a la carga de inspección", loc="left"); ax.legend(frameon=False, fontsize=8)
guardar(fig, "fig08_ats_carga")

# Figura 9: gráfico p
r = L("p_fase1_inicial")
s = r["charts"][0]
fig, ax = plt.subplots(figsize=(7.5, 3.4))
panel(ax, s, "Gráfico p, Fase I, n variable entre 81 y 120", "Fracción defectuosa")
ax.set_xlabel("Muestra"); ax.legend(ncol=5, fontsize=7.5, frameon=False, loc="upper center", bbox_to_anchor=(0.5, 1.25))
guardar(fig, "fig09_grafico_p")

# Figura 10: muestreo
m = L("muestreo_simple_diseno")
fig, ax = plt.subplots(1, 2, figsize=(7.5, 3.2))
ax[0].plot([p["x"] for p in m["oc_curve"]], [p["y"] for p in m["oc_curve"]], color=AZUL, lw=2)
ax[0].axvline(0.01, color=VERDE, ls=":", label="AQL = 1 %"); ax[0].axvline(0.06, color=ROJO, ls="--", label="LTPD = 6 %")
ax[0].set_title(f"Curva OC, n = {m['n']}, c = {m['c']}", loc="left"); ax[0].set_xlabel("Fracción defectuosa del lote"); ax[0].set_ylabel("Probabilidad de aceptación"); ax[0].legend(frameon=False, fontsize=8)
ax[1].plot([p["x"] for p in m["aoq_curve"]], [p["y"] for p in m["aoq_curve"]], color=AZUL, lw=2)
ax[1].plot([m["aoql_at"]], [m["aoql"]], "o", color=ROJO, label=f"AOQL = {m['aoql']*100:.2f} %")
ax[1].set_title("Calidad promedio de salida (AOQ)", loc="left"); ax[1].set_xlabel("Fracción defectuosa de entrada"); ax[1].set_ylabel("AOQ"); ax[1].legend(frameon=False, fontsize=8)
guardar(fig, "fig10_muestreo")
print("figuras:", sorted(p.name for p in OUT.glob("*.png")))
