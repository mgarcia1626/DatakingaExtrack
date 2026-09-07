"""
DATAKINGA (new site: datakinga.cloudsysbar.com) - Extraction functions
Uses requests + BeautifulSoup instead of Playwright/Selenium.
Targets Pasadena (id=1) and Junin (id=2).
"""
import os
import unicodedata
import requests
import pandas as pd
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv(override=True)

BASE_URL = "https://datakinga.cloudsysbar.com"

SUCURSALES = {
    "Pasadena": 1,
    "Junin": 2,
}


def login() -> requests.Session:
    username = os.getenv("DATAKINGA_Cloud_USER")
    password = os.getenv("DATAKINGA_Cloud_PASSWORD")

    if not username or not password:
        raise ValueError("Define DATAKINGA_USER y DATAKINGA_PASSWORD en .env")

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})

    # 1. GET login page to grab CSRF token
    r = session.get(f"{BASE_URL}/Identity/Account/Login", timeout=15)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    token_input = soup.find("input", {"name": "__RequestVerificationToken"})
    if not token_input:
        raise ValueError("Could not find CSRF token on login page")

    # 2. POST credentials
    payload = {
        "Input.Username": username,
        "Input.Password": password,
        "Input.RememberMe": "false",
        "__RequestVerificationToken": token_input["value"],
    }
    r = session.post(
        f"{BASE_URL}/Identity/Account/Login",
        data=payload,
        timeout=15,
        allow_redirects=True,
    )
    r.raise_for_status()

    if "Identity/Account/Login" in r.url:
        raise ValueError("Login failed - check DATAKINGA_USER / DATAKINGA_PASSWORD")

    print(f"   v Login OK -> {r.url}")
    return session


def _parse_importe(raw: str) -> float:
    try:
        return float(raw.replace("$", "").replace(".", "").replace(",", ".").strip())
    except Exception:
        return 0.0


def _normalize_lookup_key(value: str) -> str:
    text = unicodedata.normalize('NFKD', str(value))
    text = ''.join(ch.lower() for ch in text if not unicodedata.combining(ch))
    return ''.join(ch for ch in text if ch.isalnum())


def _find_product_code(value, fallback_idx: int):
    """Recursively walk nested payloads and return the first plausible product code."""
    candidates = {
        'codigoarticulo', 'codigoarticuloproducto', 'codigoproducto', 'codigo', 'idarticulo',
        'articuloid', 'productoid', 'id', 'codigodearticulo', 'codigodeproducto', 'codigoitem',
        'articulocodigo', 'productocodigo', 'codigoarticuloitem', 'idproducto'
    }

    def walk(node):
        if isinstance(node, dict):
            for key, item in node.items():
                norm_key = _normalize_lookup_key(key)
                if norm_key in candidates and item is not None and str(item).strip() not in ('', 'None', 'nan'):
                    return str(item).strip()
                if isinstance(item, (dict, list)):
                    found = walk(item)
                    if found is not None:
                        return found
        elif isinstance(node, list):
            for item in node:
                found = walk(item)
                if found is not None:
                    return found
        return None

    return walk(value)


def _fetch_detalle(session: requests.Session, internal_id: str, comanda_meta: dict) -> list:
    """Fetch /Comandas/Detalle/{id} JSON and return list of ticket rows."""
    try:
        r = session.get(f"{BASE_URL}/Comandas/Detalle/{internal_id}", timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"   ! Error detalle {internal_id}: {e}")
        return []

    fecha_str = data.get("fechaInicio", "")
    try:
        dt = datetime.strptime(fecha_str, "%d/%m/%Y %H:%M")
        fecha = str(dt.date())
        hora = dt.strftime("%H:%M:%S")
    except Exception:
        fecha = None
        hora = None

    def _fallback_codigo(descripcion: str, fallback_idx: int) -> str:
        # Stable synthetic key per line when API omits product code.
        # Keeps audit strict while avoiding silent line merges.
        norm = _normalize_lookup_key(descripcion)
        token = norm[:24] if norm else "item"
        return f"NC_{fallback_idx}_{token}"

    def _extract_codigo(item: dict, descripcion: str, fallback_idx: int) -> str:
        value = _find_product_code(item, fallback_idx)
        if value is None:
            return _fallback_codigo(descripcion, fallback_idx)
        value = str(value).strip()
        if value in ("", "None", "nan"):
            return _fallback_codigo(descripcion, fallback_idx)
        return value


    def _line_importe_unit(item: dict) -> float:
        cantidad = _parse_importe(str(item.get("cantidad", item.get("cantidadArticulo", "0"))))
        imp_unit = _parse_importe(str(item.get("importeUnitario", "")))
        imp_total = _parse_importe(str(item.get("importeTotal", item.get("importe", "0"))))
        if imp_unit > 0:
            return imp_unit
        if cantidad > 0 and imp_total > 0:
            return imp_total / cantidad
        return imp_total
    rows = []
    for idx, item in enumerate(data.get("detalle", []), start=1):
        descripcion = (
            item.get("nombreArticulo")
            or item.get("descripcionArticulo")
            or item.get("articulo")
            or item.get("descripcion")
            or ""
        )
        cantidad = _parse_importe(str(item.get("cantidad", item.get("cantidadArticulo", "0"))))
        unit_importe = _line_importe_unit(item)
        rows.append({
            "Numero": str(data["numComanda"]),
            "Tipo": comanda_meta["Tipo"],
            "Sucursal": comanda_meta["Sucursal"],
            "Mesa": str(data.get("numeroMesa", "")),
            "Mozo": data.get("nombreMozo", ""),
            "Nombre": data.get("nombreCliente", ""),
            "Codigo": _extract_codigo(item, descripcion, idx),
            "Descripcion": descripcion,
            "Cantidad": cantidad,
            "Importe": unit_importe,
            "Turno": comanda_meta.get("Turno"),
            "Fecha": fecha,
            "Hora": hora,
        })

    # Normalize line totals to match ticket final total (after discounts/adjustments)
    comanda_total = _parse_importe(str(data.get("importeTotal", "0")))
    subtotal_lines = sum((r["Cantidad"] or 0) * (r["Importe"] or 0) for r in rows)
    if comanda_total > 0 and subtotal_lines > 0:
        factor = comanda_total / subtotal_lines
        for r in rows:
            r["Importe"] = (r["Importe"] or 0) * factor

    return rows
def _build_turno_map(session: requests.Session, sucursal_id: int, desde: datetime, hasta: datetime) -> dict:
    """Returns {internal_id: turno_label} for all comandas of a sucursal.
    Queries day-by-day to avoid server-side table pagination truncation."""
    turno_map = {}
    try:
        r = session.get(f"{BASE_URL}/Comandas/Turnos", params=[("sucursalIds", sucursal_id)], timeout=10)
        turnos = r.json()
    except Exception:
        return turno_map

    current = desde
    while current <= hasta:
        day_str = current.strftime("%Y-%m-%d")
        for turno in turnos:
            label = "Manana" if "a" in turno.lower() and "n" in turno.lower() else "Tarde/Noche"
            try:
                r = session.get(
                    f"{BASE_URL}/Comandas",
                    params=[("sucursalIds", sucursal_id), ("turnos", turno),
                            ("desde", day_str), ("hasta", day_str)],
                    timeout=30,
                )
                soup = BeautifulSoup(r.text, "html.parser")
                table = soup.find("table", {"id": "kt_comandas_table"})
                if table:
                    for tr in table.select("tbody tr[data-comanda-id]"):
                        turno_map[tr["data-comanda-id"]] = label
            except Exception:
                pass
        current += timedelta(days=1)

    return turno_map


def _get_comandas_for_day(session, sucursal_id, sucursal_nombre, day_str, turno=None, turno_label=None):
    """Fetch comanda rows for a single sucursal + day, optionally filtered by turno."""
    params = [("sucursalIds", sucursal_id), ("desde", day_str), ("hasta", day_str)]
    if turno:
        params.append(("turnos", turno))
    try:
        r = session.get(f"{BASE_URL}/Comandas", params=params, timeout=30)
        r.raise_for_status()
    except Exception as e:
        print(f"   ! Error consultando {sucursal_nombre} {day_str} turno={turno}: {e}")
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    table = soup.find("table", {"id": "kt_comandas_table"})
    if not table:
        return []
    result = []
    for tr in table.select("tbody tr[data-comanda-id]"):
        cells = tr.find_all("td")
        if len(cells) < 3:
            continue
        result.append({
            "internalId": tr["data-comanda-id"],
            "Tipo": tr.get("data-estado", "").strip().upper(),
            "Sucursal": sucursal_nombre,
            "Turno": turno_label,
        })
    return result


def _get_comandas_for_day(session, sucursal_id, sucursal_nombre, day_str, turno=None, turno_label=None):
    """Fetch comanda rows for a single sucursal + day, optionally filtered by turno."""
    params = [("sucursalIds", sucursal_id), ("desde", day_str), ("hasta", day_str)]
    if turno:
        params.append(("turnos", turno))
    try:
        r = session.get(f"{BASE_URL}/Comandas", params=params, timeout=30)
        r.raise_for_status()
    except Exception as e:
        print(f"   ! Error consultando {sucursal_nombre} {day_str} turno={turno}: {e}")
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    table = soup.find("table", {"id": "kt_comandas_table"})
    if not table:
        return []
    result = []
    for tr in table.select("tbody tr[data-comanda-id]"):
        cells = tr.find_all("td")
        if len(cells) < 3:
            continue
        result.append({
            "internalId": tr["data-comanda-id"],
            "Tipo": tr.get("data-estado", "").strip().upper(),
            "Sucursal": sucursal_nombre,
            "Turno": turno_label,
        })
    return result


def extraer_tickets(session: requests.Session, desde: datetime, hasta: datetime) -> pd.DataFrame:
    print("\n" + "=" * 60)
    print("EXTRACCION: TICKETS DETALLE (nuevo sitio)")
    print("=" * 60)
    print(f"   Periodo: {desde.strftime('%d/%m/%Y')} -> {hasta.strftime('%d/%m/%Y')}")

    comandas_map = {}  # {internalId: comanda_meta} ? deduplicates across passes

    for nombre, sucursal_id in SUCURSALES.items():
        print(f"\n   --- Sucursal: {nombre} ---")

        # Get available turnos for this sucursal
        try:
            r = session.get(f"{BASE_URL}/Comandas/Turnos", params=[("sucursalIds", sucursal_id)], timeout=10)
            turnos_disponibles = r.json()
        except Exception:
            turnos_disponibles = []
        print(f"   Turnos disponibles: {turnos_disponibles}")

        # Pass 1: query per turno per day (Noche + Tarde both map to Tarde/Noche)
        for turno in turnos_disponibles:
            label = "Manana" if "a" in turno.lower() and "n" in turno.lower() else "Tarde/Noche"
            current = desde
            count_turno = 0
            while current <= hasta:
                day_str = current.strftime("%Y-%m-%d")
                rows = _get_comandas_for_day(session, sucursal_id, nombre, day_str, turno=turno, turno_label=label)
                for row in rows:
                    cid = row["internalId"]
                    if cid not in comandas_map:
                        comandas_map[cid] = row
                        count_turno += 1
                current += timedelta(days=1)
            print(f"   v {nombre} turno '{turno}' ({label}): {count_turno} comandas")

        # Pass 2: query WITHOUT turno filter per day to catch comandas with no turno
        current = desde
        count_sin_turno = 0
        while current <= hasta:
            day_str = current.strftime("%Y-%m-%d")
            rows = _get_comandas_for_day(session, sucursal_id, nombre, day_str, turno=None, turno_label=None)
            for row in rows:
                cid = row["internalId"]
                if cid not in comandas_map:
                    comandas_map[cid] = row  # Turno=None -> "Sin Turno" filled in dashboard
                    count_sin_turno += 1
            current += timedelta(days=1)
        if count_sin_turno:
            print(f"   v {nombre} sin turno: {count_sin_turno} comandas")

    comandas = list(comandas_map.values())
    total = len(comandas)
    print(f"\n   v {total} comandas totales, obteniendo detalles...")

    # Fetch details concurrently
    all_rows = []
    max_workers = int(os.getenv("DETAIL_WORKERS", "10"))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_fetch_detalle, session, c["internalId"], c): c
            for c in comandas
        }
        done = 0
        for future in as_completed(futures):
            rows = future.result()
            all_rows.extend(rows)
            done += 1
            if done % 100 == 0:
                print(f"   ... {done}/{total} procesadas")

    df = pd.DataFrame(all_rows)
    print(f"   v {len(df)} lineas de detalle ({total} comandas)")
    return df


def extraer_consumos(session: requests.Session, desde: datetime, hasta: datetime) -> pd.DataFrame:
    print("\n" + "=" * 60)
    print("EXTRACCION: CONSUMOS POR ARTICULO (nuevo sitio)")
    print("=" * 60)

    frames = []
    fecha_carga = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for nombre, sucursal_id in SUCURSALES.items():
        print(f"\n   Sucursal: {nombre} (id={sucursal_id})")
        params = {
            "sucursalId": sucursal_id,
            "desde": desde.strftime("%Y-%m-%d"),
            "hasta": hasta.strftime("%Y-%m-%d"),
            "tipoVenta": "todas",
        }
        r = session.get(f"{BASE_URL}/Comandas/Consumos", params=params, timeout=30)
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")
        table = soup.find("table", {"id": "kt_consumos_table"})
        if not table:
            print(f"   ! Tabla de consumos no encontrada para {nombre}")
            continue

        familia_actual = None
        rows = []
        for tr in table.select("tbody tr"):
            classes = " ".join(tr.get("class", []))
            if "familia-header" in classes:
                familia_actual = tr.get_text(strip=True)
            elif "familia-fila" in classes:
                cells = tr.find_all("td")
                if len(cells) >= 2:
                    rows.append({
                        "Familia": familia_actual,
                        "Codigo": cells[0].get_text(strip=True),
                        "Articulo": cells[1].get_text(strip=True),
                        "Sucursal": nombre,
                        "Fecha_Carga": fecha_carga,
                    })

        df_suc = pd.DataFrame(rows)
        print(f"   v {len(df_suc)} articulos")
        frames.append(df_suc)

    if not frames:
        return pd.DataFrame()

    result = pd.concat(frames, ignore_index=True)
    print(f"\n   v Total consumos: {len(result)}")
    return result







