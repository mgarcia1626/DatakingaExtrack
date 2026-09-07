"""
upload_from_local.py - Lee los Excel de DataBase/ y sube a Supabase.

Uso:
  python upload_from_local.py              # sube todos los archivos en DataBase/
  python upload_from_local.py --dry-run    # muestra lo que subiria sin subir

Genera los Excel primero con:
  python main.py 01/01/2026 21/08/2026
"""
import os
import sys
import glob
import pandas as pd
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Importar funciones de Supabase y procesado
from datakinga.core.storage.supabase_client import get_client, insert_tickets, upsert_consumos
from datakinga.core.audit.pre_supabase_audit import run_pre_supabase_audit, print_audit_report

DRY_RUN = "--dry-run" in sys.argv

# ---------------------------------------------------------------------------
# Helpers de parseo (mismo que main_render.py)
# ---------------------------------------------------------------------------

def _parse_raw_excel(df_raw, nombre_sucursal=None):
    headers = df_raw.iloc[3].tolist()
    df = df_raw.iloc[4:].copy()
    df.columns = headers
    df = df.reset_index(drop=True)
    if nombre_sucursal is not None:
        df["Sucursal"] = nombre_sucursal
    return df


def _sucursal_de_archivo(nombre_archivo):
    """Extrae nombre de sucursal del nombre de archivo."""
    base = Path(nombre_archivo).stem  # sin extension
    partes = base.split("_")
    # consumos_SUCURSAL_DD_MM_YYYY -> partes[1:-3]
    # detalle_SUCURSAL_DD_MM_YYYY  -> partes[1:-3]
    if len(partes) >= 5:
        return " ".join(partes[1:-3]).upper()
    elif len(partes) >= 2:
        return " ".join(partes[1:]).upper()
    return base.upper()


def procesar_tickets(detalle_folder, cinta_folder):
    """Lee todos los Excel de Detalle/, parsea y combina."""
    archivos = sorted(glob.glob(str(Path(detalle_folder) / "*.xls*")))
    if not archivos:
        print(f"  ! No hay archivos en {detalle_folder}")
        return pd.DataFrame()

    # Leer cinta testigo para turnos
    df_cinta = None
    cinta_archivos = sorted(glob.glob(str(Path(cinta_folder) / "*.xls*")))
    if cinta_archivos:
        # Usar el ultimo (mas reciente)
        df_raw_c = pd.read_excel(cinta_archivos[-1], header=None)
        df_c = _parse_raw_excel(df_raw_c)
        df_c = df_c.dropna(how="all")
        col_map = {}
        for col in df_c.columns:
            u = str(col).upper().strip()
            if "MERO" in u:
                col_map[col] = "Numero"
            elif u == "TURNO":
                col_map[col] = "Turno"
        df_c = df_c.rename(columns=col_map)
        if "Numero" in df_c.columns and "Turno" in df_c.columns:
            df_c = df_c.dropna(subset=["Numero"])
            df_cinta = df_c[["Numero", "Turno"]]
            print(f"  Cinta Testigo: {len(df_cinta)} registros de turno")

    frames = []
    for archivo in archivos:
        sucursal = _sucursal_de_archivo(archivo)
        print(f"  Leyendo detalle: {Path(archivo).name} -> {sucursal}")
        df_raw = pd.read_excel(archivo, header=None)
        df = _parse_raw_excel(df_raw, nombre_sucursal=sucursal)

        # Eliminar columna Sucursal duplicada del excel
        cols_dup = [c for c in df.columns if str(c).strip().upper() == "SUCURSAL" and c != "Sucursal"]
        if cols_dup:
            df = df.drop(columns=cols_dup)

        num_col = next((c for c in df.columns if "mero" in str(c).lower()), None)
        if num_col:
            df = df.dropna(subset=[num_col])
        frames.append(df)

    if not frames:
        return pd.DataFrame()

    df_tickets = pd.concat(frames, ignore_index=True)

    # Agregar turno
    if df_cinta is not None:
        num_col = next((c for c in df_tickets.columns if "mero" in str(c).lower()), None)
        if num_col:
            cinta_merge = df_cinta.copy()
            cinta_merge.columns = [num_col, "Turno"]
            df_tickets = df_tickets.merge(cinta_merge, on=num_col, how="left")

    # Extraer Fecha/Hora de F.Cierre
    for col in df_tickets.columns:
        if "cierre" in str(col).lower():
            df_tickets[col] = pd.to_datetime(df_tickets[col], errors="coerce")
            df_tickets["Fecha"] = df_tickets[col].dt.date
            df_tickets["Hora"] = df_tickets[col].dt.time
            df_tickets = df_tickets.drop(columns=[col])
            break

    df_tickets = df_tickets.drop_duplicates()
    df_tickets = df_tickets[df_tickets["Sucursal"].notna()]
    print(f"  Total tickets procesados: {len(df_tickets)}")
    return df_tickets


def procesar_consumos(consumos_folder):
    """Lee todos los Excel de Consumos/, parsea y combina."""
    archivos = sorted(glob.glob(str(Path(consumos_folder) / "*.xls*")))
    if not archivos:
        print(f"  ! No hay archivos en {consumos_folder}")
        return pd.DataFrame()

    frames = []
    fecha_carga = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for archivo in archivos:
        sucursal = _sucursal_de_archivo(archivo)
        print(f"  Leyendo consumos: {Path(archivo).name} -> {sucursal}")
        df_raw = pd.read_excel(archivo, header=None)
        df = _parse_raw_excel(df_raw, nombre_sucursal=sucursal)

        data_cols = [c for c in df.columns if c != "Sucursal"]
        if len(data_cols) >= 3:
            df = df[data_cols[:3]].copy()
            df.columns = ["Familia", "Codigo", "Articulo"]
            df["Sucursal"] = sucursal
        else:
            print(f"  ! {sucursal}: formato inesperado")
            continue

        df = df.dropna(subset=["Codigo", "Articulo"])
        df["Fecha_Carga"] = fecha_carga
        frames.append(df)
        print(f"    {sucursal}: {len(df)} productos")

    if not frames:
        return pd.DataFrame()

    df_consumos = pd.concat(frames, ignore_index=True)
    print(f"  Total consumos procesados: {len(df_consumos)}")
    return df_consumos


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("UPLOAD FROM LOCAL - DataBase/ -> Supabase")
    print("=" * 60)
    if DRY_RUN:
        print("** DRY RUN - no se subira nada **")

    print("\n[1/4] Procesando Tickets...")
    df_tickets = procesar_tickets("DataBase/Detalle", "DataBase/Cinta")

    print("\n[2/4] Procesando Consumos...")
    df_consumos = procesar_consumos("DataBase/Consumos")

    print("\n[3/4] Auditoria pre-Supabase...")
    audit = run_pre_supabase_audit(df_tickets, df_consumos)
    print_audit_report(audit)

    strict_audit = os.getenv("AUDIT_STRICT", "1").strip().lower() not in {"0", "false", "no"}
    if strict_audit and not audit.get("ok", False):
        print("\nERROR: auditoria fallida. Carga cancelada, no se suben datos a Supabase.")
        return 1

    if not DRY_RUN:
        print("\n[4/4] Subiendo a Supabase...")
        supabase = get_client()
        if not df_tickets.empty:
            insert_tickets(supabase, df_tickets)
        if not df_consumos.empty:
            upsert_consumos(supabase, df_consumos)
        print("\nListo! Datos subidos a Supabase.")
    else:
        print(f"\n[DRY RUN] Tickets listos para subir: {len(df_tickets)}")
        print(f"[DRY RUN] Consumos listos para subir: {len(df_consumos)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

