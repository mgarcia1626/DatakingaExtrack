# DatakingaExtrack

Sistema de extracciÃ³n y visualizaciÃ³n de datos de Datakinga.com con dashboard interactivo.

## ðŸ“Š Dashboard

El dashboard estÃ¡ disponible en: [URL de tu Streamlit Cloud]

## InstalaciÃ³n Local

```powershell
pip install -r requirements.txt
```

## ConfiguraciÃ³n

Edita `.env` con tus credenciales:
```env
DATAKINGA_USER=tu_usuario
DATAKINGA_PASSWORD=tu_contraseÃ±a
```

## Uso

### Dashboard Interactivo
```powershell
streamlit run main_dashboard.py
```

### ExtracciÃ³n de Datos
```powershell
python main.py
```

### ActualizaciÃ³n Incremental
```powershell
python main_database_incremental.py
```

### ActualizaciÃ³n Diaria Completa
```powershell
# EjecuciÃ³n manual Ãºnica
python run_daily_update.py

# Modo scheduler (se mantiene corriendo y ejecuta en horarios configurados)
python run_daily_update.py --schedule

# O usando el archivo .bat (Windows)
start_scheduler.bat
```

**Horarios de ejecuciÃ³n automÃ¡tica:**
Los horarios se configuran en el archivo `.env`:
- `SCHEDULE_TIME_1` - Por defecto: 04:00
- `SCHEDULE_TIME_2` - Por defecto: 16:30
- `SCHEDULE_TIME_3` - Por defecto: 22:00

Cuando ejecutas en modo `--schedule`, el script se mantiene corriendo continuamente y ejecutarÃ¡ automÃ¡ticamente el proceso completo (extracciÃ³n + actualizaciÃ³n de BD) en los horarios configurados.

## ðŸš€ Deploy en Streamlit Cloud

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
   Si necesitas actualizar datos en producciÃ³n, agrega en Streamlit Cloud:
   - `DATAKINGA_USER`
   - `DATAKINGA_PASSWORD`

## Estructura del Proyecto

Comandos de uso externo (compatibilidad):
- `main_dashboard.py` - Wrapper compatible para Streamlit
- `main_render.py` - Wrapper compatible para extracción en Render cron
- `main.py` - Wrapper compatible para extracción manual
- `main_database_incremental.py` - Wrapper compatible para actualización incremental
- `run_daily_update.py` - Wrapper compatible para ejecución diaria/scheduler

Nueva estructura interna (`src/`):
- `src/datakinga/apps/dashboard/streamlit_app.py` - App de dashboard
- `src/datakinga/apps/pipelines/extract_pipeline.py` - Pipeline de extracción legacy
- `src/datakinga/apps/pipelines/render_pipeline.py` - Pipeline de extracción para Render
- `src/datakinga/apps/pipelines/incremental_db_pipeline.py` - Pipeline incremental SQLite
- `src/datakinga/apps/scheduler/daily_update_runner.py` - Orquestador diario
- `src/datakinga/apps/tools/` - Utilidades operativas (rebuild/upload)
- `src/datakinga/core/` - Módulos reutilizables (auth, extractors, storage, audit)

Compatibilidad de imports:
- `FunctionsGrouping/` se mantiene como shim para no romper imports históricos.
- El runtime de datos sigue en `DataBase/` durante esta fase.
## Uso Programático

```python
from datakinga.core.extractors.new_site_extraction import login

# Login al nuevo sitio
session = login()
```

## Rebuild Total (Desde Cero) + Auditoria

Si detectas diferencias entre el sistema y la base, usa el rebuild completo:

```powershell
python rebuild_from_zero.py 01/01/2026 06/09/2026
```

Esto hace:
1. Backup de `DataBase/datakinga.db`
2. Limpieza de Excels temporales en `DataBase/Detalle`, `DataBase/Consumos`, `DataBase/Cinta`
3. Descarga nuevamente por bloques mensuales
4. Auditoria de cobertura por sucursales esperadas
5. Auditoria pre-Supabase y subida (solo si pasa)

Opciones utiles:

```powershell
# Solo descarga + auditoria de cobertura (sin subir)
python rebuild_from_zero.py 01/01/2026 06/09/2026 --no-upload

# Simulacion (no ejecuta nada)
python rebuild_from_zero.py 01/01/2026 06/09/2026 --dry-run

# Definir sucursales esperadas manualmente
python rebuild_from_zero.py 01/01/2026 06/09/2026 --expected-sucursales "COSTAVERDE,PASADENA,ENTRE RIOS,SAAVEDRA,SAENZ PENA"
```

Variables de entorno:
- `AUDIT_STRICT=1` (default): bloquea la subida si falla auditoria
- `EXPECTED_SUCURSALES`: cobertura esperada para validar que se extrajo todo



