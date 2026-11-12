# Capturas de pantalla para el manual de usuario

Generadas por las pruebas E2E (`web/e2e/`) con `npx playwright test`, en escritorio (1440 px de ancho, página completa) y con **datos sintéticos** de `data/ejemplos/`. Se regeneran en cada corrida con los mismos nombres de archivo.

| Archivo | Qué muestra |
|---|---|
| `01-login.png` | Pantalla de acceso: pestañas Iniciar sesión / Crear cuenta, correo y contraseña. |
| `02-estudios.png` | Lista de estudios con una tarjeta (nombre, tipo, insignia de datos sintéticos, Abrir / Editar / Eliminar). |
| `03-datos-carga.png` | Módulo Datos con `sintetico_fase1.csv`: columnas detectadas, formato x1..x5, justificación del subgrupo, estadística descriptiva y resumen por subgrupo. |
| `03b-datos-sucio.png` | Carga de `sintetico_sucio.csv`: recuadro «Avisos al leer el archivo (8)» con las conversiones hechas, región «Subgrupos incompletos (3)» (subgrupos 3, 7 y 11) con «Retirar todos…» y «Retirar…» por subgrupo, y el valor atípico 5050 marcado para decidir. |
| `04-variables-fase1.png` | Gráficos X-barra y R en Fase I con límites de prueba, el subgrupo 12 con la señal WE1, parámetros, tabla de señales e interpretación. |
| `05-variables-excluir.png` | Fase I tras excluir el subgrupo 12 con su causa asignable: límites recalculados con 24 subgrupos, proceso bajo control, tabla de puntos excluidos. |
| `06-variables-fase2.png` | Fase II con `sintetico_fase2.csv` contra los límites congelados: 11 de 15 subgrupos con señal. |
| `07-atributos.png` | Gráfico p con tamaño de muestra variable (`sintetico_p_n_variable`): asistente de selección, límites escalonados, muestras 8 y 20 con señal. |
| `08-supuestos.png` | Validación de supuestos con límites congelados: recuadro «Datos que se usarán» (120 de 125 observaciones, de 24 de 25 subgrupos), casilla «Usar todas las observaciones», pruebas de normalidad e independencia, Q-Q, histograma y ACF. |
| `09-capacidad.png` | Capacidad con LSL 495 y USL 505 sobre los 24 subgrupos retenidos y la sigma de Fase I (n = 120; Cp 1,287, Cpk 1,238, capacidad marginal): recuadro «Datos que se usarán», casilla «Calcular con todos los subgrupos», índices con intervalos, histograma con especificaciones y fracción no conforme. |
| `10-diseno-arl.png` | Diseño de gráficos: ARL0, ATS0, carga muestral, tabla ARL1/ATS1 por desplazamiento, curvas y comparador de alternativas. |
| `10b-diseno-comparador.png` | Comparador de diseños con una lista de n, L y h no válida: mensaje de error junto al formulario; debajo sigue la tabla de 2 alternativas calculada antes (n = 4 y 8, L = 3, h = 1, desplazamiento de 2 sigma) con su gráfico de detección frente a carga. Complementa a `10-diseno-arl.png`. |
| `11-muestreo.png` | Muestreo de aceptación: plan simple diseñado (n, c, riesgos reales), curva OC, AOQ y ATI. |
| `12-reporte.png` | Reporte: lista de análisis guardados, botones de imprimir y exportar a Excel, y el documento con tablas y figuras numeradas. |
| `13-movil-variables.png` | Gráficos por variables en un teléfono (390 px de ancho, solo la parte visible, desplazada hasta el gráfico): el gráfico cabe en pantalla y la página no se desplaza en horizontal. |

Todas salvo `13-movil-variables.png` son de página completa a 1440 px; la móvil es la ventana de 390 x 844 px.
