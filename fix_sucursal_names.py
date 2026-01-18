import sqlite3

# Conectar a la base de datos
conn = sqlite3.connect('DataBase/datakinga.db')
cursor = conn.cursor()

print("Actualizando nombres de sucursales para usar guiones bajos...")

# Actualizar consumos
cursor.execute("UPDATE consumos SET Sucursal = REPLACE(Sucursal, ' ', '_')")
print(f"✓ Consumos actualizados: {cursor.rowcount} registros")

# Actualizar tickets_detalle
cursor.execute("UPDATE tickets_detalle SET Sucursal = REPLACE(Sucursal, ' ', '_')")
print(f"✓ Tickets actualizados: {cursor.rowcount} registros")

conn.commit()

# Verificar
print("\n=== SUCURSALES EN CONSUMOS ===")
cursor.execute("SELECT DISTINCT Sucursal FROM consumos ORDER BY Sucursal")
for row in cursor.fetchall():
    print(f"  • {row[0]}")

print("\n=== SUCURSALES EN TICKETS ===")
cursor.execute("SELECT DISTINCT Sucursal FROM tickets_detalle ORDER BY Sucursal")
for row in cursor.fetchall():
    print(f"  • {row[0]}")

conn.close()
print("\n✅ Actualización completada")
