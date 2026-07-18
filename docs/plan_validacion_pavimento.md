# Plan de Validación - Módulo Pavimento Flexible

Este plan establece las reglas de negocio y validaciones sistémicas que Codex deberá programar para garantizar la integridad de los resultados geotécnicos y estructurales.

## Validaciones Críticas a Implementar

1. **Datos de Entrada**
   - $CBR \le 0$: Lanza excepción.
   - $CBR > 150$: Lanza advertencia `CBR_FUERA_DE_RANGO_TIPICO`.
   - $M_r \le 0$: Lanza excepción.
   - Tráfico ($ESAL \le 0$): Lanza excepción.
   - Confiabilidad $R$: Debe estar entre $50\%$ y $99.9\%$.
   - $\Delta PSI$: Debe ser $> 0$. (Serviciabilidad inicial $>$ Serviciabilidad final).

2. **Coeficientes Estructurales y de Drenaje**
   - $a_1, a_2, a_3$: Deben ser $\ge 0$. Advertencia si son $> 0.50$ (poco realista).
   - $m_2, m_3$: Deben estar entre $0.40$ y $1.40$. Fuera de esto, advertencia.

3. **Restricciones de Diseño por Capas**
   - Espesores ($D_1, D_2, D_3$) $< 0$: Lanza excepción.
   - $SN_{aportado} < SN_{requerido}$: Lanza advertencia crítica (El diseño falla).
   - Espesor adoptado $<$ Espesor mínimo normativo: Lanza advertencia (ej. "La carpeta asfáltica requiere 5 cm según tabla, se han adoptado 4 cm").

4. **Calidad de los Datos y Advertencias**
   - **Mr proveniente de correlación:** Alerta de `DISEÑO_CON_DATOS_ESTIMADOS`.
   - **Falta de información de drenaje:** Alerta.
   - **Uso de CBR no saturado:** Alerta indicando que no se está evaluando la condición crítica de diseño y el pavimento está en alto riesgo.
   - **Múltiples factores de crecimiento:** Advertencia si el ESAL importado ya contenía tasas de crecimiento y el usuario trata de aplicar un factor adicional en la interfaz de diseño.

## Indicador de Calidad del Resultado
El sistema etiquetará cada diseño generado con un nivel de calidad:
- `DISEÑO_PRELIMINAR`: Cuando hay valores estimados o pendientes de confirmación.
- `DISEÑO_ACADEMICO`: Cuando se fuerzan valores fuera de los rangos de la ABC para resolver una tarea universitaria.
- `DISEÑO_CON_DATOS_MEDIDOS`: Alta confianza (Triaxial, datos validados).
- `DISEÑO_CON_DATOS_ESTIMADOS`: Confianza media (Mr por CBR).
- `SIMULACION`: Cuando el usuario juega con los parámetros para encontrar sensibilidades sin estar asociado a un proyecto real.
