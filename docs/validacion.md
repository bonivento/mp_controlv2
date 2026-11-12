# Validación estadística del software CEP

Revisión independiente de `api/app/spc/` (once módulos, unas 6 000 líneas) hecha por el validador estadístico. La primera pasada (Ola 3) encontró los hallazgos H1 a H16 y las sospechas S1 a S5. La segunda pasada (2026-11-11), después de las correcciones de los autores, comprobó cada corrección con la misma desconfianza, midió otra vez coberturas y tamaños reales, revisó todos los textos de interpretación y registró los hallazgos nuevos H17 a H26 y las observaciones S6 a S8. El objetivo es comprobar que lo que calcula el software es correcto y que lo que afirma en sus interpretaciones está soportado por los datos. Sirve como evidencia de ejecución para el informe técnico.

> **Estado posterior a la segunda pasada (2026-11-12).** Los autores corrigieron los hallazgos H17 a H26 y atendieron la observación S6. Las 15 pruebas que los documentaban como fallo esperado pasan ahora y se les quitó la marca: la corrida completa da `953 passed, 1 skipped`, sin fallos esperados. Donde este documento dice "abierto" para H17 a H26, léase "corregido; verificado por la prueba ejecutable del hallazgo". Esas correcciones no tuvieron una tercera revisión independiente más allá de dichas pruebas. Siguen como observaciones sin cambio en el código S7 (parcialmente atendida en el texto del resumen de capacidad) y S8.

## 1. Método

1. **Recalcular por otro camino.** No se reutilizan las funciones ni las pruebas de los autores para obtener el valor esperado. Cada esperado sale de una de estas vías, todas en `api/tests/validation/independiente.py`:
   - otra integral (d2 por la esperanza del máximo, d3 por la densidad del rango, c4 por la media de la distribución chi);
   - fórmulas escritas a mano en la prueba (límites, índices, ARL exactos, probabilidades binomiales y de Poisson sumadas término a término);
   - implementaciones con bucles explícitos (las doce reglas de corrida);
   - cadenas de Markov propias (WE1 a WE4 y reglas de racha, también con empates sobre la línea central);
   - una ecuación integral resuelta en malla para el ARL de N3 y N4 con datos i.i.d. continuos (`arl_orden_iid`);
   - enumeración exhaustiva (distribución de rachas, búsqueda del plan de muestreo de menor n) y aritmética racional exacta con enteros grandes (valor p de rachas con más de 1 000 datos);
   - simulación Monte Carlo (cobertura de intervalos, tamaño real de las pruebas, grados de libertad efectivos por el coeficiente de variación, plan doble).
2. **Distinguir la fuente.** En cada tabla la columna "Fuente del esperado" dice si el valor coincide con un cálculo propio o con un valor publicado. No se usó ningún valor publicado que no se haya podido reproducir con un cálculo propio. Los datos de libro de las pruebas de los autores se transcribieron de memoria: solo se verificó su consistencia interna (totales y columnas derivadas) y se marca como **no verificable contra el libro** lo demás.
3. **Hallazgos como pruebas ejecutables.** Cada error confirmado tiene una prueba marcada `xfail(strict=True)` con el caso mínimo. Figura como "xfailed"; cuando se corrija el código pasará a XPASS y hará fallar la corrida, señal para quitar la marca. En la segunda pasada, 18 de las 20 pruebas de la primera pasaron a XPASS y los autores quitaron la marca. Las otras dos (`test_cobertura_con_rbar_d2` y `test_cobertura_con_limites_congelados`) estaban mal planteadas: se reescribieron y hoy pasan (sección 7). Hay 15 marcas nuevas, una por cada caso mínimo de H18 a H26.

### Cómo reproducir

```bash
cd api
.venv/bin/python -m pytest -q                       # 917 passed, 1 skipped, 15 xfailed (735 de los autores + 182 de validación)
.venv/bin/python -m pytest -q -rxX tests/validation  # detalle de los 15 hallazgos ejecutables abiertos
.venv/bin/python -m tests.validation.reporte        # imprime las tablas de las secciones 3 a 9
```

Entorno: Python 3.12, numpy 2.5.4, scipy 1.18.1, macOS. Todas las simulaciones usan semillas fijas. En las tablas de este documento los números van con punto decimal, como los devuelve la API en JSON. Los textos de interpretación del software usan coma decimal (por ejemplo "Cpk = 1,41"); `test_val_interpretacion.py::test_numeros_con_coma_decimal` lo comprueba en los textos de capacidad, supuestos, diseño, muestreo y gráficos, y en las descripciones de `rules.py` y `phases.py`.

## 2. Resumen por módulo

| Módulo | Qué se comprobó | Veredicto (segunda pasada) |
|---|---|---|
| `constants.py` | d2, d3 y c4 para n = 2 a 25 por otras integrales; los 14 factores del apéndice VI | Correcto (diferencias ≤ 5e-7) |
| `variables.py` | Límites de X-barra-R, X-barra-S e I-MR a mano; estimadores de sigma; truncamiento de LCI; MR con exclusiones; panel MR marcado como serialmente correlacionado | Correcto |
| `attributes.py` | p, np, c, u a mano; n variable con límites por punto; truncamientos en 0 y 1 | Correcto |
| `phases.py` | Excluidos fuera del cálculo y dentro del gráfico; Fase II sin recálculo; reconstrucción con otro n; L = 0 rechazado | Correcto (H16 corregido) |
| `rules.py` | 3 600 evaluaciones contra bucles; serie justa y a un punto por regla; ARL frente a cadenas de Markov; reglas por panel | Cálculo correcto. Criterio por panel correcto (H5). La advertencia de WE4 y N2 afirma "más falsas alarmas" también cuando la LC es un conteo posible y hay menos (H19); redacción (H25) |
| `assumptions.py` | Ljung-Box y ACF por FFT; rachas exactas para todo n; A² por otra fórmula; tamaño real por simulación | Correcto (H3 y H10 corregidos) |
| `capability.py` | Índices, fracción no conforme, una sola especificación, Cpm, ν efectivos, IC y cobertura real | Correcto (H1, H2, H14 corregidos; S2 resuelta). ν de I-MR congelado con exclusiones levemente alto (H26) |
| `design.py` | ARL, ATS, OC exactos; ARL0 real de p y c; simulación frente a cadenas de Markov | Correcto. Texto "no puede señalar mejoras" con WE4 aplicada (H22) |
| `sampling.py` | Plan de menor n por fuerza bruta; OC, AOQ, AOQL, ATI; plan doble por Monte Carlo; redondeo de D | Correcto (H15 corregido) |
| `interpretation.py` | Todos los textos con los casos mínimos de la primera pasada y con `data/ejemplos/` | H4, H6 a H9, H11 a H14 corregidos en lo principal. Abiertos: H18, H20, H21, H23, H24 y redacción (H25) |
| `descriptive.py` | Cuartiles tipo 7, asimetría y curtosis ajustadas, cercas de Tukey, Sturges, curva normal escalada | Correcto (los umbrales de forma que usa la interpretación, en H21) |

## 3. Constantes

Esperado: d2 = 2n∫xφ(x)Φ(x)^(n-1)dx (esperanza del máximo), d3 = √(E[W²] - E[W]²) con la densidad del rango integrada por Simpson en una malla (y, t), c4 = E[χ_(n-1)]/√(n-1). Ninguna de las tres es la fórmula que usa el software. Sin cambios en la segunda pasada.

| n | d2 propio | d2 software | d3 propio | d3 software | c4 propio | c4 software | máx. dif. | Veredicto |
|---|---|---|---|---|---|---|---|---|
| 2 | 1.1283792 | 1.128379 | 0.8525025 | 0.852502 | 0.7978846 | 0.7978846 | 4.7e-07 | correcto |
| 3 | 1.6925688 | 1.692569 | 0.8883680 | 0.888368 | 0.8862269 | 0.8862269 | 2.5e-07 | correcto |
| 4 | 2.0587507 | 2.058751 | 0.8798082 | 0.879808 | 0.9213177 | 0.9213177 | 2.5e-07 | correcto |
| 5 | 2.3259289 | 2.325929 | 0.8640819 | 0.864082 | 0.9399856 | 0.9399856 | 5.9e-08 | correcto |
| 6 | 2.5344127 | 2.534413 | 0.8480397 | 0.848040 | 0.9515329 | 0.9515329 | 3.1e-07 | correcto |
| 7 | 2.7043568 | 2.704357 | 0.8332053 | 0.833205 | 0.9593688 | 0.9593688 | 3.4e-07 | correcto |
| 8 | 2.8472006 | 2.847201 | 0.8198315 | 0.819831 | 0.9650305 | 0.9650305 | 4.9e-07 | correcto |
| 9 | 2.9700263 | 2.970026 | 0.8078343 | 0.807834 | 0.9693107 | 0.9693107 | 3.2e-07 | correcto |
| 10 | 3.0775055 | 3.077505 | 0.7970507 | 0.797051 | 0.9726593 | 0.9726593 | 4.6e-07 | correcto |
| 11 | 3.1728727 | 3.172873 | 0.7873146 | 0.787315 | 0.9753501 | 0.9753501 | 3.8e-07 | correcto |
| 12 | 3.2584553 | 3.258455 | 0.7784783 | 0.778478 | 0.9775594 | 0.9775594 | 3.4e-07 | correcto |
| 13 | 3.3359804 | 3.335980 | 0.7704162 | 0.770416 | 0.9794056 | 0.9794056 | 3.5e-07 | correcto |
| 14 | 3.4067631 | 3.406763 | 0.7630231 | 0.763023 | 0.9809714 | 0.9809714 | 1.1e-07 | correcto |
| 15 | 3.4718269 | 3.471827 | 0.7562114 | 0.756211 | 0.9823162 | 0.9823162 | 4.3e-07 | correcto |
| 16 | 3.5319828 | 3.531983 | 0.7499081 | 0.749908 | 0.9834835 | 0.9834835 | 2.1e-07 | correcto |
| 17 | 3.5878840 | 3.587884 | 0.7440518 | 0.744052 | 0.9845064 | 0.9845064 | 2.2e-07 | correcto |
| 18 | 3.6400638 | 3.640064 | 0.7385909 | 0.738591 | 0.9854100 | 0.9854100 | 2.4e-07 | correcto |
| 19 | 3.6889630 | 3.688963 | 0.7334815 | 0.733481 | 0.9862141 | 0.9862141 | 5.0e-07 | correcto |
| 20 | 3.7349501 | 3.734950 | 0.7286863 | 0.728686 | 0.9869343 | 0.9869343 | 3.5e-07 | correcto |
| 21 | 3.7783358 | 3.778336 | 0.7241733 | 0.724173 | 0.9875829 | 0.9875829 | 3.4e-07 | correcto |
| 22 | 3.8193846 | 3.819385 | 0.7199148 | 0.719915 | 0.9881703 | 0.9881703 | 3.6e-07 | correcto |
| 23 | 3.8583234 | 3.858323 | 0.7158867 | 0.715887 | 0.9887045 | 0.9887045 | 4.2e-07 | correcto |
| 24 | 3.8953481 | 3.895348 | 0.7120682 | 0.712068 | 0.9891927 | 0.9891927 | 1.8e-07 | correcto |
| 25 | 3.9306292 | 3.930629 | 0.7084408 | 0.708441 | 0.9896404 | 0.9896404 | 2.3e-07 | correcto |

Factores derivados (A, A2, A3, B3 a B6, D1 a D4) recalculados desde las constantes propias para n = 2 a 25 y L = 3 y 2.5: diferencia máxima con el software 5e-6 (`test_val_constantes.py::test_factores_derivados`). Frente a la tabla del apéndice VI que transcribieron los autores, las diferencias son de redondeo a tres decimales salvo d3(19), donde la tabla imprime 0.734 y el valor es 0.73348 (dos integrales distintas y 400 000 simulaciones coinciden). Por arrastre, D1(19) y D2(19) de la tabla difieren en 0.0015.

## 4. Gráficos por variables y atributos; Fase I y Fase II

| Caso | Fuente del esperado | Esperado | Software | Diferencia | Veredicto |
|---|---|---|---|---|---|
| Anillos de pistón, LCS X-barra | x̿ + 3R̄/(d2√5), d2 propio | 74.0146 | 74.0146 | 3.0e-10 | correcto |
| Anillos de pistón, LCS R | R̄(1 + 3d3/d2) | 0.049141 | 0.049141 | 1.2e-09 | correcto |
| Anillos de pistón, LCS S | S̄(1 + 3√(1-c4²)/c4) | 0.0196355 | 0.0196355 | 3.5e-18 | correcto |
| Hipotecas, LCS I | x̄ + 3MR̄/d2(2) | 321.21 | 321.21 | 3.1e-06 | correcto |
| Hipotecas, LCS MR | MR̄(1 + 3d3/d2) | 25.4446 | 25.4446 | 7.0e-06 | correcto |
| Jugo de naranja, LCS p | p̄ + 3√(p̄(1-p̄)/50) | 0.410239 | 0.410239 | 0.0e+00 | correcto |
| Jugo de naranja, puntos fuera | conteo a mano | [14, 22] | [14, 22] | — | correcto |
| Jugo, límites revisados (sin 15 y 23) | p̄ = 301/1400 | 0.389297 | 0.389297 | 0.0e+00 | correcto |
| Jugo, revisado: señal | conteo a mano | [20] | [20] | — | correcto |
| Tarjetas de circuito, LCS c | c̄ + 3√c̄ con c̄ = 516/26 | 33.2109 | 33.2109 | 0.0e+00 | correcto |
| Computadores, LCI u | ū - 3√(ū/5) | 0.0661331 | 0.0661331 | 0.0e+00 | correcto |
| p con n variable, LCS muestra 11 (n = 110) | p̄ + 3√(p̄(1-p̄)/110) | 0.179582 | 0.179582 | 0.0e+00 | correcto |
| `data/referencia/xbar_r_n3.json`, LCS X-barra | JSON (A2 = 1.023) | 14.5575 | 14.5583 | 8.2e-04 | correcto (redondeo de A2) |
| `data/referencia/xbar_s_n3.json`, LCS X-barra | JSON (A3 = 1.954) | 14.4425 | 14.4430 | 5.1e-04 | correcto (redondeo de A3) |
| `data/referencia/p.json`, LCS n = 80 | fórmula exacta (el JSON dice 0.1436922) | 0.1436899 | 0.1436899 | 0.0e+00 | software correcto; el JSON tiene un error aritmético de 2.3e-6 (H17) |
| `data/referencia/np.json`, LCS | fórmula exacta (el JSON dice 14.04849) | 14.04846 | 14.04846 | 0.0e+00 | software correcto; el JSON tiene un error aritmético de 3e-5 (H17) |
| Fase II con n = 8 (Fase I n = 5), LC del gráfico S | c4(8)·σ congelada | 0.00964992 | 0.00964992 | 0.0e+00 | correcto |

Comprobaciones adicionales (`test_val_graficos.py`), todas correctas:

| Caso | Esperado (cálculo propio) | Resultado |
|---|---|---|
| I-MR con el punto 3 excluido en [5, 7, 6, 40, 6.5, 5.5, 7.5, 6] | MR̄ = (2+1+1+2+1.5)/5 = 1.5 con los pares (0,1), (1,2), (4,5), (5,6), (6,7); x̄ sin el 40; MR_3 y MR_4 marcados como excluidos; el 40 sigue graficado | coincide |
| X-barra-R con el subgrupo 11 desplazado y excluido | x̿ y R̄ de los otros 24; 25 puntos graficados; `points_used` = 24 | coincide |
| Fase II con datos multiplicados por 3 y desplazados | límites idénticos a los de los datos originales | coincide (no recalcula) |
| Fase II X-barra-R con n = 3 desde Fase I n = 5 | LC_R = d2(3)σ, LCS_R = (d2(3) + 3d3(3))σ | coincide |
| Fase II u con tamaños 2, 4, 8 | ū ± 3√(ū/n_i) con ū = 1.93 congelado | coincide |
| p con n = 10 y p̄ pequeño | LCI truncado en 0 en todos los puntos y WE2 omitida | coincide |
| Límites congelados con `limit_width` = 0 (H16) | debe rechazarse | `SPCInputError` "debe ser positivo; se recibió 0" |

### Casos de `data/referencia/`

Se confirman las siete constantes de tabla que los autores tomaron de memoria: A2(3) = 1.023 (exacto 1.02333), D4(3) = 2.574 (exacto 2.57459; la tabla del libro redondea con d2 y d3 de tres decimales), A3(3) = 1.954 (exacto 1.95441), B4(3) = 2.568 (exacto 2.56817), d2(2) = 1.128, E2 = 3/d2(2) = 2.66 (exacto 2.65868) y D4(2) = 3.267 (exacto 3.26654). Los siete casos sirven como evidencia con estas salvedades:

- `xbar_r_n3`, `xbar_s_n3` e `i_mr`: los esperados del JSON llevan el redondeo de las constantes; el software, con constantes exactas, difiere en 5e-4 a 3.3e-3 (por ejemplo LCS_I = 18.6467 frente a 18.65). Los puntos fuera de control coinciden.
- `p.json`: σ para n = 80 está mal calculada en el JSON (0.0270641; el valor es 0.0270633, porque √0.000732421875 = 0.02706329) y el LCS correcto es 0.1436899. La conclusión (muestra 5 fuera) no cambia. **Sigue sin corregir en la segunda pasada (H17).**
- `np.json`: √6.1644 = 2.482821, no 2.482830; 3σ = 7.448463 y LCS = 14.04846. La conclusión no cambia. **Sigue sin corregir (H17).**
- `c.json` y `u.json`: exactos (recalculados con 30 dígitos).

### Datos de libro: qué se pudo verificar

| Caso (tal como lo citan los autores) | Verificado | No verificable contra el libro |
|---|---|---|
| Anillos de pistón (25 × 5) | Las medias y rangos de la transcripción reproducen la columna x̄ y R transcrita y ΣR = 0.581 | Los datos mismos. La suma de las x̄ redondeadas de la transcripción es 1850.028; conviene cotejar con el total que imprime el libro (recuerdo, sin poder confirmarlo, 1850.024: si es así, hay una fila mal copiada) |
| Hipotecas (20 individuales) | ΣMR = 148 y x̄ = 300.5 son consistentes con MR̄ = 7.79 publicado | Los datos individuales |
| Jugo de naranja (30 × 50) | Σ = 347, p̄ = 0.2313, revisado 301/1400 = 0.2150, muestras 15, 23 y luego 21: todo consistente | Los datos individuales; los 24 de Fase II (Σ = 133) |
| Tarjetas de circuito (26) | Σ = 516, revisado 472/24 = 19.67 | Los datos individuales. El software da LCS = 33.21 con c̄ sin redondear; el libro redondea c̄ a 19.85 y da 33.22 |
| Computadores (20 × 5) | Σ = 193, ū = 1.93, LCS = 3.79, LCI = 0.07 | Los datos individuales |
| p con n variable (tabla 7.4) | Σn = 2450 y ΣD = 234 reproducen p̄ = 0.096 | Los 25 pares (n_i, D_i). Con la transcripción, la muestra 11 (20/110 = 0.1818) supera su LCS (0.1796); si el libro declara el proceso en control, hay que revisar D_11 o n_11 en el libro |
| Plan (89, 2) y doble (50, 1, 4, 100, 3) | α, β, Pa, AOQ, ATI recalculados | Que sean los ejemplos exactos del libro |
| Capacidad: pistón (Cp = 1.68) y envases (Cpl = 0.67) | La aritmética con los estadísticos publicados | Los datos originales (los autores construyeron subgrupos con la media y la desviación publicadas; es válido como prueba de la aritmética, no del ejemplo) |
| IC de Cp (2.29 → 1.57 a 3.01) y de Bissell (1.33 → 0.88 a 1.78) | Coinciden con el cálculo propio con χ² y z | Número de ejemplo y de sección (citados de memoria, 6.ª ed.) |

## 5. Reglas de corrida

| Caso | Fuente del esperado | Esperado | Software | Diferencia | Veredicto |
|---|---|---|---|---|---|
| 3 600 evaluaciones (300 series × 12 reglas, con y sin excluidos) | bucles explícitos (`reglas_ingenuas`) | 0 diferencias | 0 diferencias | — | correcto |
| Serie que activa cada regla justo en el último punto / serie a un punto, para las 12 reglas | definición de la regla | señal en el último / ninguna | igual | — | correcto |
| Puntos exactamente sobre el límite, sobre 2σ, sobre 1σ, sobre la LC | comparación estricta | sin señal | sin señal | — | correcto |
| Límites asimétricos (LC 2, LCS 4.3, LCI 0) | solo WE1, WE4, N1-N4 | 6 reglas omitidas con motivo | igual | — | correcto |
| Panel MR con las 12 reglas pedidas (H5, decisión aplicada) | solo WE1 y N1 | 10 omitidas con motivo; el panel I aplica las 12 | igual | — | correcto |
| Excluido dentro de una racha | la corrida salta sobre el excluido | WE4 en el índice 8 | 8 | — | correcto |
| ARL0 WE1-WE4, individuales | cadena de Markov propia | 91.751 | 91.869 (EE ≈ 1.0) | 0.12 | correcto |
| ARL1 WE1-WE4, δ = 1 | cadena de Markov propia | 9.2219 | 9.2112 | 0.011 | correcto |
| ARL0 WE1 + WE4, individuales | cadena de rachas propia | 152.73 | 153.35 | 0.62 | correcto |
| ARL0 de N3 en R con n = 2 (asimétrico) | ecuación integral propia, i.i.d. continuo: 421.6 | 421.6 | 418.4 (EE 2.4) | 1.3 EE | correcto: no depende de la asimetría |
| ARL0 de N3 en individuales | ídem | 421.6 | 420.3 (EE 2.4) | 0.5 EE | correcto |
| ARL0 de N4 en R con n = 2 | ecuación integral propia: 601.0 | 601.0 | 601.6 (EE 3.4) | 0.2 EE | correcto |
| ARL0 de N4 en individuales | ídem | 601.0 | 604.9 (EE 3.4) | 1.1 EE | correcto |
| ARL0 de WE4 en c con c̄ = 2 (LC sobre un conteo posible) | cadena propia con empates: 1 924.1 | 1 924.1 | dentro de 4 EE (4 000 corridas) | — | correcto el cálculo; **la advertencia dice lo contrario (H19)** |

La cadena propia de WE1-WE4 da ARL0 = 91.75, el mismo valor que publican Champ y Woodall (1987) para estas cuatro reglas; como el valor publicado lo recuerdo y no lo cotejé con el artículo, la evidencia es el acuerdo entre la cadena y la simulación del software. Con 400 000 corridas la simulación coincide con la cadena en δ = 0, 0.5 y 1 (|z| < 1), sin sesgo detectable.

**ARL en control de las reglas de racha en paneles asimétricos (duda 1 y H5).** En un panel simétrico, WE4 sola tiene ARL0 = 255 y N2 sola 511.

| Panel | Regla | ARL0 si P(arriba de la LC) = 0.5 | ARL0 real | Método |
|---|---|---|---|---|
| R, n = 2 | WE4 | 255 | 173.7 | cadena propia, P(R > R̄) = 0.4249 |
| R, n = 5 | WE4 | 255 | 236.1 | cadena propia, P(R > R̄) = 0.4687 |
| R, n = 10 | WE4 | 255 | 241.0 | cadena propia, P(R > R̄) = 0.4734 |
| R, n = 2 | N2 | 511 | 312.2 | cadena propia |
| MR (hoy no se aplica) | WE4 | 255 | 94 | simulación, 6 000 corridas |
| MR (hoy no se aplica) | N2 | 511 | 154 | simulación |
| MR (hoy no se aplica) | N3 | 421.6 (exacto, datos independientes) | 257 | simulación |
| MR (hoy no se aplica) | N4 | 601.0 (exacto, datos independientes) | ≥ 1 237 | simulación |
| I, R, S (cualquier estadístico continuo i.i.d.) | N3 | 421.6 | 421.6 | ecuación integral; depende solo del orden |
| I, R, S (cualquier estadístico continuo i.i.d.) | N4 | 601.0 | 601.0 | ecuación integral |
| Poisson(2.5), Poisson(4) | N3 | 421.6 | > 8 000 (ninguna señal en 6 000 × 8 000) | simulación con la lógica del software: los empates cortan la tendencia |
| Poisson(20) | N3 y N4 | 421.6 y 601.0 | ≥ 5 941 y ≥ 2 515 | ídem |
| p, n = 100, p̄ = 0.0098 | WE4 | 255 | 107.3 | cadena propia, P(D > n·p̄) = 0.626 |
| p, n = 100, p̄ = 0.0102 | WE4 | 255 | 42.8 | cadena propia, P(D > n·p̄) = 0.272 |
| p, n = 100, p̄ = 0.01 (n·p̄ = 1) | WE4 | 255 | 4 507.9 | cadena propia; P(D = 1) = 0.370 cae sobre la LC y corta la racha |
| c, c̄ = 2 | WE4 | 255 | 1 924.1 | cadena propia; P(X = 2) = 0.271 |
| c, c̄ = 4 | WE4 | 255 | 1 071.1 | cadena propia; P(X = 4) = 0.195 |
| c, c̄ = 4.25 (`data/referencia/c.json`, sin empates) | WE4 | 255 | 166.2 | cadena propia |

Conclusión sobre la decisión de los autores (H5): en MR solo se evalúan WE1 y N1 (verificado, `test_panel_mr_solo_reglas_de_limite`). El argumento de que N3 y N4 dependen solo del orden es **correcto**: con observaciones i.i.d. continuas todas las ordenaciones son equiprobables, así que su ARL0 es el mismo para cualquier distribución (421.6 y 601.0 por la ecuación integral; la simulación del software en R con n = 2 da 418.4 ± 2.4 y 601.6 ± 3.4). El 437 que simularon los autores es ruido de simulación, no un efecto. Con conteos, los empates alargan mucho el ARL0 (N3 casi nunca señala con c̄ ≤ 4). Lo que no es correcto es la frase "su tasa de falsas alarmas es mayor que la nominal" para WE4 y N2 en todos los casos: si la línea central coincide con un conteo posible, los puntos sobre ella cortan la racha y WE4 da muchas menos falsas alarmas (1 924 frente a 255 con c̄ = 2), y también pierde sensibilidad (H19).

**R con n ≥ 7 y S con n ≥ 6 (duda nueva).** Para esos n el LCI ya no se trunca y los límites quedan simétricos alrededor de la LC, pero la distribución del estadístico sigue siendo asimétrica: con n = 7, P(R > R̄ + 2σ_R) = 0.0328 y P(R < R̄ - 2σ_R) = 0.0095 frente a 0.0228 de cada lado en la normal; más allá de 3σ, 0.0044 arriba y 0.0000 abajo frente a 0.00135. Con S y n = 10: 0.0289 y 0.0148 en 2σ. Las zonas A, B y C darían tasas de falsa alarma distintas de las nominales, así que es correcto seguir marcando R y S como asimétricos. El motivo que se escribe ("los límites no son simétricos alrededor de la línea central") es falso en esos casos (H25).

**Muchas reglas a la vez (observación S6).** Con las 12 reglas, el ARL0 de un gráfico de individuales es 66.2 (EE 0.8, simulación del software). En una Fase I de 25 puntos en control la probabilidad de al menos una señal es del orden de 0.3: por ejemplo `data/ejemplos/sintetico_xbar_s_n10.csv` (proceso estable) da una señal N3 en el subgrupo 7 y `sintetico_np.csv` da WE4 y N2 (P(D ≤ 3) = 0.62 con n·p̄ = 3.1). El texto no avisa que con muchas reglas las falsas alarmas son frecuentes.

## 6. Supuestos

| Caso | Fuente del esperado | Esperado | Software | Diferencia | Veredicto |
|---|---|---|---|---|---|
| ACF y Ljung-Box, 100 series aleatorias (n de 8 a 300, m de 1 a 29) | autocovarianza por FFT y Q escrita de nuevo | — | — | ≤ 1e-12 | correcto |
| Ljung-Box, Q (n = 120, m = 20) | ACF por FFT | 76.5309 | 76.5309 | 4.3e-14 | correcto |
| Ljung-Box, valor p | χ²(20) de la Q propia | 1.51109e-08 | 1.51109e-08 | 2.7e-22 | correcto |
| Banda de la ACF | z_{0.975}/√n | 0.16003 (n = 150) | 0.16003 | 0 | correcto |
| Rachas, distribución exacta (n1, n2 ≤ 8) | enumeración de las C(n1+n2, n1) disposiciones | — | — | 0 | correcto |
| Rachas, valor p exacto (n = 16) | enumeración | 0.20047 | 0.20047 | 0 | correcto |
| Rachas n1 = n2 = 31, R = 24: valor p (H10) | distribución exacta | 0.05413 | 0.05413 | 0 | correcto (antes 0.04048) |
| Rachas con log-gamma, (501, 500), (600, 700), (1 500, 1 500), (2 500, 2 400) (H10) | aritmética racional exacta | — | — | error relativo ≤ 9e-12 en toda la distribución y en los valores p de z = -6 a 6; la pmf suma 1 a 4e-12 | correcto |
| Anderson-Darling, A² | fórmula con `scipy.special.ndtr` y `scipy.stats.anderson` | 0.288747 | 0.288747 | 0 | correcto |
| Anderson-Darling, tamaño real α = 0.05, n = 8 / 15 / 30 / 100 (H3) | simulación bajo H0, 60 000 réplicas | 0.05 | 0.0505 / 0.0506 / 0.0496 / 0.0493 | ≤ 7e-4 | correcto (antes 0.038 / 0.061 / 0.056 / 0.046) |
| Anderson-Darling, valor crítico n = 3 | debe ser positivo | > 0 | 0.5013 | — | correcto (antes -1.771) |
| Shapiro-Wilk | `scipy.stats.shapiro` | — | igual | 0 | correcto (delegado a scipy) |

**Tamaño real de Anderson-Darling tras la corrección (H3).** El software usa la tabla de D'Agostino y Stephens (1986), 0.561, 0.631, 0.752, 0.873, 1.035, dividida por 1 + 0.75/n + 2.25/n², la misma que trae `scipy.stats.anderson` 1.18.1 (verificado en el código fuente instalado). Simulación propia bajo H0, 100 000 réplicas por celda (EE 0.0009, 0.0007 y 0.0003):

| n | α = 0.10 | α = 0.05 | α = 0.01 |
|---|---|---|---|
| 4 | 0.1067 | 0.0470 | 0.0012 |
| 5 | 0.1053 | 0.0475 | 0.0073 |
| 8 | 0.1023 | 0.0507 | 0.0092 |
| 10 | 0.1033 | 0.0504 | 0.0091 |
| 15 | 0.1009 | 0.0502 | 0.0096 |
| 20 | 0.1010 | 0.0503 | 0.0097 |
| 30 | 0.1007 | 0.0498 | 0.0104 |
| 50 | 0.1003 | 0.0501 | 0.0103 |
| 100 | 0.1009 | 0.0507 | 0.0099 |
| 200 | 0.0977 | 0.0492 | 0.0096 |

Con α interpolado en log α (n = 30): 0.0195 para α = 0.02 y 0.0751 para α = 0.075. Desde n = 8 el tamaño real queda a ±0.003 del nominal en los tres niveles. Con n = 3 (solo por la librería; la API exige n ≥ 8) el máximo posible de A² es 0.4878, menor que el crítico 0.5013 de α = 0.05: la prueba no puede rechazar nunca, aunque el texto dice "casi no tiene potencia" (observación menor, `test_ad_n3_no_puede_rechazar`).

**Tamaño real conjunto.** Primera pasada (3 000 réplicas normales e independientes, α = 0.05): `is_normal = False` en el 7.1 % de los casos (n = 30 y n = 100) e `is_independent = False` en el 8.7 % (n = 30) y el 13.4 % (n = 100). El texto lo dice ahora explícitamente ("del orden del 7 % al 13 %"). Ljung-Box solo rechaza el 6.8 % a 7.5 % con n entre 50 y 100 y m = n/4: es una propiedad conocida de la aproximación χ², no un error de implementación.

**Probabilidad de que algún rezago salga de la banda por azar (H23).** El texto la calcula como 1 - (1 - α)^m y el número esperado como α·m, lo que supone rezagos independientes con varianza exactamente 1/n. Simulación propia (4 000 series normales por caso):

| n, m | P(al menos uno fuera), simulada | 1 - 0.95^m (texto) | número esperado fuera, simulado | α·m (texto) |
|---|---|---|---|---|
| 40, 10 | 0.261 | 0.401 | 0.32 | 0.50 |
| 60, 15 | 0.368 | 0.537 | 0.49 | 0.75 |
| 120, 20 | 0.517 | 0.642 | 0.76 | 1.00 |
| 300, 20 | 0.593 | 0.642 | 0.91 | 1.00 |

La varianza de r_k bajo H0 es (n - k)/(n(n + 2)), menor que 1/n, y los r_k están correlacionados; por eso salen menos rezagos de los que dice el texto.

**Forma de la distribución con muestras pequeñas (H21).** El hallazgo "Forma de la distribución" aparece si |G1| ≥ 0.5 o |G2| ≥ 1, sin mirar n. Con datos normales (40 000 muestras por n):

| n | P(\|G1\| ≥ 0.5) | P(\|G2\| ≥ 1) | P(aparece el hallazgo) |
|---|---|---|---|
| 8 | 0.491 | 0.486 | 0.747 |
| 15 | 0.366 | 0.294 | 0.532 |
| 20 | 0.307 | 0.228 | 0.433 |
| 30 | 0.226 | 0.150 | 0.304 |
| 60 | 0.101 | 0.069 | 0.140 |
| 100 | 0.042 | 0.036 | 0.065 |
| 200 | 0.005 | 0.012 | 0.015 |

### Textos de supuestos con `data/ejemplos/`

| Archivo | Lo que dice el resumen | Veredicto |
|---|---|---|
| `sintetico_i_mr.csv` (60) | compatible con normalidad e independencia; "no que esté demostrado que se cumplan"; r3 = 0.261 fuera de banda con 0.75 esperados | correcto (H6 corregido) |
| `sintetico_no_normal.csv` (80, lognormal) | evidencia contra la normalidad; recuerda que un proceso inestable también la produce | correcto (S3 corregida) |
| `sintetico_autocorrelado.csv` (60, AR(1) 0.7) | evidencia de autocorrelación con r1 = 0.703, recomienda modelar | correcto |
| `sintetico_fase1.csv` sin el subgrupo 12 (120) | evidencia débil: Ljung-Box p = 0.0245, rachas p = 0.5182 (exacta), un solo rezago (r6 = -0.281); no habla de AR(1) ni de autocorrelación positiva | correcto (H6 corregido); el "0,64" debería ser ≈ 0.52 (H23) |
| 8 observaciones (caso de H6) | "compatibles … no que esté demostrado"; advierte poca potencia | correcto; pero afirma "colas más livianas que la normal" por G2 = -1.2, cuyo EE con n = 8 es 1.48 (H21) |

## 7. Capacidad

| Caso | Fuente del esperado | Esperado | Software | Diferencia | Veredicto |
|---|---|---|---|---|---|
| Cp, Cpl, Cpu, Cpk, Ppk, Cpm, PPM por cola (25 × 5, R̄/d2) | fórmulas a mano | — | — | ≤ 1e-6 relativo | correcto |
| Una sola especificación (solo USL) | Cp, Cpl, Pp y cola inferior en null; Cpk = Cpu | — | igual | — | correcto |
| IC de Cp, Ĉp = 2.29, n = 20: inferior | 2.29·√(χ²_{0.025,19}/19) | 1.568 | 1.568 | 2e-16 | correcto |
| IC de Cp, Ĉp = 1.5, n = 40, 90 % | cuantiles χ² propios | — | igual | 0 | correcto |
| IC de Bissell, Ĉpk = 1.33, n = 20: inferior | Ĉ - z√(1/(9n) + Ĉ²/(2(n-1))) | 0.8826 | 0.8826 | 2e-16 | correcto |
| IC de Bissell con índice negativo (-0.4) | mismo semiancho, centrado en -0.4 | — | igual | 1e-6 | correcto |
| ν de R̄/d2, 25 × 5 | m·d2²/(2d3²) con d2 y d3 propios: 90.57; simulación del CV: 90.8 | 90.57 | 90.57 | 1e-5 relativo | correcto |
| ν de S̄/c4, 25 × 5 | m·c4²/(2(1 - c4²)) = 94.86; simulación: 94.96 | 94.86 | 94.86 | — | correcto |
| ν de MR̄/d2, N = 50 (k = 49) | fórmula con Cov(MR_i, MR_{i+1}) = 0.16275σ²: 29.83; simulación: 29.77 | 29.83 | 29.83 | 0.2 % frente a la simulación | correcto |
| ν de S combinada, n de 2 a 15 (25 subgrupos) | Σ(n_i - 1) = 144; simulación: 143.5 | 144 | 144 | — | correcto (exacto: ν·s_p²/σ² ~ χ²_ν) |
| σ combinada con n variable (S2) | s_p/c4(ν + 1) a mano | 2.002211 | 2.002211 | 0 | correcto |
| Cota unilateral 95 % de Cpk (S4) | Ĉ - z_{0.95}√(1/(9N) + Ĉ²/(2ν)) a mano | — | el texto imprime el mismo valor | — | correcto (`test_cota_unilateral_de_cpk_a_mano`) |
| LSL = NaN o infinito (H2) | debe rechazarse | ValueError en la librería; 422 en la API | ValueError "LSL debe ser un número finito"; API 422 "lsl: debe ser un número finito" | — | correcto |
| Objetivo T fuera de [LSL, USL] (H14) | debe rechazarse o avisarse | Cpm null y advertencia | igual | — | correcto |

**Derivación de los ν que usa el software (H1).** Se comprobaron las cuatro expresiones del docstring de `capability.py`:

- R̄/d2: Var(R_i) = d3²σ² y los R_i son independientes, así que CV²(R̄/d2) = d3²/(m·d2²) y ν = 1/(2CV²) = m·d2²/(2d3²). Correcto.
- S̄/c4: Var(S_i) = σ²(1 - c4²), así que ν = m·c4²/(2(1 - c4²)) (3.79·m para n = 5). Correcto.
- MR̄/d2: con U = x_i - x_{i-1} y V = x_{i+1} - x_i, Var(U) = Var(V) = 2σ² y ρ = -1/2. Para una normal bivariada, E|U||V| = (2·2σ²/π)(√(1 - ρ²) + ρ·arcsen ρ) = (4σ²/π)(√3/2 + π/12) = σ²(2√3/π + 1/3). Restando E|U|·E|V| = 4σ²/π queda Cov(MR_i, MR_{i+1}) = σ²((2√3 - 4)/π + 1/3) = 0.162752σ² (verificado). Los MR a distancia 2 no comparten observaciones y son independientes. Var(MR̄) = σ²[k·d3(2)² + 2(k - 1)·0.16275]/k² y ν = d2(2)²k²/(2[k·d3(2)² + 2(k - 1)·0.16275]). Correcto. El docstring dice "ν ≈ 0,6045·k": el límite para k grande es 4/π / (2(2 - 4/π + 0.32550)) = 0.6050·k, y con k = 49 la razón es 0.6088 (detalle menor).
- S combinada con n variable: ν·s_p²/σ² ~ χ²_ν con ν = Σ(n_i - 1); el intervalo χ² es exacto para s_p. El software usa s_p/c4(ν + 1), insesgado; el factor desplaza el intervalo un 0.1 % a 0.3 % hacia abajo, sin efecto medible en la cobertura (observación S8).
- Límites congelados: ν es el de la Fase I, reconstruido con `points_used`, `subgroup_size` y `sigma_method`; si faltan, los IC van en null y se advierte. Correcto. En I-MR con exclusiones intermedias se cuentan points_used - 1 rangos aunque haya menos (H26).

**Cobertura real del IC del 95 % tras la corrección (H1).** Proceso normal con σ = 1, LSL = -5, USL = 4, μ = 0 (Cp = 1.5, Cpk = 4/3). 5 000 réplicas por caso (EE 0.003). "Software": el intervalo que devuelve `analyze_capability`. "Propio": σ̂ y Ĉ calculados en el script con ν medido por simulación del CV y cuantiles χ² y z de scipy. "ν = N - 1": la fórmula del libro sin corregir, como en la primera pasada.

| Estimador de σ | ν | Cp: software | Cp: propio | Cp: ν = N - 1 | Cpk: software | Cpk: propio | Cpk: ν = N - 1 |
|---|---|---|---|---|---|---|---|
| R̄/d2, 25 × 5 | 90.6 | 0.947 | 0.947 | 0.905 | 0.951 | 0.950 | 0.917 |
| S̄/c4, 25 × 5 | 94.9 | 0.947 | 0.947 | 0.909 | 0.951 | 0.951 | 0.921 |
| MR̄/d2, N = 50 | 29.8 | 0.944 | 0.946 | 0.864 | 0.951 | 0.951 | 0.879 |
| S combinada, n de 2 a 15 (N = 169) | 144 | 0.948 | 0.949 | 0.928 | 0.951 | 0.951 | 0.934 |
| Congelada X-barra-R (25 × 5), N = 500 nuevos | 90.6 | 0.948 | 0.947 | 0.591 | 0.950 | 0.949 | 0.610 |
| Congelada I-MR (30 puntos), N = 100 nuevos | 17.7 | 0.955 | 0.955 | 0.584 | 0.955 | 0.955 | 0.609 |

Todas entre 0.944 y 0.955, de acuerdo con el 0.947 a 0.952 que reportaron los autores. La cota unilateral del 95 % que usa el texto "con 95 % de confianza Cpk supera…" (S4) cubre el 0.953 (R̄/d2, 25 × 5) y el 0.955 (MR̄/d2, N = 50) de las veces (100 000 réplicas, cálculo propio vectorizado).

**Dos pruebas disputadas.** `test_cobertura_con_rbar_d2` y `test_cobertura_con_limites_congelados` llamaban a `cp_confidence_interval(cp, N)` sin `dof`, igual que la prueba de control con la desviación muestral. Esa función no sabe con qué estimador se calculó σ: con `dof` omitido usa N - 1, que es lo correcto para la desviación muestral. Las tres pruebas no podían pasar a la vez con ningún código, así que los autores tenían razón. Se reescribieron para medir el camino real: comprueban que `analyze_capability` devuelve el intervalo de `cp_confidence_interval(cp, N, dof=sigma_dof(...))` (o `frozen_sigma_dof(limits)`), que ese ν coincide con m·d2²/(2d3²) calculado con las constantes propias, y miden la cobertura con ese ν (6 000 réplicas, banda 0.935 a 0.965). Se agregó `test_cobertura_bissell_con_mrbar_d2` (ν contra la simulación del CV y cobertura de Bissell con N = 50).

**Razón σ_largo/σ_corto (H9).** El texto compara la razón con exp(z_{0.95}·√V), con V = 1/(2ν) - 1/(2(N - 1)) (los mismos datos; la desviación muestral es el estimador eficiente y su covarianza con un estimador insesgado menos eficiente es igual a su varianza) o V = 1/(2ν) + 1/(2(N - 1)) (σ congelada, independiente), con un piso de 1.10. Con datos estables (2 000 réplicas), frecuencia con que el texto afirma que la diferencia "es mayor que la esperable por azar":

| Datos estables | Primera pasada ("Hay variación entre subgrupos") | Segunda pasada: afirma exceso | dice "compatible con el azar" | afirma σ_largo < σ_corto más allá del azar |
|---|---|---|---|---|
| I-MR, N = 30 | 0.17 | 0.049 | 0.122 | 0.039 |
| I-MR, N = 50 | 0.12 | 0.056 | 0.068 | 0.040 |
| I-MR, N = 100 | 0.05 | 0.051 | 0.000 | 0.031 |
| 25 × 5, R̄/d2 | 0.013 | 0.013 | 0.000 | 0.000 |
| 25 × 10, S̄/c4 | — | 0.000 | 0.000 | 0.000 |
| n variable (S combinada) | — | 0.002 | 0.000 | 0.000 |
| Congelada 25 × 5, N = 500 | — | 0.059 | — | 0.055 |

El nivel queda en el 5 % nominal donde el umbral estadístico manda (I-MR, congelada) y por debajo donde manda el piso de 1.10 (subgrupos).

**ν de I-MR congelado con exclusiones intermedias (duda nueva, H26).** 30 individuales; ν que usa el software (points_used - 1 rangos consecutivos) frente al exacto (solo los MR con ambos puntos retenidos y las covarianzas entre MR vecinos que existen) y al simulado (40 000 réplicas):

| Exclusiones | points_used | MR usados | ν software | ν exacto | ν simulado | Sobrestimación |
|---|---|---|---|---|---|---|
| ninguna | 30 | 29 | 17.73 | 17.73 | 17.81 | 0 % |
| 15 | 29 | 27 | 17.13 | 16.72 | 16.69 | 2.5 % |
| 5, 15, 25 | 27 | 23 | 15.92 | 14.71 | 14.54 | 8.2 % |
| 2, 5, 8, …, 17 (6) | 24 | 17 | 14.10 | 11.79 | 11.84 | 19.7 % |

**Bissell con σ congelada (duda nueva).** La fórmula supone que x̄ (de los datos nuevos) y σ̂ (de la Fase I) son independientes. Lo son por construcción, porque salen de datos distintos; incluso con los mismos datos, bajo normalidad x̄ es independiente de cualquier estimador de σ invariante a la localización (teorema de Basu). La cobertura medida es 0.950 (X-barra-R) y 0.955 (I-MR). El supuesto que importa es otro: que σ no haya cambiado entre la Fase I y los datos nuevos. La advertencia lo dice ("suponen que la variabilidad no cambió desde la Fase I").

**Mínimo de 1.25 para especificación unilateral (S1, duda nueva).** La tabla de valores mínimos recomendados (1.33 bilateral y 1.25 unilateral para procesos existentes; 1.50 y 1.45 para procesos nuevos; 1.50 y 1.45, y 1.67 y 1.60, para parámetros críticos) coincide con la transcripción de Montgomery (2004, 5.ª ed., p. 776) que publica Wikipedia ("Process capability index") y con la guía de Analyse-it, que atribuye 1.33 y 1.25 a Montgomery (2012). No se cotejó con la 6.ª edición: antes de citarla en el informe hay que verificar número de tabla y página en el libro.

### Textos de capacidad con `data/ejemplos/`

| Caso | Lo que dice | Veredicto |
|---|---|---|
| `sintetico_xbar_r_en_control`, estable | "veredicto de capacidad adecuado" con Cpk = 1.41; aparte: "no se puede afirmar con 95 % de confianza" (cota 1.24) | correcto; el veredicto del resumen es el de la estimación puntual (observación S7) |
| ídem, `is_stable` None | "el veredicto es condicional … solo si el proceso es estable" | correcto (H7 corregido) |
| ídem, `is_stable` False | "no se puede declarar su capacidad" | correcto en el resumen; con un Cpk alto un hallazgo afirma "con 95 % de confianza Cpk supera el mínimo" (H20) |
| `sintetico_xbar_r_desplazamiento`, inestable | razón 1.30 > 1.07: "mayor que la esperable por azar … indicio": correcto; "está por debajo de el mínimo" | correcto salvo redacción (H25) |
| `sintetico_fase2` con límites congelados de `fase1` sin el 12 | ν ≈ 86.9 de la Fase I (24 × 5), advierte que la variabilidad se supone igual | correcto |
| `sintetico_i_mr`, solo USL | mínimo 1.25 unilateral; ν ≈ 35.9 | correcto |

## 8. ARL y ATS

| Caso | Fuente del esperado | Esperado | Software | Diferencia | Veredicto |
|---|---|---|---|---|---|
| ARL0, L = 3 | 1/(2Φ(-3)) | 370.398 | 370.398 | 0 | correcto |
| ARL1, n = 5, δ = 1 | 1/(1 - β), β = Φ(3-√5) - Φ(-3-√5) | 4.49531 | 4.49531 | 0 | correcto |
| ATS1, h = 0.5 | ARL1·h | 2.24766 | 2.24766 | 0 | correcto |
| ARL, ATS, β y unidades para (n, L, δ) = (1, 3, 1), (4, 2.5, 0.75), (9, 3.2, 0.5) | fórmulas a mano | — | — | ≤ 1e-10 relativo | correcto |
| ARL0 real del gráfico p (n = 50, p0 = 0.2) | 1/[1 - P(2 ≤ D ≤ 18)] con suma binomial propia | 369.839 | 369.839 | 6e-13 | correcto |
| ARL0 real del gráfico c (c0 = 4, LCS = 10 exacto) | 1/P(X ≥ 11) | 352.142 | 352.142 | 0 | correcto |
| ARL0 real del gráfico c (c0 = 19.85) | 1/[1 - P(7 ≤ X ≤ 33)] | — | igual | ≤ 1e-9 relativo | correcto |
| ARL0 simulado (solo WE1) frente al exacto | 370.398 ± 4 EE | 370.4 | 375.5 (EE 4.2) | 5.1 | correcto |
| Simulación de p y c frente a su fórmula exacta | ± 4 EE | — | dentro | — | correcto |
| WE1-WE4 con X-barra n = 4, δ = 0.5σ (equivale a δ = 1 en σ/√n) | cadena propia | 9.2219 | dentro de 4 EE | — | correcto |
| WE1 + WE4 en c truncado, c0 = 4 (LC entera, con empates) | cadena propia: 265.9 | 265.9 | 263.1 (EE 4.2) | 0.7 EE | correcto |
| Comparación de diseños (n = 2, 8; h = 0.25, 1) | ARL0, ATS1 y carga n/h a mano | — | igual | — | correcto |

**WE4 en p y c truncados dentro de `design.py` (duda nueva).** No hace falta advertir que WE4 tiene más falsas alarmas: la simulación genera conteos de la distribución discreta real y aplica la misma lógica de reglas que los gráficos, así que el ARL0 informado ya es el real, con la asimetría y los empates incluidos (265.9 por la cadena propia frente a 263.1 ± 4.2 simulado). El texto además compara con el ARL0 de WE1 sola ("multiplican las falsas alarmas por…"). Lo que sí está mal es otra frase: con WE4 aplicada el texto sigue diciendo "el gráfico no puede señalar mejoras", mientras la misma salida informa ARL1 = 16.95 para c1 = 2 (frente a 120 363 con WE1 sola) (H22). Detalle: con p0 = 0.01 y n = 100 (n·p0 entero) el texto dice que las reglas suplementarias "multiplican las falsas alarmas por 0,994", una diferencia que está dentro del error de simulación (H25).

## 9. Muestreo de aceptación

| Caso | Fuente del esperado | Esperado | Software | Veredicto |
|---|---|---|---|---|
| AQL 0.01, LTPD 0.06, α 0.05, β 0.10, binomial | fuerza bruta sobre todos los (n, c) | (110, 3) | (110, 3) | correcto |
| ídem, Poisson | fuerza bruta | (112, 3) | (112, 3) | correcto |
| AQL 0.02, LTPD 0.08, binomial | fuerza bruta | (98, 4) | (98, 4) | correcto |
| AQL 0.015, LTPD 0.10, α = β = 0.10, binomial | fuerza bruta | (52, 2) | (52, 2) | correcto |
| AQL 0.03, LTPD 0.12, α = β = 0.05, binomial | fuerza bruta | (85, 5) | (85, 5) | correcto |
| AQL 0.02, LTPD 0.10, hipergeométrica, N = 500 | fuerza bruta | (63, 3) | (63, 3) | correcto |
| AQL 0.04, LTPD 0.16, hipergeométrica, N = 200 | fuerza bruta | (38, 3) | (38, 3) | correcto |
| Plan del nomograma (89, 2): α y β reales | suma binomial propia | 0.06031 y 0.09187 | 0.06031 y 0.09187 | correcto: no cumple α |
| Plan (110, 3): α y β reales | suma binomial propia | 0.02504 y 0.09803 | igual | correcto |
| AOQ y ATI de (89, 2) con N = 10 000 en toda la curva | Pa·p(N - n)/N y n + (1 - Pa)(N - n) | — | ≤ 1e-8 | correcto |
| AOQL de (89, 2) | máximo en malla de 3 001 puntos | — | 1e-5 relativo | correcto |
| Plan doble (50, 1, 4, 100, 3), p = 0.05: Pa | Monte Carlo, 400 000 lotes | 0.2895 | 0.2904 | correcto (< 5 EE) |
| Plan doble, ASN, AOQ y ATI en p = 0.01, 0.03, 0.06 | Monte Carlo de lotes con N = 5 000 | — | ≤ 1 % (AOQ ≤ 3 %) | correcto |
| Pa hipergeométrica decreciente en n (base de la bisección) | evaluación en n = 3 a 199 | monótona | monótona | correcto |
| D = redondeo(p·N) (H15): N = 50, p = 0.05, 0.03, 0.01 | redondeo aritmético | 3, 2, 1 | 3, 2, 1 | correcto (antes 2, 2, 0) |
| D = redondeo(p·N), 79 992 combinaciones (p de 0.0001 a 0.9999; N = 7 a 2 500) | `Decimal` con ROUND_HALF_UP | — | 0 discrepancias (también la función de la interpretación) | correcto |

La interpretación ya no menciona nomogramas que nadie leyó (H8): con AQL 0.005 y LTPD 0.03 explica por qué c = 2 no sirve (n = 176 cumple β pero da α = 0.05915) con números de la búsqueda exacta.

## 10. Robustez numérica

| Entrada | Resultado del software | Veredicto |
|---|---|---|
| Todos los valores iguales (σ = 0) en gráficos | límites colapsan en la LC, reglas de zonas omitidas, advertencia | correcto |
| σ = 0 en capacidad y supuestos | ValueError con mensaje en español | correcto |
| n mínimo (n = 2 en X-barra-R; 2 puntos en I-MR) | calcula | correcto |
| Conteos todos 0 (p, c, u) | p̄ = 0, límites en 0, advertencia; sin NaN | correcto |
| NaN o infinito en datos de gráficos, supuestos o capacidad | rechazado | correcto |
| NaN en `limit_width`, en `sigma` congelada, L negativo o 0 | rechazado (422) | correcto (H16 corregido) |
| LSL, USL u objetivo = NaN o infinito en capacidad (H2) | ValueError en la librería; 422 por la API (`allow_inf_nan=False` en el contrato) | correcto |
| `capability_verdict(NaN)` | ValueError | correcto |
| Anderson-Darling con n = 3, 4, 5 (solo por la librería; la API exige n ≥ 8) | crítico positivo; tamaño real 0.047 con n = 4 y 5; con n = 3 no puede rechazar | correcto salvo el texto de n = 3 (observación) |
| α de diseño muy pequeño (L = 5.5) en los textos (H13) | "α = 3,798·10⁻⁸ (< 0,001 % …)" | correcto |
| Rachas con más de 1 000 datos (H10) | log-gamma, error relativo ≤ 9e-12 hasta 4 900 datos; 10 ms | correcto |
| p0 = 1e-9 o L = 40 en ARL | ARL finito o ValueError claro ("probabilidad de señal es 0") | correcto |
| Valores graficados ≥ 10⁶ en las descripciones de `rules.py` | `_fmt` usa 6 cifras: "1,23457e+06" | menor (H25) |

## 11. Hallazgos

Ordenados por gravedad. "Confirmado" significa reproducido con un caso mínimo y un valor correcto obtenido por otro camino; "sospecha" es algo que no pude cerrar o que depende de una referencia que no tengo a mano.

### Estado tras la segunda pasada

| Hallazgo | Estado | Evidencia de la segunda pasada |
|---|---|---|
| H1. IC de capacidad con g.l. equivocados | Corregido y verificado | ν derivados a mano y por simulación del CV; cobertura 0.944 a 0.955 en seis casos (sección 7); pruebas disputadas reescritas y en verde. Detalles: docstring "0,6045·k" (límite 0.6050·k) y H26 |
| H2. Especificaciones no finitas | Corregido y verificado | ValueError en la librería, 422 en la API, `capability_verdict(NaN)` rechaza |
| H3. Críticos de Anderson-Darling | Corregido y verificado | tamaño real a ±0.003 del nominal para n de 8 a 200 y α = 0.10, 0.05, 0.01 (100 000 réplicas); crítico positivo para todo n |
| H4. Fase I y Fase II: excluidos | Corregido y verificado | "los 24 subgrupos retenidos están en control … se excluyó 1 subgrupo"; en Fase II "Esas exclusiones son de la Fase I y no forman parte de este gráfico" |
| H5. Reglas de racha en paneles asimétricos | Corregido con observaciones | MR solo WE1 y N1 (verificado); N3 y N4 sin aumento de falsas alarmas (confirmado: 421.6 y 601.0 exactos). Abiertos: H18, H19, H24 y el motivo de R y S con límites simétricos (H25) |
| H6. Supuestos "se cumplen" por no rechazar | Corregido con observaciones | resumen "no hay evidencia en contra … no que esté demostrado"; Ljung-Box débil descrito como débil, sin AR(1). Abiertos: H21 y H23 |
| H7. Capacidad sin estabilidad | Corregido con observaciones | resumen condicional (None) o "no se puede declarar" (False). Abierto: H20 |
| H8. Nomograma inventado | Corregido y verificado | `test_muestreo_no_inventa_lectura_de_nomograma` |
| H9. Razón de sigmas | Corregido y verificado | frecuencia de la afirmación con datos estables 4.9 % a 5.9 % (I-MR, congelada), 0 % a 1.3 % con subgrupos |
| H10. Rachas con aproximación normal | Corregido y verificado | exacta para todo n; log-gamma con error ≤ 9e-12 frente a aritmética racional |
| H11. Texto de N8 del mismo lado | Corregido y verificado | "indica un desplazamiento del nivel del proceso, no dos poblaciones" |
| H12. Concordancia y coma decimal | Corregido con observaciones | concordancias de la primera pasada corregidas; coma decimal en todos los módulos (`test_numeros_con_coma_decimal`); mejora en Fase II resumida como "posible mejora". Abierto: H25 |
| H13. `fmt` imprimía "0" | Corregido y verificado | notación científica con coma ("3,798·10⁻⁸") |
| H14. Cpm con objetivo fuera de especificación | Corregido y verificado | Cpm null y advertencia |
| H15. Redondeo al par en la hipergeométrica | Corregido y verificado | 0 discrepancias en 79 992 casos frente a `Decimal` |
| H16. `limit_width` = 0 | Corregido y verificado | `SPCInputError` |
| S1. Umbral unilateral | Resuelta | usa 1.25 unilateral; la escala de cuatro categorías se cita como convención; 1.25 corroborado en fuente secundaria (sección 7) |
| S2. σ con n variable | Resuelta | desviación combinada s_p/c4(ν + 1), ν = Σ(n_i - 1); cobertura 0.948 |
| S3. Normalidad con proceso inestable | Resuelta | advertencia y resumen lo dicen |
| S4. Cota unilateral | Resuelta y verificada | Ĉ - z_{0.95}·EE; cobertura 0.953 y 0.955 |
| S5. Colas pesadas frente a inestabilidad | Resuelta | "Puede deberse a colas más pesadas … o a inestabilidad" |

### Errores confirmados de la primera pasada

**H1. Intervalos de confianza de capacidad con grados de libertad equivocados (gravedad alta).** *Estado: corregido y verificado.* `capability.py`; `interpretation.py`. Los IC de Cp (χ²) y de Cpk, Cpl, Cpu (Bissell) usaban n - 1 con n = total de observaciones aunque σ saliera de R̄/d2, S̄/c4, MR̄/d2 o de límites congelados. Cobertura real del IC "95 %": 0.915 con R̄/d2 (25 × 5), 0.868 con MR̄/d2 (N = 50) y 0.601 con σ congelada de una Fase I de 25 × 5 y 500 datos nuevos. Valor correcto: ν ≈ d2²·m/(2d3²) para R̄/d2, ν ≈ 0.95·m(n-1) para S̄/c4, ν ≈ 0.61(N - 1) para MR̄/d2 y, con límites congelados, el ν de la Fase I. Hoy el software usa esos ν (`sigma_dof`, `frozen_sigma_dof`) y la cobertura es nominal (sección 7).

**H2. Especificaciones no finitas aceptadas, veredicto "excelente" con Cpk nulo (gravedad alta en robustez).** *Estado: corregido y verificado.* Caso mínimo: `analyze_capability([[1, 2], [2, 3.5], [1.5, 2.5]], lsl=float("nan"), usl=5.0)` devolvía `verdict = "excellent"`. Hoy: ValueError; por la API, 422.

**H3. Valores críticos de Anderson-Darling inexactos y degenerados con n pequeño (gravedad media).** *Estado: corregido y verificado.* La combinación de Stephens (1974) con (1 + 4/n - 25/n²) daba un tamaño real de 0.038 (n = 8) a 0.061 (n = 15) para α = 0.05 y un crítico negativo con n = 3. Hoy usa D'Agostino y Stephens (1986) con (1 + 0.75/n + 2.25/n²), la misma tabla que scipy 1.18.1; tamaño real en la sección 6.

**H4. La Fase I declaraba "en control" a los subgrupos excluidos y la Fase II repetía las exclusiones de Fase I con etiquetas equivocadas (gravedad media).** *Estado: corregido y verificado.* Casos mínimos: `phase_one("c", [5, 6, 4, 30, 5, 6, 5, 4, 6, 5], excluded=[(3, "lote defectuoso")])` y la Fase II del jugo de naranja con etiquetas "F2-k". Verificado también con `data/ejemplos/sintetico_fase1.csv` sin el subgrupo 12 y `sintetico_fase2.csv`.

**H5. WE4, N2 y N3 en R, S, MR y atributos: más falsas alarmas sin advertencia (gravedad media).** *Estado: corregido con observaciones.* Decisión aplicada: en MR solo WE1 y N1; en R, S y atributos truncados WE4 y N2 con advertencia y N3 y N4 sin ella porque dependen solo del orden. La decisión es correcta y su justificación también (sección 5). Quedan H18 (el hallazgo de `interpretation.py` contradice a `rules.py` sobre N3 y N4), H19 (la advertencia de WE4 y N2 es falsa con empates en la LC), H24 (texto del panel MR) y el motivo de R y S con límites simétricos (H25).

**H6. Supuestos: "se cumplen" por no rechazar (gravedad media).** *Estado: corregido con observaciones.* El resumen ya no afirma cumplimiento, recuerda la poca potencia con n < 20 y avisa del error tipo I conjunto (7 % a 13 %). El caso de Ljung-Box con `sintetico_fase1` sin el subgrupo 12 se presenta como evidencia débil, con el signo y el rezago correctos y sin AR(1). Quedan H21 (forma de la distribución por ruido de muestreo) y H23 (probabilidad de rezagos fuera de banda por azar sobrestimada).

**H7. Capacidad: veredicto sin reserva cuando la estabilidad no se informó, y veredicto "adecuado" con proceso inestable (gravedad media).** *Estado: corregido con observaciones.* El resumen es condicional con `is_stable=None` y dice "no se puede declarar su capacidad" con `is_stable=False`. Queda H20: un hallazgo sigue afirmando "con 95 % de confianza Cpk supera el mínimo" en esos dos casos.

**H8. Muestreo: afirmación inventada sobre el nomograma (gravedad media-baja).** *Estado: corregido y verificado.*

**H9. Capacidad: "Hay variación entre subgrupos" por una razón de sigmas sin prueba (gravedad media-baja).** *Estado: corregido y verificado.* El umbral depende de N y ν; la afirmación aparece con datos estables en el 5 % nominal (sección 7) y está redactada como indicio.

**H10. Prueba de rachas: aproximación normal sin corrección de continuidad para n1 + n2 > 60 (gravedad baja).** *Estado: corregido y verificado.* Distribución exacta para todo n; con n1 = n2 = 31 y R = 24 da 0.05413.

**H11. Texto de N8 incorrecto cuando los 8 puntos están del mismo lado (gravedad baja).** *Estado: corregido y verificado.*

**H12. Concordancia y redacción (gravedad baja).** *Estado: corregido con observaciones.* "Se excluyó 1 subgrupo", "Shapiro-Wilk y Anderson-Darling rechazan", "el subgrupo 7", coma decimal y la mejora en Fase II están corregidos. Quedan los detalles de H25.

**H13. `fmt` imprimía "0" para valores positivos menores que 5e-7 (gravedad baja).** *Estado: corregido y verificado.*

**H14. Cpm con objetivo fuera de especificación (gravedad baja).** *Estado: corregido y verificado.*

**H15. Redondeo al par en la hipergeométrica (gravedad baja).** *Estado: corregido y verificado.*

**H16. `limit_width` = 0 en límites congelados se cambiaba en silencio por 3 (gravedad baja).** *Estado: corregido y verificado.*

### Errores confirmados nuevos (segunda pasada)

**H20. Capacidad: con proceso inestable o sin estabilidad confirmada, un hallazgo afirma "con 95 % de confianza Cpk supera el mínimo" (gravedad media).** `interpretation.py`, líneas 1208-1221 (el bloque de la cota unilateral no mira `is_stable`). Caso mínimo: `analyze_capability(np.random.default_rng(2).normal(10, 0.2, (25, 5)).tolist(), lsl=8.5, usl=11.5, is_stable=False, is_normal=True)`: el resumen dice "no se puede declarar su capacidad" y un hallazgo dice "La cota inferior de confianza unilateral del 95 % para Cpk es 2,14: con 95 % de confianza Cpk supera el mínimo de 1,33". Con un proceso inestable Cpk no está definido como parámetro del proceso futuro, así que esa afirmación no está soportada; con `is_stable=None` pasa lo mismo. Correcto: con `is_stable` distinto de True, condicionar la frase ("si el proceso fuera estable, la cota … sería …") o no darla. Prueba: `test_val_interpretacion.py::test_capacidad_no_estable_no_afirma_con_confianza` (dos casos).

**H21. Supuestos: "Forma de la distribución" afirma colas o asimetría por ruido de muestreo (gravedad media-baja).** `interpretation.py`, líneas 192-213 (umbrales fijos |G1| ≥ 0.5 y |G2| ≥ 1). Caso mínimo: las 8 observaciones [10.1, 9.8, 10.3, 10.0, 9.7, 10.2, 9.9, 10.4] dan G2 = -1.2 y el texto afirma "colas más livianas que la normal, lo que puede indicar mezcla de dos fuentes o datos truncados", aunque el error estándar de G2 con n = 8 es 1.48 y las dos pruebas de normalidad no rechazan. Con datos normales el hallazgo aparece en el 75 % de las muestras de n = 8, el 43 % con n = 20 y el 30 % con n = 30 (sección 6, simulación propia de 40 000 muestras por n). Correcto: comparar con el error estándar (EE(G1) = √(6n(n - 1)/((n - 2)(n + 1)(n + 3))), EE(G2) = √(4(n² - 1)EE(G1)²/((n - 3)(n + 5)))) y redactarlo como descripción de la muestra cuando no lo supera. Prueba: `::test_forma_no_se_afirma_dentro_del_error_de_muestreo`.

**H18. N3 y N4 en paneles asimétricos: el hallazgo contradice la advertencia (gravedad media-baja).** `interpretation.py`, línea 1475 (`_RUN_RULES = {"WE4", "N2", "N3", "N4"}`) y líneas 1623-1631. Caso mínimo: X-barra-R con seis rangos crecientes (`test_val_interpretacion.py::_r_con_tendencia`) y reglas WE1 y N3. La misma salida dice en un hallazgo "las reglas de racha (N3) dan falsas alarmas más a menudo que en un gráfico simétrico" y en una advertencia "la regla N3 depende solo del orden de los valores, así que la asimetría no aumenta su tasa de falsas alarmas". También con `data/ejemplos/sintetico_u_n_variable.csv` y todas las reglas (N4 en el punto 24). La advertencia es la correcta: el ARL0 de N3 es 421.6 en cualquier estadístico continuo i.i.d. y la simulación en R con n = 2 da 418.4 ± 2.4. Correcto: limitar ese hallazgo a WE4 y N2. Pruebas: `::test_n3_en_panel_r_sin_contradiccion`, `::test_n4_en_u_sintetico_sin_contradiccion`.

**H19. WE4 y N2 con la línea central sobre un conteo posible: la advertencia dice "más falsas alarmas" y son muchas menos (gravedad media-baja).** `rules.py`, líneas 534-539 (`asymmetry_warning`), e `interpretation.py`, líneas 1625-1631 (este último, en todo panel de atributos aunque no esté truncado). Caso mínimo: `phase_one("c", [1]*8 + [3, 2]*8 + [2], rules=["WE1", "WE4"])` (c̄ = 50/25 = 2 exacto) da WE4 en el índice 7 y la advertencia "su tasa de falsas alarmas es mayor que la nominal". Valor correcto, por la cadena propia con empates: ARL0 de WE4 = 1 924 con c̄ = 2, 1 071 con c̄ = 4 y 4 508 en un gráfico p con n = 100 y n·p̄ = 1, frente a 255 nominal, porque los puntos iguales a la LC cortan la racha; la simulación con la lógica del software coincide (`test_we4_con_empates_en_la_linea_central`). Sin empates (por ejemplo c̄ = 4.25) la advertencia es correcta (ARL0 166). Correcto: decir que el ARL0 difiere del nominal y en qué dirección según haya o no conteos sobre la LC. Prueba: `test_val_reglas.py::test_advertencia_we4_con_linea_central_entera`.

**H22. Diseño: "el gráfico no puede señalar mejoras" con WE4 aplicada (gravedad baja-media).** `interpretation.py`, líneas 842-847. Caso mínimo: `compute_arl("c", c0=4, c1=[2.0, 8.0], rules=["WE1", "WE4"])`: el texto dice "no puede señalar mejoras … las filas con valores menores al de control muestran ARL1 muy grandes" y la misma salida informa ARL1 = 16.95 para c1 = 2 (120 363 con WE1 sola). WE4 detecta rachas por debajo de la LC. Correcto: dar esa frase solo si las reglas aplicadas son WE1 o N1. Prueba: `test_val_diseno.py::test_diseno_con_we4_puede_senalar_mejoras`.

**H24. Panel MR: "cambió la variabilidad dentro de los subgrupos" en un gráfico de individuales (gravedad baja).** `interpretation.py`, líneas 1632-1654. Caso mínimo: `data/ejemplos/sintetico_i_mr.csv` (un MR fuera en la observación 16): "Los puntos fuera de límites del gráfico de rangos móviles indican que cambió la variabilidad dentro de los subgrupos … corrija primero la dispersión". En I-MR no hay subgrupos; un MR grande aislado indica un salto entre dos observaciones consecutivas (un dato atípico o un cambio de nivel, visible en el gráfico I) más que un cambio de la variabilidad. Prueba: `::test_mr_no_habla_de_subgrupos`.

**H23. Probabilidad de rezagos fuera de banda por azar sobrestimada (gravedad baja).** `interpretation.py`, líneas 234-235 (`expected_out = alpha * m`, `p_any = 1 - (1 - alpha) ** m`). Caso mínimo: `sintetico_fase1.csv` sin el subgrupo 12: "la probabilidad de ver al menos uno fuera por azar es 0,64"; por simulación es 0.52 (n = 120, m = 20) y el número esperado 0.76, no 1 (sección 6). Hace que la evidencia parezca más débil de lo que es. Correcto: usar Var(r_k) = (n - k)/(n(n + 2)) o simular. Prueba: `::test_probabilidad_de_rezago_fuera_por_azar`.

**H26. ν de la σ congelada de I-MR con exclusiones intermedias, levemente sobrestimado (gravedad baja).** `capability.py`, líneas 215-231 (`frozen_sigma_dof` usa points_used - 1 rangos). Caso mínimo: 30 individuales con los puntos 5, 15 y 25 excluidos: ν = 15.92 frente a 14.71 exacto (8 %); con 6 exclusiones, 20 % (tabla de la sección 7). Los límites congelados traen `excluded` con índices, así que el número real de MR y de pares vecinos se puede reconstruir. El efecto sobre la cobertura es pequeño. Prueba: `test_val_capacidad.py::test_nu_congelado_i_mr_con_exclusiones`.

**H17. `data/referencia/p.json` y `np.json` con errores aritméticos (gravedad baja; archivos de `datos-prueba`).** `p.json`, muestra de n = 80: σ = √(0.0625·0.9375/80) = √0.000732421875 = 0.0270633 (el JSON dice 0.0270641), 3σ = 0.0811899 y LCS = 0.1436899 (el JSON dice 0.0811922 y 0.1436922, en `calculo` y en `esperado.ucl_por_muestra[4]`). `np.json`: √6.1644 = 2.4828210 (el JSON dice 2.482830), 3σ = 7.4484629 y LCS = 14.04846 (el JSON dice 7.448490 y 14.04849, en `calculo` y en `esperado.ucl`). Recalculado con 30 dígitos (`decimal`). Las conclusiones (punto 5 fuera en ambos) no cambian y el README redondeado (0,1437 y 14,0485) es correcto. Lo debe corregir el agente `datos-prueba`.

**H25. Redacción y detalles de texto (gravedad baja).**
- `interpretation.py`, línea 1237: "está por debajo de el mínimo" (debe ser "del"). Prueba: `::test_redaccion_de_el`.
- `rules.py`, líneas 549-550: al unir las dos partes de la advertencia de asimetría solo se pone mayúscula a la primera ("… no una prueba. las reglas N3 y N4 …"). Prueba: `::test_redaccion_mayuscula_advertencia_asimetria`.
- `interpretation.py`, líneas 1497-1500: "LCI entre 0 y 0" cuando el LCI está truncado en todos los puntos. Prueba: `::test_redaccion_lci_constante`.
- `interpretation.py`, línea 882: "1 unidades inspeccionadas por hora" (gráfico c o individuales). Prueba: `test_val_diseno.py::test_concordancia_carga_unitaria`.
- `rules.py`, líneas 489-490: el motivo "los límites no son simétricos alrededor de la línea central" es falso en R con n ≥ 7 y en S con n ≥ 6 (por ejemplo `sintetico_xbar_s_n10.csv`: 0.3662, 1.291, 2.216). Debe decir que la distribución del estadístico es asimétrica (sección 5). Prueba: `::test_motivo_de_zonas_en_s_con_limites_simetricos`.
- `interpretation.py`, líneas 894-899: "multiplican las falsas alarmas por 0,994" cuando la diferencia está dentro del error de simulación (p0 = 0.01, n = 100, ARL0 54.74 ± 1.22 frente a 54.42).
- `rules.py`, línea 555: `_fmt` con 6 cifras escribe "1,23457e+06" para valores graficados grandes.
- `capability.py`, línea 58: "ν ≈ 0,6045·k"; el límite es 0.6050·k.
- `assumptions.py`, líneas 219-223: con n = 3 la prueba de Anderson-Darling no puede rechazar (máximo de A² 0.4878 < 0.5013), no "casi no tiene potencia" (solo por la librería).

### Sospechas y observaciones (no confirmadas o de criterio)

- **S6. Muchas reglas a la vez.** Con las 12 reglas el ARL0 de individuales es 66.2 (EE 0.8); en 25 puntos en control la probabilidad de alguna señal es del orden de 0.3. Los datos estables de `sintetico_xbar_s_n10.csv` y `sintetico_np.csv` dan señales. Los cálculos son correctos, pero la interpretación de un gráfico no lo advierte; conviene una frase cuando hay más reglas que WE1.
- **S7. Veredicto del resumen por estimación puntual.** Con `sintetico_xbar_r_en_control` el resumen dice "veredicto de capacidad adecuado" (Cpk = 1.41) y un hallazgo aclara que la cota unilateral (1.24) no alcanza 1.33. Es la convención usual, pero el resumen podría decir que el veredicto es el de la estimación puntual.
- **S8. IC de Cp con σ corregida por sesgo.** El intervalo χ² es exacto para s (o s_p) sin corregir; el software lo aplica a S̄/c4 y s_p/c4(ν + 1). El desplazamiento es del 0.1 % al 0.3 % y la cobertura medida es nominal: sin efecto práctico.
- **1.25 unilateral.** Corroborado en dos fuentes secundarias (sección 7), no en la 6.ª edición.

## 12. Veredicto sobre las 18 dudas de los autores

| # | Duda | Veredicto |
|---|---|---|
| 1 | WE4 y N2 en R, S, MR y atributos | Primera pasada: defendible aplicarlas, pero no sin advertir. Segunda pasada: decisión aplicada (MR solo WE1 y N1; WE4 y N2 con advertencia; N3 y N4 sin aumento por depender del orden) y correcta. La advertencia de WE4 y N2 no vale cuando la LC es un conteo posible (H19), y el hallazgo de la interpretación contradice lo de N3 y N4 (H18) |
| 2 | N8 sin exigir ambos lados | Defendible (es la convención de Minitab; si los 8 están del mismo lado, N6 se activa antes). El texto ya distingue desplazamiento de mezcla (H11 corregido) |
| 3 | Comparaciones estrictas y ventana parcial al inicio | Correcto. Un punto sobre el límite no está "más allá". La ventana parcial equivale al estado cero de Champ y Woodall (1987): la cadena propia con ventana parcial reproduce 91.75 |
| 4 | N3 y N4 sobre valores graficados, también con n variable | Defendible: la tendencia es del nivel del proceso. Con n variable las p_i no son idénticamente distribuidas y el ARL0 de N3 y N4 deja de ser exactamente 421.6 y 601.0; con conteos pequeños los empates casi anulan N3 |
| 5 | MR en el promedio solo si sus dos puntos están retenidos | Correcto; verificado con un caso propio (MR̄ = 1.5) |
| 6 | d2 y d3 con 6 decimales; d3(19) = 0.734 en el apéndice | El software tiene razón: 0.7334815 por dos integrales distintas |
| 7 | Tabla 7.4 y transcripciones de memoria | Totales consistentes (234/2450 = 0.096). La muestra 11 queda fuera con esos datos; los pares (n_i, D_i) no son verificables contra el libro |
| 8 | Fase I no itera sola | Correcto: Montgomery pide investigar cada señal y excluir solo con causa asignable |
| 9 | Señal en el punto donde se completa y repetida mientras persista | Correcto y consistente con Minitab |
| 10 | Cpm con σ de largo plazo y min(T - LSL, USL - T)/(3τ) | Defendible; T fuera de especificación hoy deja Cpm en null con advertencia (H14 corregido) |
| 11 | IC con n - 1 aunque σ sea R̄/d2 o congelada; Bissell en índices unilaterales | Error en la primera pasada (H1); corregido y verificado. Bissell en Cpl, Cpu, Ppl, Ppu y Ppk está bien: es la aproximación delta de primer orden |
| 12 | n variable: promedio de R_i/d2(n_i) o S_i/c4(n_i) | Primera pasada: ineficiente y mal citado (S2). Hoy usa la desviación combinada corregida por c4(ν + 1) con ν = Σ(n_i - 1): correcto y verificado (cobertura 0.948) |
| 13 | Límites congelados: σ de Fase I con media actual | Defendible; ν de la Fase I correcto (cobertura 0.950 y 0.955); independencia de x̄ y σ̂ garantizada por construcción. Detalle en I-MR con exclusiones (H26) |
| 14 | Anderson-Darling con Stephens (1974) y (1 + 4/n - 25/n²) | Error en la primera pasada (H3); hoy D'Agostino y Stephens (1986), tamaño real nominal |
| 15 | Rachas exactas hasta 60, sin corrección de continuidad; Ljung-Box con m g.l.; banda ±z/√n | Rachas hoy exactas para todo n (H10 corregido, precisión ≤ 9e-12). Ljung-Box con m g.l. correcto sin ajustar modelos. Banda ±z/√n correcta como aproximación de Bartlett; la probabilidad de salidas por azar que cita el texto está sobrestimada (H23) |
| 16 | Punto sobre el límite en p y c; OC de simulación con WE1 sola | Correcto y coherente entre `rules.py` y `design.py` |
| 17 | Hipergeométrica con D = round(p·N); criterio de menor n; (89, 2) frente a (110, 3) | Criterio y búsqueda correctos; redondeo aritmético hoy (H15 corregido) |
| 18 | Capacidad con subgrupos construidos; citas de memoria | Válido como prueba de aritmética, no de los ejemplos |

### Dudas de la segunda pasada

| Duda | Veredicto |
|---|---|
| Las dos pruebas de cobertura en xfail no pueden pasar con ningún código | Los autores tienen razón: llamaban a `cp_confidence_interval(cp, N)` con el ν del libro. Reescritas para medir el camino real; pasan (sección 7) |
| N3 y N4 no cambian su ARL0 por la asimetría (437 en R con n = 2 frente a 424) | Confirmado con un cálculo exacto independiente: 421.6 y 601.0 para cualquier estadístico continuo i.i.d.; la diferencia simulada era ruido. Con conteos el ARL0 crece mucho por los empates |
| La advertencia atribuye más falsas alarmas solo a WE4 y N2 | Correcto para N3 y N4; para WE4 y N2 es falso cuando la LC es un conteo posible (H19). Además la interpretación contradice la advertencia (H18) |
| `design.py` aplica WE4 en p y c truncados sin avisar | No necesita la advertencia: el ARL simulado ya es el real (265.9 exacto frente a 263.1 ± 4.2). Sí debe quitar "no puede señalar mejoras" cuando WE4 está aplicada (H22) |
| Mínimo de 1.25 citado de memoria | Coincide con dos fuentes secundarias que lo atribuyen a Montgomery (2004 y 2012); falta cotejar la 6.ª ed. |
| Bissell con σ congelada supone independencia | Se cumple por construcción; lo que se supone es que σ no cambió, y el texto lo dice |
| En I-MR congelado ν usa points_used - 1 rangos | Sobrestima ν un 2.5 % a 20 % según las exclusiones (H26); se puede corregir con `excluded` |
| R con n ≥ 7 sigue marcado como asimétrico | Correcto marcarlo: las colas de R no son las normales aunque los límites sean simétricos. El motivo escrito es falso (H25) |

## 13. Archivos de la validación

- `api/tests/validation/independiente.py`: cálculos independientes (constantes, reglas con bucles, cadenas de Markov con y sin empates, ARL exacto de N3 y N4 por ecuación integral, Ljung-Box por FFT, rachas por enumeración y por aritmética racional, tamaño de Anderson-Darling, planes por fuerza bruta, Monte Carlo del plan doble).
- `api/tests/validation/test_val_constantes.py`, `test_val_graficos.py`, `test_val_reglas.py`, `test_val_supuestos.py`, `test_val_capacidad.py`, `test_val_diseno.py`, `test_val_muestreo.py`, `test_val_interpretacion.py`: 182 pruebas que pasan y 15 hallazgos abiertos `xfail(strict=True)` (H18 a H26).
- `api/tests/validation/reporte.py`: imprime las tablas de las secciones 3 a 9 (actualizado: cobertura con el ν del software y con N - 1, N3 y N4 exactos, WE4 con empates).
