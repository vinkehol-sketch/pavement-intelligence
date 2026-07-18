# Revisión Documental y Metodología Geotécnica

## 1. Fuentes Revisadas

Durante la revisión documental para la implementación del módulo geotécnico de pavimentos flexibles, se analizaron las siguientes fuentes disponibles en el proyecto:

1. **Manual de Diseño de Carreteras ABC (Bolivia)**
   - **Documento:** `MI-SGC-002-v3.pdf`
   - **Autor/Institución:** Administradora Boliviana de Carreteras (ABC)
   - **Aplicabilidad al MVP:** Referencia principal normativa para variables de diseño, factores equivalentes de carga y recomendaciones de confiabilidad/serviciabilidad locales.
2. **Archivos Excel de Diseño Académico**
   - **Documentos:** `Excel pavimentos examen.xlsx`, `Excel Pavimentos Andrés Barrientos Pav Rígido (1).xlsx`, `2 PARCIAL PAVIMENTOS 1-2023.xlsx`
   - **Aplicabilidad al MVP:** Auditar fórmulas locales para correlación CBR a Módulo Resiliente, cálculo iterativo de SN y factores equivalentes de carga. De allí se extrajeron ecuaciones específicas para CBR y espectros de carga (ej. 8.2t, 14.8t, etc.).
3. **Guías de Laboratorio**
   - **Documento:** `Laboratorios Pavi-fusionado.pdf`
   - **Aplicabilidad al MVP:** Definición de la metodología de obtención de los valores de límites de Atterberg, humedad óptima, Proctor modificado y ensayo CBR. Estos datos dictan las columnas mínimas para la importación.

## 2. Metodología Recomendada para el MVP

El sistema implementará la metodología **AASHTO 1993** para el diseño de pavimentos flexibles. El enfoque metodológico será el siguiente:

### Caracterización de la Subrasante
1. **Recolección de Datos:** Se importarán datos geotécnicos puntuales extraídos de laboratorios. Se requiere, mínimamente, la ubicación (progresiva) y el CBR de diseño.
2. **Estimación del Módulo Resiliente (Mr):** Debido a que rara vez se mide directamente el Mr en el medio local (Bolivia), el sistema proveerá una correlación basada en el CBR. Sin embargo, el sistema requerirá etiquetar el origen de este dato como `MR_CORRELACIONADO` para dejar constancia de que no es un dato `MR_MEDIDO`.

### Diseño de la Estructura (AASHTO 1993)
1. **Cálculo de Ejes Equivalentes (ESALs):** Proporcionado por el módulo de ESAL.
2. **Determinación del Número Estructural Requerido (SN_req):** A través de la ecuación empírica AASHTO, integrando Confiabilidad (R), Serviciabilidad (ΔPSI) y el Módulo Resiliente de la subrasante (Mr).
3. **Diseño por Capas:** Asignación de coeficientes estructurales (a_i) y coeficientes de drenaje (m_i) para proponer una combinación de capas cuyo Número Estructural Aportado (SN_aportado) sea mayor o igual al requerido.

## 3. Limitaciones y Advertencias
- Las correlaciones de CBR a Mr introducen un margen de error; la confiabilidad del diseño se ve impactada por esto. El sistema generará una alerta de "Diseño con datos estimados" cuando aplique.
- No se deberán inventar parámetros de drenaje y serviciabilidad si el usuario no los proporciona explícitamente, pero se pueden proveer valores por defecto marcados como `PENDIENTE_CONFIRMACION` para el usuario, obligando a que sean confirmados.
