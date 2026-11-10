# Plan de muestreo y gráfico de control

Este documento justifica el diseño del muestreo para la variable de calidad elegida. Sirve de base para el módulo 7 y para la defensa del criterio de ingeniería (ID3). Llenar cada sección con datos de la empresa o, si aún no hay, con el caso de ejemplo y marcarlo como tal.

## 1. Identificación

| Campo | Valor |
|---|---|
| Empresa (o código) | |
| Proceso y estación | |
| Producto y presentación | |
| Fecha de elaboración | |
| Elaborado por | |
| ¿Datos sintéticos? | Sí / No (si es sí, indicar el archivo de `data/ejemplos/`) |

## 2. Variable de calidad

- **Nombre y unidad**:
- **Tipo**: variable (medida continua) o atributo (conteo de defectuosos o defectos).
- **Especificación**: nominal, LIE, LSE. Fuente de la especificación:
- **Instrumento y resolución**: resolución frente a la tolerancia (regla práctica: resolución ≤ 10 % de la tolerancia total):
- **Justificación de la elección**: por qué esta variable y no otra (impacto en cliente, frecuencia de no conformidades, costo de medición):

## 3. Subgrupo racional

Criterio: dentro del subgrupo, la variación debe ser solo la causa común; entre subgrupos, la variación debe incluir las causas especiales que se quieren detectar.

- **Forma elegida**: por tiempo consecutivo, por producción consecutiva (unidades seguidas), por tamaño fijo, por turno.
- **Justificación**:
- **Qué variación queda dentro del subgrupo**:
- **Qué variación queda entre subgrupos**:

Criterios para decidir:

| Si... | Entonces... |
|---|---|
| Las medidas de un subgrupo se toman en el mismo instante o con el mismo ajuste | Es un subgrupo racional: se pueden comparar entre subgrupos |
| Se quiere detectar cambios entre turnos | Un subgrupo por turno, con medidas repartidas a lo largo del turno |
| Se quiere detectar drift de la máquina | Subgrupos pequeños y frecuentes, consecutivos |
| Las unidades de un subgrupo vienen de lotes distintos | Redefinir el subgrupo; mezclar lotes oculta la variación entre lotes |

## 4. Tamaño de subgrupo (n)

| Tipo de gráfico | Recomendación | Elegido | Justificación |
|---|---|---|---|
| X̄-R | n = 3 a 5 | | |
| X̄-S | n ≥ 10 | | |
| I-MR | n = 1 | | |
| p / np | n tal que n p̄ ≥ 5 (idealmente ≥ 10) | | |
| c / u | unidad de inspección fija o variable, con defectos esperados ≥ 1 por unidad | | |

Criterios para decidir n:

- Mayor n detecta cambios más pequeños pero cuesta más medir y retrasa la señal.
- Con n = 5 y un cambio de 1,5σ, la probabilidad de detección por punto es baja; esperar varios subgrupos o usar reglas de corrida.
- Si la medición es destructiva o costosa, preferir n pequeño con frecuencia alta.

## 5. Frecuencia de muestreo

- **Frecuencia elegida**:
- **Costo de muestrear** (tiempo de operario, costo de la prueba):
- **Velocidad del proceso** (cuántas unidades por hora, cuánto tarda en desajustarse según la operación):
- **Criterio**: el intervalo debe ser menor que el tiempo típico en que el proceso se desajusta. Si no se conoce, empezar con una muestra cada hora o cada cambio de turno y ajustar tras Fase I.

## 6. Número de subgrupos

- **Fase I (fijar límites)**: al menos 20 a 25 subgrupos. Con menos, los límites son inestables.
- **Fase II (monitoreo)**: el plan de muestreo continuo, sin fecha fija de fin.
- **Subgrupos previstos**:
- **Justificación**:

## 7. Plan resultante

| Concepto | Valor |
|---|---|
| Gráfico | |
| Subgrupos de Fase I | |
| n por subgrupo | |
| Frecuencia | |
| Responsable de la medición | |
| Responsable de la revisión de señales | |
| Acción ante una señal | |

Acción ante una señal (plantilla): detener la verificación, revisar el instrumento, revisar la causa documentada en el registro, excluir solo con causa asignable documentada, recalcular límites en Fase I.

## 8. Supuestos y verificación

- ¿La variable es aproximadamente normal? (Verificar con el módulo de supuestos.)
- ¿Los subgrupos son independientes? (Autocorrelación bajo control.)
- ¿El instrumento tiene calibración vigente?
- ¿Se conocen las causas asignables de los puntos atípicos de Fase I?

## 9. Referencias

- Montgomery, D. C. *Introduction to Statistical Quality Control*, caps. 5 a 7 (subgrupos racionales, diseño de gráficos, frecuencia de muestreo).
