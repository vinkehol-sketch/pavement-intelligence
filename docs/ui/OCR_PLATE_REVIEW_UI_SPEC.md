# Especificación Técnica: Revisión y Validación de Placas OCR (Streamlit)

Esta especificación detalla la implementación de la pantalla **Revisión y Validación de Placas OCR** (`pages/ocr_plate_review.py`) utilizando los componentes nativos de **Streamlit** y conservando las pautas visuales de Stitch.

---

## 1. Diseño del Layout y Distribución

La interfaz se estructura mediante una división de dos columnas principales para mantener la tabla de registros visible mientras se edita una lectura en el panel lateral.

```
+-------------------------------------------------------------------------+
| 🔍 Lecturas de Placas [EXPERIMENTAL]                [Revelar Placa Completa 🔓] |
| 🛈 Las lecturas requieren validación humana. Revise lecturas dudosas.    |
+-------------------------------------------------------------------------+
|   SECCIÓN CENTRAL (Ancho 8)            |   PANEL DE EDICIÓN (Ancho 4)   |
|                                        |                                |
|   +--------------------------------+   |   +------------------------+   |
|   | 📊 Resumen de Métricas (5 col)  |   |   | 📝 Revisión Manual     |   |
|   +--------------------------------+   |   +------------------------+   |
|   | 🔍 Filtros (Fecha, Estado,...)  |   |   | 🖼️ Fotograma & Recorte |   |
|   +--------------------------------+   |   +------------------------+   |
|   | 📋 Tabla de Lecturas           |   |   | 🔤 Corrección OCR      |   |
|   | (st.dataframe interactivo)     |   |   |   Original: GHK-4?2    |   |
|   |                                |   |   |   Corregida: [GHK-492] |   |
|   +--------------------------------+   |   +------------------------+   |
|                                        |   | 📋 Motivo & Revisor    |   |
|                                        |   +------------------------+   |
|                                        |   | 📜 Historial de Cambios|   |
|                                        |   +------------------------+   |
|                                        |   | [Confirmar] [Guardar]  |   |
|                                        |   | [Dudosa]   [Ilegible]  |   |
|                                        |   +------------------------+   |
+-------------------------------------------------------------------------+
```

---

## 2. Definición de Componentes en Streamlit

### A. Cabecera y Banner de Advertencia
* **Título**: `st.title("🔍 Lecturas de placas")` con una etiqueta "EXPERIMENTAL" gris al lado.
* **Fila de Control Superior**: Botón para "Exportar lecturas revisadas" (descarga un archivo JSON/CSV de `st.session_state["ocr_review_records"]`).
* **Banner Informativo**: `st.info("Las lecturas requieren validación humana. Por favor revise las lecturas marcadas como dudosas.")`

### B. Resumen de Métricas (Top Metrics)
Un bloque de 5 columnas `st.columns(5)` para KPIs principales:
1. `Placas Detectadas`: Conteo total.
2. `Lecturas Válidas`: Placas en estado `válida`.
3. `Dudosas`: Placas en estado `dudosa` (con borde izquierdo amarillo en CSS).
4. `Pendientes`: Placas en estado `pendiente`.
5. `Confianza Media OCR`: Porcentaje promedio de confianza de la lectura de placa.

### C. Panel de Filtros
Contenedor con bordes `st.container(border=True)` y cuatro columnas para filtrar la tabla de registros:
* **Fecha/Hora**: `st.date_input` y `st.time_input`.
* **Estado**: `st.selectbox` (Todos, Válida, Dudosa, Ilegible, Pendiente).
* **Tipo**: `st.selectbox` (Todos, Ligero, Pesado).
* **Confianza Mínima**: `st.selectbox` (0%, 50%, 80%).
* **Buscar ID Anonimizado**: `st.text_input` con lupa para filtrar por identificador de tracking (ej. `TRK-842`).

### D. Tabla Central de Lecturas
Implementada usando `st.dataframe` o `st.data_editor` para desplegar la información en formato de tabla de alta densidad:
* **Columnas**:
  * `Hora`: Marca de tiempo del cruce.
  * `IDs`: Referencia inmutable del tracker y detector (`L: L-93822`, `S: S-594`).
  * `Miniatura`: Imagen reducida del recorte. Para cumplir con la privacidad, la miniatura se renderiza por defecto en escala de grises y difuminada (blur de 1px).
  * `Lectura`: La placa se muestra enmascarada por defecto (ej: `***-4A7`) acompañada del icono 🔒.
  * `Confianza`: Porcentaje de certeza del motor OCR.
  * `Tipo`: Categoría de vehículo asociada (Ligero / Pesado).
  * `Sentido`: Dirección del flujo (N-S, S-N).
  * `Estado`: Badge de estado visual (`VÁLIDA` en verde, `DUDOSA` en amarillo, `ILEGIBLE` en rojo, `PENDIENTE` en gris).
* **Acción de Selección**: El operador puede seleccionar una fila para cargar sus datos en el panel lateral de edición.

### E. Panel Lateral de Revisión (Edición Manual)
Se implementa en la columna de la derecha (`col2`) y contiene:
1. **🖼️ Imágenes de Evidencia**:
   * Despliegue del fotograma original completo en miniatura (`st.image`).
   * Recorte ampliado de la placa (`st.image`).
2. **🔒 Control de Revelado (Privacidad)**:
   * Casilla de verificación o botón de activación: `Revelar placa completa`.
   * **Mecanismo de Auditoría**: Al activarse, el sistema ejecuta una función interna que registra el evento en la bitácora:
     ```python
     def log_unmask_event(event_id: str, auditor_username: str):
         log_entry = {
             "timestamp": datetime.now().isoformat(),
             "event_id": event_id,
             "auditor": auditor_username,
             "action": "PLACA_REVELADA"
         }
         st.session_state["ocr_audit_log"].append(log_entry)
     ```
3. **🔤 Corrección OCR**:
   * **Lectura Original OCR**: Bloque deshabilitado (`st.text_input` o `st.code`) que muestra el texto inmutable (ej: `GHK-4?2`) y confianza asociada.
   * **Lectura Corregida**: Campo de texto libre `st.text_input` inicializado con el valor sugerido del OCR para que el operador escriba la placa correcta.
4. **📋 Formulario de Justificación e Identidad**:
   * **Motivo de la corrección**: Selector obligatorio `st.selectbox` con motivos cerrados:
     * *Seleccione un motivo...* (deshabilitante)
     * Carácter confundido por OCR
     * Imagen obstruida / sucia
     * Reflejo o iluminación deficiente
     * Recorte incorrecto
     * Lectura duplicada
     * Otro
   * **Observaciones**: Cuadro de texto opcional `st.text_area`.
   * **Revisor (Identidad Controlada)**: Selector `st.selectbox` (`reviewed_by`) con la lista de auditores autenticados o registrados en la sesión activa (ej. `["jperez", "mrodriguez", "dvelasco"]`), evitando la escritura libre de nombres.
5. **📜 Historial de Revisión (Bitácora)**:
   * Un acordeón plegable `st.expander("Historial de Cambios")` que lee de `ocr_review_records` y despliega la auditoría del registro seleccionado (Revisor, fecha, cambio realizado y motivo).
6. **📥 Botones de Acción**:
   * **Confirmar sin cambios**: Valida que la placa original es correcta y la guarda en estado `válida` sin modificaciones.
   * **Guardar y confirmar corrección**: Habilitado **únicamente** si se ingresó un texto corregido, se seleccionó un motivo de corrección y se especificó el revisor. Guarda el registro como `válida` (o `corregida`).
   * **Acciones Rápidas de Estado**:
     * Botón amarillo `Marcar como dudosa`: Cambia el estado a `dudosa`.
     * Botón rojo `Marcar como ilegible`: Cambia el estado a `ilegible` (descartando la lectura de placa pero manteniendo la trazabilidad del paso del vehículo).

---

## 3. Reglas de Negocio del Flujo OCR

* **Estados Mutuamente Excluyentes**: Un registro OCR sólo puede estar en uno de los cuatro estados: `válida`, `dudosa`, `pendiente` o `ilegible`. Cualquier acción de guardado sobrescribe el estado anterior de forma atómica.
* **Separación de Lógica**: Este formulario escribe exclusivamente en `st.session_state["ocr_review_records"]`. Ningún campo del aforo de tráfico (como el tipo de vehículo del conteo oficial o la dirección) es modificado por esta pantalla.
* **Trazabilidad**: Toda placa que sufra una corrección conserva su lectura original de OCR y su nivel de confianza original para permitir auditorías del motor de reconocimiento.
