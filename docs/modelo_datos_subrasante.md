# Modelo de Datos Geotécnicos de Subrasante

El objetivo de este modelo es capturar la información mínima requerida para el diseño (MVP) y sentar las bases para la futura incorporación de datos avanzados (fase 2).

## 1. Datos Mínimos del MVP

Todo ensayo o muestra representativa de subrasante debe registrar:

- `tramo_vial` (String): Identificador del tramo al que pertenece.
- `progresiva` (Float): Ubicación longitudinal de la muestra (ej. km 12+500 se anota como 12500).
- `profundidad_muestra` (Float, m): Profundidad a la cual se extrajo la muestra.
- `descripcion_suelo` (String): Descripción visual o de campo.
- `humedad_natural` (Float, %): Contenido de agua natural.
- `granulometria` (JSON/Object): Porcentajes pasando tamices principales (ej. N°4, N°10, N°40, N°200).
- `limite_liquido` (Float, %): Límite Líquido (LL).
- `limite_plastico` (Float, %): Límite Plástico (LP).
- `indice_plasticidad` (Float, %): Índice de Plasticidad (IP = LL - LP).
- `clasificacion_sucs` (String): Clasificación según el Sistema Unificado de Clasificación de Suelos.
- `clasificacion_aashto` (String): Clasificación según el método AASHTO (ej. A-2-4).
- `indice_grupo` (Float): Índice de Grupo (IG).
- `densidad_seca_maxima` (Float, g/cm³ o kg/m³): Obtenida del ensayo Proctor.
- `humedad_optima` (Float, %): Humedad óptima de compactación.
- `tipo_ensayo_proctor` (Enum): `ESTANDAR` o `MODIFICADO`.
- `cbr` (Float, %): Valor de Relación de Soporte de California.
- `condicion_cbr` (Enum): `SATURADO`, `NO_SATURADO`. (En MVP siempre debe exigirse condición crítica, usualmente saturado).
- `porcentaje_compactacion` (Float, %): Nivel de compactación asociado al CBR (ej. 95% del Proctor Modificado).
- `expansion` (Float, %): Porcentaje de expansión durante el ensayo CBR.
- `nivel_freatico` (Float, m): Profundidad del nivel freático reportado.
- `condicion_drenaje` (Enum): `EXCELENTE`, `BUENO`, `REGULAR`, `POBRE`, `MUY_POBRE`.

## 2. Datos Avanzados Futuros

En versiones posteriores se añadirán:
- `modulo_resiliente_medido` (Float, MPa): Obtenido por ensayo triaxial cíclico.
- `modulo_resiliente_estimado` (Float, MPa): Si se estima mediante correlaciones distintas a las del software.
- `permeabilidad` (Float, cm/s): Coeficiente de permeabilidad k.
- `potencial_expansivo` (String): Clasificación del potencial expansivo.
- `colapsabilidad` (Boolean/Float).
- `materia_organica` (Float, %).
- `sales_sulfatos` (Float, ppm).
- `resistencia_corte` (Object): Parámetros de cohesión y ángulo de fricción.
- `consolidacion` (Object): Parámetros edométricos.
- `modulo_reaccion_k` (Float, MPa/m): Principalmente para pavimento rígido.
- `variacion_estacional_humedad` (Object): Perfil de humedad según época del año.

## 3. Metadatos del Ensayo

Para trazabilidad estricta, cada registro de muestra debe contener:
- `unidad`: Sistema métrico o inglés.
- `metodo_ensayo`: Norma utilizada (ej. ASTM D1557, AASHTO T180).
- `fuente`: Laboratorio emisor del informe.
- `fecha`: Fecha de ejecución del ensayo.
- `calidad`: Índice de confianza en el dato.
- `estado_revision`: `BORRADOR`, `REVISADO`, `APROBADO`.
- `origen_dato`: `MEDIDO`, `ESTIMADO`, `CORRELACIONADO`, `SIMULADO`.
