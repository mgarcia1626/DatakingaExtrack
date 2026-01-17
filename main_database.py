"""
DATAKINGA - Cargar datos a SQLite (Prueba con Consumos)
"""
import sqlite3
import pandas as pd
from pathlib import Path
import glob
import os

print("=" * 70)
print("DATAKINGA - CARGA A BASE DE DATOS")
print("=" * 70)

# Ruta a la base de datos
db_path = Path('DataBase/datakinga.db')
print(f"\n📁 Base de datos: {db_path}")

# Conectar a SQLite (se crea automáticamente si no existe)
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    # ========== CONSUMOS ==========
    print("\n" + "=" * 70)
    print("PROCESANDO: CONSUMOS POR SUCURSAL")
    print("=" * 70)
    
    # 1. BUSCAR TODOS LOS ARCHIVOS DE CONSUMOS
    print("\n[1/3] BUSCANDO ARCHIVOS DE CONSUMOS")
    consumos_folder = Path('DataBase/Consumos')
    
    if not consumos_folder.exists():
        print(f"   ⚠️ No existe la carpeta {consumos_folder}")
    else:
        # Buscar archivos .xls o .xlsx
        archivos = []
        archivos.extend(glob.glob(str(consumos_folder / '*.xls')))
        archivos.extend(glob.glob(str(consumos_folder / '*.xlsx')))
        
        if not archivos:
            print(f"   ⚠️ No se encontraron archivos Excel en {consumos_folder}")
        else:
            print(f"   ✓ {len(archivos)} archivos encontrados")
            
            # 2. LEER Y COMBINAR TODOS LOS ARCHIVOS
            print("\n[2/3] LEYENDO Y COMBINANDO ARCHIVOS")
            
            dataframes = []
            
            for archivo in archivos:
                nombre_archivo = os.path.basename(archivo)
                print(f"\n   Procesando: {nombre_archivo}")
                
                # Extraer nombre exacto de sucursal del archivo
                # Formato esperado desde extraction_functions: consumos_NOMBRESUCURSAL_DD_MM_YYYY.xlsx
                partes = nombre_archivo.replace('.xls', '').replace('.xlsx', '').split('_')
                
                if partes[0].lower() == 'consumos' and len(partes) >= 5:
                    # Formato automático: consumos_SUCURSAL_DD_MM_YYYY
                    nombre_sucursal = '_'.join(partes[1:-3])
                else:
                    # Formato manual: Consumo_SUCURSAL o similar
                    nombre_sucursal = '_'.join(partes[1:])
                
                print(f"   Sucursal: {nombre_sucursal}")
                
                # Leer archivo sin headers
                df_raw = pd.read_excel(archivo, header=None)
                
                # Extraer headers de la fila 3 (índice 3)
                headers = df_raw.iloc[3].tolist()
                
                # Extraer datos desde la fila 4 en adelante (índice 4+)
                df_temp = df_raw.iloc[4:].copy()
                df_temp.columns = headers
                
                # Mantener solo las primeras 3 columnas
                df_temp = df_temp.iloc[:, :3]
                df_temp.columns = ['Familia', 'Codigo', 'Articulo']
                
                # Agregar columna Sucursal
                df_temp['Sucursal'] = nombre_sucursal
                
                # Reset index
                df_temp = df_temp.reset_index(drop=True)
                
                dataframes.append(df_temp)
                print(f"   ✓ {len(df_temp)} registros procesados")
            
            # Combinar todos los DataFrames
            df_final = pd.concat(dataframes, ignore_index=True)
            
            print(f"\n   Total combinado: {len(df_final)} registros de {len(archivos)} sucursales")
            print(f"\n   Primeras 5 filas:")
            print(df_final.head(5).to_string(index=False))
            
            # 3. CARGAR A SQLITE
            print("\n[3/3] CARGANDO A SQLITE")
            cursor.execute("DROP TABLE IF EXISTS consumos")
            df_final.to_sql('consumos', conn, if_exists='replace', index=False)
            print(f"   ✓ {len(df_final)} registros insertados en tabla 'consumos'")
            print(f"   ✓ Columnas: Familia, Codigo, Articulo, Sucursal")
    
    # ========== DETALLE ==========
    print("\n" + "=" * 70)
    print("PROCESANDO: TICKETS CON DETALLE")
    print("=" * 70)
    
    # 1. BUSCAR TODOS LOS ARCHIVOS DE DETALLE
    print("\n[1/4] BUSCANDO ARCHIVOS DE DETALLE")
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
            for archivo in archivos_detalle:
                print(f"      - {os.path.basename(archivo)}")
            
            # 2. LEER Y COMBINAR TODOS LOS ARCHIVOS
            print("\n[2/4] LEYENDO Y COMBINANDO ARCHIVOS")
            
            df_list = []
            for i, archivo in enumerate(archivos_detalle):
                # Extraer nombre exacto de sucursal del archivo
                # Formato esperado desde extraction_functions: tickets_detalle_NOMBRESUCURSAL_DD_MM_YYYY_HH_MM_SS.xlsx
                nombre_archivo = os.path.basename(archivo).replace('.xlsx', '').replace('.xls', '')
                partes = nombre_archivo.split('_')
                
                if partes[0].lower() == 'tickets' and len(partes) > 2:
                    # Formato automático: tickets_detalle_SUCURSAL_DD_MM_YYYY_HH_MM_SS
                    # partes = [tickets, detalle, SUCURSAL..., DD, MM, YYYY, HH, MM, SS]
                    # Necesitamos todo entre posición 2 y los últimos 6 elementos (DD_MM_YYYY_HH_MM_SS)
                    nombre_sucursal = '_'.join(partes[2:-6])
                else:
                    # Formato manual: Ticket_SUCURSAL o similar
                    nombre_sucursal = '_'.join(partes[1:])
                
                print(f"\n   Procesando: {nombre_sucursal}")
                
                # Leer Excel sin procesar primero
                df_raw = pd.read_excel(archivo, header=None)
                
                if i == 0:  # Solo mostrar para el primer archivo
                    print(f"\n      DEBUG - Primeras 5 filas del archivo RAW:")
                    print(df_raw.head(5).to_string(index=True))
                
                # Las primeras 3 filas son basura, la fila 3 (índice 3) tiene los encabezados
                # Extraer los encabezados de la fila 3
                headers = df_raw.iloc[3].tolist()
                print(f"      Headers encontrados en fila 3: {headers}")
                
                # Tomar datos desde la fila 4 en adelante
                df_temp = df_raw.iloc[4:].copy()
                df_temp.columns = headers
                
                print(f"      Datos: {len(df_temp)} filas")
                
                # Eliminar columna Sucursal si existe (viene vacía del archivo)
                if 'Sucursal' in df_temp.columns:
                    df_temp = df_temp.drop(columns=['Sucursal'])
                
                # Agregar columna Sucursal con el valor correcto
                df_temp['Sucursal'] = nombre_sucursal
                print(f"      ✓ Columna 'Sucursal' configurada: {nombre_sucursal}")
                
                # Reset index
                df_temp = df_temp.reset_index(drop=True)
                
                df_list.append(df_temp)
                print(f"      ✓ {len(df_temp)} filas agregadas")
            
            # Combinar todos los DataFrames
            df_detalle = pd.concat(df_list, ignore_index=True)
            print(f"\n   ✓ Total combinado: {len(df_detalle)} filas")
            print(f"   ✓ Columnas finales: {list(df_detalle.columns)}")
            
            print(f"\n   Primeras 3 filas:")
            print(df_detalle.head(3).to_string(index=False))
            
            # 3. AGREGAR COLUMNA TURNO DESDE CINTA TESTIGO
            print("\n[3/4] AGREGANDO COLUMNA TURNO DESDE CINTA TESTIGO")
            
            # Buscar archivo de Cinta Testigo
            cinta_folder = Path('DataBase/Cinta')
            archivos_cinta = []
            archivos_cinta.extend(glob.glob(str(cinta_folder / '*.xls')))
            archivos_cinta.extend(glob.glob(str(cinta_folder / '*.xlsx')))
            
            if not archivos_cinta:
                print(f"   ⚠️ No se encontró archivo de Cinta Testigo")
            else:
                archivo_cinta = max(archivos_cinta, key=os.path.getctime)
                print(f"   ✓ Archivo Cinta encontrado: {os.path.basename(archivo_cinta)}")
                
                # Leer Cinta Testigo
                df_cinta_raw = pd.read_excel(archivo_cinta, header=None)
                
                print(f"\n   DEBUG - Primeras 5 filas de Cinta RAW:")
                print(df_cinta_raw.head(5).to_string(index=True))
                
                # Extraer headers de la fila correcta (probar fila 3)
                headers_cinta = df_cinta_raw.iloc[3].tolist()
                print(f"\n   Headers Cinta en fila 3: {headers_cinta}")
                
                # Tomar datos desde la fila 4
                df_cinta = df_cinta_raw.iloc[4:].copy()
                df_cinta.columns = headers_cinta
                df_cinta = df_cinta.reset_index(drop=True)
                
                print(f"   ✓ Cinta Testigo: {len(df_cinta)} registros")
                
                # Verificar que existan las columnas necesarias
                if 'Número' in df_cinta.columns or 'NUMERO' in df_cinta.columns:
                    # Normalizar nombre de columna
                    numero_col = 'Número' if 'Número' in df_cinta.columns else 'NUMERO'
                    
                    if 'Turno' in df_cinta.columns or 'TURNO' in df_cinta.columns:
                        turno_col = 'Turno' if 'Turno' in df_cinta.columns else 'TURNO'
                        
                        # Extraer solo Número y Turno
                        df_turno = df_cinta[[numero_col, turno_col]].copy()
                        df_turno.columns = ['Numero', 'Turno']
                        
                        print(f"   ✓ Columnas extraídas: Numero y Turno")
                        print(f"\n   Ejemplo de datos:")
                        print(df_turno.head(3).to_string(index=False))
                        
                        # Hacer merge con tickets_detalle
                        # Primero verificar nombre de columna Número en detalle
                        numero_detalle_col = None
                        for col in df_detalle.columns:
                            if col.lower() in ['número', 'numero']:
                                numero_detalle_col = col
                                break
                        
                        if numero_detalle_col:
                            print(f"\n   Haciendo JOIN por columna '{numero_detalle_col}'...")
                            
                            # Renombrar temporalmente para el merge
                            df_detalle_temp = df_detalle.rename(columns={numero_detalle_col: 'Numero'})
                            
                            # Merge left: mantener todos los registros de detalle
                            df_detalle_final = df_detalle_temp.merge(
                                df_turno[['Numero', 'Turno']], 
                                on='Numero', 
                                how='left'
                            )
                            
                            # Restaurar nombre original de columna Numero
                            df_detalle_final = df_detalle_final.rename(columns={'Numero': numero_detalle_col})
                            
                            df_detalle = df_detalle_final
                            
                            print(f"   ✓ Columna TURNO agregada")
                            print(f"   ✓ Columnas finales: {list(df_detalle.columns)}")
                        else:
                            print(f"   ⚠️ No se encontró columna Número en tickets_detalle")
                    else:
                        print(f"   ⚠️ No se encontró columna TURNO en Cinta Testigo")
                        print(f"   Columnas disponibles: {list(df_cinta.columns)}")
                else:
                    print(f"   ⚠️ No se encontró columna NUMERO en Cinta Testigo")
                    print(f"   Columnas disponibles: {list(df_cinta.columns)}")
            
            # 3.5 SEPARAR F.CIERRE EN FECHA Y HORA
            print("\n[3.5/4] SEPARANDO F.CIERRE EN FECHA Y HORA")
            
            # Buscar columna F.Cierre o F. Cierre
            fcierre_col = None
            for col in df_detalle.columns:
                if 'cierre' in str(col).lower():
                    fcierre_col = col
                    break
            
            if fcierre_col:
                print(f"   ✓ Columna encontrada: '{fcierre_col}'")
                
                # Convertir a datetime
                df_detalle[fcierre_col] = pd.to_datetime(df_detalle[fcierre_col], errors='coerce')
                
                # Extraer fecha (solo día) y hora
                df_detalle['Fecha'] = df_detalle[fcierre_col].dt.date
                df_detalle['Hora'] = df_detalle[fcierre_col].dt.time
                
                print(f"   ✓ Columnas creadas: 'Fecha' y 'Hora'")
                print(f"\n   Ejemplo:")
                print(f"      {fcierre_col}: {df_detalle[fcierre_col].iloc[0]}")
                print(f"      Fecha: {df_detalle['Fecha'].iloc[0]}")
                print(f"      Hora: {df_detalle['Hora'].iloc[0]}")
            else:
                print(f"   ⚠️ No se encontró columna F.Cierre")
                print(f"   Columnas disponibles: {list(df_detalle.columns)}")
            
            # 4. CARGAR A SQLITE
            print("\n[4/4] CARGANDO A SQLITE")
            cursor.execute("DROP TABLE IF EXISTS tickets_detalle")
            df_detalle.to_sql('tickets_detalle', conn, if_exists='replace', index=False)
            print(f"   ✓ {len(df_detalle)} registros insertados en tabla 'tickets_detalle'")
    
    conn.commit()
    conn.commit()
    
    # RESUMEN FINAL
    print("\n" + "=" * 70)
    print("✅ CARGA COMPLETADA")
    print("=" * 70)
    
    # Contar registros en cada tabla
    tablas = ['consumos', 'tickets_detalle']
    print(f"\n📊 Resumen de tablas:")
    for tabla in tablas:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {tabla}")
            count = cursor.fetchone()[0]
            print(f"   - {tabla}: {count} registros")
        except:
            print(f"   - {tabla}: No existe")
    
    print(f"\n📁 Base de datos: {db_path}")
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

finally:
    conn.close()
    print("\n✓ Conexión cerrada")
