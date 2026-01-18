"""
DATAKINGA - Descarga de Datos para Creación Inicial de BD
Descarga archivos con fechas personalizadas desde DataKinga
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.edge.options import Options
from pathlib import Path
import time
import os
import sys
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Agregar el directorio padre al path para importar módulos
sys.path.insert(0, str(Path(__file__).parent.parent))

# Importar funciones de extracción
from FunctionsGrouping.extraction_functions import extraer_cinta_testigo, extraer_tickets_detalle, extraer_consumos

load_dotenv()

# Configuración de fechas
# Verificar si se pasaron argumentos de línea de comandos
if len(sys.argv) >= 3:
    # Modo: python main.py FECHA_DESDE FECHA_HASTA
    # Formato esperado: DD/MM/YYYY DD/MM/YYYY
    try:
        fecha_desde_str = sys.argv[1]
        fecha_hasta_str = sys.argv[2]
        fecha_desde = datetime.strptime(fecha_desde_str, '%d/%m/%Y')
        fecha_hasta = datetime.strptime(fecha_hasta_str, '%d/%m/%Y')
        print(f"📅 Modo manual: Descargando desde {fecha_desde_str} hasta {fecha_hasta_str}")
    except ValueError:
        print("❌ Error: Formato de fecha inválido. Use: DD/MM/YYYY DD/MM/YYYY")
        print("   Ejemplo: python main.py 01/01/2026 18/01/2026")
        sys.exit(1)
else:
    # Modo automático: Leer fechas del .env o usar ayer por defecto
    fecha_desde_env = os.getenv('FECHA_DESDE', '')
    fecha_hasta_env = os.getenv('FECHA_HASTA', '')
    
    if fecha_desde_env and fecha_hasta_env:
        # Usar fechas del .env
        try:
            fecha_desde = datetime.strptime(fecha_desde_env, '%d/%m/%Y')
            fecha_hasta = datetime.strptime(fecha_hasta_env, '%d/%m/%Y')
            print(f"📅 Modo .env: Descargando desde {fecha_desde_env} hasta {fecha_hasta_env}")
        except ValueError:
            print("❌ Error: Formato de fecha inválido en .env")
            sys.exit(1)
    else:
        # Por defecto: solo ayer
        ayer = datetime.now() - timedelta(days=1)
        fecha_desde = ayer
        fecha_hasta = ayer
        print(f"📅 Modo automático: Descargando solo ayer ({ayer.strftime('%d/%m/%Y')})")

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
    archivo_cinta = extraer_cinta_testigo(driver, wait, download_dir_cinta, fecha_desde, fecha_hasta)
    
    # 3. EXTRAER TICKETS CON DETALLE
    print("\n" + "=" * 70)
    print("FASE 3: TICKETS CON DETALLE")
    print("=" * 70)
    archivos_tickets = extraer_tickets_detalle(driver, wait, download_dir_detalle, fecha_desde, fecha_hasta)
    
    # 4. EXTRAER CONSUMOS
    print("\n" + "=" * 70)
    print("FASE 4: CONSUMOS")
    print("=" * 70)
    archivo_consumos = extraer_consumos(driver, wait, download_dir_consumos, fecha_desde, fecha_hasta)
    
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
