# DatakingaExtrack

Sistema de extracción y visualización de datos de Datakinga.com con dashboard interactivo.

## 📊 Dashboard

El dashboard está disponible en: [URL de tu Streamlit Cloud]

## Instalación Local

```powershell
pip install -r requirements.txt
```

## Configuración

Edita `.env` con tus credenciales:
```env
DATAKINGA_USER=tu_usuario
DATAKINGA_PASSWORD=tu_contraseña
```

## Uso

### Dashboard Interactivo
```powershell
streamlit run main_dashboard.py
```

### Extracción de Datos
```powershell
python main.py
```

### Actualización Incremental
```powershell
python main_database_incremental.py
```

### Actualización Diaria Completa
```powershell
# Ejecución manual única
python run_daily_update.py

# Modo scheduler (se mantiene corriendo y ejecuta en horarios configurados)
python run_daily_update.py --schedule

# O usando el archivo .bat (Windows)
start_scheduler.bat
```

**Horarios de ejecución automática:**
Los horarios se configuran en el archivo `.env`:
- `SCHEDULE_TIME_1` - Por defecto: 04:00
- `SCHEDULE_TIME_2` - Por defecto: 16:30
- `SCHEDULE_TIME_3` - Por defecto: 22:00

Cuando ejecutas en modo `--schedule`, el script se mantiene corriendo continuamente y ejecutará automáticamente el proceso completo (extracción + actualización de BD) en los horarios configurados.

## 🚀 Deploy en Streamlit Cloud

1. **Preparar el repositorio:**
   ```powershell
   git add DataBase/datakinga.db
   git commit -m "Add database for Streamlit Cloud"
   git push
   ```

2. **Configurar en Streamlit Cloud:**
   - Ve a [share.streamlit.io](https://share.streamlit.io)
   - Conecta tu repositorio
   - Selecciona `main_dashboard.py` como archivo principal
   - Deploy!

3. **Variables de entorno (opcional):**
   Si necesitas actualizar datos en producción, agrega en Streamlit Cloud:
   - `DATAKINGA_USER`
   - `DATAKINGA_PASSWORD`

## Estructura del Proyecto

- `main_dashboard.py` - Dashboard interactivo con Streamlit
- `main.py` - Script de extracción manual
- `main_database_incremental.py` - Actualización incremental de la BD
- `DataBase/datakinga.db` - Base de datos SQLite
- `FunctionsGrouping/` - Módulos de funciones

## Uso Programático

```python
from main import login, get_page_html

# Login
session = login()

# Obtener HTML
html = get_page_html(session, "https://datakinga.com/pagina.aspx")
```
