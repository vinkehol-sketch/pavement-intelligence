# Especificación Técnica para Implementación en Codex (Pavimento Flexible)

## 1. Alcance
Desarrollo del módulo de cálculo estructural de pavimentos flexibles según método AASHTO 1993, integrando caracterización geotécnica de subrasante, cálculo de número estructural requerido (SN) iterativo, y comprobación de diseño multicapa. **Fase:** MVP.

## 2. Estado de Implementación

### LISTO_PARA_IMPLEMENTAR
- Modelos de datos de subrasante y capas (sin valores por defecto automáticos).
- Validaciones de rango para entradas (ESAL > 0, espesores > 0).
- Ecuación AASHTO 1993 confirmada.
- Algoritmo de bisección para SN (tolerancia 0.001, 100 iteraciones).
- Cálculo de SN aportado sumando (a_i * m_i * D_i).
- Manejo de unidades (cálculo interno en psi/pulgadas, UI en MPa/cm).
- Trazabilidad (etiquetado de calidad de diseño).

### PENDIENTE_CONFIRMACION
- **Correlaciones CBR–Mr dudosas:** Rechazadas temporalmente por discontinuidades severas. Codex NO debe implementar una conversión automática de CBR a Mr sin que el usuario especifique explícitamente la ecuación a usar.
- **Espesores mínimos locales:** Las tablas bolivianas no se encuentran confirmadas, solo se implementará advertencia si el espesor es muy bajo según parámetros configurables.
- **Criterio estadístico para CBR de diseño:** No se permite promediar directamente.
- **Coeficientes estructurales:** No se asignarán valores automáticos (a1, a2, a3, m2, m3) por defecto; requieren ingreso explícito.

## 3. Modelos de Dominio (Entidades)
- GeotechSample
- HomogeneousSection
- FlexibleDesignProfile
- PavementLayer
- DesignAlternative

## 4. Enumeraciones
- CbrCondition: SATURADO, NO_SATURADO
- DrainageQuality: EXCELENTE, BUENO, REGULAR, POBRE, MUY_POBRE
- DesignQualityStatus: DISEÑO_PRELIMINAR, DISEÑO_ACADEMICO, DISEÑO_CON_DATOS_MEDIDOS, DISEÑO_CON_DATOS_ESTIMADOS, SIMULACION.
- MaterialType: ASPHALT_CONCRETE, GRANULAR_BASE, GRANULAR_SUBBASE.

## 5. Entradas / Salidas del Algoritmo Central
**Input:** W18 (ESAL), R (%), S0, pi, pt, Mr (psi).
**Output:** SN requerido.
**Algoritmo:** Bisección.

## 6. Ecuaciones Aprobadas (MVP)
1. **ZR**: Función Inversa Normal Estándar de R.
2. **Delta PSI**: pi - pt
3. **Ecuación AASHTO 1993**:
   log10(W18) = ZR * S0 + 9.36 * log10(SN + 1) - 0.20 + (log10(Delta PSI / 2.7)) / (0.40 + 1094 / (SN + 1)^5.19) + 2.32 * log10(Mr) - 8.07
   (El denominador 2.7 proviene de 4.2 - 1.5).
4. **SN Aportado**: SUM(a_i * m_i * D_i)

## 7. Validaciones del Algoritmo
- Error si Mr <= 0 o ESAL <= 0.
- Advertencia si SN_aportado < SN_requerido.

## 8. Pruebas Unitarias Requeridas
- 	est_sn_bisection_convergence (ESAL=5M, R=90%, Mr=10k -> SN=4.0421)
- 	est_layer_structural_contribution (a1=0.4, D1=5, a2=0.14, D2=6 -> SN_aportado=4.16)
- 	est_invalid_esal_throws_exception

## Requisitos de Materiales (Subbase y Base)
- **Subbase Granular (S0102):**
  - **Uso:** Capas de subbase bajo pavimentos asfálticos o de hormigón.
  - **Mecánica:** CBR >= 40% y Desgaste Los Ángeles <= 40%. (Si va bajo pavimento de hormigón: CBR >= 50%).
  - **Plasticidad:** Límite Líquido max 35, IP max 8.
  - **Banda:** TM-50a.
- **Base Granular Estabilizada Hidráulicamente:**
  - **Uso:** Capa de base granular convencional.
  - **Mecánica:** CBR >= 80%. Desgaste Los Ángeles <= 35%. Si va bajo tratamiento superficial doble (TSD): CBR >= 100%. Porcentaje de chancado >= 50% (70% para TSD).
  - **Plasticidad:** Límite Líquido max 35, IP max 6.
  - **Bandas:** TM-50b, TM-50c o TM-25.
- **Carpeta de Rodadura Granular (sin protección asfáltica):**
  - **Mecánica:** CBR >= 60% bajo inmersión (CBR >= 80% si no hay inmersión). Desgaste Los Ángeles <= 30%. Chancado >= 50%. IP entre 5 y 10.
  *(Fuente: S24-SCV-MA-3_SUELOS.pdf, Págs. 32-33)*

## Requisitos de Espesores Mínimos
- **Regla del NMAS (Capa Individual):** El espesor mínimo de una sola capa constructiva de mezcla asfáltica de granulometría densa debe ser >= 4 × NMAS (Tamaño Máximo Nominal del Agregado). Esto asegura la compactabilidad y previene rotura de agregados. *(Fuente: MANUAL DEL PAVIMENTO ASFALTICO_2025.pdf, Pág. 216)*
- **Ensanches Estructurales hacia Berma:** Cuando se diseña una berma como un ensanche estructural con capa asfáltica (sobre base de CBR 80%), este asfalto debe tener un **espesor mínimo de 0.05 m (5 cm)**. Este valor de 5 cm no es el mínimo universal del paquete asfáltico del carril, sino el de este elemento auxiliar. *(Fuente: S24-SCV-MA-4_DISEÑO DE CARRETERAS.pdf, Pág. 151)*