# Informe de implementación — Centro de monitoreo de tráfico

## Alcance implementado

Se implementó la primera fase de la interfaz de movilidad en Streamlit: modelos de presentación puros, fixtures JSON sintéticos, utilidades visuales mínimas, pantalla de monitoreo, integración en la navegación y pruebas unitarias.

La pantalla no ejecuta YOLO, ByteTrack u OCR. Tampoco modifica eventos técnicos, el flujo oficial de revisión, TPDA ni los módulos de pavimentos.

## Decisiones técnicas

- Los modelos viven en `domain/traffic/presentation.py` y usan `dataclass`/`Enum` sin dependencia de Streamlit.
- Los estados operativos, de fuente, congestión y revisión son enumeraciones cerradas.
- La desconexión de fuente se valida como un estado coherente y mutuamente excluyente.
- Los datos de UI se identifican con `SYNTHETIC_UI_DEMO` y se almacenan fuera del código productivo.
- La pantalla usa un fotograma local ya anotado; no inicializa modelos de visión.
- Se usan componentes nativos de Streamlit, tema en `config.toml` y CSS acotado únicamente para chips de estado.
- El resumen OCR no lee ni modifica la aprobación del aforo.

## Diferencias inevitables respecto a Stitch

- Streamlit conserva su navegación lateral y flujo vertical, por lo que no replica el drawer lateral de placas ni el posicionamiento absoluto del HTML.
- El fotograma demostrativo disponible difiere de la avenida usada en Stitch.
- Los controles de video son simulados y no reproducen un stream continuo.
- Las alertas se muestran en una tabla nativa y la revisión OCR completa queda fuera de esta fase.

## Verificación

Estado inicial: 452 pruebas aprobadas y sin errores previos observados. `git status --short` mostraba `?? docs/ui/`; esa documentación obligatoria ya estaba presente como contenido no rastreado antes de la implementación y se preservó.

Resultados finales:

- Pruebas nuevas: 11 aprobadas.
- Suite completa: 463 aprobadas en 7.16 s.
- Render con `streamlit.testing.v1.AppTest`: sin excepciones.
- Compilación de los nuevos módulos: correcta.
- `pip check`: sin dependencias rotas.
- `git diff --check`: sin errores (solo aviso de normalización LF/CRLF en `app.py`).

Comandos usados:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest -q
& '.\.venv\Scripts\python.exe' -m pip check
```

## Apertura de la pantalla

Ejecutar desde la raíz del proyecto:

```powershell
& '.\.venv\Scripts\streamlit.exe' run src\pavement_intelligence\ui\app.py
```

Después, seleccionar **Monitoreo de tráfico** en la navegación lateral.

## Riesgos pendientes

- Los valores de congestión, velocidad, ocupación y OCR son demostrativos, no resultados técnicos.
- La navegación desde “Revisar conteo” depende de la ruta existente de Streamlit y no transfiere ni aprueba datos.
- La reproducción real, el cálculo definitivo de congestión y la revisión OCR permanecen pendientes.
