"""
DATAKINGA - Visor de Log de Ejecuciones
=========================================
Muestra el historial de ejecuciones del proceso automático

Uso:
    python view_log.py              # Ver últimas 50 líneas
    python view_log.py --all        # Ver todo el log
    python view_log.py --today      # Ver solo ejecuciones de hoy
    python view_log.py --clear      # Limpiar el log
"""

import sys
from pathlib import Path
from datetime import datetime

LOG_FILE = Path("DataBase") / "execution_log.txt"

def view_log(mode="last"):
    """Muestra el log de ejecuciones"""
    
    if not LOG_FILE.exists():
        print("📄 No hay log de ejecuciones todavía")
        print(f"   El archivo se creará en: {LOG_FILE}")
        return
    
    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    if not lines:
        print("📄 El log está vacío")
        return
    
    print("=" * 80)
    print("DATAKINGA - HISTORIAL DE EJECUCIONES".center(80))
    print("=" * 80)
    print(f"📄 Archivo: {LOG_FILE}")
    print(f"📊 Total de registros: {len(lines)}\n")
    
    if mode == "all":
        print("Mostrando TODAS las ejecuciones:\n")
        for line in lines:
            print(line.rstrip())
    
    elif mode == "today":
        today = datetime.now().strftime('%d/%m/%Y')
        today_lines = [line for line in lines if today in line]
        
        if today_lines:
            print(f"Mostrando ejecuciones de HOY ({today}):\n")
            for line in today_lines:
                print(line.rstrip())
        else:
            print(f"⚠️ No hay ejecuciones registradas para hoy ({today})")
    
    else:  # last
        num_lines = 50
        print(f"Mostrando ÚLTIMAS {num_lines} ejecuciones:\n")
        for line in lines[-num_lines:]:
            print(line.rstrip())
    
    print("\n" + "=" * 80)

def clear_log():
    """Limpia el archivo de log"""
    if not LOG_FILE.exists():
        print("📄 No hay log para limpiar")
        return
    
    confirm = input("⚠️ ¿Estás seguro de que quieres BORRAR todo el log? (s/n): ")
    if confirm.lower() == 's':
        LOG_FILE.unlink()
        print("✅ Log borrado exitosamente")
    else:
        print("❌ Operación cancelada")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        
        if arg == "--all":
            view_log("all")
        elif arg == "--today":
            view_log("today")
        elif arg == "--clear":
            clear_log()
        else:
            print("Uso:")
            print("  python view_log.py              # Ver últimas 50 líneas")
            print("  python view_log.py --all        # Ver todo el log")
            print("  python view_log.py --today      # Ver solo ejecuciones de hoy")
            print("  python view_log.py --clear      # Limpiar el log")
    else:
        view_log("last")
