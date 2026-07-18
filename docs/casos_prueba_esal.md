# Casos de Validación y Prueba

## Caso 1: Equivalencias por Grupo de Ejes (Aprobado)
Extraído de las memorias de cálculo del archivo `3er parcial.xlsx` (Fórmula `EE = (P / P_std)^n`):
- Eje delantero simple (P=7tn, P_std=6.6tn, n=4) -> `EE = (7/6.6)^4 = 1.265`
- Eje trasero simple (P=11tn, P_std=8.2tn, n=4) -> `EE = (11/8.2)^4 = 3.238`
- Eje trasero tándem (P=18tn, P_std=15.1tn, n=4) -> `EE = (18/15.1)^4 = 2.019`
- Eje trasero trídem (P=25tn, P_std=21.8tn, n=3.9) -> `EE = (25/21.8)^3.9 = 1.706`

## Caso 2: Error Histórico Identificado (Uso de Fórmulas por Categoría)
En las diapositivas de clase (Pág 66 y 67), se identificaron problemas de regresiones dependientes de flota que no deben automatizarse.
- El cálculo `(22 / 22.98)^4.22 = 0.83` asume 22 tn como **Peso Bruto Vehicular** para un vehículo "Muy Pesado", lo que da 0.83 ESALs para el vehículo entero.
- Posteriormente, en la Pág 67, existe un error tipográfico en la clase donde se asume el factor de la categoría Medianos como `4.14` en lugar del calculado `3.61`.
- El total final proyectado de la clase era 73,950,655 ESALs, pero debido a que proviene de regresiones estáticas y errores aritméticos en los supuestos, **no debe usarse como test unitario para el motor dinámico ESAL**.
