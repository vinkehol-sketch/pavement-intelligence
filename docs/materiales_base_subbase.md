# Propiedades de Materiales de Base y Subbase

## Modelo de Datos de Materiales

Se requiere diseñar modelos para capturar las propiedades de los materiales a utilizar en la estructura.

### 1. Carpeta Asfáltica (Capa 1)
- `tipo_mezcla`: Ej. Concreto Asfáltico en Caliente.
- `modulo_elastico` (MPa o psi).
- `estabilidad_marshall` (lb o kg).
- `coeficiente_estructural` ($a_1$): Usualmente entre 0.35 y 0.44.
- `espesor_minimo` (pulgadas o cm).
- `observaciones` (String).

### 2. Base Granular (Capa 2)
- `cbr` (%): Típicamente $\ge 80\%$.
- `granulometria` (JSON).
- `limites_atterberg` (LL, IP).
- `desgaste_los_angeles` (%).
- `equivalente_arena` (%).
- `densidad` (g/cm³).
- `coeficiente_estructural` ($a_2$): Típicamente entre 0.10 y 0.14.
- `coeficiente_drenaje` ($m_2$).

### 3. Subbase Granular (Capa 3)
- `cbr` (%): Típicamente $\ge 30\%$ o $40\%$.
- `granulometria` (JSON).
- `plasticidad` (IP máximo).
- `coeficiente_estructural` ($a_3$): Típicamente entre 0.08 y 0.11.
- `coeficiente_drenaje` ($m_3$).

## Tipología de Valores

Para garantizar trazabilidad, el sistema debe registrar el origen del coeficiente $a_i$:
- `MEDIDO`: Obtenido indirectamente a partir de un Módulo Resiliente de laboratorio del material.
- `NORMATIVO`: Extraído directamente de una tabla oficial del Manual ABC (ej. $a_1 = 0.40$).
- `SELECCIONADO`: Escogido mediante ábaco o gráfico (AASHTO) basado en CBR o Módulo.
- `ESTIMADO`: Valor adoptado empíricamente por el usuario.
