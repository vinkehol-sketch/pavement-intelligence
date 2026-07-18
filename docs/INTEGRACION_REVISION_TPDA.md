# Integración y Traspaso de Datos: Revisión Manual a Aforo y TPDA
**Proyecto:** Pavement Intelligence (Plataforma de Análisis de Tránsito y Diseño de Pavimentos)  
**Estado:** Especificación de Integración de Flujo Aprobada  
**Fecha:** 2026-07-17  

Este documento describe la integración de la pantalla **Revisión del Aforo Automático** en la navegación principal del sistema, y detalla el mecanismo de traspaso manual, explícito y reversible de los conteos auditados hacia el módulo **Aforo y TPDA**.

---

## 1. Navegación Principal y Orden del Flujo
El menú lateral de la aplicación Streamlit ha sido unificado utilizando el sistema de navegación nativo programático (`st.navigation`). Esto garantiza que la navegación de la hackatón siga el orden secuencial lógico de ingeniería vial:

1. **🏠 Inicio:** Panel de bienvenida, estado de módulos y visualización del avance del flujo.
2. **🎥 Análisis de video:** Procesamiento del video vial con YOLOv8 y ByteTrack.
3. **🔍 Revisión del aforo automático:** Auditoría visual, corrección de clases y descarte de falsos positivos de visión.
4. **📊 Aforo y TPDA:** Carga del conteo auditado, aplicación de factores temporales (ABC) y proyecciones futuras (AASHTO).
5. **⚖️ Pesaje:** Importación de cargas WIM para caracterización de daño por eje.
6. **🔢 ESAL:** Cálculo del número acumulado de ejes equivalentes de diseño (W18).
7. **🌍 Estudio de suelo:** Registro de muestras CBR y determinación de la resistencia de la subrasante.
8. **🛣️ Diseño de pavimento:** Determinación de espesores de capas usando el método AASHTO 93.
9. **📄 Reportes:** Consolidación de resultados y exportación técnica.

---

## 2. Indicadores de Estado Visuales en la Página de Inicio
La página de inicio (`home.py`) lee dinámicamente el estado de la sesión de Streamlit para guiar al usuario a través del flujo sin falsos positivos (no marca etapas completadas por variables vacías):

* **Visión Artificial:**
  - `🔴 Video no procesado`: Si no se ha ejecutado el pipeline de visión.
  - `🟢 Conteo disponible`: Al completarse el procesamiento.
* **Auditoría Manual:**
  - `⚪ Esperando video`: Si no hay detecciones.
  - `🟡 Revisión pendiente`: Conteo disponible pero no aprobado.
  - `🟢 Aforo revisado y aprobado`: Aprobado formalmente (`traffic_review_approved == True`).
* **Traspaso a TPDA:**
  - `⚪ Esperando aprobación`: Revisión no aprobada.
  - `🟡 Traspaso pendiente`: Aprobado pero no transferido.
  - `🟢 Datos enviados a TPDA`: Transferencia confirmada (`tpda_input_from_review` creado).
* **Diseño de Tránsito:**
  - `⚪ TPDA sin calcular`: Si no hay resultados de tránsito guardados.
  - `🟢 TPDA calculado`: Cálculo guardado en `tpda_result`.

---

## 3. Acción Manual y Flujo de Confirmación
El traspaso de información es un acto **intencional y explícito** del usuario. En la pantalla de revisión (`traffic_review.py`) se implementó una sección dedicada:

1. **Habilitación de Acción:** Solo se activa si el aforo fue aprobado (`traffic_review_approved == True`) y no hay discrepancias de datos.
2. **Casilla de Confirmación:** El usuario debe marcar: *"Confirmo que deseo transferir este lote de aforo aprobado al módulo de TPDA."*
3. **Botón de Traspaso:** Al presionarse, empaqueta los datos estructurados en una variable intermedia de la sesión.

---

## 4. Estructura de Transferencia (`st.session_state["tpda_input_from_review"]`)
Los datos se guardan bajo la clave `tpda_input_from_review` (dejando `tpda_result` aislado):

```python
{
    "counts_by_category": dict[str, int],  # Conteos finales corregidos
    "total": int,                          # Total corregido
    "source": str,                         # Archivo de video de origen
    "data_origin": "OBSERVADO_POR_VIDEO",  # Origen técnico
    "vision_batch": list[str],             # Lista de IDs de eventos incluidos
    "model_name": "yolov8n.pt",            # Modelo utilizado
    "line_y": 360,                         # Línea virtual de conteo
    "review_date": str,                    # ISO Datetime de revisión
    "reviewer": "Auditor Vial",            # Nombre del auditor
    "is_synthetic": bool,                  # Si proviene de datos sintéticos
    "warnings": list[str],                 # Advertencias activas
    "batch_hash": str                      # Huella digital del lote para invalidaciones
}
```

---

## 5. Recepción y Trazabilidad en `survey_tpda.py`
Cuando la pantalla **Aforo y TPDA** detecta la clave `tpda_input_from_review`:

1. **Selector de Fuente Inteligente:** Añade dinámicamente la opción: `"Lote auditado aprobado (Revisión manual)"` al selector radial y lo autoselecciona.
2. **Revisión y Edición Previa:** Los datos cargados se pre-completan en la tabla interactiva (`st.data_editor`), permitiendo al ingeniero modificarlos o rechazarlos libremente antes de calcular.
3. **Panel de Trazabilidad:** Muestra un acordeón con el origen del lote (video, revisor, modelo, línea, fecha y huella).
4. **Advertencia de Auditoría:** Muestra de forma destacada:  
   `⚠️ El conteo fue revisado manualmente antes de utilizarse en el cálculo de TPDA.`
5. **Propagación de Datos Sintéticos:** Si los datos provienen de simulación, la advertencia roja de datos sintéticos se muestra en la pantalla de TPDA y se guarda en el objeto `tpda_result` final.

---

## 6. Mecanismo de Invalidation (Reversibilidad)
Para evitar que se procesen cálculos desactualizados tras una corrección posterior:

* Si el usuario regresa a la pantalla de **Revisión del Aforo** y edita cualquier celda de la tabla después de haber aprobado, el sistema detecta que el conteo de la UI difiere de `st.session_state["traffic_counts_corrected"]`.
* **Acción de Invalidador:**
  - Configura `st.session_state["tpda_input_from_review"] = None`.
  - Configura `st.session_state["traffic_review_approved"] = False`.
  - Muestra una advertencia: *"La revisión de eventos ha sido modificada. El traspaso anterior ha sido invalidado. Vuelva a aprobar para habilitar el traspaso."*
* **Aislamiento de TPDA:** El resultado guardado en `st.session_state["tpda_result"]` **nunca es eliminado ni modificado de forma silenciosa**, protegiendo los diseños estructurales en curso. El sistema simplemente alerta que el TPDA actual está desactualizado respecto a la auditoría de visión.
