# Clasificación Vehicular (Bolivia)

De acuerdo a la normativa y formatos de la **Administradora Boliviana de Carreteras (ABC)** (ref. Planillas de aforo CHIMATE - MAPIRI / CAIHUASI), la clasificación vehicular se estructura en 13 grupos operativos orientados a la recolección de campo, que posteriormente se agrupan en Livianos, Buses y Camiones para el cálculo de ESAL.

## 1. Clasificación Oficial (Formulario de Aforo ABC)

### LIVIANOS
1. **Automóviles, Vagonetas y Jeep**
2. **Camionetas** (Hasta 2 Toneladas)

### BUSES
3. **Minibuses** (7 a 15 asientos)
4. **Microbuses de 2 ejes** (16 a 21 asientos)
5. **Buses Medianos de 2 ejes** (22 a 35 asientos)
6. **Buses Grandes de 3 ejes o más** (36 asientos o más)

### CAMIONES
7. **Camión Mediano de 2 ejes** (Hasta 10 Toneladas)
8. **Camión Grande de 2 ejes**
9. **Camión Grande de 3 ejes**
10. **Camión Semiremolque**
11. **Camión Remolque**

### OTROS
12. **Motocicletas**
13. **Otros vehículos** (Agricolas, Tracción animal)

---

## 2. Correspondencia para MVP

Para mantener el sistema adaptable entre la visión artificial y los cálculos de ingeniería, se establecen las siguientes capas de clasificación:

### A. Clase Visual (Detección YOLO / COCO)
* `car` (Automóviles, Vagonetas, Jeep, Camionetas)
* `bus` (Microbuses, Minibuses, Buses grandes)
* `truck` (Camiones medianos, grandes, articulados)
* `motorcycle` (Motos)

### B. Categoría Simplificada de Aforo (Interfaz de Usuario)
Agrupación de las 13 categorías en 4 grupos macro para importación genérica:
1. **LIVIANOS** (Auto, Vagoneta, Camioneta)
2. **BUSES** (Minibus, Microbus, Bus)
3. **CAMIONES** (Rígidos, Semiremolques, Remolques)
4. **OTROS** (Motos)

### C. Configuración de Ejes (DS 24327 - Pesos y Dimensiones)
Para cálculos futuros de ESAL, los camiones deben mapearse a las siguientes configuraciones legales en Bolivia:
* **Eje sencillo de 2 llantas** (Max 7.00 t)
* **Eje sencillo de 4 llantas** (Max 11.00 t)
* **Eje tipo tándem** (Max 18.00 t)
* **Eje tipo trídem** (Max 25.00 t)

> **Nota para la implementación:** El código Python debe manejar enums separados para `VisionClass` y `VehicleCategory`, con un mapeo explícito hacia las clasificaciones oficiales de la ABC.
