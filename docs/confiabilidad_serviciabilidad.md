# Confiabilidad y Serviciabilidad

## Confiabilidad (R) y Desviación Normal (Zr)

La Confiabilidad ($R$) es la probabilidad de que el pavimento alcance su vida útil sin fallar antes de tiempo. A cada nivel de $R$ le corresponde un valor estadístico $Z_R$.

- $R$ debe ingresarse como un porcentaje (ej. 90%).
- $Z_R$ será calculado algorítmicamente usando la función inversa de la distribución normal estándar.

**Valores típicos de R según el tráfico (AASHTO / Manual ABC):**
- Vías de alto tráfico/autopistas: 85% - 99.9%
- Vías principales: 80% - 99%
- Vías secundarias/locales: 50% - 80%

## Desviación Estándar Global ($S_0$)

Combina errores de predicción de tráfico y variaciones de desempeño:
- Pavimentos flexibles: $S_0$ típicamente varía entre **0.40 y 0.50**.
- Valor recomendado general si no hay estudios locales específicos: **0.45**.

## Serviciabilidad (PSI)

La Serviciabilidad refleja el nivel de confort del usuario.
- **Serviciabilidad Inicial ($p_i$):** Típicamente 4.2 para pavimentos flexibles.
- **Serviciabilidad Terminal ($p_t$):** Típicamente 2.5 o 3.0 para vías principales, 2.0 para locales.
- **Pérdida de Serviciabilidad ($\Delta PSI$):**
  $$ \Delta PSI = p_i - p_t $$

**Advertencia de Implementación:** Si el Manual de Diseño ABC no cuenta con una tabla estricta, el sistema debe permitir la selección manual de estos 4 parámetros (R, $S_0$, $p_i$, $p_t$) generando una advertencia si los valores salen de los rangos típicos.
