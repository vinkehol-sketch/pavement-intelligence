# Plan de Validación ESAL

1. **Pruebas Unitarias**:
   - Computar ESAL para todas las configuraciones de ejes dadas cargas conocidas y asertar con los resultados del Excel académico.
   - Validar que el parseo de CSV detecte y levante excepciones ante cargas negativas o suma de ejes inválida.

2. **Pruebas de Integración**:
   - Simular un flujo de objetos Vehículo integrando aforo + asignación de peso estático, y verificar que el TPDA ponderado genere el Factor Camión correcto.
   
3. **Casos Manuales**:
   - Cargar un Excel histórico en la interfaz y comprobar que la tabla de salida coincide exactamente con las planillas ABC del proyecto original (ej. CHIMATE - MAPIRI).
