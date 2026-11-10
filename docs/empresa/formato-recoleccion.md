# Formato de recolección de datos

Este formato es el que carga el software CEP. Si los datos llegan en otro formato, se pasan a este antes de cargarlos. La plantilla lista para llenar es `plantilla_recoleccion.xlsx` (una sola hoja `datos`, con los encabezados ya escritos).

## Reglas generales

- Una hoja de cálculo (XLSX) o un CSV por estudio. Una hoja, sin celdas combinadas ni filas de totales.
- Primera fila: encabezados. Sin tildes, sin espacios, en minúsculas.
- Una fila por subgrupo (variables) o por muestra (atributos), en el orden en que se produjeron.
- Fecha en formato `AAAA-MM-DD` (o fecha de Excel). Nunca `05/03/2026` escrito como texto.
- Decimal con punto. No usar separador de miles.
- Dejar vacía la celda que no se midió. No escribir `N/D`, `-` ni `0` para indicar ausencia.
- No borrar ni corregir valores atípicos en la hoja original. Si hay una causa conocida, anotarla en la columna `observacion` (opcional).

## Variables (X̄-R, X̄-S, I-MR)

| Columna | Contenido | Ejemplo |
|---|---|---|
| `fecha` | Fecha del subgrupo | 2026-03-02 |
| `turno` | Turno, sin tildes en el encabezado (el valor puede llevar tilde) | Mañana |
| `subgrupo` | Número o código del subgrupo | 1 |
| `x1` ... `xn` | Una columna por medida dentro del subgrupo | 500.31 |

- Subgrupos de tamaño constante: X̄-R y X̄-S requieren la misma cantidad de columnas `x` en todas las filas.
- Individuales (I-MR): una sola columna de valor, llamada `valor`. Sin columnas `x1`.

## Atributos (p, np, c, u)

| Gráfico | Columnas |
|---|---|
| p (n variable) | `fecha`, `turno`, `subgrupo`, `defectuosos`, `tamano_muestra` |
| np (n constante) | `fecha`, `turno`, `subgrupo`, `defectuosos`, `tamano_muestra` |
| c | `fecha`, `turno`, `subgrupo`, `defectos` |
| u (n variable) | `fecha`, `turno`, `subgrupo`, `defectos`, `unidades_inspeccion` |

- `defectuosos` es el número de unidades con al menos un defecto (p, np). `defectos` es el número de defectos contados (c, u).
- `tamano_muestra` y `unidades_inspeccion` son enteros positivos. Obligatorios en p, np y u.
- En np, `tamano_muestra` debe ser igual en todas las filas.

## Ejemplo de llenado (X̄-R con n = 3)

| fecha | turno | subgrupo | x1 | x2 | x3 |
|---|---|---|---|---|---|
| 2026-03-02 | Mañana | 1 | 499.8 | 500.4 | 501.1 |
| 2026-03-02 | Tarde | 2 | 498.9 | 500.0 | 499.7 |

## Errores frecuentes que el software reporta

| Situación | Aviso esperado |
|---|---|
| Encabezados con tilde o espacios | Se normalizan; se muestra el mapeo de columnas |
| Celda con coma decimal (`500,4`) | Se convierte, con aviso |
| Texto en una columna numérica (`N/D`) | Se trata como faltante, con aviso |
| Fila sin subgrupo o con subgrupo repetido | Se rechaza la fila, con aviso |
| Número de columnas `x` distinto entre filas | Error: no se puede construir X̄-R |

## Qué traer de la empresa

1. El archivo en el formato anterior, con al menos 25 subgrupos (variables) o 25 muestras (atributos) para Fase I.
2. Un bloque posterior de 10 a 15 subgrupos para Fase II, si existe.
3. Las especificaciones LIE y LSE del producto, por escrito.
4. Una nota de cambios: fechas de cambio de formato, de proveedor, de equipo o de operario, y cualquier causa asignable conocida.
