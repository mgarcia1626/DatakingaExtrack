"""
DATAKINGA - Orquestador para Render
Usa requests + BeautifulSoup (sin Playwright, sin navegador).
Extrae Pasadena y Junin desde datakinga.cloudsysbar.com

Uso:
  python main_render.py                        # ayer -> hoy
  python main_render.py 01/01/2026 09/08/2026  # rango manual
"""
import os
import sys
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv

from FunctionsGrouping.extraction_new_site import (
    login,
    extraer_tickets,
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
        fecha_desde = datetime.strptime(sys.argv[1], "%d/%m/%Y")
        fecha_hasta = datetime.strptime(sys.argv[2], "%d/%m/%Y")
        print(f"Modo manual: {sys.argv[1]} -> {sys.argv[2]}")
    except ValueError:
        print("Error: formato de fecha invalido. Use DD/MM/YYYY DD/MM/YYYY")
        sys.exit(1)
else:
    fecha_desde = datetime.now() - timedelta(days=1)
    fecha_hasta = datetime.now()
    print(f"Modo automatico: {fecha_desde.strftime('%d/%m/%Y')} -> {fecha_hasta.strftime('%d/%m/%Y')}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _month_ranges(desde: datetime, hasta: datetime):
    chunks = []
    current = desde.replace(day=1)
    while current <= hasta:
        chunk_end = (current.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        chunk_end = min(chunk_end, hasta)
        chunks.append((current if current >= desde else desde, chunk_end))
        current = chunk_end + timedelta(days=1)
    return chunks


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 70)
    print("DATAKINGA - EXTRACCION PARA RENDER (nuevo sitio)")
    print("=" * 70)

    supabase = get_client()
    print("v Supabase client inicializado")

    chunks = _month_ranges(fecha_desde, fecha_hasta)
    print(f"Procesando {len(chunks)} mes(es): " + ", ".join(
        f"{d.strftime('%d/%m/%Y')}->{h.strftime('%d/%m/%Y')}" for d, h in chunks
    ))

    for chunk_idx, (chunk_desde, chunk_hasta) in enumerate(chunks, 1):
        print(f"\n{'='*70}")
        print(f"BLOQUE {chunk_idx}/{len(chunks)}: {chunk_desde.strftime('%d/%m/%Y')} -> {chunk_hasta.strftime('%d/%m/%Y')}")
        print("=" * 70)

        try:
            session = login()

            print("\n--- TICKETS DETALLE ---")
            df_tickets = extraer_tickets(session, chunk_desde, chunk_hasta)

            print("\n--- CONSUMOS ---")
            df_consumos = extraer_consumos(session, chunk_desde, chunk_hasta)

        except Exception as e:
            import traceback
            print(f"\nERROR en bloque {chunk_idx}: {e}")
            traceback.print_exc()
            print("Continuando con el siguiente bloque...")
            continue

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
