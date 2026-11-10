# Datos sintéticos de prueba (`data/ejemplos/`)

**Todos los datos de esta carpeta son sintéticos.** Los genera `data/generar_ejemplos.py` con semilla fija; no provienen de una empresa real. Cada archivo lleva el prefijo `sintetico_` y existe en CSV (UTF-8, separador coma, punto decimal) y en XLSX (una hoja llamada `datos`).

## Ambientación

Llenado de envases de 500 g de salsa en una línea manufacturera.

- Especificaciones: nominal 500 g, **LIE 495 g, LSE 505 g**.
- Proceso estable: media 500 g, desviación individual σ = 1,2 g (Cp ≈ 1,39, Cpk ≈ 1,39 centrado).
- Turnos: Mañana, Tarde, Noche. Cada tres subgrupos avanza un día, desde el 2026-03-02.
- Columnas de variables: `fecha`, `turno`, `subgrupo`, `x1`..`xn`. Para individuales, una sola columna `valor`.
- Columnas de atributos: `fecha`, `turno`, `subgrupo` y las de conteo y tamaño que correspondan.

Los resultados de las columnas "esperado" salen de cálculos independientes sobre estos mismos archivos (límites de 3σ con las constantes de Montgomery). Son el comportamiento que debería verse al cargar cada archivo. Si el software difiere, revisar primero el archivo y luego el cálculo.

## Archivos

| Archivo | Filas × columnas (CSV) | Qué contiene | Resultado esperado al cargarlo |
|---|---|---|---|
| `sintetico_xbar_r_en_control` | 25 × 8 | 25 subgrupos de n = 5, proceso estable | X-barra y R dentro de control. Límites X-barra aprox. 498,34 y 501,43; R-barra 2,675. Sin puntos fuera. |
| `sintetico_xbar_r_desplazamiento` | 25 × 8 | Igual que el anterior; desde el subgrupo 16 la media sube 1,5σ (1,8 g). Los subgrupos 1 a 15 son idénticos a `en_control`. | Límites iguales a `en_control`. Fuera de control: subgrupos **16, 18 y 20**. Sólo 3 de 10 se detectan; es lo normal con un desplazamiento de 1,5σ en n = 5. |
| `sintetico_xbar_s_n10` | 25 × 13 | 25 subgrupos de n = 10 | S-barra aprox. 1,29. Sin puntos fuera en X-barra ni en S. Probar que n = 10 usa S y no R. |
| `sintetico_i_mr` | 60 × 4 | 60 individuales (`valor`). Desde la observación 46 hay una tendencia ascendente de 0,2 g por observación. | MR-barra aprox. 1,67; límites I aprox. 495,9 y 504,8; LSC de MR 5,46. Sólo el MR de la observación **16** sale fuera de control. Ningún individual sale de sus límites, pero la media de las observaciones 46 a 60 (aprox. 501,4) contra 499,97 de las primeras 45 muestra la tendencia. La regla de 8 consecutivos de un lado **no** se cumple, así que el software no debe prometer marcarla con las reglas básicas. |
| `sintetico_p_n_variable` | 30 × 5 | 30 muestras con n entre 80 y 120 (`tamano_muestra`). Dos muestras con 14 % defectuosos. | p-barra aprox. 0,048. Fuera de control: muestras **8 y 20**. Los límites cambian por muestra (más anchos cuando n es chico). |
| `sintetico_np` | 30 × 5 | 30 muestras de n = 100 | np-barra aprox. 3,1; LCL 0; UCL aprox. 8,3. Sin puntos fuera. |
| `sintetico_c` | 30 × 4 | 30 unidades, `defectos` por unidad | c-barra 2,5; UCL aprox. 7,24; LCL 0. Fuera: unidad **18** (9 defectos). |
| `sintetico_u_n_variable` | 30 × 5 | 30 muestras con `unidades_inspeccion` entre 4 y 10 | u-barra aprox. 0,76. Fuera: muestras **10 y 23**. Los límites dependen de cada `unidades_inspeccion`. |
| `sintetico_fase1` | 25 × 8 | 25 subgrupos de n = 5 para fijar límites de Fase I. El subgrupo **12** tiene +3 g (causa asignable, por ejemplo boquilla obstruida). | Fase I: el subgrupo 12 sale fuera. Tras documentar la causa y excluirlo, recalcular: límites aprox. 498,1 y 501,7 con R-barra aprox. 3,06 (antes de excluir). |
| `sintetico_fase2` | 15 × 8 | 15 subgrupos posteriores al mismo proceso, con desplazamiento de 1,5σ (+1,8 g). Continúan la fecha de `fase1`. | Contra los límites congelados de `fase1`: fuera de control **11 de 15**, subgrupos 26, 28, 30 a 36, 38 y 39. Es la prueba de que Fase II detecta el cambio sin recalcular límites. |
| `sintetico_no_normal` | 80 × 4 | 80 tiempos de llenado en segundos (`valor`), distribución lognormal | Media 3,12, mediana 2,88, asimetría aprox. 1,5. La prueba de normalidad debe rechazar (p muy pequeño) y el software debe advertirlo en supuestos. |
| `sintetico_autocorrelado` | 60 × 4 | 60 observaciones AR(1), φ = 0,7 (`valor`) | Autocorrelación de orden 1 aprox. 0,70. La prueba de independencia debe advertir; los límites I-MR no son confiables sin tratar la autocorrelación. |
| `sintetico_sucio` | 20 × 8 | Mismo tipo de datos que `xbar_r` con problemas de captura (ver abajo) | Debe cargarse con advertencias en la bitácora de limpieza, sin errores fatales. |

### Problemas de `sintetico_sucio`

| Ubicación | Problema | Tratamiento esperado |
|---|---|---|
| Subgrupo 3, x2 | Celda vacía | Se registra como faltante; el subgrupo queda con n = 4 o se excluye, con aviso |
| Subgrupo 7, x4 | Celda vacía | Igual que el anterior |
| Subgrupo 11, x1 | Texto `N/D` en columna numérica | Se convierte en faltante, con aviso |
| Subgrupo 14, x3 | Coma decimal `500,8` | Se interpreta como 500,8 |
| Subgrupo 17, x5 | Coma decimal `497,7` | Se interpreta como 497,7 |
| Subgrupo 9, x5 | Valor absurdo `5050.0` (decimal mal capturado) | Se marca como atípico y no se borra en silencio; el usuario decide con justificación |
| Subgrupo 5, turno | Espacios alrededor de `Tarde` | Se normaliza a `Tarde` |
| Subgrupo 16, turno | Turno vacío | Se registra como faltante |
| Subgrupo 12, fecha | Fecha en formato `05/03/2026` (día/mes/año) | Se convierte a fecha, con aviso de formato |

Las celdas con coma decimal están escritas como texto, igual que en Excel con configuración regional española.

## Regenerar

Desde la raíz del proyecto:

```bash
"api/.venv/bin/python" data/generar_ejemplos.py
```

Produce los mismos datos (los CSV son idénticos byte a byte; los XLSX cambian solo su marca de fecha de creación). Si cambia algún parámetro, actualizar también la tabla anterior.
