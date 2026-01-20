"""
DATAKINGA - Actualización incremental de la base de datos
Solo agrega datos nuevos sin eliminar los existentes
"""
import sqlite3
import pandas as pd
from pathlib import Path
import glob
import os
from datetime import datetime

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
    # ========== CONSUMOS - AGREGAR CON FECHA DE CARGA ==========
    print("\n" + "=" * 70)
    print("PROCESANDO: CONSUMOS (CON FECHA DE CARGA)")
    print("=" * 70)
    
    # 1. VERIFICAR ESTRUCTURA DE LA TABLA
    print("\n[1/5] VERIFICANDO ESTRUCTURA DE LA TABLA")
    try:
        # Leer productos existentes con fecha de carga
        df_existentes = pd.read_sql("SELECT Codigo, Articulo, Sucursal, Fecha_Carga FROM consumos", conn)
        print(f"   ✓ {len(df_existentes)} productos en la base de datos")
        tiene_fecha_carga = True
    except Exception as e:
        # Si no existe la columna Fecha_Carga, necesitamos agregar la tabla con la nueva estructura
        try:
            df_existentes = pd.read_sql("SELECT Codigo, Articulo, Sucursal FROM consumos", conn)
            print(f"   ⚠️ Tabla existente sin columna Fecha_Carga. Se agregará.")
            tiene_fecha_carga = False
        except:
            print(f"   ℹ️ No hay tabla consumos todavía (se creará)")
            df_existentes = pd.DataFrame()
            tiene_fecha_carga = False
    
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
                # Ejemplo: consumos_ENTRE_RIOS_18_01_2026.xlsx → SUCURSAL = ENTRE_RIOS
                nombre_archivo = Path(archivo).stem
                partes = nombre_archivo.split('_')
                nombre_sucursal = '_'.join(partes[1:-3])  # Maneja nombres con guiones bajos
                
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
            
            # 4. AGREGAR FECHA DE CARGA
            print("\n[4/5] AGREGANDO FECHA DE CARGA")
            
            # Combinar todos los archivos
            df_nuevos = pd.concat(dataframes, ignore_index=True)
            
            # Agregar fecha y hora de carga actual
            fecha_carga = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            df_nuevos['Fecha_Carga'] = fecha_carga
            
            print(f"   Total productos en archivos: {len(df_nuevos)}")
            print(f"   Fecha de carga: {fecha_carga}")
            
            # 5. INSERTAR O ACTUALIZAR EN LA BASE DE DATOS
            print("\n[5/5] INSERTANDO/ACTUALIZANDO PRODUCTOS EN LA BASE DE DATOS")
            
            if len(df_existentes) == 0 or not tiene_fecha_carga:
                # Crear tabla nueva con estructura correcta
                cursor.execute("DROP TABLE IF EXISTS consumos")
                cursor.execute("""
                    CREATE TABLE consumos (
                        Familia TEXT,
                        Codigo TEXT,
                        Articulo TEXT,
                        Sucursal TEXT,
                        Fecha_Carga TEXT,
                        PRIMARY KEY (Codigo, Articulo, Sucursal)
                    )
                """)
                print("   ✓ Tabla consumos creada con columna Fecha_Carga y clave primaria")
                
                # Si había datos antiguos sin fecha, reinsertarlos con fecha actual
                if len(df_existentes) > 0 and not tiene_fecha_carga:
                    df_existentes['Fecha_Carga'] = fecha_carga
                    df_existentes.to_sql('consumos', conn, if_exists='append', index=False)
                    print(f"   ✓ {len(df_existentes)} productos existentes migrados con fecha")
            
            # Usar INSERT OR REPLACE para actualizar fecha si el producto ya existe
            # Esto actualiza la fecha si (Codigo, Articulo, Sucursal) ya existe, o inserta si es nuevo
            productos_insertados = 0
            productos_actualizados = 0
            
            for _, row in df_nuevos.iterrows():
                # Verificar si el producto ya existe
                cursor.execute("""
                    SELECT Fecha_Carga FROM consumos 
                    WHERE Codigo = ? AND Articulo = ? AND Sucursal = ?
                """, (row['Codigo'], row['Articulo'], row['Sucursal']))
                
                existe = cursor.fetchone()
                
                if existe:
                    # Actualizar solo la fecha
                    cursor.execute("""
                        UPDATE consumos 
                        SET Fecha_Carga = ?
                        WHERE Codigo = ? AND Articulo = ? AND Sucursal = ?
                    """, (fecha_carga, row['Codigo'], row['Articulo'], row['Sucursal']))
                    productos_actualizados += 1
                else:
                    # Insertar nuevo producto
                    cursor.execute("""
                        INSERT INTO consumos (Familia, Codigo, Articulo, Sucursal, Fecha_Carga)
                        VALUES (?, ?, ?, ?, ?)
                    """, (row['Familia'], row['Codigo'], row['Articulo'], row['Sucursal'], fecha_carga))
                    productos_insertados += 1
            
            print(f"   ✓ {productos_insertados} productos nuevos insertados")
            print(f"   ✓ {productos_actualizados} productos existentes actualizados (fecha)")
            
            # Mostrar desglose por sucursal
            print("\n   Desglose por sucursal:")
            for sucursal in df_nuevos['Sucursal'].unique():
                count = len(df_nuevos[df_nuevos['Sucursal'] == sucursal])
                print(f"   • {sucursal}: {count} productos procesados")
            
            # Crear índice para búsqueda rápida (ya no es necesario con PRIMARY KEY)
            # La clave primaria ya crea un índice automático
    
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
                # Formato generado por extraction_functions.py: SUCURSAL_DD_MM_YYYY.xlsx
                # Ejemplo: ENTRE_RIOS_18_01_2026.xlsx → SUCURSAL = ENTRE_RIOS
                nombre_archivo = Path(archivo).stem
                partes = nombre_archivo.split('_')
                
                # Tomar todas las partes excepto las últimas 3 (DD_MM_YYYY)
                nombre_sucursal = '_'.join(partes[:-3]) if len(partes) > 3 else partes[0]
                
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
            if df_cinta is not None:
                print("\n   Agregando columna TURNO desde Cinta Testigo...")
                
                # Buscar la columna de turno (puede ser 'Turno' o 'TURNO')
                turno_col = None
                for col in df_cinta.columns:
                    if col.upper() == 'TURNO':
                        turno_col = col
                        break
                
                # Buscar la columna de número
                numero_col = None
                for col in df_cinta.columns:
                    if col.upper() == 'NÚMERO' or col.upper() == 'NUMERO':
                        numero_col = col
                        break
                
                if turno_col and numero_col:
                    # Renombrar columnas para el merge
                    df_cinta_merge = df_cinta[[numero_col, turno_col]].copy()
                    df_cinta_merge.columns = ['Número', 'Turno']
                    
                    # Hacer merge
                    df_tickets = df_tickets.merge(
                        df_cinta_merge,
                        on='Número',
                        how='left'
                    )
                    registros_con_turno = df_tickets['Turno'].notna().sum()
                    print(f"   ✓ {registros_con_turno} registros con TURNO asignado")
                else:
                    print(f"   ⚠️ No se encontraron columnas necesarias")
                    print(f"   Columnas disponibles: {list(df_cinta.columns)}")
            else:
                print("   ⚠️ No se pudo agregar TURNO (falta archivo de Cinta)")
            
            # 5. DIVIDIR F.CIERRE EN FECHA Y HORA
            print("\n[5/6] PROCESANDO FECHA Y HORA")
            
            fcierre_col = None
            for col in df_tickets.columns:
                if 'cierre' in col.lower():
                    fcierre_col = col
                    print(f"   Columna encontrada: {col}")
                    df_tickets[col] = pd.to_datetime(df_tickets[col], errors='coerce')
                    df_tickets['Fecha'] = df_tickets[col].dt.date
                    df_tickets['Hora'] = df_tickets[col].dt.time
                    print(f"   ✓ Fecha y Hora extraídas")
                    break
            
            # Eliminar columna F.Cierre después de procesarla
            if fcierre_col and fcierre_col in df_tickets.columns:
                df_tickets = df_tickets.drop(columns=[fcierre_col])
                print(f"   ✓ Columna '{fcierre_col}' eliminada (ya se extrajo Fecha y Hora)")
            
            # 6. VALIDAR Y FILTRAR DUPLICADOS
            print("\n[6/8] VALIDANDO CALIDAD DE DATOS")
            
            # Eliminar registros con Sucursal NULL
            registros_antes = len(df_tickets)
            df_tickets = df_tickets[df_tickets['Sucursal'].notna()]
            registros_sin_sucursal = registros_antes - len(df_tickets)
            if registros_sin_sucursal > 0:
                print(f"   ⚠️ Eliminados {registros_sin_sucursal} registros sin Sucursal")
            else:
                print(f"   ✓ Todos los registros tienen Sucursal")
            
            # Eliminar duplicados dentro del mismo DataFrame
            registros_antes = len(df_tickets)
            df_tickets = df_tickets.drop_duplicates()
            duplicados_internos = registros_antes - len(df_tickets)
            if duplicados_internos > 0:
                print(f"   ⚠️ Eliminados {duplicados_internos} duplicados internos")
            else:
                print(f"   ✓ No hay duplicados internos")
            
            print(f"   Total registros válidos: {len(df_tickets)}")
            
            # 7. VALIDAR DUPLICADOS CON LA BASE DE DATOS
            print("\n[7/8] VALIDANDO DUPLICADOS CON BASE DE DATOS")
            
            # Leer tickets existentes de la base de datos
            try:
                df_existentes = pd.read_sql("SELECT * FROM tickets_detalle", conn)
                print(f"   Registros existentes en BD: {len(df_existentes)}")
                
                # Usar solo Número + Código para detectar duplicados (combinación única por línea de ticket)
                # Esto es más confiable que comparar todas las columnas
                df_tickets['_key'] = df_tickets['Número'].astype(str) + '|' + df_tickets['Código'].astype(str)
                df_existentes['_key'] = df_existentes['Número'].astype(str) + '|' + df_existentes['Código'].astype(str)
                
                # Filtrar solo registros nuevos
                keys_existentes = set(df_existentes['_key'])
                df_tickets['es_duplicado'] = df_tickets['_key'].isin(keys_existentes)
                
                duplicados = df_tickets['es_duplicado'].sum()
                df_nuevos = df_tickets[~df_tickets['es_duplicado']].drop(columns=['_key', 'es_duplicado'])
                
                print(f"   Registros en archivos: {len(df_tickets)}")
                print(f"   Duplicados detectados: {duplicados}")
                print(f"   Registros nuevos a insertar: {len(df_nuevos)}")
                
            except Exception as e:
                print(f"   ℹ️ No hay tabla tickets_detalle todavía (se creará): {e}")
                df_nuevos = df_tickets.copy()
                if '_key' in df_nuevos.columns:
                    df_nuevos = df_nuevos.drop(columns=['_key'])
                if 'es_duplicado' in df_nuevos.columns:
                    df_nuevos = df_nuevos.drop(columns=['es_duplicado'])
            
            # 7. INSERTAR SOLO TICKETS NUEVOS
            print("\n[7/7] INSERTANDO TICKETS EN LA BASE DE DATOS")
            
            if len(df_nuevos) > 0:
                # Si no existe la tabla, crearla
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS tickets_detalle (
                        Número TEXT,
                        Tipo TEXT,
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
                
                # Insertar solo registros nuevos (modo append)
                df_nuevos.to_sql('tickets_detalle', conn, if_exists='append', index=False)
                print(f"   ✓ {len(df_nuevos)} registros nuevos insertados")
                
                # Mostrar desglose por sucursal
                print("\n   Desglose por sucursal:")
                for sucursal in df_nuevos['Sucursal'].unique():
                    count = len(df_nuevos[df_nuevos['Sucursal'] == sucursal])
                    print(f"   • {sucursal}: {count} tickets")
            else:
                print("   ℹ️ No hay registros nuevos para insertar (todos son duplicados)")
    
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
