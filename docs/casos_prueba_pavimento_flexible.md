# Casos de Prueba - Pavimento Flexible (AASHTO 1993)

Estos casos de prueba han sido diseñados y auditados matemáticamente para verificar la implementación del algoritmo en Codex, sin depender de redondeos ambiguos de las planillas de Excel.

## 1. Conversión CBR a Módulo Resiliente
**Entradas:** CBR en %
**Procedimiento:** Aplicar ecuaciones locales.
- **Caso 1A:** `CBR = 5%`
  - $Mr = 1500 \cdot 5 = 7500$ psi
  - $Mr$ (MPa) = $7500 / 145.038 \approx 51.71$ MPa
  - **Tolerancia:** $\pm 1$ psi
- **Caso 1B:** `CBR = 15%`
  - $Mr = 3500 \cdot 15 = 52500$ psi
  - $Mr$ (MPa) = $52500 / 145.038 \approx 361.97$ MPa
- **Caso 1C:** `CBR = 30%`
  - $Mr = 4326 \cdot \ln(30) + 241 = 14953$ psi
  - $Mr$ (MPa) = $14953 / 145.038 \approx 103.10$ MPa
*(Nota: Extrañamente, en el Excel, la ecuación para $CBR>20$ da un valor MENOR que para $CBR=15$. Se requerirá validación estricta de la ecuación `4326*LN(CBR)+241` con la normativa ABC. Para la prueba, el valor matemático exacto debe coincidir, asumiendo la fórmula tal cual se definió).*

## 2. Cálculo del Número Estructural (SN)
**Entradas:**
- $W_{18} = 5,000,000$ (ESAL)
- $R = 90\%$ $\rightarrow Z_R = -1.282$
- $S_0 = 0.45$
- $\Delta PSI = 4.2 - 2.5 = 1.7$
- $M_r = 10,000$ psi

**Procedimiento:** Resolver $f(SN) = 0$ mediante bisección.
- Lado Derecho de la ecuación debe igualar a $\log_{10}(5,000,000) \approx 6.69897$.
- **Resultado Esperado:** $SN \approx 4.0421$ pulgadas.
- **Tolerancia:** $\pm 0.005$ pulgadas.

## 3. Verificación de SN Aportado y Diseño por Capas
**Entradas:**
- $SN_{req} = 4.0421$
- Capa 1 (Asfalto): $a_1 = 0.40$, $D_1 = 4.0$ pulg
- Capa 2 (Base): $a_2 = 0.14$, $m_2 = 1.0$, $D_2 = 6.0$ pulg
- Capa 3 (Subbase): $a_3 = 0.11$, $m_3 = 1.0$, $D_3 = 12.0$ pulg

**Procedimiento:**
$SN_{aportado} = (0.40 \cdot 4) + (0.14 \cdot 1.0 \cdot 6) + (0.11 \cdot 1.0 \cdot 12) = 1.6 + 0.84 + 1.32 = 3.76$

**Verificación (Caso Falla):**
- ¿$SN_{aportado} \ge SN_{req}$? No ($3.76 < 4.0421$).
- **Déficit Estructural:** $4.0421 - 3.76 = 0.2821$
- **Resultado Esperado:** El diseño Falla. Se genera advertencia de déficit estructural.

## 4. Verificación de SN Aportado y Diseño por Capas (Caso Éxito)
**Entradas:**
- $SN_{req} = 4.0421$
- Capa 1 (Asfalto): $a_1 = 0.40$, $D_1 = 5.0$ pulg
- Capa 2 (Base): $a_2 = 0.14$, $m_2 = 1.0$, $D_2 = 6.0$ pulg
- Capa 3 (Subbase): $a_3 = 0.11$, $m_3 = 1.0$, $D_3 = 12.0$ pulg

**Procedimiento:**
$SN_{aportado} = (0.40 \cdot 5) + (0.14 \cdot 1.0 \cdot 6) + (0.11 \cdot 1.0 \cdot 12) = 2.0 + 0.84 + 1.32 = 4.16$

**Verificación (Caso Éxito):**
- ¿$SN_{aportado} \ge SN_{req}$? Sí ($4.16 \ge 4.0421$).
- **Margen Estructural:** $4.16 - 4.0421 = 0.1179$
- **Resultado Esperado:** El diseño Pasa. No se generan advertencias.

## 5. Validaciones de Errores
- **Caso 4A:** $W_{18} = -100$. **Resultado:** Error de Validación (`ESAL_INVALIDO`).
- **Caso 4B:** $R = 105\%$. **Resultado:** Error de Validación (`CONFIABILIDAD_OUT_OF_RANGE`).
- **Caso 4C:** Espesor de Asfalto $D_1 = 1.0$ pulg, cuando el mínimo normativo es $2.0$ pulg. **Resultado:** Advertencia (`ESPESOR_MINIMO_NO_CUMPLIDO`).
- **Caso 4D:** $CBR = -5$. **Resultado:** Error de Validación (`CBR_INVALIDO`).
