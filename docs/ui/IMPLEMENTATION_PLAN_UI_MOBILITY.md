# Plan de Implementación de la Interfaz de Movilidad (Streamlit)

Este plan de implementación detalla la ruta de desarrollo para integrar las pantallas de **Monitoreo de Tráfico** y **Revisión de Placas OCR** en la aplicación Streamlit existente del proyecto Pavement Intelligence.

---

## 1. Orden de Implementación por Fases

La implementación se dividirá en 5 fases secuenciales para minimizar la regresión de características y asegurar pruebas robustas de cada capa:

```
+-------------------------------------------------------------------+
| FASE 1: Fundamentos y Datos Simulados                             |
| -> Modelos de presentación (LprReviewPresentationModel)           |
| -> Generador de datos sintéticos (tráfico y placas)               |
+-------------------------------------------------------------------+
                                  |
                                  v
+-------------------------------------------------------------------+
| FASE 2: Pantalla de Validación OCR                                |
| -> Creación de pages/ocr_plate_review.py                          |
| -> Tabla enmascarada, filtros y formulario lateral de edición     |
| -> Bitácora de auditoría y log de revelado                        |
+-------------------------------------------------------------------+
                                  |
                                  v
+-------------------------------------------------------------------+
| FASE 3: Dashboard de Monitoreo de Tránsito                        |
| -> Creación de pages/traffic_monitoring.py                        |
| -> Superposición OpenCV en st.image (vídeo simulado)              |
| -> Bento grid, KPI metrics y mini LPR card                        |
+-------------------------------------------------------------------+
                                  |
                                  v
+-------------------------------------------------------------------+
| FASE 4: Sincronización e Invalidación de Estados                  |
| -> Navegación st.navigation (pages/ en app.py)                    |
| -> Aislamiento de variables en st.session_state                   |
| -> Invalidación mutua ante modificaciones de aforo                |
+-------------------------------------------------------------------+
                                  |
                                  v
+-------------------------------------------------------------------+
| FASE 5: Verificación y Reportes                                   |
| -> Pruebas unitarias de adaptadores y lógica de aprobación        |
| -> Inclusión opcional de estadísticas OCR en reportes             |
+-------------------------------------------------------------------+
```

---

## 2. Detalle de las Fases de Desarrollo

### Fase 1: Fundamentos y Datos Simulados
* **Objetivo**: Proveer la infraestructura de datos e interfaces de estilo sin tocar el flujo YOLO real.
* **Acciones**:
  * Diseñar el modelo de presentación para la revisión OCR en `pavement_intelligence/domain/traffic/presentation.py`:
    * `OcrPlateReviewItem`: Representa un registro OCR que incluye `original_plate`, `corrected_plate`, `confidence`, `status`, `reviewer`, `reason` y el historial de auditoría.
  * Crear un simulador de tráfico y placas en `pavement_intelligence/services/traffic_simulator.py` que entregue una secuencia de fotogramas e información de placas con lecturas degradadas (ej. caracteres comodín `?`).
  * Escribir los estilos CSS del sistema de diseño en `pavement_intelligence/ui/utils/styles.py` para inyección.

### Fase 2: Pantalla de Validación OCR
* **Objetivo**: Implementar la interfaz interactiva de auditoría de placas.
* **Acciones**:
  * Programar `pavement_intelligence/ui/pages/ocr_plate_review.py`.
  * Inicializar el estado de sesión: `ocr_readings_raw` y `ocr_review_records`.
  * Renderizar los KPIs y el panel de filtros.
  * Implementar la tabla con `st.data_editor`. El campo `Lectura` debe enmascararse a nivel de servidor (ej. `***-4A7`), revelándose únicamente mediante el botón auditado.
  * Diseñar la columna de edición derecha con visualización del recorte de placa (aplicando Gaussian Blur en Python por seguridad).
  * Validar obligatoriedad: El botón de confirmación se habilitará sólo si se selecciona un motivo válido de corrección y se define un responsable.

### Fase 3: Dashboard de Monitoreo de Tránsito
* **Objetivo**: Crear el Centro de Monitoreo centralizando métricas operativas y transmisión de video simulada.
* **Acciones**:
  * Programar `pavement_intelligence/ui/pages/traffic_monitoring.py`.
  * Implementar el bucle de renderizado de video simulado usando `st.image`. Los recuadros de vehículos y la línea de aforo se dibujarán en el fotograma usando OpenCV.
  * Colocar los KPI cards (`st.metric`) de velocidad, flujo y ocupación.
  * Cargar la tarjeta resumen de LPR que lee en tiempo real el estado de `st.session_state["ocr_review_records"]`.

### Fase 4: Sincronización e Invalidación de Estados
* **Objetivo**: Configurar la navegación e integrar la sesión completa.
* **Acciones**:
  * Modificar `src/pavement_intelligence/ui/app.py` para añadir las dos nuevas páginas a la lista de navegación.
  * Controlar la invalidación: Si un conteo aprobado es modificado en `pages/traffic_review.py`, se invalidará la aprobación del aforo (`traffic_review_approval = False`), pero el registro de placas OCR (`ocr_review_records`) permanecerá intacto para evitar pérdida de datos de auditoría.

### Fase 5: Verificación y Reportes
* **Objetivo**: Validar la fiabilidad y documentar auditorías.
* **Acciones**:
  * Desarrollar pruebas unitarias en `tests/unit/test_ocr_review.py` para validar la exclusión de estados de placa y las reglas del revisor.
  * Actualizar el generador de reportes PDF/Excel para incluir (de forma experimental y opcional) la tasa de placas válidas y la bitácora de auditoría de revelados.

---

## 3. Riesgos Técnicos y Mitigaciones

| Riesgo Técnico Detectado | Impacto en la Hackatón | Estrategia de Mitigación |
| :--- | :--- | :--- |
| **Inyección de CSS inestable** | Medio. Streamlit puede alterar sus clases internas de HTML y romper el diseño. | Usar clases CSS genéricas y limitarse a los contenedores nativos (`st.container(border=True)`). Evitar selectores de DOM complejos. |
| **Pérdida de rendimiento en video** | Alto. El bucle de dibujo OpenCV + Rerun de Streamlit puede saturar el CPU. | Ejecutar la simulación a una tasa controlada de refresco (ej: 5-10 FPS en la UI) y limitar la resolución del canvas a 960x540 píxeles. |
| **Falsos positivos de visualización** | Medio. Exponer placas reales desveladas en el navegador de forma insegura. | Aplicar el difuminado gaussiano (Gaussian Blur) a nivel de servidor Python. Nunca enviar la imagen nítida de la placa a menos que se haya disparado y auditado la acción de desvelado. |
| **Acoplamiento de datos** | Alto. Alterar variables de conteo al editar placas o viceversa. | Mantener claves de sesión totalmente separadas: `traffic_review_events` y `ocr_review_records`. Ninguna operación de OCR modificará categorías vehiculares ni direcciones. |
