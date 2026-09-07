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
import threading
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv, set_key

from datakinga.core.extractors.new_site_extraction import (
    login,
    extraer_tickets,
    extraer_consumos,
    SUCURSALES,
)
from datakinga.core.storage.supabase_client import (
    get_client,
    insert_tickets,
    upsert_consumos,
)
from datakinga.core.audit.pre_supabase_audit import run_pre_supabase_audit, print_audit_report

load_dotenv()

# Archivo .env (para persistir LAST_RUN_TIME / LAST_RUN_STATUS entre procesos)
ENV_FILE = Path(".env")

# Re-entrancy guard: evita correr dos extracciones en paralelo dentro del
# mismo proceso (por ejemplo, dos clicks seguidos del boton en Streamlit).
_extraction_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Configuracion de fechas
# ---------------------------------------------------------------------------
def resolve_date_range(argv=None):
    """Resuelve fecha_desde / fecha_hasta a partir de argv (CLI) o default.

    Si argv trae al menos 2 elementos ademas del nombre del script
    (argv[1], argv[2]) con formato DD/MM/YYYY, se usa ese rango manual.
    En caso contrario, se usa el rango por defecto "ayer -> hoy".
    """
    if argv is not None and len(argv) >= 3:
        try:
            fecha_desde = datetime.strptime(argv[1], "%d/%m/%Y")
            fecha_hasta = datetime.strptime(argv[2], "%d/%m/%Y")
            print(f"Modo manual: {argv[1]} -> {argv[2]}")
        except ValueError:
            print("Error: formato de fecha invalido. Use DD/MM/YYYY DD/MM/YYYY")
            sys.exit(1)
    else:
        fecha_desde = datetime.now() - timedelta(days=1)
        fecha_hasta = datetime.now()
        print(f"Modo automatico: {fecha_desde.strftime('%d/%m/%Y')} -> {fecha_hasta.strftime('%d/%m/%Y')}")

    return fecha_desde, fecha_hasta


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


def _save_last_run(success: bool):
    """Guarda LAST_RUN_TIME / LAST_RUN_STATUS en .env y en os.environ.

    Se setea tambien en os.environ para que, dentro del mismo proceso
    (por ejemplo un servidor Streamlit de larga duracion), os.getenv(...)
    vea el valor actualizado sin necesidad de reiniciar el proceso.
    """
    timestamp = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    status = "SUCCESS" if success else "ERROR"

    try:
        set_key(ENV_FILE, "LAST_RUN_TIME", timestamp)
        set_key(ENV_FILE, "LAST_RUN_STATUS", status)
    except Exception as e:
        print(f"No se pudo guardar ultima ejecucion en .env: {e}")

    os.environ["LAST_RUN_TIME"] = timestamp
    os.environ["LAST_RUN_STATUS"] = status


# ---------------------------------------------------------------------------
# Extraccion (callable, sin sys.exit, sin leer sys.argv)
# ---------------------------------------------------------------------------

def run_extraction(fecha_desde: datetime = None, fecha_hasta: datetime = None) -> dict:
    """Ejecuta la extraccion completa y devuelve un resumen (nunca lanza).

    Args:
        fecha_desde: inicio del rango. Si es None, se usa "ayer".
        fecha_hasta: fin del rango. Si es None, se usa "hoy".

    Returns:
        dict con: success (bool), blocks_processed (int), blocks_total (int),
        errors (list[str]), message (str).
    """
    if not _extraction_lock.acquire(blocking=False):
        return {
            "success": False,
            "blocks_processed": 0,
            "blocks_total": 0,
            "errors": ["Ya hay una actualizacion en curso."],
            "message": "Ya hay una actualizacion en curso.",
        }

    try:
        if fecha_desde is None:
            fecha_desde = datetime.now() - timedelta(days=1)
        if fecha_hasta is None:
            fecha_hasta = datetime.now()

        errors = []
        blocks_processed = 0

        try:
            print("=" * 70)
            print("DATAKINGA - EXTRACCION PARA RENDER (nuevo sitio)")
            print("=" * 70)

            supabase = get_client()
            print("v Supabase client inicializado")

            chunks = _month_ranges(fecha_desde, fecha_hasta)
            blocks_total = len(chunks)
            print(f"Procesando {blocks_total} mes(es): " + ", ".join(
                f"{d.strftime('%d/%m/%Y')}->{h.strftime('%d/%m/%Y')}" for d, h in chunks
            ))

            for chunk_idx, (chunk_desde, chunk_hasta) in enumerate(chunks, 1):
                print(f"\n{'='*70}")
                print(f"BLOQUE {chunk_idx}/{blocks_total}: {chunk_desde.strftime('%d/%m/%Y')} -> {chunk_hasta.strftime('%d/%m/%Y')}")
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
                    errors.append(f"Bloque {chunk_idx}: {e}")
                    continue

                print("\n--- AUDITORIA PRE-SUPABASE ---")
                expected_sucursales = list(SUCURSALES.keys())
                audit = run_pre_supabase_audit(
                    df_tickets,
                    df_consumos,
                    expected_sucursales=expected_sucursales,
                )
                print_audit_report(audit)

                strict_audit = os.getenv("AUDIT_STRICT", "1").strip().lower() not in {"0", "false", "no"}
                if strict_audit and not audit.get("ok", False):
                    print("\nERROR: auditoria fallida. Bloque cancelado, no se sube a Supabase.")
                    print("Tip: revisa EXPECTED_SUCURSALES o corrige datos antes de reintentar.")
                    errors.append(f"Bloque {chunk_idx}: auditoria fallida")
                    continue

                print("\n--- GUARDANDO EN SUPABASE ---")
                if not df_tickets.empty:
                    insert_tickets(supabase, df_tickets)
                if not df_consumos.empty:
                    upsert_consumos(supabase, df_consumos)

                blocks_processed += 1

            print("\n" + "=" * 70)
            print("PROCESO COMPLETO FINALIZADO")
            print("=" * 70)

            success = blocks_processed == blocks_total and not errors
            message = (
                f"Procesados {blocks_processed}/{blocks_total} bloque(s) correctamente."
                if success
                else f"Procesados {blocks_processed}/{blocks_total} bloque(s). Errores: {len(errors)}."
            )

            _save_last_run(success)

            return {
                "success": success,
                "blocks_processed": blocks_processed,
                "blocks_total": blocks_total,
                "errors": errors,
                "message": message,
            }

        except Exception as e:
            import traceback
            print(f"\nERROR inesperado en run_extraction: {e}")
            traceback.print_exc()
            _save_last_run(False)
            return {
                "success": False,
                "blocks_processed": blocks_processed,
                "blocks_total": 0,
                "errors": errors + [str(e)],
                "message": f"Error inesperado: {e}",
            }
    finally:
        _extraction_lock.release()


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def main():
    fecha_desde, fecha_hasta = resolve_date_range(sys.argv)
    result = run_extraction(fecha_desde, fecha_hasta)
    print(f"\n{result['message']}")
    if not result["success"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
