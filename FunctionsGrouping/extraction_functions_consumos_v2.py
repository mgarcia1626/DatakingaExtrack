"""
Función de extracción de Consumos por sucursal (versión mejorada)
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


def extraer_consumos_por_sucursal(driver, wait, download_dir):
    """
    Extrae Consumos por cada sucursal (usando checkboxes individuales)
    """
    print("\n" + "=" * 70)
    print("EXTRACCIÓN: CONSUMOS POR SUCURSAL")
    print("=" * 70)
    
    # Navegar a Consumos
    print("\n[1/4] NAVEGANDO A CONSUMOS")
    driver.get("https://datakinga.com/Consumos.aspx")
    print("   ✓ Navegación exitosa")
    time.sleep(2)
    
    # Configurar fecha
    print("\n[2/4] CONFIGURANDO FECHA")
    fecha_hasta_field = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_txtHasta")
    fecha_con_barras = fecha_hasta_field.get_attribute('value')
    fecha_sin_barras = fecha_con_barras.replace('/', '')
    print(f"   Fecha: {fecha_con_barras}")
    
    fecha_field = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_txtDesde")
    fecha_field.click()
    time.sleep(0.2)
    fecha_field.send_keys('\ue009a\ue000')  # Ctrl+A
    time.sleep(0.2)
    fecha_field.send_keys(fecha_sin_barras)
    print(f"   ✓ Fecha configurada")
    time.sleep(1)
    
    # Obtener checkboxes de sucursales
    print("\n[3/4] OBTENIENDO SUCURSALES")
    
    # Nombres de las sucursales en orden
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
    print("\n[4/4] EXPORTANDO POR SUCURSAL")
    archivos_guardados = []
    downloads_path = os.path.join(os.path.expanduser('~'), 'Downloads')
    
    for i, nombre_sucursal in enumerate(sucursales):
        print(f"\n   --- Procesando {i+1}/{len(sucursales)}: {nombre_sucursal} ---")
        
        # Si no es la primera iteración, volver a navegar a Consumos
        if i > 0:
            print(f"   🔄 Volviendo a Consumos...")
            driver.get("https://datakinga.com/Consumos.aspx")
            time.sleep(2)
            
            # Reconfigurar fecha
            fecha_field = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_txtDesde")
            fecha_field.click()
            time.sleep(0.2)
            fecha_field.send_keys('\ue009a\ue000')  # Ctrl+A
            time.sleep(0.2)
            fecha_field.send_keys(fecha_sin_barras)
            time.sleep(0.5)
        
        max_intentos = 3
        archivo_guardado = False
        
        for intento in range(1, max_intentos + 1):
            if intento > 1:
                print(f"\n   🔄 Reintento {intento}/{max_intentos}")
                # Si es un reintento, volver a Consumos
                driver.get("https://datakinga.com/Consumos.aspx")
                time.sleep(2)
                
                # Reconfigurar fecha
                fecha_field = driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_txtDesde")
                fecha_field.click()
                time.sleep(0.2)
                fecha_field.send_keys('\ue009a\ue000')  # Ctrl+A
                time.sleep(0.2)
                fecha_field.send_keys(fecha_sin_barras)
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
            
            # Preparar nombre
            fecha_archivo = fecha_con_barras.replace('/', '_')
            
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
                fecha_archivo = fecha_con_barras.replace('/', '_')
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
    
    print(f"\n✅ CONSUMOS POR SUCURSAL COMPLETADO")
    print(f"   Archivos guardados: {len(archivos_guardados)}/{len(sucursales)}")
    
    return archivos_guardados
