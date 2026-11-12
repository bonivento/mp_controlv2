# Control estadístico de un proceso de llenado: desarrollo y aplicación de un software de CEP

**Informe técnico final**

> **POR COMPLETAR: portada.** Nombres completos de los integrantes del equipo (de 3 a 5), programa académico, facultad e institución, año de entrega (el enunciado fija la última semana de mayo). Docente según el enunciado: Manuel J. Campuzano, Ph.D. Asignatura: Control Estadístico de Procesos.

| Elemento de portada (APA 7) | Contenido |
|---|---|
| Título | Control estadístico de un proceso de llenado: desarrollo y aplicación de un software de CEP |
| Autores | POR COMPLETAR |
| Afiliación | Facultad de Ingeniería, POR COMPLETAR (institución y programa) |
| Curso | Control Estadístico de Procesos |
| Docente | Manuel J. Campuzano, Ph.D. |
| Fecha de entrega | POR COMPLETAR (última semana de mayo) |

---

## Nota sobre el origen de los datos y sobre el estado del trabajo

Este informe tiene dos partes de naturaleza distinta y conviene no confundirlas.

1. **El software**, que está terminado y probado: 953 pruebas automáticas de la API pasan (1 omitida, ninguna con fallo esperado; ver sección 7.4), y un revisor independiente recalculó sus resultados por otro camino (`docs/validacion.md`).
2. **El análisis del caso**. Al momento de redactar **no existe empresa ni datos reales**. El caso que se analiza es un **ejemplo de aplicación con datos sintéticos** (archivos `sintetico_*` de `data/ejemplos/`), generado por un programa con semilla fija. Ninguna cifra de este informe describe un proceso productivo real, y toda sección que dependa de la empresa está marcada con un bloque `POR COMPLETAR CON LA EMPRESA`. El ejemplo sintético demuestra que el software y la metodología funcionan de punta a punta; **no** sustituye la visita a la planta ni los hallazgos reales que pide el enunciado.

Convenciones: en el texto los decimales se escriben con coma; en las salidas del software y en los anexos, con punto. Cada cifra se puede rastrear a un archivo de `docs/informe/anexos/salidas/` (petición y respuesta reales de la API), citado en la nota de la tabla o figura. Los scripts que generan esas salidas y las figuras están en `docs/informe/anexos/`.

---

## Resumen ejecutivo

Se desarrolló un software web de Control Estadístico de Procesos (CEP) con ocho módulos: gestión de datos, gráficos de control por variables y por atributos con separación explícita de Fase I y Fase II, validación de supuestos, capacidad del proceso, diseño de gráficos con ARL0, ARL1 y ATS, muestreo de aceptación y reportes. El motor de cálculo (Python, FastAPI, NumPy y SciPy) está probado con 953 pruebas automáticas y revisado por un validador independiente que recalculó sus resultados por otro camino, encontró errores y los vio corregidos, y la interfaz (Next.js) guarda los estudios en una base de datos Supabase con acceso por usuario.

Para demostrar el flujo completo se analizó un **proceso sintético** de llenado de envases de 500 g de salsa, con especificaciones de 495 g a 505 g. En Fase I (25 subgrupos de cinco envases) el gráfico X-barra señaló el subgrupo 12; tras excluirlo con una causa asignable (ficticia, propia del ejemplo) los límites quedaron en 498,072 g y 501,547 g y la dispersión en R-barra = 3,012 g. La capacidad de corto plazo resultó marginal: Cp = 1,287 y Cpk = 1,238 (IC 95 %: 1,044 a 1,431), con 133 partes por millón fuera de especificación esperadas. En Fase II, con los límites congelados, 11 de 15 subgrupos dieron señal y el Cpk calculado sobre esos datos cayó a 0,841, aunque ninguna de las 75 unidades medidas salió de especificación: el proceso se desplazó antes de producir producto no conforme observable. El análisis ARL/ATS muestra que, con n = 5 y una muestra cada 8 horas, un desplazamiento de 1,5 sigmas tarda en promedio 1,57 muestras (12,5 horas) en detectarse, y que activar las reglas de Western Electric reduce el ARL0 de 370,4 a 91,5.

Las conclusiones son de método y de software: el ejemplo ilustra el flujo y sus advertencias. Los hallazgos de planta, la priorización final de mejoras y el diagnóstico de empresa **quedan por completar con la empresa real** (ver bloques marcados).

---

## 1. Introducción

La calidad de un proceso se decide durante la producción, no en la inspección final. El Control Estadístico de Procesos ofrece herramientas para distinguir la variación natural de un proceso (causas comunes) de la variación atribuible a hechos concretos (causas especiales), para medir qué tan bien cumple sus especificaciones y para dimensionar el esfuerzo de inspección necesario (Montgomery, 2009). Aplicar esas herramientas exige cálculo repetitivo y decisiones documentadas, lo que justifica un software propio que las integre.

Este informe documenta el diseño, la validación y la aplicación de ese software. Describe qué calcula y cómo, muestra su uso con un caso sintético completo y deja identificados los puntos que se llenarán con una empresa manufacturera real.

## 2. Planteamiento del problema

Las empresas manufactureras suelen registrar mediciones de sus procesos en hojas de cálculo que se archivan sin análisis o se resumen con promedios que ocultan cambios en el tiempo. Tres preguntas quedan sin respuesta: ¿el proceso es estable?, ¿es capaz de cumplir la especificación con holgura? y ¿cuánto y cada cuánto hay que medir para detectar un cambio a tiempo? Contestarlas requiere gráficos de control con una distinción clara entre la fase en que se estiman los límites (Fase I) y la fase en que se vigila contra ellos (Fase II), pruebas de los supuestos estadísticos, índices de capacidad con su incertidumbre y herramientas para diseñar el muestreo.

**Problema de ingeniería de este trabajo:** construir un software que responda esas tres preguntas con rigor estadístico y trazabilidad, y aplicarlo a un proceso real de producción para formular mejoras sustentadas en evidencia.

> **POR COMPLETAR CON LA EMPRESA:** planteamiento del problema concreto de la empresa (qué síntoma o reclamo motivó el estudio, qué no conformidades se observan, cuánto cuestan). Información faltante: respuestas del responsable de calidad y del jefe de producción a las preguntas de `docs/empresa/guia-visita.md` (secciones «A quién preguntar» y «Qué describir para cerrar la visita») y el último trimestre de no conformidades.

## 3. Objetivos

**Objetivo general.** Diseñar, desarrollar y validar un software de CEP que permita analizar datos de producción, diagnosticar el comportamiento estadístico de un proceso y sustentar propuestas de mejora con evidencia cuantitativa.

**Objetivos específicos.**

1. Implementar gráficos de control por variables (X-barra-R, X-barra-S, I-MR) y por atributos (p, np, c, u), con Fase I y Fase II diferenciadas y reglas de corrida.
2. Implementar la validación de supuestos (normalidad e independencia) y el cálculo de Cp, Cpk, Cpl, Cpu, Pp, Ppk, Cpm y fracción no conforme.
3. Implementar el diseño de gráficos con ARL0, ARL1 y ATS y el muestreo de aceptación simple y doble.
4. Verificar el software con pruebas automáticas contra resultados conocidos y con un caso de aplicación completo.
5. Aplicar el software a un proceso de una empresa manufacturera y formular mejoras priorizadas por impacto y facilidad. *(Pendiente: depende de la empresa; ver bloque en la sección 4.)*

## 4. Descripción de la empresa y del proceso

> **POR COMPLETAR CON LA EMPRESA:** esta sección no puede redactarse sin la visita. Información faltante y formato de origen:
>
> | Dato faltante | Se obtiene de |
> |---|---|
> | Empresa (código anonimizado, sector, tamaño), producto y presentación | Acta de visita (`docs/empresa/guia-visita.md`, «Acta de visita», puntos 1 y 4) y reglas de códigos de `docs/empresa/confidencialidad.md` |
> | Diagrama de flujo del proceso, tiempos de ciclo, operarios por estación, turnos | Guía de visita, «Qué observar» (punto 1) |
> | Operación crítica y razón de su elección | Guía de visita, «Qué observar» (punto 3) y acta, punto 5 |
> | Variable de calidad, unidad, LIE, LSE, instrumento y resolución | `docs/empresa/plan-muestreo.md`, secciones 1 y 2 |
> | Evidencia (fotos autorizadas, acta firmada) | Guía de visita, «Evidencias que hay que traer» |
>
> No se inventa ni se supone ninguno de estos datos.

### 4.1 Proceso del caso de ejemplo (sintético)

Para poder ilustrar el análisis se usa un proceso hipotético de **llenado de envases de 500 g de salsa en una línea manufacturera**, descrito en `data/ejemplos/README.md`. No corresponde a ninguna empresa.

| Característica | Valor del ejemplo sintético |
|---|---|
| Variable de calidad | Peso neto por envase (g), variable continua |
| Valor nominal y especificaciones | 500 g; LIE = 495 g; LSE = 505 g (tolerancia total de 10 g) |
| Proceso estable de referencia | Media 500 g y desviación individual de 1,2 g, según el README de los datos |
| Turnos | Mañana, Tarde y Noche; un subgrupo por turno |

Los valores de las especificaciones, el nominal y el intervalo de muestreo de 8 horas (un subgrupo por turno) son **supuestos del ejemplo**, no datos de planta.

## 5. Alcance del análisis

**Dentro del alcance.** El software completo (ocho módulos) y su aplicación al caso sintético: Fase I y Fase II de variables con X-barra-R (y X-barra-S como contraste), gráfico p de atributos con tamaño de muestra variable, supuestos, capacidad, ARL/ATS, un plan de muestreo de aceptación y los archivos de prueba para casos particulares (datos no normales, autocorrelados, con errores de captura).

**Fuera del alcance.** Gráficos de memoria (CUSUM, EWMA) y multivariados; análisis de sistemas de medición (repetibilidad y reproducibilidad); transformaciones de datos no normales; modelado de series autocorrelacionadas.

**Limitaciones del alcance del caso.** Los datos son simulados con distribución normal (o con los defectos introducidos a propósito en cada archivo), de modo que el ejemplo no puede revelar problemas de medición, de formación de subgrupos o de comportamiento humano que sí aparecerían en planta.

> **POR COMPLETAR CON LA EMPRESA:** alcance del estudio real (línea, producto, variable, periodo cubierto, número de subgrupos de Fase I y Fase II, exclusiones). Formato de origen: `docs/empresa/plan-muestreo.md`, secciones 6 y 7.

## 6. Metodología

### 6.1 Enfoque general

El trabajo sigue cuatro pasos: (a) diseño del software con un contrato de datos único entre la interfaz y el motor de cálculo; (b) implementación de cada fórmula con su fuente bibliográfica y una prueba contra un resultado conocido; (c) verificación con datos sintéticos de resultado esperado independiente (`data/ejemplos/README.md`) y con una revisión estadística independiente que recalcula cada resultado por otro camino (sección 7.4); (d) aplicación a un proceso, que con datos reales exige plan de muestreo, recolección, anonimización y análisis.

### 6.2 Fundamentos estadísticos implementados

Cada fórmula, sus supuestos y su fuente están reunidos en `docs/fundamentos-estadisticos.md`, elaborado con el revisor independiente del software; aquí se resumen los elementos que sustentan el análisis. Las citas de capítulo corresponden a Montgomery (2009, 6.ª ed.) y se dan a nivel de capítulo. La notación es: $m$ subgrupos de tamaño $n$, $L$ el ancho de los límites en desviaciones estándar del estadístico graficado (3 por defecto), $\sigma_w$ la sigma de corto plazo (dentro de subgrupos) y $\sigma_o$ la de largo plazo (todos los datos).

**Supuesto común.** Los gráficos de Shewhart y los índices de capacidad suponen observaciones independientes e idénticamente distribuidas mientras el proceso está en control, y normales en los gráficos por variables y en los índices (Montgomery, 2009, caps. 5, 6 y 8). La sección 11 verifica ambos supuestos en el caso de ejemplo.

**Gráficos por variables (cap. 6).** Las constantes $d_2(n)$, $d_3(n)$ y $c_4(n)$ se calculan por integración numérica para $n$ de 2 a 25 (Tippett, 1925) y de ellas se derivan $A_2$, $A_3$, $B_3$, $B_4$, $D_3$, $D_4$ para cualquier $L$. Cada gráfico se construye en dos pasos: estimar $(\mu, \sigma)$ con los subgrupos retenidos y construir los límites a partir de ellos.

- X-barra y R: líneas de X-barra en $\bar{\bar{x}} \pm A_2 \bar{R}$ (equivale a $\hat\mu \pm L\hat\sigma/\sqrt{n}$); R con LCS = $D_4\bar{R}$ y LCI = $D_3\bar{R}$; $\hat{\sigma} = \bar{R}/d_2$.
- X-barra y S: $\bar{\bar{x}} \pm A_3 \bar{S}$; S con LCS = $B_4\bar{S}$ y LCI = $B_3\bar{S}$; $\hat{\sigma} = \bar{S}/c_4$.
- Individuales y rango móvil: $\bar{x} \pm 3\,\overline{MR}/d_2$ con $d_2 = 1{,}128$ y $MR_i = |x_i - x_{i-1}|$; con exclusiones, un rango móvil entra en $\overline{MR}$ solo si sus dos puntos están retenidos.
- Con parámetros conocidos (Fase II): X-barra $\mu \pm L\sigma/\sqrt{n}$; R $(d_2 \pm L d_3)\sigma$; S $(c_4 \pm L\sqrt{1-c_4^2})\sigma$. Si el tamaño de subgrupo cambia, los límites se reconstruyen con el nuevo $n$.

**Gráficos por atributos (cap. 7).** p: $\bar{p} \pm L\sqrt{\bar{p}(1-\bar{p})/n_i}$, con límites por punto cuando $n$ varía; np: $n\bar{p} \pm L\sqrt{n\bar{p}(1-\bar{p})}$; c: $\bar{c} \pm L\sqrt{\bar{c}}$; u: $\bar{u} \pm L\sqrt{\bar{u}/n_i}$. El límite inferior negativo se trunca en 0. El asistente de selección elige p o np para unidades defectuosas (np solo si $n$ es constante) y c o u para defectos (c solo si la unidad de inspección es constante).

**Fase I y Fase II (cap. 5).** En **Fase I**, retrospectiva, se estiman los parámetros del proceso ($\mu$ y $\sigma$, o $\bar{p}$, $\bar{c}$, $\bar{u}$) **sin** los puntos excluidos con causa asignable documentada; se grafican todos los puntos, pero los excluidos no participan en el cálculo ni en las reglas. El software no itera solo: el usuario investiga, excluye y recalcula. Los parámetros resultantes se **congelan**. En **Fase II**, prospectiva, los datos nuevos se comparan con los parámetros congelados y **nunca se recalculan**; la API rechaza excluir puntos en Fase II. Se recomienda un mínimo de 20 a 25 subgrupos en Fase I.

**Reglas de corrida.** Western Electric (WE1 a WE4; Western Electric Company, 1956) y Nelson (N1 a N8; Nelson, 1984; Montgomery, 2009, cap. 5). Convenciones: las comparaciones son estrictas (un punto sobre un límite no cuenta), un punto sobre la línea central corta la racha, y la ventana de las reglas «k de m» es parcial al inicio de la serie, lo que equivale al ARL de estado cero de Champ y Woodall (1987); la señal se marca en el punto donde se completa la regla. Las reglas que usan zonas (WE2, WE3, N5 a N8) solo se evalúan cuando la distribución del estadístico graficado es simétrica respecto de la línea central: X-barra, individuales y atributos sin límite truncado. El tratamiento de los paneles restantes es el siguiente.

- **Paneles R, S y atributos con un límite truncado.** Las reglas con zonas se omiten y el software informa cuáles y por qué: la distribución del estadístico graficado es asimétrica respecto de la línea central (o un límite está truncado en 0), de modo que las zonas A, B y C no tienen las probabilidades de una distribución simétrica. Las reglas de racha que no usan zonas (WE1, WE4, N1 a N4) **sí se aplican**, y WE4 y N2 **con una advertencia**: una señal de ellas debe tomarse como indicio por confirmar y no como prueba. El sentido de la advertencia depende del panel. En R y S, la probabilidad de quedar por encima de la línea central no es 1/2 y la tasa de falsas alarmas es **mayor** que la nominal: la revisión independiente midió, para WE4 sola, un ARL0 de 174 en R con $n$ = 2 frente a 255 en un panel simétrico. En los gráficos de conteos, en cambio, la tasa es **distinta de la nominal y puede ser mucho menor** si la línea central coincide con un conteo posible, porque los puntos iguales a ella cortan la racha: con un gráfico c y $\bar{c}$ = 2, la validación calculó un ARL0 de WE4 de 1 924, con la consiguiente pérdida de sensibilidad. N3 y N4 dependen solo del orden de los valores y su tasa de falsas alarmas no cambia con la asimetría (ARL0 de 421,6 y 601,0 con datos continuos independientes).
- **Panel de rango móvil.** Solo se evalúa el punto fuera de límites (WE1 y N1). Dos rangos móviles consecutivos comparten una observación y están correlacionados, además de ser asimétricos, de modo que las demás reglas darían varias veces las falsas alarmas nominales (ARL0 medido de 94 para WE4 frente a 255).
- **Varias reglas a la vez.** Cuando se activan varias reglas, la tasa de falsa alarma conjunta sube. Con un estadístico normal y el proceso en control, el ARL0 es de 370 con solo un punto fuera de límites, cerca de 92 con las cuatro reglas de Western Electric (Champ y Woodall, 1987) y cerca de 66 con las doce. El software lo advierte en cada análisis con más de una regla y remite al módulo de diseño para calcular el ARL0 de la combinación elegida.

**Supuestos (caps. 3, 5 y 10).**

- *Normalidad.* Shapiro-Wilk (Shapiro y Wilk, 1965), con el valor p de SciPy. Anderson-Darling con media y varianza estimadas (Stephens, 1974): el estadístico $A^2$ se corrige con $(1 + 0{,}75/n + 2{,}25/n^2)$ y se compara con los valores críticos de D'Agostino y Stephens (1986), 0,561; 0,631; 0,752; 0,873 y 1,035 para $\alpha$ = 0,15; 0,10; 0,05; 0,025 y 0,01, interpolando en $\ln\alpha$. Esta tabla reproduce el tamaño nominal de la prueba; la combinación de valores críticos usada en una versión previa tenía un tamaño real de 0,038 a 0,061 para $\alpha$ = 0,05 y degeneraba con $n$ pequeño (hallazgo H3 de la validación). El valor crítico depende de $n$ (con $n$ = 120 es 0,7472). Se agrega el gráfico Q-Q con posiciones $(j-0{,}5)/n$.
- *Independencia.* Función de autocorrelación $r_k$ con banda aproximada $\pm z_{1-\alpha/2}/\sqrt{n}$ bajo ruido blanco (Bartlett, 1946; Box et al., 2008); la prueba de Ljung-Box $Q = n(n+2)\sum_{k=1}^{m} r_k^2/(n-k) \sim \chi^2_m$, sin restar grados de libertad porque no se ajusta un modelo (Ljung y Box, 1978); y la prueba de rachas de Wald-Wolfowitz respecto a la mediana (Wald y Wolfowitz, 1940; Siegel y Castellan, 1988) con **valor p bilateral exacto**, $2\min(P(R \le r), P(R \ge r))$, a partir de la distribución exacta del número de rachas. Una versión previa usaba la aproximación normal sin corrección de continuidad para más de 60 datos, que es anticonservadora (hallazgo H10).
- *Decisión conjunta y cautela.* La conclusión de normalidad combina dos pruebas y la de independencia otras dos; por eso su error tipo I conjunto es mayor que $\alpha$ (la validación midió 7 % para normalidad y de 8,7 % a 13,4 % para independencia con $\alpha$ = 0,05). No rechazar $H_0$ no demuestra el supuesto, y un proceso fuera de control también produce rechazos. El software redacta sus conclusiones con esa cautela.

**Capacidad (cap. 8).** $C_p = (LSE-LIE)/(6\sigma_w)$; $C_{pu} = (LSE-\mu)/(3\sigma_w)$; $C_{pl} = (\mu - LIE)/(3\sigma_w)$; $C_{pk}=\min(C_{pu},C_{pl})$ (Kane, 1986); $P_p$ y $P_{pk}$ con $\sigma_o$ (desviación muestral, divisor $N-1$); $C_{pm}$ con $\tau = \sqrt{\sigma_o^2 + (\mu - T)^2}$ (Chan et al., 1988). La sigma de corto plazo $\sigma_w$ se toma, por orden de prioridad, de los límites congelados de Fase I, de $\bar{R}/d_2$ ($n$ constante hasta 10) o $\bar{S}/c_4$, o de $\overline{MR}/d_2$ para individuales. El veredicto por Cpk (menor que 1 inadecuada, de 1 a 1,33 marginal, de 1,33 a 1,67 adecuada, 1,67 o más excelente) es una convención de uso común, no una tabla del libro. Fracción no conforme esperada: $\Phi((LIE-\mu)/\sigma)$ y $1 - \Phi((LSE-\mu)/\sigma)$, con $\sigma_w$ y con $\sigma_o$; la observada es el conteo directo.

*Intervalos de confianza y grados de libertad.* El intervalo de $C_p$ del libro, $\hat{C}_p\sqrt{\chi^2_{\alpha/2,\nu}/\nu} \le C_p \le \hat{C}_p\sqrt{\chi^2_{1-\alpha/2,\nu}/\nu}$, supone que sigma se estimó con la desviación muestral de $N$ datos normales y, entonces, $\nu = N-1$. Pero la sigma de corto plazo no siempre se estima así: $\bar{R}/d_2$, $\bar{S}/c_4$, $\overline{MR}/d_2$ y la sigma congelada de la Fase I son estimadores con variabilidad distinta, es decir, con distinta cantidad de información sobre sigma. Un estimador con coeficiente de variación $CV$ se comporta como una desviación muestral con $\nu = 1/(2\,CV^2)$ grados de libertad (aproximación de Patnaik, 1950). Resulta $\nu \approx m\,d_2^2/(2d_3^2)$ para $\bar{R}/d_2$ con $m$ subgrupos de tamaño $n$ (3,62 por subgrupo con $n$ = 5), $\nu \approx 0{,}95\,m(n-1)$ para $\bar{S}/c_4$, $\nu \approx 0{,}61(N-1)$ para $\overline{MR}/d_2$ (los rangos móviles vecinos están correlacionados) y, con límites congelados, el $\nu$ de la Fase I. Con 24 subgrupos de $n$ = 5, $\nu \approx$ 86,9, no los 119 que daría $N - 1$ con 120 datos. Usar $N-1$ en todos los casos subestima la incertidumbre: por simulación, la cobertura real del intervalo nominal de 95 % era de 0,915 con $\bar{R}/d_2$ (25 subgrupos de 5), 0,868 con $\overline{MR}/d_2$ ($N$ = 50) y 0,601 con una sigma congelada aplicada a 500 datos nuevos; con el $\nu$ efectivo la cobertura de $\bar{R}/d_2$ vuelve a 0,948 (hallazgo H1). El software usa ahora el $\nu$ del estimador, lo informa en la interpretación y avisa que el intervalo es aproximado; para $P_p$ y $P_{pk}$, que usan la desviación muestral, $\nu = N-1$. Los intervalos de $C_{pk}$, $C_{pl}$ y $C_{pu}$ usan la aproximación de Bissell (1990), $\hat{C}[1 \mp z_{1-\alpha/2}\sqrt{1/(9N\hat{C}^2) + 1/(2\nu)}]$, donde el término $1/(9N)$ recoge la incertidumbre de estimar la media con $N$ datos y $1/(2\nu)$ la de estimar sigma.

**ARL y ATS (caps. 5 a 7).** Con límites $\mu_0 \pm L\sigma/\sqrt{n}$ y un desplazamiento $\delta\sigma$: $\beta(\delta) = \Phi(L - \delta\sqrt{n}) - \Phi(-L - \delta\sqrt{n})$; $\text{ARL}_0 = 1/\alpha$ con $\alpha = 2\Phi(-L)$; $\text{ARL}_1 = 1/(1-\beta)$; $\text{ATS} = \text{ARL}\cdot h$, carga muestral $n/h$ y unidades hasta la señal $\text{ARL}_1\cdot n$. En p y c, la región sin señal son los conteos enteros entre los límites, de modo que la discreción hace que el ARL0 real difiera de 370,4. Con reglas suplementarias la longitud de corrida deja de ser geométrica y se **estima por Monte Carlo**, con semilla fija; la referencia exacta es la cadena de Markov de Champ y Woodall (1987), que da ARL0 = 91,75 para WE1 a WE4 en individuales. Los ARL suponen parámetros conocidos: con parámetros estimados con pocos subgrupos de Fase I, el ARL0 real puede ser menor.

**Muestreo de aceptación (cap. 15).** Plan simple (n, c): $P_a(p) = P(d \le c)$ con binomial, Poisson o hipergeométrica; diseño por dos puntos de la curva OC, $P_a(AQL) \ge 1-\alpha$ y $P_a(LTPD) \le \beta$, con una búsqueda exacta del menor $n$ y no la lectura de un nomograma; $\text{AOQ} = P_a\,p\,(N-n)/N$; AOQL como máximo de la curva; $\text{ATI} = n + (1-P_a)(N-n)$. Plan doble con ASN sin truncar (Montgomery, 2009; Schilling y Neubauer, 2009).

**Estadística descriptiva.** Cuartiles por interpolación lineal (tipo 7 de Hyndman y Fan, 1996), asimetría y exceso de curtosis ajustados, cercas de Tukey $Q_1 - 1{,}5\,IQR$ y $Q_3 + 1{,}5\,IQR$ para marcar atípicos sin eliminarlos (Tukey, 1977) e histograma con $\lceil\log_2 n\rceil + 1$ clases (Sturges, 1926). Los cálculos usan NumPy (Harris et al., 2020) y SciPy (Virtanen et al., 2020).

**Documentación complementaria.** La derivación completa de cada fórmula está en `docs/fundamentos-estadisticos.md` y la comparación del software contra cálculos independientes, en `docs/validacion.md` (sección 7.4). Si el código cambia, las cifras de este informe se regeneran ejecutando de nuevo `generar_salidas.py`.

### 6.3 Plan de muestreo del caso sintético

Un subgrupo por turno (Mañana, Tarde, Noche), de cinco envases consecutivos, formado por el generador de datos. **Justificación del subgrupo racional (del ejemplo):** cinco envases consecutivos de una misma línea y turno comparten materia prima, ajuste de máquina y operario, de modo que la variación dentro del subgrupo refleja causas comunes y la variación entre subgrupos incluye los cambios de turno y de ajuste que se quieren detectar. Fase I: 25 subgrupos (el mínimo recomendado es de 20 a 25). Fase II: 15 subgrupos posteriores.

> **POR COMPLETAR CON LA EMPRESA:** plan de muestreo real: justificación de la variable, instrumento y resolución frente a la tolerancia, forma y tamaño del subgrupo, frecuencia, número de subgrupos de Fase I y Fase II, responsables y acción ante una señal. Formato de origen: `docs/empresa/plan-muestreo.md` completo (secciones 2 a 7). Los datos reales se recolectan con `docs/empresa/formato-recoleccion.md` y se anonimizan según `docs/empresa/confidencialidad.md`.

### 6.4 Reproducibilidad

El script `docs/informe/anexos/generar_salidas.py` llama a la API local con los archivos de `data/ejemplos/` y guarda cada petición y respuesta como JSON en `docs/informe/anexos/salidas/` (38 archivos; ver Anexo A). El script `generar_figuras.py` dibuja las figuras solo a partir de esas respuestas, sin recalcular nada. La simulación de ARL usa la semilla 12345.

## 7. Descripción del software

### 7.1 Arquitectura

Tres piezas con responsabilidades separadas (ver `docs/arquitectura.md`): una interfaz web (Next.js) que gestiona la sesión y guarda los datos, un motor de cálculo sin estado (FastAPI con NumPy y SciPy) y una base de datos (Supabase) con seguridad por filas, de modo que cada usuario ve solo sus estudios. El motor de cálculo es determinista y no guarda nada; el contrato entre interfaz y motor son esquemas Pydantic de los que se generan los tipos de la interfaz. La librería estadística `api/app/spc/` es Python puro, sin dependencia de la web.

### 7.2 Módulos

| Módulo del enunciado | Pantalla | Rutas de la API | Qué entrega |
|---|---|---|---|
| 1. Gestión de datos | Datos | `/api/data/parse`, `/api/data/summary`, `/api/data/summary/attributes` | Lectura de CSV y Excel con avisos de limpieza por hoja, subgrupos racionales con justificación obligatoria, retiro de subgrupos incompletos con justificación, bitácora de limpieza, atípicos marcados sin borrarlos, tablas resumen |
| 2. Variables | Variables | `/api/charts/variables` | X-barra-R, X-barra-S e I-MR, Fase I con exclusión por causa asignable, congelado de límites y Fase II |
| 3. Atributos | Atributos | `/api/charts/attributes`, `/api/charts/attributes/recommend` | p, np, c y u con asistente de selección justificado |
| 4. Supuestos | Supuestos | `/api/assumptions` | Cuatro pruebas, Q-Q, histograma y ACF |
| 5. Capacidad | Capacidad | `/api/capability` | Cp, Cpk, Cpl, Cpu, Pp, Ppk, Cpm con intervalos y fracción no conforme esperada y observada |
| 6. Diseño | Diseño | `/api/design/arl`, `/api/design/compare` | ARL0, ARL1, ATS, curvas OC y ARL, comparador de n, L y h |
| 7. Muestreo | Muestreo | `/api/sampling/single/design`, `/single/evaluate`, `/double/evaluate` | Planes simples y dobles, curvas OC, AOQ, ATI y ASN |
| 8. Reportes | Reporte | `/api/reports/excel` | Reporte imprimible con tablas y figuras numeradas y exportación a Excel |

### 7.3 Características de calidad del software

- **Pruebas:** 953 pruebas automáticas de la API (librería `spc`, rutas HTTP, contrato y validación independiente) pasan; ver la subsección 7.4.
- **Interpretación automática:** cada respuesta incluye una conclusión, hallazgos y advertencias en español, con coma decimal y redactadas con cautela (por ejemplo, que no se interpreta la capacidad de un proceso inestable y que no rechazar una prueba no demuestra el supuesto).
- **Trazabilidad:** causas asignables, decisiones sobre atípicos y justificaciones de subgrupo se guardan con el estudio.
- **Prevención de errores:** nunca devuelve NaN ni infinito (va `null` con advertencia); no permite excluir puntos sin causa ni calcular Fase II sin límites congelados.
- **Seguridad:** inicio de sesión y políticas RLS; la API verifica el JWT de Supabase.
- **Estado de despliegue:** en producción en Vercel desde el 11 de noviembre de 2026: web en <https://cep-web.vercel.app> y API en <https://cep-api-xi.vercel.app>. Las pruebas de extremo a extremo se repitieron contra producción (35 pasan, 2 omitidas).

### 7.4 Verificación del software

La verificación tiene dos niveles. El primero son las pruebas automáticas de los autores, que contrastan cada fórmula con un resultado conocido. La última corrida de `cd api && .venv/bin/python -m pytest -q` entregó la línea `953 passed, 1 skipped`: 953 pruebas que pasan y una omitida (una prueba de rutas que exige celdas vacías, que la API limpia antes de calcular). No queda ninguna prueba marcada como fallo esperado: todos los hallazgos de la revisión independiente quedaron corregidos.

El segundo nivel es una **revisión estadística independiente** (`docs/validacion.md`) hecha por un revisor que no participó en la implementación y que recalculó cada resultado por otro camino: otras integrales para las constantes, fórmulas escritas a mano para límites e índices, implementaciones con bucles explícitos para las doce reglas de corrida, cadenas de Markov propias para los ARL con reglas, enumeración exhaustiva para la prueba de rachas y para el plan de muestreo de menor tamaño, y simulación de Monte Carlo para la cobertura de intervalos y el tamaño real de las pruebas. Sus pruebas (`api/tests/validation/`) son parte de las 953.

La revisión **encontró errores y se corrigieron**, lo que es evidencia de que el proceso de verificación funciona. En su primera pasada confirmó 16 hallazgos (H1 a H16). Los de mayor efecto en este informe fueron:

| Hallazgo | Qué estaba mal | Qué cambió en las cifras del informe |
|---|---|---|
| H1 | Intervalos de confianza de Cp y Cpk con $N-1$ grados de libertad aunque sigma viniera de $\bar{R}/d_2$ o de límites congelados (cobertura real de 0,60 a 0,92 en lugar de 0,95) | Los intervalos de la Tabla 7 y de la sección 13 cambiaron (Cp de [1,124; 1,450] a [1,096; 1,478]) |
| H3 | Valores críticos de Anderson-Darling mal calibrados, degenerados con $n$ pequeño | Crítico de 0,7629 a 0,7472 con $n$ = 120; las decisiones no cambian |
| H10 | Prueba de rachas con aproximación normal para más de 60 datos | Valor p de la Fase I depurada de 0,4595 a 0,5182; la decisión no cambia |
| H5 | WE4, N2 y N3 aplicadas en R, S, rango móvil y atributos sin advertir su efecto sobre la tasa de falsas alarmas | Rango móvil solo con WE1 y N1; en R, S y atributos, advertencia que distingue el sentido del efecto (sección 6.2) |
| H4 | La Fase I declaraba «en control» a los subgrupos excluidos y la Fase II repetía exclusiones de Fase I | La interpretación habla de los 24 subgrupos retenidos |
| H6 | El resumen de supuestos afirmaba «se cumplen» o «están autocorrelacionados» por no rechazar o por un rechazo marginal | La interpretación de la sección 11 es ahora cautelosa |
| H2, H8, H11, H14, H16 | Especificaciones no finitas aceptadas, una afirmación sin sustento sobre nomogramas, texto de la regla N8, objetivo fuera de especificación y ancho de límites igual a 0 sustituido en silencio | Sin efecto en las cifras; mejoras de robustez y de redacción |

**Segunda pasada de validación.** Después de las correcciones de los autores, el revisor repitió la verificación con la misma desconfianza y la documentó en `docs/validacion.md`. Tuvo tres resultados.

1. *Los hallazgos de la primera pasada quedaron corregidos.* De las 20 pruebas ejecutables con que el revisor documentó esos hallazgos (marcadas `xfail` mientras el error existía), 18 pasaron a verde de inmediato. Las otras dos estaban mal planteadas, porque llamaban a la función del intervalo sin informar con qué estimador se había calculado sigma, y se reescribieron para medir el camino real; hoy pasan.
2. *La corrección de los intervalos de capacidad se verificó por simulación propia.* Con un proceso normal de Cp = 1,5 y Cpk = 4/3, el intervalo nominal del 95 % cubrió el valor verdadero entre 0,944 y 0,955 de las veces en seis casos (sigma estimada con $\bar{R}/d_2$, con $\bar{S}/c_4$, con $\overline{MR}/d_2$, por desviación combinada con $n$ variable y con límites congelados de X-barra-R y de I-MR), frente a 0,58 a 0,93 con los grados de libertad $N-1$ de la versión anterior. Este es el respaldo empírico de que los intervalos de la sección 12 tienen la confianza que declaran.
3. *Se registraron diez hallazgos nuevos (H17 a H26)*, casi todos de redacción de la interpretación automática y de gravedad baja o media-baja: una frase de confianza sobre Cpk que se daba también con proceso inestable (H20); un hallazgo de formas de distribución afirmado por ruido de muestreo con $n$ pequeño (H21); la probabilidad de ver algún rezago fuera de banda por azar, sobrestimada al suponer rezagos independientes (H23: 0,64 frente a 0,52 por simulación con $n$ = 120 y 20 rezagos); una advertencia de falsas alarmas que no valía cuando la línea central coincide con un conteo posible (H19) y un hallazgo que contradecía la advertencia sobre N3 y N4 (H18); el texto «no puede señalar mejoras» en el diseño con WE4 aplicada (H22); el texto sobre «variabilidad dentro de los subgrupos» en un gráfico de individuales (H24); una sobrestimación leve de los grados de libertad de I-MR con exclusiones intermedias (H26); errores aritméticos en dos archivos de referencia (H17); y detalles de redacción (H25). Todos se corrigieron y **la suite quedó sin pruebas con fallo esperado**: la línea final es `953 passed, 1 skipped`. Las cifras numéricas de este informe no cambiaron con esas correcciones; cambiaron los textos de interpretación, y las salidas del anexo A se regeneraron con el software corregido.

> **Alcance de la verificación de H17 a H26.** El cuerpo de `docs/validacion.md` describe la segunda pasada tal como quedó antes de corregir esos diez hallazgos; su nota inicial registra el estado posterior. Estas últimas correcciones se comprobaron con la prueba ejecutable que el revisor dejó para cada hallazgo, no con una tercera revisión independiente.

**Límites de la verificación.** Los datos de libro de los ejemplos de las pruebas se transcribieron de memoria y solo se verificó su consistencia interna; los números de sección y de ejemplo de Montgomery citados en el código no se cotejaron con el ejemplar. La verificación confirma que el software calcula lo que dice calcular y que sus textos no afirman más de lo que los datos permiten; no sustituye la validación con datos reales de una empresa.

## 8. Caracterización de los datos

> Todos los datos de esta sección son **sintéticos**.

### 8.1 Archivos usados

**Tabla 1**

*Archivos sintéticos usados en el caso de aplicación*

| Archivo | Contenido | Uso en el informe |
|---|---|---|
| `sintetico_fase1` | 25 subgrupos de n = 5 (125 pesos) con un desplazamiento de +3 g en el subgrupo 12 | Fase I, supuestos y capacidad |
| `sintetico_fase2` | 15 subgrupos de n = 5 con la media desplazada 1,8 g (1,5 sigmas) | Fase II |
| `sintetico_p_n_variable` | 30 muestras con n entre 81 y 120 | Gráfico p |

*Nota.* Los archivos y su resultado esperado se describen en `data/ejemplos/README.md`. Los datos se generaron con semilla fija. La lectura de cada uno está en `salidas/parse_sintetico_fase1.json`, `parse_sintetico_fase2.json` y `parse_sintetico_p_n_variable.json`.

### 8.2 Estadística descriptiva de la Fase I

**Tabla 2**

*Estadística descriptiva del peso neto, Fase I (datos sintéticos)*

| Estadístico | Con los 25 subgrupos (n = 125) | Sin el subgrupo 12 (n = 120) |
|---|---|---|
| Media (g) | 499,896 | 499,809 |
| Desviación estándar (g) | 1,384 | 1,306 |
| Mínimo (g) | 496,53 | 496,53 |
| Máximo (g) | 503,41 | 502,85 |
| Asimetría | 0,198 | 0,050 |
| Exceso de curtosis | -0,124 | -0,233 |

*Nota.* Fuentes: `salidas/resumen_fase1.json` y `salidas/supuestos_fase1_depurada.json` (campo `descriptive`).

**Interpretación.** La media está muy cerca del nominal (500 g) y la asimetría y la curtosis son pequeñas: no hay un sesgo visible. Retirar el subgrupo 12 reduce la desviación de 1,384 g a 1,306 g, es decir, ese único subgrupo explica casi toda la dispersión extra. Un detalle metodológico importante: el criterio de atípicos de Tukey (1,5 veces el rango intercuartílico) **no marcó ninguna observación** de la Fase I, incluidas las del subgrupo 12, porque el desplazamiento de +3 g mueve las cinco lecturas del subgrupo a la vez y ninguna queda lejos de las demás. El gráfico de control sí lo detecta (sección 10). Un filtro de valores individuales no sustituye al gráfico de control.

### 8.3 Calidad de los datos y limpieza

El archivo `sintetico_sucio` (20 subgrupos de hasta cinco envases) ilustra el tratamiento de errores de captura. Su lectura (`salidas/parse_sintetico_sucio.json`) devuelve, junto con las columnas, ocho **avisos de limpieza** (campo `warnings` de la hoja): una fecha escrita día/mes/año normalizada a formato ISO; en `turno`, una celda con espacios recortados y un texto vacío registrado como faltante; en `x1`, un texto no numérico (de tipo «N/D») tratado como faltante; en `x2` y en `x4`, una celda vacía cada una; y en `x3` y `x5`, un valor con coma decimal convertido a punto. La interfaz muestra estos avisos en un recuadro al leer el archivo y, al guardar el conjunto, los copia a la bitácora de limpieza, de modo que ninguna conversión queda sin rastro.

El resumen (`salidas/resumen_sucio.json`) cuenta 97 observaciones en lugar de 100, calcula una media de 546,8 g y una desviación de 462 g (valores sin sentido para un proceso de 500 g) y marca como atípico el valor 5050 del subgrupo 9 (posición 5) con la cerca de Tukey Q3 + 1,5·IQR = 503,7, sin eliminarlo: la decisión queda a cargo del usuario, con justificación escrita. Los subgrupos 3, 7 y 11 quedan con 4 observaciones porque les faltaba una celda. Como X-barra necesita subgrupos del mismo tamaño, la interfaz lista esos subgrupos como incompletos y permite **retirarlos**, uno a uno o todos, con una justificación obligatoria que va a la bitácora. No rellena los valores faltantes: inventar datos distorsionaría los límites y la estimación de sigma. Que el valor 5050 sea un decimal mal capturado es una **interpretación del equipo sobre un archivo construido a propósito**; en un proceso real habría que verificarlo en la fuente.

> **POR COMPLETAR CON LA EMPRESA:** caracterización de los datos reales: periodo, número de subgrupos y observaciones, faltantes, valores corregidos a mano, cambios de formato, de proveedor o de equipo, y bitácora de limpieza del software. Formato de origen: archivo recolectado según `docs/empresa/formato-recoleccion.md` y la «nota de cambios» que ese formato pide traer.

## 9. Diagnóstico preliminar

> **POR COMPLETAR CON LA EMPRESA:** el diagnóstico preliminar (hallazgos de la visita, registros actuales, instrumentos y su calibración, condiciones que cambian el resultado, quejas de clientes) sale de la visita técnica y de las entrevistas. Información faltante: acta de visita firmada, notas de observación y respuestas por cargo (`docs/empresa/guia-visita.md`, «Qué observar» y «A quién preguntar»). No se redactan hallazgos de planta sin haber ido a la planta.

**Lo que sí puede decirse con el ejemplo sintético.** Antes de graficar, el plan exige tres comprobaciones que el software facilita: que los subgrupos estén justificados (el programa no guarda un conjunto sin esa justificación), que los datos estén limpios (bitácora) y que el tamaño de subgrupo sea constante para X-barra. El ejemplo de Fase I las cumple.

## 10. Análisis de los gráficos de control

> Caso **sintético**. Salidas: `salidas/fase1_xbar_r_inicial.json`, `fase1_xbar_r_depurada.json`, `fase2_xbar_r.json` y archivos asociados.

### 10.1 Fase I: estimación de los límites

Con los 25 subgrupos y solo la regla de un punto fuera de los límites, el gráfico X-barra-R estima los parámetros de la Tabla 3 y señala el subgrupo 12.

**Tabla 3**

*Límites de control X-barra-R en Fase I, antes y después de excluir el subgrupo 12 (datos sintéticos)*

| Parámetro | Antes de excluir (25 subgrupos) | Tras excluir el subgrupo 12 (24 subgrupos) |
|---|---|---|
| Línea central X-barra (g) | 499,896 | 499,809 |
| LCS X-barra (g) | 501,659 | 501,547 |
| LCI X-barra (g) | 498,133 | 498,072 |
| R-barra (g) | 3,056 | 3,012 |
| LCS de R (g) | 6,462 | 6,369 |
| LCI de R (g) | 0 | 0 |
| Sigma estimada, R-barra/d2 (g) | 1,314 | 1,295 |
| Señales (regla WE1) | Subgrupo 12 (media 501,98 g) | Ninguna |

*Nota.* Fuentes: `salidas/fase1_xbar_r_inicial.json` y `salidas/fase1_xbar_r_depurada.json`. La causa asignable «boquilla obstruida» es **ficticia** y pertenece al ejemplo; el programa exige escribir una causa para excluir un punto.

**Figura 1**

*Gráfico X-barra-R de la Fase I antes de excluir puntos (datos sintéticos)*

![Gráfico X-barra y R de la Fase I con el subgrupo 12 fuera del límite superior](../figuras/fig01_fase1_inicial.png)

*Nota.* Los rombos rojos marcan señales de la regla de un punto fuera de límites. Fuente: `salidas/fase1_xbar_r_inicial.json`.

**Interpretación.** La media del subgrupo 12, 501,98 g, supera el LCS (501,659 g) por 0,32 g, y el gráfico R no muestra señales: la **dispersión dentro del subgrupo es normal y solo cambió su nivel**. Eso orienta la búsqueda de causas: una variable que desplaza toda la fila de envases del turno a la vez (por ejemplo, un ajuste de la dosificadora o una obstrucción de boquilla), no una pérdida de repetibilidad. Mientras la señal esté sin explicar, el software advierte que la sigma incluye una causa especial y que los índices de capacidad no son válidos. Excluir el subgrupo 12 mueve la línea central 0,09 g hacia el nominal y estrecha los límites unas centésimas, un efecto pequeño pero que sesgaría la vigilancia posterior si la causa se dejara dentro.

**Figura 2**

*Gráfico X-barra-R de la Fase I tras excluir el subgrupo 12 (datos sintéticos)*

![Gráfico X-barra y R de la Fase I con el subgrupo 12 marcado como excluido y límites recalculados](../figuras/fig02_fase1_depurada.png)

*Nota.* La cruz negra indica el subgrupo excluido del cálculo, que permanece visible. Fuente: `salidas/fase1_xbar_r_depurada.json`.

**Interpretación.** Con los 24 subgrupos restantes no queda ningún punto con señal, tampoco con las cuatro reglas de Western Electric (`salidas/fase1_xbar_r_depurada_we.json`): el proceso de Fase I se considera estable y sus límites pueden congelarse. Como comprobación de coherencia del método, el gráfico X-barra-S sobre los mismos datos estima una sigma de 1,289 g contra 1,295 g del método R-barra (`salidas/fase1_xbar_s_depurada.json`): difieren menos de 0,5 %, como corresponde a n = 5.

### 10.2 Fase II: monitoreo con límites congelados

Se congelaron los parámetros de la Tabla 3 ($\mu$ = 499,809 g y $\sigma$ = 1,295 g) y se compararon los 15 subgrupos de `sintetico_fase2`.

**Tabla 4**

*Resultado de Fase II con límites congelados (datos sintéticos)*

| Configuración | Subgrupos con señal (de 15) | Subgrupos |
|---|---|---|
| Solo un punto fuera de límites (WE1) | 11 | 26, 28, 30, 31, 32, 33, 34, 35, 36, 38 y 39 |
| Reglas WE1 a WE4 | 15 | Todos, el primero en el 26 |
| Gráfico R (WE1) | 0 | Ninguno |

*Nota.* Fuentes: `salidas/fase2_xbar_r.json` y `salidas/fase2_xbar_r_we.json`. En Fase II los subgrupos continúan la numeración de la Fase I (26 a 40).

**Figura 3**

*Gráfico X-barra-R de la Fase II con límites congelados (datos sintéticos)*

![Gráfico X-barra y R de la Fase II con los puntos sobre el límite superior congelado](../figuras/fig03_fase2.png)

*Nota.* Los límites son los de la Fase I depurada y no se recalcularon. Fuente: `salidas/fase2_xbar_r.json`.

**Interpretación.** La primera señal aparece en el primer subgrupo de Fase II. La media de los 75 envases de Fase II es 501,73 g, es decir, el proceso se desplazó unos 1,92 g, o 1,48 desviaciones de proceso, respecto de la media de Fase I. Con n = 5 y L = 3, la probabilidad teórica de que un desplazamiento de 1,5 sigmas dé señal en un subgrupo es 1 − β = 0,638 (sección 14.1), así que se esperarían unas 9,6 señales en 15 subgrupos; se observaron 11, lo que es coherente. Que 4 de 15 puntos queden dentro de los límites **no significa que el proceso haya vuelto a control**: los subgrupos 27, 29, 37 y 40 son simplemente los que el ruido dejó por debajo del LCS. Ese comportamiento justifica activar reglas de zona, que con WE1 a WE4 dejan los 15 subgrupos señalizados. El gráfico R no señala: la variabilidad no cambió, solo el nivel. Esto distingue un problema de **centrado** (ajuste) de uno de **dispersión** (repetibilidad), y define la acción: recentrar, no reparar la máquina.

**Contraste: límites sin depurar.** Con los límites de la Fase I sin excluir el subgrupo 12 (`salidas/fase2_xbar_r_limites_sin_depurar.json`), los mismos 11 subgrupos señalan, porque la diferencia entre ambos conjuntos de límites (0,11 g en el LCS) es mucho menor que el desplazamiento de Fase II. En este ejemplo depurar no cambia la conclusión de Fase II, pero sí cambia la sigma que alimenta la capacidad y el ARL; con un desplazamiento menor, la diferencia entre ambos conjuntos de límites podría decidir si hay señal o no.

### 10.3 Gráficos por atributos: gráfico p con tamaño de muestra variable

El asistente del software recomienda el gráfico p para unidades defectuosas con tamaño variable, porque el gráfico np exigiría un n constante (`salidas/recomendar_p.json`). Con las 30 muestras de `sintetico_p_n_variable` (n entre 81 y 120; 150 defectuosos en 3 099 unidades, p-barra = 0,0484):

**Tabla 5**

*Gráfico p de Fase I antes y después de excluir las muestras 8 y 20 (datos sintéticos)*

| Elemento | Antes de excluir (30 muestras) | Tras excluir las muestras 8 y 20 (28 muestras) |
|---|---|---|
| Línea central p-barra | 0,04840 | 0,04183 |
| LCS (rango según n de cada muestra) | 0,1072 a 0,1199 | 0,09665 a 0,1086 |
| LCI | 0 (truncado) | 0 (truncado) |
| Señales (regla WE1) | Muestras 8 (0,1395) y 20 (0,1417) | Ninguna |

*Nota.* Fuentes: `salidas/p_fase1_inicial.json`, `salidas/p_fase1_depurada.json` y `salidas/resumen_atributos_p.json`. Las causas escritas para excluir las muestras 8 y 20 son **ficticias** y están marcadas como tales en la petición guardada; sirven solo para ejecutar el flujo.

**Figura 4**

*Gráfico p de Fase I con límites por muestra (datos sintéticos)*

![Gráfico p con límites variables y las muestras 8 y 20 sobre el límite superior](../figuras/fig09_grafico_p.png)

*Nota.* Los límites cambian de una muestra a otra porque cambia el tamaño. Fuente: `salidas/p_fase1_inicial.json`.

**Interpretación.** Las dos muestras señaladas tienen un 14 % de defectuosos frente a un 4,8 % medio. Por construcción de los datos esas muestras son las anómalas, y el gráfico las detecta. Como el límite inferior se trunca en 0, el gráfico p con n cercano a 100 y p-barra de 4,8 % **no puede señalar mejoras** (una baja inesperada de defectuosos), y el software lo avisa. En una planta, esto importa: una mejora real no aparecería como señal y habría que usar otros criterios para reconocerla.

El gráfico p es un ejemplo de selección justificada de gráfico por tipo de variable y tamaño de muestra, como pide el módulo 3. Los gráficos np, c y u se verificaron con sus archivos de prueba; por ejemplo, el gráfico c de `sintetico_c` da c-barra = 2,5, LCS = 7,243 y señala la unidad 18 con 9 defectos (`salidas/c_ejemplo.json`).

### 10.4 Gráfico de individuales

Con `sintetico_i_mr` (60 observaciones con tendencia desde la 46), el gráfico I-MR da MR-barra = 1,672, límites de individuales de 495,88 g a 504,77 g y señala únicamente el rango móvil de la observación 16 (`salidas/imr_ejemplo.json`). Ningún individual sale de sus límites, y **la tendencia de la observación 46 en adelante no se detecta con la regla de un punto**. Esto ilustra un límite del gráfico de Shewhart con la regla básica ante derivas lentas, que se discute en las limitaciones de la sección 18. En el panel de rango móvil el software solo evalúa la regla de un punto fuera de límites, porque rangos móviles consecutivos están correlacionados (sección 6.2); activar más reglas en ese panel no añadiría señales válidas. La interpretación automática de esa salida trata el rango móvil fuera de límites como lo que es en un gráfico de individuales: «un salto grande entre dos observaciones consecutivas: un dato atípico, un error de registro o un cambio de nivel», y añade que «un rango móvil grande aislado no demuestra que haya cambiado la variabilidad del proceso»; recomienda revisar esas observaciones en el gráfico de individuales, porque MR-barra ensancha los límites de ese gráfico.

## 11. Validación de supuestos

> Caso **sintético**, Fase I depurada (120 observaciones). Salida: `salidas/supuestos_fase1_depurada.json`.

**Tabla 6**

*Pruebas de normalidad e independencia, Fase I depurada, α = 0,05 (datos sintéticos)*

| Prueba | Estadístico | Valor p o valor crítico | Decisión |
|---|---|---|---|
| Shapiro-Wilk | W = 0,9935 | p = 0,8524 | No se rechaza normalidad |
| Anderson-Darling | A² = 0,2113 | Crítico 0,7472 | No se rechaza normalidad |
| Ljung-Box (20 rezagos) | Q = 34,24 | p = 0,0245 | Se rechaza independencia |
| Rachas (mediana, exacta) | z = -0,74 | p = 0,5182 | No se rechaza aleatoriedad |

*Nota.* Fuente: `salidas/supuestos_fase1_depurada.json`. El valor crítico de Anderson-Darling es el de D'Agostino y Stephens (1986) para n = 120. Con los 125 datos originales, Ljung-Box da Q = 33,82 (p = 0,0274) y rachas p = 0,6528 (`salidas/supuestos_fase1_con_subgrupo12.json`).

**Figura 5**

*Histograma y gráfico Q-Q normal, Fase I depurada (datos sintéticos)*

![Histograma con curva normal y gráfico Q-Q de los 120 pesos](../figuras/fig04_normalidad.png)

*Nota.* La recta del gráfico Q-Q usa la media y la desviación de los datos. Fuente: `salidas/supuestos_fase1_depurada.json`.

**Figura 6**

*Función de autocorrelación, Fase I depurada (datos sintéticos)*

![Autocorrelación de 20 rezagos con el rezago 6 fuera de la banda de significancia](../figuras/fig05_acf.png)

*Nota.* La banda es ±0,179. Solo el rezago 6 (r = -0,281) sale de la banda. Fuente: `salidas/supuestos_fase1_depurada.json`.

**Interpretación y juicio de ingeniería.** La normalidad se sostiene con ambas pruebas, y el Q-Q tiene correlación de 0,9975 con la recta normal: los índices de capacidad basados en el modelo normal son razonables (sin olvidar que no rechazar no demuestra normalidad). La independencia es más delicada, y el software la presenta como lo que es: **evidencia débil** contra la independencia, no una demostración de autocorrelación. Ljung-Box rechaza (p = 0,0245), pero hay cuatro razones para no tomar ese rechazo al pie de la letra. Primera, depende de una sola prueba: la de rachas no rechaza (p = 0,5182). Segunda, en la ACF solo un rezago de 20 sale de la banda, el 6, con signo negativo (r = -0,281) y sin sentido físico claro; con 20 rezagos, n = 120 y α = 0,05 el software informa que se esperan unos 0,79 rezagos fuera de banda solo por azar (aproximación con la varianza (n - k)/(n(n + 2)) de cada autocorrelación), de modo que uno aislado no es raro. (La probabilidad de ver al menos uno, que según la simulación del revisor es de 0,52 con estos n y número de rezagos, no la calcula el software; la cifra proviene de `docs/validacion.md`, hallazgo H23.) Tercera, el rezago 1, el que más preocupa en un proceso de llenado continuo, es pequeño y está dentro de la banda (r1 = 0,074). Cuarta, con muchos rezagos el tamaño real de Ljung-Box es algo mayor que α, y combinar dos pruebas de independencia eleva la probabilidad de que alguna rechace por azar (del orden de 7 % a 13 % con α = 0,05, según la validación). Además, los datos se generaron como independientes (`data/generar_ejemplos.py`), de modo que este rechazo es una **falsa alarma esperable de una prueba hecha al 5 %**. La lección para el caso real es doble: no se debe descartar un análisis por un único valor p marginal, y tampoco ignorar el resultado: se mira la ACF, el contexto de muestreo y se decide, y con más datos u otro orden de muestreo se confirma. El software expresa esa cautela: su conclusión dice que la evidencia contra la independencia es débil y que no alcanza para afirmar que las observaciones estén autocorrelacionadas. Una limitación adicional, que el software también advierte: la serie concatena subgrupos (cinco mediciones seguidas y luego una pausa) y, en Fase I depurada, tiene un hueco donde se retiró el subgrupo 12, de modo que el rezago k no corresponde siempre al mismo intervalo y las pruebas son aproximadas; un análisis más fino requeriría trabajar con las medias de subgrupo.

**Casos de contraste (sintéticos).** `sintetico_no_normal` (80 tiempos de llenado lognormales) rechaza la normalidad con Shapiro-Wilk W = 0,8873 (p menor que 0,0001), A² = 2,116 y asimetría 1,57, con independencia sostenida; el software advierte que los índices de capacidad no serían confiables y que, antes de transformar los datos, hay que confirmar que el proceso esté en control, porque un proceso con desplazamientos también hace rechazar estas pruebas. `sintetico_autocorrelado` (60 datos AR(1) con φ = 0,7) obtiene r1 = 0,703 y 7 de 15 rezagos fuera de banda (se esperarían unos 0,75 por azar), Ljung-Box Q = 87,22 (p menor que 0,0001) y rachas con p = 0,0003; aquí sí, y con la evidencia en conjunto, el software afirma que hay evidencia de autocorrelación y advierte que los límites de Shewhart darían falsas alarmas (`salidas/supuestos_no_normal.json` y `salidas/supuestos_autocorrelado.json`). Que el software detecte ambos casos construidos a propósito es la evidencia de que la validación de supuestos funciona.

**Patrones no aleatorios.** Se evalúan con las reglas de corrida de los gráficos de control (sección 10): en Fase I no hay patrones con WE1 a WE4 tras excluir el subgrupo 12.

**Causas especiales.** La única identificada en el ejemplo es el subgrupo 12, con causa ficticia documentada en la petición.

> **POR COMPLETAR CON LA EMPRESA:** supuestos y causas especiales del proceso real, con la causa verificada en planta para cada punto excluido (qué ocurrió, quién lo informó, evidencia). Información faltante: registros de turno y bitácora de mantenimiento (guía de visita, «A quién preguntar», encargado de mantenimiento y operario de la estación crítica).

## 12. Capacidad del proceso

> Caso **sintético**. Especificaciones del ejemplo: LIE = 495 g, LSE = 505 g, nominal = 500 g. Salida: `salidas/capacidad_fase1_depurada.json`.

**Tabla 7**

*Índices de capacidad, Fase I depurada (n = 120; datos sintéticos)*

| Índice | Valor | IC 95 % |
|---|---|---|
| Cp | 1,287 | 1,096 a 1,478 |
| Cpl | 1,238 | 1,044 a 1,431 |
| Cpu | 1,336 | 1,129 a 1,543 |
| Cpk | 1,238 | 1,044 a 1,431 |
| Pp | 1,276 | 1,114 a 1,438 |
| Ppk | 1,227 | 1,060 a 1,394 |
| Cpm (T = 500) | 1,263 | no calculado |

*Nota.* Los datos son los 24 subgrupos retenidos de la Fase I (120 observaciones), que es lo que la interfaz usa por defecto cuando hay límites congelados. Sigma de corto plazo 1,295 g (de los límites congelados, con ν ≈ 86,9 grados de libertad efectivos) y de largo plazo 1,306 g (desviación muestral, 119 grados de libertad). Media 499,809 g. Los intervalos de Cp, Cpl, Cpu y Cpk usan ν = 86,9; los de Pp y Ppk, N - 1. Veredicto del software: marginal. Fuente: `salidas/capacidad_fase1_depurada.json`.

**Figura 7**

*Histograma con especificaciones, Fase I depurada (datos sintéticos)*

![Histograma de los pesos entre las líneas de especificación 495 y 505](../figuras/fig06_capacidad.png)

*Nota.* Fuente: `salidas/capacidad_fase1_depurada.json`.

**Interpretación.** Cp = 1,29 indica que la tolerancia de 10 g es 1,29 veces la dispersión natural de 6 sigmas (7,77 g): el proceso ocupa el 77,7 % del intervalo de especificación. La media (499,81 g) está a 0,19 g del centro, así que Cpk (1,24) es muy cercano a Cp: **para mejorar la capacidad habría que reducir la variación más que recentrar**. Las sigmas de corto y largo plazo son casi iguales (1,295 y 1,306 g), así que Ppk y Cpk cuentan lo mismo: no hay desplazamientos importantes entre subgrupos. El veredicto «marginal» (1 a 1,33) debe leerse con la incertidumbre: el IC 95 % de Cpk (1,04 a 1,43) incluye valores por debajo de 1,33 y por encima; **con 120 datos no se puede asegurar ni que el proceso sea adecuado ni que sea inadecuado**, solo que su capacidad es del orden de 1,0 a 1,4 y que no demuestra el 1,33 que se recomienda para procesos existentes con especificación bilateral. Cpm (1,26) es cercano a Cpk, lo que confirma que no hay desviación apreciable respecto al nominal.

**Por qué los intervalos son más anchos que con $N-1$.** Como la sigma de corto plazo es la congelada de la Fase I, que equivale a 24 desviaciones de subgrupo y no a 119 grados de libertad, el intervalo de Cp mide 0,38 de ancho (de 1,096 a 1,478) en lugar de los 0,33 que daría tratar la sigma como una desviación muestral de 120 datos (de 1,124 a 1,450). Es el efecto de la corrección de grados de libertad descrita en la sección 6.2, y el software lo advierte en la interpretación.

**Cómo el software formula la conclusión de capacidad.** La frase «con 95 % de confianza Cpk supera el mínimo» solo se afirma cuando la estabilidad del proceso está confirmada; con un proceso inestable o sin estabilidad informada, el resumen declara que no se puede declarar la capacidad, como en la salida de Fase II citada en la sección 13. Y cuando el Cpk puntual alcanza el mínimo requerido pero la cota inferior de confianza unilateral no, el resumen dice que el veredicto no es concluyente. En el caso sintético de Fase I depurada (estable, Cpk = 1,24 < 1,33) ninguna de las dos situaciones se presenta, y la salida dice que «la conclusión firme es que el proceso no demuestra la capacidad requerida». El diagnóstico de fondo no cambia (capacidad marginal), pero la incertidumbre es mayor de lo que mostraba la versión anterior.

Los resultados dependen de supuestos: proceso estable (cumplido tras excluir el subgrupo 12) y normalidad (no rechazada). La evidencia débil contra la independencia señalada en la sección 11 no modifica de forma importante las sigmas de corto y largo plazo, tan parecidas entre sí.

> **POR COMPLETAR CON LA EMPRESA:** capacidad del proceso real, con las especificaciones reales y su fuente (LIE, LSE, nominal), y comparación con lo que la empresa considera aceptable. Formato de origen: `docs/empresa/plan-muestreo.md`, sección 2, y hoja de especificaciones del producto.

## 13. Fracción no conforme

**Tabla 8**

*Fracción no conforme esperada y observada (datos sintéticos)*

| Conjunto | Modelo | Bajo LIE (PPM) | Sobre LSE (PPM) | Total (PPM) | Observada |
|---|---|---|---|---|---|
| Fase I depurada (n = 120) | Normal, sigma de corto plazo | 102 | 31 | 133 | 0 de 120 |
| Fase I depurada (n = 120) | Normal, sigma de largo plazo | 116 | 35 | 151 | 0 de 120 |
| Fase II (n = 75), sigma congelada | Normal, sigma de corto plazo | 0,1 | 5 816 | 5 816 | 0 de 75 |
| Fase II (n = 75) | Normal, sigma de largo plazo | 0,003 | 2 419 | 2 419 | 0 de 75 |

*Nota.* Fuentes: `salidas/capacidad_fase1_depurada.json` y `salidas/capacidad_fase2_limites_fase1.json`. Cifras redondeadas desde las salidas, que dan las proporciones exactas.

**Interpretación.** En Fase I se espera ~133 PPM (0,013 %), con mayor aporte del lado inferior (102 PPM): coherente con una media ligeramente por debajo del nominal. En Fase II, con la media desplazada hacia el LSE, se esperan entre 2 419 y 5 816 PPM, de 18 a 44 veces más. Las unidades fuera de especificación observadas son 0 en ambos periodos y eso **no contradice** el modelo: con 75 datos solo se vería alguna unidad fuera si la fracción no conforme fuera del orden de 1,3 % o mayor, así que la fracción observada no sirve para confirmar valores de PPM bajos. Para un responsable de planta esta es la conclusión práctica: **el proceso ya estaba produciendo con riesgo creciente de incumplimiento mientras el conteo de unidades no conformes seguía en cero.** El gráfico de control y la capacidad modelada ven el problema antes que la inspección por conteo.

Capacidad en Fase II (`salidas/capacidad_fase2_limites_fase1.json`): Cpk = 0,841 (IC 95 %: 0,695 a 0,987), Cpm = 0,799. El resumen del software dice que, como el proceso no está en control estadístico, «no se puede declarar su capacidad», y advierte que esos índices no son confiables. Se informan solo para dimensionar el efecto del desplazamiento: Cp se mantiene en 1,287 (la dispersión no cambió) y Cpk cae 0,40 por el descentrado. Con la sigma de Fase II calculada por R-barra (1,165 g) el Cpk es 0,935 (IC 95 %: 0,744 a 1,127, con ν ≈ 54,3 grados de libertad efectivos; `salidas/capacidad_fase2_rbar.json`), una diferencia que muestra la sensibilidad del índice a la estimación de sigma y que el programa explica con una advertencia.

## 14. Análisis ARL y ATS

> Caso **sintético**. Supuestos del ejemplo: un subgrupo por turno, es decir, h = 8 horas, y operación continua de 24 horas (tres turnos). Los desplazamientos se miden en múltiplos de la desviación individual $\sigma$ del proceso.

### 14.1 Desempeño del diseño vigente (n = 5, L = 3, h = 8 h)

**Tabla 9**

*ARL y ATS del gráfico X-barra con n = 5, L = 3 y h = 8 h, solo con la regla de un punto fuera (cálculo exacto)*

| Desplazamiento (σ) | β | ARL1 (muestras) | ATS1 (h) | Unidades hasta la señal |
|---|---|---|---|---|
| 0,5 | 0,9701 | 33,40 | 267,2 | 167,0 |
| 1,0 | 0,7775 | 4,495 | 35,96 | 22,48 |
| 1,5 | 0,3616 | 1,566 | 12,53 | 7,83 |
| 2,0 | 0,0705 | 1,076 | 8,61 | 5,38 |
| 3,0 | 0,0001 | 1,000 | 8,00 | 5,00 |

*Nota.* ARL0 = 370,4 muestras y ATS0 = 2 963 h (aproximadamente 123 días de operación continua); carga muestral 0,625 unidades por hora. Fuente: `salidas/arl_xbar_n5_h8.json`.

**Interpretación.** El gráfico detecta rápido los cambios grandes (de 2 sigmas en adelante, en un subgrupo o poco más) y es muy lento para los pequeños: 0,5 sigmas tarda 33 muestras, unas 267 horas, más de 11 días, con 167 envases medidos hasta la señal. La falsa alarma ocurre cada 370 muestras, cada 123 días de operación continua, un costo bajo. Es la relación habitual: los límites de 3 sigmas protegen contra falsas alarmas a costa de sensibilidad a cambios pequeños.

### 14.2 Efecto de las reglas suplementarias

**Tabla 10**

*Efecto de las reglas WE1 a WE4 en el diseño n = 5, L = 3, h = 8 h (simulación, 5 000 corridas, semilla 12345)*

| Medida | Solo WE1 (exacto) | WE1 a WE4 (simulado) |
|---|---|---|
| ARL0 (muestras) | 370,4 | 91,53 (error estándar 1,25) |
| ATS0 (h) | 2 963 | 732,2 (unos 30 días) |
| ARL1 con 0,5σ | 33,40 | 7,630 |
| ARL1 con 1,0σ | 4,495 | 2,610 |
| ARL1 con 1,5σ | 1,566 | 1,423 |
| ATS1 con 1,5σ (h) | 12,53 | 11,39 |

*Nota.* Fuentes: `salidas/arl_xbar_n5_h8.json` y `salidas/arl_xbar_n5_h8_we.json`.

**Figura 8**

*ARL1 del gráfico X-barra según el desplazamiento y el diseño (datos de la API)*

![ARL1 frente al desplazamiento para n = 3, 5 y 10 y para n = 5 con reglas de Western Electric](../figuras/fig07_arl1.png)

*Nota.* Escala logarítmica en el eje vertical. Fuentes: `salidas/arl_xbar_n3_h8.json`, `arl_xbar_n5_h8.json`, `arl_xbar_n10_h8.json` y `arl_xbar_n5_h8_we.json`.

**Interpretación.** Activar WE1 a WE4 multiplica las falsas alarmas por unas 4 (el ARL0 baja de 370,4 a 91,5: una falsa alarma cada 30 días en lugar de cada 123) y a cambio detecta el cambio de 1 sigma en 2,6 muestras en lugar de 4,5 y el de 0,5 sigmas en 7,6 en lugar de 33. Es la decisión de fondo del diseño: cuánta tolerancia se tiene a las falsas alarmas frente a la sensibilidad. Si cada falsa alarma implica detener y revisar la línea, el costo de una cada 30 días puede ser aceptable cuando el costo de producir fuera de centro es alto, que es el caso de este ejemplo, como se muestra a continuación.

### 14.3 Cómo se conectan ARL y ATS con n y h

**Tabla 11**

*Diseños alternativos para detectar un desplazamiento de 1,5σ, L = 3 (cálculo exacto)*

| n | h (h) | Carga n/h | ARL1 | ATS1 (h) | ATS0 (h) |
|---|---|---|---|---|---|
| 3 | 8 | 0,375 | 2,908 | 23,26 | 2 963 |
| 5 | 8 | 0,625 | 1,566 | 12,53 | 2 963 |
| 5 | 4 | 1,25 | 1,566 | 6,27 | 1 482 |
| 5 | 2 | 2,5 | 1,566 | 3,13 | 741 |
| 8 | 4 | 2,0 | 1,120 | 4,48 | 1 482 |
| 10 | 4 | 2,5 | 1,042 | 4,17 | 1 482 |
| 10 | 2 | 5,0 | 1,042 | 2,08 | 741 |

*Nota.* Selección de las 12 combinaciones de `salidas/comparar_disenos_1_5_sigma.json` (n = 3, 5, 8, 10 con h = 2, 4 y 8 h). El ARL1 depende solo de n y L; h escala el tiempo.

**Figura 9**

*ATS1 frente a la carga muestral para un desplazamiento de 1,5σ*

![Tiempo promedio hasta la señal frente a unidades inspeccionadas por hora para varios n y h](../figuras/fig08_ats_carga.png)

*Nota.* Cada punto es un par (n, h); las etiquetas indican h en horas. Fuente: `salidas/comparar_disenos_1_5_sigma.json`.

**Interpretación.** Para un mismo nivel de esfuerzo de inspección, la combinación de n y h no es indiferente. Con una carga de 2,5 unidades por hora, n = 5 cada 2 h detecta en 3,13 h y n = 10 cada 4 h en 4,17 h: **muestrear más seguido con subgrupos pequeños gana a muestrear menos seguido con subgrupos grandes** cuando el cambio es de tamaño moderado a grande y sostenido (el cambio se detecta casi siempre en el primer o segundo subgrupo, y lo que domina es el tiempo entre muestras). Para cambios pequeños la ventaja pasa a n grande, porque el ARL1 con n = 10 cae mucho más (12,8 muestras contra 33,4 para 0,5 sigmas; `salidas/arl_xbar_n10_h8.json`). La elección debe tomar en cuenta además el costo de una unidad medida y la rapidez con que el proceso suele desajustarse (`docs/empresa/plan-muestreo.md`, sección 5).

**Qué desplazamiento importa en este ejemplo.** Un desplazamiento de 1 sigma (1,295 g) lleva la media a unos 501,1 g y el Cpu a ≈ 1,00 (cálculo aritmético con los valores de la Tabla 7), es decir, ya hay riesgo apreciable de incumplimiento. Con n = 5 y h = 8 h ese cambio tarda 4,5 muestras, 36 horas, con solo WE1; con WE1 a WE4, 2,6 muestras (20,9 h); con n = 10 y h = 8 h, 1,77 muestras (14,2 h) con una carga de 1,25 envases por hora (`salidas/arl_xbar_n10_h8.json`). Un diseño razonable para este ejemplo sería entonces n = 5 con reglas de zona y h = 4 h, o n = 5 con h = 8 h y WE1 a WE4 si el costo de falsas alarmas lo permite. Es una recomendación **para el caso sintético**; con la empresa se redefine con sus costos.

### 14.4 Gráfico p

Para el gráfico p con n = 100, p0 = 0,048, L = 3 y h = 8 h (`salidas/arl_p_n100.json`), el ARL0 exacto es 323,9 y no 370,4, porque el conteo es discreto y el límite inferior se trunca en 0, de modo que toda la probabilidad de falsa alarma está en la cola superior (α = 0,0031). Detectar un aumento de la fracción defectuosa de 4,8 % a 7,2 % tarda en promedio 17,9 muestras (143 h) y a 9,6 %, 3,99 muestras (31,9 h), con carga de 12,5 unidades por hora. Los gráficos de atributos son más lentos que los de variables porque cada unidad aporta menos información; por eso se necesitan muestras mayores (n ≈ 100).

> **POR COMPLETAR CON LA EMPRESA:** diseño de muestreo real (n y h) justificado con el costo de medir, el costo de producir fuera de control y la velocidad de desajuste de la empresa. Información faltante: costos y velocidad de producción (guía de visita, jefe de producción y responsable de calidad) y `docs/empresa/plan-muestreo.md`, secciones 4 y 5.

## 15. Muestreo de aceptación

> Caso **sintético**. Supuestos del ejemplo, declarados por el equipo: AQL = 1 %, α = 5 %, LTPD = 6 %, β = 10 %, lote de 2 000 envases, distribución binomial.

**Tabla 12**

*Planes de muestreo de aceptación del ejemplo*

| Plan | n | Criterio | α real | β real | AOQL | ATI en AQL | ATI en LTPD |
|---|---|---|---|---|---|---|---|
| Simple diseñado | 110 | Aceptar si hay 3 o menos defectuosas | 0,0250 | 0,0980 | 1,67 % (con lotes de 2,66 %) | 157,3 | 1 815 |
| Doble evaluado | 50 + 50 | n1 = 50, c1 = 0, r1 = 3; n2 = 50, c2 = 2 | 0,0710 | 0,0831 | 1,39 % (con lotes de 2,40 %) | 204,7 | 1 840 |

*Nota.* El plan doble es un plan propuesto por el equipo para comparar, **no** una solución del problema de diseño. Fuentes: `salidas/muestreo_simple_diseno.json` y `salidas/muestreo_doble_evaluacion.json`. El ASN del doble es 69,1 unidades en AQL y 68,6 en LTPD.

**Figura 10**

*Curva OC y AOQ del plan simple n = 110, c = 3 (datos de la API)*

![Curva característica de operación y calidad promedio de salida del plan simple](../figuras/fig10_muestreo.png)

*Nota.* Fuente: `salidas/muestreo_simple_diseno.json`.

**Interpretación.** El software encuentra el plan simple más pequeño que cumple los dos riesgos: n = 110 y c = 3. Con c = 2 el menor n que cumple el riesgo del consumidor es 88, pero entonces el riesgo del productor es 5,87 % (más de 5 %), y aumentar n solo lo empeora; por eso hay que pasar a c = 3. El programa lo explica (con c = 2 el menor n que cumple β es 88, con β = 0,0959, pero α = 0,0587 > 0,05, y aumentar n solo empeora α) y la búsqueda es exacta, no la lectura de un nomograma, cuyo plan aproximado de n = 88 y c = 2 no garantizaría el riesgo del productor. El plan doble evaluado ahorra inspección en los extremos (ASN de unas 69 unidades frente a 110) pero **no cumple α ≤ 5 %** (α = 7,1 %), así que como está no sustituye al simple.

**Relación con el control del proceso.** La fracción no conforme esperada del proceso de Fase I (133 PPM, 0,013 %) y aun la de Fase II (hasta 0,58 %) están por debajo del AQL del ejemplo (1 %): un plan con ese AQL aceptaría prácticamente todos los lotes de este proceso en ambas fases, incluso después de desplazarse. El muestreo de aceptación **no habría detectado el cambio que el gráfico X-barra sí detectó en el primer subgrupo**. Es la razón por la que el software lo advierte: el muestreo de aceptación decide sobre lotes, la mejora y la detección temprana vienen del control estadístico del proceso. Si el cliente exigiera un AQL del orden de 0,05 % (500 PPM), el desplazamiento de Fase II sí lo violaría; esa exigencia es la que se debe confirmar con la empresa.

> **POR COMPLETAR CON LA EMPRESA:** AQL, LTPD, riesgos, tamaño de lote y distribución del acuerdo real con el cliente o proveedor, y tipo de inspección (con o sin rectificación). Información faltante: contrato o norma de aceptación (guía de visita, responsable de calidad).

## 16. Resultados

Síntesis del caso de aplicación **sintético**, en el orden del flujo de trabajo.

**Tabla 13**

*Resumen de resultados del caso sintético*

| Pregunta | Resultado | Sección |
|---|---|---|
| ¿Es estable el proceso en Fase I? | No inicialmente (subgrupo 12). Sí tras excluirlo con causa asignable: LC = 499,809 g, límites 498,072 y 501,547 g, R-barra = 3,012 g | 10.1 |
| ¿Siguen estable los datos nuevos (Fase II)? | No: 11 de 15 subgrupos con WE1 y 15 de 15 con WE1 a WE4; R sin señales. Es un desplazamiento de nivel de ≈ 1,5σ | 10.2 |
| ¿Se cumplen normalidad e independencia? | No hay evidencia contra la normalidad. Evidencia débil contra la independencia: una sola prueba marginal (p = 0,0245), rachas sin rechazo (p = 0,5182) y un solo rezago fuera de banda | 11 |
| ¿Es capaz el proceso? | Marginal: Cp = 1,287 y Cpk = 1,238 (IC 95 %: 1,044 a 1,431) | 12 |
| ¿Qué fracción se espera fuera de especificación? | 133 PPM en Fase I; 2 419 a 5 816 PPM con el desplazamiento de Fase II; 0 unidades observadas en ambas | 13 |
| ¿Qué tan rápido detecta el diseño vigente? | ARL0 = 370,4; 1,5σ en 1,57 muestras (12,5 h); 1σ en 4,5 muestras (36 h) | 14 |
| ¿Cuánto cuestan las reglas suplementarias? | ARL0 pasa de 370,4 a 91,5 (una falsa alarma cada ≈ 30 días) | 14.2 |
| ¿Qué plan de aceptación? | n = 110, c = 3, para AQL 1 % y LTPD 6 % | 15 |

*Nota.* Todas las cifras proceden de las salidas de la API enumeradas en el Anexo A y son sintéticas.

**Qué dice el conjunto.** El ejemplo cuenta una historia coherente de la que cada módulo aporta una pieza: un proceso con capacidad marginal pero estable, una causa especial identificada y retirada en Fase I, un desplazamiento posterior de 1,5σ que el gráfico detecta de inmediato pese a que el conteo de unidades fuera de especificación sigue en cero, y un diseño de muestreo cuyo costo y sensibilidad se pueden cuantificar. Los módulos de supuestos y capacidad, además, imponen cautelas (evidencia débil contra la independencia, intervalos amplios) que impiden sobreinterpretar.

> **POR COMPLETAR CON LA EMPRESA:** resultados del proceso real en la misma estructura de la Tabla 13, con el archivo de datos anonimizado y las salidas guardadas del software. Las cifras reales deben sustituir a las sintéticas y los gráficos deben regenerarse con `docs/informe/anexos/generar_figuras.py` apuntando a las nuevas salidas.

## 17. Propuestas de mejora

Se separan dos grupos. Las propuestas del **caso sintético** muestran cómo se enlazan hallazgo, acción y prioridad; son ilustrativas porque la causa «boquilla obstruida» es ficticia. Las **propuestas reales** dependen de la empresa.

### 17.1 Propuestas derivadas del caso sintético (ilustrativas)

Prioridad por impacto (efecto esperado sobre la capacidad o el riesgo) y facilidad (esfuerzo, costo y tiempo), cada una en alta, media o baja, y combinadas en una prioridad de ejecución.

**Tabla 14**

*Propuestas de mejora del caso sintético, enlazadas con su hallazgo y priorizadas*

| # | Propuesta | Hallazgo que la motiva | Impacto | Facilidad | Prioridad |
|---|---|---|---|---|---|
| 1 | Recentrar el proceso cuando X-barra señale en Fase II y verificar con un procedimiento de ajuste: la dispersión no cambió, solo el nivel | Fase II: 11 de 15 subgrupos con señal, R sin señales, Cpk de 1,24 a 0,84 con Cp constante (secciones 10.2 y 13) | Alto | Alta | **1 (inmediata)** |
| 2 | Adoptar el diseño n = 5 con reglas WE1 a WE4 y h = 4 h (o h = 8 h si el costo de falsas alarmas es limitante) | Con h = 8 h y solo WE1, 1σ tarda 36 h; con el cambio de 1σ el Cpu ya es ≈ 1,0 (sección 14) | Alto | Media: más muestreo y más falsas alarmas | **2** |
| 3 | Rutina de verificación de la boquilla al inicio de cada turno y registro de la causa cuando haya una señal | Subgrupo 12: desplazamiento de nivel sin cambio en la dispersión (sección 10.1) | Medio | Alta | **3** |
| 4 | Reducir la variación común para llevar el Cpk de 1,24 a más de 1,33 | Capacidad marginal con proceso centrado; IC 95 % de Cpk de 1,04 a 1,43 (sección 12) | Alto | Baja: exige estudio de causas comunes | 4 (planificar) |
| 5 | Verificar la independencia con más datos y separar muestras cuando haya dependencia | Evidencia débil contra la independencia: Ljung-Box marginal (p = 0,0245), rachas sin rechazo y un solo rezago fuera de banda (sección 11) | Bajo (depende de un solo rezago) | Alta | 5 |
| 6 | No depender del muestreo de aceptación con AQL de 1 % como control del proceso | Fracción no conforme esperada de 0,013 % a 0,58 %, por debajo del AQL (sección 15) | Medio | Alta | 6 (política) |

*Nota.* La clasificación de impacto y de facilidad es un juicio del equipo para el ejemplo sintético y debe revalidarse con la empresa. Las cifras citadas salen de las secciones indicadas.

**Discusión.** La propuesta 1 combina el mayor impacto con la mayor facilidad y se justifica con la combinación específica de hallazgos de Fase II: gráfico R sin señales, X-barra con señales y Cpk deteriorado con Cp constante, que apunta a un problema de centrado y no de repetibilidad. La propuesta 4 es la de mayor impacto de largo plazo pero requiere identificar causas comunes de variación, que este ejemplo sintético no puede mostrar. La propuesta 2 tiene una compensación visible en los resultados (más falsas alarmas a cambio de detección más rápida) que la empresa debe resolver con sus costos. La propuesta 5 tiene bajo impacto precisamente porque la evidencia es débil, y se incluye para mostrar que no toda señal estadística justifica una acción.

### 17.2 Propuestas para la empresa real

> **POR COMPLETAR CON LA EMPRESA:** propuestas técnicamente viables, priorizadas por impacto, facilidad y relación con los hallazgos estadísticos reales, en la estructura de la Tabla 14. Información faltante: hallazgos del análisis con datos reales (secciones 9 a 16) y restricciones operativas, de costo y de personal de la empresa (guía de visita).

## 18. Conclusiones

Las conclusiones separan lo que el trabajo logró sobre el software, lo que muestra el caso sintético y lo que queda abierto.

**Sobre el software.**

1. El software cubre los ocho módulos del enunciado, diferencia Fase I y Fase II en la interfaz y en la API (que impide excluir puntos en Fase II y exige límites congelados), exige justificación de subgrupo racional y causa asignable y devuelve en cada análisis conclusiones y advertencias en español. Sus 953 pruebas automáticas pasan (1 omitida y ninguna con fallo esperado).
2. Por regla del proyecto, cada fórmula lleva su fuente y una prueba contra un resultado conocido; además, los archivos sintéticos traen un resultado esperado calculado de forma independiente, y una revisión estadística independiente (`docs/validacion.md`) recalculó los resultados por otro camino. Esa revisión **encontró errores** (16 confirmados en la primera pasada, entre ellos los grados de libertad de los intervalos de capacidad, los valores críticos de Anderson-Darling y la prueba de rachas) y **se corrigieron**; las cifras de este informe se regeneraron después de las correcciones. Los resultados del caso coinciden con los esperados del README de datos: límites de Fase I con R-barra ≈ 3,06 antes de excluir (obtenido: 3,056), y 11 de 15 subgrupos con señal en Fase II (subgrupos 26, 28, 30 a 36, 38 y 39).

**Sobre el caso sintético.**

3. Un proceso con Cpk de 1,24 puede parecer aceptable y sin embargo desplazarse 1,5 sigmas sin que se observe ni una unidad fuera de especificación: el gráfico de control lo detecta en el primer subgrupo y el conteo no. Es el hallazgo central de ingeniería del ejemplo.
4. La estimación de capacidad con 120 datos tiene una incertidumbre amplia (IC 95 % de Cpk de 1,04 a 1,43): el veredicto «marginal» no distingue entre un proceso adecuado y uno apenas capaz. Hay que reportar el intervalo junto con el índice.
5. El diseño del gráfico es una decisión de compromiso cuantificable: con h = 8 h y solo WE1, un cambio de 1σ tarda 36 horas; con reglas de zona baja a 21 horas pero el ARL0 cae de 370 a 91 muestras. No hay un diseño óptimo sin los costos de la empresa.

**Limitaciones del experimento y efecto sobre las conclusiones.**

6. **Los datos son sintéticos y normales por construcción.** Las pruebas de normalidad y la sigma de corto y largo plazo coinciden por diseño. Un proceso real tendrá colas, derivas, mediciones redondeadas y subgrupos mal formados que este ejemplo no reproduce; por eso las cifras **no se pueden extrapolar** a ninguna empresa.
7. **La causa asignable es ficticia.** No se verificó en planta, así que la discusión de las propuestas 1 a 3 es ilustrativa. En el caso real, excluir un punto sin verificar su causa sesgaría los límites.
8. **Tamaño de la Fase I.** Con 24 subgrupos, los límites son estimaciones con error: el ARL0 real puede ser menor que el nominal de 370,4, como advierte el propio software. Con la sigma estimada con pocos subgrupos, las probabilidades de falsa alarma y de detección son aproximadas, y por la misma razón los intervalos de capacidad se calculan con 86,9 grados de libertad efectivos y no con 119 (sección 6.2).
9. **Independencia.** El rechazo marginal de Ljung-Box en datos independientes por construcción ilustra el riesgo de falsos positivos al aplicar varias pruebas (con 20 rezagos y n = 120 se esperan unos 0,79 rezagos fuera de banda solo por azar, según el software, y la simulación del revisor da una probabilidad de 0,52 de ver al menos uno; `docs/validacion.md`, H23). No permite concluir autocorrelación real, pero tampoco ignorar el resultado sin mirar la ACF, y la serie aplanada mezcla variación dentro y entre subgrupos, de modo que la prueba es aproximada.
10. **Supuestos de diseño.** El intervalo h = 8 h, las especificaciones, el AQL y el LTPD son supuestos del equipo para el ejemplo. Operación continua de 24 horas sostenida. Los ARL suponen parámetros conocidos y datos normales e independientes.
11. **Fuera del alcance:** gráficos CUSUM y EWMA, que serían más apropiados para detectar los cambios de 0,5 sigmas que tardan 33 muestras aquí, y el análisis del sistema de medición, cuyo error de medición no está modelado.

**Sobre lo que falta.**

12. El diagnóstico de empresa, la evidencia de visita, los hallazgos reales y las propuestas finales **no están hechos** y están marcados en este informe. La rúbrica premia la articulación entre software, datos reales y juicio de ingeniería; este documento muestra que la herramienta está lista para esa articulación, no que se haya hecho.

> **POR COMPLETAR CON LA EMPRESA:** conclusiones del proceso real (estabilidad, capacidad, cumplimiento de especificaciones, comportamiento de no conformidades), con las limitaciones propias del muestreo realizado y su efecto en los resultados, y la discusión del impacto, la aplicabilidad y el aporte del proyecto para la empresa.

## 19. Recomendaciones

**Para el uso del software.**

1. Fijar los límites con al menos 20 a 25 subgrupos, justificar cada subgrupo racional por escrito y excluir puntos solo con causa asignable verificada en planta.
2. Interpretar siempre la capacidad con su intervalo de confianza y solo si el proceso es estable.
3. Leer las pruebas de supuestos en conjunto (valores p, ACF y gráficos) y no por un valor p aislado.
4. Dimensionar n y h con el módulo de diseño usando los costos propios, y no por costumbre.
5. Usar el muestreo de aceptación como complemento y no como sustituto del control del proceso.

**Para la siguiente fase del trabajo.**

6. Realizar la visita técnica con `docs/empresa/guia-visita.md`, recolectar datos con `docs/empresa/formato-recoleccion.md` (mínimo 25 subgrupos para Fase I y de 10 a 15 para Fase II), anonimizar según `docs/empresa/confidencialidad.md` y completar todos los bloques marcados de este informe.
7. Con datos reales, comprobar si el proceso cumple los supuestos; si no, considerar transformaciones o gráficos de memoria.
8. Antes de interpretar la capacidad, verificar el sistema de medición (resolución del instrumento frente a la tolerancia, `docs/empresa/plan-muestreo.md`, sección 2).

**Para el software.**

9. Extender a CUSUM y EWMA para detectar cambios pequeños, y a un análisis de autocorrelación sobre las medias de subgrupo.
10. Hecho el 11 de noviembre de 2026: el software se desplegó en Vercel (<https://cep-web.vercel.app>) y la prueba de aislamiento entre usuarios y las demás pruebas de extremo a extremo se repitieron contra producción (`docs/pruebas-e2e.md`).

## Referencias

Bartlett, M. S. (1946). On the theoretical specification and sampling properties of autocorrelated time-series. *Supplement to the Journal of the Royal Statistical Society, 8*(1), 27-41.

Bissell, A. F. (1990). How reliable is your capability index? *Journal of the Royal Statistical Society: Series C (Applied Statistics), 39*(3), 331-340.

Box, G. E. P., Jenkins, G. M., & Reinsel, G. C. (2008). *Time series analysis: Forecasting and control* (4.ª ed.). John Wiley & Sons.

Champ, C. W., & Woodall, W. H. (1987). Exact results for Shewhart control charts with supplementary runs rules. *Technometrics, 29*(4), 393-399.

Chan, L. K., Cheng, S. W., & Spiring, F. A. (1988). A new measure of process capability: Cpm. *Journal of Quality Technology, 20*(3), 162-175.

D'Agostino, R. B., & Stephens, M. A. (Eds.). (1986). *Goodness-of-fit techniques*. Marcel Dekker.

Harris, C. R., Millman, K. J., van der Walt, S. J., Gommers, R., Virtanen, P., Cournapeau, D., ... Oliphant, T. E. (2020). Array programming with NumPy. *Nature, 585*, 357-362.

Hyndman, R. J., & Fan, Y. (1996). Sample quantiles in statistical packages. *The American Statistician, 50*(4), 361-365.

Kane, V. E. (1986). Process capability indices. *Journal of Quality Technology, 18*(1), 41-52.

Ljung, G. M., & Box, G. E. P. (1978). On a measure of lack of fit in time series models. *Biometrika, 65*(2), 297-303.

Montgomery, D. C. (2009). *Introduction to statistical quality control* (6.ª ed.). John Wiley & Sons.

Nelson, L. S. (1984). The Shewhart control chart: Tests for special causes. *Journal of Quality Technology, 16*(4), 237-239.

Patnaik, P. B. (1950). The use of mean range as an estimator of variance in statistical tests. *Biometrika, 37*(1-2), 78-87.

Schilling, E. G., & Neubauer, D. V. (2009). *Acceptance sampling in quality control* (2.ª ed.). CRC Press.

Shapiro, S. S., & Wilk, M. B. (1965). An analysis of variance test for normality (complete samples). *Biometrika, 52*(3-4), 591-611.

Siegel, S., & Castellan, N. J. (1988). *Nonparametric statistics for the behavioral sciences* (2.ª ed.). McGraw-Hill.

Stephens, M. A. (1974). EDF statistics for goodness of fit and some comparisons. *Journal of the American Statistical Association, 69*(347), 730-737.

Sturges, H. A. (1926). The choice of a class interval. *Journal of the American Statistical Association, 21*(153), 65-66.

Tippett, L. H. C. (1925). On the extreme individuals and the range of samples taken from a normal population. *Biometrika, 17*(3-4), 364-387.

Tukey, J. W. (1977). *Exploratory data analysis*. Addison-Wesley.

Virtanen, P., Gommers, R., Oliphant, T. E., Haberland, M., Reddy, T., Cournapeau, D., ... SciPy 1.0 Contributors. (2020). SciPy 1.0: Fundamental algorithms for scientific computing in Python. *Nature Methods, 17*, 261-272.

Wald, A., & Wolfowitz, J. (1940). On a test whether two samples are from the same population. *The Annals of Mathematical Statistics, 11*(2), 147-162.

Western Electric Company. (1956). *Statistical quality control handbook*. Western Electric Company.

> **POR COMPLETAR: verificar contra el ejemplar del curso.** Las referencias se tomaron de `docs/fundamentos-estadisticos.md`, que las escribió de memoria sin acceso a las fuentes; este informe no inventa DOI ni páginas, y por eso **no lleva ningún DOI**. Antes de la entrega hay que confirmar contra las fuentes: (1) de Montgomery (2009), la edición que usa el curso (el informe y el código citan la 6.ª edición; una edición posterior cambia la numeración de capítulos, sobre todo la del muestreo de aceptación, que aquí figura como cap. 15) y que los capítulos citados (3, 5, 6, 7, 8, 10 y 15) correspondan a esa edición; los números de sección que aparecen en los docstrings del código se citaron de memoria y no se usan en este informe; (2) las páginas, volúmenes y números de los artículos de Bartlett, Bissell, Champ y Woodall, Chan et al., Hyndman y Fan, Kane, Ljung y Box, Nelson, Patnaik (el código cita 1949 y esta lista 1950), Shapiro y Wilk, Stephens, Sturges, Tippett y Wald y Wolfowitz; (3) las ediciones y editoriales de Box et al., D'Agostino y Stephens, Schilling y Neubauer, Siegel y Castellan, Tukey y Western Electric Company (la edición de 1956); (4) la lista completa de autores de Harris et al. (2020) y de Virtanen et al. (2020), abreviada aquí con puntos suspensivos; y (5) los DOI de todas las fuentes que los tengan.

---

## Anexos

### Anexo A. Salidas de la API que respaldan las cifras

Cada archivo contiene la ruta, la petición y la respuesta (carpeta `docs/informe/anexos/salidas/`).

| Archivo | Contenido | Se usa en |
|---|---|---|
| `parse_sintetico_fase1`, `parse_sintetico_fase2`, `parse_sintetico_p_n_variable`, `parse_sintetico_sucio`, `parse_sintetico_no_normal`, `parse_sintetico_autocorrelado`, `parse_sintetico_i_mr`, `parse_sintetico_c` | Lectura de los archivos | 8 |
| `resumen_fase1`, `resumen_sucio`, `resumen_atributos_p` | Estadística descriptiva y atípicos | 8, 10.3 |
| `fase1_xbar_r_inicial`, `fase1_xbar_r_depurada`, `fase1_xbar_r_depurada_we`, `fase1_xbar_s_depurada` | Fase I | 10.1 |
| `fase2_xbar_r`, `fase2_xbar_r_we`, `fase2_xbar_r_limites_sin_depurar` | Fase II | 10.2 |
| `recomendar_p`, `p_fase1_inicial`, `p_fase1_depurada`, `c_ejemplo`, `imr_ejemplo` | Atributos e individuales | 10.3, 10.4 |
| `supuestos_fase1_depurada`, `supuestos_fase1_con_subgrupo12`, `supuestos_no_normal`, `supuestos_autocorrelado` | Supuestos | 11 |
| `capacidad_fase1_depurada`, `capacidad_fase2_limites_fase1`, `capacidad_fase2_rbar` | Capacidad y fracción no conforme | 12, 13 |
| `arl_xbar_n3_h8`, `arl_xbar_n5_h8`, `arl_xbar_n10_h8`, `arl_xbar_n5_h8_we`, `comparar_disenos_1_5_sigma`, `arl_p_n100` | ARL y ATS | 14 |
| `muestreo_simple_diseno`, `muestreo_doble_evaluacion` | Muestreo de aceptación | 15 |

### Anexo B. Scripts y figuras

| Archivo | Función |
|---|---|
| `docs/informe/anexos/generar_salidas.py` | Llama a la API local y guarda las salidas; declara los supuestos del ejemplo en su docstring |
| `docs/informe/anexos/generar_figuras.py` | Dibuja las diez figuras en `docs/informe/figuras/` a partir de las salidas (requiere matplotlib en un entorno aparte) |

### Anexo C. Supuestos declarados del caso sintético

| Supuesto | Valor | Origen |
|---|---|---|
| Nominal, LIE, LSE | 500 g, 495 g, 505 g | README de `data/ejemplos/` |
| Intervalo de muestreo | 8 h (un subgrupo por turno), operación de 24 h | Supuesto del equipo, coherente con los tres turnos del README |
| Subgrupo 12 | +3 g en las cinco lecturas | Generador `data/generar_ejemplos.py` |
| Causa asignable «boquilla obstruida» | Ficticia | Supuesto del README de datos y del equipo |
| AQL, α, LTPD, β, lote | 1 %, 5 %, 6 %, 10 %, 2 000 | Supuesto del equipo |
| Plan doble comparado | n1 = 50, c1 = 0, r1 = 3, n2 = 50, c2 = 2 | Supuesto del equipo |
| Semilla de simulación de ARL | 12345 | Valor por defecto de la API |

### Anexo D. Evidencia de la visita (por completar)

> **POR COMPLETAR CON LA EMPRESA:** acta de visita firmada (escaneada en carpeta privada, no en el repositorio), fotos autorizadas, hoja de especificaciones anonimizada y registro de la transformación de anonimización. Formato de origen: `docs/empresa/guia-visita.md` («Evidencias que hay que traer» y «Acta de visita») y `docs/empresa/confidencialidad.md` («Procedimiento»).

### Anexo E. Plan de muestreo y formato de recolección (por completar)

> **POR COMPLETAR CON LA EMPRESA:** `docs/empresa/plan-muestreo.md` diligenciado con los datos reales y el archivo recolectado en el formato de `docs/empresa/formato-recoleccion.md` (anonimizado).

### Anexo F. Evidencia de ejecución del software

Las pruebas automáticas de la API se ejecutan con `cd api && .venv/bin/python -m pytest -q`; la última corrida entregó `953 passed, 1 skipped`. La evidencia de validación estadística independiente se documenta en `docs/validacion.md` y los fundamentos en `docs/fundamentos-estadisticos.md` (secciones 6.2 y 7.4). Las capturas de pantalla de cada módulo están en `docs/capturas/`.
