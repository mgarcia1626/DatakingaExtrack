"""
DATAKINGA - Dashboard Interactivo
VisualizaciÃ³n de datos con Streamlit
"""
import streamlit as st
import pandas as pd
import os
from datetime import datetime
from dotenv import load_dotenv
import plotly.express as px
import plotly.graph_objects as go
from FunctionsGrouping.supabase_client import get_client, fetch_tickets, fetch_consumos

# Cargar variables de entorno
load_dotenv()

# ConfiguraciÃ³n de la pÃ¡gina
st.set_page_config(
    page_title="DataKinga Dashboard",
    page_icon="ðŸ“Š",
    layout="wide",
    initial_sidebar_state="expanded"
)

# TÃ­tulo principal
st.title("ðŸ“Š DataKinga Dashboard")
st.markdown("---")

# Cargar datos
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


df_tickets, df_consumos = cargar_datos()

# Sidebar - Filtros globales
st.sidebar.header("ðŸ” Filtros")

# Filtro por sucursal (OBLIGATORIO - solo una)
if 'Sucursal' in df_tickets.columns:
    sucursales = sorted(df_tickets['Sucursal'].dropna().unique().tolist())
    if len(sucursales) > 0:
        sucursal_seleccionada = st.sidebar.selectbox(
            "Sucursal",
            sucursales,
            index=0,
            key="sb_sucursal_2"
        )
        df_tickets_filtrado = df_tickets[df_tickets['Sucursal'] == sucursal_seleccionada]
    else:
        st.sidebar.error("âš ï¸ No hay sucursales disponibles")
        df_tickets_filtrado = df_tickets
else:
    st.sidebar.error("âš ï¸ No hay columna Sucursal")
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
            max_value=fecha_max,
            key="fecha_desde_2"
        )
    
    with col2:
        fecha_hasta = st.date_input(
            "Hasta",
            value=fecha_max,
            min_value=fecha_min,
            max_value=fecha_max,
            key="fecha_hasta_2"
        )
    
    # Aplicar filtro de fechas
    df_tickets_filtrado = df_tickets_filtrado[
        (df_tickets_filtrado['Fecha_dt'].dt.date >= fecha_desde) & 
        (df_tickets_filtrado['Fecha_dt'].dt.date <= fecha_hasta)
    ]
else:
    st.sidebar.warning("âš ï¸ No hay columna Fecha")

# Filtro por turno (desplegable con opciÃ³n Todos)
if 'Turno' in df_tickets_filtrado.columns:
    turnos_disponibles = sorted(df_tickets_filtrado['Turno'].dropna().unique().tolist())
    if len(turnos_disponibles) > 0:
        # Agregar opciÃ³n "Todos" al inicio
        opciones_turno = ["Todos"] + turnos_disponibles
        
        turno_seleccionado = st.sidebar.selectbox(
            "Turno",
            opciones_turno,
            index=0,  # Por defecto "Todos"
            key="sb_turno_2"
        )
        
        # Aplicar filtro de turnos solo si no es "Todos"
        if turno_seleccionado != "Todos":
            df_tickets_filtrado = df_tickets_filtrado[df_tickets_filtrado['Turno'] == turno_seleccionado]

# Ãšltima actualizaciÃ³n (pequeÃ±o, debajo del filtro de turno)
st.sidebar.markdown("---")
last_run_time = os.getenv('LAST_RUN_TIME', '')
last_run_status = os.getenv('LAST_RUN_STATUS', '')

if last_run_time:
    status_icon = "âœ…" if last_run_status == "SUCCESS" else "âŒ"
    st.sidebar.caption(f"ðŸ• Ãšltima actualizaciÃ³n: {last_run_time} {status_icon}")

# MenÃº de navegaciÃ³n
st.sidebar.markdown("---")
st.sidebar.header("ðŸ“‹ MenÃº")

# UN SOLO radio button con todas las opciones y separadores
opciones_menu = [
    "FacturaciÃ³n",
    "AnÃ¡lisis por Familia",
    "â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€",
    "Buscador de Productos en Tickets",
    "â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€",
    "Ranking de productos",
    "Productos mas vendidos", 
    "Productos menos vendidos", 
    "Productos mejor facturacion", 
    "Productos peor facturacion",
    "â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€",
    "Relaciones por producto", 
    "Relaciones por familia",
    "â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€",
    "CreaciÃ³n de Combos",
    "â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€",
    "AnÃ¡lisis de regalos"
]

# Inicializar session_state si no existe
if 'menu_seleccion' not in st.session_state:
    st.session_state.menu_seleccion = "FacturaciÃ³n"

# Encontrar el Ã­ndice de la selecciÃ³n actual
try:
    index_actual = opciones_menu.index(st.session_state.menu_seleccion)
except ValueError:
    index_actual = 0

menu_opcion_temp = st.sidebar.radio(
    "Selecciona una vista",
    opciones_menu,
    index=index_actual,
    label_visibility="collapsed",
    key="menu_principal_2"
)

# Si se selecciona un separador, mantener la Ãºltima selecciÃ³n vÃ¡lida
if menu_opcion_temp.startswith("â”€"):
    menu_opcion = st.session_state.menu_seleccion
else:
    menu_opcion = menu_opcion_temp
    st.session_state.menu_seleccion = menu_opcion

# ========== VISTA: FACTURACIÃ“N ==========
if menu_opcion == "FacturaciÃ³n":
    st.header("ðŸ’° FacturaciÃ³n")
    
    # Calcular mÃ©tricas del periodo
    if 'Importe' in df_tickets_filtrado.columns and 'Cantidad' in df_tickets_filtrado.columns:
        # FacturaciÃ³n total del periodo
        df_temp_metricas = df_tickets_filtrado.copy()
        df_temp_metricas['Importe_Total'] = df_temp_metricas['Cantidad'] * df_temp_metricas['Importe']
        facturacion_total_periodo = df_temp_metricas['Importe_Total'].sum()
        
        # Cantidad de dÃ­as facturados (dÃ­as con al menos una venta)
        if 'Fecha' in df_tickets_filtrado.columns:
            dias_facturados = df_tickets_filtrado['Fecha'].nunique()
        else:
            dias_facturados = 0
        
        # Mostrar mÃ©tricas
        col1, col2 = st.columns(2)
        with col1:
            st.metric("FacturaciÃ³n Total del Periodo", f"${facturacion_total_periodo:,.2f}")
        with col2:
            st.metric("Cantidad de DÃ­as Facturados", f"{dias_facturados}")
        
        st.markdown("---")
    
    # GrÃ¡fico de barras: FacturaciÃ³n por dÃ­a
    st.subheader("ðŸ“Š FacturaciÃ³n Diaria")
    if 'Fecha' in df_tickets_filtrado.columns and 'Importe' in df_tickets_filtrado.columns:
        if 'Turno' in df_tickets_filtrado.columns:
            # Calcular importe total (Cantidad * Importe unitario)
            df_temp = df_tickets_filtrado.copy()
            df_temp['Importe_Total'] = df_temp['Cantidad'] * df_temp['Importe']
            # FacturaciÃ³n por dÃ­a y turno (barras apiladas)
            facturacion_diaria_turno = df_temp.groupby(['Fecha', 'Turno'])['Importe_Total'].sum().reset_index()
            facturacion_diaria_turno = facturacion_diaria_turno.rename(columns={'Importe_Total': 'Importe'})
            facturacion_diaria_turno['Fecha'] = pd.to_datetime(facturacion_diaria_turno['Fecha'])
            facturacion_diaria_turno = facturacion_diaria_turno.sort_values('Fecha')
            
            # Crear rango completo de fechas (incluyendo dÃ­as faltantes)
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
            
            # Crear etiquetas de fecha con dÃ­a de la semana en espaÃ±ol
            dias_semana = {
                'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'MiÃ©rcoles',
                'Thursday': 'Jueves', 'Friday': 'Viernes', 'Saturday': 'SÃ¡bado', 'Sunday': 'Domingo'
            }
            facturacion_diaria_turno['Fecha_Label'] = facturacion_diaria_turno['Fecha'].apply(
                lambda x: f"{dias_semana[x.strftime('%A')]}<br>{x.day}/{x.month}"
            )
            
            # FunciÃ³n para formatear valores con k y M
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
                title='FacturaciÃ³n Total por DÃ­a (por Turno)',
                labels={'Importe': 'FacturaciÃ³n ($)', 'Fecha_Label': 'DÃ­a y Fecha', 'Turno': 'Turno'},
                barmode='stack',
                color_discrete_map=color_map,
                text='Texto'
            )
            
            # Configurar el texto dentro de las barras (horizontal, nÃºmeros oscuros)
            fig_barras.update_traces(
                textposition='inside',
                textangle=0,
                textfont=dict(color='#1C2833', size=11, family='Arial', weight='bold')
            )
        else:
            # Calcular importe total (Cantidad * Importe unitario)
            df_temp = df_tickets_filtrado.copy()
            df_temp['Importe_Total'] = df_temp['Cantidad'] * df_temp['Importe']
            # FacturaciÃ³n sin turno
            facturacion_diaria = df_temp.groupby('Fecha')['Importe_Total'].sum().reset_index()
            facturacion_diaria = facturacion_diaria.rename(columns={'Importe_Total': 'Importe'})
            facturacion_diaria['Fecha'] = pd.to_datetime(facturacion_diaria['Fecha'])
            facturacion_diaria = facturacion_diaria.sort_values('Fecha')
            
            # Crear rango completo de fechas (incluyendo dÃ­as faltantes)
            fecha_min = facturacion_diaria['Fecha'].min()
            fecha_max = facturacion_diaria['Fecha'].max()
            todas_fechas = pd.date_range(start=fecha_min, end=fecha_max, freq='D')
            
            # Reindexar con todas las fechas
            facturacion_diaria = facturacion_diaria.set_index('Fecha').reindex(todas_fechas).reset_index()
            facturacion_diaria = facturacion_diaria.rename(columns={'index': 'Fecha'})
            facturacion_diaria['Importe'] = facturacion_diaria['Importe'].fillna(0)
            
            # Crear etiquetas de fecha con dÃ­a de la semana en espaÃ±ol
            dias_semana = {
                'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'MiÃ©rcoles',
                'Thursday': 'Jueves', 'Friday': 'Viernes', 'Saturday': 'SÃ¡bado', 'Sunday': 'Domingo'
            }
            facturacion_diaria['Fecha_Label'] = facturacion_diaria['Fecha'].apply(
                lambda x: f"{dias_semana[x.strftime('%A')]}<br>{x.day}/{x.month}"
            )
            
            # FunciÃ³n para formatear valores con k y M
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
                title='FacturaciÃ³n Total por DÃ­a',
                labels={'Importe': 'FacturaciÃ³n ($)', 'Fecha_Label': 'DÃ­a y Fecha'},
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
            xaxis_title='DÃ­a y Fecha'
        )
        st.plotly_chart(fig_barras, use_container_width=True)
    else:
        st.warning("âš ï¸ No hay datos de facturaciÃ³n disponibles")
    
    st.markdown("---")
    
    # GrÃ¡fico de torta: % de facturaciÃ³n por familia
    st.subheader("ðŸ¥§ FacturaciÃ³n por Familia")
    if 'CÃ³digo' in df_tickets_filtrado.columns and 'Importe' in df_tickets_filtrado.columns:
        # Convertir columnas a string para el merge
        df_tickets_temp = df_tickets_filtrado.copy()
        df_consumos_temp = df_consumos.copy()
        
        # Limpiar y normalizar columnas
        df_tickets_temp['CÃ³digo'] = df_tickets_temp['CÃ³digo'].astype(str).str.strip().str.upper()
        df_tickets_temp['Sucursal'] = df_tickets_temp['Sucursal'].astype(str).str.strip().str.upper()
        df_consumos_temp['Codigo'] = df_consumos_temp['Codigo'].astype(str).str.strip().str.upper()
        df_consumos_temp['Sucursal'] = df_consumos_temp['Sucursal'].astype(str).str.strip().str.upper()
        
        # Eliminar duplicados en consumos (mismo Codigo+Sucursal, mantener el primero)
        df_consumos_unique = df_consumos_temp.drop_duplicates(subset=['Codigo', 'Sucursal'], keep='first')
        
        # Hacer merge con consumos para obtener la familia (usando CÃ³digo y Sucursal)
        df_con_familia = df_tickets_temp.merge(
            df_consumos_unique[['Codigo', 'Familia', 'Sucursal']],
            left_on=['CÃ³digo', 'Sucursal'],
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
            title='DistribuciÃ³n de FacturaciÃ³n por Familia',
            hole=0.4,
            custom_data=['Familia']
        )
        fig_torta.update_traces(
            textposition='inside',
            text=facturacion_familia['Familia'],
            hovertemplate='<b>%{customdata[0]}</b><br>FacturaciÃ³n: $%{value:,.2f}<extra></extra>'
        )
        st.plotly_chart(fig_torta, use_container_width=True)
        
        # Mostrar tabla de resumen con formato
        tabla_familia = facturacion_familia[['Familia', 'Importe', 'Porcentaje']].copy()
        tabla_familia['Importe'] = tabla_familia['Importe'].apply(lambda x: f"${x:,.2f}")
        tabla_familia['Porcentaje'] = tabla_familia['Porcentaje'].apply(lambda x: f"{x:.2f}%")
        tabla_familia = tabla_familia.rename(
            columns={'Importe': 'FacturaciÃ³n ($)', 'Porcentaje': '% del Total'}
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
        st.warning("âš ï¸ No hay datos de cÃ³digo para vincular con familias")

# ========== VISTA: BUSCADOR DE PRODUCTOS EN TICKETS ==========
elif menu_opcion == "Buscador de Productos en Tickets":
    st.header("ðŸ” Buscador de Productos en Tickets")
    st.markdown("Busca un producto y visualiza todos los tickets donde aparece, junto con los demÃ¡s productos de cada ticket.")
    
    # Verificar que tenemos las columnas necesarias
    if 'DescripciÃ³n' not in df_tickets_filtrado.columns or 'NÃºmero' not in df_tickets_filtrado.columns:
        st.error("âš ï¸ Faltan columnas necesarias (DescripciÃ³n o NÃºmero) en los datos")
    else:
        # Selector de producto
        productos_disponibles = sorted(df_tickets_filtrado['DescripciÃ³n'].dropna().unique().tolist())
        
        if len(productos_disponibles) == 0:
            st.warning("âš ï¸ No hay productos disponibles en el periodo seleccionado")
        else:
            col1, col2 = st.columns([3, 1])
            
            with col1:
                producto_seleccionado = st.selectbox(
                    "Selecciona un producto",
                    productos_disponibles,
                    index=0,
                    key="producto_combo_sel"
                )
            
            with col2:
                st.metric("Total productos", len(productos_disponibles))
            
            st.markdown("---")
            
            # Buscar todos los tickets que contienen el producto seleccionado
            tickets_con_producto = df_tickets_filtrado[
                df_tickets_filtrado['DescripciÃ³n'] == producto_seleccionado
            ]['NÃºmero'].unique()
            
            if len(tickets_con_producto) == 0:
                st.info(f"â„¹ï¸ No se encontraron tickets con el producto '{producto_seleccionado}'")
            else:
                # Filtrar todos los datos de esos tickets
                df_tickets_completos = df_tickets_filtrado[
                    df_tickets_filtrado['NÃºmero'].isin(tickets_con_producto)
                ].copy()
                
                # Calcular estadÃ­sticas
                total_tickets = len(tickets_con_producto)
                total_items_producto = df_tickets_filtrado[
                    df_tickets_filtrado['DescripciÃ³n'] == producto_seleccionado
                ]['Cantidad'].sum()
                
                # Calcular facturaciÃ³n del producto
                if 'Importe' in df_tickets_filtrado.columns and 'Cantidad' in df_tickets_filtrado.columns:
                    df_producto = df_tickets_filtrado[df_tickets_filtrado['DescripciÃ³n'] == producto_seleccionado].copy()
                    df_producto['Total'] = df_producto['Cantidad'] * df_producto['Importe']
                    facturacion_producto = df_producto['Total'].sum()
                else:
                    facturacion_producto = 0
                
                # Mostrar mÃ©tricas principales
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Tickets encontrados", f"{total_tickets:,}")
                with col2:
                    st.metric("Cantidad vendida", f"{int(total_items_producto):,}")
                with col3:
                    if facturacion_producto > 0:
                        st.metric("FacturaciÃ³n total", f"${facturacion_producto:,.2f}")
                
                st.markdown("---")
                
                # Ordenar por fecha y hora
                if 'Fecha' in df_tickets_completos.columns and 'Hora' in df_tickets_completos.columns:
                    df_tickets_completos['Fecha_dt'] = pd.to_datetime(df_tickets_completos['Fecha'])
                    df_tickets_completos['Hora_str'] = df_tickets_completos['Hora'].astype(str)
                    df_tickets_completos = df_tickets_completos.sort_values(['Fecha_dt', 'Hora_str'], ascending=[False, False])
                
                # Agrupar por ticket y mostrar
                st.subheader("ðŸ“‹ Detalle de Tickets")
                
                for i, numero_ticket in enumerate(tickets_con_producto[:50]):  # Limitar a 50 tickets para rendimiento
                    df_ticket = df_tickets_completos[df_tickets_completos['NÃºmero'] == numero_ticket].copy()
                    
                    # InformaciÃ³n del ticket
                    fecha = df_ticket['Fecha'].iloc[0] if 'Fecha' in df_ticket.columns else "N/A"
                    hora = df_ticket['Hora'].iloc[0] if 'Hora' in df_ticket.columns else "N/A"
                    turno = df_ticket['Turno'].iloc[0] if 'Turno' in df_ticket.columns else "N/A"
                    
                    # Calcular total del ticket
                    if 'Importe' in df_ticket.columns and 'Cantidad' in df_ticket.columns:
                        df_ticket['Total_Item'] = df_ticket['Cantidad'] * df_ticket['Importe']
                        total_ticket = df_ticket['Total_Item'].sum()
                    else:
                        total_ticket = 0
                    
                    # Expandir con informaciÃ³n del ticket
                    with st.expander(
                        f"ðŸŽ« Ticket #{numero_ticket} - {fecha} {hora} - Total: ${total_ticket:,.2f}",
                        expanded=(i < 3)  # Expandir los primeros 3
                    ):
                        # InformaciÃ³n adicional
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.write(f"**ðŸ“… Fecha:** {fecha}")
                        with col2:
                            st.write(f"**ðŸ• Hora:** {hora}")
                        with col3:
                            st.write(f"**â° Turno:** {turno}")
                        
                        st.markdown("---")
                        st.write("**Productos en este ticket:**")
                        
                        # Preparar tabla de productos
                        columnas_mostrar = ['DescripciÃ³n', 'Cantidad']
                        if 'Importe' in df_ticket.columns:
                            columnas_mostrar.append('Importe')
                        if 'Total_Item' in df_ticket.columns:
                            columnas_mostrar.append('Total_Item')
                        
                        df_display = df_ticket[columnas_mostrar].copy()
                        
                        # Renombrar columnas para mejor presentaciÃ³n
                        if 'Total_Item' in df_display.columns:
                            df_display = df_display.rename(columns={'Total_Item': 'Total'})
                        
                        # Resaltar el producto buscado
                        def highlight_producto(row):
                            if row['DescripciÃ³n'] == producto_seleccionado:
                                return ['background-color: #90EE90'] * len(row)
                            return [''] * len(row)
                        
                        st.dataframe(
                            df_display.style.apply(highlight_producto, axis=1),
                            use_container_width=True,
                            hide_index=True
                        )
                        
                        # Mostrar total del ticket
                        if total_ticket > 0:
                            st.markdown(f"**Total del ticket:** ${total_ticket:,.2f}")
                
                # Mostrar aviso si hay mÃ¡s tickets
                if len(tickets_con_producto) > 50:
                    st.info(f"â„¹ï¸ Mostrando los primeros 50 tickets de {len(tickets_con_producto)} encontrados. Ajusta los filtros de fecha para ver menos resultados.")

# ========== VISTA: PRODUCTOS MAS VENDIDOS ==========
elif menu_opcion == "Productos mas vendidos":
    st.header("ðŸ“¦ Productos mas vendidos")
    
    # Selector de cantidad de productos
    cantidad_productos = st.selectbox(
        "Cantidad de productos a mostrar",
        options=[5, 10, 15, 20, 25, 30],
        index=3,  # Por defecto 20
        key="cant_prod_1"
    )
    
    if 'DescripciÃ³n' in df_tickets_filtrado.columns:
        
        if 'Cantidad' in df_tickets_filtrado.columns:
            top_cantidad = df_tickets_filtrado.groupby('DescripciÃ³n')['Cantidad'].sum().reset_index()
            top_cantidad = top_cantidad.sort_values('Cantidad', ascending=False).head(cantidad_productos)
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                fig = px.bar(
                    top_cantidad,
                    x='Cantidad',
                    y='DescripciÃ³n',
                    orientation='h',
                    title=f'Top {cantidad_productos} Productos MÃ¡s Vendidos',
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
        st.warning("âš ï¸ No hay columna DescripciÃ³n en los datos")

# ========== VISTA: PRODUCTOS MENOS VENDIDOS ==========
elif menu_opcion == "Productos menos vendidos":
    st.header("ðŸ“‰ Productos menos vendidos")
    
    # Selector de cantidad de productos
    cantidad_productos = st.selectbox(
        "Cantidad de productos a mostrar",
        options=[5, 10, 15, 20, 25, 30],
        index=3,  # Por defecto 20
        key="cant_prod_2"
    )
    
    if 'DescripciÃ³n' in df_tickets_filtrado.columns:
        
        if 'Cantidad' in df_tickets_filtrado.columns:
            bottom_cantidad = df_tickets_filtrado.groupby('DescripciÃ³n')['Cantidad'].sum().reset_index()
            bottom_cantidad = bottom_cantidad.sort_values('Cantidad', ascending=True).head(cantidad_productos)
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                fig = px.bar(
                    bottom_cantidad,
                    x='Cantidad',
                    y='DescripciÃ³n',
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
        st.warning("âš ï¸ No hay columna DescripciÃ³n en los datos")

# ========== VISTA: PRODUCTOS MEJOR FACTURACION ==========
elif menu_opcion == "Productos mejor facturacion":
    st.header("ðŸ’µ Productos mejor facturacion")
    
    # Selector de cantidad de productos
    cantidad_productos = st.selectbox(
        "Cantidad de productos a mostrar",
        options=[5, 10, 15, 20, 25, 30],
        index=3,  # Por defecto 20
        key="cant_prod_3"
    )
    
    if 'DescripciÃ³n' in df_tickets_filtrado.columns:
        
        if 'Importe' in df_tickets_filtrado.columns and 'Cantidad' in df_tickets_filtrado.columns:
            # Calcular importe total (Cantidad * Importe unitario)
            df_temp = df_tickets_filtrado.copy()
            df_temp['Importe_Total'] = df_temp['Cantidad'] * df_temp['Importe']
            
            top_facturacion = df_temp.groupby('DescripciÃ³n').agg({
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
                    y='DescripciÃ³n',
                    orientation='h',
                    title=f'Top {cantidad_productos} Productos por Ingresos',
                    color='Importe',
                    color_continuous_scale='Oranges'
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.dataframe(
                    top_facturacion.rename(columns={'Importe': 'FacturaciÃ³n Total ($)'}),
                    use_container_width=True,
                    hide_index=True
                )
    else:
        st.warning("âš ï¸ No hay columna DescripciÃ³n en los datos")

# ========== VISTA: PRODUCTOS PEOR FACTURACION ==========
elif menu_opcion == "Productos peor facturacion":
    st.header("ðŸ’¸ Productos peor facturacion")
    
    # Selector de cantidad de productos
    cantidad_productos = st.selectbox(
        "Cantidad de productos a mostrar",
        options=[5, 10, 15, 20, 25, 30],
        index=3,  # Por defecto 20
        key="cant_prod_4"
    )
    
    if 'DescripciÃ³n' in df_tickets_filtrado.columns:
        
        if 'Importe' in df_tickets_filtrado.columns and 'Cantidad' in df_tickets_filtrado.columns:
            # Calcular importe total (Cantidad * Importe unitario)
            df_temp = df_tickets_filtrado.copy()
            df_temp['Importe_Total'] = df_temp['Cantidad'] * df_temp['Importe']
            
            bottom_facturacion = df_temp.groupby('DescripciÃ³n').agg({
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
                    y='DescripciÃ³n',
                    orientation='h',
                    title=f'Top {cantidad_productos} Productos con Menor FacturaciÃ³n',
                    color='Importe',
                    color_continuous_scale='Reds_r'
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.dataframe(
                    bottom_facturacion.rename(columns={'Importe': 'FacturaciÃ³n Total ($)'}),
                    use_container_width=True,
                    hide_index=True
                )
    else:
        st.warning("âš ï¸ No hay columna DescripciÃ³n en los datos")

# ========== VISTA: RELACIONES POR PRODUCTO ==========
elif menu_opcion == "Relaciones por producto":
    st.header("ðŸŽ¯ Relaciones por producto")
    
    if 'NÃºmero' in df_tickets_filtrado.columns and 'DescripciÃ³n' in df_tickets_filtrado.columns:
        
        # AnÃ¡lisis por Producto
        st.subheader("ðŸ” AnÃ¡lisis de Combos por Producto")
        
        # Selector de cantidad de combos para producto
        cantidad_combos_producto = st.selectbox(
            "Cantidad de combinaciones a mostrar",
            options=[5, 10, 15, 20],
            index=1,  # Por defecto 10
            key="cantidad_combos_producto"
        )
        
        productos_disponibles = sorted(df_tickets_filtrado['DescripciÃ³n'].dropna().unique().tolist())
        producto_seleccionado = st.selectbox(
            "Selecciona un producto para ver con quÃ© se vende",
            productos_disponibles,
            key="producto_combo"
        )
        
        # Checkbox para omitir productos de la misma familia
        omitir_misma_familia = st.checkbox(
            "Omitir productos de la misma familia",
            value=False,
            key="omitir_familia"
        )
        
        # Multiselect para omitir familias especÃ­ficas
        if 'CÃ³digo' in df_tickets_filtrado.columns:
            df_tickets_temp = df_tickets_filtrado.copy()
            df_consumos_temp = df_consumos.copy()
            df_tickets_temp['CÃ³digo'] = df_tickets_temp['CÃ³digo'].astype(str)
            df_tickets_temp['Sucursal'] = df_tickets_temp['Sucursal'].astype(str)
            df_consumos_temp['Codigo'] = df_consumos_temp['Codigo'].astype(str)
            df_consumos_temp['Sucursal'] = df_consumos_temp['Sucursal'].astype(str)
            
            df_temp_familias = df_tickets_temp.merge(
                df_consumos_temp[['Codigo', 'Familia', 'Sucursal']],
                left_on=['CÃ³digo', 'Sucursal'],
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
                df_tickets_filtrado['DescripciÃ³n'] == producto_seleccionado
            ]['NÃºmero'].unique()
            
            # Calcular cuÃ¡ntos tickets tienen SOLO este producto (solo en el ticket)
            tickets_solo = 0
            for ticket_num in tickets_con_producto:
                productos_en_ticket = df_tickets_filtrado[
                    df_tickets_filtrado['NÃºmero'] == ticket_num
                ]['DescripciÃ³n'].nunique()
                if productos_en_ticket == 1:
                    tickets_solo += 1
            
            # Mostrar mÃ©trica de tickets solo
            col_metric1, col_metric2 = st.columns(2)
            with col_metric1:
                st.metric("Total de tickets con este producto", len(tickets_con_producto))
            with col_metric2:
                st.metric("Solo en el ticket", tickets_solo)
            
            st.markdown("---")
            
            # Obtener todos los productos en esos tickets (excepto el producto seleccionado)
            df_combos = df_tickets_filtrado[
                (df_tickets_filtrado['NÃºmero'].isin(tickets_con_producto)) &
                (df_tickets_filtrado['DescripciÃ³n'] != producto_seleccionado)
            ].copy()
            
            # Si el checkbox estÃ¡ marcado, filtrar por familia
            if omitir_misma_familia and 'CÃ³digo' in df_tickets_filtrado.columns:
                # Merge para obtener familia del producto seleccionado
                df_tickets_temp = df_tickets_filtrado[df_tickets_filtrado['DescripciÃ³n'] == producto_seleccionado].copy()
                df_consumos_temp = df_consumos.copy()
                df_tickets_temp['CÃ³digo'] = df_tickets_temp['CÃ³digo'].astype(str)
                df_tickets_temp['Sucursal'] = df_tickets_temp['Sucursal'].astype(str)
                df_consumos_temp['Codigo'] = df_consumos_temp['Codigo'].astype(str)
                df_consumos_temp['Sucursal'] = df_consumos_temp['Sucursal'].astype(str)
                
                df_temp = df_tickets_temp.merge(
                    df_consumos_temp[['Codigo', 'Familia', 'Sucursal']],
                    left_on=['CÃ³digo', 'Sucursal'],
                    right_on=['Codigo', 'Sucursal'],
                    how='left'
                )
                
                if len(df_temp) > 0 and 'Familia' in df_temp.columns:
                    familia_producto = df_temp['Familia'].iloc[0]
                    
                    # Merge para obtener familia de los combos
                    df_combos_temp = df_combos.copy()
                    df_consumos_temp2 = df_consumos.copy()
                    df_combos_temp['CÃ³digo'] = df_combos_temp['CÃ³digo'].astype(str)
                    df_combos_temp['Sucursal'] = df_combos_temp['Sucursal'].astype(str)
                    df_consumos_temp2['Codigo'] = df_consumos_temp2['Codigo'].astype(str)
                    df_consumos_temp2['Sucursal'] = df_consumos_temp2['Sucursal'].astype(str)
                    
                    df_combos = df_combos_temp.merge(
                        df_consumos_temp2[['Codigo', 'Familia', 'Sucursal']],
                        left_on=['CÃ³digo', 'Sucursal'],
                        right_on=['Codigo', 'Sucursal'],
                        how='left'
                    )
                    
                    # Filtrar productos de diferente familia
                    df_combos = df_combos[df_combos['Familia'] != familia_producto]
            
            # Aplicar filtro de familias a omitir
            if len(familias_omitir) > 0 and 'CÃ³digo' in df_tickets_filtrado.columns:
                # Si aÃºn no se hizo merge, hacerlo ahora
                if 'Familia' not in df_combos.columns:
                    df_combos_temp = df_combos.copy()
                    df_consumos_temp3 = df_consumos.copy()
                    df_combos_temp['CÃ³digo'] = df_combos_temp['CÃ³digo'].astype(str)
                    df_combos_temp['Sucursal'] = df_combos_temp['Sucursal'].astype(str)
                    df_consumos_temp3['Codigo'] = df_consumos_temp3['Codigo'].astype(str)
                    df_consumos_temp3['Sucursal'] = df_consumos_temp3['Sucursal'].astype(str)
                    
                    df_combos = df_combos_temp.merge(
                        df_consumos_temp3[['Codigo', 'Familia', 'Sucursal']],
                        left_on=['CÃ³digo', 'Sucursal'],
                        right_on=['Codigo', 'Sucursal'],
                        how='left'
                    )
                
                # Filtrar productos que NO estÃ©n en las familias a omitir
                df_combos = df_combos[~df_combos['Familia'].isin(familias_omitir)]
            
            if len(df_combos) > 0:
                # Contar frecuencia de cada producto
                combos_frecuencia = df_combos.groupby('DescripciÃ³n').size().reset_index(name='Veces')
                combos_frecuencia = combos_frecuencia.sort_values('Veces', ascending=False).head(cantidad_combos_producto)
                
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    fig_combos = px.bar(
                        combos_frecuencia,
                        x='Veces',
                        y='DescripciÃ³n',
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
        st.warning("âš ï¸ Faltan columnas necesarias para anÃ¡lisis de combos")

# ========== VISTA: RELACIONES POR FAMILIA ==========
elif menu_opcion == "Relaciones por familia":
    st.header("ðŸ“Š Relaciones por familia")
    
    if 'NÃºmero' in df_tickets_filtrado.columns and 'DescripciÃ³n' in df_tickets_filtrado.columns:
        
        # AnÃ¡lisis por Familia
        st.subheader("ðŸ“Š AnÃ¡lisis de Combos por Familia")
        
        # Selector de cantidad de combos para familia
        cantidad_combos_familia = st.selectbox(
            "Cantidad de combinaciones a mostrar",
            options=[5, 10, 15, 20],
            index=1,  # Por defecto 10
            key="cantidad_combos_familia"
        )
        
        if 'CÃ³digo' in df_tickets_filtrado.columns:
            # Hacer merge con consumos para obtener familia (usando CÃ³digo y Sucursal)
            df_tickets_temp = df_tickets_filtrado.copy()
            df_consumos_temp = df_consumos.copy()
            df_tickets_temp['CÃ³digo'] = df_tickets_temp['CÃ³digo'].astype(str)
            df_tickets_temp['Sucursal'] = df_tickets_temp['Sucursal'].astype(str)
            df_consumos_temp['Codigo'] = df_consumos_temp['Codigo'].astype(str)
            df_consumos_temp['Sucursal'] = df_consumos_temp['Sucursal'].astype(str)
            
            df_con_familia = df_tickets_temp.merge(
                df_consumos_temp[['Codigo', 'Familia', 'Sucursal']],
                left_on=['CÃ³digo', 'Sucursal'],
                right_on=['Codigo', 'Sucursal'],
                how='left'
            )
            
            familias_disponibles = sorted(df_con_familia['Familia'].dropna().unique().tolist())
            familia_combo_seleccionada = st.selectbox(
                "Selecciona una familia para anÃ¡lisis de combos",
                familias_disponibles,
                key="familia_combo"
            )
            
            if familia_combo_seleccionada:
                # Obtener productos de la familia seleccionada
                df_familia_combo = df_con_familia[df_con_familia['Familia'] == familia_combo_seleccionada]
                
                # Encontrar top 5 mÃ¡s vendidos de la familia
                top5_familia_combo = df_familia_combo.groupby('DescripciÃ³n')['Cantidad'].sum().reset_index()
                top5_familia_combo = top5_familia_combo.sort_values('Cantidad', ascending=False).head(5)
                
                st.write(f"**Top 5 Productos de {familia_combo_seleccionada}:**")
                for producto in top5_familia_combo['DescripciÃ³n'].tolist():
                    st.write(f"â€¢ {producto}")
                
                st.markdown("---")
                
                # Analizar combinaciones para cada producto del top 5
                st.write(f"**Combinaciones de los Top 5 de {familia_combo_seleccionada}:**")
                
                for producto in top5_familia_combo['DescripciÃ³n'].tolist():
                    with st.expander(f"ðŸ”— Combinaciones de: {producto}"):
                        # Encontrar tickets con este producto
                        tickets_producto = df_con_familia[
                            df_con_familia['DescripciÃ³n'] == producto
                        ]['NÃºmero'].unique()
                        
                        # Productos que aparecen en esos tickets (excepto el producto actual)
                        df_combos_familia = df_con_familia[
                            (df_con_familia['NÃºmero'].isin(tickets_producto)) &
                            (df_con_familia['DescripciÃ³n'] != producto)
                        ]
                        
                        if len(df_combos_familia) > 0:
                            # Contar por producto (sin importar la familia)
                            combos_por_producto = df_combos_familia.groupby('DescripciÃ³n').size().reset_index(name='Veces')
                            combos_por_producto = combos_por_producto.sort_values('Veces', ascending=False).head(cantidad_combos_familia)
                            
                            col1, col2 = st.columns([2, 1])
                            
                            with col1:
                                fig = px.bar(
                                    combos_por_producto,
                                    x='Veces',
                                    y='DescripciÃ³n',
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
            st.warning("âš ï¸ No hay datos de cÃ³digo para vincular con familias")
    else:
        st.warning("âš ï¸ Faltan columnas necesarias para anÃ¡lisis de combos")

# ========== VISTA: ANÃLISIS POR FAMILIA ==========
elif menu_opcion == "AnÃ¡lisis por Familia":
    st.header("ðŸ“Š AnÃ¡lisis por Familia")
    
    if 'CÃ³digo' in df_tickets_filtrado.columns and 'Importe' in df_tickets_filtrado.columns:
        # Hacer merge con consumos para obtener la familia (usando CÃ³digo y Sucursal)
        df_tickets_temp = df_tickets_filtrado.copy()
        df_consumos_temp = df_consumos.copy()
        df_tickets_temp['CÃ³digo'] = df_tickets_temp['CÃ³digo'].astype(str)
        df_tickets_temp['Sucursal'] = df_tickets_temp['Sucursal'].astype(str)
        df_consumos_temp['Codigo'] = df_consumos_temp['Codigo'].astype(str)
        df_consumos_temp['Sucursal'] = df_consumos_temp['Sucursal'].astype(str)
        
        df_con_familia = df_tickets_temp.merge(
            df_consumos_temp[['Codigo', 'Familia', 'Articulo', 'Sucursal']],
            left_on=['CÃ³digo', 'Sucursal'],
            right_on=['Codigo', 'Sucursal'],
            how='left'
        )
        
        # GrÃ¡fico de torta: % de facturaciÃ³n por familia (fijo)
        st.subheader("ðŸ’° DistribuciÃ³n de FacturaciÃ³n por Familia")
        
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
            title='Porcentaje de FacturaciÃ³n por Familia',
            hole=0.4,
            custom_data=['Familia']
        )
        fig_familia.update_traces(
            textposition='inside',
            text=facturacion_familia['Familia'],
            hovertemplate='<b>%{customdata[0]}</b><br>FacturaciÃ³n: $%{value:,.2f}<extra></extra>'
        )
        st.plotly_chart(fig_familia, use_container_width=True)
        
        st.markdown("---")
        
        # Selector de familia
        familias_disponibles = sorted(df_con_familia['Familia'].dropna().unique().tolist())
        
        if len(familias_disponibles) > 0:
            familia_seleccionada = st.selectbox(
                "Selecciona una familia para anÃ¡lisis detallado",
                familias_disponibles,
                key="familia_sel"
            )
        else:
            st.warning("âš ï¸ No hay familias disponibles para esta sucursal")
            familia_seleccionada = None
        
        if familia_seleccionada:
            df_familia = df_con_familia[df_con_familia['Familia'] == familia_seleccionada]
            
            st.subheader(f"ðŸ” AnÃ¡lisis Detallado: {familia_seleccionada}")
            
            # GrÃ¡fico de torta: % de productos dentro de la familia
            st.markdown("### ðŸ¥§ DistribuciÃ³n de Productos en la Familia")
            
            # Calcular importe total (Cantidad * Importe unitario)
            df_familia['Importe_Total'] = df_familia['Cantidad'] * df_familia['Importe']
            productos_familia = df_familia.groupby('DescripciÃ³n')['Importe_Total'].sum().reset_index()
            productos_familia = productos_familia.rename(columns={'Importe_Total': 'Importe'})
            total_familia = productos_familia['Importe'].sum()
            productos_familia['Porcentaje'] = (productos_familia['Importe'] / total_familia * 100).round(2)
            productos_familia = productos_familia.sort_values('Importe', ascending=False)
            
            # Crear columna con nombre y porcentaje para la leyenda
            productos_familia['Producto_Label'] = productos_familia.apply(
                lambda row: f"{row['DescripciÃ³n']} ({row['Porcentaje']:.1f}%)", axis=1
            )
            
            fig_torta_familia = px.pie(
                productos_familia,
                values='Importe',
                names='Producto_Label',
                title=f'DistribuciÃ³n de FacturaciÃ³n en {familia_seleccionada}',
                hole=0.4,
                custom_data=['DescripciÃ³n']
            )
            fig_torta_familia.update_traces(
                textposition='inside',
                text=productos_familia['DescripciÃ³n'],
                hovertemplate='<b>%{customdata[0]}</b><br>FacturaciÃ³n: $%{value:,.2f}<extra></extra>'
            )
            st.plotly_chart(fig_torta_familia, use_container_width=True)
            
            st.markdown("---")
            
            # Lista completa de productos con cantidad y facturaciÃ³n
            st.markdown("### ðŸ“‹ Lista Completa de Productos")
            
            if 'Cantidad' in df_familia.columns:
                # Calcular importe total (Cantidad * Importe unitario)
                df_familia['Importe_Total'] = df_familia['Cantidad'] * df_familia['Importe']
                
                productos_completos = df_familia.groupby('DescripciÃ³n').agg({
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
                    st.metric("Total FacturaciÃ³n", f"${total_importe_familia:,.2f}")
                
                st.markdown("")  # Espacio
                
                # Calcular porcentajes
                productos_completos['% FacturaciÃ³n'] = (productos_completos['Importe_Total'] / total_importe_familia * 100).round(2)
                
                # Ordenar por facturaciÃ³n descendente
                productos_completos = productos_completos.sort_values('Importe_Total', ascending=False)
                
                # Formatear valores como en la tabla de facturaciÃ³n
                tabla_display = productos_completos[['DescripciÃ³n', 'Cantidad', 'Importe_Total', '% FacturaciÃ³n']].copy()
                tabla_display['Cantidad'] = tabla_display['Cantidad'].apply(lambda x: f"{x:,.0f}")
                tabla_display['Importe_Total'] = tabla_display['Importe_Total'].apply(lambda x: f"${x:,.2f}")
                tabla_display['% FacturaciÃ³n'] = tabla_display['% FacturaciÃ³n'].apply(lambda x: f"{x:.2f}%")
                tabla_display = tabla_display.rename(
                    columns={
                        'Cantidad': 'Cantidad Vendida',
                        'Importe_Total': 'FacturaciÃ³n ($)',
                        '% FacturaciÃ³n': '% facturado sobre total de la familia'
                    }
                )
                
                # Usar el mismo estilo que la tabla de facturaciÃ³n
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
        st.warning("âš ï¸ No hay datos suficientes para anÃ¡lisis por familia")

# ========== VISTA: RANKING DE PRODUCTOS ==========
elif menu_opcion == "Ranking de productos":
    st.header("ðŸ† Ranking de productos")
    
    if 'DescripciÃ³n' in df_tickets_filtrado.columns and 'Cantidad' in df_tickets_filtrado.columns and 'Importe' in df_tickets_filtrado.columns:
        # Calcular importe total por producto
        df_temp = df_tickets_filtrado.copy()
        df_temp['Importe_Total'] = df_temp['Cantidad'] * df_temp['Importe']
        
        # Agrupar por producto
        ranking_productos = df_temp.groupby('DescripciÃ³n').agg({
            'Cantidad': 'sum',
            'Importe_Total': 'sum'
        }).reset_index()
        
        # Calcular porcentaje de facturaciÃ³n
        facturacion_total_periodo = ranking_productos['Importe_Total'].sum()
        ranking_productos['% FacturaciÃ³n'] = (ranking_productos['Importe_Total'] / facturacion_total_periodo * 100).round(2)
        
        # Ordenar de mÃ¡s vendido a menos vendido
        ranking_productos = ranking_productos.sort_values('Cantidad', ascending=False)
        
        # Agregar columna de ranking
        ranking_productos.insert(0, 'Ranking', range(1, len(ranking_productos) + 1))
        
        # Mostrar mÃ©tricas del periodo
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total de Productos", f"{len(ranking_productos):,}")
        with col2:
            cantidad_total = ranking_productos['Cantidad'].sum()
            st.metric("Cantidad Total Vendida", f"{cantidad_total:,.0f}")
        with col3:
            st.metric("FacturaciÃ³n Total", f"${facturacion_total_periodo:,.2f}")
        
        st.markdown("---")
        
        # Nota explicativa
        st.info("â„¹ï¸ **Nota:** El ranking se basa en la cantidad total vendida de cada producto durante el perÃ­odo seleccionado.")
        
        # Buscador de producto
        buscar_producto = st.text_input("ðŸ” Buscar producto", placeholder="Escribe el nombre del producto...", key="buscar_ranking")
        
        # Formatear valores para la tabla
        tabla_ranking = ranking_productos.copy()
        
        # Filtrar por bÃºsqueda si hay texto
        if buscar_producto:
            tabla_ranking = tabla_ranking[tabla_ranking['DescripciÃ³n'].str.contains(buscar_producto, case=False, na=False)]
        
        tabla_ranking['Cantidad'] = tabla_ranking['Cantidad'].apply(lambda x: f"{x:,.0f}")
        tabla_ranking['Importe_Total'] = tabla_ranking['Importe_Total'].apply(lambda x: f"${x:,.2f}")
        tabla_ranking['% FacturaciÃ³n'] = tabla_ranking['% FacturaciÃ³n'].apply(lambda x: f"{x:.2f}%")
        
        tabla_ranking = tabla_ranking.rename(columns={
            'Ranking': '#',
            'DescripciÃ³n': 'Producto',
            'Cantidad': 'Cantidad Vendida',
            'Importe_Total': 'FacturaciÃ³n Total',
            '% FacturaciÃ³n': '% del Total'
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
        st.warning("âš ï¸ Faltan columnas necesarias para el ranking de productos")

# ========== VISTA: CREACIÃ“N DE COMBOS ==========
elif menu_opcion == "CreaciÃ³n de Combos":
    st.header("ðŸŽ¨ CreaciÃ³n de Combos")
    
    if 'CÃ³digo' in df_tickets_filtrado.columns and 'DescripciÃ³n' in df_tickets_filtrado.columns:
        st.write("Selecciona una o mÃ¡s familias para ver los productos mÃ¡s y menos vendidos de cada una.")
        
        # Hacer merge con consumos para obtener familias
        df_tickets_temp = df_tickets_filtrado.copy()
        df_consumos_temp = df_consumos.copy()
        df_tickets_temp['CÃ³digo'] = df_tickets_temp['CÃ³digo'].astype(str).str.strip().str.upper()
        df_tickets_temp['Sucursal'] = df_tickets_temp['Sucursal'].astype(str).str.strip().str.upper()
        df_consumos_temp['Codigo'] = df_consumos_temp['Codigo'].astype(str).str.strip().str.upper()
        df_consumos_temp['Sucursal'] = df_consumos_temp['Sucursal'].astype(str).str.strip().str.upper()
        
        df_con_familia = df_tickets_temp.merge(
            df_consumos_temp[['Codigo', 'Familia', 'Sucursal']],
            left_on=['CÃ³digo', 'Sucursal'],
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
            st.info("â„¹ï¸ Selecciona al menos una familia para comenzar")
        else:
            st.markdown("---")
            
            # Por cada familia seleccionada, mostrar top mÃ¡s y menos vendidos
            for familia in familias_seleccionadas:
                st.subheader(f"ðŸ“¦ {familia}")
                
                # Filtrar productos de esta familia
                df_familia = df_con_familia[df_con_familia['Familia'] == familia]
                
                if len(df_familia) > 0 and 'Cantidad' in df_familia.columns:
                    # Agrupar por producto y sumar cantidades
                    productos_familia = df_familia.groupby('DescripciÃ³n')['Cantidad'].sum().reset_index()
                    productos_familia = productos_familia.sort_values('Cantidad', ascending=False)
                    
                    # Top mÃ¡s vendidos
                    top_mas = productos_familia.head(cantidad_top).copy()
                    top_mas['Cantidad'] = top_mas['Cantidad'].apply(lambda x: f"{x:,.0f}")
                    
                    # Top menos vendidos
                    top_menos = productos_familia.tail(cantidad_top).sort_values('Cantidad', ascending=True).copy()
                    top_menos['Cantidad'] = top_menos['Cantidad'].apply(lambda x: f"{x:,.0f}")
                    
                    # Mostrar ambas tablas en columnas
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown(f"**âœ… Top {cantidad_top} MÃ¡s Vendidos**")
                        st.dataframe(
                            top_mas.rename(columns={'DescripciÃ³n': 'Producto', 'Cantidad': 'Cantidad Vendida'}),
                            use_container_width=True,
                            hide_index=True
                        )
                    
                    with col2:
                        st.markdown(f"**âš ï¸ Top {cantidad_top} Menos Vendidos**")
                        st.dataframe(
                            top_menos.rename(columns={'DescripciÃ³n': 'Producto', 'Cantidad': 'Cantidad Vendida'}),
                            use_container_width=True,
                            hide_index=True
                        )
                    
                    st.markdown("---")
                else:
                    st.warning(f"âš ï¸ No hay datos de cantidad para la familia {familia}")
    else:
        st.warning("âš ï¸ Faltan columnas necesarias para anÃ¡lisis de combos")

# ========== VISTA: ANÃLISIS DE REGALOS ==========
elif menu_opcion == "AnÃ¡lisis de regalos":
    st.header("ðŸŽ AnÃ¡lisis de regalos")
    
    if 'NÃºmero' in df_tickets_filtrado.columns and 'DescripciÃ³n' in df_tickets_filtrado.columns:
        # Obtener todos los productos
        productos_disponibles = sorted(df_tickets_filtrado['DescripciÃ³n'].dropna().unique().tolist())
        
        # Filtrar productos que contengan "regalo" (por defecto)
        productos_regalo = [p for p in productos_disponibles if 'regalo' in p.lower()]
        
        # Determinar el Ã­ndice por defecto
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
            df_tickets_filtrado['DescripciÃ³n'] == producto_regalo_seleccionado
        ]['NÃºmero'].unique()
        
        if len(tickets_con_regalo) > 0:
            # Filtrar todos los productos en esos tickets
            df_productos_en_tickets = df_tickets_filtrado[
                df_tickets_filtrado['NÃºmero'].isin(tickets_con_regalo)
            ].copy()
            
            # Calcular importe total por producto
            if 'Cantidad' in df_productos_en_tickets.columns and 'Importe' in df_productos_en_tickets.columns:
                df_productos_en_tickets['Importe_Total'] = df_productos_en_tickets['Cantidad'] * df_productos_en_tickets['Importe']
                
                # Agrupar por producto
                resumen_productos = df_productos_en_tickets.groupby('DescripciÃ³n').agg({
                    'Cantidad': 'sum',
                    'Importe_Total': 'sum'
                }).reset_index()
                
                # Ordenar por facturaciÃ³n descendente
                resumen_productos = resumen_productos.sort_values('Importe_Total', ascending=False)
                
                # Calcular totales
                facturacion_total_tickets = resumen_productos['Importe_Total'].sum()
                cantidad_regalo = resumen_productos[
                    resumen_productos['DescripciÃ³n'] == producto_regalo_seleccionado
                ]['Cantidad'].sum()
                costo_total = cantidad_regalo * costo_unitario
                
                # Mostrar mÃ©tricas
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
                    'DescripciÃ³n': 'Producto',
                    'Cantidad': 'Cantidad Vendida',
                    'Importe_Total': 'FacturaciÃ³n en estos Tickets'
                })
                
                # Mostrar tabla
                st.subheader("ðŸ“‹ Productos vendidos en tickets con el regalo")
                st.dataframe(
                    tabla_productos,
                    use_container_width=True,
                    hide_index=True,
                    height=500
                )
            else:
                st.warning("âš ï¸ Faltan columnas de Cantidad o Importe")
        else:
            st.info(f"No se encontraron tickets con el producto '{producto_regalo_seleccionado}'")
    else:
        st.warning("âš ï¸ Faltan columnas necesarias para el anÃ¡lisis de regalos")

# Footer
st.markdown("---")
st.caption("DataKinga Dashboard v1.0 - Datos actualizados en tiempo real")
