# Casos de referencia (`data/referencia/`)

Un archivo JSON por tipo de gráfico. Cada uno trae:

- `datos`: entrada mínima, pequeña para poder calcular a mano.
- `calculo`: pasos aritméticos escritos a mano, en orden.
- `esperado`: los valores que el software debe devolver (límites, promedios, puntos fuera de control).
- `fuente`: capítulo y ecuación de Montgomery, *Introduction to Statistical Quality Control*.

| Archivo | Gráfico | Resultado esperado |
|---|---|---|
| `xbar_r_n3.json` | X-barra y R, n = 3 | Límites X-barra 9,4425 y 14,5575; punto 4 fuera |
| `xbar_s_n3.json` | X-barra y S, n = 3 | Límites X-barra 9,5575 y 14,4425; punto 4 fuera |
| `i_mr.json` | Individuales y MR | Límites I 5,35 y 18,65; sin puntos fuera |
| `p.json` | p, n variable | Muestra 5 fuera (0,15 > 0,1437) |
| `np.json` | np, n = 100 | LCL 0, UCL 14,0485; muestra 5 fuera |
| `c.json` | c | UCL 10,4347, LCL 0; unidad 8 fuera |
| `u.json` | u, n variable | Muestra 4 fuera (2,6 > 2,5071) |

Las constantes de tabla (A2, A3, B4, D4, d2, E2) se toman del Apéndice VI de Montgomery. El validador-estadistico debe confirmarlas antes de usar estos casos como evidencia. No se transcriben tablas de datos de libros.
