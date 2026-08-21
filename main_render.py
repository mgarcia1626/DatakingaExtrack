"""
DATAKINGA - Orquestador para Render
Usa Playwright (Chromium headless) + Supabase
Sin disco, sin SQLite, sin Edge.

Uso:
  python main_render.py                        # ayer -> hoy
  python main_render.py 01/01/2026 09/08/2026  # rango manual
"""
import os
import sys
import time
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from FunctionsGrouping.extraction_playwright import (
    login,
    extraer_cinta_testigo,
    extraer_tickets_detalle,
    extraer_consumos,
)
from FunctionsGrouping.supabase_client import (
    get_client,
    insert_tickets,
    upsert_consumos,
)

load_dotenv()

# ---------------------------------------------------------------------------
# Configuracion de fechas
# ---------------------------------------------------------------------------
if len(sys.argv) >= 3:
    try:
        fecha_desde = datetime.strptime(sys.argv[1], '%d/%m/%Y')
        fecha_hasta = datetime.strptime(sys.argv[2], '%d/%m/%Y')
        print(f"Modo manual: {sys.argv[1]} -> {sys.argv[2]}")
    except ValueError:
        print("Error: formato de fecha invalido. Use DD/MM/YYYY DD/MM/YYYY")
        sys.exit(1)
else:
    fecha_desde = datetime.now() - timedelta(days=1)
    fecha_hasta = datetime.now()
    print(f"Modo automatico: {fecha_desde.strftime('%d/%m/%Y')} -> {fecha_hasta.strftime('%d/%m/%Y')}")


# ---------------------------------------------------------------------------
# Procesadores de DataFrames crudos
# ---------------------------------------------------------------------------

def _parse_raw_excel(df_raw: pd.DataFrame, nombre_sucursal: str = None) -> pd.DataFrame:
    """
    Convierte un Excel crudo (header en fila 3, datos desde fila 4) en DataFrame limpio.
    Si nombre_sucursal no es None, agrega/sobreescribe la columna Sucursal.
    """
    headers = df_raw.iloc[3].tolist()
    df = df_raw.iloc[4:].copy()
    df.columns = headers
    df = df.reset_index(drop=True)
    if nombre_sucursal is not None:
        df['Sucursal'] = nombre_sucursal
    return df


def procesar_cinta(df_raw: pd.DataFrame) -> pd.DataFrame | None:
    """Parsea cinta testigo cruda y retorna DataFrame con Numero y Turno."""
    if df_raw is None:
        return None
    df = _parse_raw_excel(df_raw)
    df = df.dropna(how='all')

    # Normalizar nombre de columnas
    col_map = {}
    for col in df.columns:
        col_upper = str(col).upper().strip()
        if 'MERO' in col_upper or col_upper == 'NUMERO':
            col_map[col] = 'Numero'
        elif col_upper == 'TURNO':
            col_map[col] = 'Turno'
    df = df.rename(columns=col_map)

    if 'Numero' not in df.columns or 'Turno' not in df.columns:
        print(f"   ! Cinta: columnas esperadas no encontradas. Disponibles: {list(df.columns)}")
        return None

    df = df.dropna(subset=['Numero'])
    print(f"   v Cinta Testigo: {len(df)} registros")
    return df[['Numero', 'Turno']]


def procesar_tickets(tickets_raw: list, df_cinta: pd.DataFrame | None) -> pd.DataFrame:
    """
    Procesa lista de (sucursal, DataFrame_crudo) de tickets.
    Agrega Turno desde cinta testigo y extrae Fecha/Hora de F.Cierre.
    """
    frames = []
    for nombre_sucursal, df_raw in tickets_raw:
        df = _parse_raw_excel(df_raw, nombre_sucursal=nombre_sucursal)

        # Eliminar columna Sucursal si viene del Excel (viene vacia)
        cols_excel = [c for c in df.columns if str(c).strip().upper() == 'SUCURSAL' and c != 'Sucursal']
        if cols_excel:
            df = df.drop(columns=cols_excel)

        df = df.dropna(subset=['Número'] if 'Número' in df.columns else [])
        frames.append(df)

    if not frames:
        return pd.DataFrame()

    df_tickets = pd.concat(frames, ignore_index=True)

    # Agregar Turno desde Cinta Testigo
    if df_cinta is not None:
        numero_col = None
        for col in df_tickets.columns:
            if 'mero' in str(col).lower() or str(col).upper() == 'NUMERO':
                numero_col = col
                break
        if numero_col:
            df_cinta_merge = df_cinta.copy()
            df_cinta_merge.columns = [numero_col, 'Turno']
            df_tickets = df_tickets.merge(df_cinta_merge, on=numero_col, how='left')
            registros_con_turno = df_tickets['Turno'].notna().sum()
            print(f"   v {registros_con_turno} registros con Turno asignado")
        else:
            df_tickets['Turno'] = None
    else:
        df_tickets['Turno'] = None

    # Extraer Fecha y Hora de F.Cierre
    for col in df_tickets.columns:
        if 'cierre' in str(col).lower():
            df_tickets[col] = pd.to_datetime(df_tickets[col], errors='coerce')
            df_tickets['Fecha'] = df_tickets[col].dt.date
            df_tickets['Hora'] = df_tickets[col].dt.time
            df_tickets = df_tickets.drop(columns=[col])
            print(f"   v Fecha/Hora extraidas de '{col}'")
            break

    # Quitar duplicados internos
    df_tickets = df_tickets.drop_duplicates()
    df_tickets = df_tickets[df_tickets['Sucursal'].notna()]

    print(f"   v Tickets procesados: {len(df_tickets)} registros validos")
    return df_tickets


def procesar_consumos(consumos_raw: list) -> pd.DataFrame:
    """
    Procesa lista de (sucursal, DataFrame_crudo) de consumos.
    Retorna DataFrame con Familia, Codigo, Articulo, Sucursal, Fecha_Carga.
    """
    frames = []
    fecha_carga = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    for nombre_sucursal, df_raw in consumos_raw:
        df = _parse_raw_excel(df_raw, nombre_sucursal=nombre_sucursal)

        # Mantener solo primeras 3 columnas de datos + Sucursal
        data_cols = [c for c in df.columns if c != 'Sucursal']
        if len(data_cols) >= 3:
            df = df[data_cols[:3]].copy()
            df.columns = ['Familia', 'Codigo', 'Articulo']
            df['Sucursal'] = nombre_sucursal
        else:
            print(f"   ! {nombre_sucursal}: formato inesperado, columnas: {list(df.columns)}")
            continue

        df = df.dropna(subset=['Codigo', 'Articulo'])
        df['Fecha_Carga'] = fecha_carga
        frames.append(df)
        print(f"   v {nombre_sucursal}: {len(df)} productos")

    if not frames:
        return pd.DataFrame()

    df_consumos = pd.concat(frames, ignore_index=True)
    print(f"   v Consumos procesados: {len(df_consumos)} registros totales")
    return df_consumos


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _month_ranges(desde: datetime, hasta: datetime):
    """Split a date range into monthly chunks."""
    chunks = []
    current = desde.replace(day=1)
    while current <= hasta:
        chunk_end = (current.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        chunk_end = min(chunk_end, hasta)
        chunks.append((current if current >= desde else desde, chunk_end))
        current = chunk_end + timedelta(days=1)
    return chunks


def _make_browser(p):
    browser = p.chromium.launch(
        headless=True,
        args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-blink-features=AutomationControlled'],
    )
    context = browser.new_context(
        accept_downloads=True,
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    )
    return browser, context.new_page()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 70)
    print("DATAKINGA - EXTRACCION PARA RENDER")
    print("=" * 70)

    username = os.getenv('DATAKINGA_USER')
    password = os.getenv('DATAKINGA_PASSWORD')
    if not username or not password:
        print("ERROR: Define DATAKINGA_USER y DATAKINGA_PASSWORD en .env")
        sys.exit(1)

    supabase = get_client()
    print("v Supabase client inicializado")

    chunks = _month_ranges(fecha_desde, fecha_hasta)
    print(f"Procesando {len(chunks)} mes(es): " + ", ".join(f"{d.strftime('%d/%m/%Y')}->{h.strftime('%d/%m/%Y')}" for d, h in chunks))

    for chunk_idx, (chunk_desde, chunk_hasta) in enumerate(chunks, 1):
        print(f"\n{'='*70}")
        print(f"BLOQUE {chunk_idx}/{len(chunks)}: {chunk_desde.strftime('%d/%m/%Y')} -> {chunk_hasta.strftime('%d/%m/%Y')}")
        print("=" * 70)

        with sync_playwright() as p:
            browser, page = _make_browser(p)
            try:
                login(page, username, password)

                print("\n--- CINTA TESTIGO ---")
                df_cinta_raw = extraer_cinta_testigo(page, chunk_desde, chunk_hasta)
                df_cinta = procesar_cinta(df_cinta_raw)

                print("\n--- TICKETS CON DETALLE ---")
                tickets_raw = extraer_tickets_detalle(page, chunk_desde, chunk_hasta)
                df_tickets = procesar_tickets(tickets_raw, df_cinta)

                print("\n--- CONSUMOS ---")
                consumos_raw = extraer_consumos(page, chunk_desde, chunk_hasta)
                df_consumos = procesar_consumos(consumos_raw)

            except Exception as e:
                import traceback
                print(f"\nERROR en bloque {chunk_idx}: {e}")
                traceback.print_exc()
                print("Continuando con el siguiente bloque...")
                browser.close()
                continue
            finally:
                browser.close()
                print("\n v Navegador cerrado")

        print("\n--- GUARDANDO EN SUPABASE ---")
        if not df_tickets.empty:
            insert_tickets(supabase, df_tickets)
        if not df_consumos.empty:
            upsert_consumos(supabase, df_consumos)

    print("\n" + "=" * 70)
    print("PROCESO COMPLETO FINALIZADO")
    print("=" * 70)


if __name__ == "__main__":
    main()
