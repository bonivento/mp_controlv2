# Guion del video de marketing: Sigmalena

| Dato | Valor |
|---|---|
| Duración objetivo | 3 minutos 15 segundos (el enunciado pide entre 2 y 4 minutos) |
| Público | Jefes de producción, responsables de calidad e ingenieros de proceso de empresas manufactureras |
| Tono | Profesional, directo, sin jerga innecesaria; locución en español neutro |
| Formato de grabación | Pantalla del programa a 1920 x 1080, locución en off, música instrumental suave a bajo volumen |
| Caso que se muestra | Llenado de envases de 500 g de salsa. **Los datos son sintéticos** y el video lo declara en pantalla |

> **POR COMPLETAR CON LA EMPRESA:** si se aplica el software a una empresa real antes de grabar, sustituir el caso sintético de las escenas 4 a 6 por el de la empresa (anonimizado según `docs/empresa/confidencialidad.md`), con sus cifras reales, y cambiar el rótulo «datos sintéticos» por «datos anonimizados de una empresa manufacturera». Formatos de origen: `docs/empresa/formato-recoleccion.md` y `docs/empresa/guia-visita.md`. Mientras no exista empresa, el video debe mantener el rótulo de datos sintéticos.

> URL de producción para la escena final: <https://cep-web.vercel.app>. **POR COMPLETAR: contacto del equipo.**

## Mensaje central

Un proceso puede estar dentro de especificación y aun así estar fuera de control. Sigmalena dice cuándo el proceso cambió, qué tan capaz es y cuánta inspección hace falta para enterarse a tiempo, en un solo lugar y con el resultado explicado en español.

## Guion por escenas

| # | Tiempo | Lo que se ve | Locución | Texto en pantalla |
|---|---|---|---|---|
| 1 | 0:00 a 0:25 | Línea de llenado en imagen de archivo o animación sencilla. Una balanza marca 501,9 g y luego 500,2 g. Corte a una hoja de cálculo llena de columnas de pesos. | «Cada día una línea de producción genera cientos de mediciones. Casi nadie las mira a tiempo. Cuando un proceso se desajusta, se nota en el reclamo del cliente, no en el dato. Mientras tanto, hay una hoja de cálculo que nadie sabe cómo convertir en una decisión.» | «Los datos existen. La decisión llega tarde.» |
| 2 | 0:25 a 0:45 | Pantalla de acceso (`01-login`) y lista de estudios (`02-estudios`). Cursor entra y abre un estudio. | «Sigmalena convierte esas mediciones en control estadístico del proceso. Pruébala sin registrarte. Crea un estudio por proceso y carga tu archivo, o pega los datos desde Excel.» | «Sigmalena» y «Control estadístico de procesos» y «Pruébalo sin registrarte» |
| 3 | 0:45 a 1:15 | Carga del archivo `sintetico_fase1.csv`; tabla de columnas detectadas; selector de subgrupos; recuadro de justificación; resumen por subgrupo (`03-datos-carga`) y, con `sintetico_sucio.csv`, el recuadro de avisos de limpieza y los subgrupos incompletos (`03b-datos-sucio`). | «Sube tu archivo y el programa detecta las columnas y te avisa de cada corrección que hizo: comas decimales, celdas vacías, fechas. Tú defines el subgrupo racional y explicas por qué: el software no te deja avanzar sin esa justificación. Los valores atípicos se marcan, no se borran, y los subgrupos incompletos se retiran solo si escribes la razón. Todo queda en una bitácora.» | «Subgrupos racionales justificados» y «Avisos de limpieza y bitácora: nada se corrige en silencio» |
| 4 | 1:15 a 1:55 | Gráfico X-barra y R en Fase I. Un punto con rombo rojo (subgrupo 12). Clic en el punto, ventana de causa asignable, escribir «Boquilla obstruida». Los límites se recalculan. Botón «Congelar límites». (`04-variables-fase1`, `05-variables-excluir`) | «En Fase I el programa estima los límites con tus datos. Aquí aparece una señal: el subgrupo 12. Lo investigas, documentas la causa y lo excluyes. Los límites se recalculan sin él, y la exclusión queda registrada con su explicación. Cuando el proceso es estable, congelas los límites.» | «Fase I: estimar y depurar» y «Causa asignable obligatoria» |
| 5 | 1:55 a 2:20 | Cambio a la pestaña Fase II con el aviso «los límites no se recalculan». Llegan datos nuevos: 11 de 15 puntos quedan fuera de los límites. Se resaltan en rojo. (`06-variables-fase2`) | «En Fase II monitoreas datos nuevos contra los límites congelados. Aquí el proceso se desplazó, y el gráfico lo muestra de inmediato: 11 de 15 subgrupos con señal. Sin que ninguna unidad saliera todavía de especificación.» | «Fase II: monitorear, sin recalcular» y «11 de 15 subgrupos con señal (datos sintéticos)» |
| 6 | 2:20 a 2:50 | Módulo Capacidad: recuadro «Datos que se usarán» (24 de 25 subgrupos, sigma de Fase I), índices Cp y Cpk con intervalos de confianza y PPM esperadas (`09-capacidad`). Módulo Diseño: curva ARL contra desplazamiento y comparador de n y h (`10-diseno-arl`). | «¿El proceso es capaz? Cp, Cpk, Pp, Ppk y la fracción no conforme, con su intervalo de confianza calculado según cómo se estimó la variación, y una advertencia cuando el proceso no es estable o no se verificó la normalidad. Y para decidir cuánto muestrear, el módulo de diseño calcula cuántas muestras tarda el gráfico en detectar un cambio, en horas y en unidades inspeccionadas.» | «Cpk 1,24 antes del cambio y 0,84 después (datos sintéticos)» y «ARL y ATS para elegir n y frecuencia» |
| 7 | 2:50 a 3:05 | Módulo Reporte: lista de análisis, botones «Imprimir / guardar PDF» y «Exportar a Excel»; vista del documento con tablas y figuras numeradas (`12-reporte`). | «Guarda cada análisis y arma el reporte: tablas y figuras numeradas, conclusiones preliminares en español, listo para imprimir o llevar a Excel.» | «Reporte listo para decidir» |
| 8 | 3:05 a 3:15 | Fondo limpio con el logotipo de Sigmalena (isotipo propio, azul `#004A87` y naranja `#FF9400`). Aparecen la URL y el contacto. | «Sigmalena: del dato a la decisión. Pruébala con tu proceso, sin registrarte.» | «cep-web.vercel.app» y «POR COMPLETAR: contacto del equipo» |

El gráfico por atributos (`07-atributos`) puede insertarse como plano de apoyo en la escena 6 con una frase: «Y si cuentas defectuosos en vez de medir, el asistente te recomienda el gráfico p, np, c o u». Las cifras de las escenas 5 y 6 salen de `docs/informe/anexos/salidas/` (`fase2_xbar_r.json` y `capacidad_fase1_depurada.json` con `capacidad_fase2_limites_fase1.json`). Si el validador corrige un cálculo y cambian, regenerar con `generar_salidas.py` y actualizar el texto de pantalla.

## Beneficios que debe quedar claro que el espectador recibe

1. **Detecta antes.** Señales en el gráfico antes de que el reclamo llegue.
2. **Decide con respaldo.** Cada conclusión lleva su prueba, su intervalo y su advertencia.
3. **Distingue fases.** Fase I para fijar límites con rigor y Fase II para vigilar sin recalcularlos.
4. **Dimensiona el muestreo.** ARL y ATS traducen «cuántas unidades medir y cada cuánto» en horas hasta la señal.
5. **Deja evidencia.** Causas asignables, decisiones sobre atípicos, bitácora de limpieza y reporte, todo guardado por estudio.
6. **Es confiable.** Más de 890 pruebas automáticas y una revisión estadística independiente que recalculó los resultados por otro camino y cuyos errores se corrigieron (`docs/validacion.md`). Usar como texto de apoyo, sin cifras en pantalla.

## Lista de tomas de pantalla que hay que grabar

Las capturas fijas están en `docs/capturas/`; para el video se graba pantalla en movimiento de lo siguiente. Usar el estudio de ejemplo con los archivos `sintetico_fase1.csv` y `sintetico_fase2.csv`.

| Toma | Qué grabar | Escena |
|---|---|---|
| T1 | Pantalla de acceso: mostrar el botón «Continuar como invitado» y entrar con él (o iniciar sesión) hasta la lista de estudios | 2 |
| T2 | Crear estudio: nombre, característica, LSL 495, USL 505, objetivo 500, casilla «Datos sintéticos» marcada | 2 |
| T3 | Datos: elegir el archivo (y, en un par de segundos, la pestaña «Escribir o pegar datos» con un bloque pegado desde Excel), ver la tabla de columnas detectadas, elegir formato de varias columnas (x1 a x5), escribir la justificación del subgrupo | 3 |
| T4 | Resumen: estadística descriptiva y tabla por subgrupo; con `sintetico_sucio.csv`, mostrar el recuadro «Avisos al leer el archivo», la tabla de atípicos con la ventana «Decidir…» y la tarjeta «Subgrupos incompletos» con «Retirar todos…» y su justificación | 3 |
| T5 | Guardar el conjunto como Fase I | 3 |
| T6 | Variables, Fase I: gráfico X-barra y R, señal en el subgrupo 12, clic en el punto, escribir la causa, ver el recálculo, «Congelar límites» | 4 |
| T7 | Pasar a las reglas de Western Electric con el botón del mismo nombre y ver cómo cambian las señales | 5 |
| T8 | Guardar `sintetico_fase2.csv` como Fase II y abrir la pestaña Fase II: barra verde de límites congelados y puntos fuera | 5 |
| T9 | Supuestos: pulsar «Validar supuestos», recorrer tablas de pruebas, Q-Q, histograma y ACF | 6 |
| T10 | Capacidad: mostrar el recuadro «Datos que se usarán» (con la casilla «Calcular con todos los subgrupos» sin marcar), pulsar «Calcular capacidad», mostrar índices con intervalos y el cuadro de fracción no conforme. Antes, guardar los análisis de Variables (Fase I) y de Supuestos para que los menús lean «Según mis análisis guardados» | 6 |
| T10b | Atributos: con un estudio de atributos y `sintetico_p_n_variable.csv`, el asistente «Recomendar gráfico» y el gráfico p con límites escalonados | 6 |
| T11 | Diseño: parámetros n = 5, L = 3, h = 8, pulsar «Calcular»; luego «Comparar» con varios n y h | 6 |
| T12 | Muestreo: «Diseñar plan simple» con AQL 0,01 y LTPD 0,06, curva OC | 6 |
| T13 | Reporte: marcar análisis con «Incluir», pulsar «Imprimir / guardar PDF» y mostrar la vista previa; pulsar «Exportar a Excel» | 7 |
| T14 | Plano final con URL y contacto (gráfico fijo, sin grabación) | 8 |

## Notas de producción

- Ocultar el correo del usuario en la barra superior o usar la cuenta de demostración.
- Mantener visible el rótulo «datos sintéticos» en las escenas 3 a 6, también en las capturas exportadas.
- No mostrar logotipos ni nombres de empresas reales sin autorización (ver `docs/empresa/confidencialidad.md`).
- Subtítulos en español incrustados; la locución dura unos 3 minutos a ritmo tranquilo (cerca de 400 palabras).
- Revisar que ninguna cifra mostrada contradiga el informe técnico antes de exportar.
