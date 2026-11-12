"""Genera las salidas reales de la API que respaldan cada cifra del informe.

Uso (con la API local sin autenticación en el puerto 8040):

    cd api && AUTH_DISABLED=1 .venv/bin/uvicorn main:app --port 8040
    api/.venv/bin/python docs/informe/anexos/generar_salidas.py

Cada llamada se guarda en docs/informe/anexos/salidas/<nombre>.json con la
petición y la respuesta. Todos los datos son sintéticos (data/ejemplos/).
Supuestos declarados del ejemplo (no vienen de ninguna empresa):
  - LIE = 495 g, LSE = 505 g, nominal = 500 g (README de data/ejemplos).
  - Un subgrupo por turno: intervalo de muestreo h = 8 h.
  - Muestreo de aceptación: AQL 1 %, LTPD 6 %, alfa 5 %, beta 10 %, lote de 2000.
"""
import json
from pathlib import Path

import httpx

RAIZ = Path(__file__).resolve().parents[3]
DATOS = RAIZ / "data" / "ejemplos"
SALIDAS = Path(__file__).resolve().parent / "salidas"
SALIDAS.mkdir(exist_ok=True)
BASE = "http://localhost:8040"
cli = httpx.Client(base_url=BASE, timeout=120)


def guardar(nombre, ruta, peticion, respuesta):
    (SALIDAS / f"{nombre}.json").write_text(
        json.dumps({"ruta": ruta, "peticion": peticion, "respuesta": respuesta}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )


def post(nombre, ruta, cuerpo):
    r = cli.post(ruta, json=cuerpo)
    try:
        resp = r.json()
    except Exception:
        resp = {"status": r.status_code}
    if r.status_code != 200:
        resp = {"http_status": r.status_code, **(resp if isinstance(resp, dict) else {"body": resp})}
    guardar(nombre, ruta, cuerpo, resp)
    return resp


def parse(archivo):
    with open(DATOS / f"{archivo}.csv", "rb") as f:
        r = cli.post("/api/data/parse", files={"file": (f"{archivo}.csv", f, "text/csv")})
    resp = r.json()
    guardar(f"parse_{archivo}", "/api/data/parse", {"archivo": f"{archivo}.csv"}, resp)
    return resp["sheets"][0]


def columna(hoja, nombre):
    i = [c["name"] for c in hoja["columns"]].index(nombre)
    return [fila[i] for fila in hoja["rows"]]


def subgrupos_ancho(hoja, n):
    cols = [columna(hoja, f"x{k}") for k in range(1, n + 1)]
    return [[float(c[i]) for c in cols] for i in range(len(cols[0]))]


LIE, LSE, NOM = 495.0, 505.0, 500.0
CAUSA = "Boquilla obstruida (causa asignable ficticia del ejemplo sintético)"

# ---- Fase I y Fase II de variables -------------------------------------------------
h1 = parse("sintetico_fase1")
h2 = parse("sintetico_fase2")
g1 = subgrupos_ancho(h1, 5)
g2 = subgrupos_ancho(h2, 5)
et1 = [str(int(x)) for x in columna(h1, "subgrupo")]
et2 = [str(int(x)) for x in columna(h2, "subgrupo")]
WE = {"enabled": ["WE1", "WE2", "WE3", "WE4"]}

post("resumen_fase1", "/api/data/summary", {"subgroups": g1, "labels": et1})
f1_a = post("fase1_xbar_r_inicial", "/api/charts/variables",
            {"chart_type": "xbar_r", "phase": "I", "subgroups": g1, "labels": et1, "rules": {"enabled": ["WE1"]}})
f1_b = post("fase1_xbar_r_depurada", "/api/charts/variables",
            {"chart_type": "xbar_r", "phase": "I", "subgroups": g1, "labels": et1,
             "excluded": [{"index": 11, "label": "12", "cause": CAUSA}], "rules": {"enabled": ["WE1"]}})
post("fase1_xbar_r_depurada_we", "/api/charts/variables",
     {"chart_type": "xbar_r", "phase": "I", "subgroups": g1, "labels": et1,
      "excluded": [{"index": 11, "label": "12", "cause": CAUSA}], "rules": WE})
lim = f1_b["limits"]
post("fase2_xbar_r", "/api/charts/variables",
     {"chart_type": "xbar_r", "phase": "II", "subgroups": g2, "labels": et2, "limits": lim, "rules": {"enabled": ["WE1"]}})
post("fase2_xbar_r_we", "/api/charts/variables",
     {"chart_type": "xbar_r", "phase": "II", "subgroups": g2, "labels": et2, "limits": lim, "rules": WE})
# Contraste: Fase II con los límites de la Fase I sin depurar (muestra el efecto de no excluir la causa)
post("fase2_xbar_r_limites_sin_depurar", "/api/charts/variables",
     {"chart_type": "xbar_r", "phase": "II", "subgroups": g2, "labels": et2, "limits": f1_a["limits"],
      "rules": {"enabled": ["WE1"]}})
post("fase1_xbar_s_depurada", "/api/charts/variables",
     {"chart_type": "xbar_s", "phase": "I", "subgroups": g1, "labels": et1,
      "excluded": [{"index": 11, "label": "12", "cause": CAUSA}], "rules": {"enabled": ["WE1"]}})

# ---- Supuestos -------------------------------------------------------------------
valores_f1 = [x for i, s in enumerate(g1) if i != 11 for x in s]
valores_f1_todos = [x for s in g1 for x in s]
post("supuestos_fase1_depurada", "/api/assumptions", {"values": valores_f1})
post("supuestos_fase1_con_subgrupo12", "/api/assumptions", {"values": valores_f1_todos})

# ---- Capacidad -------------------------------------------------------------------
g1_dep = [s for i, s in enumerate(g1) if i != 11]
post("capacidad_fase1_depurada", "/api/capability",
     {"subgroups": g1_dep, "lsl": LIE, "usl": LSE, "target": NOM, "limits": lim,
      "is_stable": True, "is_normal": True})
post("capacidad_fase2_limites_fase1", "/api/capability",
     {"subgroups": g2, "lsl": LIE, "usl": LSE, "target": NOM, "limits": lim,
      "is_stable": False})
post("capacidad_fase2_rbar", "/api/capability",
     {"subgroups": g2, "lsl": LIE, "usl": LSE, "target": NOM, "sigma_method": "rbar_d2", "is_stable": False})

# ---- Diseño: ARL / ATS ------------------------------------------------------------
H = 8.0
for n in (3, 5, 10):
    post(f"arl_xbar_n{n}_h8", "/api/design/arl",
         {"chart": "xbar", "n": n, "limit_width": 3.0, "sampling_interval": H,
          "shifts": [0.5, 1.0, 1.5, 2.0, 3.0]})
post("arl_xbar_n5_h8_we", "/api/design/arl",
     {"chart": "xbar", "n": 5, "limit_width": 3.0, "sampling_interval": H, "shifts": [0.5, 1.0, 1.5, 2.0, 3.0],
      "rules": WE, "max_runs": 5000, "seed": 12345})
post("comparar_disenos_1_5_sigma", "/api/design/compare",
     {"n_values": [3, 5, 8, 10], "limit_widths": [3.0], "sampling_intervals": [2.0, 4.0, 8.0], "shift": 1.5})
post("arl_p_n100", "/api/design/arl",
     {"chart": "p", "n": 100, "limit_width": 3.0, "sampling_interval": H, "p0": 0.048})

# ---- Atributos -------------------------------------------------------------------
hp = parse("sintetico_p_n_variable")
cuentas = [float(x) for x in columna(hp, "defectuosos")]
tam = [float(x) for x in columna(hp, "tamano_muestra")]
etp = [str(int(x)) for x in columna(hp, "subgrupo")]
post("resumen_atributos_p", "/api/data/summary/attributes", {"counts": cuentas, "sizes": tam, "labels": etp})
post("recomendar_p", "/api/charts/attributes/recommend", {"counting": "defectives", "constant_size": False})
p_a = post("p_fase1_inicial", "/api/charts/attributes",
           {"chart_type": "p", "phase": "I", "counts": cuentas, "sizes": tam, "labels": etp,
            "rules": {"enabled": ["WE1"]}})
post("p_fase1_depurada", "/api/charts/attributes",
     {"chart_type": "p", "phase": "I", "counts": cuentas, "sizes": tam, "labels": etp,
      "excluded": [{"index": 7, "label": "8", "cause": "Causa ficticia del ejemplo sintético: lote de envases defectuoso"},
                   {"index": 19, "label": "20", "cause": "Causa ficticia del ejemplo sintético: ajuste del sellador"}],
      "rules": {"enabled": ["WE1"]}})

# ---- Muestreo de aceptación --------------------------------------------------------
post("muestreo_simple_diseno", "/api/sampling/single/design",
     {"aql": 0.01, "alpha": 0.05, "ltpd": 0.06, "beta": 0.10, "lot_size": 2000, "distribution": "binomial"})
post("muestreo_doble_evaluacion", "/api/sampling/double/evaluate",
     {"n1": 50, "c1": 0, "r1": 3, "n2": 50, "c2": 2, "lot_size": 2000, "aql": 0.01, "ltpd": 0.06})

# ---- Otros archivos del manual -------------------------------------------------------
hs = parse("sintetico_sucio")
hn = parse("sintetico_no_normal")
ha = parse("sintetico_autocorrelado")
# Subgrupos del archivo sucio: se omiten las celdas faltantes, como hace la web al formar subgrupos
def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)
sub_sucio = [[float(v) for v in fila[3:8] if _num(v)] for fila in hs["rows"]]
post("resumen_sucio", "/api/data/summary", {"subgroups": sub_sucio, "labels": [str(int(f[2])) for f in hs["rows"]]})
post("supuestos_no_normal", "/api/assumptions", {"values": [float(x) for x in columna(hn, "valor")]})
post("supuestos_autocorrelado", "/api/assumptions", {"values": [float(x) for x in columna(ha, "valor")]})
hi = parse("sintetico_i_mr")
vi = [[float(x)] for x in columna(hi, "valor")]
post("imr_ejemplo", "/api/charts/variables", {"chart_type": "i_mr", "phase": "I", "subgroups": vi})
hc = parse("sintetico_c")
post("c_ejemplo", "/api/charts/attributes",
     {"chart_type": "c", "phase": "I", "counts": [float(x) for x in columna(hc, "defectos")]})
print("listo", len(list(SALIDAS.glob('*.json'))), "archivos")
