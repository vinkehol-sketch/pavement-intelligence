# Solución del Número Estructural (SN)

La ecuación AASHTO 1993 para pavimentos flexibles no permite despejar analíticamente el Número Estructural (SN). Por consiguiente, se debe recurrir a métodos iterativos para hallar su valor.

## Procedimiento Recomendado: Bisección

Debido a que la función que iguala ambos lados de la ecuación es continua y monótona creciente respecto al SN en el dominio positivo, el **método de bisección** es el más robusto para garantizar convergencia incondicional sin depender de derivadas.

1. **Definir la función objetivo $f(SN)$:**
   $f(SN) = \text{Lado Derecho de AASHTO} - \log_{10}(W_{18})$

   Lado Derecho:
   $Z_R S_0 + 9.36 \log_{10}(SN + 1) - 0.20 + \frac{\log_{10}\left[\frac{\Delta PSI}{2.7}\right]}{0.40 + \frac{1094}{(SN + 1)^{5.19}}} + 2.32 \log_{10}(M_r) - 8.07$

   La raíz de $f(SN) = 0$ será el $SN$ requerido.

2. **Límites Iniciales:**
   - $SN_{min} = 0.01$ (Límite físico estructural muy bajo).
   - $SN_{max} = 15.0$ (Límite extremo exagerado que excede cualquier diseño real).

3. **Tolerancia y Criterio de Convergencia:**
   - Criterio: $|f(SN)| < \epsilon$ o $(SN_{max} - SN_{min}) < \epsilon$
   - $\epsilon = 0.001$ pulgadas.
   - Límite máximo de iteraciones: 100.

4. **Validaciones en caso de no convergencia:**
   - Si tras 100 iteraciones no se alcanza la tolerancia, arrojar error: "Error de convergencia en cálculo de SN".
   - Verificar si $f(SN_{min}) \cdot f(SN_{max}) > 0$. Si ambos signos son iguales, el tráfico o las condiciones están fuera del rango matemático de la ecuación AASHTO, requiriendo revisión de las entradas (ej. ESAL = 0, Mr negativo).

## Manejo de Excepciones

- En el caso improbable de que se introduzca un ESAL extraordinariamente grande que requiera $SN > 15$, la validación inicial fallará. Para esto, debe haber una alerta que indique "El requerimiento estructural excede un SN de 15, la ecuación de AASHTO se encuentra fuera de su rango empírico válido".
