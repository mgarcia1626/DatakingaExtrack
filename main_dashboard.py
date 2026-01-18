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

# Conectar a la base de datos
@st.cache_resource
def get_database_connection():
    db_path = Path('DataBase/datakinga.db')
    if not db_path.exists():
        st.error(f"❌ No se encontró la base de datos: {db_path}")
        st.stop()
    return sqlite3.connect(db_path, check_same_thread=False)

conn = get_database_connection()

# Cargar datos
@st.cache_data
def cargar_datos():
    # Cargar tickets_detalle
    df_tickets = pd.read_sql_query("SELECT * FROM tickets_detalle", conn)
    
    # Cargar consumos
    df_consumos = pd.read_sql_query("SELECT * FROM consumos", conn)
    
    # Convertir columnas numéricas
    if 'Cantidad' in df_tickets.columns:
        df_tickets['Cantidad'] = pd.to_numeric(df_tickets['Cantidad'], errors='coerce')
    if 'Importe' in df_tickets.columns:
        df_tickets['Importe'] = pd.to_numeric(df_tickets['Importe'], errors='coerce')
    
    return df_tickets, df_consumos

df_tickets, df_consumos = cargar_datos()

# Mostrar última actualización y métricas
last_run_time = os.getenv('LAST_RUN_TIME', '')
last_run_status = os.getenv('LAST_RUN_STATUS', '')

if last_run_time:
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        status_icon = "✅" if last_run_status == "SUCCESS" else "❌"
        status_text = "Exitosa" if last_run_status == "SUCCESS" else "Con errores"
        st.info(f"🕐 **Última actualización:** {last_run_time} {status_icon} {status_text}")
    with col2:
        st.metric("📊 Total Tickets", f"{len(df_tickets):,}")
    with col3:
        st.metric("🛒 Total Productos", f"{len(df_consumos):,}")
else:
    col1, col2 = st.columns(2)
    with col1:
        st.metric("📊 Total Tickets", f"{len(df_tickets):,}")
    with col2:
        st.metric("🛒 Total Productos", f"{len(df_consumos):,}")

st.markdown("---")

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

# Filtro por turno (OPCIONAL - múltiple selección)
if 'Turno' in df_tickets_filtrado.columns:
    turnos_disponibles = sorted(df_tickets_filtrado['Turno'].dropna().unique().tolist())
    if len(turnos_disponibles) > 0:
        st.sidebar.markdown("**Turno**")
        
        # Opción "Todos"
        seleccionar_todos = st.sidebar.checkbox("Seleccionar todos los turnos", value=True)
        
        if seleccionar_todos:
            turnos_seleccionados = turnos_disponibles
        else:
            turnos_seleccionados = st.sidebar.multiselect(
                "Seleccionar turnos",
                turnos_disponibles,
                default=turnos_disponibles
            )
        
        # Aplicar filtro de turnos
        if turnos_seleccionados:
            df_tickets_filtrado = df_tickets_filtrado[df_tickets_filtrado['Turno'].isin(turnos_seleccionados)]
        else:
            st.sidebar.warning("⚠️ Selecciona al menos un turno")

st.sidebar.markdown("---")
st.sidebar.info(f"📋 Registros filtrados: {len(df_tickets_filtrado)}")

# Crear pestañas
tab1, tab2, tab3, tab4, tab5 = st.tabs(["💰 Facturación", "🏆 Ranking de Productos", "🎯 Mejores Combos", "📊 Análisis por Familia", "🎨 Creación de Combos"])

# ========== PESTAÑA 1: FACTURACIÓN ==========
with tab1:
    st.header("💰 Facturación")
    
    # Gráfico de barras: Facturación por día
    st.subheader("📊 Facturación Diaria")
    if 'Fecha' in df_tickets_filtrado.columns and 'Importe' in df_tickets_filtrado.columns:
        if 'Turno' in df_tickets_filtrado.columns:
            # Facturación por día y turno (barras apiladas)
            facturacion_diaria_turno = df_tickets_filtrado.groupby(['Fecha', 'Turno'])['Importe'].sum().reset_index()
            facturacion_diaria_turno['Fecha'] = pd.to_datetime(facturacion_diaria_turno['Fecha'])
            facturacion_diaria_turno = facturacion_diaria_turno.sort_values('Fecha')
            
            fig_barras = px.bar(
                facturacion_diaria_turno,
                x='Fecha',
                y='Importe',
                color='Turno',
                title='Facturación Total por Día (por Turno)',
                labels={'Importe': 'Facturación ($)', 'Fecha': 'Día', 'Turno': 'Turno'},
                barmode='stack'
            )
        else:
            # Facturación sin turno
            facturacion_diaria = df_tickets_filtrado.groupby('Fecha')['Importe'].sum().reset_index()
            facturacion_diaria['Fecha'] = pd.to_datetime(facturacion_diaria['Fecha'])
            facturacion_diaria = facturacion_diaria.sort_values('Fecha')
            
            fig_barras = px.bar(
                facturacion_diaria,
                x='Fecha',
                y='Importe',
                title='Facturación Total por Día',
                labels={'Importe': 'Facturación ($)', 'Fecha': 'Día'},
                color='Importe',
                color_continuous_scale='Blues'
            )
        
        fig_barras.update_layout(showlegend=True)
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
        
        df_tickets_temp['Código'] = df_tickets_temp['Código'].astype(str)
        df_tickets_temp['Sucursal'] = df_tickets_temp['Sucursal'].astype(str)
        df_consumos_temp['Codigo'] = df_consumos_temp['Codigo'].astype(str)
        df_consumos_temp['Sucursal'] = df_consumos_temp['Sucursal'].astype(str)
        
        # Hacer merge con consumos para obtener la familia (usando Código y Sucursal)
        df_con_familia = df_tickets_temp.merge(
            df_consumos_temp[['Codigo', 'Familia', 'Sucursal']],
            left_on=['Código', 'Sucursal'],
            right_on=['Codigo', 'Sucursal'],
            how='left'
        )
        
        # Agrupar por familia
        facturacion_familia = df_con_familia.groupby('Familia')['Importe'].sum().reset_index()
        facturacion_familia = facturacion_familia.sort_values('Importe', ascending=False)
        
        # Calcular porcentajes
        total = facturacion_familia['Importe'].sum()
        facturacion_familia['Porcentaje'] = (facturacion_familia['Importe'] / total * 100).round(2)
        
        fig_torta = px.pie(
            facturacion_familia,
            values='Importe',
            names='Familia',
            title='Distribución de Facturación por Familia',
            hole=0.4
        )
        fig_torta.update_traces(
            textposition='inside',
            textinfo='percent+label',
            hovertemplate='<b>%{label}</b><br>Facturación: $%{value:,.2f}<br>Porcentaje: %{percent}<extra></extra>'
        )
        st.plotly_chart(fig_torta, use_container_width=True)
        
        # Mostrar tabla de resumen
        st.dataframe(
            facturacion_familia[['Familia', 'Importe', 'Porcentaje']].rename(
                columns={'Importe': 'Facturación ($)', 'Porcentaje': '% del Total'}
            ),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.warning("⚠️ No hay datos de código para vincular con familias")

# ========== PESTAÑA 2: RANKING DE PRODUCTOS ==========
with tab2:
    st.header("🏆 Ranking de Productos")
    
    # Selector de cantidad de productos
    cantidad_productos = st.selectbox(
        "Cantidad de productos a mostrar",
        options=[5, 10, 15, 20, 25, 30],
        index=3  # Por defecto 20
    )
    
    if 'Descripción' in df_tickets_filtrado.columns:
        # Top productos por cantidad
        st.subheader("📦 Top Productos Más Vendidos (por Cantidad)")
        
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
        
        st.markdown("---")
        
        # Productos menos vendidos por cantidad
        st.subheader("📉 Productos Menos Vendidos (por Cantidad)")
        
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
        
        st.markdown("---")
        
        # Top productos por facturación
        st.subheader("💵 Top Productos que Más Facturan")
        
        if 'Importe' in df_tickets_filtrado.columns and 'Cantidad' in df_tickets_filtrado.columns:
            top_facturacion = df_tickets_filtrado.groupby('Descripción').agg({
                'Cantidad': 'sum',
                'Importe': 'sum'
            }).reset_index()
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
        
        st.markdown("---")
        
        # Productos que menos facturan
        st.subheader("💸 Productos que Menos Facturan")
        
        if 'Importe' in df_tickets_filtrado.columns and 'Cantidad' in df_tickets_filtrado.columns:
            bottom_facturacion = df_tickets_filtrado.groupby('Descripción').agg({
                'Cantidad': 'sum',
                'Importe': 'sum'
            }).reset_index()
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

# ========== PESTAÑA 3: MEJORES COMBOS ==========
with tab3:
    st.header("🎯 Mejores Combos")
    
    if 'Número' in df_tickets_filtrado.columns and 'Descripción' in df_tickets_filtrado.columns:
        
        st.markdown("---")
        
        # SECCIÓN 1: Análisis por Producto
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
        
        st.markdown("---")
        
        # SECCIÓN 2: Análisis por Familia
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

# ========== PESTAÑA 4: ANÁLISIS POR FAMILIA ==========
with tab4:
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
        
        facturacion_familia = df_con_familia.groupby('Familia')['Importe'].sum().reset_index()
        total_facturacion = facturacion_familia['Importe'].sum()
        facturacion_familia['Porcentaje'] = (facturacion_familia['Importe'] / total_facturacion * 100).round(2)
        facturacion_familia = facturacion_familia.sort_values('Importe', ascending=False)
        
        fig_familia = px.pie(
            facturacion_familia,
            values='Importe',
            names='Familia',
            title='Porcentaje de Facturación por Familia',
            hole=0.4
        )
        fig_familia.update_traces(
            textposition='inside',
            textinfo='percent+label',
            hovertemplate='<b>%{label}</b><br>Facturación: $%{value:,.2f}<br>Porcentaje: %{percent}<extra></extra>'
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
            
            productos_familia = df_familia.groupby('Descripción')['Importe'].sum().reset_index()
            total_familia = productos_familia['Importe'].sum()
            productos_familia['Porcentaje'] = (productos_familia['Importe'] / total_familia * 100).round(2)
            productos_familia = productos_familia.sort_values('Importe', ascending=False)
            
            fig_torta_familia = px.pie(
                productos_familia,
                values='Importe',
                names='Descripción',
                title=f'Distribución de Facturación en {familia_seleccionada}',
                hole=0.4
            )
            fig_torta_familia.update_traces(
                textposition='inside',
                textinfo='percent',
                hovertemplate='<b>%{label}</b><br>Facturación: $%{value:,.2f}<br>Porcentaje: %{percent}<extra></extra>'
            )
            st.plotly_chart(fig_torta_familia, use_container_width=True)
            
            st.markdown("---")
            
            # Top 5 más vendidos y menos vendidos
            col_left, col_right = st.columns(2)
            
            with col_left:
                st.markdown("### 🏆 Top 5 Más Vendidos")
                
                if 'Cantidad' in df_familia.columns:
                    top5_familia = df_familia.groupby('Descripción').agg({
                        'Cantidad': 'sum',
                        'Importe': 'sum'
                    }).reset_index()
                    
                    total_cantidad_familia = top5_familia['Cantidad'].sum()
                    total_importe_familia = top5_familia['Importe'].sum()
                    
                    top5_familia['% Peso'] = (top5_familia['Cantidad'] / total_cantidad_familia * 100).round(2)
                    top5_familia = top5_familia.sort_values('Cantidad', ascending=False).head(5)
                    
                    st.dataframe(
                        top5_familia[['Descripción', 'Cantidad', '% Peso', 'Importe']].rename(
                            columns={'Importe': 'Facturado ($)'}
                        ),
                        use_container_width=True,
                        hide_index=True
                    )
            
            with col_right:
                st.markdown("### 📉 Top 5 Menos Vendidos")
                
                if 'Cantidad' in df_familia.columns:
                    bottom5_familia = df_familia.groupby('Descripción').agg({
                        'Cantidad': 'sum',
                        'Importe': 'sum'
                    }).reset_index()
                    
                    total_cantidad_familia = bottom5_familia['Cantidad'].sum()
                    
                    bottom5_familia['% Peso'] = (bottom5_familia['Cantidad'] / total_cantidad_familia * 100).round(2)
                    bottom5_familia = bottom5_familia.sort_values('Cantidad', ascending=True).head(5)
                    
                    st.dataframe(
                        bottom5_familia[['Descripción', 'Cantidad', '% Peso', 'Importe']].rename(
                            columns={'Importe': 'Facturado ($)'}
                        ),
                        use_container_width=True,
                        hide_index=True
                    )
    else:
        st.warning("⚠️ No hay datos suficientes para análisis por familia")

# ========== PESTAÑA 5: CREACIÓN DE COMBOS ==========
with tab5:
    st.header("🎨 Creación de Combos")
    
    if 'Número' in df_tickets_filtrado.columns and 'Descripción' in df_tickets_filtrado.columns:
        st.write("Selecciona entre 2 y 4 productos para analizar cuántas veces aparecen juntos en los mismos tickets.")
        
        # Lista de productos disponibles
        productos_disponibles_combos = sorted(df_tickets_filtrado['Descripción'].dropna().unique().tolist())
        
        # Multiselect para elegir productos
        productos_seleccionados = st.multiselect(
            "Selecciona los productos para el combo (mínimo 2, máximo 4)",
            productos_disponibles_combos,
            default=[],
            max_selections=4,
            key="productos_combo_personalizado"
        )
        
        if len(productos_seleccionados) < 2:
            st.info("ℹ️ Selecciona al menos 2 productos para analizar el combo")
        elif len(productos_seleccionados) > 4:
            st.warning("⚠️ Puedes seleccionar máximo 4 productos")
        else:
            st.markdown("---")
            st.subheader(f"📊 Análisis del Combo: {', '.join(productos_seleccionados)}")
            
            # Encontrar tickets que contienen TODOS los productos seleccionados
            tickets_con_todos = None
            
            for producto in productos_seleccionados:
                tickets_producto = set(df_tickets_filtrado[
                    df_tickets_filtrado['Descripción'] == producto
                ]['Número'].unique())
                
                if tickets_con_todos is None:
                    tickets_con_todos = tickets_producto
                else:
                    tickets_con_todos = tickets_con_todos.intersection(tickets_producto)
            
            cantidad_tickets_combo = len(tickets_con_todos)
            
            # Mostrar resultado
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric(
                    "🎫 Tickets con este combo",
                    f"{cantidad_tickets_combo:,}"
                )
            
            with col2:
                total_tickets = df_tickets_filtrado['Número'].nunique()
                porcentaje = (cantidad_tickets_combo / total_tickets * 100) if total_tickets > 0 else 0
                st.metric(
                    "📊 % del total de tickets",
                    f"{porcentaje:.2f}%"
                )
            
            with col3:
                if cantidad_tickets_combo > 0:
                    # Calcular facturación del combo
                    df_combo_tickets = df_tickets_filtrado[
                        (df_tickets_filtrado['Número'].isin(tickets_con_todos)) &
                        (df_tickets_filtrado['Descripción'].isin(productos_seleccionados))
                    ]
                    facturacion_combo = df_combo_tickets['Importe'].sum() if 'Importe' in df_combo_tickets.columns else 0
                    st.metric(
                        "💰 Facturación del combo",
                        f"${facturacion_combo:,.2f}"
                    )
                else:
                    st.metric("💰 Facturación del combo", "$0.00")
            
            # Detalles de los tickets
            if cantidad_tickets_combo > 0:
                st.markdown("---")
                st.subheader("🔍 Detalle de Tickets con el Combo")
                
                # Mostrar información de cada ticket
                with st.expander(f"Ver los {cantidad_tickets_combo} tickets"):
                    for ticket in sorted(tickets_con_todos):
                        df_ticket = df_tickets_filtrado[df_tickets_filtrado['Número'] == ticket]
                        
                        st.write(f"**Ticket #{ticket}**")
                        
                        # Productos del combo en este ticket
                        df_combo_en_ticket = df_ticket[df_ticket['Descripción'].isin(productos_seleccionados)]
                        
                        if 'Cantidad' in df_combo_en_ticket.columns and 'Importe' in df_combo_en_ticket.columns:
                            st.dataframe(
                                df_combo_en_ticket[['Descripción', 'Cantidad', 'Importe']],
                                use_container_width=True,
                                hide_index=True
                            )
                        else:
                            st.write(df_combo_en_ticket['Descripción'].tolist())
                        
                        st.markdown("---")
            else:
                st.info("ℹ️ No se encontraron tickets donde estos productos aparezcan juntos")
    else:
        st.warning("⚠️ Faltan columnas necesarias para análisis de combos")

# Footer
st.markdown("---")
st.caption("DataKinga Dashboard v1.0 - Datos actualizados en tiempo real")
