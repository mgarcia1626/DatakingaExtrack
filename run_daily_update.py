"""
DATAKINGA - ACTUALIZACIÓN DIARIA AUTOMÁTICA
============================================
Este script ejecuta el proceso completo de extracción y actualización de datos:
1. Extrae datos de Datakinga (main.py)
2. Actualiza la base de datos de forma incremental (main_database_incremental.py)

Puede ejecutarse de dos formas:
- Manual: python run_daily_update.py
- Automática: python run_daily_update.py --schedule
  (se ejecutará en los horarios configurados en .env)
"""

import subprocess
import sys
import os
import time
import schedule
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv, set_key

# Cargar variables de entorno
load_dotenv()

# Archivo .env
ENV_FILE = Path(".env")

# Archivo de log
LOG_FILE = Path("DataBase") / "execution_log.txt"

def log_execution(message, execution_type="MANUAL"):
    """Registra la ejecución en el archivo de log"""
    timestamp = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    log_entry = f"[{timestamp}] [{execution_type}] {message}\n"
    
    try:
        # Crear carpeta si no existe
        LOG_FILE.parent.mkdir(exist_ok=True)
        
        # Escribir en el log
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(log_entry)
    except Exception as e:
        print(f"⚠️ No se pudo escribir en el log: {e}")

def save_last_run(success):
    """Guarda información de la última ejecución en .env"""
    timestamp = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    status = "SUCCESS" if success else "ERROR"
    
    try:
        set_key(ENV_FILE, "LAST_RUN_TIME", timestamp)
        set_key(ENV_FILE, "LAST_RUN_STATUS", status)
        print(f"\n💾 Última ejecución guardada: {timestamp} - {status}")
    except Exception as e:
        print(f"⚠️ No se pudo guardar última ejecución: {e}")

def print_header(text):
    """Imprime un encabezado formateado"""
    print("\n" + "=" * 70)
    print(text.center(70))
    print("=" * 70 + "\n")

def run_script(script_name, description):
    """Ejecuta un script de Python y retorna el código de salida"""
    print_header(f"PASO: {description}")
    print(f"⏳ Ejecutando {script_name}...\n")
    
    try:
        # Ejecutar el script
        result = subprocess.run(
            [sys.executable, script_name],
            check=True,
            capture_output=False,
            text=True
        )
        
        print(f"\n✅ {description} completado exitosamente")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"\n❌ ERROR en {description}")
        print(f"   Código de salida: {e.returncode}")
        return False
    except Exception as e:
        print(f"\n❌ ERROR inesperado en {description}: {str(e)}")
        return False

def main():
    """Función principal que orquesta todo el proceso"""
    inicio = datetime.now()
    
    print_header("DATAKINGA - ACTUALIZACIÓN DIARIA AUTOMÁTICA")
    print(f"🕐 Inicio: {inicio.strftime('%d/%m/%Y %H:%M:%S')}\n")
    
    log_execution("Iniciando proceso de actualización", "MANUAL")
    
    # Paso 1: Extraer datos
    if not run_script("main.py", "EXTRACCIÓN DE DATOS"):
        print("\n⚠️ Proceso detenido debido a errores en la extracción")
        save_last_run(success=False)
        log_execution("ERROR: Fallo en extracción de datos", "MANUAL")
        return False
    
    # Paso 2: Actualizar base de datos
    if not run_script("main_database_incremental.py", "ACTUALIZACIÓN DE BASE DE DATOS"):
        print("\n⚠️ Proceso detenido debido a errores en la actualización")
        save_last_run(success=False)
        log_execution("ERROR: Fallo en actualización de base de datos", "MANUAL")
        return False
    
    # Resumen final
    fin = datetime.now()
    duracion = fin - inicio
    
    print_header("PROCESO COMPLETADO EXITOSAMENTE")
    print(f"🕐 Inicio:    {inicio.strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"🕐 Fin:       {fin.strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"⏱️  Duración:  {duracion.total_seconds():.1f} segundos")
    print("\n✅ Todos los pasos completados correctamente")
    print("=" * 70 + "\n")
    
    # Guardar información de última ejecución
    save_last_run(success=True)
    log_execution(f"Proceso completado exitosamente (duración: {duracion.total_seconds():.1f}s)", "MANUAL")
    
    return True

def run_scheduled():
    """Ejecuta el proceso completo y registra en log"""
    print(f"\n{'='*70}")
    print(f"🔔 EJECUCIÓN PROGRAMADA - {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"{'='*70}")
    
    log_execution("Iniciando ejecución programada", "SCHEDULED")
    inicio = datetime.now()
    
    # Ejecutar main
    success = main_without_log()
    
    fin = datetime.now()
    duracion = fin - inicio
    
    if success:
        log_execution(f"Ejecución programada completada exitosamente (duración: {duracion.total_seconds():.1f}s)", "SCHEDULED")
    else:
        log_execution("ERROR: Ejecución programada falló", "SCHEDULED")
        print("\n⚠️ ATENCIÓN: El proceso programado tuvo errores")
    
    return success

def main_without_log():
    """Versión de main sin logging redundante para ejecuciones programadas"""
    inicio = datetime.now()
    
    print_header("DATAKINGA - ACTUALIZACIÓN DIARIA AUTOMÁTICA")
    print(f"🕐 Inicio: {inicio.strftime('%d/%m/%Y %H:%M:%S')}\n")
    
    # Paso 1: Extraer datos
    if not run_script("main.py", "EXTRACCIÓN DE DATOS"):
        print("\n⚠️ Proceso detenido debido a errores en la extracción")
        save_last_run(success=False)
        return False
    
    # Paso 2: Actualizar base de datos
    if not run_script("main_database_incremental.py", "ACTUALIZACIÓN DE BASE DE DATOS"):
        print("\n⚠️ Proceso detenido debido a errores en la actualización")
        save_last_run(success=False)
        return False
    
    # Resumen final
    fin = datetime.now()
    duracion = fin - inicio
    
    print_header("PROCESO COMPLETADO EXITOSAMENTE")
    print(f"🕐 Inicio:    {inicio.strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"🕐 Fin:       {fin.strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"⏱️  Duración:  {duracion.total_seconds():.1f} segundos")
    print("\n✅ Todos los pasos completados correctamente")
    print("=" * 70 + "\n")
    
    # Guardar información de última ejecución
    save_last_run(success=True)
    
    return True

def setup_schedule():
    """Configura los horarios de ejecución desde .env"""
    time_1 = os.getenv('SCHEDULE_TIME_1', '08:00')
    time_2 = os.getenv('SCHEDULE_TIME_2', '14:00')
    time_3 = os.getenv('SCHEDULE_TIME_3', '20:00')
    
    print_header("CONFIGURACIÓN DE HORARIOS AUTOMÁTICOS")
    print(f"📅 Horario 1: {time_1}")
    print(f"📅 Horario 2: {time_2}")
    print(f"📅 Horario 3: {time_3}")
    print(f"\n📄 Log de ejecuciones: {LOG_FILE}")
    print("\n⏰ El proceso se ejecutará automáticamente en estos horarios")
    print("   Presiona Ctrl+C para detener\n")
    print("=" * 70)
    
    # Registrar inicio del scheduler
    log_execution(f"Scheduler iniciado - Horarios: {time_1}, {time_2}, {time_3}", "SYSTEM")
    
    # Programar las 3 ejecuciones diarias
    schedule.every().day.at(time_1).do(run_scheduled)
    schedule.every().day.at(time_2).do(run_scheduled)
    schedule.every().day.at(time_3).do(run_scheduled)
    
    print(f"\n✅ Programación configurada exitosamente")
    print(f"⏳ Esperando siguiente ejecución...\n")
    
    # Loop infinito para mantener el scheduler corriendo
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # Verificar cada minuto
    except KeyboardInterrupt:
        log_execution("Scheduler detenido por el usuario", "SYSTEM")
        print("\n\n⚠️ Programación detenida por el usuario")
        print("=" * 70 + "\n")

if __name__ == "__main__":
    # Verificar si se ejecuta en modo programado
    if len(sys.argv) > 1 and sys.argv[1] == "--schedule":
        setup_schedule()
    else:
        # Ejecución manual única
        success = main()
        sys.exit(0 if success else 1)
