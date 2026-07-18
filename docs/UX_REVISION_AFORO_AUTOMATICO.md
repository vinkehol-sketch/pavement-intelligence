# Diseño de Experiencia de Usuario (UX) — Revisión del Aforo Automático
**Proyecto:** Pavement Intelligence  
**Módulo UI:** `Revisión del Aforo Automático` (Página de Auditoría de Visión Artificial)  
**Estado:** Especificación de Diseño Funcional  
**Fecha:** 2026-07-17  

Este documento detalla el diseño de experiencia de usuario (UX) para el módulo de auditoría de los datos capturados por el contador YOLO. Su objetivo es proporcionar una interfaz limpia y eficiente para la hackatón vial, permitiendo que un ingeniero de tránsito revise, corrija y apruebe los datos de visión antes de enviarlos a los cálculos de diseño de pavimentos.

---

1. **Ingreso y Selección:** El usuario accede a la pantalla de **Revisión del Aforo Automático** y selecciona el video de tráfico procesado (ej. `car-detection.mp4`). El sistema le advierte que el conteo automático es estrictamente **preliminar** y la revisión manual es **obligatoria**.
2. **Registro de Configuración:** El sistema muestra y registra en el reporte la versión del modelo YOLO (ej: `yolov8n.pt`) y la posición de la línea virtual de conteo utilizada en la inferencia.
3. **Diagnóstico Rápido (WOW Factor):** Revisa de un vistazo las **Tarjetas Resumen** que comparan el total automático de la IA versus el total corregido acumulado, junto con el porcentaje de desviación.
4. **Identificación de Alertas (Umbral Configurable):** El usuario puede configurar en el panel lateral el *Umbral de Confianza de Alerta*, y la tabla etiquetará dinámicamente aquellos eventos de `⚠️ Baja Confianza` por debajo de dicho valor, además de marcar los camiones como `🚚 Camión no confirmado` (`truck`).
5. **Edición e Ingesta:**
   - Selecciona la categoría vial oficial de la ABC en el dropdown para los registros `truck` (ej. `C3` o `BUS`).
   - Cambia el estado de un evento de falso positivo a `Descartado`.
   - Hace clic en **Agregar Vehículo Omitido** para insertar vehículos omitidos por la cámara.
   - En cada edición, se recomienda ingresar una nota justificativa corta.
6. **Aprobación de Integridad:** El usuario debe validar y aprobar explícitamente los totales. Una vez revisados los registros en estado `Sin Revisar` o `Camión no confirmado`, se desbloquea el botón de aprobación.
7. **Envío al TPDA:** El usuario presiona **Aprobar y Enviar a Aforo y TPDA**, transfiriendo los datos limpios al módulo de tránsito. El resultado no es automáticamente válido para el diseño oficial de pavimentos sin firma y validación documental independiente.


---

## 2. Boceto Textual de la Pantalla (Wireframe Layout)

```
🛣️ Pavement Intelligence · Módulo de Auditoría de Tránsito
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[🎥 REVISIÓN DE AFORO AUTOMÁTICO]

  ┌─ 🎥 Evidencia de Video ────────────────────────────────────────────────────────┐
  │ [ Reproductor de Video con Bounding Boxes y Línea Virtual de Aforo ]           │
  │ Video: data/videos/samples/car-detection.mp4 (YOLOv8n.pt)                      │
  └────────────────────────────────────────────────────────────────────────────────┘

  ┌─ 📊 Tarjetas de Resumen (Comparación en Tiempo Real) ──────────────────────────┐
  │                                                                                │
  │   🤖 TOTAL AUTOMÁTICO     ✍️ TOTAL CORREGIDO      📉 DESVIACIÓN     🎯 ESTADO  │
  │        120 vehículos          125 vehículos          +4.17 %       Pendiente   │
  │                                                                                │
  └────────────────────────────────────────────────────────────────────────────────┘

  ┌─ 🔍 Panel de Filtros ──────────────────────────────────────────────────────────┐
  │  [ Filtro Categoría: Todos ]  [ Filtro Estado: Sin Revisar ▾ ]  [ Baja Confianza: [x] ] │
  └────────────────────────────────────────────────────────────────────────────────┘

  ┌─ 📋 Tabla de Eventos Individuales ─────────────────────────────────────────────┐
  │ ID  │ Track ID │ Clase IA │ Cat. Vial Confirmada ✎ │ Confianza │ Estado ✎    │ Acci. │
  ├─────┼──────────┼──────────┼────────────────────────┼───────────┼─────────────┼───────┤
  │ 001 │ 12       │ car      │ AUTO                   │ 92%       │ Aceptado    │ [✍️]  │
  │ 002 │ 15       │ truck    │ [ Seleccionar... ▾ ]   │ 48% (Bajo)│ Sin Revisar │ [✍️]  │
  │ 003 │ 19       │ car      │ AUTO                   │ 91%       │ Descartado  │ [✍️]  │
  │ 004 │ MN-01    │ (Manual) │ C3                     │ 100%      │ Agregado    │ [🗑️]  │
  └────────────────────────────────────────────────────────────────────────────────┘
  [➕ Agregar Vehículo Omitido]

  ┌─ ⚠️ Advertencias de Validación ────────────────────────────────────────────────┐
  │ ⚠️ Hay 1 vehículo tipo "Camión no confirmado" pendiente de clasificación.     │
  │ 📌 Se están utilizando datos sintéticos (SIMULADO) para demostración de flujo.│
  └────────────────────────────────────────────────────────────────────────────────┘

  [📂 APROBAR Y ENVIAR A AFORO Y TPDA] (Deshabilitado hasta resolver alertas)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 3. Estados de los Eventos

Para garantizar el ciclo de vida y auditoría de cada registro de tráfico, se definen los siguientes estados:

* **`sin_revisar` (Sin Revisar):** Estado por defecto para todas las detecciones automáticas de la IA. Se renderiza con un badge gris.
* **`aceptado` (Aceptado):** El operador validó que la detección visual y la categoría preliminar son correctas. Badge verde.
* **`corregido` (Corregido):** Se modificó la categoría vehicular (ej. de `truck` a `C3`) o se ajustó el sentido de circulación. Badge azul.
* **`descartado` (Descartado / Falso Positivo):** Se identificó como falso positivo (sombras, reflejos). No suma al conteo, pero se conserva en la base de datos por trazabilidad. Badge rojo.
* **`agregado_manualmente` (Agregado):** Vehículo que la IA omitió (punto ciego, oclusión) y fue ingresado por el operador. Badge naranja.
* **`requiere_revision` (Dudoso):** Registro marcado para revisión posterior o consulta con la jefatura de diseño. Badge amarillo.

---

## 4. Tabla de Campos del Contrato de Interfaz

| Campo UI | Columna Técnica | Editable | Control UI | Descripción / Validaciones |
| :--- | :--- | :---: | :--- | :--- |
| **ID Evento** | `event_id` | No | Texto | UUID simplificado o correlativo visual. |
| **Track ID** | `track_id` | No | Número | ID del tracker de la IA. Si es `-1` se muestra en rojo y no suma. |
| **Clase IA** | `visual_class` | No | Badge | Clase visual YOLO (`car`, `bus`, `truck`, `motorcycle`). |
| **Cat. Vial** | `corrected_category` | Sí | Selectbox | Mapeado a la lista oficial `CATEGORIAS_ABC` de la ABC Bolivia. |
| **Confianza** | `confidence` | No | Barra/Porcentaje | Confianza de la IA. Alertas si $c < 0.55$. |
| **Sentido** | `direction` | Sí | Selectbox | Sentido de circulación (`Ascendente` / `Descendente`). |
| **Estado** | `validation_status` | Sí | Selectbox | Estados del evento (`Aceptado`, `Descartado`, etc.). |
| **Justificación**| `correction_reason` | Sí | Cuadro Texto | Obligatorio si el estado es `Corregido` o `Descartado`. |
| **Auditor** | `reviewed_by` | No | Texto | Nombre de usuario de la sesión actual. |
| **Fecha/Hora** | `reviewed_at` | No | Timestamp | Fecha y hora del guardado de la corrección. |

---

## 5. Reglas de Corrección y Validación

* **Regla del Camión no Confirmado:** La clase visual `truck` de YOLO nunca debe auto-mapearse de forma predeterminada a un camión específico de la ABC (como `C2` o `C3`). Debe forzar al usuario a seleccionar la categoría en el dropdown y cambiar el estado del evento a `corregido`.
* **Conservación del Registro Original:** Al editar un registro, el campo `visual_class` y `automatic_category` permanecen inalterables. Los valores corregidos se guardan en `corrected_category` y `corrected_value` para garantizar auditorías de exactitud de la IA.
* **Rechazo de Track ID `-1`:** Cualquier detección que tenga `track_id == -1` (ruido o detección inestable de 1 solo frame) debe marcarse automáticamente como `Descartado` y no computarse en las estadísticas base.
* **Recomendación de Justificación:** Si el usuario descarta un vehículo o cambia su categoría, se le aconseja ingresar una justificación corta (ej. "Sombra de árbol contada como moto", "Camión mediano de 2 ejes") para garantizar la trazabilidad del estudio. Esta justificación se maneja como una recomendación de UX sugerida, no como un bloqueo rígido de caracteres.

---

## 6. Modal / Formulario para Agregar Vehículos Omitidos
Al presionar el botón `➕ Agregar Vehículo Omitido`, se despliega un formulario lateral (Sidebar) o modal con los siguientes campos:
- **Categoría Vehicular ABC:** Dropdown con las 10 categorías oficiales.
- **Sentido:** Dropdown (Ascendente/Descendente).
- **Hora Estimada de Paso:** Input de tiempo (HH:MM).
- **Justificación:** Cuadro de texto para explicar la omisión (ej. "Pasó camión C3 cubierto por otro vehículo en carril izquierdo").
Al guardar, se inserta una fila en la tabla con un ID manual autogenerado (ej. `MAN-001`) y estado `agregado_manualmente`.

---

## 7. Criterios para Habilitar "Aprobar y Enviar a TPDA"
El botón de envío al módulo de tránsito permanecerá **deshabilitado** (`disabled=True`) hasta que se cumplan las siguientes condiciones:
1. **Ningún camión sin confirmar:** Todos los eventos `truck` deben haber sido clasificados en una categoría ABC.
2. **Revisión del Umbral Configurado:** Todos los registros con confianza inferior al *Umbral de Confianza de Alerta* seleccionado en la interfaz por el usuario deben haber sido revisados y tener su estado actualizado (distinto de `Sin Revisar`).
3. **Validación y Aprobación de Totales:** El operador debe marcar explícitamente una casilla de verificación confirmando que ha revisado la tabla y aprueba los totales resultantes del conteo.
4. **Aprobación de datos sintéticos:** Si la fuente son los archivos de demostración, se debe marcar una casilla de verificación de entendimiento: *"Entiendo que estoy enviando datos simulados/sintéticos y que no son aptos para el diseño estructural final."*


---

## 8. Comportamiento Responsive (Escritorio vs. Celular)
* **Escritorio (Uso en Oficina / Notebook):** Visualización en pantalla dividida (Split Screen). A la izquierda el reproductor de video; a la derecha la tabla de revisión interactiva completa y las métricas de desviación.
* **Celular (Uso en Campo por Inspectores):** El reproductor de video se oculta en un acordeón colapsable. La tabla de eventos individuales se transforma en una lista de tarjetas (Cards) verticales de un solo evento con botones rápidos de acción directa (`Aceptar` 👍 / `Descartar` 👎 / `Editar` ✏️).

---

## 9. Estrategia de Integración de Session State

### Consumo de Datos:
* La pantalla lee la clave **`st.session_state.vision_events_raw`** que es producida al finalizar el procesamiento en `video_analysis.py`.

### Producción de Datos:
Al presionar el botón de aprobación, la pantalla escribe dos claves críticas en la sesión:
1. **`st.session_state.vision_events_reviewed`:** La lista completa de eventos con sus estados de auditoría (`aceptado`, `corregido`, `descartado`, `agregado_manualmente`).
2. **`st.session_state.traffic_counts_corrected`:** Diccionario de agregación final listo para el TPDA (ej: `{"AUTO": 650, "C2": 55, ...}`). Excluye las detecciones con estado `descartado`.

---

## 10. Versión Hackatón vs. Mejoras Posteriores

### Versión Mínima para la Hackatón (MVP):
- Formulario de edición simple integrado directamente en la tabla usando `st.data_editor`.
- Carga del CSV de aforo de 24 horas y visualización del video `car-detection.mp4`.
- Botón de aprobación directo para demostrar el flujo rápido frente al jurado.

### Mejoras Posteriores (Producción):
- **Evidencia Visual Interactiva:** Hacer clic en un evento de la tabla adelanta automáticamente el video al frame exacto (`frame_index`) donde cruzó la línea virtual para verificar visualmente el tipo de eje.
- **Asociación de OCR:** Mostrar la matrícula leída por OCR al lado de la clase para verificar la trazabilidad.
- **Sincronización en la Nube:** Guardar la sesión de auditoría en la base de datos SQLite para permitir revisiones concurrentes por múltiples ingenieros.
