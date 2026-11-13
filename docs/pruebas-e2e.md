# Pruebas de extremo a extremo (Playwright)

Prueban Sigmalena (antes «CEP», Control estadístico de procesos) como lo vería un usuario nuevo: navegador real (Chromium), web Next.js, API FastAPI con **autenticación activa** y Supabase real. Todo con datos sintéticos de `data/ejemplos/`.

## Cómo correrlas

```bash
cd web
npm install
npx playwright install chromium        # una vez
npx playwright test                    # levanta API (8030) y web (3030), corre y los apaga
npm run test:e2e                       # equivalente
npx playwright show-report e2e/.report # informe HTML
```

Requisitos: `web/.env.local` con el proyecto de Supabase (`NEXT_PUBLIC_DEMO_MODE=0`, `NEXT_PUBLIC_API_MOCK=0`), `api/.env.local` con `SUPABASE_URL` y `api/.venv` creado. El registro por correo debe confirmarse solo en el proyecto de Supabase.

| Variable | Efecto |
|---|---|
| `BASE_URL` | URL de la web a probar. Si se define (p. ej. producción) **no** se levantan servidores locales. |
| `E2E_WEB_PORT`, `E2E_API_PORT` | Puertos locales (3030 y 8030 por defecto). |
| `E2E_WEB_DIR` | Carpeta desde donde se lanza `next dev`. Next 16 solo permite un `next dev` por carpeta; si ya hay uno en `web/`, usa una copia. |
| `E2E_KEEP=1` | No borra los estudios creados al final. |

Si ya hay un `next dev` corriendo en `web/` (por ejemplo en el puerto 3000), la suite no puede lanzar el suyo: copia `web/` (con `node_modules`, sin `.next`) a otra carpeta y corre `E2E_WEB_DIR=<copia> npx playwright test`; la copia solo aporta el código de la web, las capturas siguen saliendo en `docs/capturas/`.

Contra producción: `BASE_URL=https://<dominio> npx playwright test`.

### Usuarios y datos

- Los usuarios A y B se registran por la interfaz la primera vez y quedan en `web/e2e/.auth/state.json` (ignorado por git, con sus sesiones). Se reutilizan en las corridas siguientes; no se pueden borrar sin clave de servicio. Para crear otros, borra `web/e2e/.auth/`.
- **Invitado:** cada corrida crea exactamente un usuario anónimo de Supabase (`08-invitado`), que al final del recorrido se convierte en la cuenta `e2e-g-<sello>@example.com` (contraseña de las pruebas). Su sesión queda en `e2e/.auth/user-g.json` (y sus credenciales en `user-g.creds.json`) solo para que `99-limpieza` borre su estudio. Esos usuarios no se pueden borrar sin clave de servicio: se acumulan uno por corrida. Reutilizar la cuenta convertida entre corridas haría que la corrida siguiente no ejerciera el alta anónima, que es lo que se quiere probar; por eso no se reutiliza. Una opción razonable sería correr la parte anónima solo en las corridas completas y, en las rápidas, iniciar sesión con la última cuenta convertida (R9.2, R9.3 y R9.5 no dependen de que sea anónima).
- Todos los estudios se llaman `E2E ...` y `99-limpieza.spec.ts` los elimina al final.
- Cerrar sesión revoca todas las sesiones del usuario (alcance global de Supabase): por eso la sesión guardada se toma después del cierre.
- Los archivos están en orden numérico y comparten estado: corren en serie, de uno en uno.

## Archivos

| Archivo | Recorrido |
|---|---|
| `01-sesion.spec.ts` | 1. Registro, inicio, cierre; ruta protegida |
| `02-aislamiento.spec.ts` | 2. Usuario B no ve el estudio de A |
| `03-variables.spec.ts` | 3. Flujo completo por variables (incluye D1 en Supuestos y Capacidad) |
| `04-atributos.spec.ts` | 4. Atributos con tamaño variable, asistente y advertencia de reglas con límite truncado |
| `05-muestreo.spec.ts` | 5. Muestreo de aceptación |
| `06-sucio-y-errores.spec.ts` | 6. Archivo sucio (D2, D3, D4) y 7. Errores |
| `07-extras.spec.ts` | 8. Comparador de diseños, XLSX guardado, móvil 390 px, PDF del reporte, reglas en MR |
| `08-invitado.spec.ts` | 9. Modo invitado: entrada anónima, aviso, estudio, API real, cancelar cierre, conversión en cuenta, aislamiento |
| `09-manual.spec.ts` | 10. Ingreso manual: teclado, pegado con tabuladores y coma decimal, renombrar, borrador entre pestañas, Fase I, valores; atributos con `1.000,0` |
| `99-limpieza.spec.ts` | Borra estudios de prueba (usuarios A, B e invitado/convertido) |
| `helpers.ts`, `pdf.ts` | Utilidades; `pdf.ts` lee páginas y texto de un PDF de Chromium sin librerías externas |

Las pruebas comprueban valores calculados aparte: línea central y límites contra la media y R-barra del CSV y contra la respuesta de la API; Cp/Cpk/sigma contra R-barra/d2 sobre los subgrupos retenidos; ARL0, ARL1, ATS y carga de las 24 alternativas del comparador contra la normal estándar; plan de muestreo contra una búsqueda binomial propia; línea central de `sintetico_sucio` contra el CSV con comas decimales y sin los subgrupos retirados.

Valores de referencia de Capacidad con `sintetico_fase1`, subgrupo 12 excluido, LSL 495 y USL 505: n = 120, sigma dentro 1,2950 (R-barra de 24 subgrupos / 2,326), Cp 1,287, Cpk 1,238, veredicto marginal; IC Cp 1,096 a 1,478 y Cpk 1,044 a 1,431 (valores entregados con la corrección de grados de libertad efectivos; la prueba los fija con tolerancia de 0,005). **Corrección del documento anterior:** decía que Cpk debía ser cerca de 1,39 con sigma cerca de 1,2; eso era una estimación errónea (1,2 es la sigma del generador, no la de la muestra sin el subgrupo 12). Con los datos retenidos el valor correcto es 1,238.

Notas de ejecución: la web en modo desarrollo muestra el botón «N» de Next.js en las capturas; con una máquina muy cargada Supabase puede tardar más de 20 s en responder (los tiempos de espera de la configuración ya son holgados).

## Defectos de la primera pasada: estado

| Defecto | Estado | Prueba |
|---|---|---|
| D1. Capacidad usaba todos los subgrupos | **Verificado corregido.** Por defecto usa 24 de 25 subgrupos y la sigma de Fase I y lo dice; la casilla «Calcular con todos los subgrupos» restituye el 12. Supuestos: n = 120 por defecto y «Usar todas las observaciones» da 125 | R3.5, R3.6 |
| D2. Subgrupos incompletos sin salida | **Verificado corregido.** Región «Subgrupos incompletos (3)» (3, 7 y 11), retirar uno o todos con justificación obligatoria, quedan 17 con n = 5 y Variables calcula (16 tras retirar el atípico 9; línea central igual a la del CSV) | R6.1 |
| D3. Avisos de limpieza incompletos | **Verificado corregido.** «Avisos al leer el archivo (8)» con fecha d/m/a, espacios, turno vacío, N/D, celdas vacías y comas decimales; pasan a la bitácora guardada | R6.1 |
| D4. Motivo cortado en la tabla de atípicos | **Verificado corregido** (ninguna celda ni el contenedor se desbordan a 1440 px; el texto se ajusta en dos líneas) | R6.1 |
| D5. Textos de la API con punto decimal | **Verificado corregido** en interpretaciones de gráficos, supuestos, capacidad y advertencias de reglas (ninguna coincide con `\d\.\d`) | R3.2, R3.5, R3.6, R4.4, R7.3, R8.5 |

## Defectos nuevos

Ninguno funcional. Observaciones menores, no bloqueantes:

- En modo desarrollo aparece el indicador «N» de Next.js sobre las capturas (no ocurre en producción).
- Un contexto nuevo del navegador que abre `/login` con sesión activa en el estado compartido redirige a `/estudios`; es el comportamiento esperado, pero obliga a las pruebas a usar un contexto sin estado guardado para probar el inicio de sesión en móvil.

## Lista de verificación del enunciado (sección 9)

| Punto | Prueba que lo cubre | Resultado |
|---|---|---|
| Ejecuta correctamente con datos de prueba y datos reales | R3.1-R3.8, R4, R5, R6, R8 con datos sintéticos (CSV y XLSX) | Aprobado con datos sintéticos. **Datos reales: no probado** (no hay archivos reales en el repositorio) |
| Gráficos con límites, línea central, puntos fuera de control y señales | R3.2 (LC, LCS, LCI contra el CSV), R3.4 (11 de 15), R4.2 (muestras 8 y 20), R4.4 y R8.5 (reglas y advertencias) | Aprobado |
| Se diferencia explícitamente Fase I y Fase II | R3.2 («FASE I — límites de prueba»), R3.4 («FASE II — límites congelados», sin recalcular ni excluir), R7.2 | Aprobado |
| Cp, Cpk, Cpl, Cpu y fracción no conforme, con interpretación | R3.6 (valores contra el CSV: Cp 1,287, Cpk 1,238, marginal; intervalos; tabla de fracción no conforme; interpretación sin punto decimal), R7.3 | Aprobado (D1 corregido) |
| ARL0, ARL1 y ATS conectados con muestreo y carga muestral | R3.7 (ARL0 370,4; ARL1 1,57 en 1,5 sigma), R8.1 (comparador de 24 diseños: ARL, ATS, carga u/h contra cálculo propio) | Aprobado, incluido el comparador |
| Diseño y aplicación de planes de muestreo | R5.1-R5.3 | Aprobado |
| El informe contiene diagnóstico, alcance, resultados, propuestas, conclusiones y anexos | No es software: no cubierto por E2E (el reporte de la aplicación sí: R3.8, R8.4) | No aplica a esta prueba |
| El manual permite instalar, cargar datos y usar el programa | No cubierto; `docs/capturas/` (17 imágenes) es su insumo | No aplica a esta prueba |
| El video comunica el valor empresarial | No cubierto | No aplica a esta prueba |

## Recorridos nuevos (marca Sigmalena)

- R1.1 comprueba ahora `heading` «Sigmalena» en `/login`.
- R9.1-R9.5 (invitado): cabecera «Invitado» y aviso «Crear cuenta para conservar mis datos» que persiste al recargar; estudio y carga de `sintetico_fase1` con la sesión anónima y gráfico cuya línea central y límites coinciden con la API y con el CSV; cancelar el cierre de sesión mantiene sesión y datos; el formulario de conversión valida correo y contraseña, y al convertir el estudio sigue ahí (también tras recargar, con su conjunto de datos), aparece el correo y desaparece el aviso; el usuario A no ve el estudio ni lo abre por URL.
- R10.1-R10.3 (manual): escritura con Tab y Enter, pegado de un bloque 14 x 7 (crea 5 filas y una columna), renombrar columna, borrador intacto al cambiar de pestaña; «Usar estos datos», aviso de coma decimal, guardado como Fase I y límites X-barra calculados aparte (media, R-barra, 0,577 R-barra); en atributos, `1.000,0` se lee como 1000 con su aviso de separador de miles y p-barra = suma de defectuosos / suma de inspeccionados.
- Capturas nuevas: `14-invitado.png`, `15-ingreso-manual.png`. El pegado se simula con un `ClipboardEvent` real con `DataTransfer` (no con el portapapeles del sistema).

## Cobertura adicional

- R8.2: `sintetico_fase1.xlsx` cargado, guardado, listado con su nombre de archivo y graficado; la línea central coincide con la del CSV.
- R8.3: flujo principal con 390 px (inicio de sesión, estudio, carga, gráficos, excluir con causa, capacidad, reporte) sin desborde horizontal de la página.
- R8.4: `page.pdf` del reporte: al menos 2 páginas, contiene el título del estudio y «Tabla 1», y no contiene los botones.
- R8.5 y R4.4: reglas de racha; en MR solo se evalúa el punto fuera de límites y en p con LCI truncado se evalúan WE1 y WE4, con las demás listadas como no evaluadas.

## Pendiente de probar

Datos reales; navegadores distintos de Chromium; Safari/iOS real (el móvil es emulación de Chromium).

Última corrida local completa (2026-11-13, tras el rediseño): **44 pasan y 2 se omiten** (R1.3 y R1.5, registro de A y B, porque ya existen). 

Contra producción se corrió el 2026-11-13 con `BASE_URL=https://cep-web.vercel.app`, ya con la marca y las funciones nuevas desplegadas: 44 pasan y 2 se omiten (R1.6 inicia la sesión de B cuando el usuario ya existe, porque la sesión guardada vale solo para el dominio en que se creó).
