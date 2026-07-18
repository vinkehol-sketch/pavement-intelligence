# CBR y Módulo Resiliente (Mr)

El Módulo Resiliente (Mr) es el principal input para caracterizar la subrasante en AASHTO 1993. 

## 1. Correlaciones Disponibles

En base a los archivos auditados del medio académico local (`Excel pavimentos examen.xlsx` y `Excel Pavimentos Andrés Barrientos Pav Rígido (1).xlsx`), las fórmulas utilizadas localmente son:

Para **Mr en psi**:
1. Si `CBR < 7.2`: 
   **$Mr = 1500 \cdot CBR$**
2. Si `7.2 \le CBR \le 20`:
   **$Mr = 3500 \cdot CBR$** (Correlación empírica hallada en las hojas de cálculo locales)
3. Si `CBR > 20`:
   **$Mr = 4326 \cdot \ln(CBR) + 241$** (Correlación empírica hallada en las hojas de cálculo locales)

**Advertencia:** Existen múltiples ecuaciones empíricas (ej. CSIR, TRRL, Powell). Para el MVP, estas 3 ecuaciones cubren los rangos encontrados en la práctica local. Sin embargo, cualquier correlación debe validarse con el Manual de Diseño de la ABC (documento que no pudo ser procesado por texto y está `PENDIENTE_CONFIRMACION`).

**Conversión a MPa**:
$1 \text{ MPa} = 145.038 \text{ psi}$
$Mr (MPa) = \frac{Mr (psi)}{145.038}$

## 2. Tipología de Módulo Resiliente

No se debe convertir automáticamente el CBR a Mr sin notificar al usuario. En el sistema, la variable del módulo resiliente tendrá estados diferentes para garantizar trazabilidad:

- `MR_MEDIDO`: Ingresado directamente a partir de un ensayo triaxial.
- `MR_CORRELACIONADO`: Calculado automáticamente por el software usando una de las ecuaciones en base al CBR ingresado.
- `MR_ESTIMADO_POR_CLASIFICACION`: Cuando el CBR no está disponible y se estima un Mr a partir del tipo de suelo (ej. AASHTO A-6). Este método es de menor calidad y generará advertencias serias.
- `MR_INGRESADO_MANUALMENTE`: El ingeniero sobreescribe el valor bajo su propia responsabilidad.

## 3. Limitaciones
- La ecuación original del CSIR/AASHTO ($1500 \cdot CBR$) sólo es válida típicamente para suelos finos con $CBR \le 10$ o $12$.
- Las ecuaciones locales para CBR altos deben ser tomadas con precaución. Si un suelo tiene CBR de 80, la estimación del Mr tiene alta varianza.
- Las condiciones de humedad del CBR deben corresponder a la situación de servicio. Usualmente, se requiere usar CBR de suelo saturado.
