# Especificación de Dominio para Codex (Módulo ESAL)

## Alcance
Implementar el motor de cálculo ESAL, modelos de datos de cargas y validadores. *NO programar interfaz visual ni módulos de cámara.*

## Modelos de Dominio (Entidades)
1. `AxleGroupType`: (enum SINGLE_STEERING, SINGLE_DUAL, TANDEM, TRIDEM)
2. `AxleGroupRecord`: peso (float), tipo (`AxleGroupType`).
3. `VehicleLoad`: compuesto por lista de `AxleGroupRecord`, estado fuente de datos.
4. `DataSource`: (enum WIM, STATIC, MANUAL, ESTIMATED, NORMATIVE, SIMULATED)

## Interfaces y Cálculos

- `calculate_axle_group_esal(group: AxleGroupRecord) -> float`
  *(Implementación Aprobada: Usa los denominadores 6.6, 8.2, 15.1, 21.8 según el tipo de grupo).*

- `calculate_truck_factor(vehicle: VehicleLoad) -> float`
  *(Implementación Aprobada: Sumatoria de `calculate_axle_group_esal` para todos los grupos del vehículo).*

- `calculate_vehicle_esal_by_gross_weight()`
  *(Estado: `PENDIENTE_CONFIRMACION` / Rechazado para uso genérico, no implementar en esta etapa).*

## Validaciones (Exceptions)
- Lanza `NegativeLoadError` si la carga < 0.
- Lanza `GrossWeightMismatchError` si suma de grupos de ejes != peso bruto (tolerancia 5%).

## Excluido del MVP
- Fórmulas de equivalencia de peso bruto vehicular a ESAL directo.
- Ecuaciones rigurosas AASHTO 93 (con SN y Pt).