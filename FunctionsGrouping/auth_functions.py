"""
Funciones de autenticación y obtención de páginas.
"""

import requests
from bs4 import BeautifulSoup
import os
from dotenv import load_dotenv

# Cargar credenciales
load_dotenv()

LOGIN_URL = "https://datakinga.com/Login.aspx?ReturnUrl=%2f"


def login():
    """Hace login y retorna la sesión autenticada."""
    username = os.getenv('DATAKINGA_USER')
    password = os.getenv('DATAKINGA_PASSWORD')
    
    if not username or not password:
        raise ValueError("Define DATAKINGA_USER y DATAKINGA_PASSWORD en .env")
    
    session = requests.Session()
    
    # Obtener página de login
    print(f"[1/3] Obteniendo login page...")
    response = session.get(LOGIN_URL, timeout=15)
    
    # Parsear campos del formulario
    print("[2/3] Parseando formulario...")
    soup = BeautifulSoup(response.text, 'html.parser')
    form = soup.find('form', {'id': 'form1'})
    
    fields = {}
    for input_tag in form.find_all('input'):
        name = input_tag.get('name')
        value = input_tag.get('value', '')
        if name:
            fields[name] = value
    
    # Agregar credenciales
    fields['__EVENTTARGET'] = 'Ingresar'
    fields['__EVENTARGUMENT'] = ''
    fields['txtUsuario'] = username
    fields['txtClave'] = password
    
    # Enviar login
    print("[3/3] Enviando login...")
    action = form.get('action', '')
    login_url = action if action.startswith('http') else f"https://datakinga.com/{action.lstrip('./')}"
    
    response = session.post(
        login_url,
        data=fields,
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        timeout=15,
        allow_redirects=True
    )
    
    if 'Login.aspx' in response.url:
        print("✗ Login fallido")
        return None
    
    print(f"✓ Login exitoso - URL: {response.url}")
    return session


def get_page_html(session, url):
    """Obtiene el HTML de una página usando la sesión autenticada."""
    print(f"\nObteniendo: {url}")
    response = session.get(url, timeout=15)
    print(f"✓ Descargado: {len(response.text)} bytes")
    return response.text


def click_cinta_testigo(session):
    """
    Navega a la página de Cinta Testigo.
    Equivalente a hacer clic en el enlace "Cinta Testigo".
    """
    url = "https://datakinga.com/CintaTestigo.aspx"
    print("\n[Cinta Testigo] Navegando a la página...")
    response = session.get(url, timeout=15)
    print(f"✓ Página Cinta Testigo cargada: {len(response.text)} bytes")
    return response.text


def click_procesar(session):
    """
    Presiona el botón 'Procesar' en la página de Cinta Testigo.
    Envía el formulario con los campos ASP.NET necesarios.
    """
    # Primero obtener la página para tener los campos actualizados
    url = "https://datakinga.com/CintaTestigo.aspx"
    print("\n[Procesar] Obteniendo página Cinta Testigo...")
    response = session.get(url, timeout=15)
    
    # Parsear campos del formulario
    print("[Procesar] Parseando formulario...")
    soup = BeautifulSoup(response.text, 'html.parser')
    form = soup.find('form')  # Buscar cualquier form
    
    if not form:
        raise ValueError("No se encontró el formulario")
    
    fields = {}
    for input_tag in form.find_all('input'):
        name = input_tag.get('name')
        value = input_tag.get('value', '')
        if name:
            fields[name] = value
    
    # Agregar el botón Procesar
    fields['ctl00$ContentPlaceHolder1$cmdProcesar'] = 'Procesar'
    
    # Enviar formulario
    print("[Procesar] Enviando formulario...")
    action = form.get('action', '')
    post_url = action if action.startswith('http') else f"https://datakinga.com/{action.lstrip('./')}"
    
    response = session.post(
        post_url,
        data=fields,
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        timeout=15,
        allow_redirects=True
    )
    
    print(f"✓ Procesar ejecutado: {len(response.text)} bytes")
    return response.text


def click_pagina_numero(session, html_actual, numero_pagina):
    """
    Hace clic en un botón de paginación específico.
    """
    soup = BeautifulSoup(html_actual, 'html.parser')
    
    # Buscar el link de paginación
    pagination_link = None
    for link in soup.find_all('a', href=lambda x: x and f'Page${numero_pagina}' in x):
        pagination_link = link
        break
    
    if not pagination_link:
        print(f"   ✗ No se encontró el botón de página {numero_pagina}")
        return None
    
    # Parsear formulario para obtener ViewState Y todos los demás campos
    form = soup.find('form')
    if not form:
        print(f"   ✗ No se encontró formulario")
        return None
    
    fields = {}
    
    # Extraer todos los campos input
    for input_tag in form.find_all('input'):
        name = input_tag.get('name')
        value = input_tag.get('value', '')
        if name:
            fields[name] = value
    
    # Extraer todos los campos select (dropdowns)
    for select_tag in form.find_all('select'):
        name = select_tag.get('name')
        if not name:
            continue
        
        # Buscar opción seleccionada
        selected = select_tag.find('option', selected=True)
        if selected:
            value = selected.get('value', '')
        else:
            # Usar primera opción si no hay selección
            first_option = select_tag.find('option')
            value = first_option.get('value', '') if first_option else ''
        
        fields[name] = value
    
    # Extraer todos los campos textarea
    for textarea_tag in form.find_all('textarea'):
        name = textarea_tag.get('name')
        if name:
            fields[name] = textarea_tag.get_text(strip=True)
    
    # Simular clic en el botón de paginación
    fields['__EVENTTARGET'] = 'ctl00$ContentPlaceHolder1$GridView1'
    fields['__EVENTARGUMENT'] = f'Page${numero_pagina}'
    
    # Eliminar el botón Exportar para que no interfiera
    if 'ctl00$ContentPlaceHolder1$cmdExportar' in fields:
        del fields['ctl00$ContentPlaceHolder1$cmdExportar']
    
    # Hacer POST
    action = form.get('action', '')
    post_url = action if action.startswith('http') else f"https://datakinga.com/{action.lstrip('./')}"
    
    response = session.post(
        post_url,
        data=fields,
        headers={
            'Content-Type': 'application/x-www-form-urlencoded',
            'Referer': post_url,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.9',
            'Cache-Control': 'no-cache'
        },
        timeout=15
    )
    
    return response.text


def extraer_datos_tabla(html):
    """
    Extrae los datos de la tabla principal de una página.
    """
    soup = BeautifulSoup(html, 'html.parser')
    tables = soup.find_all('table')
    
    # Buscar tabla principal
    main_table = None
    for table in tables:
        rows = table.find_all('tr')
        if len(rows) > 10:
            first_row = rows[0] if rows else None
            if first_row:
                cells = first_row.find_all(['th', 'td'])
                if cells:
                    header_text = cells[0].get_text(strip=True)
                    if header_text in ['Id', 'Fecha', 'Número', 'Codigo']:
                        main_table = table
                        break
    
    if not main_table:
        main_table = max(tables, key=lambda t: len(t.find_all('tr')))
    
    rows = main_table.find_all('tr')
    data = []
    headers = []
    
    for i, row in enumerate(rows):
        cells = row.find_all(['th', 'td'])
        cell_data = [cell.get_text(strip=True) for cell in cells]
        
        if i == 0:
            headers = cell_data
        else:
            if cell_data and any(cell_data):
                data.append(cell_data)
    
    return headers, data


def exportar_excel(session, html_procesado):
    """
    Extrae los datos de TODAS las páginas de paginación y crea un archivo Excel.
    """
    from pathlib import Path
    from datetime import datetime
    import pandas as pd
    
    print("\n[Excel] Detectando páginas de paginación...")
    soup = BeautifulSoup(html_procesado, 'html.parser')
    
    # Detectar cuántas páginas hay
    pagination_links = soup.find_all('a', href=lambda x: x and 'Page$' in x)
    total_pages = 1  # Página actual
    
    for link in pagination_links:
        href = link.get('href', '')
        if 'Page$' in href:
            page_num = int(href.split('Page$')[1].split("'")[0])
            total_pages = max(total_pages, page_num)
    
    print(f"[Excel] Total de páginas encontradas: {total_pages}")
    
    # Lista para acumular todos los datos
    all_data = []
    headers = []
    
    # Extraer datos de la página actual (página 1)
    print(f"\n[Excel] Extrayendo página 1/{total_pages}...")
    headers, page_data = extraer_datos_tabla(html_procesado)
    all_data.extend(page_data)
    
    # Verificar primeros IDs
    first_ids = [row[0] for row in page_data[:3]]
    print(f"   ✓ {len(page_data)} filas extraídas - IDs: {first_ids}")
    
    # Navegar por las páginas restantes haciendo clic en cada botón
    current_html = html_procesado
    
    for page_num in range(2, total_pages + 1):
        print(f"\n[Excel] Haciendo clic en botón de página {page_num}/{total_pages}...")
        
        # Hacer clic en el botón de paginación
        new_html = click_pagina_numero(session, current_html, page_num)
        
        if not new_html:
            print(f"   ✗ Error al navegar a página {page_num}")
            continue
        
        # Actualizar HTML actual
        current_html = new_html
        
        # Extraer datos de la nueva página
        _, page_data = extraer_datos_tabla(current_html)
        all_data.extend(page_data)
        
        # Verificar primeros IDs
        first_ids = [row[0] for row in page_data[:3]]
        print(f"   ✓ {len(page_data)} filas extraídas - IDs: {first_ids}")
    
    # Crear DataFrame con todos los datos
    print(f"\n[Excel] Creando archivo Excel con todos los datos...")
    df = pd.DataFrame(all_data, columns=headers if headers else None)
    print(f"[Excel] Total: {len(df)} filas x {len(df.columns)} columnas")
    
    # Crear carpeta DataBase
    output_folder = Path('DataBase')
    output_folder.mkdir(exist_ok=True)
    
    # Guardar Excel
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'cinta_testigo_completo_{timestamp}.xlsx'
    filepath = output_folder / filename
    
    df.to_excel(filepath, index=False, engine='openpyxl')
    
    print(f"✓ Archivo Excel guardado: {filepath}")
    print(f"✓ Formato: Excel (.xlsx)")
    
    return str(filepath)
