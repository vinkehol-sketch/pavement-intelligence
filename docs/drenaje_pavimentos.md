# Drenaje en Pavimentos Flexibles

El drenaje es un factor crítico en el diseño AASHTO 1993, afectando la vida útil del pavimento a través de los coeficientes de drenaje ($m_2$ para la base y $m_3$ para la subbase).

## 1. Definición

No se debe confundir el drenaje superficial (cunetas, pendientes transversales) con el **coeficiente de drenaje estructural ($m_i$)**. Este último refleja la capacidad de una capa granular para drenar rápidamente el agua que se infiltra, considerando el tiempo durante el cual la estructura estará sometida a niveles de humedad próximos a la saturación.

## 2. Variables Principales

La selección de los valores $m_i$ se basa empíricamente en dos factores:
1. **Calidad del drenaje:** Tiempo que tarda la capa en drenar el agua (ej. 2 horas = Excelente, 1 mes = Muy Pobre).
2. **Tiempo de exposición a humedad:** Porcentaje de tiempo durante el año que la estructura del pavimento estará expuesta a niveles de humedad que se aproximan a la saturación (ej. < 1%, 1-5%, 5-25%, > 25%).

## 3. Rangos de Valores
- **Excelente:** $m_i$ entre 1.40 y 1.20
- **Bueno:** $m_i$ entre 1.25 y 1.00
- **Regular:** $m_i$ entre 1.15 y 0.80
- **Pobre:** $m_i$ entre 1.05 y 0.60
- **Muy Pobre:** $m_i$ entre 0.95 y 0.40

**Advertencia para el sistema:** El usuario debe proveer el valor $m_i$. Si no lo provee, el sistema sugerirá $m_i = 1.0$, indicando una condición "Regular" y exposición del 5-25% (condición neutral). Todo diseño sin información explícita de drenaje generará la advertencia: `Falta información de drenaje; asumiendo drenaje estándar m=1.0`.

## 4. Drenaje de la Subrasante
El diseño AASHTO 1993 *no* tiene un factor "$m_1$" o "$m_{subrasante}$". El drenaje de la subrasante impacta directamente reduciendo su **Módulo Resiliente ($M_r$)** en estado saturado, pero no utiliza un coeficiente $m$. Por esta razón, el ensayo CBR debe ser ejecutado en la condición crítica (saturado) o bajo el perfil de variación estacional esperado.
