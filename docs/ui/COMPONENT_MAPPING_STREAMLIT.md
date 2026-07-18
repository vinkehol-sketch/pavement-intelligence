# Mapeo de Componentes de Interfaz: Tailwind a Streamlit

Este documento detalla la equivalencia técnica entre los componentes HTML/Tailwind CSS exportados por Stitch y los controles nativos de **Streamlit** para el proyecto Pavement Intelligence.

---

## 1. Tabla de Correspondencia de Estilos y Estructura

| Elemento Visual en Stitch (HTML/Tailwind) | Equivalente Técnico en Streamlit | Descripción de Implementación |
| :--- | :--- | :--- |
| **Contenedor Principal** (`.bg-surface`) | Tema nativo o `st.container()` | Controlado por `backgroundColor` en `.streamlit/config.toml`. |
| **Grid Bento** (`.grid-cols-12`) | `st.columns([col_weights])` | Distribución horizontal. Para layouts 75%/25% se usa `st.columns([9, 3])`. |
| **Tarjeta Bento** (`.bg-surface-container-lowest` + bordes) | `st.container(border=True)` | Genera un cuadro blanco con bordes redondeados y sombra suave de forma nativa. |
| **Botón Primario** (`.bg-primary-container` + `.text-on-primary`) | `st.button(type="primary")` | Streamlit colorea automáticamente el botón con el color primario configurado. |
| **Botón Secundario** (Borde gris, texto azul) | `st.button(type="secondary")` | Estilo por defecto de Streamlit. |
| **Selectores e Inputs** (`.border-outline-variant` + focus) | `st.selectbox()`, `st.text_input()` | Renderizados de forma nativa respetando la paleta de colores del tema. |
| **Tabla de Datos** (`<table class="w-full">`) | `st.dataframe()` o `st.data_editor()` | Despliegue de datos interactivos con soporte para ordenación, filtrado y descarga. |
| **Chips de Estado** (`.bg-[#dcfce7]` + `.text-[#166534]`) | HTML inyectado puntual o formato condicional | Se renderizan celdas de texto con color o badges HTML inyectados en Markdown. |
| **Gráficos** (Líneas y barras de flujo) | `st.plotly_chart()` | Gráficos vectoriales e interactivos generados en Python mediante Plotly. |

---

## 2. Soluciones Técnicas para Incompatibilidades y Simplificación

Streamlit es un framework centrado en datos; por lo tanto, no soporta la manipulación directa del DOM de HTML ni la superposición de capas absolutas CSS de forma nativa. A continuación se detallan las estrategias de simplificación técnica:

### A. Superposición sobre el Video (Bounding Boxes y Líneas)
* **Incompatibilidad**: En Stitch, las cajas de los vehículos (bounding boxes) y la línea de conteo se colocan con CSS absoluto (`position: absolute`) sobre la imagen de video.
* **Solución**: Preprocesar el fotograma en Python. Antes de enviar la imagen a `st.image()`, se utiliza OpenCV (`cv2`) para dibujar los rectángulos y textos de inferencia. Esto garantiza que las cajas estén perfectamente alineadas a nivel de píxel y consume menos recursos de renderizado en el navegador.

### B. Selección de Registros en la Tabla (Fila Activa)
* **Incompatibilidad**: En la tabla HTML de Stitch, hacer clic en una fila carga sus detalles en el panel de edición lateral.
* **Solución (Streamlit 1.35+)**: Utilizar la característica `on_select` de `st.dataframe` o `st.data_editor`. Al activar la selección de filas:
  ```python
  event = st.dataframe(
      df,
      on_select="rerun",
      selection_mode="single-row"
  )
  if event.selection.rows:
      selected_idx = event.selection.rows[0]
      # Carga los detalles en el panel de revisión
  ```
* **Alternativa Simple**: Un control `st.selectbox` en la parte superior del panel de edición lateral que permite elegir el `ID` o `Track ID` del vehículo que se desea auditar.

### C. Anonimización y Difuminado (Miniaturas y Placas)
* **Incompatibilidad**: En Stitch, el difuminado de la placa en la miniatura se realiza mediante filtros CSS de Tailwind (`blur-[1px]`). Si un atacante inspecciona la página web, podría retirar el filtro CSS y ver la placa.
* **Solución**: Procesar la seguridad en el servidor de Python. La imagen de la miniatura se corta y se le aplica un desenfoque gaussiano real (`cv2.GaussianBlur` o PIL `ImageFilter.GaussianBlur`) antes de enviarla a Streamlit. La placa original limpia solo se renderiza si el operador hace clic en "Revelar placa completa", acción que es auditada en el log.

### D. Panel Lateral de Revisión (Drawer o Sidebar)
* **Incompatibilidad**: El panel lateral de Stitch se desliza sobre la pantalla cubriendo parte del contenido.
* **Solución**: Colocar el panel de edición a la derecha usando `st.columns([8, 4])` donde la segunda columna contiene todo el formulario. Esto mantiene una disposición limpia y evita problemas de solapamiento visual que Streamlit no gestiona bien.

---

## 3. Componentes Reutilizables a Nivel de Código (Streamlit Utilities)

Para mantener la consistencia entre pantallas, se implementarán funciones de renderizado compartidas en `pavement_intelligence/ui/utils/`:

1. **`render_status_chip(status: str) -> str`**: Retorna el código HTML de un chip estilizado según el estado de la placa o aforo.
2. **`apply_gaussian_blur(image_path_or_bytes, radius: int = 15) -> bytes`**: Función de seguridad para difuminar imágenes de placas antes de enviarlas al navegador.
3. **`draw_inference_overlays(frame, boxes, line_y) -> numpy.ndarray`**: Dibuja las bounding boxes y la línea de conteo en los fotogramas del video.
