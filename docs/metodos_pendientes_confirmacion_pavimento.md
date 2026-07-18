# Métodos y Parámetros Pendientes de Confirmación

Debido a que el Manual de Diseño de Carreteras de la ABC (`MI-SGC-002-v3.pdf`) no pudo ser auditado completamente en formato texto durante esta fase, los siguientes parámetros y decisiones arquitectónicas quedan catalogados como `PENDIENTE_CONFIRMACION`.

El ingeniero civil a cargo o un auditor local deberá ratificar estos puntos antes de la fase de implementación por Codex.

## 1. Valor Característico de la Subrasante por Tramo
- **Estado Actual:** El MVP sugiere percentil 87.5% o el valor mínimo como configuraciones, siguiendo AASHTO general.
- **Acción Pendiente:** Confirmar si la normativa ABC exige un método estadístico diferente para agrupar CBRs en un tramo homogéneo (ej. Promedio menos una desviación estándar, u otro percentil).

## 2. Ecuaciones de Módulo Resiliente para CBR > 20
- **Estado Actual:** Se extrajo de las planillas locales la fórmula $Mr = 4326 \cdot \ln(CBR) + 241$.
- **Acción Pendiente:** Esta fórmula da valores de Mr inconsistentes frente a la fórmula de rango medio (15 a 20). Debe confirmarse si existe un error tipográfico en la hoja de Excel académica original o si así lo exige un manual boliviano particular. De ser erróneo, se estandarizará usando $1500 \cdot CBR$ o coeficientes avalados internacionalmente.

## 3. Espesores Mínimos Normativos (Bolivia)
- **Estado Actual:** Se implementará la lógica para advertir si no se cumplen espesores mínimos.
- **Acción Pendiente:** Confirmar la tabla exacta de la ABC para espesores mínimos de carpeta asfáltica y base granular en función del ESAL de diseño, para integrarlos como reglas fijas en el sistema.

## 4. Tablas de Confiabilidad y Serviciabilidad Locales
- **Estado Actual:** Se propusieron rangos generales AASHTO (ej. R=90%, $p_i=4.2$, $p_t=2.5$).
- **Acción Pendiente:** Ratificar si la ABC estipula cuadros de confiabilidad obligatorios según clasificación de carreteras (Autopistas, Red Fundamental, Red Departamental).

## 5. Coeficientes Estructurales ($a_i$) y de Drenaje ($m_i$)
- **Estado Actual:** Se dejaron como inputs abiertos al ingeniero.
- **Acción Pendiente:** Confirmar si el MVP debería incluir un catálogo pre-cargado de materiales bolivianos con coeficientes $a_i$ estandarizados para que el usuario seleccione desde un menú desplegable en lugar de teclear el número a ciegas.
