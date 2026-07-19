# Guía de Validación y Checklist de Pruebas Manuales

Este documento establece los pasos prácticos de verificación manual que el arquitecto técnico o el equipo de QA deben realizar para validar la correcta integración de fuentes reales de video y cámara local en el Centro de Monitoreo de Tránsito.

---

## 1. Pruebas con Video Local Pregrabado

Utilizar el video de prueba versionado en `data/samples/ui/assets/traffic_monitoring_demo.mp4`.

* **[ ] Paso 1: Carga de Archivo**
  * *Acción*: Elegir `Video pregrabado`, seleccionar el video local y pulsar `Iniciar análisis`.
  * *Resultado esperado*: El Centro de Monitoreo detecta el archivo, obtiene sus metadatos (resolución y FPS correctos) y muestra el primer fotograma en reposo con los overlays de la línea virtual de conteo dibujados correctamente.
* **[ ] Paso 2: Acción - Iniciar análisis**
  * *Acción*: Presionar el botón `Iniciar análisis`.
  * *Resultado esperado*:
    * El análisis real se inicia sin mezclar métricas sintéticas; el FPS depende del hardware.
    * Se muestran rectángulos de seguimiento (bounding boxes) que siguen dinámicamente a los vehículos en escena.
    * El texto mono de diagnóstico de FPS y latencia se actualiza en tiempo real.
* **[ ] Paso 3: Acción - Pausar (Pause)**
  * *Acción*: Con el video procesándose, presionar el botón `Pausar`.
  * *Resultado esperado*:
    * La reproducción se detiene instantáneamente.
    * El canvas visual retiene el último fotograma procesado.
    * La fuente permanece abierta en la posición actual.
    * No se genera ninguna recarga infinita de la página Streamlit.
* **[ ] Paso 4: Acción - Continuar (Continue)**
  * *Acción*: Presionar `Continuar`.
  * *Resultado esperado*: La reproducción se reanuda de forma fluida desde el mismo fotograma y marca de tiempo en que fue pausado.
* **[ ] Paso 5: Acción - Reiniciar (Reset)**
  * *Acción*: Presionar el botón `Reiniciar`.
  * *Resultado esperado*:
    * El puntero de video vuelve al fotograma `0`.
    * Los contadores de vehículos acumulados y en escena se reestablecen a cero.
    * Se crean detector, tracker, contador, eventos y pipeline nuevos para el lote reiniciado.
    * La pantalla actualiza los componentes en reposo.
* **[ ] Paso 6: Acción - Finalización (Fin de Video)**
  * *Acción*: Dejar que el video reproduzca hasta el final de su duración.
  * *Resultado esperado*:
    * Al completarse la lectura, el fragmento deja de programar procesamiento.
    * Se muestra la advertencia `Fin de la fuente.`.
    * El estado de reproducción cambia a inactivo y el descriptor del archivo de video se cierra.

---

## 2. Pruebas con Cámara Local (Canal 0)

Asegurar que la computadora cuente con una cámara web disponible y habilitada.

* **[ ] Paso 7: Apertura de Cámara**
  * *Acción*: Seleccionar `Cámara en vivo`, elegir índice 0 o 1 y pulsar `Iniciar cámara`.
  * *Resultado esperado*:
    * El sistema invoca exitosamente la cámara en el índice `0`.
    * Se activa el led físico de la cámara web.
    * Comienza la transmisión en vivo de frames anotados.
* **[ ] Paso 8: Liberación de Cámara**
  * *Acción*: Presionar `Detener cámara` o cambiar la fuente de análisis.
  * *Resultado esperado*:
    * El stream se detiene de forma inmediata.
    * El led físico de la cámara web se apaga, indicando que el descriptor `cv2.VideoCapture` se ha liberado correctamente.
    * La cámara queda disponible al instante para ser utilizada por otras aplicaciones del sistema operativo.
  * *Nota*: `Pausar` no libera la cámara; permite continuar desde la posición actual.

---

## 3. Pruebas de Inferencia, Conteo e Integración

* **[ ] Paso 9: Validación de Frames Anotados**
  * *Acción*: Observar los vehículos cruzando la línea virtual en pantalla.
  * *Resultado esperado*:
    * Cada vehículo detectado tiene un recuadro con su `ID` de seguimiento y su categoría vial preliminar (`Auto`, `Bus`, `Camión`).
    * Al cruzar la línea virtual, el color del contorno de la caja cambia o se dispara visualmente la actualización del indicador de conteo.
* **[ ] Paso 10: Validación de Conteos**
  * *Acción*: Contar visualmente los vehículos que cruzan y comparar con la métrica `Total Acumulado`.
  * *Resultado esperado*: El acumulado del contador coincide plenamente con los cruces físicos observados.
* **[ ] Paso 11: Navegación y Traspaso a Revisión**
  * *Acción*: Presionar `Finalizar y revisar`.
  * *Resultado esperado*:
    * Se navega a la página de revisión.
    * Los eventos reales capturados se listan en la tabla con estado inicial `sin_revisar` y asociados a su `track_id` inmutable.
    * Las variables sintéticas demostrativas previas se han limpiado de la sesión de manera segura.
    * El lote pasa por `build_traffic_event_batch`, queda pendiente y no se aprueba ni se transfiere a TPDA automáticamente.

---

## 4. Pruebas de Comportamiento Frente a Errores

* **[ ] Paso 12: Cámara No Disponible (Dispositivo Ocupado)**
  * *Acción*: Abrir la cámara web en otra aplicación (ej. aplicación Cámara de Windows) e intentar iniciar el análisis en Streamlit.
  * *Resultado esperado*:
    * El sistema captura el fallo de inicialización.
    * Se despliega un banner rojo: `st.error("La cámara local 0 no está disponible.")`.
    * La aplicación Streamlit no sufre segmentación de memoria ni cierres forzados.
* **[ ] Paso 13: Desconexión de Dispositivo en Ejecución**
  * *Acción*: Desconectar físicamente la cámara USB a mitad del análisis en vivo.
  * *Resultado esperado*:
    * El lector de frames devuelve `success = False`.
    * El controlador cierra la fuente explícitamente, cambia a estado final/error y Streamlit muestra la advertencia sin un bucle bloqueante.

La cámara física continúa pendiente de validación manual en un equipo con dispositivo y permisos disponibles.
