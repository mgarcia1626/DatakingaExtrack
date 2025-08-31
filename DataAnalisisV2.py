import pandas as pd
import streamlit as st
import plotly.graph_objects as go

st.title("Diagrama de Pareto - Productos por Importe")

# Leer el archivo CSV con las columnas correctas
columnas = ['FAMILIA', 'CODIGO', 'ARTICULO', 'CANTIDAD', 'IMPORTE', 'SUBFAMILIA']
df = pd.read_csv('DATA.csv', sep=';', skiprows=4, names=columnas, encoding='utf-8', engine='python')

# Limpieza y conversión de datos con manejo de errores
df['IMPORTE'] = df['IMPORTE'].replace(',', '.', regex=True)
df['IMPORTE'] = pd.to_numeric(df['IMPORTE'], errors='coerce')

df['CANTIDAD'] = df['CANTIDAD'].replace(',', '.', regex=True)
df['CANTIDAD'] = pd.to_numeric(df['CANTIDAD'], errors='coerce')

# Remover filas con valores NaN si es necesario
df = df.dropna(subset=['IMPORTE', 'CANTIDAD'])

# Filtrar descuentos (código 999999) para KPIs
df_sin_descuentos = df[df['CODIGO'] != 999999]

# --- KPIs arriba del dashboard ---

# Facturación total (sin descuentos)
facturacion_total = df_sin_descuentos['IMPORTE'].sum()

# Descuentos: importe de la fila con código 999999
descuentos_total = df.loc[df['CODIGO'] == 999999, 'IMPORTE'].sum()

# Productos vendidos (suma de cantidades, sin descuentos)
productos_vendidos = df_sin_descuentos['CANTIDAD'].sum()

# Mostrar KPIs
st.markdown(f"""
### Facturación total: **${facturacion_total:,.2f}**
### Descuentos: **${abs(descuentos_total):,.2f}**
### Productos vendidos: **{productos_vendidos:,.0f}**
""")

# Filtro principal por subfamilia
subfamilias = st.multiselect(
    "Filtrar por Subfamilia",
    options=sorted(df_sin_descuentos['SUBFAMILIA'].unique()),
    default=sorted(df_sin_descuentos['SUBFAMILIA'].unique())
)

# Filtro secundario por familia basado en las subfamilias seleccionadas
familias_disponibles = df_sin_descuentos[df_sin_descuentos['SUBFAMILIA'].isin(subfamilias)]['FAMILIA'].unique()
familias = st.multiselect(
    "Filtrar por Familia",
    options=sorted(familias_disponibles),
    default=sorted(familias_disponibles)
)

df_filtrado = df_sin_descuentos[
    (df_sin_descuentos['SUBFAMILIA'].isin(subfamilias)) & 
    (df_sin_descuentos['FAMILIA'].isin(familias))
]

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

# --- Gráfico simple de cantidad de ventas por subfamilia ---

# Agrupa y ordena por cantidad por subfamilia
df_subfamilia_cant = df_filtrado.groupby('SUBFAMILIA').agg({'CANTIDAD':'sum'}).reset_index()
df_subfamilia_cant = df_subfamilia_cant.sort_values('CANTIDAD', ascending=False)

fig_subfamilia = go.Figure()

fig_subfamilia.add_trace(
    go.Bar(
        x=df_subfamilia_cant['SUBFAMILIA'],
        y=df_subfamilia_cant['CANTIDAD'],
        name='Cantidad Vendida por Subfamilia',
        marker_color='mediumpurple',
        text=[f"{int(cant):,}" for cant in df_subfamilia_cant['CANTIDAD']],
        textposition='auto'
    )
)

fig_subfamilia.update_layout(
    width=1600,
    height=500,
    xaxis=dict(
        title=dict(text='Subfamilia', font=dict(size=18)),
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
        text='Cantidad Vendida por Subfamilia de Productos',
        font=dict(size=22)
    ),
    legend=dict(
        x=0.01,
        y=0.99,
        font=dict(size=14)
    )
)

st.plotly_chart(fig_subfamilia, use_container_width=True)

# --- Diagrama de Pareto Acumulado por Subfamilia ---

# Agrupa por subfamilia y calcula importes
df_subfamilia_pareto = df_filtrado.groupby('SUBFAMILIA').agg({'IMPORTE':'sum', 'CANTIDAD':'sum'}).reset_index()
df_subfamilia_pareto = df_subfamilia_pareto.sort_values('IMPORTE', ascending=False).reset_index(drop=True)

# Calcular porcentajes y acumulados
df_subfamilia_pareto['Porcentaje Individual'] = 100 * df_subfamilia_pareto['IMPORTE'] / df_subfamilia_pareto['IMPORTE'].sum()
df_subfamilia_pareto['Porcentaje Acumulado'] = df_subfamilia_pareto['Porcentaje Individual'].cumsum()
df_subfamilia_pareto['Acumulado Previo'] = df_subfamilia_pareto['Porcentaje Acumulado'] - df_subfamilia_pareto['Porcentaje Individual']

fig_subfamilia_pareto = go.Figure()

# Barra naranja: acumulado previo
fig_subfamilia_pareto.add_trace(
    go.Bar(
        x=df_subfamilia_pareto['SUBFAMILIA'],
        y=df_subfamilia_pareto['Acumulado Previo'],
        name='Acumulado (%)',
        marker_color='orange',
        text=[f"{acum:.1f}%" for acum in df_subfamilia_pareto['Acumulado Previo']],
        textposition='auto',
        yaxis='y1'
    )
)

# Barra azul: aporte individual
fig_subfamilia_pareto.add_trace(
    go.Bar(
        x=df_subfamilia_pareto['SUBFAMILIA'],
        y=df_subfamilia_pareto['Porcentaje Individual'],
        name='Aporte Subfamilia (%)',
        marker_color='dodgerblue',
        text=[f"{pct:.1f}%" for pct in df_subfamilia_pareto['Porcentaje Individual']],
        textposition='auto',
        yaxis='y1'
    )
)

# Línea de porcentaje acumulado
fig_subfamilia_pareto.add_trace(
    go.Scatter(
        x=df_subfamilia_pareto['SUBFAMILIA'],
        y=df_subfamilia_pareto['Porcentaje Acumulado'],
        name='Porcentaje Acumulado (%)',
        mode='lines+markers',
        line=dict(color='white', width=2, dash='dot'),
        marker=dict(color='black'),
        yaxis='y2'
    )
)

fig_subfamilia_pareto.update_layout(
    barmode='stack',
    width=1600,
    height=700,
    xaxis=dict(
        title=dict(text='Subfamilia', font=dict(size=18)),
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
        text='Diagrama de Pareto Acumulado - Subfamilias por Importe',
        font=dict(size=22)
    ),
    legend=dict(
        x=0.01,
        y=0.99,
        font=dict(size=14)
    )
)

st.plotly_chart(fig_subfamilia_pareto, use_container_width=True)

# --- Gráfico simple de cantidad de ventas por familia ---

# Agrupa y ordena por cantidad por familia
df_familia_cant = df_filtrado.groupby('FAMILIA').agg({'CANTIDAD':'sum'}).reset_index()
df_familia_cant = df_familia_cant.sort_values('CANTIDAD', ascending=False)

fig_familia = go.Figure()

fig_familia.add_trace(
    go.Bar(
        x=df_familia_cant['FAMILIA'],
        y=df_familia_cant['CANTIDAD'],
        name='Cantidad Vendida por Familia',
        marker_color='lightcoral',
        text=[f"{int(cant):,}" for cant in df_familia_cant['CANTIDAD']],
        textposition='auto'
    )
)

fig_familia.update_layout(
    width=1600,
    height=500,
    xaxis=dict(
        title=dict(text='Familia', font=dict(size=18)),
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
        text='Cantidad Vendida por Familia de Productos',
        font=dict(size=22)
    ),
    legend=dict(
        x=0.01,
        y=0.99,
        font=dict(size=14)
    )
)

st.plotly_chart(fig_familia, use_container_width=True)

# --- Diagrama de Pareto Acumulado por Familia ---

# Agrupa por familia y calcula importes
df_familia_pareto = df_filtrado.groupby('FAMILIA').agg({'IMPORTE':'sum', 'CANTIDAD':'sum'}).reset_index()
df_familia_pareto = df_familia_pareto.sort_values('IMPORTE', ascending=False).reset_index(drop=True)

# Calcular porcentajes y acumulados
df_familia_pareto['Porcentaje Individual'] = 100 * df_familia_pareto['IMPORTE'] / df_familia_pareto['IMPORTE'].sum()
df_familia_pareto['Porcentaje Acumulado'] = df_familia_pareto['Porcentaje Individual'].cumsum()
df_familia_pareto['Acumulado Previo'] = df_familia_pareto['Porcentaje Acumulado'] - df_familia_pareto['Porcentaje Individual']

fig_familia_pareto = go.Figure()

# Barra naranja: acumulado previo
fig_familia_pareto.add_trace(
    go.Bar(
        x=df_familia_pareto['FAMILIA'],
        y=df_familia_pareto['Acumulado Previo'],
        name='Acumulado (%)',
        marker_color='orange',
        text=[f"{acum:.1f}%" for acum in df_familia_pareto['Acumulado Previo']],
        textposition='auto',
        yaxis='y1'
    )
)

# Barra azul: aporte individual
fig_familia_pareto.add_trace(
    go.Bar(
        x=df_familia_pareto['FAMILIA'],
        y=df_familia_pareto['Porcentaje Individual'],
        name='Aporte Familia (%)',
        marker_color='dodgerblue',
        text=[f"{pct:.1f}%" for pct in df_familia_pareto['Porcentaje Individual']],
        textposition='auto',
        yaxis='y1'
    )
)

# Línea de porcentaje acumulado
fig_familia_pareto.add_trace(
    go.Scatter(
        x=df_familia_pareto['FAMILIA'],
        y=df_familia_pareto['Porcentaje Acumulado'],
        name='Porcentaje Acumulado (%)',
        mode='lines+markers',
        line=dict(color='white', width=2, dash='dot'),
        marker=dict(color='black'),
        yaxis='y2'
    )
)

fig_familia_pareto.update_layout(
    barmode='stack',
    width=1600,
    height=700,
    xaxis=dict(
        title=dict(text='Familia', font=dict(size=18)),
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
        text='Diagrama de Pareto Acumulado - Familias por Importe',
        font=dict(size=22)
    ),
    legend=dict(
        x=0.01,
        y=0.99,
        font=dict(size=14)
    )
)

st.plotly_chart(fig_familia_pareto, use_container_width=True)

