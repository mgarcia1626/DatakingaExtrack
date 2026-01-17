# DatakingaExtrack

Script simple para hacer login en Datakinga.com y obtener HTML de páginas.

## Instalación

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

```powershell
python main.py
```

El script:
1. Hace login automático
2. Te pide la URL de la página que quieres
3. Descarga el HTML
4. Opcionalmente lo guarda en un archivo

## Uso Programático

```python
from main import login, get_page_html

# Login
session = login()

# Obtener HTML
html = get_page_html(session, "https://datakinga.com/pagina.aspx")
```
