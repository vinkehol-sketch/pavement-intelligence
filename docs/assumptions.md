# Hipótesis, Supuestos y Limitaciones del Sistema

## 1. Datos Sintéticos y Demostrativos
- El caso de estudio es ficticio y demostrativo (marcado como SIMULADO).
- CBR de diseño = 5%, Tasa de crecimiento = 4%, Periodo = 20 años.

## 2. Visión Artificial
- Detección usa YOLOv8 preentrenado (COCO).
- Mapeo COCO -> ABC Bolivia es una aproximación inicial.
- Placas son procesadas asumiendo resolución mínima 720p.

## 3. Ingeniería
- Factor de distribución direccional (FDD) = 0.50 por defecto.
- Método de pavimento flexible según AASHTO 93.
- Módulo resiliente (MR) en psi = 1500 x CBR (para CBR < 10%).

## 4. Privacidad
- Placas se guardan como hash SHA-256 (8 caracteres).
