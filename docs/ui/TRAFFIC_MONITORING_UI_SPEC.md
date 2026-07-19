# Especificación Técnica: Centro de Monitoreo de Tránsito (Streamlit)

Esta especificación detalla la implementación de la pantalla **Centro de Monitoreo de Tránsito** (`pages/traffic_monitoring.py`) utilizando los componentes nativos de **Streamlit** y conservando las pautas visuales de Stitch.

---

## 1. Estructura y Distribución de la Pantalla (Layout)

La pantalla se organiza en una cabecera global de controles y un bento grid simulado mediante columnas de Streamlit.

```
+-------------------------------------------------------------------------+
| [🎥 Centro de Monitoreo de Tráfico]    [Hoy 📅] [Revisar Conteo 🔍] [Exportar 📥] |
| Av. Central - Punto 04  |  Cámara en vivo  |  Bidireccional              |
+-------------------------------------------------------------------------+
|                                        |                                |
|   COLUMNA IZQUIERDA (Ancho 9)          |    COLUMNA DERECHA (Ancho 3)   |
|                                        |                                |
|   +--------------------------------+   |   +------------------------+   |
|   | 🎥 Reproductor de Video        |   |   | 🚦 Estado Operativo    |   |
|   | (st.image con overlays)        |   |   | (Congestión Moderada)  |   |
|   +--------------------------------+   |   +------------------------+   |
|   | [Play] [Pause] [Replay]        |   |   | 📊 Métricas de Tráfico |   |
|   +--------------------------------+   |   | (Flow, Speed, VisOcc)  |   |
|                                        |   +------------------------+   |
|   +--------------------------------+   |   | 📝 Resumen OCR (Exp.)  |   |
|   | 🚚 Clasificación Vehicular     |   |   | [Ver lecturas OCR 🔍]  |   |
|   | (Última hora - 5 Columnas)     |   |   +------------------------+   |
|   +--------------------------------+   |   | ⚠️ Alertas Recientes    |   |
|   | 📈 Gráfico de Flujo (Plotly)   |   |   | (Últimos 30 min)       |   |
|   +--------------------------------+   |   +------------------------+   |
+-------------------------------------------------------------------------+
```

---

## 2. Definición Detallada de Componentes

### A. Cabecera y Barra de Acciones
* **Título**: `st.title("🎥 Centro de monitoreo de tráfico")`
* **Metadatos del Punto**: Una fila horizontal usando `st.columns([1, 1, 1, 3])` que muestra:
  * `📍 Ubicación: Av. Central - Punto 04`
  * `🎥 Fuente: Cámara en vivo`
  * `↔️ Sentido: Bidireccional`
* **Botones de Acción (Esquina Superior Derecha)**:
  * **📅 Hoy**: Selector temporal.
  * **🔍 Revisar Conteo**: Redirige a la pantalla `pages/traffic_review.py` (Aforo).
  * **📥 Exportar Datos**: Descarga de los conteos acumulados de tráfico.

### B. Reproductor de Video Simulado (Cámara en Vivo)
* **Visualizador**: `st.image(image_bytes_or_numpy, use_container_width=True)`.
  * El fotograma del video se obtiene de manera simulada a partir de imágenes locales de muestra.
  * **Superposición Gráfica (Detecciones)**: No se usa HTML/CSS absoluto. Se utiliza la biblioteca OpenCV (`cv2`) para dibujar en el backend de Python:
    * Bounding boxes alrededor de los vehículos (ej. rectángulos verdes para autos y azules para buses con etiquetas `Auto | ID:458 | 95%`).
    * Línea virtual de conteo en la posición de píxeles correspondiente (ej. línea discontinua amarilla con texto "LÍNEA DE CONTEO").
* **Banda de Controles**: Fila horizontal con botones `st.button` para simular reproducción (`▶️ Play`, `⏸️ Pause`, `🔄 Replay`) y texto informativo del stream en formato mono (FPS, resolución, latencia).

### C. Panel Lateral de Estado y Métricas (Columna Derecha)
* **🚦 Estado de Congestión**: Un contenedor con borde de advertencia `st.container(border=True)` que muestra un indicador grande: `Congestión Moderada` junto con un icono de advertencia.
* **📊 Indicadores de Tráfico**:
  * `Flujo actual`: `st.metric(label="Flujo Actual", value="32 veh/min")`
  * `Velocidad promedio`: `st.metric(label="Velocidad Promedio", value="21 km/h")`
  * `Ocupación visual estimada`: `st.metric(label="Ocupación Visual Estima", value="64%")` (marcado como experimental).
  * `Total acumulado`: `st.metric(label="Total Acumulado", value="1,556")`
* **📝 Resumen OCR Experimental**:
  * Un cuadro de información que despliega estadísticas agregadas de la sesión:
    * Placas detectadas: `142`
    * Lecturas válidas: `128`
    * Lecturas pendientes de revisión OCR: `14`
  * **Botón de Enlace**: `st.button("🔍 Ver lecturas OCR")` que, mediante un cambio en la navegación o en una variable de control, redirige a `pages/ocr_plate_review.py`.
* **⚠️ Alertas Recientes (30 min)**:
  * Tabla compacta de alertas implementada con `st.dataframe` o un bucle de `st.markdown()` para renderizar alertas operativas como "Congestión Alta" o "Flujo Anormal".

### D. Panel de Clasificación Vehicular (Última Hora)
* Fila de 5 columnas `cols = st.columns(5)` que contiene sub-contenedores con bordes para mostrar:
  1. **Automóviles**: Icono de auto, total (`1,245`), y tendencia (`▲ 5.2%` en verde).
  2. **Minibuses**: Icono de minivan, total (`312`), y tendencia (`▼ 1.1%` en amarillo).
  3. **Buses**: Icono de autobús, total (`189`), y tendencia (`▲ 2.4%` en verde).
  4. **Camiones**: Icono de camión pesado, total (`84`), y tendencia (`▲ 0.5%` en verde).
  5. **Motocicletas**: Icono de moto, total (`456`), y tendencia (`▲ 12.3%` en rojo).

### E. Historial de Flujo Vehicular
* Gráfico de líneas que muestra la distribución temporal del flujo (veh/min) desglosado por sentido (Norte $\rightarrow$ Sur y Sur $\rightarrow$ Norte) en las últimas horas.
* Implementado nativamente usando `st.plotly_chart(fig, use_container_width=True)`.

---

## 3. Lógica de Datos y Estado de Sesión

### A. Datos Simulados para el Monitoreo
La pantalla consumirá datos generados por un servicio de simulación (`pavement_intelligence/services/traffic_simulator.py`) que entregará:
* Una trama de video de muestra (fotogramas OpenCV anotados dinámicamente con coordenadas de vehículos en movimiento).
* Series de tiempo de conteo vehicular por minuto.
* Contadores acumulados del día.

### B. Integración con el Flujo de Tránsito
* **Estado de la Revisión**: La cabecera consulta el estado de aprobación del aforo en `st.session_state["traffic_review_approval"]`. Si es `True`, muestra una etiqueta verde de "Aforo Aprobado" al lado del botón "Revisar Conteo".
* **Estado del OCR**: La tarjeta de LPR lee directamente la longitud de los registros de placas y su estado desde `st.session_state["ocr_review_records"]` para mostrar la cantidad de pendientes reales en tiempo de ejecución.
# Extensión: reproductor de video demostrativo

El Centro de Monitoreo admite dos fuentes de demostración: `Imagen estática` (modo inicial y fallback) y `Video local`. El segundo modo reproduce exclusivamente un MP4 local preprocesado mediante fotogramas servidos por Streamlit; no conecta con detección, tracking, OCR ni aforo oficial.

Los controles Reproducir, Pausar y Reiniciar operan sobre estado de sesión aislado con prefijo `traffic_demo_`. La interfaz muestra fotograma, progreso, tiempo actual/total, FPS y resolución. Toda métrica sincronizada con el progreso debe llevar la leyenda visible “Métricas demostrativas, no calculadas desde el video”. Un fallo de lectura debe pausar el reproductor y restaurar visualmente la imagen estática sin interrumpir la página.
