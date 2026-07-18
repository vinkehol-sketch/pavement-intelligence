# Configuraciones de Ejes

Para el cálculo preciso de cargas equivalentes, es fundamental modelar el vehículo separando la categoría vehicular de la configuración física de sus ejes.

## Tipos de Ejes
De acuerdo a la normativa boliviana (Ley 441, DS 24327):
1. **Eje Simple (Sencillo)**:
   - **1RS**: Rueda Simple (2 llantas). Peso máximo: 7.0 tn - 7.5 tn.
   - **1RD**: Rueda Doble (4 llantas). Peso máximo: 10.5 tn - 11.5 tn.
2. **Eje Tándem**:
   - Constituido por dos ejes sencillos. Ej. 4 llantas, 6 llantas, 8 llantas. Peso máximo entre 14.5 tn y 18.5 tn.
3. **Eje Trídem**:
   - Constituido por tres ejes sencillos. Ej. 6 llantas a 12 llantas. Peso máximo entre 17.0 tn y 25.5 tn.

## Tipos de Vehículos
- **Camión Rígido**: Chasis único.
- **Tractocamión y Semirremolque**: Vehículo articulado, el semirremolque apoya sobre el tractor.
- **Remolque**: Vehículo arrastrado que soporta toda su propia carga.

## Entidades de Dominio
Debe existir independencia estricta entre:
- Categoría Vehicular ABC.
- Configuración de ejes (ej. 1RS-1RD, 1RS-2RD, etc.).
- Número de ejes.
- Tipo de rueda.
- Carga medida y Peso Bruto.
