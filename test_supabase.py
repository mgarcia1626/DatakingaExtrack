import os, sys
from dotenv import load_dotenv
load_dotenv()

print('=' * 60)
print('DATAKINGA - Supabase Connection Test')
print('=' * 60)
print()

url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_KEY')
print('[1] SUPABASE_URL:', url)
if key:
    print('[1] SUPABASE_KEY:', key[:20] + '...')
else:
    print('[1] SUPABASE_KEY: NOT SET')
if not url or not key:
    print('ERROR: Set SUPABASE_URL and SUPABASE_KEY in .env')
    sys.exit(1)

from supabase import create_client
try:
    client = create_client(url, key)
    print('[2] Client created OK')
except Exception as e:
    print('[2] ERROR creating client:', e)
    sys.exit(1)

print()
print('--- Testing tickets_detalle table ---')
try:
    resp = client.table('tickets_detalle').select('id').limit(1).execute()
    print('[3] Table exists. Rows sampled:', len(resp.data))
except Exception as e:
    print('[3] ERROR - table may not exist:', e)
    print('    -> Run supabase_create_tables.sql in the Supabase SQL Editor first')

print()
print('--- Testing consumos table ---')
try:
    resp = client.table('consumos').select('id').limit(1).execute()
    print('[4] Table exists. Rows sampled:', len(resp.data))
except Exception as e:
    print('[4] ERROR - table may not exist:', e)
    print('    -> Run supabase_create_tables.sql in the Supabase SQL Editor first')

print()
print('--- Insert test row into tickets_detalle ---')
test_row = {
    'numero': 'TEST-001', 'tipo': 'TEST', 'sucursal': 'TEST_SUCURSAL',
    'mesa': '0', 'mozo': 'TestUser', 'nombre': 'Test Product',
    'codigo': 'TEST-CODE-001', 'descripcion': 'Fila de prueba - borrar',
    'cantidad': 1, 'importe': 99.99, 'turno': 'T1',
    'fecha': '2026-01-01', 'hora': '10:00:00',
}
inserted_id = None
try:
    resp = client.table('tickets_detalle').insert(test_row).execute()
    inserted_id = resp.data[0]['id'] if resp.data else None
    print('[5] Insert OK - id:', inserted_id)
except Exception as e:
    print('[5] ERROR inserting:', e)

print()
print('--- Read test row back ---')
try:
    resp = client.table('tickets_detalle').select('*').eq('numero', 'TEST-001').execute()
    if resp.data:
        row = resp.data[0]
        print('[6] Read OK: numero=' + str(row['numero']) + ', importe=' + str(row['importe']))
    else:
        print('[6] Row not found after insert')
except Exception as e:
    print('[6] ERROR reading:', e)

print()
print('--- Upsert test consumo ---')
test_consumo = {
    'familia': 'TEST_FAM', 'codigo': 'TEST-CODE-001',
    'articulo': 'Producto de Prueba', 'sucursal': 'TEST_SUCURSAL',
    'fecha_carga': '2026-01-01 10:00:00',
}
try:
    resp = client.table('consumos').upsert(test_consumo, on_conflict='codigo,articulo,sucursal').execute()
    print('[7] Upsert consumo OK')
except Exception as e:
    print('[7] ERROR upserting consumo:', e)

print()
print('--- Row counts ---')
try:
    t = client.table('tickets_detalle').select('id', count='exact').execute()
    c = client.table('consumos').select('id', count='exact').execute()
    print('[8] tickets_detalle:', t.count, 'rows')
    print('[8] consumos:       ', c.count, 'rows')
except Exception as e:
    print('[8] ERROR counting:', e)

print()
print('--- Cleanup test data ---')
try:
    client.table('tickets_detalle').delete().eq('numero', 'TEST-001').execute()
    client.table('consumos').delete().eq('codigo', 'TEST-CODE-001').eq('sucursal', 'TEST_SUCURSAL').execute()
    print('[9] Test rows deleted OK')
except Exception as e:
    print('[9] ERROR during cleanup:', e)

print()
print('=' * 60)
print('Test complete')
print('=' * 60)
