# Confidencialidad: cómo anonimizar nombres, productos y valores

Objetivo: usar datos reales de la empresa en el informe, el video y el software sin revelar su identidad ni información comercial sensible, sin cambiar la estadística. El enunciado lo permite (sección 5, punto 3).

## Principios

1. **Lo estadístico se conserva**: la forma de la distribución, la variación relativa y los patrones en el tiempo deben mantenerse. Lo que se cambia es la identificación.
2. **Un código por entidad**, siempre el mismo dentro del trabajo. Ejemplo: EMP-A, PROD-1, EST-3.
3. **Registro privado de la correspondencia**: el archivo que relaciona códigos con nombres reales se guarda fuera del repositorio y fuera de la entrega.
4. **Nada real en git**: los datos reales no se suben al repositorio. `data/` del proyecto contiene solo sintéticos.
5. **Declarar la anonimización** en el informe y en el video: qué se cambió y por qué.

## Nombres de empresa, personas y lugares

| Dato original | Reemplazo | Notas |
|---|---|---|
| Nombre de la empresa | EMP-A | Sin pistas (ciudad, sector muy específico) si no son necesarias |
| Nombre de operarios, supervisores, jefes | Cargo: "Operario de estación 2" | Nunca el nombre, ni en fotos |
| Nombre de proveedores | PROV-1, PROV-2 | |
| Dirección, planta, ciudad | "Planta de la región" o omitir | |
| Logotipos y marcas en fotos | Recortar o difuminar | Antes de guardar la foto |
| Correos y teléfonos | Eliminar | |

## Productos y marcas

| Dato original | Reemplazo |
|---|---|
| Nombre comercial | PROD-1 y una descripción genérica ("salsa de tomate, envase de 500 g") |
| Recetas y fórmulas | Omitir. Describir solo la propiedad controlada |
| Presentaciones con diseño propio | "Envase flexible de 500 g" |
| Nombre de clientes | CLI-1, CLI-2, o "cliente de retail" |

## Valores comerciales y de producción

Cambiar el valor sin cambiar la estadística:

- **Escala**: multiplicar todos los valores de una variable por una constante fija (por ejemplo 1,0 a 1,3 o por 0,01), y transformar LIE, LSE y nominal con la misma constante. La capacidad (Cp, Cpk) no cambia.
- **Desplazamiento**: sumar una constante a todos los valores y a LIE y LSE. Los límites de control y la capacidad no cambian. No usar cuando el valor absoluto es el resultado (por ejemplo, una concentración con límite legal).
- **Recodificar el tiempo**: cambiar la fecha base por una fecha ficticia, manteniendo los días de la semana si importan para el análisis de turnos.
- **Cantidades de producción**: redondear o reportar en porcentaje de la producción nominal.

Lo que no debe cambiarse:

- La proporción entre LIE, nominal y LSE (la capacidad depende de ella).
- Los puntos atípicos. Se conservan con su código, porque son parte del análisis (ID3).
- El orden de los subgrupos.
- Los valores faltantes y las observaciones de causa asignable, aunque se anonimicen.

## Procedimiento

1. Copiar el archivo original a una carpeta privada fuera del repositorio.
2. Renombrar la columna de identificación (si existe) y eliminar cualquier columna con nombres.
3. Aplicar la transformación de escala o desplazamiento, la misma a todas las filas y a las especificaciones.
4. Verificar que los estadísticos básicos de la versión anonimizada son coherentes con los originales: media y desviación escaladas, Cp y Cpk iguales.
5. Documentar en un registro privado: archivo original, transformación aplicada, constante usada, fecha.
6. Guardar la versión anonimizada en `data/` solo si es necesaria para la prueba, y marcar el nombre del archivo como anonimizado.

## Qué se publica en el informe y en el video

- Códigos, no nombres. Constantes de transformación solo si la discusión lo exige, y sin revelar el valor real.
- Gráficos con ejes en unidades relativas o escaladas cuando el valor absoluto es sensible.
- Declaración: "Los datos de la empresa fueron anonimizados según el procedimiento de confidencialidad; la estadística (límites relativos, índices de capacidad y patrones) se conserva."

## Lo que no se hace

- No inventar datos de la empresa y presentarlos como reales. Los sintéticos se marcan como sintéticos en el nombre del archivo y en el texto.
- No quitar las observaciones que incomodan al análisis.
- No dejar el registro privado dentro de la entrega ni dentro del repositorio.
