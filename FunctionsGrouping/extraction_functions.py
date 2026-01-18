"""
Funciones de extracción de datos desde Datakinga
"""
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from pathlib import Path
import time
import pandas as pd
from datetime import datetime
import os
import glob


def extraer_cinta_testigo(driver, wait, download_dir):
    """
    Extrae datos de Cinta Testigo usando el botón Exportar a Excel
    Desde: día anterior, Hasta: hoy
    """
    print("\n" + "=" * 70)
    print("EXTRACCIÓN: CINTA TESTIGO")
    print("=" * 70)
    
    # Calcular fechas
    from datetime import datetime, timedelta
    fecha_ayer = datetime.now() - timedelta(days=1)
    fecha_hoy = datetime.now()
    
    fecha_desde_barras = fecha_ayer.strftime('%d/%m/%Y')
    fecha_desde_sin_barras = fecha_ayer.strftime('%d%m%Y')
    
    fecha_hasta_barras = fecha_hoy.strftime('%d/%m/%Y')
    fecha_hasta_sin_barras = fecha_hoy.strftime('%d%m%Y')
    
    print(f"\n   📅 Desde: {fecha_desde_barras} | Hasta: {fecha_hasta_barras}")
    
    # Navegar a Cinta Testigo
    print("\n[1/4] NAVEGANDO A CINTA TESTIGO")
    cinta_link = wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "Cinta Testigo")))
    cinta_link.click()
    print("   ✓ Navegación exitosa")
    time.sleep(2)
    
    # Configurar fechas
    print("\n[2/4] CONFIGURANDO FECHAS")
    fecha_desde_field = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_txtDesde")
    fecha_desde_field.click()
    time.sleep(0.2)
    fecha_desde_field.send_keys('\ue009a\ue000')  # Ctrl+A
    time.sleep(0.2)
    fecha_desde_field.send_keys(fecha_desde_sin_barras)
    print(f"   ✓ Fecha Desde: {fecha_desde_barras}")
    
    fecha_hasta_field = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_txtHasta")
    fecha_hasta_field.click()
    time.sleep(0.2)
    fecha_hasta_field.send_keys('\ue009a\ue000')  # Ctrl+A
    time.sleep(0.2)
    fecha_hasta_field.send_keys(fecha_hasta_sin_barras)
    print(f"   ✓ Fecha Hasta: {fecha_hasta_barras}")
    time.sleep(1)
    
    # Hacer clic en Procesar
    print("\n[3/4] PROCESANDO")
    try:
        procesar_btn = wait.until(
            EC.element_to_be_clickable((By.ID, "ctl00_ContentPlaceHolder1_cmdProcesar"))
        )
        procesar_btn.click()
        print("   ✓ Botón Procesar clickeado")
        time.sleep(3)
    except:
        print("   ⚠️ No se encontró el botón Procesar o ya está procesado")
        time.sleep(2)
    
    # Exportar a Excel
    print("\n[4/4] EXPORTANDO A EXCEL")
    
    max_intentos = 3
    archivo_guardado = False
    downloads_path = os.path.join(os.path.expanduser('~'), 'Downloads')
    
    for intento in range(1, max_intentos + 1):
        if intento > 1:
            print(f"\n   🔄 Reintento {intento}/{max_intentos}")
        
        # Click en Exportar a Excel
        exportar_btn = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_cmdExportar")
        exportar_btn.click()
        print(f"   ✓ Exportar a Excel clickeado")
        
        # Esperar descarga
        print(f"   ⏳ Esperando descarga...")
        max_wait = 20
        waited = 0
        archivo_encontrado = None
        
        while waited < max_wait:
            time.sleep(1)
            waited += 1
            
            list_of_files = []
            list_of_files.extend(glob.glob(os.path.join(downloads_path, '*.xls')))
            list_of_files.extend(glob.glob(os.path.join(downloads_path, '*.xlsx')))
            
            if list_of_files:
                latest_file = max(list_of_files, key=os.path.getctime)
                file_age = time.time() - os.path.getctime(latest_file)
                
                if file_age < 15 and not latest_file.endswith('.crdownload'):
                    archivo_encontrado = latest_file
                    print(f"   📥 Detectado: {os.path.basename(latest_file)} ({file_age:.1f}s)")
                    break
            
            if waited % 3 == 0:
                print(f"   ... esperando ({waited}s)")
        
        if archivo_encontrado:
            # Renombrar con timestamp
            from datetime import datetime
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            _, ext = os.path.splitext(archivo_encontrado)
            nuevo_nombre = f"cinta_testigo_{timestamp}{ext}"
            destino = os.path.join(download_dir, nuevo_nombre)
            
            if os.path.exists(destino):
                os.remove(destino)
            
            os.rename(archivo_encontrado, destino)
            print(f"   ✓ Guardado: {nuevo_nombre}")
            
            print(f"\n✅ CINTA TESTIGO COMPLETADO")
            print(f"   Archivo: {nuevo_nombre}")
            
            archivo_guardado = True
            return destino
        else:
            print(f"   ⚠️ No detectado (intento {intento}/{max_intentos})")
            if intento < max_intentos:
                print(f"   💡 Reintentando en 3 segundos...")
                time.sleep(3)
    
    if not archivo_guardado:
        print(f"   ❌ Fallo después de {max_intentos} intentos")
        return None


def extraer_tickets_detalle(driver, wait, download_dir):
    """
    Extrae Tickets con Detalle para todas las sucursales
    Desde: día anterior, Hasta: hoy
    """
    print("\n" + "=" * 70)
    print("EXTRACCIÓN: TICKETS CON DETALLE")
    print("=" * 70)
    
    # Calcular fechas
    from datetime import datetime, timedelta
    fecha_ayer = datetime.now() - timedelta(days=1)
    fecha_hoy = datetime.now()
    
    fecha_desde_barras = fecha_ayer.strftime('%d/%m/%Y')
    fecha_desde_sin_barras = fecha_ayer.strftime('%d%m%Y')
    
    fecha_hasta_barras = fecha_hoy.strftime('%d/%m/%Y')
    fecha_hasta_sin_barras = fecha_hoy.strftime('%d%m%Y')
    
    print(f"\n   📅 Desde: {fecha_desde_barras} | Hasta: {fecha_hasta_barras}")
    
    # Navegar a Ticket con Detalle
    print("\n[1/4] NAVEGANDO A TICKET CON DETALLE")
    ticket_link = wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "Ticket con Detalle")))
    ticket_link.click()
    print("   ✓ Navegación exitosa")
    time.sleep(2)
    
    # Configurar fechas
    print("\n[2/4] CONFIGURANDO FECHAS")
    fecha_desde_field = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_txtDesde")
    fecha_desde_field.click()
    time.sleep(0.2)
    fecha_desde_field.send_keys('\ue009a\ue000')  # Ctrl+A
    time.sleep(0.2)
    fecha_desde_field.send_keys(fecha_desde_sin_barras)
    print(f"   ✓ Fecha Desde: {fecha_desde_barras}")
    
    fecha_hasta_field = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_txtHasta")
    fecha_hasta_field.click()
    time.sleep(0.2)
    fecha_hasta_field.send_keys('\ue009a\ue000')  # Ctrl+A
    time.sleep(0.2)
    fecha_hasta_field.send_keys(fecha_hasta_sin_barras)
    print(f"   ✓ Fecha Hasta: {fecha_hasta_barras}")
    time.sleep(1)
    
    # Detectar desplegable de sucursales
    print("\n[3/4] DETECTANDO SUCURSALES")
    dropdown = wait.until(EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_cmbSucursal")))
    select = Select(dropdown)
    options = select.options
    
    print(f"   Total de sucursales: {len(options)}")
    for i, option in enumerate(options):
        print(f"   [{i}] {option.text}")
    
    # Procesar todas las sucursales
    print("\n[4/4] PROCESANDO TODAS LAS SUCURSALES")
    
    archivos_guardados = []
    downloads_path = os.path.join(os.path.expanduser('~'), 'Downloads')
    
    for i, option in enumerate(options):
        print(f"\n   --- Procesando {i+1}/{len(options)}: {option.text} ---")
        
        max_intentos = 3
        archivo_guardado = False
        
        for intento in range(1, max_intentos + 1):
            if intento > 1:
                print(f"\n   🔄 Reintento {intento}/{max_intentos}")
            
            # Seleccionar sucursal
            select.select_by_index(i)
            print(f"   ✓ Sucursal seleccionada: {option.text}")
            time.sleep(1)
            
            # Exportar
            exportar_btn = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_dgExportar")
            exportar_btn.click()
            print(f"   ✓ Exportar clickeado")
            
            # Preparar nombre
            nombre_sucursal = option.text.replace(' ', '_')
            fecha_archivo = fecha_hasta_barras.replace('/', '_')
            
            # Esperar descarga
            print(f"   ⏳ Esperando descarga...")
            max_wait = 20
            waited = 0
            archivo_encontrado = None
            
            while waited < max_wait:
                time.sleep(1)
                waited += 1
                
                list_of_files = []
                list_of_files.extend(glob.glob(os.path.join(downloads_path, '*.xls')))
                list_of_files.extend(glob.glob(os.path.join(downloads_path, '*.xlsx')))
                
                if list_of_files:
                    latest_file = max(list_of_files, key=os.path.getctime)
                    file_age = time.time() - os.path.getctime(latest_file)
                    
                    if file_age < 15 and not latest_file.endswith('.crdownload'):
                        archivo_encontrado = latest_file
                        print(f"   📥 Detectado: {os.path.basename(latest_file)} ({file_age:.1f}s)")
                        break
                
                if waited % 3 == 0:
                    print(f"   ... esperando ({waited}s)")
            
            if archivo_encontrado:
                _, ext = os.path.splitext(archivo_encontrado)
                nuevo_nombre = f"{nombre_sucursal}_{fecha_archivo}{ext}"
                destino = os.path.join(download_dir, nuevo_nombre)
                
                if os.path.exists(destino):
                    os.remove(destino)
                
                os.rename(archivo_encontrado, destino)
                print(f"   ✓ Guardado: {nuevo_nombre}")
                archivos_guardados.append(nuevo_nombre)
                archivo_guardado = True
                break
            else:
                print(f"   ⚠️ No detectado (intento {intento}/{max_intentos})")
                if intento < max_intentos:
                    print(f"   💡 Reintentando en 3 segundos...")
                    time.sleep(3)
        
        if not archivo_guardado:
            print(f"   ❌ Fallo después de {max_intentos} intentos")
        
        time.sleep(2)
    
    print(f"\n✅ TICKETS CON DETALLE COMPLETADO")
    print(f"   Archivos guardados: {len(archivos_guardados)}/{len(options)}")
    
    return archivos_guardados


def extraer_consumos(driver, wait, download_dir):
    """
    Extrae datos de Consumos por sucursal usando checkboxes
    Desde: día anterior, Hasta: hoy
    """
    print("\n" + "=" * 70)
    print("EXTRACCIÓN: CONSUMOS POR SUCURSAL")
    print("=" * 70)
    
    # Calcular fechas
    from datetime import datetime, timedelta
    fecha_ayer = datetime.now() - timedelta(days=1)
    fecha_hoy = datetime.now()
    
    fecha_desde_barras = fecha_ayer.strftime('%d/%m/%Y')
    fecha_desde_sin_barras = fecha_ayer.strftime('%d%m%Y')
    
    fecha_hasta_barras = fecha_hoy.strftime('%d/%m/%Y')
    fecha_hasta_sin_barras = fecha_hoy.strftime('%d%m%Y')
    
    print(f"\n   📅 Desde: {fecha_desde_barras} | Hasta: {fecha_hasta_barras}")
    
    # Navegar a Consumos
    print("\n[1/5] NAVEGANDO A CONSUMOS")
    driver.get("https://datakinga.com/Consumos.aspx")
    print("   ✓ Navegación exitosa")
    time.sleep(2)
    
    # Configurar fechas
    print("\n[2/5] CONFIGURANDO FECHAS")
    fecha_desde_field = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_txtDesde")
    fecha_desde_field.click()
    time.sleep(0.2)
    fecha_desde_field.send_keys('\ue009a\ue000')  # Ctrl+A
    time.sleep(0.2)
    fecha_desde_field.send_keys(fecha_desde_sin_barras)
    print(f"   ✓ Fecha Desde: {fecha_desde_barras}")
    
    fecha_hasta_field = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_txtHasta")
    fecha_hasta_field.click()
    time.sleep(0.2)
    fecha_hasta_field.send_keys('\ue009a\ue000')  # Ctrl+A
    time.sleep(0.2)
    fecha_hasta_field.send_keys(fecha_hasta_sin_barras)
    print(f"   ✓ Fecha Hasta: {fecha_hasta_barras}")
    time.sleep(1)
    
    # Nombres de las sucursales en orden
    print("\n[3/5] PREPARANDO SUCURSALES")
    sucursales = [
        "COSTAVERDE",
        "PASADENA", 
        "ENTRE RIOS",
        "SAAVEDRA",
        "SAENZ PEÑA"
    ]
    
    print(f"   Sucursales a procesar: {len(sucursales)}")
    for i, suc in enumerate(sucursales):
        print(f"   {i+1}. {suc}")
    
    # Iterar sobre cada sucursal
    print("\n[4/5] EXPORTANDO POR SUCURSAL")
    archivos_guardados = []
    downloads_path = os.path.join(os.path.expanduser('~'), 'Downloads')
    
    for i, sucursal_original in enumerate(sucursales):
        # Convertir espacios a guiones bajos para el nombre del archivo
        nombre_sucursal = sucursal_original.replace(' ', '_')
        print(f"\n   --- Procesando {i+1}/{len(sucursales)}: {sucursal_original} ---")
        
        # Si no es la primera iteración, volver a navegar a Consumos
        if i > 0:
            print(f"   🔄 Volviendo a Consumos...")
            driver.get("https://datakinga.com/Consumos.aspx")
            time.sleep(2)
            
            # Reconfigurar fechas
            fecha_desde_field = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_txtDesde")
            fecha_desde_field.click()
            time.sleep(0.2)
            fecha_desde_field.send_keys('\ue009a\ue000')  # Ctrl+A
            time.sleep(0.2)
            fecha_desde_field.send_keys(fecha_desde_sin_barras)
            time.sleep(0.5)
            
            fecha_hasta_field = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_txtHasta")
            fecha_hasta_field.click()
            time.sleep(0.2)
            fecha_hasta_field.send_keys('\ue009a\ue000')  # Ctrl+A
            time.sleep(0.2)
            fecha_hasta_field.send_keys(fecha_hasta_sin_barras)
            time.sleep(0.5)
        
        max_intentos = 3
        archivo_guardado = False
        
        for intento in range(1, max_intentos + 1):
            if intento > 1:
                print(f"\n   🔄 Reintento {intento}/{max_intentos}")
                # Si es un reintento, volver a Consumos
                driver.get("https://datakinga.com/Consumos.aspx")
                time.sleep(2)
                
                # Reconfigurar fechas
                fecha_desde_field = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_txtDesde")
                fecha_desde_field.click()
                time.sleep(0.2)
                fecha_desde_field.send_keys('\ue009a\ue000')  # Ctrl+A
                time.sleep(0.2)
                fecha_desde_field.send_keys(fecha_desde_sin_barras)
                time.sleep(0.5)
                
                fecha_hasta_field = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_txtHasta")
                fecha_hasta_field.click()
                time.sleep(0.2)
                fecha_hasta_field.send_keys('\ue009a\ue000')  # Ctrl+A
                time.sleep(0.2)
                fecha_hasta_field.send_keys(fecha_hasta_sin_barras)
                time.sleep(0.5)
            
            # Esperar a que los checkboxes estén disponibles
            wait.until(EC.presence_of_element_located((By.ID, f"ctl00_ContentPlaceHolder1_chkSucursales_0")))
            time.sleep(0.5)
            
            # Desmarcar todos los checkboxes primero
            for j in range(len(sucursales)):
                checkbox_id = f"ctl00_ContentPlaceHolder1_chkSucursales_{j}"
                try:
                    checkbox = driver.find_element(By.ID, checkbox_id)
                    if checkbox.is_selected():
                        checkbox.click()
                        time.sleep(0.2)
                except:
                    pass
            
            # Marcar solo el checkbox actual
            checkbox_id = f"ctl00_ContentPlaceHolder1_chkSucursales_{i}"
            checkbox = driver.find_element(By.ID, checkbox_id)
            if not checkbox.is_selected():
                checkbox.click()
                time.sleep(0.5)
            print(f"   ✓ Checkbox seleccionado: {nombre_sucursal}")
            
            # Procesar
            procesar_btn = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_cmdProcesar")
            procesar_btn.click()
            print(f"   ✓ Procesar clickeado")
            time.sleep(3)
            
            # Exportar
            exportar_btn = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_cmdExportar")
            exportar_btn.click()
            print(f"   ✓ Exportar clickeado")
            
            # Preparar nombre (usar fecha hasta = hoy)
            fecha_archivo = fecha_hasta_barras.replace('/', '_')
            
            # Esperar descarga
            print(f"   ⏳ Esperando descarga...")
            max_wait = 20
            waited = 0
            archivo_encontrado = None
            
            while waited < max_wait:
                time.sleep(1)
                waited += 1
                
                list_of_files = []
                list_of_files.extend(glob.glob(os.path.join(downloads_path, '*.xls')))
                list_of_files.extend(glob.glob(os.path.join(downloads_path, '*.xlsx')))
                
                if list_of_files:
                    latest_file = max(list_of_files, key=os.path.getctime)
                    file_age = time.time() - os.path.getctime(latest_file)
                    
                    if file_age < 15 and not latest_file.endswith('.crdownload'):
                        archivo_encontrado = latest_file
                        print(f"   📥 Detectado: {os.path.basename(latest_file)} ({file_age:.1f}s)")
                        break
                
                if waited % 3 == 0:
                    print(f"   ... esperando ({waited}s)")
            
            if archivo_encontrado:
                fecha_archivo = fecha_hasta_barras.replace('/', '_')
                _, ext = os.path.splitext(archivo_encontrado)
                nuevo_nombre = f"consumos_{nombre_sucursal}_{fecha_archivo}{ext}"
                destino = os.path.join(download_dir, nuevo_nombre)
                
                # Si existe, eliminarlo (reescribir)
                if os.path.exists(destino):
                    os.remove(destino)
                    print(f"   ⚠️ Archivo existente eliminado")
                
                os.rename(archivo_encontrado, destino)
                print(f"   ✓ Guardado: {nuevo_nombre}")
                archivos_guardados.append(nuevo_nombre)
                archivo_guardado = True
                break
            else:
                print(f"   ⚠️ No detectado (intento {intento}/{max_intentos})")
                if intento < max_intentos:
                    print(f"   💡 Reintentando en 3 segundos...")
                    time.sleep(3)
        
        if not archivo_guardado:
            print(f"   ❌ Fallo después de {max_intentos} intentos")
        
        time.sleep(2)
    
    # Resumen final
    print("\n[5/5] RESUMEN")
    print("=" * 70)
    print("✅ CONSUMOS COMPLETADO")
    print("=" * 70)
    print(f"\n   Total archivos guardados: {len(archivos_guardados)}/{len(sucursales)}")
    
    return archivos_guardados