# -*- coding: utf-8 -*-
content = open('main_dashboard.py', encoding='utf-8').read()

# Remove sqlite3 and Path imports
content = content.replace('import sqlite3\n', '', 1)
content = content.replace('from pathlib import Path\n', '', 1)

# Add supabase import after go import
content = content.replace(
    'import plotly.graph_objects as go\n',
    'import plotly.graph_objects as go\nfrom FunctionsGrouping.supabase_client import get_client, fetch_tickets, fetch_consumos\n',
    1
)

# Replace get_database_path + cargar_datos block
idx_start = content.find('# Funci')
idx_end = content.find('        conn.close()\n') + len('        conn.close()\n')
print('idx_start:', idx_start, 'idx_end:', idx_end)

new_block = '''# Cargar datos
@st.cache_data(ttl=300)
def cargar_datos():
    try:
        client = get_client()
        df_tickets = fetch_tickets(client)
        df_consumos = fetch_consumos(client)
        if 'Cantidad' in df_tickets.columns:
            df_tickets['Cantidad'] = pd.to_numeric(df_tickets['Cantidad'], errors='coerce')
        if 'Importe' in df_tickets.columns:
            df_tickets['Importe'] = pd.to_numeric(df_tickets['Importe'], errors='coerce')
        return df_tickets, df_consumos
    except Exception as e:
        st.error(f'Error al cargar datos desde Supabase: {str(e)}')
        st.info('Verifica que SUPABASE_URL y SUPABASE_KEY esten configurados.')
        st.stop()
'''

content = content[:idx_start] + new_block + '\n' + content[idx_end:]
print('sqlite3 removed:', 'import sqlite3' not in content)
print('fetch_tickets added:', 'fetch_tickets' in content)
open('main_dashboard.py', 'w', encoding='utf-8').write(content)
print('Saved OK')
