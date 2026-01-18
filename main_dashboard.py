"""
DATAKINGA - Dashboard Interactivo
Visualización de datos con Streamlit
"""
import streamlit as st
import pandas as pd
import sqlite3
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import plotly.express as px
import plotly.graph_objects as go

# Cargar variables de entorno
load_dotenv()

# Configuración de la página
st.set_page_config(
    page_title="DataKinga Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Título principal
st.title("📊 DataKinga Dashboard")
st.markdown("---")

# Función para obtener la ruta de la base de datos
def get_database_path():
    """Busca la base de datos en múltiples ubicaciones posibles"""
    possible_paths = [
        Path('DataBase/datakinga.db'),  # Desarrollo local
        Path('/mount/src/datakingaextrack/DataBase/datakinga.db'),  # Streamlit Cloud
        Path(__file__).parent / 'DataBase' / 'datakinga.db',  # Relativo al script
    ]
    
    for path in possible_paths:
        if path.exists():
            return str(path)
    
    # Si no se encuentra, mostrar error con ubicaciones buscadas
    st.error("❌ No se encontró la base de datos en ninguna ubicación")
    st.info("Ubicaciones buscadas:")
    for p in possible_paths:
        st.write(f"- {p.absolute()}")
    st.stop()
    
    return None

# Cargar datos
@st.cache_data
def cargar_datos():
    """Carga los datos de la base de datos SQLite"""
    db_path = get_database_path()
    
    # Crear conexión dentro de la función (mejor para el caché de Streamlit)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    
    try:
        # Cargar tickets_detalle
        df_tickets = pd.read_sql_query("SELECT * FROM tickets_detalle", conn)
        
        # Cargar consumos - solo la versión más reciente de cada Codigo+Sucursal
        df_consumos = pd.read_sql_query("""
            SELECT c1.* 
            FROM consumos c1
            INNER JOIN (
                SELECT Codigo, Sucursal, MAX(Fecha_Carga) as max_fecha
                FROM consumos
                GROUP BY Codigo, Sucursal
        ) c2 ON c1.Codigo = c2.Codigo 
            AND c1.Sucursal = c2.Sucursal 
            AND c1.Fecha_Carga = c2.max_fecha
        """, conn)
        
        # Convertir columnas numéricas
        if 'Cantidad' in df_tickets.columns:
            df_tickets['Cantidad'] = pd.to_numeric(df_tickets['Cantidad'], errors='coerce')
        if 'Importe' in df_tickets.columns:
            df_tickets['Importe'] = pd.to_numeric(df_tickets['Importe'], errors='coerce')
        
        return df_tickets, df_consumos
        
    except Exception as e:
        st.error(f"❌ Error al cargar datos de la base de datos: {str(e)}")
        st.info("Verifica que la base de datos tenga las tablas 'tickets_detalle' y 'consumos'")
        raise
    finally:
        conn.close()

df_tickets, df_consumos = cargar_datos()

# Sidebar - Filtros globales
st.sidebar.header("🔍 Filtros")

# Filtro por sucursal (OBLIGATORIO - solo una)
if 'Sucursal' in df_tickets.columns:
    sucursales = sorted(df_tickets['Sucursal'].dropna().unique().tolist())
    if len(sucursales) > 0:
        sucursal_seleccionada = st.sidebar.selectbox(
            "Sucursal",
            sucursales,
            index=0
        )
        df_tickets_filtrado = df_tickets[df_tickets['Sucursal'] == sucursal_seleccionada]
    else:
        st.sidebar.error("⚠️ No hay sucursales disponibles")
        df_tickets_filtrado = df_tickets
else:
    st.sidebar.error("⚠️ No hay columna Sucursal")
    df_tickets_filtrado = df_tickets

# Filtro por rango de fechas
if 'Fecha' in df_tickets_filtrado.columns:
    df_tickets_filtrado = df_tickets_filtrado.copy()
    df_tickets_filtrado['Fecha_dt'] = pd.to_datetime(df_tickets_filtrado['Fecha'])
    fecha_min = df_tickets_filtrado['Fecha_dt'].min().date()
    fecha_max = df_tickets_filtrado['Fecha_dt'].max().date()
    
    st.sidebar.markdown("**Rango de Fechas**")
    col1, col2 = st.sidebar.columns(2)
    
    with col1:
        fecha_desde = st.date_input(
            "Desde",
            value=fecha_min,
            min_value=fecha_min,
            max_value=fecha_max
        )
    
    with col2:
        fecha_hasta = st.date_input(
            "Hasta",
            value=fecha_max,
            min_value=fecha_min,
            max_value=fecha_max
        )
    
    # Aplicar filtro de fechas
    df_tickets_filtrado = df_tickets_filtrado[
        (df_tickets_filtrado['Fecha_dt'].dt.date >= fecha_desde) & 
        (df_tickets_filtrado['Fecha_dt'].dt.date <= fecha_hasta)
    ]
else:
    st.sidebar.warning("⚠️ No hay columna Fecha")

# Filtro por turno (desplegable con opción Todos)
if 'Turno' in df_tickets_filtrado.columns:
    turnos_disponibles = sorted(df_tickets_filtrado['Turno'].dropna().unique().tolist())
    if len(turnos_disponibles) > 0:
        # Agregar opción "Todos" al inicio
        opciones_turno = ["Todos"] + turnos_disponibles
        
        turno_seleccionado = st.sidebar.selectbox(
            "Turno",
            opciones_turno,
            index=0  # Por defecto "Todos"
        )
        
        # Aplicar filtro de turnos solo si no es "Todos"
        if turno_seleccionado != "Todos":
            df_tickets_filtrado = df_tickets_filtrado[df_tickets_filtrado['Turno'] == turno_seleccionado]

# Última actualización (pequeño, debajo del filtro de turno)
st.sidebar.markdown("---")
last_run_time = os.getenv('LAST_RUN_TIME', '')
last_run_status = os.getenv('LAST_RUN_STATUS', '')

if last_run_time:
    status_icon = "✅" if last_run_status == "SUCCESS" else "❌"
    st.sidebar.caption(f"🕐 Última actualización: {last_run_time} {status_icon}")

# Menú de navegación
st.sidebar.markdown("---")
st.sidebar.header("📋 Menú")

# UN SOLO radio button con todas las opciones y separadores
opciones_menu = [
    "Facturación",
    "Análisis por Familia",
    "─────────────",
    "Ranking de productos",
    "Productos mas vendidos", 
    "Productos menos vendidos", 
    "Productos mejor facturacion", 
    "Productos peor facturacion",
    "─────────────",
    "Relaciones por producto", 
    "Relaciones por familia",
    "─────────────",
    "Creación de Combos",
    "─────────────",
    "Análisis de regalos"
]

# Inicializar session_state si no existe
if 'menu_seleccion' not in st.session_state:
    st.session_state.menu_seleccion = "Facturación"

# Encontrar el índice de la selección actual
try:
    index_actual = opciones_menu.index(st.session_state.menu_seleccion)
except ValueError:
    index_actual = 0

menu_opcion_temp = st.sidebar.radio(
    "Selecciona una vista",
    opciones_menu,
    index=index_actual,
    label_visibility="collapsed"
)

# Si se selecciona un separador, mantener la última selección válida
if menu_opcion_temp.startswith("─"):
    menu_opcion = st.session_state.menu_seleccion
else:
    menu_opcion = menu_opcion_temp
    st.session_state.menu_seleccion = menu_opcion

# ========== VISTA: FACTURACIÓN ==========
if menu_opcion == "Facturación":
    st.header("💰 Facturación")
    
    # Calcular métricas del periodo
    if 'Importe' in df_tickets_filtrado.columns and 'Cantidad' in df_tickets_filtrado.columns:
        # Facturación total del periodo
        df_temp_metricas = df_tickets_filtrado.copy()
        df_temp_metricas['Importe_Total'] = df_temp_metricas['Cantidad'] * df_temp_metricas['Importe']
        facturacion_total_periodo = df_temp_metricas['Importe_Total'].sum()
        
        # Cantidad de días facturados (días con al menos una venta)
        if 'Fecha' in df_tickets_filtrado.columns:
            dias_facturados = df_tickets_filtrado['Fecha'].nunique()
        else:
            dias_facturados = 0
        
        # Mostrar métricas
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Facturación Total del Periodo", f"${facturacion_total_periodo:,.2f}")
        with col2:
            st.metric("Cantidad de Días Facturados", f"{dias_facturados}")
        
        st.markdown("---")
    
    # Gráfico de barras: Facturación por día
    st.subheader("📊 Facturación Diaria")
    if 'Fecha' in df_tickets_filtrado.columns and 'Importe' in df_tickets_filtrado.columns:
        if 'Turno' in df_tickets_filtrado.columns:
            # Calcular importe total (Cantidad * Importe unitario)
            df_temp = df_tickets_filtrado.copy()
            df_temp['Importe_Total'] = df_temp['Cantidad'] * df_temp['Importe']
            # Facturación por día y turno (barras apiladas)
            facturacion_diaria_turno = df_temp.groupby(['Fecha', 'Turno'])['Importe_Total'].sum().reset_index()
            facturacion_diaria_turno = facturacion_diaria_turno.rename(columns={'Importe_Total': 'Importe'})
            facturacion_diaria_turno['Fecha'] = pd.to_datetime(facturacion_diaria_turno['Fecha'])
            facturacion_diaria_turno = facturacion_diaria_turno.sort_values('Fecha')
            
            # Crear rango completo de fechas (incluyendo días faltantes)
            fecha_min = facturacion_diaria_turno['Fecha'].min()
            fecha_max = facturacion_diaria_turno['Fecha'].max()
            todas_fechas = pd.date_range(start=fecha_min, end=fecha_max, freq='D')
            todos_turnos = facturacion_diaria_turno['Turno'].unique()
            
            # Crear DataFrame con todas las combinaciones de fecha y turno
            index_completo = pd.MultiIndex.from_product([todas_fechas, todos_turnos], names=['Fecha', 'Turno'])
            df_completo = pd.DataFrame(index=index_completo).reset_index()
            
            # Merge con los datos reales
            facturacion_diaria_turno = df_completo.merge(
                facturacion_diaria_turno,
                on=['Fecha', 'Turno'],
                how='left'
            )
            facturacion_diaria_turno['Importe'] = facturacion_diaria_turno['Importe'].fillna(0)
            
            # Crear etiquetas de fecha con día de la semana en español
            dias_semana = {
                'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'Miércoles',
                'Thursday': 'Jueves', 'Friday': 'Viernes', 'Saturday': 'Sábado', 'Sunday': 'Domingo'
            }
            facturacion_diaria_turno['Fecha_Label'] = facturacion_diaria_turno['Fecha'].apply(
                lambda x: f"{dias_semana[x.strftime('%A')]}<br>{x.day}/{x.month}"
            )
            
            # Función para formatear valores con k y M
            def format_value(val):
                if val == 0:
                    return ""
                elif val >= 1_000_000:
                    return f"${val/1_000_000:.1f}M"
                elif val >= 1_000:
                    return f"${val/1_000:.1f}k"
                else:
                    return f"${val:.0f}"
            
            # Agregar columna formateada
            facturacion_diaria_turno['Texto'] = facturacion_diaria_turno['Importe'].apply(format_value)
            
            # Colores modernos y profesionales
            color_map = {
                turno: color for turno, color in zip(
                    facturacion_diaria_turno['Turno'].unique(),
                    ['#5DADE2', '#58D68D', '#F8B739', '#EC7063', '#AF7AC5']
                )
            }
            
            fig_barras = px.bar(
                facturacion_diaria_turno,
                x='Fecha_Label',
                y='Importe',
                color='Turno',
                title='Facturación Total por Día (por Turno)',
                labels={'Importe': 'Facturación ($)', 'Fecha_Label': 'Día y Fecha', 'Turno': 'Turno'},
                barmode='stack',
                color_discrete_map=color_map,
                text='Texto'
            )
            
            # Configurar el texto dentro de las barras (horizontal, números oscuros)
            fig_barras.update_traces(
                textposition='inside',
                textangle=0,
                textfont=dict(color='#1C2833', size=11, family='Arial', weight='bold')
            )
        else:
            # Calcular importe total (Cantidad * Importe unitario)
            df_temp = df_tickets_filtrado.copy()
            df_temp['Importe_Total'] = df_temp['Cantidad'] * df_temp['Importe']
            # Facturación sin turno
            facturacion_diaria = df_temp.groupby('Fecha')['Importe_Total'].sum().reset_index()
            facturacion_diaria = facturacion_diaria.rename(columns={'Importe_Total': 'Importe'})
            facturacion_diaria['Fecha'] = pd.to_datetime(facturacion_diaria['Fecha'])
            facturacion_diaria = facturacion_diaria.sort_values('Fecha')
            
            # Crear rango completo de fechas (incluyendo días faltantes)
            fecha_min = facturacion_diaria['Fecha'].min()
            fecha_max = facturacion_diaria['Fecha'].max()
            todas_fechas = pd.date_range(start=fecha_min, end=fecha_max, freq='D')
            
            # Reindexar con todas las fechas
            facturacion_diaria = facturacion_diaria.set_index('Fecha').reindex(todas_fechas).reset_index()
            facturacion_diaria = facturacion_diaria.rename(columns={'index': 'Fecha'})
            facturacion_diaria['Importe'] = facturacion_diaria['Importe'].fillna(0)
            
            # Crear etiquetas de fecha con día de la semana en español
            dias_semana = {
                'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'Miércoles',
                'Thursday': 'Jueves', 'Friday': 'Viernes', 'Saturday': 'Sábado', 'Sunday': 'Domingo'
            }
            facturacion_diaria['Fecha_Label'] = facturacion_diaria['Fecha'].apply(
                lambda x: f"{dias_semana[x.strftime('%A')]}<br>{x.day}/{x.month}"
            )
            
            # Función para formatear valores con k y M
            def format_value(val):
                if val == 0:
                    return ""
                elif val >= 1_000_000:
                    return f"${val/1_000_000:.1f}M"
                elif val >= 1_000:
                    return f"${val/1_000:.1f}k"
                else:
                    return f"${val:.0f}"
            
            # Agregar columna formateada
            facturacion_diaria['Texto'] = facturacion_diaria['Importe'].apply(format_value)
            
            fig_barras = px.bar(
                facturacion_diaria,
                x='Fecha_Label',
                y='Importe',
                title='Facturación Total por Día',
                labels={'Importe': 'Facturación ($)', 'Fecha_Label': 'Día y Fecha'},
                text='Texto'
            )
            
            # Configurar colores modernos y texto oscuro dentro de las barras (horizontal)
            fig_barras.update_traces(
                marker_color='#5DADE2',
                textposition='inside',
                textangle=0,
                textfont=dict(color='#1C2833', size=11, family='Arial', weight='bold')
            )
        
        fig_barras.update_layout(
            showlegend=True,
            xaxis_title='Día y Fecha'
        )
        st.plotly_chart(fig_barras, use_container_width=True)
    else:
        st.warning("⚠️ No hay datos de facturación disponibles")
    
    st.markdown("---")
    
    # Gráfico de torta: % de facturación por familia
    st.subheader("🥧 Facturación por Familia")
    if 'Código' in df_tickets_filtrado.columns and 'Importe' in df_tickets_filtrado.columns:
        # Convertir columnas a string para el merge
        df_tickets_temp = df_tickets_filtrado.copy()
        df_consumos_temp = df_consumos.copy()
        
        # Limpiar y normalizar columnas
        df_tickets_temp['Código'] = df_tickets_temp['Código'].astype(str).str.strip().str.upper()
        df_tickets_temp['Sucursal'] = df_tickets_temp['Sucursal'].astype(str).str.strip().str.upper()
        df_consumos_temp['Codigo'] = df_consumos_temp['Codigo'].astype(str).str.strip().str.upper()
        df_consumos_temp['Sucursal'] = df_consumos_temp['Sucursal'].astype(str).str.strip().str.upper()
        
        # Eliminar duplicados en consumos (mismo Codigo+Sucursal, mantener el primero)
        df_consumos_unique = df_consumos_temp.drop_duplicates(subset=['Codigo', 'Sucursal'], keep='first')
        
        # Hacer merge con consumos para obtener la familia (usando Código y Sucursal)
        df_con_familia = df_tickets_temp.merge(
            df_consumos_unique[['Codigo', 'Familia', 'Sucursal']],
            left_on=['Código', 'Sucursal'],
            right_on=['Codigo', 'Sucursal'],
            how='left'
        )
        
        # Filtrar valores nulos en Familia antes de agrupar
        df_con_familia = df_con_familia.dropna(subset=['Familia'])
        
        # Calcular importe total (Cantidad * Importe unitario)
        df_con_familia['Importe_Total'] = df_con_familia['Cantidad'] * df_con_familia['Importe']
        
        # Agrupar por familia
        facturacion_familia = df_con_familia.groupby('Familia')['Importe_Total'].sum().reset_index()
        facturacion_familia = facturacion_familia.rename(columns={'Importe_Total': 'Importe'})
        facturacion_familia = facturacion_familia.sort_values('Importe', ascending=False)
        
        # Calcular porcentajes
        total = facturacion_familia['Importe'].sum()
        facturacion_familia['Porcentaje'] = (facturacion_familia['Importe'] / total * 100).round(2)
        
        # Crear columna con nombre y porcentaje para la leyenda
        facturacion_familia['Familia_Label'] = facturacion_familia.apply(
            lambda row: f"{row['Familia']} ({row['Porcentaje']:.1f}%)", axis=1
        )
        
        fig_torta = px.pie(
            facturacion_familia,
            values='Importe',
            names='Familia_Label',
            title='Distribución de Facturación por Familia',
            hole=0.4,
            custom_data=['Familia']
        )
        fig_torta.update_traces(
            textposition='inside',
            text=facturacion_familia['Familia'],
            hovertemplate='<b>%{customdata[0]}</b><br>Facturación: $%{value:,.2f}<extra></extra>'
        )
        st.plotly_chart(fig_torta, use_container_width=True)
        
        # Mostrar tabla de resumen con formato
        tabla_familia = facturacion_familia[['Familia', 'Importe', 'Porcentaje']].copy()
        tabla_familia['Importe'] = tabla_familia['Importe'].apply(lambda x: f"${x:,.2f}")
        tabla_familia['Porcentaje'] = tabla_familia['Porcentaje'].apply(lambda x: f"{x:.2f}%")
        tabla_familia = tabla_familia.rename(
            columns={'Importe': 'Facturación ($)', 'Porcentaje': '% del Total'}
        )
        
        # Usar HTML para centrar el texto
        st.markdown("""
            <style>
            .centered-table td, .centered-table th {
                text-align: center !important;
                font-size: 110% !important;
            }
            </style>
        """, unsafe_allow_html=True)
        
        st.dataframe(
            tabla_familia,
            use_container_width=True,
            hide_index=True
        )
    else:
        st.warning("⚠️ No hay datos de código para vincular con familias")

# ========== VISTA: PRODUCTOS MAS VENDIDOS ==========
elif menu_opcion == "Productos mas vendidos":
    st.header("📦 Productos mas vendidos")
    
    # Selector de cantidad de productos
    cantidad_productos = st.selectbox(
        "Cantidad de productos a mostrar",
        options=[5, 10, 15, 20, 25, 30],
        index=3  # Por defecto 20
    )
    
    if 'Descripción' in df_tickets_filtrado.columns:
        
        if 'Cantidad' in df_tickets_filtrado.columns:
            top_cantidad = df_tickets_filtrado.groupby('Descripción')['Cantidad'].sum().reset_index()
            top_cantidad = top_cantidad.sort_values('Cantidad', ascending=False).head(cantidad_productos)
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                fig = px.bar(
                    top_cantidad,
                    x='Cantidad',
                    y='Descripción',
                    orientation='h',
                    title=f'Top {cantidad_productos} Productos Más Vendidos',
                    color='Cantidad',
                    color_continuous_scale='Viridis'
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.dataframe(
                    top_cantidad,
                    use_container_width=True,
                    hide_index=True
                )
    else:
        st.warning("⚠️ No hay columna Descripción en los datos")

# ========== VISTA: PRODUCTOS MENOS VENDIDOS ==========
elif menu_opcion == "Productos menos vendidos":
    st.header("📉 Productos menos vendidos")
    
    # Selector de cantidad de productos
    cantidad_productos = st.selectbox(
        "Cantidad de productos a mostrar",
        options=[5, 10, 15, 20, 25, 30],
        index=3  # Por defecto 20
    )
    
    if 'Descripción' in df_tickets_filtrado.columns:
        
        if 'Cantidad' in df_tickets_filtrado.columns:
            bottom_cantidad = df_tickets_filtrado.groupby('Descripción')['Cantidad'].sum().reset_index()
            bottom_cantidad = bottom_cantidad.sort_values('Cantidad', ascending=True).head(cantidad_productos)
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                fig = px.bar(
                    bottom_cantidad,
                    x='Cantidad',
                    y='Descripción',
                    orientation='h',
                    title=f'Top {cantidad_productos} Productos Menos Vendidos',
                    color='Cantidad',
                    color_continuous_scale='Reds_r'
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.dataframe(
                    bottom_cantidad,
                    use_container_width=True,
                    hide_index=True
                )
    else:
        st.warning("⚠️ No hay columna Descripción en los datos")

# ========== VISTA: PRODUCTOS MEJOR FACTURACION ==========
elif menu_opcion == "Productos mejor facturacion":
    st.header("💵 Productos mejor facturacion")
    
    # Selector de cantidad de productos
    cantidad_productos = st.selectbox(
        "Cantidad de productos a mostrar",
        options=[5, 10, 15, 20, 25, 30],
        index=3  # Por defecto 20
    )
    
    if 'Descripción' in df_tickets_filtrado.columns:
        
        if 'Importe' in df_tickets_filtrado.columns and 'Cantidad' in df_tickets_filtrado.columns:
            # Calcular importe total (Cantidad * Importe unitario)
            df_temp = df_tickets_filtrado.copy()
            df_temp['Importe_Total'] = df_temp['Cantidad'] * df_temp['Importe']
            
            top_facturacion = df_temp.groupby('Descripción').agg({
                'Cantidad': 'sum',
                'Importe_Total': 'sum'
            }).reset_index()
            top_facturacion = top_facturacion.rename(columns={'Importe_Total': 'Importe'})
            top_facturacion = top_facturacion.sort_values('Importe', ascending=False).head(cantidad_productos)
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                fig = px.bar(
                    top_facturacion,
                    x='Importe',
                    y='Descripción',
                    orientation='h',
                    title=f'Top {cantidad_productos} Productos por Ingresos',
                    color='Importe',
                    color_continuous_scale='Oranges'
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.dataframe(
                    top_facturacion.rename(columns={'Importe': 'Facturación Total ($)'}),
                    use_container_width=True,
                    hide_index=True
                )
    else:
        st.warning("⚠️ No hay columna Descripción en los datos")

# ========== VISTA: PRODUCTOS PEOR FACTURACION ==========
elif menu_opcion == "Productos peor facturacion":
    st.header("💸 Productos peor facturacion")
    
    # Selector de cantidad de productos
    cantidad_productos = st.selectbox(
        "Cantidad de productos a mostrar",
        options=[5, 10, 15, 20, 25, 30],
        index=3  # Por defecto 20
    )
    
    if 'Descripción' in df_tickets_filtrado.columns:
        
        if 'Importe' in df_tickets_filtrado.columns and 'Cantidad' in df_tickets_filtrado.columns:
            # Calcular importe total (Cantidad * Importe unitario)
            df_temp = df_tickets_filtrado.copy()
            df_temp['Importe_Total'] = df_temp['Cantidad'] * df_temp['Importe']
            
            bottom_facturacion = df_temp.groupby('Descripción').agg({
                'Cantidad': 'sum',
                'Importe_Total': 'sum'
            }).reset_index()
            bottom_facturacion = bottom_facturacion.rename(columns={'Importe_Total': 'Importe'})
            bottom_facturacion = bottom_facturacion.sort_values('Importe', ascending=True).head(cantidad_productos)
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                fig = px.bar(
                    bottom_facturacion,
                    x='Importe',
                    y='Descripción',
                    orientation='h',
                    title=f'Top {cantidad_productos} Productos con Menor Facturación',
                    color='Importe',
                    color_continuous_scale='Reds_r'
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.dataframe(
                    bottom_facturacion.rename(columns={'Importe': 'Facturación Total ($)'}),
                    use_container_width=True,
                    hide_index=True
                )
    else:
        st.warning("⚠️ No hay columna Descripción en los datos")

# ========== VISTA: RELACIONES POR PRODUCTO ==========
elif menu_opcion == "Relaciones por producto":
    st.header("🎯 Relaciones por producto")
    
    if 'Número' in df_tickets_filtrado.columns and 'Descripción' in df_tickets_filtrado.columns:
        
        # Análisis por Producto
        st.subheader("🔍 Análisis de Combos por Producto")
        
        # Selector de cantidad de combos para producto
        cantidad_combos_producto = st.selectbox(
            "Cantidad de combinaciones a mostrar",
            options=[5, 10, 15, 20],
            index=1,  # Por defecto 10
            key="cantidad_combos_producto"
        )
        
        productos_disponibles = sorted(df_tickets_filtrado['Descripción'].dropna().unique().tolist())
        producto_seleccionado = st.selectbox(
            "Selecciona un producto para ver con qué se vende",
            productos_disponibles,
            key="producto_combo"
        )
        
        # Checkbox para omitir productos de la misma familia
        omitir_misma_familia = st.checkbox(
            "Omitir productos de la misma familia",
            value=False,
            key="omitir_familia"
        )
        
        # Multiselect para omitir familias específicas
        if 'Código' in df_tickets_filtrado.columns:
            df_tickets_temp = df_tickets_filtrado.copy()
            df_consumos_temp = df_consumos.copy()
            df_tickets_temp['Código'] = df_tickets_temp['Código'].astype(str)
            df_tickets_temp['Sucursal'] = df_tickets_temp['Sucursal'].astype(str)
            df_consumos_temp['Codigo'] = df_consumos_temp['Codigo'].astype(str)
            df_consumos_temp['Sucursal'] = df_consumos_temp['Sucursal'].astype(str)
            
            df_temp_familias = df_tickets_temp.merge(
                df_consumos_temp[['Codigo', 'Familia', 'Sucursal']],
                left_on=['Código', 'Sucursal'],
                right_on=['Codigo', 'Sucursal'],
                how='left'
            )
            familias_disponibles_filtro = sorted(df_temp_familias['Familia'].dropna().unique().tolist())
            
            familias_omitir = st.multiselect(
                "Omitir productos de las siguientes familias",
                familias_disponibles_filtro,
                default=[],
                key="familias_omitir"
            )
        else:
            familias_omitir = []
        
        if producto_seleccionado:
            # Encontrar todos los tickets que contienen el producto seleccionado
            tickets_con_producto = df_tickets_filtrado[
                df_tickets_filtrado['Descripción'] == producto_seleccionado
            ]['Número'].unique()
            
            # Obtener todos los productos en esos tickets (excepto el producto seleccionado)
            df_combos = df_tickets_filtrado[
                (df_tickets_filtrado['Número'].isin(tickets_con_producto)) &
                (df_tickets_filtrado['Descripción'] != producto_seleccionado)
            ].copy()
            
            # Si el checkbox está marcado, filtrar por familia
            if omitir_misma_familia and 'Código' in df_tickets_filtrado.columns:
                # Merge para obtener familia del producto seleccionado
                df_tickets_temp = df_tickets_filtrado[df_tickets_filtrado['Descripción'] == producto_seleccionado].copy()
                df_consumos_temp = df_consumos.copy()
                df_tickets_temp['Código'] = df_tickets_temp['Código'].astype(str)
                df_tickets_temp['Sucursal'] = df_tickets_temp['Sucursal'].astype(str)
                df_consumos_temp['Codigo'] = df_consumos_temp['Codigo'].astype(str)
                df_consumos_temp['Sucursal'] = df_consumos_temp['Sucursal'].astype(str)
                
                df_temp = df_tickets_temp.merge(
                    df_consumos_temp[['Codigo', 'Familia', 'Sucursal']],
                    left_on=['Código', 'Sucursal'],
                    right_on=['Codigo', 'Sucursal'],
                    how='left'
                )
                
                if len(df_temp) > 0 and 'Familia' in df_temp.columns:
                    familia_producto = df_temp['Familia'].iloc[0]
                    
                    # Merge para obtener familia de los combos
                    df_combos_temp = df_combos.copy()
                    df_consumos_temp2 = df_consumos.copy()
                    df_combos_temp['Código'] = df_combos_temp['Código'].astype(str)
                    df_combos_temp['Sucursal'] = df_combos_temp['Sucursal'].astype(str)
                    df_consumos_temp2['Codigo'] = df_consumos_temp2['Codigo'].astype(str)
                    df_consumos_temp2['Sucursal'] = df_consumos_temp2['Sucursal'].astype(str)
                    
                    df_combos = df_combos_temp.merge(
                        df_consumos_temp2[['Codigo', 'Familia', 'Sucursal']],
                        left_on=['Código', 'Sucursal'],
                        right_on=['Codigo', 'Sucursal'],
                        how='left'
                    )
                    
                    # Filtrar productos de diferente familia
                    df_combos = df_combos[df_combos['Familia'] != familia_producto]
            
            # Aplicar filtro de familias a omitir
            if len(familias_omitir) > 0 and 'Código' in df_tickets_filtrado.columns:
                # Si aún no se hizo merge, hacerlo ahora
                if 'Familia' not in df_combos.columns:
                    df_combos_temp = df_combos.copy()
                    df_consumos_temp3 = df_consumos.copy()
                    df_combos_temp['Código'] = df_combos_temp['Código'].astype(str)
                    df_combos_temp['Sucursal'] = df_combos_temp['Sucursal'].astype(str)
                    df_consumos_temp3['Codigo'] = df_consumos_temp3['Codigo'].astype(str)
                    df_consumos_temp3['Sucursal'] = df_consumos_temp3['Sucursal'].astype(str)
                    
                    df_combos = df_combos_temp.merge(
                        df_consumos_temp3[['Codigo', 'Familia', 'Sucursal']],
                        left_on=['Código', 'Sucursal'],
                        right_on=['Codigo', 'Sucursal'],
                        how='left'
                    )
                
                # Filtrar productos que NO estén en las familias a omitir
                df_combos = df_combos[~df_combos['Familia'].isin(familias_omitir)]
            
            if len(df_combos) > 0:
                # Contar frecuencia de cada producto
                combos_frecuencia = df_combos.groupby('Descripción').size().reset_index(name='Veces')
                combos_frecuencia = combos_frecuencia.sort_values('Veces', ascending=False).head(cantidad_combos_producto)
                
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    fig_combos = px.bar(
                        combos_frecuencia,
                        x='Veces',
                        y='Descripción',
                        orientation='h',
                        title=f'Top {cantidad_combos_producto} Productos que se Venden con "{producto_seleccionado}"',
                        color='Veces',
                        color_continuous_scale='Teal'
                    )
                    st.plotly_chart(fig_combos, use_container_width=True)
                
                with col2:
                    st.dataframe(
                        combos_frecuencia.rename(columns={'Veces': 'Veces Juntos'}),
                        use_container_width=True,
                        hide_index=True
                    )
            else:
                st.info(f"No se encontraron combinaciones para '{producto_seleccionado}'")
    else:
        st.warning("⚠️ Faltan columnas necesarias para análisis de combos")

# ========== VISTA: RELACIONES POR FAMILIA ==========
elif menu_opcion == "Relaciones por familia":
    st.header("📊 Relaciones por familia")
    
    if 'Número' in df_tickets_filtrado.columns and 'Descripción' in df_tickets_filtrado.columns:
        
        # Análisis por Familia
        st.subheader("📊 Análisis de Combos por Familia")
        
        # Selector de cantidad de combos para familia
        cantidad_combos_familia = st.selectbox(
            "Cantidad de combinaciones a mostrar",
            options=[5, 10, 15, 20],
            index=1,  # Por defecto 10
            key="cantidad_combos_familia"
        )
        
        if 'Código' in df_tickets_filtrado.columns:
            # Hacer merge con consumos para obtener familia (usando Código y Sucursal)
            df_tickets_temp = df_tickets_filtrado.copy()
            df_consumos_temp = df_consumos.copy()
            df_tickets_temp['Código'] = df_tickets_temp['Código'].astype(str)
            df_tickets_temp['Sucursal'] = df_tickets_temp['Sucursal'].astype(str)
            df_consumos_temp['Codigo'] = df_consumos_temp['Codigo'].astype(str)
            df_consumos_temp['Sucursal'] = df_consumos_temp['Sucursal'].astype(str)
            
            df_con_familia = df_tickets_temp.merge(
                df_consumos_temp[['Codigo', 'Familia', 'Sucursal']],
                left_on=['Código', 'Sucursal'],
                right_on=['Codigo', 'Sucursal'],
                how='left'
            )
            
            familias_disponibles = sorted(df_con_familia['Familia'].dropna().unique().tolist())
            familia_combo_seleccionada = st.selectbox(
                "Selecciona una familia para análisis de combos",
                familias_disponibles,
                key="familia_combo"
            )
            
            if familia_combo_seleccionada:
                # Obtener productos de la familia seleccionada
                df_familia_combo = df_con_familia[df_con_familia['Familia'] == familia_combo_seleccionada]
                
                # Encontrar top 5 más vendidos de la familia
                top5_familia_combo = df_familia_combo.groupby('Descripción')['Cantidad'].sum().reset_index()
                top5_familia_combo = top5_familia_combo.sort_values('Cantidad', ascending=False).head(5)
                
                st.write(f"**Top 5 Productos de {familia_combo_seleccionada}:**")
                for producto in top5_familia_combo['Descripción'].tolist():
                    st.write(f"• {producto}")
                
                st.markdown("---")
                
                # Analizar combinaciones para cada producto del top 5
                st.write(f"**Combinaciones de los Top 5 de {familia_combo_seleccionada}:**")
                
                for producto in top5_familia_combo['Descripción'].tolist():
                    with st.expander(f"🔗 Combinaciones de: {producto}"):
                        # Encontrar tickets con este producto
                        tickets_producto = df_con_familia[
                            df_con_familia['Descripción'] == producto
                        ]['Número'].unique()
                        
                        # Productos que aparecen en esos tickets (excepto el producto actual)
                        df_combos_familia = df_con_familia[
                            (df_con_familia['Número'].isin(tickets_producto)) &
                            (df_con_familia['Descripción'] != producto)
                        ]
                        
                        if len(df_combos_familia) > 0:
                            # Contar por producto (sin importar la familia)
                            combos_por_producto = df_combos_familia.groupby('Descripción').size().reset_index(name='Veces')
                            combos_por_producto = combos_por_producto.sort_values('Veces', ascending=False).head(cantidad_combos_familia)
                            
                            col1, col2 = st.columns([2, 1])
                            
                            with col1:
                                fig = px.bar(
                                    combos_por_producto,
                                    x='Veces',
                                    y='Descripción',
                                    orientation='h',
                                    title=f'Productos que se Combinan con {producto}',
                                    color='Veces',
                                    color_continuous_scale='Purp'
                                )
                                st.plotly_chart(fig, use_container_width=True)
                            
                            with col2:
                                st.dataframe(
                                    combos_por_producto.rename(columns={'Veces': 'Veces Juntos'}),
                                    use_container_width=True,
                                    hide_index=True
                                )
                        else:
                            st.info("No se encontraron combinaciones")
        else:
            st.warning("⚠️ No hay datos de código para vincular con familias")
    else:
        st.warning("⚠️ Faltan columnas necesarias para análisis de combos")

# ========== VISTA: ANÁLISIS POR FAMILIA ==========
elif menu_opcion == "Análisis por Familia":
    st.header("📊 Análisis por Familia")
    
    if 'Código' in df_tickets_filtrado.columns and 'Importe' in df_tickets_filtrado.columns:
        # Hacer merge con consumos para obtener la familia (usando Código y Sucursal)
        df_tickets_temp = df_tickets_filtrado.copy()
        df_consumos_temp = df_consumos.copy()
        df_tickets_temp['Código'] = df_tickets_temp['Código'].astype(str)
        df_tickets_temp['Sucursal'] = df_tickets_temp['Sucursal'].astype(str)
        df_consumos_temp['Codigo'] = df_consumos_temp['Codigo'].astype(str)
        df_consumos_temp['Sucursal'] = df_consumos_temp['Sucursal'].astype(str)
        
        df_con_familia = df_tickets_temp.merge(
            df_consumos_temp[['Codigo', 'Familia', 'Articulo', 'Sucursal']],
            left_on=['Código', 'Sucursal'],
            right_on=['Codigo', 'Sucursal'],
            how='left'
        )
        
        # Gráfico de torta: % de facturación por familia (fijo)
        st.subheader("💰 Distribución de Facturación por Familia")
        
        # Filtrar valores nulos en Familia antes de agrupar
        df_con_familia_limpio = df_con_familia.dropna(subset=['Familia'])
        
        # Calcular importe total (Cantidad * Importe unitario)
        df_con_familia_limpio['Importe_Total'] = df_con_familia_limpio['Cantidad'] * df_con_familia_limpio['Importe']
        
        facturacion_familia = df_con_familia_limpio.groupby('Familia')['Importe_Total'].sum().reset_index()
        facturacion_familia = facturacion_familia.rename(columns={'Importe_Total': 'Importe'})
        total_facturacion = facturacion_familia['Importe'].sum()
        facturacion_familia['Porcentaje'] = (facturacion_familia['Importe'] / total_facturacion * 100).round(2)
        facturacion_familia = facturacion_familia.sort_values('Importe', ascending=False)
        
        # Crear columna con nombre y porcentaje para la leyenda
        facturacion_familia['Familia_Label'] = facturacion_familia.apply(
            lambda row: f"{row['Familia']} ({row['Porcentaje']:.1f}%)", axis=1
        )
        
        fig_familia = px.pie(
            facturacion_familia,
            values='Importe',
            names='Familia_Label',
            title='Porcentaje de Facturación por Familia',
            hole=0.4,
            custom_data=['Familia']
        )
        fig_familia.update_traces(
            textposition='inside',
            text=facturacion_familia['Familia'],
            hovertemplate='<b>%{customdata[0]}</b><br>Facturación: $%{value:,.2f}<extra></extra>'
        )
        st.plotly_chart(fig_familia, use_container_width=True)
        
        st.markdown("---")
        
        # Selector de familia
        familias_disponibles = sorted(df_con_familia['Familia'].dropna().unique().tolist())
        
        if len(familias_disponibles) > 0:
            familia_seleccionada = st.selectbox(
                "Selecciona una familia para análisis detallado",
                familias_disponibles
            )
        else:
            st.warning("⚠️ No hay familias disponibles para esta sucursal")
            familia_seleccionada = None
        
        if familia_seleccionada:
            df_familia = df_con_familia[df_con_familia['Familia'] == familia_seleccionada]
            
            st.subheader(f"🔍 Análisis Detallado: {familia_seleccionada}")
            
            # Gráfico de torta: % de productos dentro de la familia
            st.markdown("### 🥧 Distribución de Productos en la Familia")
            
            # Calcular importe total (Cantidad * Importe unitario)
            df_familia['Importe_Total'] = df_familia['Cantidad'] * df_familia['Importe']
            productos_familia = df_familia.groupby('Descripción')['Importe_Total'].sum().reset_index()
            productos_familia = productos_familia.rename(columns={'Importe_Total': 'Importe'})
            total_familia = productos_familia['Importe'].sum()
            productos_familia['Porcentaje'] = (productos_familia['Importe'] / total_familia * 100).round(2)
            productos_familia = productos_familia.sort_values('Importe', ascending=False)
            
            # Crear columna con nombre y porcentaje para la leyenda
            productos_familia['Producto_Label'] = productos_familia.apply(
                lambda row: f"{row['Descripción']} ({row['Porcentaje']:.1f}%)", axis=1
            )
            
            fig_torta_familia = px.pie(
                productos_familia,
                values='Importe',
                names='Producto_Label',
                title=f'Distribución de Facturación en {familia_seleccionada}',
                hole=0.4,
                custom_data=['Descripción']
            )
            fig_torta_familia.update_traces(
                textposition='inside',
                text=productos_familia['Descripción'],
                hovertemplate='<b>%{customdata[0]}</b><br>Facturación: $%{value:,.2f}<extra></extra>'
            )
            st.plotly_chart(fig_torta_familia, use_container_width=True)
            
            st.markdown("---")
            
            # Lista completa de productos con cantidad y facturación
            st.markdown("### 📋 Lista Completa de Productos")
            
            if 'Cantidad' in df_familia.columns:
                # Calcular importe total (Cantidad * Importe unitario)
                df_familia['Importe_Total'] = df_familia['Cantidad'] * df_familia['Importe']
                
                productos_completos = df_familia.groupby('Descripción').agg({
                    'Cantidad': 'sum',
                    'Importe_Total': 'sum'
                }).reset_index()
                
                # Calcular totales
                total_cantidad_familia = productos_completos['Cantidad'].sum()
                total_importe_familia = productos_completos['Importe_Total'].sum()
                
                # Mostrar totales ARRIBA de la tabla
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Total Cantidad Vendida", f"{total_cantidad_familia:,.0f}")
                with col2:
                    st.metric("Total Facturación", f"${total_importe_familia:,.2f}")
                
                st.markdown("")  # Espacio
                
                # Calcular porcentajes
                productos_completos['% Facturación'] = (productos_completos['Importe_Total'] / total_importe_familia * 100).round(2)
                
                # Ordenar por facturación descendente
                productos_completos = productos_completos.sort_values('Importe_Total', ascending=False)
                
                # Formatear valores como en la tabla de facturación
                tabla_display = productos_completos[['Descripción', 'Cantidad', 'Importe_Total', '% Facturación']].copy()
                tabla_display['Cantidad'] = tabla_display['Cantidad'].apply(lambda x: f"{x:,.0f}")
                tabla_display['Importe_Total'] = tabla_display['Importe_Total'].apply(lambda x: f"${x:,.2f}")
                tabla_display['% Facturación'] = tabla_display['% Facturación'].apply(lambda x: f"{x:.2f}%")
                tabla_display = tabla_display.rename(
                    columns={
                        'Cantidad': 'Cantidad Vendida',
                        'Importe_Total': 'Facturación ($)',
                        '% Facturación': '% facturado sobre total de la familia'
                    }
                )
                
                # Usar el mismo estilo que la tabla de facturación
                st.markdown("""
                    <style>
                    .centered-table td, .centered-table th {
                        text-align: center !important;
                        font-size: 110% !important;
                    }
                    </style>
                """, unsafe_allow_html=True)
                
                # Mostrar tabla completa
                st.dataframe(
                    tabla_display,
                    use_container_width=True,
                    hide_index=True,
                    height=600
                )
    else:
        st.warning("⚠️ No hay datos suficientes para análisis por familia")

# ========== VISTA: RANKING DE PRODUCTOS ==========
elif menu_opcion == "Ranking de productos":
    st.header("🏆 Ranking de productos")
    
    if 'Descripción' in df_tickets_filtrado.columns and 'Cantidad' in df_tickets_filtrado.columns and 'Importe' in df_tickets_filtrado.columns:
        # Calcular importe total por producto
        df_temp = df_tickets_filtrado.copy()
        df_temp['Importe_Total'] = df_temp['Cantidad'] * df_temp['Importe']
        
        # Agrupar por producto
        ranking_productos = df_temp.groupby('Descripción').agg({
            'Cantidad': 'sum',
            'Importe_Total': 'sum'
        }).reset_index()
        
        # Calcular porcentaje de facturación
        facturacion_total_periodo = ranking_productos['Importe_Total'].sum()
        ranking_productos['% Facturación'] = (ranking_productos['Importe_Total'] / facturacion_total_periodo * 100).round(2)
        
        # Ordenar de más vendido a menos vendido
        ranking_productos = ranking_productos.sort_values('Cantidad', ascending=False)
        
        # Agregar columna de ranking
        ranking_productos.insert(0, 'Ranking', range(1, len(ranking_productos) + 1))
        
        # Mostrar métricas del periodo
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total de Productos", f"{len(ranking_productos):,}")
        with col2:
            cantidad_total = ranking_productos['Cantidad'].sum()
            st.metric("Cantidad Total Vendida", f"{cantidad_total:,.0f}")
        with col3:
            st.metric("Facturación Total", f"${facturacion_total_periodo:,.2f}")
        
        st.markdown("---")
        
        # Nota explicativa
        st.info("ℹ️ **Nota:** El ranking se basa en la cantidad total vendida de cada producto durante el período seleccionado.")
        
        # Buscador de producto
        buscar_producto = st.text_input("🔍 Buscar producto", placeholder="Escribe el nombre del producto...", key="buscar_ranking")
        
        # Formatear valores para la tabla
        tabla_ranking = ranking_productos.copy()
        
        # Filtrar por búsqueda si hay texto
        if buscar_producto:
            tabla_ranking = tabla_ranking[tabla_ranking['Descripción'].str.contains(buscar_producto, case=False, na=False)]
        
        tabla_ranking['Cantidad'] = tabla_ranking['Cantidad'].apply(lambda x: f"{x:,.0f}")
        tabla_ranking['Importe_Total'] = tabla_ranking['Importe_Total'].apply(lambda x: f"${x:,.2f}")
        tabla_ranking['% Facturación'] = tabla_ranking['% Facturación'].apply(lambda x: f"{x:.2f}%")
        
        tabla_ranking = tabla_ranking.rename(columns={
            'Ranking': '#',
            'Descripción': 'Producto',
            'Cantidad': 'Cantidad Vendida',
            'Importe_Total': 'Facturación Total',
            '% Facturación': '% del Total'
        })
        
        # Aplicar estilos
        st.markdown("""
            <style>
            .ranking-table td, .ranking-table th {
                text-align: center !important;
                font-size: 110% !important;
            }
            </style>
        """, unsafe_allow_html=True)
        
        # Mostrar tabla completa
        if len(tabla_ranking) > 0:
            st.dataframe(
                tabla_ranking,
                use_container_width=True,
                hide_index=True,
                height=600
            )
        else:
            st.warning(f"No se encontraron productos que coincidan con '{buscar_producto}'")
    else:
        st.warning("⚠️ Faltan columnas necesarias para el ranking de productos")

# ========== VISTA: CREACIÓN DE COMBOS ==========
elif menu_opcion == "Creación de Combos":
    st.header("🎨 Creación de Combos")
    
    if 'Código' in df_tickets_filtrado.columns and 'Descripción' in df_tickets_filtrado.columns:
        st.write("Selecciona una o más familias para ver los productos más y menos vendidos de cada una.")
        
        # Hacer merge con consumos para obtener familias
        df_tickets_temp = df_tickets_filtrado.copy()
        df_consumos_temp = df_consumos.copy()
        df_tickets_temp['Código'] = df_tickets_temp['Código'].astype(str).str.strip().str.upper()
        df_tickets_temp['Sucursal'] = df_tickets_temp['Sucursal'].astype(str).str.strip().str.upper()
        df_consumos_temp['Codigo'] = df_consumos_temp['Codigo'].astype(str).str.strip().str.upper()
        df_consumos_temp['Sucursal'] = df_consumos_temp['Sucursal'].astype(str).str.strip().str.upper()
        
        df_con_familia = df_tickets_temp.merge(
            df_consumos_temp[['Codigo', 'Familia', 'Sucursal']],
            left_on=['Código', 'Sucursal'],
            right_on=['Codigo', 'Sucursal'],
            how='left'
        )
        
        # Obtener lista de familias disponibles
        familias_disponibles = sorted(df_con_familia['Familia'].dropna().unique().tolist())
        
        # Selector de cantidad de productos a mostrar
        cantidad_top = st.selectbox(
            "Cantidad de productos a mostrar en cada top",
            options=[5, 10, 15, 20],
            index=0,  # Por defecto 5
            key="cantidad_top_combos"
        )
        
        # Multiselect para elegir familias
        familias_seleccionadas = st.multiselect(
            "Selecciona las familias que deseas analizar",
            familias_disponibles,
            default=[],
            key="familias_combo"
        )
        
        if len(familias_seleccionadas) == 0:
            st.info("ℹ️ Selecciona al menos una familia para comenzar")
        else:
            st.markdown("---")
            
            # Por cada familia seleccionada, mostrar top más y menos vendidos
            for familia in familias_seleccionadas:
                st.subheader(f"📦 {familia}")
                
                # Filtrar productos de esta familia
                df_familia = df_con_familia[df_con_familia['Familia'] == familia]
                
                if len(df_familia) > 0 and 'Cantidad' in df_familia.columns:
                    # Agrupar por producto y sumar cantidades
                    productos_familia = df_familia.groupby('Descripción')['Cantidad'].sum().reset_index()
                    productos_familia = productos_familia.sort_values('Cantidad', ascending=False)
                    
                    # Top más vendidos
                    top_mas = productos_familia.head(cantidad_top).copy()
                    top_mas['Cantidad'] = top_mas['Cantidad'].apply(lambda x: f"{x:,.0f}")
                    
                    # Top menos vendidos
                    top_menos = productos_familia.tail(cantidad_top).sort_values('Cantidad', ascending=True).copy()
                    top_menos['Cantidad'] = top_menos['Cantidad'].apply(lambda x: f"{x:,.0f}")
                    
                    # Mostrar ambas tablas en columnas
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown(f"**✅ Top {cantidad_top} Más Vendidos**")
                        st.dataframe(
                            top_mas.rename(columns={'Descripción': 'Producto', 'Cantidad': 'Cantidad Vendida'}),
                            use_container_width=True,
                            hide_index=True
                        )
                    
                    with col2:
                        st.markdown(f"**⚠️ Top {cantidad_top} Menos Vendidos**")
                        st.dataframe(
                            top_menos.rename(columns={'Descripción': 'Producto', 'Cantidad': 'Cantidad Vendida'}),
                            use_container_width=True,
                            hide_index=True
                        )
                    
                    st.markdown("---")
                else:
                    st.warning(f"⚠️ No hay datos de cantidad para la familia {familia}")
    else:
        st.warning("⚠️ Faltan columnas necesarias para análisis de combos")

# ========== VISTA: ANÁLISIS DE REGALOS ==========
elif menu_opcion == "Análisis de regalos":
    st.header("🎁 Análisis de regalos")
    
    if 'Número' in df_tickets_filtrado.columns and 'Descripción' in df_tickets_filtrado.columns:
        # Obtener todos los productos
        productos_disponibles = sorted(df_tickets_filtrado['Descripción'].dropna().unique().tolist())
        
        # Filtrar productos que contengan "regalo" (por defecto)
        productos_regalo = [p for p in productos_disponibles if 'regalo' in p.lower()]
        
        # Determinar el índice por defecto
        if len(productos_regalo) > 0:
            producto_default = productos_regalo[0]
            indice_default = productos_disponibles.index(producto_default)
        else:
            indice_default = 0
        
        # Selector de producto regalo
        producto_regalo_seleccionado = st.selectbox(
            "Selecciona el producto regalo",
            productos_disponibles,
            index=indice_default,
            key="producto_regalo"
        )
        
        # Campo para ingresar el costo del producto
        costo_unitario = st.number_input(
            "Costo unitario del producto seleccionado ($)",
            min_value=0.0,
            value=0.0,
            step=0.01,
            format="%.2f",
            key="costo_regalo"
        )
        
        st.markdown("---")
        
        # Buscar tickets que contienen el producto regalo seleccionado
        tickets_con_regalo = df_tickets_filtrado[
            df_tickets_filtrado['Descripción'] == producto_regalo_seleccionado
        ]['Número'].unique()
        
        if len(tickets_con_regalo) > 0:
            # Filtrar todos los productos en esos tickets
            df_productos_en_tickets = df_tickets_filtrado[
                df_tickets_filtrado['Número'].isin(tickets_con_regalo)
            ].copy()
            
            # Calcular importe total por producto
            if 'Cantidad' in df_productos_en_tickets.columns and 'Importe' in df_productos_en_tickets.columns:
                df_productos_en_tickets['Importe_Total'] = df_productos_en_tickets['Cantidad'] * df_productos_en_tickets['Importe']
                
                # Agrupar por producto
                resumen_productos = df_productos_en_tickets.groupby('Descripción').agg({
                    'Cantidad': 'sum',
                    'Importe_Total': 'sum'
                }).reset_index()
                
                # Ordenar por facturación descendente
                resumen_productos = resumen_productos.sort_values('Importe_Total', ascending=False)
                
                # Calcular totales
                facturacion_total_tickets = resumen_productos['Importe_Total'].sum()
                cantidad_regalo = resumen_productos[
                    resumen_productos['Descripción'] == producto_regalo_seleccionado
                ]['Cantidad'].sum()
                costo_total = cantidad_regalo * costo_unitario
                
                # Mostrar métricas
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Tickets con el producto", f"{len(tickets_con_regalo):,}")
                with col2:
                    st.metric("Cantidad del producto regalo", f"{cantidad_regalo:,.0f}")
                with col3:
                    st.metric(
                        f"Facturado debido a '{producto_regalo_seleccionado}'",
                        f"${facturacion_total_tickets:,.2f}"
                    )
                with col4:
                    st.metric("Costo total", f"${costo_total:,.2f}")
                
                st.markdown("---")
                
                # Formatear tabla
                tabla_productos = resumen_productos.copy()
                tabla_productos['Cantidad'] = tabla_productos['Cantidad'].apply(lambda x: f"{x:,.0f}")
                tabla_productos['Importe_Total'] = tabla_productos['Importe_Total'].apply(lambda x: f"${x:,.2f}")
                
                tabla_productos = tabla_productos.rename(columns={
                    'Descripción': 'Producto',
                    'Cantidad': 'Cantidad Vendida',
                    'Importe_Total': 'Facturación en estos Tickets'
                })
                
                # Mostrar tabla
                st.subheader("📋 Productos vendidos en tickets con el regalo")
                st.dataframe(
                    tabla_productos,
                    use_container_width=True,
                    hide_index=True,
                    height=500
                )
            else:
                st.warning("⚠️ Faltan columnas de Cantidad o Importe")
        else:
            st.info(f"No se encontraron tickets con el producto '{producto_regalo_seleccionado}'")
    else:
        st.warning("⚠️ Faltan columnas necesarias para el análisis de regalos")

# Footer
st.markdown("---")
st.caption("DataKinga Dashboard v1.0 - Datos actualizados en tiempo real")
