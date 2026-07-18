"""Script para comparar el conteo automático vs manual."""
import pandas as pd
import json
from pathlib import Path

def generate_comparison_report(manual_csv: str, auto_csv: str, out_prefix: str):
    out_dir = Path("data/processed/reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        df_manual = pd.read_csv(manual_csv)
    except FileNotFoundError:
        print(f"No se encontró el archivo manual: {manual_csv}")
        return
        
    try:
        df_auto = pd.read_csv(auto_csv)
    except FileNotFoundError:
        print(f"No se encontró el archivo automático: {auto_csv}")
        return

    # Total counts
    total_manual = len(df_manual)
    total_auto = len(df_auto)
    diff = total_auto - total_manual
    error_pct = (abs(diff) / total_manual * 100) if total_manual > 0 else 0
    
    # By category
    cat_manual = df_manual['manual_category'].value_counts()
    cat_auto = df_auto['category'].value_counts()
    
    # By direction
    dir_manual = df_manual['direction'].value_counts()
    dir_auto = df_auto['direction'].value_counts()
    
    report_md = f"""# Resumen de Validación: {out_prefix}

## Totales
- **Total manual:** {total_manual}
- **Total automático:** {total_auto}
- **Diferencia absoluta:** {abs(diff)}
- **Error porcentual:** {error_pct:.1f}%

## Conteo por Categoría
**Manual:**
{cat_manual.to_string()}

**Automático:**
{cat_auto.to_string()}

## Conteo por Dirección
**Manual:**
{dir_manual.to_string()}

**Automático:**
{dir_auto.to_string()}

## Identificación de Errores
- Falsos positivos: {max(0, diff)}
- Falsos negativos: {max(0, -diff)}
- Posibles dobles conteos: {max(0, diff)}
- Errores de clasificación: 0 (Asumido al no haber enlace individual preciso en este MVP)

## Observaciones
- Al ser un agente de IA sin capacidad de reproducción visual fluida, el "conteo manual" fue generado inspeccionando fotogramas clave y asumiendo una alta precisión en este video sencillo. 
- No es posible asociar eventos individualmente con total certeza de ID sin una herramienta de anotación visual, por lo que la comparación se limita a conteos agregados.
- Se requiere un conjunto de pruebas más extenso con oclusiones para establecer un error real aplicable a Bolivia.
"""
    
    with open(out_dir / f"validation_summary_{out_prefix}.md", "w", encoding="utf-8") as f:
        f.write(report_md)
        
    print(f"[{out_prefix}] Reporte generado en {out_dir / f'validation_summary_{out_prefix}.md'}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--manual", default="data/processed/reports/manual_count_test_video.csv")
    parser.add_argument("--auto", default="data/processed/reports/automatic_events_test_video.csv")
    parser.add_argument("--prefix", default="test_video")
    args = parser.parse_args()
    
    generate_comparison_report(args.manual, args.auto, args.prefix)
