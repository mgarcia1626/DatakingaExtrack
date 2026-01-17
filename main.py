"""
DATAKINGA - Extracción Automática de Datos
Modo: Selenium (Navegador Edge)
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.edge.options import Options
from pathlib import Path
import time
import os
from dotenv import load_dotenv

# Importar funciones de extracción
from FunctionsGrouping.extraction_functions import extraer_cinta_testigo, extraer_tickets_detalle, extraer_consumos

load_dotenv()

# Configuración de Edge
edge_options = Options()
edge_options.add_argument('--start-maximized')
edge_options.add_argument('--disable-blink-features=AutomationControlled')
edge_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
edge_options.add_experimental_option('useAutomationExtension', False)

# Crear directorios
download_dir_cinta = str(Path('DataBase/Cinta').absolute())
download_dir_detalle = str(Path('DataBase/Detalle').absolute())
download_dir_consumos = str(Path('DataBase/Consumos').absolute())
Path(download_dir_cinta).mkdir(parents=True, exist_ok=True)
Path(download_dir_detalle).mkdir(parents=True, exist_ok=True)
Path(download_dir_consumos).mkdir(parents=True, exist_ok=True)

print("=" * 70)
print("DATAKINGA - EXTRACCIÓN AUTOMÁTICA COMPLETA")
print("=" * 70)
print("\n🌐 Iniciando Edge...")

driver = webdriver.Edge(options=edge_options)

try:
    # 1. LOGIN
    print("\n" + "=" * 70)
    print("FASE 1: LOGIN")
    print("=" * 70)
    driver.get("https://datakinga.com/")
    
    wait = WebDriverWait(driver, 10)
    username_field = wait.until(EC.presence_of_element_located((By.ID, "txtUsuario")))
    
    username_field.send_keys(os.getenv('DATAKINGA_USER'))
    driver.find_element(By.ID, "txtClave").send_keys(os.getenv('DATAKINGA_PASSWORD'))
    driver.find_element(By.ID, "Ingresar").click()
    
    print("   ✓ Login exitoso")
    time.sleep(3)
    
    # 2. EXTRAER CINTA TESTIGO
    print("\n" + "=" * 70)
    print("FASE 2: CINTA TESTIGO")
    print("=" * 70)
    archivo_cinta = extraer_cinta_testigo(driver, wait, download_dir_cinta)
    
    # 3. EXTRAER TICKETS CON DETALLE
    print("\n" + "=" * 70)
    print("FASE 3: TICKETS CON DETALLE")
    print("=" * 70)
    archivos_tickets = extraer_tickets_detalle(driver, wait, download_dir_detalle)
    
    # 4. EXTRAER CONSUMOS
    print("\n" + "=" * 70)
    print("FASE 4: CONSUMOS")
    print("=" * 70)
    archivo_consumos = extraer_consumos(driver, wait, download_dir_consumos)
    
    # RESUMEN FINAL
    print("\n" + "=" * 70)
    print("✅ PROCESO COMPLETO FINALIZADO")
    print("=" * 70)
    print(f"\n📊 Cinta Testigo:")
    print(f"   {archivo_cinta}")
    print(f"\n📄 Tickets con Detalle ({len(archivos_tickets)} archivos):")
    for archivo in archivos_tickets:
        print(f"   - {archivo}")
    print(f"\n💰 Consumos:")
    print(f"   {archivo_consumos if archivo_consumos else 'No se pudo descargar'}")
    
    print("\n⏳ El navegador se cerrará en 5 segundos...")
    time.sleep(5)

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    print("\n⏳ Presiona ENTER para cerrar...")
    input()


finally:
    driver.quit()
    print("\n" + "=" * 70)
