"""
run_monthly.py - Ejecuta main.py mes a mes y genera un archivo unificado por sucursal.

Uso:
  python run_monthly.py 01/01/2026 21/08/2026
"""
import sys
import subprocess
import glob
import os
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path


SUCURSALES_COMBINAR = ["PASADENA", "COSTA_VERDE"]


def month_ranges(desde, hasta):
    chunks = []
    current = desde.replace(day=1)
    while current <= hasta:
        end = (current.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        end = min(end, hasta)
        start = max(current, desde)
        chunks.append((start, end))
        current = end + timedelta(days=1)
    return chunks


def combine_detalle(output_path="DataBase/tickets_unificado.xlsx"):
    """Combina todos los archivos de DataBase/Detalle/ de las sucursales permitidas en un unico Excel."""
    detalle_dir = Path("DataBase/Detalle")
    dfs = []
    archivos = sorted(detalle_dir.glob("*.xls*"))
    for f in archivos:
        nombre = f.stem.upper()
        permitido = any(nombre.startswith(suc) for suc in SUCURSALES_COMBINAR)
        if not permitido:
            continue
        try:
            df = pd.read_excel(f)
            df["_archivo"] = f.name
            dfs.append(df)
            print(f"  + {f.name}: {len(df)} filas")
        except Exception as e:
            print(f"  ! Error leyendo {f.name}: {e}")
    if not dfs:
        print("  No se encontraron archivos para combinar.")
        return
    combined = pd.concat(dfs, ignore_index=True)
    combined.drop(columns=["_archivo"], inplace=True)
    combined.drop_duplicates(inplace=True)
    combined.to_excel(output_path, index=False)
    print(f"\n Archivo unificado guardado: {output_path} ({len(combined)} filas totales)")


if len(sys.argv) < 3:
    print("Uso: python run_monthly.py DD/MM/YYYY DD/MM/YYYY")
    sys.exit(1)

fecha_desde = datetime.strptime(sys.argv[1], "%d/%m/%Y")
fecha_hasta = datetime.strptime(sys.argv[2], "%d/%m/%Y")
chunks = month_ranges(fecha_desde, fecha_hasta)

print(f"Procesando {len(chunks)} mes(es)...")

for i, (d, h) in enumerate(chunks, 1):
    ds = d.strftime("%d/%m/%Y")
    hs = h.strftime("%d/%m/%Y")
    print(f"\n{'='*60}")
    print(f"MES {i}/{len(chunks)}: {ds} -> {hs}")
    print("="*60)
    result = subprocess.run(["python", "main.py", ds, hs])
    if result.returncode != 0:
        print(f"  ! Error en {ds}->{hs}, continuando...")

print("\nTodos los meses completados.")
print("\nCombinando archivos de Detalle para PASADENA y COSTA_VERDE...")
combine_detalle()
print("\nPara subir a Supabase ejecuta: python upload_from_local.py")