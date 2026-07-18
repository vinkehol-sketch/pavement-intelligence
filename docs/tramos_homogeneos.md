# Tramos Homogéneos en Vías

El diseño de un pavimento asume propiedades representativas de la subrasante para un tramo dado. Dado que las propiedades fluctúan, es necesario dividir la vía en "tramos homogéneos".

## Criterios de Zonificación

El sistema debe soportar la partición de un proyecto vial con base en cambios significativos de:
1. **Tipo de Suelo:** Cambios bruscos en la clasificación AASHTO o SUCS.
2. **Capacidad de Soporte:** Variaciones importantes en el CBR o el Módulo Resiliente.
3. **Características Topográficas / Drenaje:** Zonas de corte, terraplén, variaciones bruscas en el nivel freático.
4. **Tránsito:** Cambios en el volumen de tránsito (intersecciones que alteran significativamente el ESAL).
5. **Sección Transversal:** Zonas con ensanches o diferentes requerimientos estructurales.

## Selección del Valor de Diseño de CBR (o Mr) para el Tramo

**Regla estricta:** No se permite utilizar automáticamente un "promedio simple" del CBR para todo un tramo sin advertencias. Las propiedades de la subrasante dictan el desempeño en sus puntos más débiles.

Métodos de selección de diseño soportados para configurar en el sistema (pendientes de confirmación definitiva por normativa local):
- `MINIMO`: Selecciona el valor más bajo registrado en el tramo. (Muy conservador).
- `PERCENTIL_X`: Selecciona un percentil específico (típicamente 87.5%, 85% o 90% dependiendo de la confiabilidad y la varianza). Método recomendado por AASHTO.
- `PROMEDIO_CONSERVADOR`: Promedio menos 1 o 2 desviaciones estándar, limitando su uso según la dispersión.
- `VALOR_CARACTERISTICO`: Método definido estrictamente por un manual (ej. AASHTO o ABC).
- `DEFINIDO_POR_NORMATIVA`: Permitir sobreescribir la lógica si la normativa boliviana indica otro percentil. (La ABC suele exigir percentiles o promedios en rangos estrechos de dispersión).

**Nota para implementación:** Dejar este criterio como un parámetro seleccionable por el ingeniero de pavimentos en el módulo, con el percentil 87.5% o el Valor Característico como predeterminado (marcado como `PENDIENTE_CONFIRMACION`).
