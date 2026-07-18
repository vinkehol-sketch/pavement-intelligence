# Sistema de Diseño de Interfaz: Streamlit (Pavement Intelligence)

Este documento define la traducción técnica de los tokens de diseño visual exportados por Stitch (diseño corporativo moderno y sistemático) a la arquitectura de **Streamlit**. Está diseñado para ingenieros viales y operadores que requieren una interfaz de alta densidad de información, limpia y utilitaria.

---

## 1. Paleta de Colores y Tematización

La paleta se centra en un color primario institucional fuerte para botones y estados activos, un color de fondo claro de fatiga reducida y colores de estado semánticos estrictamente reservados para retroalimentación técnica.

### A. Archivo de Configuración de Streamlit (`.streamlit/config.toml`)
Para asegurar la coherencia estética global de la plataforma, se define el siguiente tema en el archivo de configuración del entorno de producción:

```toml
[theme]
primaryColor = "#1A56DB"            # Azul Primario (Acciones principales)
backgroundColor = "#FAF8FF"         # Fondo Principal (Gris claro de bajo brillo)
secondaryBackgroundColor = "#EDEDF8" # Contenedores y áreas secundarias
textColor = "#191B23"               # Texto Principal (Alto contraste)
font = "sans serif"                 # Usará Inter por defecto
```

### B. Mapeo Adicional de Colores (Material Design 3)
Para elementos específicos que no se pueden controlar por `.streamlit/config.toml`, se definen las siguientes variables de color inyectadas por CSS:

* **Superficies**:
  * `surface-container-lowest` (Fondo de tarjetas): `#FFFFFF`
  * `surface-container-low` (Fila inactiva / Separadores): `#F3F3FE`
  * `surface-container-high` (Hover de botones/tarjetas): `#E7E7F3`
  * `surface-container-highest` (Fila seleccionada): `#E2E1ED`
  * `on-surface-variant` (Texto secundario / Leyendas): `#434654`
  * `outline` (Bordes generales): `#737686`
  * `outline-variant` (Líneas de separación / Bordes de tarjetas): `#C3C5D7`
* **Estados Semánticos (Operacionales)**:
  * `success` (Válido / Aceptado): `#16A34A` (Fondo tintado: `#DCFCE7`)
  * `warning` (Dudoso / Alerta): `#CA8A04` (Fondo tintado: `#FEF08A`)
  * `error` (Ilegible / Descartado): `#DC2626` (Fondo tintado: `#FEE2E2`)
  * `info` (Pendiente): `#003FB1` (Fondo tintado: `#D4DCFF`)

---

## 2. Tipografía y Estilos de Texto

El sistema utiliza **Inter** por su alta legibilidad en tablas y dashboards de alta densidad.

### A. Escala Tipográfica en Streamlit
Streamlit no permite fuentes personalizadas de manera nativa sin inyección de CSS. Se usará la siguiente correspondencia visual mediante Markdown y estilos CSS inyectados de forma puntual:

| Rol de Diseño | Elemento HTML original | Tamaño CSS | Equivalente en Streamlit |
| :--- | :--- | :--- | :--- |
| **Display Large** | `h1` | 36px / Bold | `st.title()` con CSS inyectado para peso/fuente |
| **Headline Medium** | `h2` | 24px / SemiBold | `st.header()` o `st.subheader()` |
| **Headline Small** | `h3` | 20px / SemiBold | Subtítulos y cabeceras de columnas |
| **Body Large** | `p` | 16px / Regular | `st.write()` o texto estándar |
| **Body Medium** | `span`/`label` | 14px / Regular | Etiquetas de controles (`st.selectbox`, etc.) |
| **Label Medium** | `small` | 12px / Bold (Caps) | Cabeceras de tabla / Leyendas de gráficos |
| **Data Mono** | `code` | 14px / Medium (Mono) | Datos numéricos / Placas (`st.code` o dataframe) |

---

## 3. Layout y Espaciado (Grid de Alta Densidad)

El diseño sistemático de Stitch prioriza la densidad compacta de información para evitar scroll innecesario.

* **Rejilla Columnar**: Simular la rejilla de 12 columnas mediante el parámetro de pesos de `st.columns`:
  * Para una proporción 75% / 25%: `col1, col2 = st.columns([9, 3])`
  * Para una fila de KPIs (5 columnas): `cols = st.columns(5)`
  * Para una fila de clasificación (5 columnas): `cols = st.columns(5)`
* **Espaciado y Márgenes**:
  * Separación estándar entre bloques: `st.write("")` o el espaciado nativo de Streamlit.
  * Altura de contenedores compactos: Limitado mediante el uso de `st.container(border=True)`.
* **Forma (Bordes)**:
  * El radio de curvatura es estricto: 4px (`rounded-DEFAULT`) para botones y campos, y 8px (`rounded-lg`) para contenedores grandes. Esto es controlado nativamente por el tema Streamlit.

---

## 4. Clases CSS Utilitarias Inyectadas
Para los componentes específicos que requieran asemejar el color y forma de Stitch, se inyectará una única hoja de estilos en la cabecera del script (`app.py` o de forma local en cada página):

```python
import streamlit as st

def inject_design_system_css():
    st.markdown(
        """
        <style>
        /* Estilos generales para Badges y Chips de Estado */
        .status-chip {
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            display: inline-block;
        }
        .status-valida {
            background-color: #DCFCE7;
            color: #166534;
            border: 1px solid #16A34A;
        }
        .status-dudosa {
            background-color: #FEF08A;
            color: #854D0E;
            border: 1px solid #CA8A04;
        }
        .status-ilegible {
            background-color: #FEE2E2;
            color: #991B1B;
            border: 1px solid #DC2626;
        }
        .status-pendiente {
            background-color: #F3F3FE;
            color: #434654;
            border: 1px solid #C3C5D7;
        }

        /* Contenedor Bento Grid con Bordes */
        .bento-card {
            background-color: #FFFFFF;
            border: 1px solid #C3C5D7;
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 16px;
        }

        /* Modificador de ancho para st.dataframe */
        div[data-testid="stDataFrame"] {
            font-family: 'Inter', monospace;
        }
        </style>
        """,
        unsafe_allow_html=True
    )
```
