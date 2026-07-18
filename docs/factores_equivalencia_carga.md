# Factores de Equivalencia de Carga

El factor de equivalencia (EE o ESAL) transforma el daño estructural de cualquier eje vehicular al daño provocado por un eje de referencia o estándar.

## 1. Método por Ejes o Grupos de Ejes (Aprobado)
Es el método fundamental donde se calcula el EE eje por eje. Basado en la Ley de la Cuarta Potencia simplificada (AASHTO empírico), se utiliza la ecuación:

`EE = (P / P_std)^n`

Donde:
- `P`: Carga real o legal del eje o grupo de ejes (en toneladas).
- `P_std`: Carga estándar de referencia para ese grupo de ejes (en toneladas).
- `n`: Exponente empírico (generalmente entre 3.9 y 4.2).

**Valores de Referencia y Exponentes (Extraídos de las memorias de cálculo del proyecto `3er parcial.xlsx`):**
- **Eje Simple de Rueda Simple (Direccional)**: `P_std = 6.6 t`, `n = 4.0`
- **Eje Simple de Rueda Doble (Estándar)**: `P_std = 8.2 t`, `n = 4.0`
- **Eje Tándem (2 ejes)**: `P_std = 15.1 t`, `n = 4.0`
- **Eje Trídem (3 ejes)**: `P_std = 21.8 t`, `n = 3.9`

> [!IMPORTANT]
> **Sobre la Fórmula Académica General**
> Frecuentemente se cita `EE = (P / 8.2)^4.2`. Es importante notar que:
> 1. Solo aplica para **Ejes Simples de Rueda Doble**.
> 2. No debe ingresarse el Peso Bruto Vehicular en esta ecuación.
> 3. No aplica para grupos Tándem ni Trídem sin ajustes. Para estos grupos, se deben utilizar sus `P_std` correspondientes (15.1 t y 21.8 t).

## 2. Método por Peso Bruto Vehicular (Pendiente / No Recomendado para WIM)
Existen ecuaciones que regresionan el Factor Camión de todo el vehículo basándose únicamente en su Peso Bruto Total (P).
Ejemplos extraídos de literatura regional (Diapositivas académicas):
- Ligeros: `Factor Camión = (P / 7.77)^4.32`
- Medios: `Factor Camión = (P / 8.17)^4.32`
- Pesados: `Factor Camión = (P / 15.08)^4.14`
- Muy Pesados: `Factor Camión = (P / 22.98)^4.22`

En estas ecuaciones:
- `P` representa el **Peso Bruto Vehicular** total.
- Los denominadores (7.77, 8.17, etc.) **no son cargas de ejes**, sino pesos de calibración estadística para la flota analizada. Representan el peso bruto al cual un vehículo típico de esa categoría produce exactamente 1 ESAL.
- Debido a que dependen de la flota específica donde fueron calibradas, **no deben utilizarse** como base genérica para aforos WIM sin recalibración.
