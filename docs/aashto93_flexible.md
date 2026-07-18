# Método AASHTO 1993 - Pavimentos Flexibles

## 1. Ecuación General

La ecuación base de diseño para pavimentos flexibles según AASHTO 1993 es:

$$ \log_{10}(W_{18}) = Z_R \cdot S_0 + 9.36 \cdot \log_{10}(SN + 1) - 0.20 + \frac{\log_{10}\left[\frac{\Delta PSI}{4.2 - 1.5}\right]}{0.40 + \frac{1094}{(SN + 1)^{5.19}}} + 2.32 \cdot \log_{10}(M_r) - 8.07 $$

## 2. Variables de Diseño

| Variable | Símbolo | Unidad | Definición | Selección / Origen | Rango Típico |
|----------|---------|--------|------------|--------------------|--------------|
| **Tráfico** | $W_{18}$ | ESALs | Número de ejes equivalentes simples de 80 kN (18 kips) durante el período de diseño. | Calculado (Módulo ESAL) | $10^4$ a $10^8$ |
| **Confiabilidad** | $R$ | % | Probabilidad de que el pavimento cumpla su función durante su vida útil. | Ingreso Usuario | 50% a 99.9% |
| **Desviación Normal Estándar** | $Z_R$ | Adimensional | Valor estadístico de la distribución normal asociado a la confiabilidad. | Calculada a partir de R | -0.000 a -3.090 |
| **Desviación Estándar Global** | $S_0$ | Adimensional | Error estándar combinado en la predicción del tráfico y comportamiento. | Ingreso Usuario / Default | 0.40 - 0.50 |
| **Pérdida de Serviciabilidad** | $\Delta PSI$ | Adimensional | Diferencia entre la serviciabilidad inicial ($p_i$) y final ($p_t$). | Calculada ($p_i - p_t$) | 1.0 - 3.0 |
| **Módulo Resiliente** | $M_r$ | psi | Módulo resiliente de diseño de la subrasante. | Correlacionado/Ingresado | 1,500 a 40,000 psi |
| **Número Estructural** | $SN$ | pulg (adimensional) | Índice que representa la capacidad estructural total requerida del pavimento. | Calculado iterativamente | 1 a 10 |

## 3. Hipótesis y Observaciones
- La ecuación requiere resolverse para $SN$, el cual se encuentra a ambos lados de la ecuación implícitamente, por lo tanto requiere métodos iterativos.
- El $M_r$ en esta ecuación **debe estar en unidades de psi**, incluso si el proyecto se trabaja en el Sistema Internacional.
- Esta ecuación será únicamente documentada en el MVP técnico y no debe ser alterada. Su implementación algorítmica se detalla en el documento correspondiente a la Solución del SN.
