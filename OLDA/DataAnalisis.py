import pandas as pd
import streamlit as st
import plotly.graph_objects as go

st.title("Diagrama de Pareto - Productos por Importe")

# Leer el archivo CSV
columnas = ['FAMILIA', 'CODIGO', 'ARTICULO', 'CANTIDAD', 'IMPORTE']
df = pd.read_csv('DATA.csv', sep=';', skiprows=4, names=columnas, encoding='utf-8', engine='python')
df['IMPORTE'] = df['IMPORTE'].replace(',', '.', regex=True).astype(float)
df['CANTIDAD'] = df['CANTIDAD'].replace(',', '.', regex=True)
df['CANTIDAD'] = pd.to_numeric(df['CANTIDAD'], errors='coerce')

# --- KPIs arriba del dashboard ---

# Facturación total (sin descuentos)
facturacion_total = df['IMPORTE'].sum()

# Descuentos: importe de la fila con código 999999
descuentos_total = df.loc[df['CODIGO'] == 999999, 'IMPORTE'].sum()

# Productos vendidos (suma de cantidades, sin descuentos)
productos_vendidos = df['CANTIDAD'].sum()

# Mostrar KPIs
st.markdown(f"""
### Facturación total: **${facturacion_total:,.2f}**
### Descuentos: **${abs(descuentos_total):,.2f}**
### Productos vendidos: **{productos_vendidos:,.2f}**
""")

# Filtros
familias = st.multiselect(
    "Filtrar por Familia",
    options=sorted(df['FAMILIA'].unique()),
    default=sorted(df['FAMILIA'].unique())
)
articulos_filtrados = df[df['FAMILIA'].isin(familias)]['ARTICULO'].unique()
articulos = st.multiselect(
    "Filtrar por Artículo",
    options=sorted(articulos_filtrados),
    default=sorted(articulos_filtrados)
)

df_filtrado = df[(df['FAMILIA'].isin(familias)) & (df['ARTICULO'].isin(articulos))]

# Agrupar y ordenar
orden = st.selectbox("Ordenar por:", options=['IMPORTE', 'CANTIDAD', 'ARTICULO'])
asc = st.checkbox("Ascendente", value=False)

df_grouped = df_filtrado.groupby('ARTICULO').agg({'IMPORTE':'sum', 'CANTIDAD':'sum'}).reset_index()
top20 = df_grouped.sort_values('IMPORTE', ascending=False).head(20)
top20['Acumulado'] = top20['IMPORTE'].cumsum()
top20['Porcentaje Acumulado'] = 100 * top20['Acumulado'] / top20['IMPORTE'].sum()

# Calcular porcentaje individual y acumulado
top20['Porcentaje Individual'] = 100 * top20['IMPORTE'] / top20['IMPORTE'].sum()
top20['Porcentaje Acumulado'] = top20['Porcentaje Individual'].cumsum()

# Para barras apiladas: acumulado hasta el producto anterior
top20['Acumulado Previo'] = top20['Porcentaje Acumulado'] - top20['Porcentaje Individual']

fig = go.Figure()

# Barra naranja: acumulado previo (lo que ya sumaron los anteriores)
fig.add_trace(
    go.Bar(
        x=top20['ARTICULO'],
        y=top20['Acumulado Previo'],
        name='Acumulado (%)',
        marker_color='orange',
        text=[f"{acum:.1f}%" for acum in top20['Acumulado Previo']],
        textposition='none'
    )
)

# Barra azul: aporte individual de cada producto
fig.add_trace(
    go.Bar(
        x=top20['ARTICULO'],
        y=top20['Porcentaje Individual'],
        name='Aporte Producto (%)',
        marker_color='dodgerblue',
        text=[f"${int(imp):,}\n{pct:.1f}%" for imp, pct in zip(top20['IMPORTE'], top20['Porcentaje Individual'])],
        textposition='outside'
    )
)

# Línea de porcentaje acumulado (opcional, para reforzar visualmente)
fig.add_trace(
    go.Scatter(
        x=top20['ARTICULO'],
        y=top20['Porcentaje Acumulado'],
        name='Porcentaje Acumulado (%)',
        mode='lines+markers',
        line=dict(color='black', width=2, dash='dot'),
        marker=dict(color='black'),
        yaxis='y'
    )
)

fig.update_layout(
    barmode='stack',
    xaxis_title='Producto',
    yaxis=dict(
        title='Porcentaje Acumulado (%)',
        showgrid=False,
        zeroline=False,
        range=[0, 110]
    ),
    title='Diagrama de Pareto Acumulado - Top 20 Productos por Importe',
    legend=dict(x=0.01, y=0.99, font=dict(size=14)),
    xaxis_tickangle=-45
)

# Selector para cantidad de productos
max_productos = len(df_grouped)
n_productos = st.slider("Cantidad de productos a mostrar (sin contar 'Otros')", min_value=5, max_value=max_productos, value=20)

# Ordenar y seleccionar los N productos principales
df_sorted = df_grouped.sort_values('IMPORTE', ascending=False).reset_index(drop=True)
topN = df_sorted.head(n_productos).copy()

# Calcular el resto ("Otros")
if n_productos < max_productos:
    otros = df_sorted.iloc[n_productos:]
    otros_importe = otros['IMPORTE'].sum()
    otros_cantidad = otros['CANTIDAD'].sum()
    otros_row = pd.DataFrame([{
        'ARTICULO': 'Otros',
        'IMPORTE': otros_importe,
        'CANTIDAD': otros_cantidad
    }])
    topN = pd.concat([topN, otros_row], ignore_index=True)

# Calcular porcentajes y acumulados
topN['Porcentaje Individual'] = 100 * topN['IMPORTE'] / topN['IMPORTE'].sum()
topN['Porcentaje Acumulado'] = topN['Porcentaje Individual'].cumsum()
topN['Acumulado Previo'] = topN['Porcentaje Acumulado'] - topN['Porcentaje Individual']

fig = go.Figure()

# Barra naranja: acumulado previo
fig.add_trace(
    go.Bar(
        x=topN['ARTICULO'],
        y=topN['Acumulado Previo'],
        name='Acumulado (%)',
        marker_color='orange',
        text=[f"{acum:.1f}%" for acum in topN['Acumulado Previo']],
        textposition='auto',  # Muestra el texto dentro de la barra
        yaxis='y1'
    )
)

# Barra azul: aporte individual
fig.add_trace(
    go.Bar(
        x=topN['ARTICULO'],
        y=topN['Porcentaje Individual'],
        name='Aporte Producto (%)',
        marker_color='dodgerblue',
        text=[f"{pct:.1f}%" for pct in topN['Porcentaje Individual']],
        textposition='auto',  # Solo muestra el porcentaje en la barra
        yaxis='y1'
    )
)

# Línea de porcentaje acumulado (eje secundario)
fig.add_trace(
    go.Scatter(
        x=topN['ARTICULO'],
        y=topN['Porcentaje Acumulado'],
        name='Porcentaje Acumulado (%)',
        mode='lines+markers',
        line=dict(color='white', width=2, dash='dot'),
        marker=dict(color='black'),
        yaxis='y2'
    )
)

fig.update_layout(
    barmode='stack',
    width=1600,   # ancho en píxeles
    height=700,   # alto en píxeles
    xaxis=dict(
        title=dict(text='Producto', font=dict(size=18)),
        tickangle=-45,
        tickfont=dict(size=14)
    ),
    yaxis=dict(
        title=dict(text='Porcentaje Individual (%)', font=dict(size=18)),
        showgrid=False,
        zeroline=False,
        range=[0, 110],
        tickfont=dict(size=14)
    ),
    yaxis2=dict(
        title=dict(text='Porcentaje Acumulado (%)', font=dict(size=18)),
        overlaying='y',
        side='right',
        range=[0, 110],
        tickfont=dict(size=14)
    ),
    title=dict(
        text=f'Diagrama de Pareto Acumulado - Top {n_productos} Productos + Otros',
        font=dict(size=22)
    ),
    legend=dict(
        x=0.01,
        y=0.99,
        font=dict(size=14)
    )
)

st.plotly_chart(fig, use_container_width=True)

# --- Gráfico simple de cantidad de ventas por producto ---

# Agrupa y ordena por cantidad
df_cantidad = df_filtrado.groupby('ARTICULO').agg({'CANTIDAD':'sum'}).reset_index()
topN_cant = df_cantidad.sort_values('CANTIDAD', ascending=False).head(n_productos).copy()

# "Otros" para cantidad
if n_productos < len(df_cantidad):
    otros_cant = df_cantidad.iloc[n_productos:]
    otros_cant_total = otros_cant['CANTIDAD'].sum()
    otros_row_cant = pd.DataFrame([{
        'ARTICULO': 'Otros',
        'CANTIDAD': otros_cant_total
    }])
    topN_cant = pd.concat([topN_cant, otros_row_cant], ignore_index=True)

fig_cant = go.Figure()

fig_cant.add_trace(
    go.Bar(
        x=topN_cant['ARTICULO'],
        y=topN_cant['CANTIDAD'],
        name='Cantidad Vendida',
        marker_color='mediumseagreen',
        text=[f"{int(cant):,}" for cant in topN_cant['CANTIDAD']],
        textposition='auto'
    )
)

fig_cant.update_layout(
    width=1600,
    height=500,
    xaxis=dict(
        title=dict(text='Producto', font=dict(size=18)),
        tickangle=-45,
        tickfont=dict(size=14)
    ),
    yaxis=dict(
        title=dict(text='Cantidad Vendida', font=dict(size=18)),
        showgrid=True,
        zeroline=True,
        tickfont=dict(size=14)
    ),
    title=dict(
        text=f'Top {n_productos} Productos + Otros por Cantidad Vendida',
        font=dict(size=22)
    ),
    legend=dict(
        x=0.01,
        y=0.99,
        font=dict(size=14)
    )
)

st.plotly_chart(fig_cant, use_container_width=True)

