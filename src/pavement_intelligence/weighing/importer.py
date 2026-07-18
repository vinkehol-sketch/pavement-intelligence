"""
Importador de datos de pesaje vehicular.
Soporta: CSV, Excel, entrada manual, datos simulados.
Todos los datos se normalizan a unidades SI (kN).
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional
import csv
from datetime import datetime

from ..domain.weighing.models import WIMRecord, AxleLoad, WeighingSource


class WeighingImporter:
    """
    Importador de registros de pesaje desde múltiples fuentes.
    Convierte todos los datos a unidades SI (kN).
    """

    def from_csv(
        self,
        file_path: str | Path,
        delimiter: str = ",",
        encoding: str = "utf-8",
    ) -> list[WIMRecord]:
        """
        Importa registros de pesaje desde un archivo CSV.

        Formato esperado de columnas:
        timestamp, category_id, gross_weight_kn, axle1_type, axle1_load_kn,
        axle2_type, axle2_load_kn, ..., lane, speed_kmh, notes

        Retorna lista de WIMRecord con source=CSV_FILE.
        """
        records = []
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Archivo CSV no encontrado: {path}")

        with open(path, "r", encoding=encoding, newline="") as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            for row in reader:
                record = self._parse_csv_row(row, str(path.name))
                if record:
                    records.append(record)
        return records

    def from_excel(
        self,
        file_path: str | Path,
        sheet_name: str = 0,
    ) -> list[WIMRecord]:
        """Importa registros de pesaje desde un archivo Excel (.xlsx)."""
        import pandas as pd
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Archivo Excel no encontrado: {path}")
        df = pd.read_excel(path, sheet_name=sheet_name)
        records = []
        for _, row in df.iterrows():
            record = self._parse_csv_row(dict(row), str(path.name))
            if record:
                records.append(record)
        return records

    def _parse_csv_row(self, row: dict, source_file: str) -> Optional[WIMRecord]:
        """Parsea una fila CSV/Excel y crea un WIMRecord."""
        try:
            axle_loads = []
            axle_num = 1
            while f"axle{axle_num}_load_kn" in row:
                load = float(row.get(f"axle{axle_num}_load_kn", 0) or 0)
                atype = str(row.get(f"axle{axle_num}_type", "simple_dual"))
                axle_loads.append(AxleLoad(
                    axle_number=axle_num,
                    axle_type=atype,
                    load_kn=load,
                ))
                axle_num += 1

            ts_raw = row.get("timestamp", "")
            ts = datetime.fromisoformat(str(ts_raw)) if ts_raw else None

            return WIMRecord(
                source=WeighingSource.CSV_FILE,
                timestamp=ts,
                vehicle_category_id=str(row.get("category_id", "")),
                gross_weight_kn=float(row.get("gross_weight_kn", 0) or 0),
                axle_loads=axle_loads,
                speed_kmh=float(row.get("speed_kmh", 0) or 0) or None,
                lane=int(row.get("lane", 1) or 1),
                confidence=1.0,
                data_quality="importado",
                original_file=source_file,
                notes=str(row.get("notes", "")),
            )
        except Exception:
            return None  # Fila inválida, se omite
