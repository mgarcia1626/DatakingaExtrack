"""
DATAKINGA - Extraccion con Playwright (headless Chromium)
Reemplaza Selenium+Edge para funcionar en Render (Linux, sin GUI)
"""
import io
import os
import time
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
from playwright.sync_api import Page, Download

load_dotenv()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _df_from_download(download: Download) -> pd.DataFrame:
    """Lee un archivo descargado por Playwright y lo retorna como DataFrame raw."""
    path = download.path()          # bloquea hasta que la descarga completa
    return pd.read_excel(path, header=None)


def _set_date_field(page: Page, field_id: str, fecha_sin_barras: str):
    """Limpia un campo de fecha y escribe la fecha sin barras (DDMMYYYY)."""
    page.click(f"#{field_id}")
    page.keyboard.press("Control+a")
    time.sleep(0.2)
    page.keyboard.type(fecha_sin_barras)
    time.sleep(0.3)



def _get_allowed_sucursales():
    raw = os.getenv('SUCURSALES', '').strip()
    if not raw:
        return None
    return [s.strip() for s in raw.split(',') if s.strip()]


def _sucursal_permitida(nombre, allowed):
    if allowed is None:
        return True
    norm = nombre.upper().replace(' ', '').replace('_', '')
    return any(norm == a.upper().replace(' ', '').replace('_', '') for a in allowed)



def _nav_to(page: Page, link_text: str):
    page.goto('https://datakinga.com/', timeout=60000, wait_until='domcontentloaded')
    page.wait_for_selector(f'text={link_text}', timeout=30000)
    page.click(f'text={link_text}')
    page.wait_for_load_state('domcontentloaded', timeout=60000)
    time.sleep(3)


def _nav_to(page: Page, link_text: str):
    page.goto('https://datakinga.com/', timeout=30000)
    page.wait_for_load_state('domcontentloaded', timeout=60000)
    page.wait_for_selector(f'text={link_text}', timeout=20000)
    page.click(f'text={link_text}')
    page.wait_for_load_state('domcontentloaded', timeout=60000)
    time.sleep(2)


def _nav_to(page: Page, link_text: str):
    page.goto('https://datakinga.com/', timeout=60000, wait_until='domcontentloaded')
    page.wait_for_load_state('domcontentloaded', timeout=60000)
    page.wait_for_selector(f'text={link_text}', timeout=30000)
    page.click(f'text={link_text}', no_wait_after=True)
    page.wait_for_load_state('domcontentloaded', timeout=90000)
    time.sleep(2)


# Login
# ---------------------------------------------------------------------------

def login(page: Page, username: str, password: str):
    print("\n[LOGIN] Navegando a datakinga.com...")
    page.goto("https://datakinga.com/", timeout=30000)
    page.wait_for_selector("#txtUsuario", timeout=15000)
    page.fill("#txtUsuario", username)
    page.fill("#txtClave", password)
    page.click("#Ingresar")
    page.wait_for_load_state("domcontentloaded", timeout=60000)
    print("   v Login exitoso")


# ---------------------------------------------------------------------------
# Cinta Testigo
# ---------------------------------------------------------------------------

def extraer_cinta_testigo(page: Page, fecha_desde: datetime, fecha_hasta: datetime) -> pd.DataFrame | None:
    """
    Navega a Cinta Testigo, configura fechas y descarga el Excel.
    Retorna DataFrame crudo (header en fila 3, datos desde fila 4).
    """
    print("\n" + "=" * 60)
    print("EXTRACCION: CINTA TESTIGO")
    print("=" * 60)

    fecha_desde_str = fecha_desde.strftime('%d/%m/%Y')
    fecha_hasta_str = fecha_hasta.strftime('%d/%m/%Y')
    fecha_desde_sin = fecha_desde.strftime('%d%m%Y')
    fecha_hasta_sin = fecha_hasta.strftime('%d%m%Y')
    print(f"   Periodo: {fecha_desde_str} -> {fecha_hasta_str}")

    # Navegar
    print("[1/4] Navegando a Cinta Testigo...")
    _nav_to(page, "Cinta Testigo")



    # Fechas
    print("[2/4] Configurando fechas...")
    _set_date_field(page, "ctl00_ContentPlaceHolder1_txtDesde", fecha_desde_sin)
    _set_date_field(page, "ctl00_ContentPlaceHolder1_txtHasta", fecha_hasta_sin)

    # Procesar
    print("[3/4] Procesando...")
    try:
        page.click("#ctl00_ContentPlaceHolder1_cmdProcesar")
        time.sleep(3)
    except Exception:
        print("   ! No se encontro boton Procesar")

    # Exportar y capturar descarga
    print("[4/4] Exportando a Excel...")
    for intento in range(1, 4):
        try:
            with page.expect_download(timeout=90000) as dl_info:
                page.click("#ctl00_ContentPlaceHolder1_cmdExportar")
            download = dl_info.value
            df = _df_from_download(download)
            print(f"   v Cinta Testigo descargada ({len(df)} filas raw)")
            return df
        except Exception as e:
            print(f"   ! Intento {intento}/3 fallido: {e}")
            time.sleep(3)

    print("   x Cinta Testigo: fallo despues de 3 intentos")
    return None


# ---------------------------------------------------------------------------
# Tickets con Detalle
# ---------------------------------------------------------------------------

def extraer_tickets_detalle(page: Page, fecha_desde: datetime, fecha_hasta: datetime) -> list:
    """
    Descarga tickets para cada sucursal disponible en el dropdown.
    Retorna lista de tuplas (nombre_sucursal, DataFrame_crudo).
    """
    print("\n" + "=" * 60)
    print("EXTRACCION: TICKETS CON DETALLE")
    print("=" * 60)

    fecha_desde_str = fecha_desde.strftime('%d/%m/%Y')
    fecha_hasta_str = fecha_hasta.strftime('%d/%m/%Y')
    fecha_desde_sin = fecha_desde.strftime('%d%m%Y')
    fecha_hasta_sin = fecha_hasta.strftime('%d%m%Y')
    print(f"   Periodo: {fecha_desde_str} -> {fecha_hasta_str}")

    # Navegar
    print("[1/3] Navegando a Ticket con Detalle...")
    _nav_to(page, "Ticket con Detalle")

    # Fechas
    print("[2/3] Configurando fechas...")
    _set_date_field(page, "ctl00_ContentPlaceHolder1_txtDesde", fecha_desde_sin)
    _set_date_field(page, "ctl00_ContentPlaceHolder1_txtHasta", fecha_hasta_sin)

    # Leer sucursales del dropdown
    print("[3/3] Procesando sucursales...")
    page.wait_for_selector("#ctl00_ContentPlaceHolder1_cmbSucursal", timeout=10000)
    opciones = page.eval_on_selector_all(
        "#ctl00_ContentPlaceHolder1_cmbSucursal option",
        "options => options.map(o => ({value: o.value, text: o.text.trim()}))"
    )
    allowed = _get_allowed_sucursales()
    opciones = [op for op in opciones if _sucursal_permitida(op['text'], allowed)]
    print(f"   Sucursales encontradas: {len(opciones)}")
    for i, op in enumerate(opciones):
        print(f"   [{i}] {op['text']}")

    resultados = []

    for i, opcion in enumerate(opciones):
        nombre_sucursal = opcion['text']
        print(f"\n   --- {i+1}/{len(opciones)}: {nombre_sucursal} ---")

        for intento in range(1, 4):
            try:
                # Seleccionar sucursal
                page.select_option(
                    "#ctl00_ContentPlaceHolder1_cmbSucursal",
                    value=opcion['value']
                )
                time.sleep(1)

                # Exportar
                with page.expect_download(timeout=90000) as dl_info:
                    page.click("#ctl00_ContentPlaceHolder1_dgExportar")
                download = dl_info.value
                df = _df_from_download(download)
                print(f"   v {nombre_sucursal}: {len(df)} filas raw")
                resultados.append((nombre_sucursal, df))
                break
            except Exception as e:
                print(f"   ! Intento {intento}/3 fallido: {e}")
                if intento < 3:
                    # Volver a configurar la pagina
                    _nav_to(page, "Ticket con Detalle")
                    _set_date_field(page, "ctl00_ContentPlaceHolder1_txtDesde", fecha_desde_sin)
                    _set_date_field(page, "ctl00_ContentPlaceHolder1_txtHasta", fecha_hasta_sin)
                    time.sleep(1)
                else:
                    print(f"   x {nombre_sucursal}: fallo despues de 3 intentos")

        time.sleep(2)

    print(f"\n   v Tickets completado: {len(resultados)}/{len(opciones)} sucursales")
    return resultados


# ---------------------------------------------------------------------------
# Consumos
# ---------------------------------------------------------------------------

def extraer_consumos(page: Page, fecha_desde: datetime, fecha_hasta: datetime) -> list:
    """
    Descarga consumos por cada sucursal usando checkboxes.
    Retorna lista de tuplas (nombre_sucursal, DataFrame_crudo).
    """
    print("\n" + "=" * 60)
    print("EXTRACCION: CONSUMOS")
    print("=" * 60)

    fecha_desde_str = fecha_desde.strftime('%d/%m/%Y')
    fecha_hasta_str = fecha_hasta.strftime('%d/%m/%Y')
    fecha_desde_sin = fecha_desde.strftime('%d%m%Y')
    fecha_hasta_sin = fecha_hasta.strftime('%d%m%Y')
    print(f"   Periodo: {fecha_desde_str} -> {fecha_hasta_str}")

    sucursales = [
        "COSTAVERDE",
        "PASADENA",
        "ENTRE RIOS",
        "SAAVEDRA",
        "SAENZ PENA",
    ]

    resultados = []
    allowed = _get_allowed_sucursales()
    to_process = [(i, s) for i, s in enumerate(sucursales) if _sucursal_permitida(s, allowed)]

    for i, nombre_sucursal in to_process:
        print(f"\n   --- {i+1}/{len(sucursales)}: {nombre_sucursal} ---")

        for intento in range(1, 4):
            try:
                # Navegar a Consumos (siempre recargamos para estado limpio)
                page.goto("https://datakinga.com/Consumos.aspx", timeout=20000)
                page.wait_for_load_state("domcontentloaded", timeout=60000)
                time.sleep(2)

                # Configurar fechas
                _set_date_field(page, "ctl00_ContentPlaceHolder1_txtDesde", fecha_desde_sin)
                _set_date_field(page, "ctl00_ContentPlaceHolder1_txtHasta", fecha_hasta_sin)

                # Desmarcar todos los checkboxes
                for j in range(len(sucursales)):
                    cb_id = f"ctl00_ContentPlaceHolder1_chkSucursales_{j}"
                    try:
                        cb = page.query_selector(f"#{cb_id}")
                        if cb and cb.is_checked():
                            cb.click()
                            time.sleep(0.2)
                    except Exception:
                        pass

                # Marcar solo el actual
                cb_actual = f"ctl00_ContentPlaceHolder1_chkSucursales_{i}"
                page.wait_for_selector(f"#{cb_actual}", timeout=5000)
                if not page.is_checked(f"#{cb_actual}"):
                    page.click(f"#{cb_actual}")
                time.sleep(0.5)
                print(f"   v Checkbox {i} marcado")

                # Procesar
                page.click("#ctl00_ContentPlaceHolder1_cmdProcesar")
                time.sleep(3)

                # Exportar
                with page.expect_download(timeout=90000) as dl_info:
                    page.click("#ctl00_ContentPlaceHolder1_cmdExportar")
                download = dl_info.value
                df = _df_from_download(download)
                print(f"   v {nombre_sucursal}: {len(df)} filas raw")
                resultados.append((nombre_sucursal, df))
                break

            except Exception as e:
                print(f"   ! Intento {intento}/3 fallido: {e}")
                if intento == 3:
                    print(f"   x {nombre_sucursal}: fallo despues de 3 intentos")

        time.sleep(2)

    print(f"\n   v Consumos completado: {len(resultados)}/{len(sucursales)} sucursales")
    return resultados
