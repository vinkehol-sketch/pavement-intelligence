# Diseño por Capas (AASHTO 1993)

Una vez obtenido el Número Estructural Requerido ($SN_{req}$), el pavimento flexible se modela como un sistema multicapa: Carpeta asfáltica (superficie), Base, y Subbase.

## Relación Estructural

$$ SN_{aportado} = a_1 \cdot D_1 + a_2 \cdot m_2 \cdot D_2 + a_3 \cdot m_3 \cdot D_3 $$

Donde:
- $a_1, a_2, a_3$: Coeficientes estructurales por pulgada de material (adimensionales, 1/pulgada).
- $D_1, D_2, D_3$: Espesores adoptados para la carpeta asfáltica, base y subbase, respectivamente (en pulgadas).
- $m_2, m_3$: Coeficientes de drenaje para la base y subbase (adimensionales).

## Restricción de Diseño

Se debe cumplir siempre que:
$$ SN_{aportado} \ge SN_{req} $$

Y para asegurar protección individual por capas:
- $SN_1 = a_1 \cdot D_1 \ge SN_{req\_base}$
- $SN_1 + SN_2 \ge SN_{req\_subbase}$

## Tipología de Espesores

El módulo de diseño debe distinguir claramente entre:
1. **Espesor Matemático:** El valor exacto requerido (ej. 3.42 pulg).
2. **Espesor Mínimo Normativo:** Espesor dictado por tablas (ej. AASHTO estipula mínimo 2" de asfalto para cierto tráfico, la ABC puede estipular mínimo 5 cm).
3. **Espesor Constructivo Redondeado:** Espesor práctico ajustado a la realidad de obra (ej. múltiplos de 0.5 pulg, o redondeos en cm, ej. 4", o 10 cm).
4. **Espesor Adoptado:** Espesor final elegido por el ingeniero (que debe ser $\ge$ que los anteriores).

**Nota de Implementación (Codex):** Ningún coeficiente de capa $a_i$ o $m_i$ se debe asumir sin fuente. Si el usuario no lo provee, el campo se mostrará vacío o con valores por defecto locales etiquetados como `PENDIENTE_CONFIRMACION`.
