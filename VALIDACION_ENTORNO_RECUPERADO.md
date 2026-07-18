# Validación final del entorno recuperado

Fecha: 2026-07-17  
Alcance: validación final de visión por computadora, limitada a 20 fotogramas.

## Resultado general

- `pip check`: **correcto** — `No broken requirements found.`
- Imports reales: **correctos** para `torch`, `torchvision`, `cv2` y `ultralytics`.
- Carga de YOLO: **correcta**.
- Lectura del video con OpenCV: **correcta**.
- Inferencia: **correcta**, sin excepciones durante el procesamiento.
- Detecciones reales en los 20 fotogramas evaluados: **0**.
- Bloqueos pendientes: **ninguno para cargar y ejecutar el stack de visión**.

## Versiones e imports comprobados

| Paquete importado | Versión comprobada |
|---|---:|
| `torch` | `2.13.0+cpu` |
| `torchvision` | `0.28.0+cpu` |
| `cv2` | `5.0.0` |
| `ultralytics` | `8.4.99` |

CUDA reportó `False` y cero dispositivos disponibles, por lo que se utilizó CPU.

## Prueba acotada de inferencia

| Campo | Resultado |
|---|---|
| Modelo utilizado | `data/models/yolov8n.pt` |
| Ruta absoluta resuelta | `D:\proyecto Vial\pavement_intelligence\data\models\yolov8n.pt` |
| Dispositivo | `cpu` |
| Video utilizado | `D:\proyecto Vial\pavement_intelligence\data\videos\samples\car-detection.mp4` |
| OpenCV abrió el video | Sí |
| Fotogramas procesados | 20 |
| Detecciones obtenidas | 0 |
| Clases detectadas | Ninguna |
| Tiempo aproximado | 4.811 s, incluida la carga del modelo |
| Error durante inferencia | Ninguno |

No se procesó el video completo. El ciclo se detuvo al alcanzar el límite de 20 fotogramas.

## Exclusión de modelos duplicados de la raíz

La copia duplicada de la raíz se resolvió como:

`D:\proyecto Vial\pavement_intelligence\yolov8n.pt`

La comparación de rutas absolutas produjo `USES_ROOT_DUPLICATE=False`. La instancia de `YOLO` recibió explícitamente la ruta absoluta de `data/models/yolov8n.pt`; por tanto, no se utilizó el modelo duplicado de la raíz ni `yolov8s.pt`.

## Errores y advertencias observados

- El primer import de `ultralytics` intentó crear su configuración en `C:\Users\Pc\AppData\Roaming\Ultralytics` y recibió `PermissionError` por las restricciones del entorno aislado. Se repitió el import con `YOLO_CONFIG_DIR` dirigido a una ubicación escribible dentro del proyecto; el import y la inferencia funcionaron.
- Ultralytics creó archivos auxiliares de configuración bajo `D:\proyecto Vial\pavement_intelligence\Ultralytics`.
- Matplotlib no pudo usar `C:\Users\Pc\AppData\Local\matplotlib` y creó una caché temporal. Fue una advertencia de caché y no afectó la carga del modelo ni la inferencia.
- Una invocación preliminar inline fue rechazada por el analizador de PowerShell debido al escape de comillas; Python no llegó a ejecutarse y no se procesaron fotogramas en ese intento. La ejecución final usó un script temporal, posteriormente retirado.
- No hubo errores de OpenCV, carga de pesos ni inferencia en la ejecución final.

## Restricciones respetadas

- Se utilizó exclusivamente `data/models/yolov8n.pt`.
- Se procesaron como máximo 20 fotogramas.
- No se modificaron fórmulas, módulos técnicos ni parámetros del contador.
- No se procesó el video completo.

---

# Validación distribuida y comparación controlada de modelos

Fecha: 2026-07-17  
Video: `data/videos/samples/car-detection.mp4`  
Dispositivo: CPU  
Configuración: predicción Ultralytics vigente, sin cambios permanentes.

## Metadatos del video

| Propiedad | Valor |
|---|---:|
| Total de fotogramas | 377 |
| FPS | 12.5 |
| Duración calculada | 30.16 s |
| Resolución | 768 × 432 px |

Se revisaron 63 fotogramas únicos, distribuidos uniformemente y leídos por posicionamiento directo, no mediante procesamiento completo del video. Los índices fueron:

`0, 6, 12, 19, 25, 31, 38, 44, 50, 57, 63, 70, 76, 82, 89, 94, 95, 101, 108, 114, 121, 127, 133, 140, 146, 152, 159, 165, 172, 178, 184, 188, 191, 197, 203, 210, 216, 223, 229, 235, 242, 248, 254, 261, 267, 274, 280, 282, 286, 293, 299, 305, 312, 318, 325, 331, 337, 344, 350, 356, 363, 369, 376`.

Los hitos exactos fueron: inicio `0`, 25 % `94`, 50 % `188`, 75 % `282` y final `376`. Todos fueron incluidos en ambos modelos.

## Resultado comparativo

| Métrica | `yolov8n.pt` | `yolov8s.pt` |
|---|---:|---:|
| Ruta | `data/models/yolov8n.pt` | `data/models/yolov8s.pt` |
| Fotogramas evaluados | 63 | 63 |
| Detecciones totales | 32 | 30 |
| Detecciones vehiculares | 12 | 6 |
| Fotogramas con detección vehicular | 10 | 6 |
| Clases vehiculares encontradas | `car`, `bus` | `car` |
| Confianza vehicular media | 0.4735 | 0.6968 |
| Confianza vehicular máxima | 0.6930 | 0.8506 |
| Tiempo de inferencia aproximado | 5.154 s | 3.877 s |

Las clases `motorcycle` y `truck` no fueron detectadas por ninguno. `yolov8n` produjo más detecciones vehiculares, pero en el fotograma 229 asignó simultáneamente `car` y `bus` al mismo automóvil, lo que podría generar doble conteo si se aceptan ambas clases sin seguimiento o deduplicación. `yolov8s` obtuvo menos detecciones vehiculares, pero con confianza media claramente mayor y sin esa duplicación vehicular en la imagen anotada.

Los tiempos sirven sólo como referencia de esta ejecución en CPU; no constituyen un benchmark porque los modelos se ejecutaron secuencialmente y pueden beneficiarse de cachés distintas.

## Registro completo de detecciones — YOLOv8n

Formato de caja: `[x1, y1, x2, y2]`, en píxeles.

| Fotograma | Clase | Confianza | Caja |
|---:|---|---:|---|
| 63 | car | 0.5310 | `[280.4, 288.3, 478.9, 428.1]` |
| 76 | cell phone | 0.9101 | `[268.8, 117.6, 453.4, 408.0]` |
| 82 | cell phone | 0.9122 | `[271.2, 49.8, 430.4, 302.1]` |
| 89 | cell phone | 0.8557 | `[274.2, 1.5, 414.1, 203.9]` |
| 94 | cell phone | 0.8797 | `[281.0, 1.2, 404.6, 141.3]` |
| 95 | cell phone | 0.5976 | `[282.1, 0.5, 403.4, 126.0]` |
| 101 | car | 0.6325 | `[283.9, 0.3, 398.0, 66.4]` |
| 184 | spoon | 0.4631 | `[0.1, 20.0, 50.3, 52.5]` |
| 188 | spoon | 0.4512 | `[0.1, 19.9, 50.5, 52.3]` |
| 188 | cup | 0.4113 | `[146.1, 0.5, 264.2, 90.2]` |
| 191 | spoon | 0.3363 | `[0.1, 19.7, 50.6, 51.9]` |
| 191 | person | 0.2835 | `[325.9, 353.8, 493.0, 430.8]` |
| 197 | car | 0.4308 | `[120.9, 1.4, 264.4, 205.7]` |
| 197 | spoon | 0.2783 | `[0.1, 19.2, 50.2, 51.1]` |
| 203 | cell phone | 0.6409 | `[102.0, 25.5, 257.3, 310.9]` |
| 203 | car | 0.3884 | `[317.0, 175.7, 490.7, 427.0]` |
| 203 | suitcase | 0.3058 | `[315.7, 176.3, 491.0, 427.4]` |
| 210 | cell phone | 0.8263 | `[75.4, 115.4, 249.9, 427.8]` |
| 210 | bus | 0.3407 | `[313.3, 91.9, 475.7, 367.3]` |
| 216 | cell phone | 0.6279 | `[56.9, 204.4, 244.1, 426.8]` |
| 216 | bus | 0.2695 | `[308.2, 31.8, 462.2, 272.8]` |
| 223 | car | 0.5983 | `[64.1, 327.0, 235.1, 428.6]` |
| 223 | car | 0.2553 | `[305.6, 0.7, 445.5, 174.5]` |
| 229 | car | 0.6930 | `[307.2, 0.7, 432.0, 105.6]` |
| 229 | bus | 0.5016 | `[307.8, 1.0, 432.4, 106.1]` |
| 235 | car | 0.6125 | `[303.4, 0.2, 417.0, 45.1]` |
| 318 | spoon | 0.5251 | `[0.5, 19.5, 53.4, 55.6]` |
| 318 | bottle | 0.4185 | `[194.8, 0.5, 317.2, 52.2]` |
| 325 | cell phone | 0.7289 | `[158.0, 1.7, 323.2, 188.7]` |
| 325 | spoon | 0.4970 | `[0.2, 18.7, 53.7, 52.4]` |
| 331 | cell phone | 0.4096 | `[132.2, 34.7, 311.6, 345.5]` |
| 344 | car | 0.4287 | `[111.5, 322.3, 297.8, 429.0]` |

## Registro completo de detecciones — YOLOv8s

| Fotograma | Clase | Confianza | Caja |
|---:|---|---:|---|
| 57 | person | 0.2724 | `[290.6, 377.3, 463.1, 431.2]` |
| 63 | boat | 0.5122 | `[280.3, 287.8, 478.9, 428.3]` |
| 70 | cell phone | 0.8696 | `[271.7, 189.1, 478.1, 427.2]` |
| 76 | cell phone | 0.9706 | `[268.2, 117.9, 453.5, 408.1]` |
| 82 | cell phone | 0.8753 | `[267.6, 50.0, 429.4, 299.9]` |
| 89 | cell phone | 0.8720 | `[274.1, 1.4, 413.2, 203.1]` |
| 94 | cell phone | 0.8612 | `[281.4, 0.3, 404.1, 138.3]` |
| 95 | cell phone | 0.8876 | `[282.4, 0.6, 403.5, 125.5]` |
| 101 | car | 0.7705 | `[283.6, 0.7, 397.6, 63.6]` |
| 184 | car | 0.3970 | `[158.2, 1.1, 263.8, 42.0]` |
| 188 | bottle | 0.4964 | `[146.4, 1.0, 263.7, 90.6]` |
| 188 | cell phone | 0.4448 | `[146.4, 1.4, 263.8, 90.6]` |
| 191 | cell phone | 0.6358 | `[138.0, 0.5, 268.5, 126.3]` |
| 197 | cell phone | 0.6624 | `[121.4, 1.4, 263.3, 206.2]` |
| 197 | suitcase | 0.5385 | `[316.6, 263.3, 499.7, 427.8]` |
| 203 | cell phone | 0.8445 | `[100.8, 25.7, 259.2, 311.4]` |
| 203 | suitcase | 0.6047 | `[316.0, 178.0, 491.4, 426.3]` |
| 210 | cell phone | 0.8016 | `[74.2, 116.9, 248.9, 426.8]` |
| 210 | suitcase | 0.7876 | `[312.7, 94.1, 474.5, 367.0]` |
| 216 | cell phone | 0.8766 | `[56.4, 204.5, 243.1, 427.3]` |
| 216 | cell phone | 0.4039 | `[307.7, 32.0, 460.9, 271.8]` |
| 223 | car | 0.8155 | `[304.5, 1.7, 445.0, 175.6]` |
| 223 | cell phone | 0.5861 | `[63.0, 325.2, 234.4, 428.4]` |
| 229 | car | 0.8506 | `[308.6, 1.3, 432.0, 106.2]` |
| 235 | car | 0.8298 | `[303.1, 1.5, 415.9, 44.2]` |
| 318 | cell phone | 0.5755 | `[194.0, 0.6, 318.3, 52.4]` |
| 325 | cell phone | 0.8743 | `[159.3, 1.2, 324.5, 189.1]` |
| 331 | cell phone | 0.8742 | `[132.1, 34.3, 311.5, 347.7]` |
| 337 | cell phone | 0.3700 | `[108.9, 146.2, 302.5, 428.1]` |
| 344 | car | 0.5171 | `[111.7, 323.0, 296.2, 429.2]` |

## Evidencia visual guardada

Se guardaron exactamente dos imágenes anotadas:

- `validacion_vision/yolov8n_fotograma_229_anotado.jpg`
- `validacion_vision/yolov8s_fotograma_229_anotado.jpg`

La revisión visual confirma que el objeto anotado en el fotograma 229 es un automóvil real. En los fotogramas 0, 6, 12, 19, 25 y 50 la escena está vacía; en el fotograma 63 aparece el primer automóvil visible de la muestra.

## Conclusión sobre las cero detecciones iniciales

Las cero detecciones de los primeros 20 fotogramas se deben a que esos fotogramas no contienen vehículos visibles. No indican un fallo del modelo, de OpenCV, de los pesos ni de la configuración: más adelante, ambos modelos producen inferencias reales sobre automóviles visibles.

El video presenta una vista cenital y vehículos de juguete o a escala, un dominio distinto de las imágenes viales convencionales usadas por los pesos COCO. Esto explica las clasificaciones no vehiculares erróneas (`cell phone`, `suitcase`, `spoon`, entre otras) y la variación de clase/confianza durante el recorrido del mismo objeto. Es una limitación de generalización del modelo preentrenado frente al contenido del video, no un bloqueo del entorno.

## Recomendación para el MVP

Para este video concreto, `yolov8s.pt` ofrece la detección vehicular más limpia y confiable: confianza media 0.6968 frente a 0.4735 y evita la duplicación `car`/`bus` observada con `yolov8n` en el fotograma anotado. Por ello se recomienda `yolov8s.pt` para la siguiente validación del MVP si se prioriza precisión de conteo. `yolov8n.pt` conserva mejor cobertura en esta muestra (12 frente a 6 detecciones vehiculares) y sigue siendo útil si la prioridad es velocidad o sensibilidad, pero requiere especial atención a falsas clases y doble conteo.

Esta comparación no reemplaza el modelo principal ni modifica configuración alguna. El contador puede pasar a validación sobre video: el stack técnico funciona y hay detecciones reales. Antes de considerarlo validado funcionalmente deben medirse continuidad de seguimiento, cruces de línea, deduplicación entre clases vehiculares y conteo contra una referencia manual, especialmente por el cambio de dominio del video.
