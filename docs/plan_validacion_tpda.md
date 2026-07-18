# Plan de Validación de Calidad del TPDA

Para asegurar que los cálculos de TPDA sean correctos y reflejen la realidad, el sistema implementará validadores automáticos antes de permitir que un aforo pase al estado `VALIDADO`.

## Reglas de Control de Calidad

1. **Detección de Intervalos Ausentes o Brechas**
   * *Regla*: Al agrupar un aforo diario, la suma de las duraciones de los intervalos debe coincidir con el periodo reportado. (Ej. Un aforo de 24 horas debe tener intervalos que sumen 1440 minutos).
   * *Acción*: Si hay brechas, emitir alerta "Aforo incompleto. Se requiere factor horario o imputación de datos".

2. **Detección de Conteos Negativos**
   * *Regla*: `volume >= 0` para todas las categorías.
   * *Acción*: Error fatal, se rechaza la importación de la fila.

3. **Horarios Superpuestos**
   * *Regla*: Para una misma estación y sentido, los rangos `[start_time, end_time)` no pueden solaparse.
   * *Acción*: Si hay superposición, advertir sobre posible doble registro y solicitar confirmación para sobreescribir.

4. **Duplicados Absolutos**
   * *Regla*: Si todos los campos clave son idénticos, se asume duplicado.
   * *Acción*: Ignorar silenciosamente la duplicación.

5. **Aforos Demasiado Cortos**
   * *Regla*: Para estimar TPDA, se recomiendan aforos de al menos 24 horas continuas. 
   * *Acción*: Si el aforo total de una estación es menor a 12 horas, advertir: "El cálculo del TPDA a partir de aforos cortos tiene baja confiabilidad."

6. **Factores Fuera de Rango**
   * *Regla*: Factor Estacional ($f_e$) entre 0.5 y 2.0. Factor Hora Pico ($FHP$) entre 0.25 y 1.0.
   * *Acción*: Si el usuario introduce factores fuera de rango, requerir confirmación manual.

7. **Inconsistencia entre Sentidos**
   * *Regla*: El flujo de Ida no debe diferir del flujo de Vuelta por más de un 20% (Distribución direccional típica ronda el 50/50).
   * *Acción*: Advertencia: "Asimetría inusual en los flujos direccionales. Verifique factores locales (ej. puerto, frontera)."

8. **Auditoría de Hipótesis**
   * *Regla*: No se debe calcular un TPDA sin que el usuario confirme los factores utilizados. Si $f_e = 1.0$ (por defecto), debe mostrarse permanentemente que "Se ha asumido un factor estacional nulo".
