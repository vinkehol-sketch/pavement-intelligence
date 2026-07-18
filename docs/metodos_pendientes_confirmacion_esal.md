# Riesgos Metodológicos y Aspectos por Confirmar

- **Ley de la Cuarta Potencia**: Aplicar fórmulas académicas exponenciales puras asume pavimentos idénticos. Si el diseño es avanzado (AASHTO-93), la fórmula iterativa con variables SN y Pt debe activarse.
- **Conversiones de Unidades**: Se observan mezclas de Kips, KiloNewtons, Toneladas métricas y Toneladas cortas en la bibliografía. El núcleo del software debe usar `KiloNewtons (kN)` para todo cálculo y las capas de presentación realizarán la conversión de visualización a Toneladas.
- **Duplicación de Crecimiento**: Peligro matemático al aplicar crecimiento al TPDA y luego al ESAL. El diseño debe separar conceptualmente los aforos de las proyecciones para evitar aplicar tasas de forma recursiva.
- **Cargas Legales vs Medidas**: El cálculo de sobrediseños a veces asume que todos los camiones viajan al máximo peso legal. Utilizar este supuesto sin alertar puede resultar en un pavimento sobredimensionado costoso.
