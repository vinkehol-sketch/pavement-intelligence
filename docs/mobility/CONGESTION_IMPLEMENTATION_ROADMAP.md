# Hoja de ruta de la Estimación Operativa de Congestión

## Arquitectura objetivo

```text
FrameAnalysisResult
→ agregador temporal
→ CongestionInput
→ CongestionEngine
→ CongestionAssessment / CongestionAlert
→ adaptador de presentación
→ Streamlit
```

El dominio permanece independiente de Streamlit, OpenCV y estado de sesión.

## Fase 1 — Dominio neutral (completada)

Implementado y auditado en `946aaea`:

- contratos inmutables;
- configuración demostrativa validada;
- cuatro niveles;
- calentamiento de 10 segundos y 3 muestras;
- histéresis;
- candidato y confirmación HIGH de 15 segundos;
- recuperación de 5 segundos;
- alertas explicables no normativas;
- pausa y reset;
- 42 pruebas unitarias.

## Fase 2 — Agregador temporal aislado

Crear un componente neutral que transforme secuencias de `FrameAnalysisResult` en una muestra por intervalo. Debe calcular tiempo válido, flujo y acumulación con reglas documentadas, congelarse en pausa y reiniciarse por lote. No debe modificar `CongestionEngine` ni Streamlit.

## Fase 3 — Configuración por punto

Definir carga validada de `CongestionThresholds` por `monitoring_point_id`. Los defaults seguirán identificados como demostrativos hasta contar con calibración y validación de campo.

## Fase 4 — Adaptador de presentación

Crear un adaptador que convierta assessments y alertas a etiquetas, colores y textos. Solo esta capa conocerá necesidades visuales; el dominio no importará Streamlit.

## Fase 5 — Integración controlada

Conectar agregador, motor y adaptador al Centro de Monitoreo. Mantener separación entre métricas sintéticas y reales, respetar pausa/reset y no mezclar la alerta operativa con aprobación del aforo.

## Validación de campo pendiente

- calibrar umbrales por punto;
- documentar calidad y ventanas de las métricas;
- comparar estimaciones con observación autorizada;
- validar cámaras y escenarios reales;
- mantener ausencia de velocidad en km/h hasta disponer de calibración espacial.

En ninguna fase la estimación debe denominarse Nivel de Servicio, aprobar automáticamente un aforo o transferir resultados directamente a TPDA.
