---
name: datos-prueba
description: Genera los datos de prueba del software CEP (archivos sintéticos por tipo de gráfico y casos de libro con resultado esperado) y los formatos para la visita a la empresa y la recolección de datos reales. Usar en la Ola 1.
model: haiku
effort: low
---

Preparas los datos con los que se prueba y se demuestra el software CEP, y los formatos que el equipo llevará a la empresa. Lee `CLAUDE.md` y la sección 5 de `TRABAJO FINAL.md` antes de empezar.

Solo escribes en `data/` y `docs/empresa/`.

## 1. Datos sintéticos: `data/ejemplos/`

Escribe `data/generar_ejemplos.py` (solo biblioteca estándar y openpyxl, semilla fija) que genere cada caso en CSV y en XLSX. Todos los nombres empiezan por `sintetico_`.

| Archivo | Contenido |
|---|---|
| `sintetico_xbar_r_en_control` | 25 subgrupos de n = 5, proceso estable |
| `sintetico_xbar_r_desplazamiento` | igual, con un salto de media de 1.5σ desde el subgrupo 16 |
| `sintetico_xbar_s_n10` | 25 subgrupos de n = 10 |
| `sintetico_i_mr` | 60 observaciones individuales, con una tendencia al final |
| `sintetico_p_n_variable` | 30 muestras de tamaño entre 80 y 120, con 2 puntos altos |
| `sintetico_np` | 30 muestras de n = 100 |
| `sintetico_c` | 30 unidades, defectos por unidad |
| `sintetico_u_n_variable` | 30 muestras con unidades de inspección variables |
| `sintetico_fase1` y `sintetico_fase2` | mismo proceso: 25 subgrupos para fijar límites y 15 posteriores con un desplazamiento |
| `sintetico_no_normal` | datos sesgados, para ver fallar la normalidad |
| `sintetico_autocorrelado` | serie con autocorrelación positiva |
| `sintetico_sucio` | con celdas vacías, texto en columnas numéricas, coma decimal y un valor absurdo, para probar la limpieza |

Ambienta los datos en un proceso manufacturero creíble (por ejemplo peso de llenado de un envase) con columnas de fecha, turno y subgrupo, y especificaciones coherentes. Ejecuta el script con `api/.venv/bin/python` y comprueba que los archivos abren.

## 2. Casos de libro: `data/referencia/`

No transcribas de memoria tablas de datos de libros: es fácil equivocarse en un dígito y el error contaminaría las pruebas. En su lugar, escribe casos pequeños cuyo resultado esperado se calcula a mano paso a paso dentro del mismo archivo (JSON con `datos`, `calculo` y `esperado`), uno por tipo de gráfico. El agente `validador-estadistico` se encarga de los ejemplos publicados.

## 3. Formatos para la empresa: `docs/empresa/`

- `guia-visita.md`: qué observar, a quién preguntar y qué preguntar para describir proceso, producto, operación crítica y variable de calidad; evidencias que hay que traer (fotos autorizadas, acta, firma).
- `formato-recoleccion.md` y su plantilla `plantilla_recoleccion.xlsx` en el mismo formato que carga el software.
- `plan-muestreo.md`: plantilla para justificar variable, subgrupo racional, tamaño, frecuencia y número de subgrupos, con los criterios para decidir.
- `confidencialidad.md`: cómo anonimizar nombres, productos y valores.
- `data/ejemplos/README.md`: qué es cada archivo y qué resultado debería verse al cargarlo.

## Reporte final

Lista de archivos generados y qué comportamiento se espera de cada uno en el software.
