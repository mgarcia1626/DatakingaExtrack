"""
DATAKINGA - Actualización incremental de la base de datos
Solo agrega datos nuevos sin eliminar los existentes
"""
import sqlite3
import pandas as pd
from pathlib import Path
import glob

print("=" * 70)
print("DATAKINGA - ACTUALIZACIÓN INCREMENTAL")
print("=" * 70)

# Ruta a la base de datos
db_path = Path('DataBase/datakinga.db')
print(f"\n📁 Base de datos: {db_path}")

# Conectar a SQLite
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    # ========== CONSUMOS - SOLO PRODUCTOS NUEVOS ==========
    print("\n" + "=" * 70)
    print("PROCESANDO: CONSUMOS (SOLO PRODUCTOS NUEVOS)")
    print("=" * 70)
    
    # 1. LEER PRODUCTOS EXISTENTES EN LA BASE DE DATOS
    print("\n[1/5] LEYENDO PRODUCTOS EXISTENTES EN LA BASE DE DATOS")
    try:
        df_existentes = pd.read_sql("SELECT Codigo, Sucursal FROM consumos", conn)
        # Crear set de tuplas para búsqueda rápida
        productos_existentes = set(zip(df_existentes['Codigo'], df_existentes['Sucursal']))
        print(f"   ✓ {len(productos_existentes)} productos únicos en la base de datos")
    except Exception as e:
        print(f"   ℹ️ No hay tabla consumos todavía (se creará): {e}")
        productos_existentes = set()
    
    # 2. BUSCAR ARCHIVOS DE CONSUMOS NUEVOS
    print("\n[2/5] BUSCANDO ARCHIVOS DE CONSUMOS")
    consumos_folder = Path('DataBase/Consumos')
    
    if not consumos_folder.exists():
        print(f"   ⚠️ No existe la carpeta {consumos_folder}")
    else:
        archivos = []
        archivos.extend(glob.glob(str(consumos_folder / '*.xls')))
        archivos.extend(glob.glob(str(consumos_folder / '*.xlsx')))
        
        if not archivos:
            print(f"   ⚠️ No se encontraron archivos Excel en {consumos_folder}")
        else:
            print(f"   ✓ {len(archivos)} archivos encontrados")
            
            # 3. LEER Y COMBINAR ARCHIVOS
            print("\n[3/5] LEYENDO ARCHIVOS DE CONSUMOS")
            
            dataframes = []
            
            for archivo in archivos:
                # Extraer nombre de sucursal del nombre del archivo
                # Formato: consumos_SUCURSAL_DD_MM_YYYY.xlsx
                nombre_archivo = Path(archivo).stem
                partes = nombre_archivo.split('_')
                nombre_sucursal = '_'.join(partes[1:-3])  # Maneja nombres con espacios
                
                print(f"   📄 {nombre_archivo}")
                print(f"      Sucursal: {nombre_sucursal}")
                
                # Leer archivo
                df_raw = pd.read_excel(archivo, header=None)
                
                # Extraer headers (fila 4, índice 3)
                headers = df_raw.iloc[3].tolist()
                
                # Datos empiezan en fila 5 (índice 4)
                df_temp = df_raw.iloc[4:].copy()
                
                # Mantener solo las primeras 3 columnas
                df_temp = df_temp.iloc[:, :3]
                df_temp.columns = ['Familia', 'Codigo', 'Articulo']
                
                # Agregar columna de Sucursal
                df_temp['Sucursal'] = nombre_sucursal
                
                # Eliminar filas con NaN en columnas críticas
                df_temp = df_temp.dropna(subset=['Codigo', 'Articulo'])
                
                dataframes.append(df_temp)
                print(f"      ✓ {len(df_temp)} productos leídos")
            
            # 4. FILTRAR SOLO PRODUCTOS NUEVOS
            print("\n[4/5] FILTRANDO PRODUCTOS NUEVOS")
            
            # Combinar todos los archivos
            df_nuevos = pd.concat(dataframes, ignore_index=True)
            print(f"   Total productos en archivos: {len(df_nuevos)}")
            
            # Filtrar solo los que NO existen en la base de datos
            df_nuevos['existe'] = df_nuevos.apply(
                lambda row: (row['Codigo'], row['Sucursal']) in productos_existentes,
                axis=1
            )
            
            df_a_insertar = df_nuevos[~df_nuevos['existe']].drop(columns=['existe'])
            productos_repetidos = df_nuevos['existe'].sum()
            
            print(f"   ✓ Productos nuevos a insertar: {len(df_a_insertar)}")
            print(f"   ℹ️ Productos ya existentes (omitidos): {productos_repetidos}")
            
            # 5. INSERTAR SOLO PRODUCTOS NUEVOS
            if len(df_a_insertar) > 0:
                print("\n[5/5] INSERTANDO PRODUCTOS NUEVOS EN LA BASE DE DATOS")
                
                # Si no existe la tabla, crearla
                if len(productos_existentes) == 0:
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS consumos (
                            Familia TEXT,
                            Codigo TEXT,
                            Articulo TEXT,
                            Sucursal TEXT,
                            PRIMARY KEY (Codigo, Sucursal)
                        )
                    """)
                
                # Insertar nuevos productos
                df_a_insertar.to_sql('consumos', conn, if_exists='append', index=False)
                print(f"   ✓ {len(df_a_insertar)} productos nuevos insertados")
                
                # Mostrar desglose por sucursal
                print("\n   Desglose por sucursal:")
                for sucursal in df_a_insertar['Sucursal'].unique():
                    count = len(df_a_insertar[df_a_insertar['Sucursal'] == sucursal])
                    print(f"   • {sucursal}: {count} productos nuevos")
            else:
                print("\n[5/5] No hay productos nuevos para insertar")
    
    # ========== TICKETS DETALLE - INSERTAR TODOS ==========
    print("\n" + "=" * 70)
    print("PROCESANDO: TICKETS DETALLE (INSERTAR TODOS)")
    print("=" * 70)
    
    # 1. LEER CINTA TESTIGO PARA OBTENER TURNO
    print("\n[1/6] LEYENDO CINTA TESTIGO")
    cinta_folder = Path('DataBase/Cinta')
    
    df_cinta = None
    if not cinta_folder.exists():
        print(f"   ⚠️ No existe la carpeta {cinta_folder}")
    else:
        archivos_cinta = []
        archivos_cinta.extend(glob.glob(str(cinta_folder / '*.xls')))
        archivos_cinta.extend(glob.glob(str(cinta_folder / '*.xlsx')))
        
        if not archivos_cinta:
            print(f"   ⚠️ No se encontraron archivos de Cinta Testigo")
        else:
            # Tomar el archivo más reciente
            archivo_cinta = max(archivos_cinta, key=os.path.getmtime)
            print(f"   📄 {Path(archivo_cinta).name}")
            
            # Leer archivo
            df_raw_cinta = pd.read_excel(archivo_cinta, header=None)
            headers_cinta = df_raw_cinta.iloc[3].tolist()
            df_cinta = df_raw_cinta.iloc[4:].copy()
            df_cinta.columns = headers_cinta
            df_cinta = df_cinta.dropna(subset=['Número'])
            
            print(f"   ✓ {len(df_cinta)} registros leídos")
            print(f"   Columnas: {list(df_cinta.columns)}")
    
    # 2. BUSCAR ARCHIVOS DE TICKETS
    print("\n[2/6] BUSCANDO ARCHIVOS DE TICKETS DETALLE")
    detalle_folder = Path('DataBase/Detalle')
    
    if not detalle_folder.exists():
        print(f"   ⚠️ No existe la carpeta {detalle_folder}")
    else:
        archivos_detalle = []
        archivos_detalle.extend(glob.glob(str(detalle_folder / '*.xls')))
        archivos_detalle.extend(glob.glob(str(detalle_folder / '*.xlsx')))
        
        if not archivos_detalle:
            print(f"   ⚠️ No se encontraron archivos Excel en {detalle_folder}")
        else:
            print(f"   ✓ {len(archivos_detalle)} archivos encontrados")
            
            # 3. LEER Y COMBINAR ARCHIVOS
            print("\n[3/6] LEYENDO ARCHIVOS DE TICKETS DETALLE")
            
            dataframes_detalle = []
            
            for archivo in archivos_detalle:
                # Formato puede ser: Ticket_SUCURSAL.xlsx o tickets_detalle_SUCURSAL_DD_MM_YYYY_HH_MM_SS.xlsx
                nombre_archivo = Path(archivo).stem
                partes = nombre_archivo.split('_')
                
                # Si empieza con "tickets_detalle", formato largo
                if partes[0].lower() == 'tickets' and len(partes) > 2:
                    nombre_sucursal = '_'.join(partes[2:-6])  # tickets_detalle_SUCURSAL_DD_MM_YYYY_HH_MM_SS
                else:
                    # Formato simple: Ticket_SUCURSAL
                    nombre_sucursal = '_'.join(partes[1:])
                
                print(f"   📄 {nombre_archivo}")
                print(f"      Sucursal: {nombre_sucursal}")
                
                # Leer archivo
                df_raw = pd.read_excel(archivo, header=None)
                headers = df_raw.iloc[3].tolist()
                df_temp = df_raw.iloc[4:].copy()
                df_temp.columns = headers
                
                # Eliminar columna Sucursal si existe (viene vacía del archivo)
                if 'Sucursal' in df_temp.columns:
                    df_temp = df_temp.drop(columns=['Sucursal'])
                
                # Agregar columna Sucursal con el valor correcto
                df_temp['Sucursal'] = nombre_sucursal
                
                df_temp = df_temp.dropna(subset=['Número'])
                
                dataframes_detalle.append(df_temp)
                print(f"      ✓ {len(df_temp)} registros leídos")
            
            # 4. COMBINAR Y AGREGAR TURNO
            print("\n[4/6] COMBINANDO DATOS Y AGREGANDO TURNO")
            
            df_tickets = pd.concat(dataframes_detalle, ignore_index=True)
            print(f"   Total registros: {len(df_tickets)}")
            
            # Agregar TURNO desde Cinta Testigo
            if df_cinta is not None and 'TURNO' in df_cinta.columns:
                print("\n   Agregando columna TURNO desde Cinta Testigo...")
                df_tickets = df_tickets.merge(
                    df_cinta[['Número', 'TURNO']],
                    on='Número',
                    how='left'
                )
                registros_con_turno = df_tickets['TURNO'].notna().sum()
                print(f"   ✓ {registros_con_turno} registros con TURNO asignado")
            else:
                print("   ⚠️ No se pudo agregar TURNO (falta archivo o columna)")
            
            # 5. DIVIDIR F.CIERRE EN FECHA Y HORA
            print("\n[5/6] PROCESANDO FECHA Y HORA")
            
            for col in df_tickets.columns:
                if 'cierre' in col.lower():
                    print(f"   Columna encontrada: {col}")
                    df_tickets[col] = pd.to_datetime(df_tickets[col], errors='coerce')
                    df_tickets['Fecha'] = df_tickets[col].dt.date
                    df_tickets['Hora'] = df_tickets[col].dt.time
                    print(f"   ✓ Fecha y Hora extraídas")
                    break
            
            # 6. INSERTAR TICKETS EN LA BASE DE DATOS
            print("\n[6/6] INSERTANDO TICKETS EN LA BASE DE DATOS")
            
            # Si no existe la tabla, crearla
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tickets_detalle (
                    Número TEXT,
                    Tipo TEXT,
                    "F.Cierre" TEXT,
                    Sucursal TEXT,
                    Mesa TEXT,
                    Mozo TEXT,
                    Nombre TEXT,
                    Código TEXT,
                    Descripción TEXT,
                    Cantidad REAL,
                    Importe REAL,
                    Turno TEXT,
                    Fecha TEXT,
                    Hora TEXT
                )
            """)
            
            # Insertar todos los registros (modo append)
            df_tickets.to_sql('tickets_detalle', conn, if_exists='append', index=False)
            print(f"   ✓ {len(df_tickets)} registros insertados")
            
            # Mostrar desglose por sucursal
            print("\n   Desglose por sucursal:")
            for sucursal in df_tickets['Sucursal'].unique():
                count = len(df_tickets[df_tickets['Sucursal'] == sucursal])
                print(f"   • {sucursal}: {count} tickets")
    
    # ========== RESUMEN FINAL ==========
    print("\n" + "=" * 70)
    print("RESUMEN DE ACTUALIZACIÓN")
    print("=" * 70)
    
    # Contar totales en la base de datos
    cursor.execute("SELECT COUNT(*) FROM consumos")
    total_consumos = cursor.fetchone()[0]
    print(f"\n✓ Total productos en consumos: {total_consumos}")
    
    cursor.execute("SELECT COUNT(*) FROM tickets_detalle")
    total_tickets = cursor.fetchone()[0]
    print(f"✓ Total registros en tickets_detalle: {total_tickets}")
    
    # Commit cambios
    conn.commit()
    print("\n✅ ACTUALIZACIÓN INCREMENTAL COMPLETADA")
    
    # ========== LIMPIAR CARPETAS ==========
    print("\n" + "=" * 70)
    print("LIMPIANDO CARPETAS")
    print("=" * 70)
    
    carpetas_limpiar = [
        Path('DataBase/Consumos'),
        Path('DataBase/Detalle'),
        Path('DataBase/Cinta')
    ]
    
    archivos_eliminados = 0
    for carpeta in carpetas_limpiar:
        if carpeta.exists():
            archivos = []
            archivos.extend(glob.glob(str(carpeta / '*.xls')))
            archivos.extend(glob.glob(str(carpeta / '*.xlsx')))
            
            for archivo in archivos:
                try:
                    os.remove(archivo)
                    archivos_eliminados += 1
                    print(f"   ✓ Eliminado: {Path(archivo).name}")
                except Exception as e:
                    print(f"   ⚠️ Error eliminando {Path(archivo).name}: {e}")
    
    print(f"\n✓ Total archivos eliminados: {archivos_eliminados}")
    print("✅ CARPETAS LIMPIADAS")
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    conn.rollback()

finally:
    conn.close()
    print("\n📊 Base de datos cerrada")
    print("=" * 70)
