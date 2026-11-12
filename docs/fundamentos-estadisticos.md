# Fundamentos estadísticos del software CEP

Este documento reúne cada fórmula que usa `api/app/spc/`, con su notación, sus supuestos y su referencia en formato APA 7. Es la base de la sección de metodología del informe. Cuando el software se aparta de la fuente, o cuando la validación (`docs/validacion.md`) encontró una limitación, se indica en un recuadro "Nota de validación". Esta versión corresponde a la segunda pasada de la validación (2026-11-11), después de las correcciones de los autores.

## 1. Notación

| Símbolo | Significado |
|---|---|
| m | número de subgrupos (o de muestras en atributos) |
| n, n_i | tamaño del subgrupo (constante o del subgrupo i) |
| N | número total de observaciones (capacidad, supuestos) o tamaño de lote (muestreo) |
| x_ij | observación j del subgrupo i |
| x̄_i, R_i, S_i | media, rango y desviación estándar muestral (divisor n - 1) del subgrupo i |
| x̿, R̄, S̄ | promedios de x̄_i, R_i y S_i sobre los subgrupos retenidos |
| MR_i | rango móvil \|x_i - x_(i-1)\| |
| μ, σ | media y desviación estándar del proceso |
| σ_w, σ_o | sigma de corto plazo (dentro de subgrupos) y de largo plazo (global) |
| ν | grados de libertad (efectivos) del estimador de σ de corto plazo |
| L | ancho de los límites en desviaciones estándar del estadístico (3 por defecto) |
| Φ, φ | función de distribución y densidad normal estándar |
| z_q | cuantil q de la normal estándar |
| χ²_(q, ν) | cuantil q de la chi-cuadrado con ν grados de libertad |
| LSL, USL, T | límites de especificación inferior y superior y valor objetivo |

Supuesto común a todos los gráficos de Shewhart y a los índices de capacidad: observaciones independientes e idénticamente distribuidas mientras el proceso está en control; normales en los gráficos por variables y en los índices (Montgomery, 2009, caps. 5, 6 y 8).

## 2. Constantes de los gráficos por variables

Sea W = R/σ el rango relativo de n normales independientes.

- d2(n) = E[W] = ∫ [1 - Φ(x)^n - (1 - Φ(x))^n] dx (Tippett, 1925; Montgomery, 2009, cap. 6).
- d3(n) = sd(W), con E[W²] = 2 ∫∫_(x<y) [1 - Φ(y)^n - (1 - Φ(x))^n + (Φ(y) - Φ(x))^n] dx dy.
- c4(n) = E[S]/σ = √(2/(n - 1)) · Γ(n/2)/Γ((n - 1)/2) (Montgomery, 2009, cap. 6 y apéndice VI).

El software tabula d2 y d3 con seis decimales por integración numérica para n = 2 a 25 y calcula c4 exacto con la función gamma. Los demás factores se derivan de esos tres, para cualquier L:

| Factor | Fórmula | Uso |
|---|---|---|
| A | L/√n | X-barra con σ conocida: μ ± A·σ |
| A2 | L/(d2√n) | X-barra con R̄: x̿ ± A2·R̄ |
| A3 | L/(c4√n) | X-barra con S̄: x̿ ± A3·S̄ |
| B3, B4 | max(0, 1 - L√(1 - c4²)/c4), 1 + L√(1 - c4²)/c4 | gráfico S con S̄ |
| B5, B6 | max(0, c4 - L√(1 - c4²)), c4 + L√(1 - c4²) | gráfico S con σ conocida |
| D1, D2 | max(0, d2 - L·d3), d2 + L·d3 | gráfico R con σ conocida |
| D3, D4 | max(0, 1 - L·d3/d2), 1 + L·d3/d2 | gráfico R con R̄ |

> Nota de validación. Con otras dos integrales (esperanza del máximo y densidad del rango) las constantes coinciden con el software a 5e-7. La tabla del apéndice VI imprime d3(19) = 0.734; el valor es 0.73348.

## 3. Gráficos por variables

Cada gráfico se construye en dos pasos: estimar (μ, σ) con los subgrupos retenidos y construir los límites a partir de (μ, σ, n, L). Así los límites de Fase II se reconstruyen con cualquier n.

### 3.1 X-barra y R

- μ̂ = x̿; σ̂ = R̄/d2(n) (Montgomery, 2009, cap. 6).
- X-barra: LC = μ̂, límites μ̂ ± L·σ̂/√n (equivale a x̿ ± A2·R̄).
- R: LC = d2·σ̂ = R̄, LCS = (d2 + L·d3)σ̂ = D4·R̄, LCI = max(0, (d2 - L·d3)σ̂) = D3·R̄.
- Restricciones del software: n constante entre 2 y 25; con n > 10 advierte que S es más eficiente.

### 3.2 X-barra y S

- μ̂ = x̿; σ̂ = S̄/c4(n).
- X-barra: μ̂ ± L·σ̂/√n (equivale a x̿ ± A3·S̄).
- S: LC = c4·σ̂ = S̄, límites (c4 ± L√(1 - c4²))σ̂, con el inferior truncado en 0 (B3·S̄ y B4·S̄).

### 3.3 Individuales y rango móvil (I-MR)

- MR_i = |x_i - x_(i-1)|, i = 2, …, m; σ̂ = MR̄/d2(2), con d2(2) = 2/√π = 1.128379.
- I: x̄ ± L·σ̂. MR: LC = MR̄, LCS = D4(2)·MR̄, LCI = 0.
- Con exclusiones, un MR entra en MR̄ solo si sus dos puntos están retenidos (no se forman rangos entre observaciones no consecutivas).
- Dos MR consecutivos comparten una observación: con U = x_i - x_(i-1) y V = x_(i+1) - x_i, Corr(U, V) = -1/2 y Cov(MR_i, MR_(i+1)) = σ²[(2√3 - 4)/π + 1/3] = 0.16275σ² (sección 8.3). Por esa correlación, y por la asimetría de MR, en el panel MR el software solo evalúa la regla de un punto fuera de los límites (WE1 y N1; sección 6).

### 3.4 Límites con parámetros conocidos (Fase II)

Con (μ, σ) congelados y un n nuevo: X-barra μ ± L·σ/√n; R (d2(n) ± L·d3(n))σ; S (c4(n) ± L√(1 - c4(n)²))σ (Montgomery, 2009, cap. 6).

> Nota de validación. El gráfico R con límites de 3σ no tiene probabilidad de falsa alarma 0.0027: con n = 2 es 0.0091 (ARL0 ≈ 109) y con n = 5 ARL0 ≈ 217, porque la distribución de R es asimétrica. Aunque para n ≥ 7 (R) y n ≥ 6 (S) el LCI ya no se trunca y los límites quedan simétricos, las colas siguen sin ser normales: con n = 7, P(R > R̄ + 2σ_R) = 0.033 y P(R < R̄ - 2σ_R) = 0.010, frente a 0.023 de cada lado; más allá de 3σ, 0.0044 arriba y casi 0 abajo.

## 4. Gráficos por atributos

| Gráfico | Parámetro estimado | Estadístico graficado | Límites |
|---|---|---|---|
| p | p̄ = ΣD_i/Σn_i | p_i = D_i/n_i | p̄ ± L√(p̄(1 - p̄)/n_i) |
| np | p̄ (n constante) | D_i | n·p̄ ± L√(n·p̄(1 - p̄)) |
| c | c̄ = promedio de c_i | c_i | c̄ ± L√c̄ |
| u | ū = Σc_i/Σn_i | u_i = c_i/n_i | ū ± L√(ū/n_i) |

Fuente: Montgomery (2009, cap. 7). Supuestos: D_i ~ binomial(n_i, p) independientes en p y np; c_i ~ Poisson en c y u, con área de oportunidad constante en c. Con n variable el software usa límites por punto. El LCI negativo se trunca en 0 y el LCS de p en 1 (de np en n). Si algún límite se truncó, las reglas de zonas no se aplican en el panel.

Selección del gráfico (asistente): unidades no conformes, distribución binomial → np si n es constante, p si varía; no conformidades, distribución de Poisson → c si la unidad de inspección es constante, u si varía.

## 5. Fase I y Fase II

Montgomery (2009, cap. 5) distingue la Fase I, retrospectiva, en la que se establecen límites de prueba y se depuran los puntos con causa asignable, de la Fase II, en la que se monitorea con esos límites.

- Fase I: (μ, σ) o (p̄, c̄, ū) se estiman sin los puntos excluidos. Todos los puntos se grafican y los excluidos se marcan; los excluidos no reciben señal y las corridas los saltan. Cada exclusión exige una causa documentada. El software no itera solo: el usuario investiga, excluye y recalcula. La conclusión "en control" se refiere a los subgrupos retenidos.
- Fase II: los parámetros congelados nunca se recalculan con los datos nuevos. En variables, si el n cambia, los límites se reconstruyen con la sección 3.4; en p y u, por punto con el n_i de cada muestra. Las exclusiones de la Fase I se citan como origen de los límites, no como puntos del gráfico.
- Recomendación de tamaño: al menos 20 a 25 subgrupos en Fase I (Montgomery, 2009, cap. 6). El ancho L congelado debe ser positivo.

## 6. Reglas de corrida

z_t = (x_t - LC_t)/σ_t, con σ_t la desviación estándar del estadístico graficado en el punto t (por punto si n varía). Zona C: |z| < 1; zona B: 1 a 2; zona A: 2 a 3.

| Regla | Definición | Necesita zonas |
|---|---|---|
| WE1, N1 | un punto fuera de los límites de control | no |
| WE2, N5 | 2 de 3 consecutivos con z > 2 (o z < -2), del mismo lado | sí |
| WE3, N6 | 4 de 5 consecutivos con z > 1 (o z < -1), del mismo lado | sí |
| WE4 | 8 consecutivos del mismo lado de la LC | no |
| N2 | 9 consecutivos del mismo lado de la LC | no |
| N3 | 6 consecutivos estrictamente crecientes o decrecientes | no |
| N4 | 14 consecutivos que alternan subida y bajada | no |
| N7 | 15 consecutivos con \|z\| < 1 | sí |
| N8 | 8 consecutivos con \|z\| > 1, a cualquier lado | sí |

Fuentes: Western Electric Company (1956); Nelson (1984); Montgomery (2009, cap. 5). Convenciones del software: comparaciones estrictas (un punto sobre un límite no cuenta); un punto sobre la LC corta la racha; en reglas k de m la ventana es parcial al inicio de la serie, lo que equivale al ARL de estado cero de Champ y Woodall (1987); la señal se marca en el punto donde se completa y se repite mientras la condición persista; N3 y N4 se evalúan sobre los valores graficados; N8 con los 8 puntos de un mismo lado se describe como desplazamiento y con puntos de ambos lados como mezcla.

**Criterio de reglas por panel** (decisión de los autores tras el hallazgo H5):

| Panel | Reglas que se evalúan | Motivo |
|---|---|---|
| X-barra, individuales | las doce | estadístico simétrico (normal) |
| p, np, c, u sin ningún límite truncado | las doce | límites simétricos; zonas con el σ de cada punto |
| R, S (cualquier n) y atributos con algún límite truncado | WE1, N1, WE4, N2, N3, N4; se omiten WE2, WE3, N5 a N8 con su motivo | sin zonas A, B y C válidas: distribución asimétrica o límite truncado |
| MR | solo WE1 y N1 | MR consecutivos correlacionados y asimétricos |

En los paneles asimétricos, si se aplicó WE4 o N2 se advierte que P(estadístico > LC) ≠ 1/2 y que su ARL0 no es el nominal; de N3 y N4 se dice que dependen solo del orden.

ARL0 de referencia (cálculos propios de la validación): WE4 sola 255 y N2 sola 511 si P(arriba de la LC) = 1/2. N3 sola 421.6 y N4 sola 601.0 para cualquier estadístico continuo i.i.d.: con observaciones i.i.d. continuas todas las ordenaciones son equiprobables, así que el ARL de una regla que depende solo del orden no depende de la distribución. Se obtuvieron resolviendo en una malla la ecuación integral del ARL en el valor del último punto, transformado a uniforme (estado: dirección y largo de la cadena), de la misma manera que Champ y Woodall (1987) plantean la cadena de Markov para las reglas de zonas. Las cuatro reglas WE juntas en un gráfico de individuales dan ARL0 = 91.75, no 370.4; las doce reglas juntas, alrededor de 66.

> Nota de validación. Las reglas que solo usan la línea central (WE4, N2) tienen un ARL0 distinto del nominal cuando el estadístico es asimétrico o discreto. Sin empates es menor: WE4 sola da 174 en R con n = 2, 236 con n = 5 y 43 en un gráfico p con n = 100 y p̄ = 0.0102. Con la LC sobre un conteo posible (c̄ = 2, c̄ = 4 o n·p̄ = 1) los puntos sobre la LC cortan la racha y el ARL0 es mucho mayor: 1 924, 1 071 y 4 508, con la correspondiente pérdida de sensibilidad. N3 y N4 no cambian por la asimetría con datos continuos; con conteos los empates las vuelven casi inertes (N3 no señaló en 8 000 puntos Poisson(4)). Con n variable las p_i no son idénticamente distribuidas y los valores 421.6 y 601.0 son aproximados.

## 7. Validación de supuestos

### 7.1 Normalidad

- Shapiro-Wilk: W = (Σ a_i x_(i))² / Σ(x_i - x̄)², con valor p de `scipy.stats.shapiro` (Shapiro y Wilk, 1965). Se rechaza H0 si p < α.
- Anderson-Darling con media y varianza estimadas: A² = -n - (1/n) Σ_(i=1..n) (2i - 1)[ln Φ(z_(i)) + ln(1 - Φ(z_(n+1-i)))], z = (x - x̄)/s (Stephens, 1974). Se rechaza H0 si A² supera el valor crítico A*²_α/(1 + 0.75/n + 2.25/n²), con A*²_α = 0.561, 0.631, 0.752, 0.873 y 1.035 para α = 0.15, 0.10, 0.05, 0.025 y 0.01 (D'Agostino y Stephens, 1986), interpolado linealmente en log α dentro de la tabla. Es la misma tabla que usa `scipy.stats.anderson` 1.18. El factor es mayor que 1 para todo n, así que el crítico siempre es positivo. Solo da valor crítico; el valor p va en null.

> Nota de validación. Con esta tabla el tamaño real medido por simulación (100 000 réplicas por caso) queda a ±0.003 del nominal para n de 8 a 200 y α = 0.10, 0.05 y 0.01, también con α interpolado. Con la tabla anterior (Stephens, 1974, con 1 + 4/n - 25/n²) era de 0.038 a 0.061 para α = 0.05. Con n = 3 el máximo posible de A² (0.488) queda por debajo del crítico de α = 0.05 y la prueba no puede rechazar; la API exige n ≥ 8.

- Gráfico de probabilidad normal: x_(j) frente a z_((j - 0.5)/n) (Montgomery, 2009, cap. 3).
- Descriptivos de forma: asimetría G1 y exceso de curtosis G2 ajustados. Bajo normalidad sus errores estándar son EE(G1) = √(6n(n - 1)/((n - 2)(n + 1)(n + 3))) y EE(G2) = √(4(n² - 1)·EE(G1)²/((n - 3)(n + 5))) (Joanes y Gill, 1998); con n = 8 son 0.75 y 1.48.
- Decisión conjunta: `is_normal` es verdadero si ninguna de las dos pruebas rechaza. El error tipo I conjunto es mayor que α (7 % con α = 0.05).

> Nota de validación. La interpretación comenta la forma de la distribución cuando |G1| ≥ 0.5 o |G2| ≥ 1, sin mirar n. Con datos normales esos umbrales se superan en el 75 % de las muestras de n = 8 y el 30 % de las de n = 30 (hallazgo H21): con n pequeño hay que compararlos con su error estándar.

### 7.2 Independencia

- Autocorrelación muestral: r_k = Σ_(t=1..n-k)(x_t - x̄)(x_(t+k) - x̄) / Σ_(t=1..n)(x_t - x̄)², k = 1, …, m, con m = min(20, n/4) por defecto (Box et al., 2008; Montgomery, 2009, cap. 10).
- Banda aproximada bajo ruido blanco: ±z_(1-α/2)/√n (Bartlett, 1946). Bajo H0, Var(r_k) = (n - k)/(n(n + 2)), algo menor que 1/n, y los r_k están correlacionados entre sí.
- Ljung-Box: Q = n(n + 2) Σ_(k=1..m) r_k²/(n - k) ~ χ²(m) bajo H0; no se restan grados de libertad porque no se ajusta un modelo ARMA (Ljung y Box, 1978).
- Prueba de rachas respecto a la mediana (Wald y Wolfowitz, 1940; Siegel y Castellan, 1988): se descartan las observaciones iguales a la mediana; con n1 arriba, n2 abajo y R rachas,
  - E[R] = 2n1n2/(n1 + n2) + 1, Var[R] = 2n1n2(2n1n2 - n1 - n2)/[(n1 + n2)²(n1 + n2 - 1)]; se informa z = (R - E[R])/√Var[R];
  - distribución exacta: P(R = 2k) = 2·C(n1 - 1, k - 1)·C(n2 - 1, k - 1)/C(n1 + n2, n1) y P(R = 2k + 1) = [C(n1 - 1, k)·C(n2 - 1, k - 1) + C(n1 - 1, k - 1)·C(n2 - 1, k)]/C(n1 + n2, n1);
  - valor p bilateral exacto 2·min(P(R ≤ r), P(R ≥ r)) para cualquier n: con enteros exactos hasta n1 + n2 = 1 000 y, por encima, con los mismos coeficientes calculados por log-gamma.
- Decisión conjunta: `is_independent` es verdadero si ni Ljung-Box ni rachas rechazan (error tipo I conjunto del 7 % al 13 % con α = 0.05).

> Nota de validación. La distribución exacta coincide con la enumeración de todas las disposiciones para n1, n2 ≤ 8, y la versión log-gamma con la aritmética racional exacta con un error relativo ≤ 9e-12 hasta 4 900 datos. La interpretación estima la probabilidad de que algún rezago salga de la banda por azar como 1 - (1 - α)^m, que supone rezagos independientes con varianza 1/n: con n = 120 y m = 20 da 0.64, y la simulación, 0.52 (hallazgo H23).

Supuesto de uso: las pruebas se aplican a observaciones individuales en orden temporal e igualmente espaciadas. No rechazar H0 no demuestra el supuesto, en especial con n pequeño. Un proceso fuera de control (desplazamientos de la media) también produce rechazos de normalidad y de independencia.

## 8. Capacidad del proceso

### 8.1 Sigma de corto y de largo plazo

- Corto plazo σ_w, por orden de prioridad (Montgomery, 2009, caps. 6 y 8):
  1. σ de los límites congelados de Fase I;
  2. con subgrupos de n constante ≤ 10, R̄/d2 (por defecto) o S̄/c4 si se pide;
  3. con n > 10 o n variable, S: con n constante S̄/c4(n); con n variable la desviación combinada s_p = √(Σ(n_i - 1)S_i²/ν), ν = Σ(n_i - 1) (Montgomery, 2009, cap. 6, gráficos X-barra y S con tamaño de muestra variable), corregida por sesgo: σ̂ = s_p/c4(ν + 1), porque ν·s_p²/σ² ~ χ²_ν implica E[s_p] = c4(ν + 1)·σ. Con n variable y R (solo si se pide) se promedia R_i/d2(n_i);
  4. individuales: MR̄/d2(2).
- Largo plazo σ_o: desviación estándar muestral de todas las observaciones (divisor N - 1).

### 8.2 Índices

| Índice | Fórmula |
|---|---|
| Cp | (USL - LSL)/(6σ_w) |
| Cpu, Cpl | (USL - x̄)/(3σ_w), (x̄ - LSL)/(3σ_w) |
| Cpk | min(Cpu, Cpl) (con una sola especificación, el índice de ese lado) |
| Pp, Ppu, Ppl, Ppk | las mismas con σ_o |
| Cpm | min(T - LSL, USL - T)/(3τ), τ = √(σ_o² + (x̄ - T)²); solo si LSL ≤ T ≤ USL |

Fuentes: Kane (1986); Montgomery (2009, cap. 8); para Cpm, Chan et al. (1988). Con T en el punto medio, Cpm = (USL - LSL)/(6τ). Con T fuera de las especificaciones el software deja Cpm en null y lo advierte. LSL, USL y T deben ser finitos. Supuestos: proceso en control estadístico y distribución normal; sin estabilidad, Cp y Cpk no predicen la producción futura y Pp y Ppk solo describen los datos (Montgomery, 2009, cap. 8).

Criterios de interpretación:

- Escala del veredicto (convención de uso común, no una tabla del libro): Cpk < 1 inadecuado; 1 a 1.33 marginal; 1.33 a 1.67 adecuado; ≥ 1.67 excelente.
- Mínimos recomendados del índice (Montgomery, cap. 8): procesos existentes 1.33 con especificación bilateral y 1.25 con unilateral; procesos nuevos 1.50 y 1.45; parámetros críticos 1.50 y 1.45 (existentes) y 1.67 y 1.60 (nuevos).

> Nota de validación. Los mínimos se citaron de memoria. Coinciden con la transcripción de Montgomery (2004, 5.ª ed., p. 776) publicada en Wikipedia ("Process capability index") y con la guía de Analyse-it, que atribuye 1.33 y 1.25 a Montgomery (2012). No se cotejaron con la 6.ª edición: hay que verificar tabla y página antes de citarlos.

### 8.3 Intervalos de confianza

Sea ν los grados de libertad del estimador de σ. Si σ̂ se estima con la desviación muestral de N datos normales, ν·σ̂²/σ² ~ χ²_ν con ν = N - 1, y el intervalo de Cp es exacto (Montgomery, 2009, cap. 8). Con otro estimador, ν·σ̂²/σ² se aproxima con una χ²_ν cuyo coeficiente de variación coincide con el de σ̂ (Patnaik, 1950): ν = 1/(2·CV²(σ̂)).

| Estimador de σ_w | ν | Derivación |
|---|---|---|
| desviación muestral (Pp, Ppk) | N - 1 | exacto |
| R̄/d2, m subgrupos de n | m·d2²/(2d3²) (≈ 0.91·m(n - 1) con n = 5); con n variable m²/(2Σ(d3_i/d2_i)²) | Var(R_i) = d3²σ², R_i independientes |
| S̄/c4, m subgrupos de n | m·c4²/(2(1 - c4²)) (≈ 0.95·m(n - 1) con n = 5) | Var(S_i) = (1 - c4²)σ² |
| s_p/c4(ν + 1), n variable | Σ(n_i - 1) | exacto: ν·s_p²/σ² ~ χ²_ν |
| MR̄/d2, k = N - 1 rangos móviles | d2(2)²k²/(2[k·d3(2)² + 2(k - 1)·0.16275]) (≈ 0.605·k para k grande) | Var(MR) = d3(2)²σ² = (2 - 4/π)σ²; Cov(MR_i, MR_(i+1)) = 0.16275σ²; MR a distancia ≥ 2 independientes |
| σ congelada de la Fase I | el ν de la estimación de la Fase I, con m = `points_used`, n = `subgroup_size` y el método de `sigma_method`; si faltan, ν es desconocido y los IC van en null | σ̂ no se vuelve a estimar con los datos nuevos |

La covarianza de los rangos móviles sale de la fórmula de E|U||V| para una normal bivariada con varianzas s² y correlación ρ, E|U||V| = (2s²/π)(√(1 - ρ²) + ρ·arcsen ρ): con s² = 2σ² y ρ = -1/2 da σ²(2√3/π + 1/3), y Cov = σ²[(2√3 - 4)/π + 1/3].

- Cp: Ĉp·√(χ²_(α/2, ν)/ν) ≤ Cp ≤ Ĉp·√(χ²_(1-α/2, ν)/ν).
- Cpk y los índices unilaterales (Bissell, 1990): Ĉ ∓ z_(1-α/2)·√(1/(9N) + Ĉ²/(2ν)), con N el número de datos con que se estimó la media. El término 1/(9N) viene de x̄ y 1/(2ν) de σ̂; para un índice unilateral es la aproximación delta de primer orden de Var(Ĉ). Bajo normalidad x̄ es independiente de cualquier estimador de σ invariante a la localización (Basu, 1955); con σ congelada, además, salen de datos distintos.
- Cota inferior unilateral (para afirmar "con 95 % de confianza Cpk supera c"): Ĉ - z_(1-α)·√(1/(9N) + Ĉ²/(2ν)). El extremo inferior del intervalo bilateral es una cota del 97.5 %.
- Pp y Ppk usan ν = N - 1.

> Nota de validación. Cobertura real del IC del 95 %, medida por simulación con el intervalo que devuelve el software: 0.947 (R̄/d2, 25 × 5), 0.947 (S̄/c4), 0.944 (MR̄/d2, N = 50), 0.948 (S combinada, n de 2 a 15), 0.948 (σ congelada de una Fase I de 25 × 5 con 500 datos nuevos) y 0.955 (σ congelada de 30 individuales); para Cpk, de 0.950 a 0.955. Con ν = N - 1 en esos mismos casos la cobertura bajaba a valores entre 0.58 y 0.93. La cota unilateral cubre el 0.953 y el 0.955 de las veces. En I-MR congelado con exclusiones intermedias el software cuenta points_used - 1 rangos y sobrestima ν (2.5 % con una exclusión de 30 puntos, 20 % con seis; hallazgo H26). El intervalo χ² se aplica a σ̂ corregida por c4, lo que lo desplaza un 0.1 % a 0.3 %, sin efecto medible.

### 8.4 Fracción no conforme

- Esperada con la normal, por cola: P(x < LSL) = Φ((LSL - x̄)/σ), P(x > USL) = 1 - Φ((USL - x̄)/σ), con σ_w y con σ_o; PPM = 10⁶ × total (Montgomery, 2009, cap. 8).
- Observada: proporción de datos con x < LSL o x > USL.
- Con N datos solo se puede esperar observar no conformes si la fracción es del orden de 1/N o mayor. Si el conteo observado k supera al esperado e = N·(fracción con σ_o) con P(Poisson(e) ≥ k) < 0.01, el software advierte que la causa puede ser colas más pesadas o inestabilidad.

### 8.5 Razón entre la sigma de largo y de corto plazo

La interpretación compara R = σ̂_o/σ̂_w con lo esperable por azar en un proceso estable. Por el método delta, Var(ln σ̂) ≈ CV² = 1/(2ν). Si σ̂_o y σ̂_w salen de los mismos datos, la desviación muestral corregida es el estimador insesgado de varianza mínima de σ bajo normalidad, y su covarianza con cualquier otro estimador insesgado es igual a su varianza (Lehmann y Casella, 1998, cap. 2). Entonces

- mismos datos: Var(ln R) ≈ 1/(2ν) - 1/(2(N - 1));
- σ congelada (independiente): Var(ln R) ≈ 1/(2ν) + 1/(2(N - 1)).

El texto afirma que la diferencia excede el azar solo si R > max(1.10, exp(z_0.95·√Var(ln R))) y, del otro lado, si R < min(0.90, exp(-z_0.95·√Var(ln R))).

> Nota de validación. Con datos estables la afirmación aparece en el 4.9 % a 5.6 % de los casos con I-MR (N = 30 a 100), en el 5.9 % con σ congelada y en el 0 % a 1.3 % con subgrupos, donde manda el piso de 1.10.

## 9. Diseño de gráficos: ARL y ATS

- Función OC del gráfico X-barra con límites μ0 ± L·σ/√n y desplazamiento μ1 = μ0 + δσ: β(δ) = Φ(L - δ√n) - Φ(-L - δ√n) (Montgomery, 2009, cap. 6). Individuales: n = 1.
- Con muestras independientes y solo la regla de un punto fuera, la longitud de corrida es geométrica: ARL0 = 1/α, α = 2Φ(-L) (370.4 con L = 3); ARL1 = 1/(1 - β).
- Tiempo promedio hasta la señal: ATS = ARL·h, con h el intervalo entre muestras. Carga muestral = n/h; unidades inspeccionadas hasta la señal = ARL1·n.
- Gráficos p y c con parámetro conocido: la región sin señal son los conteos enteros a ≤ X ≤ b, a = ⌈n·LCI⌉, b = ⌊n·LCS⌋ (en c, sin n); β = P(a ≤ X ≤ b) con X binomial(n, p) o Poisson(c) (Montgomery, 2009, cap. 7). Por la discreción el ARL0 real difiere de 370.4.
- Con reglas suplementarias la longitud de corrida no es geométrica. El software la estima por Monte Carlo con la misma lógica de reglas de los gráficos (en p y c truncados, sin las reglas de zonas) e informa el error estándar sd(RL)/√R. La referencia exacta es la cadena de Markov de Champ y Woodall (1987): ARL = (I - Q)⁻¹·1 desde el estado inicial. Como la simulación genera conteos de la distribución discreta real, el ARL0 informado ya incluye el efecto de la asimetría y de los empates sobre WE4 y N2.
- Supuestos: parámetros conocidos; con parámetros estimados en Fase I con pocos subgrupos el ARL0 real puede ser menor.

> Nota de validación. Simulación del software y cadena propia coinciden: WE1-WE4 en individuales, 91.87 frente a 91.75; WE1 + WE4 en un gráfico c con c0 = 4, 263.1 ± 4.2 frente a 265.9.

## 10. Muestreo de aceptación por atributos

- Plan simple (n, c): se acepta si d ≤ c. Pa(p) = P(d ≤ c) con d binomial(n, p) (curva OC tipo B), Poisson(n·p), o hipergeométrica(N, D, n) con D = ⌊p·N + 0.5⌋ (redondeo aritmético, 0.5 hacia arriba; curva OC tipo A) (Montgomery, 2009, cap. 15; Schilling y Neubauer, 2009).
- Diseño por dos puntos: Pa(AQL) ≥ 1 - α y Pa(LTPD) ≤ β. Para cada c el menor n con Pa(LTPD) ≤ β es n_β(c), no decreciente en c; como Pa(AQL) decrece con n, el primer c cuyo n_β(c) cumple también α da el plan de menor n. Es una búsqueda exacta, no la lectura de un nomograma.
- Inspección rectificadora: AOQ(p) = Pa·p·(N - n)/N (sin N, AOQ ≈ Pa·p); AOQL = max_p AOQ(p); ATI = n + (1 - Pa)(N - n).
- Plan doble (n1, c1, r1, n2, c2): se acepta si d1 ≤ c1, se rechaza si d1 ≥ r1; si no, se acepta si d1 + d2 ≤ c2.
  - Pa^I = P(d1 ≤ c1); Pa^II = Σ_(d=c1+1..r1-1) P(d1 = d)·P(d2 ≤ c2 - d); Pa = Pa^I + Pa^II.
  - ASN = n1 + n2·P(c1 < d1 < r1), sin inspección truncada.
  - AOQ = p[Pa^I(N - n1) + Pa^II(N - n1 - n2)]/N; ATI = n1·Pa^I + (n1 + n2)·Pa^II + N(1 - Pa).
- Supuestos: lotes de un mismo proceso, muestra aleatoria; la binomial ignora la corrección por población finita (conviene la hipergeométrica si n/N > 0.10).

## 11. Estadística descriptiva

- Media, desviación estándar muestral (divisor n - 1), cuartiles por interpolación lineal (tipo 7 de Hyndman y Fan, 1996, igual que `QUARTILE.INC` de Excel).
- Asimetría G1 y exceso de curtosis G2 ajustados (`scipy.stats.skew` y `kurtosis` con `bias=False`; errores estándar en la sección 7.1).
- Atípicos: cercas de Tukey Q1 - 1.5·IQR y Q3 + 1.5·IQR (Tukey, 1977); se marcan, no se eliminan.
- Histograma: k = ⌈log2 n⌉ + 1 clases (Sturges, 1926) y curva normal en escala de frecuencia f(x) = N·w·φ((x - x̄)/s)/s, con w el ancho de clase.

## 12. Herramientas de cálculo

Los cálculos usan Python 3.12 con NumPy (Harris et al., 2020) y SciPy (Virtanen et al., 2020); no se usan pandas ni statsmodels. Los textos de interpretación escriben los números con coma decimal y espacio de miles, y los valores positivos menores que 0.0001 en notación científica (por ejemplo 3,8·10⁻⁸); las respuestas JSON usan punto decimal.

## Referencias

Bartlett, M. S. (1946). On the theoretical specification and sampling properties of autocorrelated time-series. *Supplement to the Journal of the Royal Statistical Society, 8*(1), 27–41.

Basu, D. (1955). On statistics independent of a complete sufficient statistic. *Sankhyā, 15*(4), 377–380.

Bissell, A. F. (1990). How reliable is your capability index? *Journal of the Royal Statistical Society: Series C (Applied Statistics), 39*(3), 331–340.

Box, G. E. P., Jenkins, G. M., & Reinsel, G. C. (2008). *Time series analysis: Forecasting and control* (4th ed.). John Wiley & Sons.

Champ, C. W., & Woodall, W. H. (1987). Exact results for Shewhart control charts with supplementary runs rules. *Technometrics, 29*(4), 393–399.

Chan, L. K., Cheng, S. W., & Spiring, F. A. (1988). A new measure of process capability: Cpm. *Journal of Quality Technology, 20*(3), 162–175.

D'Agostino, R. B., & Stephens, M. A. (Eds.). (1986). *Goodness-of-fit techniques*. Marcel Dekker.

David, H. A., & Nagaraja, H. N. (2003). *Order statistics* (3rd ed.). John Wiley & Sons.

Harris, C. R., Millman, K. J., van der Walt, S. J., Gommers, R., Virtanen, P., Cournapeau, D., … Oliphant, T. E. (2020). Array programming with NumPy. *Nature, 585*, 357–362.

Hyndman, R. J., & Fan, Y. (1996). Sample quantiles in statistical packages. *The American Statistician, 50*(4), 361–365.

Joanes, D. N., & Gill, C. A. (1998). Comparing measures of sample skewness and kurtosis. *Journal of the Royal Statistical Society: Series D (The Statistician), 47*(1), 183–189.

Kane, V. E. (1986). Process capability indices. *Journal of Quality Technology, 18*(1), 41–52.

Lehmann, E. L., & Casella, G. (1998). *Theory of point estimation* (2nd ed.). Springer.

Ljung, G. M., & Box, G. E. P. (1978). On a measure of lack of fit in time series models. *Biometrika, 65*(2), 297–303.

Montgomery, D. C. (2009). *Introduction to statistical quality control* (6th ed.). John Wiley & Sons.

Nelson, L. S. (1984). The Shewhart control chart—Tests for special causes. *Journal of Quality Technology, 16*(4), 237–239.

Patnaik, P. B. (1950). The use of mean range as an estimator of variance in statistical tests. *Biometrika, 37*(1/2), 78–87.

Schilling, E. G., & Neubauer, D. V. (2009). *Acceptance sampling in quality control* (2nd ed.). CRC Press.

Shapiro, S. S., & Wilk, M. B. (1965). An analysis of variance test for normality (complete samples). *Biometrika, 52*(3/4), 591–611.

Siegel, S., & Castellan, N. J. (1988). *Nonparametric statistics for the behavioral sciences* (2nd ed.). McGraw-Hill.

Stephens, M. A. (1974). EDF statistics for goodness of fit and some comparisons. *Journal of the American Statistical Association, 69*(347), 730–737.

Sturges, H. A. (1926). The choice of a class interval. *Journal of the American Statistical Association, 21*(153), 65–66.

Tippett, L. H. C. (1925). On the extreme individuals and the range of samples taken from a normal population. *Biometrika, 17*(3/4), 364–387.

Tukey, J. W. (1977). *Exploratory data analysis*. Addison-Wesley.

Virtanen, P., Gommers, R., Oliphant, T. E., Haberland, M., Reddy, T., Cournapeau, D., … SciPy 1.0 Contributors. (2020). SciPy 1.0: Fundamental algorithms for scientific computing in Python. *Nature Methods, 17*, 261–272.

Wald, A., & Wolfowitz, J. (1940). On a test whether two samples are from the same population. *The Annals of Mathematical Statistics, 11*(2), 147–162.

Western Electric Company. (1956). *Statistical quality control handbook*. Western Electric.

> Las citas de capítulo de Montgomery corresponden a la 6.ª edición y se dan a nivel de capítulo; los números de sección, ecuación, tabla y ejemplo que aparecen en los docstrings del código se citaron de memoria y conviene cotejarlos con el libro antes de llevarlos al informe. Las referencias de Basu (1955), Joanes y Gill (1998) y Lehmann y Casella (1998) se agregaron en la segunda pasada para respaldar resultados que la validación usó; sus datos bibliográficos también conviene cotejarlos.
