"""
DATAKINGA (new site: datakinga.cloudsysbar.com) - Extraction functions
Uses requests + BeautifulSoup instead of Playwright/Selenium.
Targets Pasadena (id=1) and Junin (id=2).
"""
import os
import requests
import pandas as pd
from datetime import datetime
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

    rows = []
    for idx, item in enumerate(data.get("detalle", []), start=1):
        rows.append({
            "Numero": str(data["numComanda"]),
            "Tipo": comanda_meta["Tipo"],
            "Sucursal": comanda_meta["Sucursal"],
            "Mesa": str(data.get("numeroMesa", "")),
            "Mozo": data.get("nombreMozo", ""),
            "Nombre": data.get("nombreCliente", ""),
            "Codigo": str(idx),
            "Descripcion": item.get("nombreArticulo", ""),
            "Cantidad": _parse_importe(item.get("cantidad", "0")),
            "Importe": _parse_importe(item.get("importeTotal", "0")),
            "Turno": comanda_meta.get("Turno"),
            "Fecha": fecha,
            "Hora": hora,
        })
    return rows


def _build_turno_map(session: requests.Session, sucursal_id: int, desde: datetime, hasta: datetime) -> dict:
    """Returns {internal_id: turno_label} for all comandas of a sucursal."""
    turno_map = {}
    try:
        r = session.get(f"{BASE_URL}/Comandas/Turnos", params=[("sucursalIds", sucursal_id)], timeout=10)
        turnos = r.json()
    except Exception:
        return turno_map

    for turno in turnos:
        label = "Manana" if "a" in turno.lower() and "n" in turno.lower() else "Tarde/Noche"
        r = session.get(
            f"{BASE_URL}/Comandas",
            params=[("sucursalIds", sucursal_id), ("turnos", turno),
                    ("desde", desde.strftime("%Y-%m-%d")), ("hasta", hasta.strftime("%Y-%m-%d"))],
            timeout=30,
        )
        soup = BeautifulSoup(r.text, "html.parser")
        table = soup.find("table", {"id": "kt_comandas_table"})
        if not table:
            continue
        for tr in table.select("tbody tr[data-comanda-id]"):
            turno_map[tr["data-comanda-id"]] = label

    return turno_map


def extraer_tickets(session: requests.Session, desde: datetime, hasta: datetime) -> pd.DataFrame:
    print("\n" + "=" * 60)
    print("EXTRACCION: TICKETS DETALLE (nuevo sitio)")
    print("=" * 60)
    print(f"   Periodo: {desde.strftime('%d/%m/%Y')} -> {hasta.strftime('%d/%m/%Y')}")

    # Step 1: build turno map per sucursal
    print("   Construyendo mapa de turnos...")
    turno_map = {}
    for nombre, sid in SUCURSALES.items():
        m = _build_turno_map(session, sid, desde, hasta)
        turno_map.update(m)
        print(f"   v {nombre}: {len(m)} comandas con turno asignado")

    # Step 2: get full Comandas list (all sucursales in one request)
    params = []
    for sid in SUCURSALES.values():
        params.append(("sucursalIds", sid))
    params += [
        ("desde", desde.strftime("%Y-%m-%d")),
        ("hasta", hasta.strftime("%Y-%m-%d")),
    ]
    r = session.get(f"{BASE_URL}/Comandas", params=params, timeout=30)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    table = soup.find("table", {"id": "kt_comandas_table"})
    if not table:
        print("   ! Tabla de comandas no encontrada")
        return pd.DataFrame()

    comandas = []
    for tr in table.select("tbody tr[data-comanda-id]"):
        cells = tr.find_all("td")
        if len(cells) < 8:
            continue
        estado = tr.get("data-estado", "").strip().upper()
        internal_id = tr["data-comanda-id"]
        comandas.append({
            "internalId": internal_id,
            "Tipo": estado,
            "Sucursal": cells[2].get_text(strip=True),
            "Turno": turno_map.get(internal_id),
        })

    print(f"   v {len(comandas)} comandas encontradas, obteniendo detalles...")

    # Step 2: fetch detail for each comanda concurrently
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
                print(f"   ... {done}/{len(comandas)} procesadas")

    df = pd.DataFrame(all_rows)
    print(f"   v {len(df)} lineas de detalle ({len(comandas)} comandas)")
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
