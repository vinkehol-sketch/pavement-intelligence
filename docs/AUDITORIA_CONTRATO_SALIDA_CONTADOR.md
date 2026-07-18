# Auditoría de Contrato de Salida del Contador — Pavement Intelligence
**Proyecto:** Pavement Intelligence (Plataforma de Análisis de Tránsito y Diseño de Pavimentos)  
**Estado:** Documento de Alineación Técnico-Funcional  
**Fecha:** 2026-07-17  

Este documento realiza la auditoría y alineación de la documentación de integración y diseño de interfaz (UX) con la salida real del contador de visión artificial corregido en `src/pavement_intelligence/vision/pipeline.py`.

---

## 1. Estructura Real Encontrada en el Código
Al inspeccionar [pipeline.py](file:///D:/proyecto%20Vial/pavement_intelligence/src/pavement_intelligence/vision/pipeline.py), se constata que cada evento de cruce de línea es capturado en la clase `TrafficEvent` con la siguiente estructura de atributos:

* `event_id`: Identificador de cadena con el formato `evt_{timestamp_sistema}_{track_id}` (generado dinámicamente).
* `track_id`: Entero que identifica el objeto seguido por ByteTrack.
  - *Regla real:* Los `track_id` inválidos se descartan en el pipeline. Los válidos son estrictamente enteros $\ge 0$.
* `original_class`: Nombre de la clase consolidada/establecida por mayoría a lo largo de la trayectoria del track (ej. `car`, `truck`, `bus`, `motorcycle`), obtenida a través de `self.counter.get_stable_class(track_id)`.
* `category`: Categoría preliminar obtenida mediante el detector del modelo (ej: `AUTO`, `MOTO`, `BUS`, `CAMION`, `DESCONOCIDO`).
* `confidence`: Nivel de confianza histórico o promedio acumulado del track (`self.counter.get_average_confidence(track_id)`).
* `frame_number`: Índice del fotograma donde ocurrió el cruce.
* `video_second`: Tiempo en segundos relativo al inicio del video (`frame_number / fps`).
* `direction`: Sentido del cruce devuelto por la línea virtual (`1` o `-1`).
* `centroid_x`, `centroid_y`: Coordenadas del centroide del vehículo en el momento de cruzar.
* `source`: Nombre del archivo de video origen.
* `processing_date`: Timestamp de procesamiento del sistema en formato ISO.
* `data_origin`: Cadena constante configurada por defecto como `"OBSERVADO_POR_VIDEO"`.

---

## 2. Matriz de Mapeo y Transformación de Campos
La siguiente matriz detalla el mapeo entre la salida real de `TrafficEvent` en el código y los campos propuestos en el contrato de integración:

| Campo Real (`TrafficEvent`) | Tipo Real | Campo Propuesto en Contrato | Tipo Propuesto | Estado de Existencia | Transformación / Acción Necesaria | Productor | Consumidor |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `event_id` | str | `event_id` | str | **Existe** | Ninguna. Se usa tal cual. | Visión | UI / Auditoría |
| `track_id` | int | `track_id` | int | **Existe** | Ninguna. Filtrar si es $< 0$ (ya se hace en backend). | Visión | UI / Auditoría |
| `original_class` | str | `visual_class` | str | **Existe (con otro nombre)** | Mapear `original_class` a `visual_class` en la UI. | Visión | UI / Auditoría |
| `category` | str | `automatic_category` | str | **Existe (con otro nombre)** | Mapear `category` a `automatic_category` (categoría preliminar). | Visión | UI / Auditoría |
| `confidence` | float | `confidence` | float | **Existe** | Representa el promedio de confianza de la trayectoria. | Visión | UI / Auditoría |
| `frame_number` | int | `frame_index` | int | **Existe (con otro nombre)** | Mapear `frame_number` a `frame_index` en la UI. | Visión | UI / Auditoría |
| `video_second` | float | `timestamp` | str | **Derivable** | Convertir `video_second` a formato relativo `+HH:MM:SS` desde el inicio del video. | Visión | UI / Auditoría |
| `direction` | int | `direction` | int | **Existe** | Usar tal cual (`1` y `-1`). | Visión | UI / Auditoría |
| `source` | str | `source_video` | str | **Existe (con otro nombre)** | Mapear `source` a `source_video`. | Visión | UI / Auditoría |
| `processing_date` | str | — | — | **Existe** | Opcional para logs de auditoría técnica. | Visión | Reportes |
| — | — | `model_name` | str | **Falta en Evento** | Obtener el nombre del modelo YOLO seleccionado en la UI. | UI | Reportes |
| — | — | `line_id` | str | **Inexistente** | Dejar como opcional. En el MVP se asume línea única. | — | — |
| — | — | `validation_status` | str | **Inexistente en Código** | Inicializar en la UI como `"AUTOMATICO"` dentro de la lista de dicts. | UI | Aforo / TPDA |

---

## 3. Clasificación de Campos por Disponibilidad

### A. Campos Disponibles Ahora:
* `event_id`, `track_id`, `original_class` (clase mayoritaria), `category` (categoría preliminar de IA), `confidence` (promedio del track), `frame_number`, `video_second`, `direction`, `source` y `processing_date`.

### B. Campos Derivables:
* **`timestamp` relativo:** Formateado a partir de `video_second` como un desplazamiento temporal (ej. `+00:01:24`).
* **`automatic_count`:** Siempre es `1` para cada fila de evento emitida.

### C. Campos que Requieren Implementación Futura en el Backend:
* **`model_name`:** Para persistir qué pesos se usaron (`yolov8n.pt` o `yolov8s.pt`) directamente en el objeto `TrafficEvent`.
* **`line_id`:** Para identificar la línea en aforos multilínea o en diferentes carriles.

### D. Campos que NO deben Inventarse:
* **Hora real del día:** No se debe simular una hora real del reloj (ej: 08:15 AM) a partir de un video si no se ingresa un offset/timestamp de inicio real por parte del usuario.
* **Categorías de ejes ABC en Visión:** No se debe clasificar automáticamente a `C2`, `C3` o `TRACTOCAMION` en el backend de visión. La visión solo distingue la clase mayoritaria `truck` y la categoría preliminar `CAMION`. El desglose a la categoría vial oficial **debe ser manual y obligatorio**.

---

## 4. Alineación Terminológica Técnico-Vial

Para unificar criterios entre el backend de Codex, el dominio y la interfaz de usuario, se establece la siguiente correspondencia terminológica:

* **Visual Class / Clase Puntual:** Corresponde a la detección frame a frame. No se expone en el evento.
* **Stable Class / Clase Consolidada:** Corresponde al campo real `original_class` (la clase por mayoría del tracking). Es la que se muestra en la UI como la clase detectada por la IA.
* **Confianza Histórica:** Corresponde al campo real `confidence` (promedio de confianza del track en la trayectoria).
* **Categoría de Tránsito Preliminar:** Corresponde al campo real `category` del evento, que realiza el mapeo de la clase consolidada a los 5 grupos macro viales de la UI (`AUTO`, `MOTO`, `BUS`, `CAMION`, `DESCONOCIDO`).
* **Categoría Vial Confirmada:** Corresponde a la categoría oficial de la ABC (`C2`, `C3`, etc.) seleccionada por el usuario en la tabla de revisión manual.

---

## 5. Manejo de Eventos con Datos Incompletos o Ausentes

* **Sin evidencia visual (sin coordenadas de centroide o frame):** Si el evento carece de `centroid_x` o `centroid_y`, la UI lo muestra en la tabla con la advertencia: *"Sin coordenadas de cruce"*. Se restringe la opción de dibujar el marcador de cruce en pantalla.
* **Sin timestamp o segundo de video:** Se asume `video_second = 0.0` y se etiqueta como `+00:00:00`.
* **Sin confianza o confianza nula:** Se muestra como `100%` si el evento es de origen manual, o `N/A` si es de origen IA, mostrando una advertencia de auditoría requerida.
* **Sin dirección o dirección = 0:** La dirección de cruce es obligatoria. Si `direction` es `0` o no coincide con los sentidos del proyecto, el evento se marca en estado `Requiere Revisión` y se bloquea el botón de envío a TPDA hasta que el usuario le asigne un sentido (`1` o `-1`) en la UI.
* **Sin categoría estable (DESCONOCIDO):** El evento se etiqueta con estado `Sin Revisar` y categoría preliminar `DESCONOCIDO`. El usuario debe clasificarlo manualmente antes de aprobar.

---

## 6. Ajustes al Diseño de Experiencia de Usuario (UX)

Para cumplir con el rigor de la ingeniería vial y la retroalimentación del proyecto, se modifican los siguientes aspectos de la UX:

1. **Revisión Manual Obligatoria:** La interfaz de Streamlit mostrará de forma destacada que el conteo automático de la IA es **preliminar e indicativo**. Ningún conteo pasará automáticamente al cálculo de TPDA sin la aprobación expresa del usuario.
2. **Registro de Configuración del Modelo:** En la parte inferior de la pantalla de revisión, debe quedar registrado y visible para el reporte:
   - Ruta del modelo YOLO utilizado (ej: `data/models/yolov8n.pt`).
   - Coordenadas de la línea virtual de conteo en píxeles.
3. **Advertencia de No Validez Automática:** La pantalla mostrará una leyenda clara indicando que el cálculo automático del aforo por video corto es una simulación temporal de tráfico y requiere validación del ingeniero responsable.
4. **Umbral de Confianza de Revisión Configurable:** En lugar de forzar un umbral de confianza rígido del 55%, el operador contará con un control deslizable (slider) en la barra lateral llamado **"Umbral de Confianza para Alerta de Revisión (%)"**. Los eventos con confianza inferior al umbral seleccionado se marcarán dinámicamente con la alerta `⚠️ Baja Confianza`.
5. **Justificación de Corrección Recomendada:** El ingreso de la justificación al corregir o descartar eventos se manejará como una recomendación de buenas prácticas. El sistema sugerirá ingresar una nota descriptiva para mantener la trazabilidad, pero la validación de envío no se bloqueará de forma rígida por longitud de caracteres (no exigir mínimo de 10 caracteres técnicamente, sino dejarlo configurable o sugerido).

---

## 7. Contrato Mínimo Viable para Implementación de la UI
Para iniciar la programación de la pantalla, la UI consumirá la lista de diccionarios devuelta por `export_corrected_records` en el módulo de video. 

El diccionario de entrada para la tabla en `survey_tpda.py` será:
```python
{
    "event_id": str,
    "track_id": int,
    "category": str,     # Categoría preliminar (AUTO, MOTO, BUS, CAMION, DESCONOCIDO)
    "direction": int,    # 1 o -1
    "source": str,       # Nombre del video
    "status": str,       # "AUTOMATICO" | "CORREGIDO_MANUALMENTE" | "AGREGADO_MANUALMENTE"
    "notes": str         # Justificación
}
```
Esto permite mapear directamente la salida existente de la página de video y construir la tabla de revisión de aforo.
