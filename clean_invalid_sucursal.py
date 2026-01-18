import sqlite3
import pandas as pd

# Conectar a la base de datos
conn = sqlite3.connect('DataBase/datakinga.db')
cursor = conn.cursor()

# Mostrar registros antes de limpiar
print("Estado ANTES de limpiar:")
df_before = pd.read_sql('SELECT Sucursal, COUNT(*) as count FROM tickets_detalle GROUP BY Sucursal', conn)
print(df_before)
print(f"\nTotal registros: {df_before['count'].sum()}\n")

# Eliminar registros con Sucursal inválida (que contenga fechas)
cursor.execute("DELETE FROM tickets_detalle WHERE Sucursal LIKE '%_01_2026'")
conn.commit()
deleted = cursor.rowcount
print(f"✓ Eliminados {deleted} registros con Sucursal inválida\n")

# Mostrar registros después de limpiar
print("Estado DESPUÉS de limpiar:")
df_after = pd.read_sql('SELECT Sucursal, COUNT(*) as count FROM tickets_detalle GROUP BY Sucursal', conn)
print(df_after)
print(f"\nTotal registros: {df_after['count'].sum()}")

conn.close()
