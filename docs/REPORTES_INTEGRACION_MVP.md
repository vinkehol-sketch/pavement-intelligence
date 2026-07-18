# Integración final y reportes del MVP - Fase 6A

## Propósito y alcance

La Fase 6A consulta contratos existentes, valida continuidad por huellas y genera
un expediente demostrativo en JSON y PDF. No recalcula fórmulas ni corrige fases,
no produce costos, firma, aprobación normativa o recomendaciones constructivas.

> Este expediente integra resultados demostrativos generados por diferentes módulos del sistema.
>
> La validez técnica depende de la calidad, representatividad y aprobación profesional de los datos de tránsito, cargas, geotecnia, parámetros AASHTO y criterios de capas.
>
> El documento no constituye un diseño vial aprobado, una especificación constructiva ni una autorización para ejecutar obras.

## Contrato global y estados

`IntegratedDossier` es inmutable y serializable. Conserva identificador, datos
administrativos, fecha, versiones, modo, estado general, fases, huellas, vigentes,
desactualizadas, ausentes, bloqueos, advertencias, condición demostrativa, historial
limitado y huella de generación.

Las fases son revisión de aforo, ESAL observado/proyectado, CBR/MR, adopción de MR,
SN requerido y capas. Una fase ausente aparece como `NO_INICIADA`; también se
admiten `PENDIENTE`, `BLOQUEADA`, `VIGENTE`, `DESACTUALIZADA`,
`APROBADA_PARA_DEMOSTRACION` y `EXCLUIDA`. La existencia de un objeto no implica
aprobación: la revisión vehicular consulta su indicador explícito de aprobación.

## Continuidad y trazabilidad

Se comprueban las huellas 3A-3B, 4A-4B, 3B/4B-5A y 5A-5B. Los estados son
`CONTINUIDAD_CONFIRMADA`, `HUELLA_INCOMPATIBLE`,
`TRANSFERENCIA_DESACTUALIZADA`, `IDENTIFICADOR_INCOMPATIBLE` y `FASE_FALTANTE`.
Una incompatibilidad bloquea el expediente completo y nunca se corrige sola.

La matriz muestra fase, entrada/resultado, huella, dependencia, estado,
continuidad, bloqueos y advertencias. Las advertencias se conservan por fase, se
deduplican sólo dentro de la misma fase y se agrupan en tránsito, geotecnia,
AASHTO, capas, metodología y trazabilidad, con severidad informativa, precaución o
bloqueo.

## Modos

- `REPORTE_COMPLETO`: exige las siete fases presentes y continuas.
- `REPORTE_PARCIAL`: admite selección explícita y exige aceptar las ausencias.
- `RESUMEN_EJECUTIVO`: muestra resultados principales y limitaciones.
- `ANEXO_TRAZABILIDAD`: prioriza contratos, huellas, estados y versiones.

Los datos administrativos nunca se inventan. Proyecto, tramo y responsable son
obligatorios; ubicación, entidad, revisor y observaciones se declaran manualmente.

## JSON

El JSON contiene metadatos, fases seleccionadas, resultados permitidos, huellas,
últimos históricos opcionales, advertencias, bloqueos y versiones. No serializa
todo `st.session_state`. Un saneador elimina claves de rutas e impide exportar
patrones como `C:\Users\...`, `file://`, temporales o workspace.

## PDF

El PDF A4 contiene portada, datos administrativos, resumen, estado de fases,
secciones por fase, tránsito/ESAL, geotecnia, AASHTO, capas, matriz, advertencias,
limitaciones y anexo metodológico. Usa tablas con encabezados repetidos, saltos de
página controlados, caracteres españoles, unidades visibles y pie con versión y
número de página. No incluye rutas locales, firma, sello ni enlaces internos.

## Vigencia e históricos

La huella cubre datos administrativos, contenido de fases, modo, selección,
históricos, advertencias, formato y versión del generador. Cualquier cambio exige
regenerar. La sesión conserva un resumen del reporte anterior, no lo sobrescribe
silenciosamente. Por defecto no se anexan históricos; opcionalmente se incluye sólo
el último anterior disponible por fase.

## Limitaciones y pruebas

La fase no sustituye revisión profesional ni valida representatividad, normativa o
constructibilidad. Reportes oficiales, firma, costos, cantidades, presupuesto,
pavimento rígido, nube y base remota quedan pendientes.

Las pruebas cubren contrato, serialización, continuidad válida e incompatible,
fases faltantes, modos, aceptación parcial, JSON privado, PDF multipágina, texto
español, tablas extensas, saltos, advertencia obligatoria, vigencia e interfaz.
