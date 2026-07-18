# Informe de implementación — Revisión experimental de placas OCR

## Alcance implementado

Se implementó una página Streamlit para revisar lecturas de placas exclusivamente sintéticas. La solución no ejecuta OCR, detección, YOLO, ByteTrack ni procesamiento de video, y no consulta propietarios ni sistemas externos.

## Archivos y componentes

- Modelos OCR puros en `domain/traffic/ocr_presentation.py`.
- Fixture `data/samples/ui/plate_readings_demo.json`, identificado como `SYNTHETIC_UI_DEMO` y compuesto por matrículas ficticias.
- Utilidades de privacidad, auditoría, revisión y exportación en `ui/utils/ocr_privacy.py`.
- Página `ui/pages/ocr_plate_review.py`.
- Navegación registrada en `ui/app.py` y enlace bidireccional con `traffic_monitoring.py`.
- Pruebas unitarias y pruebas de render con `streamlit.testing.v1.AppTest`.

## Modelos añadidos

- `PlateReadingPresentation`: lectura OCR original e inmutable y metadatos técnicos de solo lectura.
- `PlateReviewStatus`: estados exclusivos `PENDING`, `VALID`, `DOUBTFUL` e `ILLEGIBLE`.
- `PlateCorrectionRequest`: valida texto, motivo y revisor.
- `PlateReviewRecord`: conserva original y corrección por separado.
- `PlateRevealAuditRecord`: registra acciones `REVEAL` y `HIDE`.
- `OcrReviewPageState`: garantiza que solo la lectura seleccionada pueda estar visible.
- `OcrSummaryPresentation` fue ampliado con el conteo de ilegibles, conservando compatibilidad con el dashboard.

## Control mostrar/ocultar

Las placas aparecen enmascaradas en la tabla. La miniatura protegida se genera con desenfoque gaussiano real en el backend. El panel solo genera y envía el recorte legible cuando `ocr_visible_reading_id` coincide con la lectura seleccionada.

El botón alterna entre **Mostrar placa** y **Ocultar placa**. Cada revelado registra lectura, revisor, fecha y acción. Al seleccionar otra lectura, `ocr_visible_reading_id` vuelve automáticamente a `None`; no existe una acción para revelar todas las matrículas.

## Aislamiento

La página usa solamente las claves:

- `ocr_readings_raw`
- `ocr_review_records`
- `ocr_selected_reading_id`
- `ocr_visible_reading_id`
- `ocr_reveal_audit`
- `ocr_filters`

Los campos de categoría, sentido, evento y track se muestran como referencias inmutables. Las utilidades OCR no escriben en eventos de visión, aprobación del aforo ni transferencia a TPDA.

## Exportación

La descarga incluye únicamente revisiones guardadas y datos textuales sintéticos: IDs, original, corrección, estado, confianza, motivo, revisor, fecha y origen. No exporta imágenes ni registros pendientes no revisados.

## Diferencias respecto a Stitch

- El drawer superpuesto se representa como una columna derecha 8:4, de acuerdo con el mapeo Streamlit del proyecto.
- La selección usa un control nativo de revisión y una tabla protegida, sin copiar el HTML exportado.
- Las imágenes de placa se generan en backend a partir de texto ficticio; no son recortes obtenidos por un detector real.
- La sesión es demostrativa y no constituye almacenamiento persistente de auditoría.

## Verificación

- Baseline previo: 463 pruebas aprobadas.
- Pruebas finales: 486 aprobadas en 8.34 s.
- Pruebas OCR dirigidas, dashboard y AppTest: 34 aprobadas.
- AppTest de OCR y monitoreo: sin excepciones.
- `pip check`: sin dependencias rotas.
- Compilación de módulos nuevos: correcta.
- Módulos protegidos: sin diferencias respecto a `HEAD`.

## Riesgos pendientes

- La auditoría reside en `st.session_state` y se pierde al cerrar la sesión.
- Antes de admitir datos reales deben añadirse autenticación, autorización, retención segura y políticas de privacidad.
- La precisión OCR, detección y vínculo con evidencia real permanecen fuera de alcance.

## Apertura

Ejecutar:

```powershell
& '.\.venv\Scripts\streamlit.exe' run src\pavement_intelligence\ui\app.py
```

Seleccionar **Lecturas de placas** en la navegación o pulsar **Ver lecturas** desde **Monitoreo de tráfico**.
