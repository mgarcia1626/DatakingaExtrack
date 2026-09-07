"""
DATAKINGA - Dashboard Interactivo
Visualizacion de datos con Streamlit
"""
import re
import unicodedata
from difflib import SequenceMatcher
import streamlit as st
import pandas as pd
import os
from datetime import datetime
from dotenv import load_dotenv
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
from datakinga.core.storage.supabase_client import get_client, fetch_tickets, fetch_consumos
from datakinga.apps.pipelines.render_pipeline import run_extraction

# Cargar variables de entorno
load_dotenv()

def _normalizar_codigo(value):
    if value is None or pd.isna(value):
        return ""
    codigo = str(value).strip().upper().replace(" ", "")
    codigo = re.sub(r"[^A-Z0-9]", "", codigo)
    if not codigo or codigo in {"NAN", "NONE"}:
        return ""
    if codigo.isdigit():
        return str(int(codigo))
    return codigo

def _normalizar_sucursal(value):
    if value is None or pd.isna(value):
        return ""
    return str(value).strip().upper()

def _normalizar_texto(value):
    if value is None or pd.isna(value):
        return ''
    text = unicodedata.normalize('NFKD', str(value))
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _agregar_familia(df_tickets, df_consumos):
    """Match cada ticket con la familia usando el nombre del producto; el codigo queda como fallback opcional."""
    if df_tickets.empty or df_consumos.empty:
        return df_tickets.copy()

    tickets = df_tickets.copy().rename(columns={'Numero': 'Numero', 'Codigo': 'Codigo', 'Descripcion': 'Descripcion'})
    consumos = df_consumos.copy()

    if 'Codigo' in consumos.columns:
        consumos['Codigo'] = consumos['Codigo'].fillna('').astype(str).str.strip()
    if 'Articulo' in consumos.columns:
        consumos['Articulo'] = consumos['Articulo'].fillna('').astype(str).str.strip()
    if 'Sucursal' in consumos.columns:
        consumos['Sucursal'] = consumos['Sucursal'].fillna('').astype(str).str.strip()

    for col in ['Codigo', 'Sucursal', 'Descripcion']:
        if col in tickets.columns:
            tickets[col] = tickets[col].fillna('').astype(str).str.strip()

    tickets['_sucursal_match'] = tickets['Sucursal'].map(_normalizar_sucursal) if 'Sucursal' in tickets.columns else ''
    tickets['_descripcion_match'] = tickets['Descripcion'].map(_normalizar_texto) if 'Descripcion' in tickets.columns else ''
    consumos['_sucursal_match'] = consumos['Sucursal'].map(_normalizar_sucursal) if 'Sucursal' in consumos.columns else ''
    consumos['_descripcion_match'] = consumos['Articulo'].map(_normalizar_texto) if 'Articulo' in consumos.columns else ''

    lookup_desc = consumos[['Familia', '_descripcion_match', '_sucursal_match']].copy()
    lookup_desc = lookup_desc.dropna(subset=['Familia', '_descripcion_match', '_sucursal_match'])
    lookup_desc = lookup_desc.drop_duplicates(subset=['_descripcion_match', '_sucursal_match'], keep='last')
    lookup_desc_map = lookup_desc.set_index(['_descripcion_match', '_sucursal_match'])['Familia'].to_dict()

    merged = tickets.merge(
        lookup_desc.rename(columns={'_descripcion_match': 'Descripcion_match', '_sucursal_match': 'Sucursal_match'}),
        left_on=['_descripcion_match', '_sucursal_match'],
        right_on=['Descripcion_match', 'Sucursal_match'],
        how='left',
        suffixes=('_ticket', '_desc')
    )

    def _resolver_familia(row):
        if pd.notna(row.get('Familia_desc')):
            return row['Familia_desc']
        desc = row.get('_descripcion_match', '')
        suc = row.get('_sucursal_match', '')
        if not desc or not suc:
            return None
        key = (desc, suc)
        if key in lookup_desc_map:
            return lookup_desc_map[key]
        candidates = [
            (item[0], item[1]) for item in lookup_desc[['Familia', '_descripcion_match', '_sucursal_match']].itertuples(index=False, name=None)
            if item[2] == suc
        ]
        if not candidates:
            return None
        best = max(candidates, key=lambda item: SequenceMatcher(None, desc, item[1]).ratio())
        score = SequenceMatcher(None, desc, best[1]).ratio()
        return best[0] if score >= 0.7 else None

    merged['Familia'] = merged.apply(_resolver_familia, axis=1)
    merged = merged.drop(columns=['Descripcion_match', 'Sucursal_match', 'Familia_desc'], errors='ignore')
    return merged

def _format_table(df, *, currency_cols=None, percent_cols=None, int_cols=None):
    """Keep numeric columns numeric for sorting, and format only the display layer."""
    display = df.copy()
    formatters = {}

    for col in currency_cols or []:
        if col in display.columns:
            formatters[col] = "${:,.2f}".format
    for col in percent_cols or []:
        if col in display.columns:
            formatters[col] = "{:.2f}%".format
    for col in int_cols or []:
        if col in display.columns:
            formatters[col] = "{:,.0f}".format

    if not formatters:
        return display
    return display.style.format(formatters)
def _apply_dark_mode():
    """Apply a consistent dark theme for Streamlit and Plotly charts."""
    pio.templates.default = "plotly_dark"
    st.markdown(
        """
        <style>
        :root {
            --bg-main: #0f172a;
            --bg-panel: #111827;
            --bg-card: #1f2937;
            --text-main: #e5e7eb;
            --text-muted: #93a4b8;
            --accent: #22d3ee;
            --border: #334155;
        }

        .stApp {
            background: radial-gradient(circle at 10% 0%, #1e293b 0%, var(--bg-main) 45%);
            color: var(--text-main);
        }

        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0b1220 0%, #111827 100%);
            border-right: 1px solid var(--border);
        }

        .stMetric {
            background: color-mix(in srgb, var(--bg-card) 92%, #000 8%);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 10px;
        }

        .stTabs [data-baseweb="tab-list"] button {
            color: var(--text-main);
        }

        .stAlert {
            border-radius: 10px;
        }

        h1, h2, h3, h4, h5, h6, p, span, label {
            color: var(--text-main);
        }

        .stCaption {
            color: var(--text-muted);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _normalizar_familia(value):
    if value is None or pd.isna(value):
        return ""
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.lower().strip()


def _confiabilidad_promedio(serie):
    """Estima que tan confiable es un promedio muestral.

    Usa el error estandar de la media (SEM) y el margen de error al 95% (1.96 * SEM)
    relativo a la media de la muestra. Un margen de error chico respecto a la media
    indica un promedio mas confiable (menos variabilidad / mas datos).

    Retorna: n, desvio_estandar, error_estandar, margen_error_95, confiabilidad_pct.
    confiabilidad_pct = 100 * (1 - margen_error_95 / media), acotado entre 0 y 100.
    Con n < 2 o media 0 no se puede estimar variabilidad -> confiabilidad_pct = 0.0.
    """
    n = int(serie.shape[0])
    media = float(serie.mean()) if n else 0.0
    if n < 2 or media == 0:
        return {
            "n": n,
            "desvio_estandar": 0.0,
            "error_estandar": 0.0,
            "margen_error_95": 0.0,
            "confiabilidad_pct": 0.0,
        }
    desvio_estandar = float(serie.std(ddof=1))
    error_estandar = desvio_estandar / (n ** 0.5)
    margen_error_95 = 1.96 * error_estandar
    confiabilidad_pct = max(0.0, min(100.0, 100.0 * (1 - (margen_error_95 / media))))
    return {
        "n": n,
        "desvio_estandar": desvio_estandar,
        "error_estandar": error_estandar,
        "margen_error_95": margen_error_95,
        "confiabilidad_pct": confiabilidad_pct,
    }


def _clasificar_confiabilidad(confiabilidad_pct):
    """Clasifica un porcentaje de confiabilidad en 3 rangos con color asociado.

    Verde (confiable): >= 90%. Amarillo (medio confiable): 70% a 89.9%. Rojo (no confiable): < 70%.
    Retorna: (color_texto, color_fondo, etiqueta).
    """

    if confiabilidad_pct >= 90:
        return "#1e7d34", "#d4edda", "Confiable"
    if confiabilidad_pct >= 70:
        return "#8a6d00", "#fff3cd", "Medio confiable"
    return "#a12622", "#f8d7da", "No confiable"


def _metric_con_confiabilidad(label, valor_str, confiabilidad_pct):
    """Muestra un st.metric y, debajo, un badge de color con la confiabilidad del dato."""
    color_texto, color_fondo, etiqueta = _clasificar_confiabilidad(confiabilidad_pct)
    st.metric(label, valor_str)
    st.markdown(
        f"""<div style="background-color:{color_fondo}; color:{color_texto}; border-radius:6px;
        padding:2px 8px; font-size:0.75rem; font-weight:600; text-align:center; margin-top:-8px;">
        {etiqueta} - {confiabilidad_pct:,.1f}%</div>""",
        unsafe_allow_html=True,
    )


def _calcular_metricas_tickets(df_tickets_filtrado, df_consumos):
    """Compute total/food/non-food average tickets with safe handling of sparse data."""
    columnas_necesarias = {"Numero", "Importe"}
    if df_tickets_filtrado.empty or not columnas_necesarias.issubset(df_tickets_filtrado.columns):
        return {
            "total_tickets": 0,
            "tickets_comida": 0,
            "tickets_sin_comida": 0,
            "ticket_promedio_total": 0.0,
            "ticket_promedio_comida": 0.0,
            "ticket_promedio_sin_comida": 0.0,
            "cubiertos_total": 0.0,
            "cubiertos_comida": 0.0,
            "cubiertos_sin_comida": 0.0,
            "cubiertos_promedio_total": 0.0,
            "cubiertos_mediana_total": 0.0,
            "cubiertos_promedio_comida": 0.0,
            "cubiertos_mediana_comida": 0.0,
            "cubiertos_promedio_sin_comida": 0.0,
            "cubiertos_mediana_sin_comida": 0.0,
            "facturacion_por_cubierto_total": 0.0,
            "facturacion_por_cubierto_comida": 0.0,
            "facturacion_por_cubierto_sin_comida": 0.0,
            "confiabilidad_ticket_total": {"n": 0, "desvio_estandar": 0.0, "error_estandar": 0.0, "margen_error_95": 0.0, "confiabilidad_pct": 0.0},
            "confiabilidad_ticket_comida": {"n": 0, "desvio_estandar": 0.0, "error_estandar": 0.0, "margen_error_95": 0.0, "confiabilidad_pct": 0.0},
            "confiabilidad_ticket_sin_comida": {"n": 0, "desvio_estandar": 0.0, "error_estandar": 0.0, "margen_error_95": 0.0, "confiabilidad_pct": 0.0},
            "confiabilidad_cubiertos_total": {"n": 0, "desvio_estandar": 0.0, "error_estandar": 0.0, "margen_error_95": 0.0, "confiabilidad_pct": 0.0},
            "confiabilidad_cubiertos_comida": {"n": 0, "desvio_estandar": 0.0, "error_estandar": 0.0, "margen_error_95": 0.0, "confiabilidad_pct": 0.0},
            "confiabilidad_cubiertos_sin_comida": {"n": 0, "desvio_estandar": 0.0, "error_estandar": 0.0, "margen_error_95": 0.0, "confiabilidad_pct": 0.0},
            "confiabilidad_facturacion_cubierto_total": {"n": 0, "desvio_estandar": 0.0, "error_estandar": 0.0, "margen_error_95": 0.0, "confiabilidad_pct": 0.0},
            "confiabilidad_facturacion_cubierto_comida": {"n": 0, "desvio_estandar": 0.0, "error_estandar": 0.0, "margen_error_95": 0.0, "confiabilidad_pct": 0.0},
            "confiabilidad_facturacion_cubierto_sin_comida": {"n": 0, "desvio_estandar": 0.0, "error_estandar": 0.0, "margen_error_95": 0.0, "confiabilidad_pct": 0.0},
        }

    df_base = df_tickets_filtrado.copy()
    if "Cantidad" not in df_base.columns:
        df_base["Cantidad"] = 1

    df_base["Numero"] = df_base["Numero"].astype(str).str.strip()
    df_base = df_base[df_base["Numero"].ne("")].copy()
    if df_base.empty:
        return {
            "total_tickets": 0,
            "tickets_comida": 0,
            "tickets_sin_comida": 0,
            "ticket_promedio_total": 0.0,
            "ticket_promedio_comida": 0.0,
            "ticket_promedio_sin_comida": 0.0,
            "cubiertos_total": 0.0,
            "cubiertos_comida": 0.0,
            "cubiertos_sin_comida": 0.0,
            "cubiertos_promedio_total": 0.0,
            "cubiertos_mediana_total": 0.0,
            "cubiertos_promedio_comida": 0.0,
            "cubiertos_mediana_comida": 0.0,
            "cubiertos_promedio_sin_comida": 0.0,
            "cubiertos_mediana_sin_comida": 0.0,
            "facturacion_por_cubierto_total": 0.0,
            "facturacion_por_cubierto_comida": 0.0,
            "facturacion_por_cubierto_sin_comida": 0.0,
            "confiabilidad_ticket_total": {"n": 0, "desvio_estandar": 0.0, "error_estandar": 0.0, "margen_error_95": 0.0, "confiabilidad_pct": 0.0},
            "confiabilidad_ticket_comida": {"n": 0, "desvio_estandar": 0.0, "error_estandar": 0.0, "margen_error_95": 0.0, "confiabilidad_pct": 0.0},
            "confiabilidad_ticket_sin_comida": {"n": 0, "desvio_estandar": 0.0, "error_estandar": 0.0, "margen_error_95": 0.0, "confiabilidad_pct": 0.0},
            "confiabilidad_cubiertos_total": {"n": 0, "desvio_estandar": 0.0, "error_estandar": 0.0, "margen_error_95": 0.0, "confiabilidad_pct": 0.0},
            "confiabilidad_cubiertos_comida": {"n": 0, "desvio_estandar": 0.0, "error_estandar": 0.0, "margen_error_95": 0.0, "confiabilidad_pct": 0.0},
            "confiabilidad_cubiertos_sin_comida": {"n": 0, "desvio_estandar": 0.0, "error_estandar": 0.0, "margen_error_95": 0.0, "confiabilidad_pct": 0.0},
            "confiabilidad_facturacion_cubierto_total": {"n": 0, "desvio_estandar": 0.0, "error_estandar": 0.0, "margen_error_95": 0.0, "confiabilidad_pct": 0.0},
            "confiabilidad_facturacion_cubierto_comida": {"n": 0, "desvio_estandar": 0.0, "error_estandar": 0.0, "margen_error_95": 0.0, "confiabilidad_pct": 0.0},
            "confiabilidad_facturacion_cubierto_sin_comida": {"n": 0, "desvio_estandar": 0.0, "error_estandar": 0.0, "margen_error_95": 0.0, "confiabilidad_pct": 0.0},
        }

    df_base["Cantidad"] = pd.to_numeric(df_base["Cantidad"], errors="coerce").fillna(0)
    df_base["Importe"] = pd.to_numeric(df_base["Importe"], errors="coerce").fillna(0)
    df_base["Importe_Total_Linea"] = df_base["Cantidad"] * df_base["Importe"]

    df_con_familia = _agregar_familia(df_base, df_consumos)
    familia_col = "Familia" if "Familia" in df_con_familia.columns else None
    if familia_col is None:
        df_con_familia["Es_Comida"] = False
    else:
        # "almuerzo" es la familia usada por la sucursal Junin para identificar comidas
        # (Junin no usa COCINA/PLATO DEL DIA/COMIDA(S) como Pasadena).
        familias_comida = {"comida", "comidas", "plato del dia", "platos del dia", "ensalada", "ensaladas", "cocina", "almuerzo"}
        df_con_familia["Es_Comida"] = (
            df_con_familia[familia_col]
            .map(_normalizar_familia)
            .isin(familias_comida)
        )

    ticket_totales = df_con_familia.groupby("Numero", dropna=False)["Importe_Total_Linea"].sum()
    ticket_tiene_comida = df_con_familia.groupby("Numero", dropna=False)["Es_Comida"].any()

    total_tickets = int(ticket_totales.shape[0])
    facturacion_total = float(ticket_totales.sum())

    tickets_comida_idx = ticket_tiene_comida[ticket_tiene_comida].index
    tickets_sin_comida_idx = ticket_tiene_comida[~ticket_tiene_comida].index

    total_tickets_comida = int(len(tickets_comida_idx))
    total_tickets_sin_comida = int(len(tickets_sin_comida_idx))

    # Facturacion por familia: sumamos solo las lineas de las 3 familias de comida
    # (COMIDAS, PLATO DEL DIA, ENSALADAS), no el total completo de los tickets que las contienen.
    facturacion_tickets_comida = float(
        df_con_familia.loc[df_con_familia["Es_Comida"], "Importe_Total_Linea"].sum()
    )
    facturacion_tickets_sin_comida = float(
        df_con_familia.loc[~df_con_familia["Es_Comida"], "Importe_Total_Linea"].sum()
    )

    # Cubiertos: familia "CUBIERTOS" indica cantidad de personas por linea.
    # Sumamos Cantidad agrupando por ticket (puede haber mas de una linea por ticket),
    # luego clasificamos cada ticket segun si es "con comida" o "sin comida".
    if familia_col is not None:
        # Tolerancia defensiva a un typo de carga conocido en el catalogo de Consumos
        # de la sucursal Junin: "CIBIERTOS" en lugar de "CUBIERTOS" (falta la U).
        # No es un mecanismo general de correccion de typos, solo cubre esta variante puntual.
        familias_cubiertos = {"cubiertos", "cibiertos"}
        mask_cubiertos = df_con_familia[familia_col].map(_normalizar_familia).isin(familias_cubiertos)
    else:
        mask_cubiertos = pd.Series(False, index=df_con_familia.index)
    cubiertos_por_ticket = df_con_familia.loc[mask_cubiertos].groupby("Numero", dropna=False)["Cantidad"].sum()

    cubiertos_serie_total = cubiertos_por_ticket.reindex(ticket_totales.index).fillna(0)
    cubiertos_total = float(cubiertos_serie_total.sum())
    cubiertos_promedio_total = float(cubiertos_serie_total.mean()) if total_tickets else 0.0
    cubiertos_mediana_total = float(cubiertos_serie_total.median()) if total_tickets else 0.0

    cubiertos_comida = float(cubiertos_por_ticket.reindex(tickets_comida_idx).fillna(0).sum())
    cubiertos_sin_comida = float(cubiertos_por_ticket.reindex(tickets_sin_comida_idx).fillna(0).sum())

    cubiertos_serie_comida = cubiertos_por_ticket.reindex(tickets_comida_idx).fillna(0)
    cubiertos_serie_sin_comida = cubiertos_por_ticket.reindex(tickets_sin_comida_idx).fillna(0)
    cubiertos_promedio_comida = float(cubiertos_serie_comida.mean()) if total_tickets_comida else 0.0
    cubiertos_mediana_comida = float(cubiertos_serie_comida.median()) if total_tickets_comida else 0.0
    cubiertos_promedio_sin_comida = float(cubiertos_serie_sin_comida.mean()) if total_tickets_sin_comida else 0.0
    cubiertos_mediana_sin_comida = float(cubiertos_serie_sin_comida.median()) if total_tickets_sin_comida else 0.0

    ticket_promedio_total = facturacion_total / total_tickets if total_tickets else 0.0
    ticket_promedio_comida = (
        facturacion_tickets_comida / total_tickets_comida if total_tickets_comida else 0.0
    )
    ticket_promedio_sin_comida = (
        facturacion_tickets_sin_comida / total_tickets_sin_comida if total_tickets_sin_comida else 0.0
    )
    facturacion_por_cubierto_total = (
        facturacion_total / cubiertos_total if cubiertos_total else 0.0
    )
    facturacion_por_cubierto_comida = (
        facturacion_tickets_comida / cubiertos_comida if cubiertos_comida else 0.0
    )
    facturacion_por_cubierto_sin_comida = (
        facturacion_tickets_sin_comida / cubiertos_sin_comida if cubiertos_sin_comida else 0.0
    )

    # Confiabilidad estadistica de cada promedio, en base al error estandar de la muestra.
    confiabilidad_ticket_total = _confiabilidad_promedio(ticket_totales)
    confiabilidad_ticket_comida = _confiabilidad_promedio(ticket_totales.reindex(tickets_comida_idx).fillna(0))
    confiabilidad_ticket_sin_comida = _confiabilidad_promedio(ticket_totales.reindex(tickets_sin_comida_idx).fillna(0))
    confiabilidad_cubiertos_total = _confiabilidad_promedio(cubiertos_serie_total)
    confiabilidad_cubiertos_comida = _confiabilidad_promedio(cubiertos_serie_comida)
    confiabilidad_cubiertos_sin_comida = _confiabilidad_promedio(cubiertos_serie_sin_comida)

    # Confiabilidad de la facturacion por cubierto: se calcula sobre el ratio
    # (facturacion del ticket / cubiertos del ticket) evaluado ticket por ticket,
    # solo para tickets con cubiertos > 0 (division por cero no aporta informacion).
    mask_cub_total = cubiertos_serie_total > 0
    fact_por_cubierto_serie_total = ticket_totales[mask_cub_total] / cubiertos_serie_total[mask_cub_total]

    facturacion_comida_por_ticket = (
        df_con_familia.loc[df_con_familia["Es_Comida"]].groupby("Numero", dropna=False)["Importe_Total_Linea"].sum()
    ).reindex(tickets_comida_idx).fillna(0)
    mask_cub_comida = cubiertos_serie_comida > 0
    fact_por_cubierto_serie_comida = (
        facturacion_comida_por_ticket[mask_cub_comida] / cubiertos_serie_comida[mask_cub_comida]
    )

    facturacion_sin_comida_por_ticket = (
        df_con_familia.loc[~df_con_familia["Es_Comida"]].groupby("Numero", dropna=False)["Importe_Total_Linea"].sum()
    ).reindex(tickets_sin_comida_idx).fillna(0)
    mask_cub_sin_comida = cubiertos_serie_sin_comida > 0
    fact_por_cubierto_serie_sin_comida = (
        facturacion_sin_comida_por_ticket[mask_cub_sin_comida] / cubiertos_serie_sin_comida[mask_cub_sin_comida]
    )

    confiabilidad_facturacion_cubierto_total = _confiabilidad_promedio(fact_por_cubierto_serie_total)
    confiabilidad_facturacion_cubierto_comida = _confiabilidad_promedio(fact_por_cubierto_serie_comida)
    confiabilidad_facturacion_cubierto_sin_comida = _confiabilidad_promedio(fact_por_cubierto_serie_sin_comida)

    return {
        "total_tickets": total_tickets,
        "tickets_comida": total_tickets_comida,
        "tickets_sin_comida": total_tickets_sin_comida,
        "ticket_promedio_total": ticket_promedio_total,
        "ticket_promedio_comida": ticket_promedio_comida,
        "ticket_promedio_sin_comida": ticket_promedio_sin_comida,
        "cubiertos_total": cubiertos_total,
        "cubiertos_comida": cubiertos_comida,
        "cubiertos_sin_comida": cubiertos_sin_comida,
        "cubiertos_promedio_total": cubiertos_promedio_total,
        "cubiertos_mediana_total": cubiertos_mediana_total,
        "cubiertos_promedio_comida": cubiertos_promedio_comida,
        "cubiertos_mediana_comida": cubiertos_mediana_comida,
        "cubiertos_promedio_sin_comida": cubiertos_promedio_sin_comida,
        "cubiertos_mediana_sin_comida": cubiertos_mediana_sin_comida,
        "facturacion_por_cubierto_total": facturacion_por_cubierto_total,
        "facturacion_por_cubierto_comida": facturacion_por_cubierto_comida,
        "facturacion_por_cubierto_sin_comida": facturacion_por_cubierto_sin_comida,
        "confiabilidad_ticket_total": confiabilidad_ticket_total,
        "confiabilidad_ticket_comida": confiabilidad_ticket_comida,
        "confiabilidad_ticket_sin_comida": confiabilidad_ticket_sin_comida,
        "confiabilidad_cubiertos_total": confiabilidad_cubiertos_total,
        "confiabilidad_cubiertos_comida": confiabilidad_cubiertos_comida,
        "confiabilidad_cubiertos_sin_comida": confiabilidad_cubiertos_sin_comida,
        "confiabilidad_facturacion_cubierto_total": confiabilidad_facturacion_cubierto_total,
        "confiabilidad_facturacion_cubierto_comida": confiabilidad_facturacion_cubierto_comida,
        "confiabilidad_facturacion_cubierto_sin_comida": confiabilidad_facturacion_cubierto_sin_comida,
    }


def _calcular_distribucion_cubiertos_por_ticket(df_tickets_filtrado, df_consumos):
    """Cuenta cuantos tickets (mesas) tienen 1, 2, 3... cubiertos.

    Retorna un DataFrame con columnas 'Cubiertos' (int), 'Cantidad de tickets' y
    'Cubiertos_Label' (texto para el eje del grafico), ordenado de menor a mayor
    cantidad de cubiertos. Los valores de cubiertos por encima de 10 se agrupan en
    una categoria "10+" para mantener el grafico legible. Los tickets sin cubiertos
    registrados (0, es decir sin lineas de la familia CUBIERTOS) se excluyen, ya que
    no representan una mesa con cubiertos conocidos.
    """
    columnas_necesarias = {"Numero", "Importe"}
    if df_tickets_filtrado.empty or not columnas_necesarias.issubset(df_tickets_filtrado.columns):
        return pd.DataFrame(columns=['Cubiertos', 'Cantidad de tickets', 'Cubiertos_Label'])

    df_base = df_tickets_filtrado.copy()
    if "Cantidad" not in df_base.columns:
        df_base["Cantidad"] = 1

    df_base["Numero"] = df_base["Numero"].astype(str).str.strip()
    df_base = df_base[df_base["Numero"].ne("")].copy()
    if df_base.empty:
        return pd.DataFrame(columns=['Cubiertos', 'Cantidad de tickets', 'Cubiertos_Label'])

    df_base["Cantidad"] = pd.to_numeric(df_base["Cantidad"], errors="coerce").fillna(0)

    df_con_familia = _agregar_familia(df_base, df_consumos)
    familia_col = "Familia" if "Familia" in df_con_familia.columns else None
    if familia_col is None:
        return pd.DataFrame(columns=['Cubiertos', 'Cantidad de tickets', 'Cubiertos_Label'])

    familias_cubiertos = {"cubiertos", "cibiertos"}
    mask_cubiertos = df_con_familia[familia_col].map(_normalizar_familia).isin(familias_cubiertos)

    cubiertos_por_ticket = df_con_familia.loc[mask_cubiertos].groupby("Numero", dropna=False)["Cantidad"].sum()
    cubiertos_por_ticket = cubiertos_por_ticket[cubiertos_por_ticket > 0]

    if cubiertos_por_ticket.empty:
        return pd.DataFrame(columns=['Cubiertos', 'Cantidad de tickets', 'Cubiertos_Label'])

    cubiertos_enteros = cubiertos_por_ticket.round().astype(int)

    tope_cubiertos = 10
    cubiertos_bucket = cubiertos_enteros.clip(upper=tope_cubiertos)

    distribucion = cubiertos_bucket.value_counts().reset_index()
    distribucion.columns = ['Cubiertos', 'Cantidad de tickets']
    distribucion['Cubiertos_Label'] = distribucion['Cubiertos'].apply(
        lambda v: f"{tope_cubiertos}+" if v == tope_cubiertos else str(v)
    )
    distribucion = distribucion.sort_values('Cubiertos').reset_index(drop=True)
    return distribucion


# Configuracion de la pagina
st.set_page_config(
    page_title="DataKinga Dashboard",
    page_icon="DK",
    layout="wide",
    initial_sidebar_state="expanded"
)

_apply_dark_mode()

# Titulo principal
st.title("DataKinga Dashboard")
st.markdown("-------------")

# Cargar datos
SUCURSAL_ALIASES = {
    'PASADENA': 'Pasadena',
    'COSTAVERDE': 'Costa Verde',
    'COSTA VERDE': 'Costa Verde',
    'JUNIN': 'Junin',
    'ENTRE RIOS': 'Entre Rios',
    'ENTRERIOS': 'Entre Rios',
    'DRAGO': 'Drago',
    'SAAVEDRA': 'Saavedra',
    'SAENZ PENA': 'Saenz Pena',
}

def _normalizar_sucursal(nombre):
    if pd.isna(nombre):
        return nombre
    return SUCURSAL_ALIASES.get(str(nombre).strip().upper(), str(nombre).strip().title())

@st.cache_data(ttl=60)
def cargar_datos():
    try:
        client = get_client()
        df_tickets = fetch_tickets(client)
        df_consumos = fetch_consumos(client)
        if 'Cantidad' in df_tickets.columns:
            df_tickets['Cantidad'] = pd.to_numeric(df_tickets['Cantidad'], errors='coerce')
        if 'Importe' in df_tickets.columns:
            df_tickets['Importe'] = pd.to_numeric(df_tickets['Importe'], errors='coerce')
        if 'Sucursal' in df_tickets.columns:
            df_tickets['Sucursal'] = df_tickets['Sucursal'].apply(_normalizar_sucursal)
        if 'Sucursal' in df_consumos.columns:
            df_consumos['Sucursal'] = df_consumos['Sucursal'].apply(_normalizar_sucursal)
        # Normalize accented column names to plain ASCII
        import unicodedata as _ud
        _col_map = {c: ''.join(x for x in _ud.normalize('NFD', c) if _ud.category(x) != 'Mn') for c in df_tickets.columns if any(ord(x) > 127 for x in c)}
        if _col_map:
            df_tickets = df_tickets.rename(columns=_col_map)
        return df_tickets, df_consumos
    except Exception as e:
        st.error(f'Error al cargar datos desde Supabase: {str(e)}')
        st.info('Verifica que SUPABASE_URL y SUPABASE_KEY esten configurados.')
        st.stop()


df_tickets, df_consumos = cargar_datos()

# Sidebar - Filtros globales
st.sidebar.header("Filtros")

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
        st.sidebar.error("No hay sucursales disponibles")
        df_tickets_filtrado = df_tickets
else:
    st.sidebar.error("No hay columna Sucursal")
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
    st.sidebar.warning("No hay columna Fecha")

# Filtro por turno (desplegable con opcion Todos)
if 'Turno' in df_tickets_filtrado.columns:
    turnos_disponibles = sorted(df_tickets_filtrado['Turno'].dropna().unique().tolist())
    if len(turnos_disponibles) > 0:
        # Agregar opcion "Todos" al inicio
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

# sltima actualizacion (pequeno, debajo del filtro de turno)
st.sidebar.markdown("-------------")
last_run_time = os.getenv('LAST_RUN_TIME', '')
last_run_status = os.getenv('LAST_RUN_STATUS', '')

if last_run_time:
    status_icon = "OK" if last_run_status == "SUCCESS" else "X"
    st.sidebar.caption(f"Ultima actualizacion: {last_run_time} {status_icon}")

st.sidebar.markdown(
    """
    <style>
    .st-key-btn_force_update button {
        color: black !important;
    }
    .st-key-btn_force_update button p {
        color: black !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if st.sidebar.button("Actualizar datos ahora", key="btn_force_update", help="Ejecuta una extraccion manual y actualiza la base de datos"):
    with st.spinner("Actualizando datos... esto puede tardar unos minutos"):
        resultado_update = run_extraction()

    if resultado_update["success"]:
        st.sidebar.success(resultado_update["message"])
        if resultado_update["errors"]:
            for error_msg in resultado_update["errors"]:
                st.sidebar.warning(error_msg)
        st.session_state.pop("fecha_desde_2", None)
        st.session_state.pop("fecha_hasta_2", None)
        st.session_state.pop("resumen_dia_fecha", None)
        cargar_datos.clear()
        st.rerun()
    else:
        st.sidebar.error(resultado_update["message"])
        if resultado_update["errors"]:
            for error_msg in resultado_update["errors"]:
                st.sidebar.warning(error_msg)

# Menu de navegacion
st.sidebar.markdown("-------------")
st.sidebar.header("Menu")

# UN SOLO radio button con todas las opciones y separadores
opciones_menu = [
    "Resumen del dia",
    "Facturacion",
    "Analisis por Familia",
    "-------------",
    "Buscador de Productos en Tickets",
    "-------------",
    "Ranking de productos",
    "Productos mas vendidos",
    "Productos menos vendidos",
    "Productos mejor facturacion",
    "Productos peor facturacion",
    "-------------",
    "Relaciones por producto",
    "Relaciones por familia",
    "-------------",
    "Creacion de Combos",
    "-------------",
    "Analisis de tickets",
    "Negocio sin regalos",
    "Analisis de regalos"
]

# Inicializar session_state si no existe
if 'menu_seleccion' not in st.session_state:
    st.session_state.menu_seleccion = "Facturacion"

# Encontrar el indice de la seleccion actual
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

# Si se selecciona un separador, mantener la ultima seleccion valida
if menu_opcion_temp.startswith("-"):
    menu_opcion = st.session_state.menu_seleccion
else:
    menu_opcion = menu_opcion_temp
    st.session_state.menu_seleccion = menu_opcion

# ========== VISTA: RESUMEN DEL DIA ==========
if menu_opcion == "Resumen del dia":
    st.header("Resumen del dia")

    df_sucursal_completo = df_tickets[df_tickets['Sucursal'] == sucursal_seleccionada].copy() if 'Sucursal' in df_tickets.columns else df_tickets.copy()

    if 'Fecha' in df_sucursal_completo.columns and not df_sucursal_completo.empty:
        df_sucursal_completo['Fecha_dt'] = pd.to_datetime(df_sucursal_completo['Fecha'])
        fecha_min_dia = df_sucursal_completo['Fecha_dt'].min().date()
        fecha_max_dia = df_sucursal_completo['Fecha_dt'].max().date()

        if "resumen_dia_fecha" in st.session_state:
            valor_previo = st.session_state["resumen_dia_fecha"]
            if valor_previo < fecha_min_dia or valor_previo > fecha_max_dia:
                st.session_state["resumen_dia_fecha"] = fecha_max_dia

        dia_seleccionado = st.date_input(
            "Dia a mostrar",
            value=fecha_max_dia,
            min_value=fecha_min_dia,
            max_value=fecha_max_dia,
            key="resumen_dia_fecha"
        )

        df_dia = df_sucursal_completo[df_sucursal_completo['Fecha_dt'].dt.date == dia_seleccionado].copy()
        st.caption(f"Mostrando datos del dia {dia_seleccionado.strftime('%d/%m/%Y')} para {sucursal_seleccionada}. Este resumen ignora el filtro de rango de fechas y turno del panel lateral (usa el selector de dia de arriba).")
    else:
        df_dia = df_sucursal_completo.copy()
        st.warning("No hay datos de fecha disponibles para esta sucursal.")

    if df_dia.empty:
        st.warning("No hay datos disponibles para el ultimo dia.")
    else:
        # --- Grafico de torta: Facturacion por turno ---
        st.subheader("Facturacion por Turno")
        if 'Turno' in df_dia.columns and 'Cantidad' in df_dia.columns and 'Importe' in df_dia.columns:
            df_dia_turno = df_dia.copy()
            df_dia_turno['Importe_Total'] = df_dia_turno['Cantidad'] * df_dia_turno['Importe']

            facturacion_turno = df_dia_turno.groupby('Turno')['Importe_Total'].sum().reset_index()
            facturacion_turno = facturacion_turno.rename(columns={'Importe_Total': 'Importe'})
            facturacion_turno = facturacion_turno.sort_values('Importe', ascending=False)

            total_dia = facturacion_turno['Importe'].sum()
            facturacion_turno['Porcentaje'] = (facturacion_turno['Importe'] / total_dia * 100).round(2)

            facturacion_turno['Turno_Label'] = facturacion_turno.apply(
                lambda row: f"{row['Turno']} ({row['Porcentaje']:.1f}%)", axis=1
            )
            facturacion_turno['Slice_Label'] = facturacion_turno.apply(
                lambda row: f"{row['Turno']}<br>${row['Importe']:,.2f}", axis=1
            )

            fig_torta_turno = px.pie(
                facturacion_turno,
                values='Importe',
                names='Turno_Label',
                title='Distribucion de Facturacion por Turno',
                hole=0.4,
                custom_data=['Turno']
            )
            fig_torta_turno.update_traces(
                textposition='inside',
                text=facturacion_turno['Slice_Label'],
                hovertemplate='<b>%{customdata[0]}</b><br>Facturacion: $%{value:,.2f}<extra></extra>'
            )
            st.plotly_chart(fig_torta_turno, use_container_width=True)

            st.metric("Facturacion Total del Dia", f"${total_dia:,.2f}")

            tabla_turno = facturacion_turno[['Turno', 'Importe', 'Porcentaje']].copy()
            tabla_turno = tabla_turno.rename(
                columns={'Importe': 'Facturacion ($)', 'Porcentaje': '% del Total'}
            )
            st.dataframe(
                _format_table(
                    tabla_turno,
                    currency_cols=['Facturacion ($)'],
                    percent_cols=['% del Total']
                ),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.warning("No hay datos de facturacion por turno disponibles")

        st.markdown("-------------")

        # --- Grafico de torta: Facturacion por familia ---
        st.subheader("Facturacion por Familia")
        if 'Codigo' in df_dia.columns and 'Importe' in df_dia.columns:
            df_dia_temp = df_dia.copy()
            df_consumos_temp = df_consumos.copy()
            df_con_familia = _agregar_familia(df_dia_temp, df_consumos_temp)

            df_con_familia = df_con_familia.dropna(subset=['Familia'])
            df_con_familia['Importe_Total'] = df_con_familia['Cantidad'] * df_con_familia['Importe']

            facturacion_familia_dia = df_con_familia.groupby('Familia')['Importe_Total'].sum().reset_index()
            facturacion_familia_dia = facturacion_familia_dia.rename(columns={'Importe_Total': 'Importe'})
            facturacion_familia_dia = facturacion_familia_dia.sort_values('Importe', ascending=False)

            total_familia_dia = facturacion_familia_dia['Importe'].sum()
            facturacion_familia_dia['Porcentaje'] = (facturacion_familia_dia['Importe'] / total_familia_dia * 100).round(2)

            facturacion_familia_dia['Familia_Label'] = facturacion_familia_dia.apply(
                lambda row: f"{row['Familia']} ({row['Porcentaje']:.1f}%)", axis=1
            )

            fig_torta_familia_dia = px.pie(
                facturacion_familia_dia,
                values='Importe',
                names='Familia_Label',
                title='Distribucion de Facturacion por Familia',
                hole=0.4,
                custom_data=['Familia']
            )
            fig_torta_familia_dia.update_traces(
                textposition='inside',
                text=facturacion_familia_dia['Familia'],
                hovertemplate='<b>%{customdata[0]}</b><br>Facturacion: $%{value:,.2f}<extra></extra>'
            )
            st.plotly_chart(fig_torta_familia_dia, use_container_width=True)

            tabla_familia_dia = facturacion_familia_dia[['Familia', 'Importe', 'Porcentaje']].copy()
            tabla_familia_dia = tabla_familia_dia.rename(
                columns={'Importe': 'Facturacion ($)', 'Porcentaje': '% del Total'}
            )
            st.dataframe(
                _format_table(
                    tabla_familia_dia,
                    currency_cols=['Facturacion ($)'],
                    percent_cols=['% del Total']
                ),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.warning("No hay datos de codigo para vincular con familias")

        st.markdown("-------------")

        # --- Ranking: Top 15 productos mas vendidos (cantidad) ---
        st.subheader("Top 15 Productos Mas Vendidos (Cantidad)")
        if 'Descripcion' in df_dia.columns and 'Cantidad' in df_dia.columns:
            top_cantidad_dia = df_dia.groupby('Descripcion')['Cantidad'].sum().reset_index()
            top_cantidad_dia = top_cantidad_dia.sort_values('Cantidad', ascending=False).head(15)

            col1, col2 = st.columns([2, 1])

            with col1:
                fig_top_cantidad_dia = px.bar(
                    top_cantidad_dia,
                    x='Cantidad',
                    y='Descripcion',
                    orientation='h',
                    title='Top 15 Productos Mas Vendidos',
                    color='Cantidad',
                    color_continuous_scale='Viridis'
                )
                st.plotly_chart(fig_top_cantidad_dia, use_container_width=True)

            with col2:
                st.dataframe(
                    top_cantidad_dia,
                    use_container_width=True,
                    hide_index=True
                )
        else:
            st.warning("No hay columna Descripcion en los datos")

        st.markdown("-------------")

        # --- Ranking: Top 15 productos por facturacion ---
        st.subheader("Top 15 Productos con Mayor Facturacion")
        if 'Descripcion' in df_dia.columns and 'Importe' in df_dia.columns and 'Cantidad' in df_dia.columns:
            df_temp_dia = df_dia.copy()
            df_temp_dia['Importe_Total'] = df_temp_dia['Cantidad'] * df_temp_dia['Importe']

            top_facturacion_dia = df_temp_dia.groupby('Descripcion').agg({
                'Cantidad': 'sum',
                'Importe_Total': 'sum'
            }).reset_index()
            top_facturacion_dia = top_facturacion_dia.rename(columns={'Importe_Total': 'Importe'})
            top_facturacion_dia = top_facturacion_dia.sort_values('Importe', ascending=False).head(15)

            col1, col2 = st.columns([2, 1])

            with col1:
                fig_top_facturacion_dia = px.bar(
                    top_facturacion_dia,
                    x='Importe',
                    y='Descripcion',
                    orientation='h',
                    title='Top 15 Productos por Ingresos',
                    color='Importe',
                    color_continuous_scale='Oranges'
                )
                st.plotly_chart(fig_top_facturacion_dia, use_container_width=True)

            with col2:
                st.dataframe(
                    top_facturacion_dia.rename(columns={'Importe': 'Facturacion Total ($)'}),
                    use_container_width=True,
                    hide_index=True
                )
        else:
            st.warning("No hay columna Descripcion en los datos")

        st.markdown("-------------")

        # --- Analisis de tickets del dia ---
        st.subheader("Analisis de Tickets del Dia")
        st.caption(
            "Pasadena: se considera 'comida' a los tickets que incluyen productos de las familias "
            "COCINA, PLATO DEL DIA, COMIDA(S) o ENSALADAS."
        )
        st.caption(
            "Junin: se considera 'comida' a los tickets que incluyen productos de las familias "
            "ALMUERZO o ENSALADAS (Junin no usa COCINA ni PLATO DEL DIA; agrupa sus platos principales "
            "bajo la familia ALMUERZO)."
        )
        st.markdown("Calcula ticket promedio total, ticket promedio de comida y ticket promedio sin comida.")

        metricas_tickets = _calcular_metricas_tickets(df_dia, df_consumos)

        col1, col2, col3 = st.columns(3)
        with col1:
            _metric_con_confiabilidad("Ticket promedio total", f"${metricas_tickets['ticket_promedio_total']:,.2f}", metricas_tickets['confiabilidad_ticket_total']['confiabilidad_pct'])
        with col2:
            _metric_con_confiabilidad("Ticket promedio comida", f"${metricas_tickets['ticket_promedio_comida']:,.2f}", metricas_tickets['confiabilidad_ticket_comida']['confiabilidad_pct'])
        with col3:
            _metric_con_confiabilidad("Ticket promedio sin comida", f"${metricas_tickets['ticket_promedio_sin_comida']:,.2f}", metricas_tickets['confiabilidad_ticket_sin_comida']['confiabilidad_pct'])

        st.markdown("-------------")

        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Tickets totales", f"{metricas_tickets['total_tickets']:,}")
        with c2:
            st.metric("Tickets con comida", f"{metricas_tickets['tickets_comida']:,}")
        with c3:
            st.metric("Tickets sin comida", f"{metricas_tickets['tickets_sin_comida']:,}")

        st.markdown("-------------")

        st.header("Analisis por cubiertos")
        st.markdown("Calcula facturacion por cubierto total, de comida y sin comida.")

        f1, f2, f3 = st.columns(3)
        with f1:
            _metric_con_confiabilidad("Facturacion por cubierto total", f"${metricas_tickets['facturacion_por_cubierto_total']:,.2f}", metricas_tickets['confiabilidad_facturacion_cubierto_total']['confiabilidad_pct'])
        with f2:
            _metric_con_confiabilidad("Facturacion por cubierto (comida)", f"${metricas_tickets['facturacion_por_cubierto_comida']:,.2f}", metricas_tickets['confiabilidad_facturacion_cubierto_comida']['confiabilidad_pct'])
        with f3:
            _metric_con_confiabilidad("Facturacion por cubierto (sin comida)", f"${metricas_tickets['facturacion_por_cubierto_sin_comida']:,.2f}", metricas_tickets['confiabilidad_facturacion_cubierto_sin_comida']['confiabilidad_pct'])

        st.markdown("-------------")

        g1, g2, g3 = st.columns(3)
        with g1:
            st.metric("Cubiertos totales", f"{metricas_tickets['cubiertos_total']:,.0f}")
        with g2:
            st.metric("Cubiertos (comida)", f"{metricas_tickets['cubiertos_comida']:,.0f}")
        with g3:
            st.metric("Cubiertos (sin comida)", f"{metricas_tickets['cubiertos_sin_comida']:,.0f}")

        st.markdown("-------------")

        st.subheader("Cubiertos con y sin comida")
        cubiertos_comida_val = metricas_tickets['cubiertos_comida']
        cubiertos_sin_comida_val = metricas_tickets['cubiertos_sin_comida']
        cubiertos_pie_total = cubiertos_comida_val + cubiertos_sin_comida_val
        if cubiertos_pie_total > 0:
            df_cubiertos_pie = pd.DataFrame({
                'Categoria': ['Con comida', 'Sin comida'],
                'Cubiertos': [cubiertos_comida_val, cubiertos_sin_comida_val]
            })
            df_cubiertos_pie['Porcentaje'] = (df_cubiertos_pie['Cubiertos'] / cubiertos_pie_total * 100).round(2)
            df_cubiertos_pie['Categoria_Label'] = df_cubiertos_pie.apply(
                lambda row: f"{row['Categoria']} ({row['Porcentaje']:.1f}%)", axis=1
            )
            df_cubiertos_pie['Slice_Label'] = df_cubiertos_pie.apply(
                lambda row: f"{row['Categoria']}<br>{row['Cubiertos']:,.0f}", axis=1
            )

            fig_torta_cubiertos = px.pie(
                df_cubiertos_pie,
                values='Cubiertos',
                names='Categoria_Label',
                title='Distribucion de Cubiertos (con y sin comida)',
                hole=0.4,
                custom_data=['Categoria'],
                color_discrete_sequence=['#58D68D', '#EC7063']
            )
            fig_torta_cubiertos.update_traces(
                textposition='inside',
                text=df_cubiertos_pie['Slice_Label'],
                hovertemplate='<b>%{customdata[0]}</b><br>Cubiertos: %{value:,.0f}<extra></extra>'
            )
            st.plotly_chart(fig_torta_cubiertos, use_container_width=True)
        else:
            st.info("No hay datos de cubiertos para graficar.")

        st.markdown("-------------")

        st.subheader("Cubiertos promedio y mediana por ticket")

        h1, h2, h3 = st.columns(3)
        with h1:
            _metric_con_confiabilidad("Cubiertos promedio (total)", f"{metricas_tickets['cubiertos_promedio_total']:,.2f}", metricas_tickets['confiabilidad_cubiertos_total']['confiabilidad_pct'])
        with h2:
            _metric_con_confiabilidad("Cubiertos promedio (comida)", f"{metricas_tickets['cubiertos_promedio_comida']:,.2f}", metricas_tickets['confiabilidad_cubiertos_comida']['confiabilidad_pct'])
        with h3:
            _metric_con_confiabilidad("Cubiertos promedio (sin comida)", f"{metricas_tickets['cubiertos_promedio_sin_comida']:,.2f}", metricas_tickets['confiabilidad_cubiertos_sin_comida']['confiabilidad_pct'])

        i1, i2, i3 = st.columns(3)
        with i1:
            st.metric("Cubiertos mediana (total)", f"{metricas_tickets['cubiertos_mediana_total']:,.2f}")
        with i2:
            st.metric("Cubiertos mediana (comida)", f"{metricas_tickets['cubiertos_mediana_comida']:,.2f}")
        with i3:
            st.metric("Cubiertos mediana (sin comida)", f"{metricas_tickets['cubiertos_mediana_sin_comida']:,.2f}")

        st.markdown("-------------")
        st.subheader("Numero de cubiertos por ticket (mesa)")
        st.caption("Cantidad de tickets (mesas) segun la cantidad de cubiertos que tienen. Solo se incluyen tickets con cubiertos registrados (mayor a 0). Los valores de 10 cubiertos o mas se agrupan en la categoria '10+'.")

        df_distribucion_cubiertos = _calcular_distribucion_cubiertos_por_ticket(df_dia, df_consumos)

        if df_distribucion_cubiertos.empty:
            st.info("No hay datos de cubiertos para graficar.")
        else:
            fig_distribucion_cubiertos = px.bar(
                df_distribucion_cubiertos,
                x='Cubiertos_Label',
                y='Cantidad de tickets',
                title='Numero de Cubiertos por Ticket (Mesa)',
                labels={'Cubiertos_Label': 'Cantidad de cubiertos', 'Cantidad de tickets': 'Cantidad de tickets'},
                color='Cantidad de tickets',
                color_continuous_scale='Blues',
                text='Cantidad de tickets'
            )
            fig_distribucion_cubiertos.update_traces(textposition='outside')
            fig_distribucion_cubiertos.update_layout(xaxis_type='category', showlegend=False)
            st.plotly_chart(fig_distribucion_cubiertos, use_container_width=True)

            st.dataframe(
                df_distribucion_cubiertos[['Cubiertos_Label', 'Cantidad de tickets']].rename(columns={'Cubiertos_Label': 'Cubiertos'}),
                use_container_width=True,
                hide_index=True
            )

        st.caption(
            "Confiabilidad de cada promedio: verde = confiable (>=90%), amarillo = medio confiable (70-89.9%), "
            "rojo = no confiable (<70%). Confiabilidad = 100 x (1 - margen de error al 95% / promedio)."
        )

        st.caption(
            "Regla aplicada: un ticket es 'con comida' si contiene al menos un producto de las familias de comida "
            "de su sucursal (ver detalle por local abajo). Facturacion comida = suma de las lineas de esas familias "
            "(no el total del ticket). Ticket promedio comida = facturacion comida / cantidad de tickets con comida. "
            "Ticket promedio sin comida = facturacion de las demas lineas / cantidad de tickets sin comida. "
            "Cubiertos = suma de la cantidad de la familia CUBIERTOS agrupada por ticket (una o mas lineas por ticket), "
            "clasificada segun si el ticket es con, sin comida, o el total general. Facturacion por cubierto = "
            "facturacion de la clase / cubiertos de esa clase. Promedio y mediana de cubiertos se calculan sobre la "
            "cantidad de cubiertos por ticket dentro de cada categoria."
        )

# ========== VISTA: FACTURACION ==========
elif menu_opcion == "Facturacion":
    st.header("Facturacion")
    
    # Calcular metricas del periodo
    if 'Importe' in df_tickets_filtrado.columns and 'Cantidad' in df_tickets_filtrado.columns:
        # Facturacion total del periodo
        df_temp_metricas = df_tickets_filtrado.copy()
        df_temp_metricas['Importe_Total'] = df_temp_metricas['Cantidad'] * df_temp_metricas['Importe']
        facturacion_total_periodo = df_temp_metricas['Importe_Total'].sum()
        
        # Cantidad de dias facturados (dias con al menos una venta)
        if 'Fecha' in df_tickets_filtrado.columns:
            dias_facturados = df_tickets_filtrado['Fecha'].nunique()
        else:
            dias_facturados = 0
        
        # Mostrar metricas
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Facturacion Total del Periodo", f"${facturacion_total_periodo:,.2f}")
        with col2:
            st.metric("Cantidad de Dias Facturados", f"{dias_facturados}")
        
        st.markdown("-------------")
    
    # Grafico de barras: Facturacion por dia
    st.subheader("Facturacion Diaria")
    if 'Fecha' in df_tickets_filtrado.columns and 'Importe' in df_tickets_filtrado.columns:
        if 'Turno' in df_tickets_filtrado.columns:
            # Calcular importe total (Cantidad * Importe unitario)
            df_temp = df_tickets_filtrado.copy()
            df_temp['Importe_Total'] = df_temp['Cantidad'] * df_temp['Importe']
            # Facturacion por dia y turno (barras apiladas)
            facturacion_diaria_turno = df_temp.groupby(['Fecha', 'Turno'])['Importe_Total'].sum().reset_index()
            facturacion_diaria_turno = facturacion_diaria_turno.rename(columns={'Importe_Total': 'Importe'})
            facturacion_diaria_turno['Fecha'] = pd.to_datetime(facturacion_diaria_turno['Fecha'])
            facturacion_diaria_turno = facturacion_diaria_turno.sort_values('Fecha')
            
            # Crear rango completo de fechas (incluyendo dias faltantes)
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
            
            # Crear etiquetas de fecha con dia de la semana en espanol
            dias_semana = {
                'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'Miercoles',
                'Thursday': 'Jueves', 'Friday': 'Viernes', 'Saturday': 'Sabado', 'Sunday': 'Domingo'
            }
            facturacion_diaria_turno['Fecha_Label'] = facturacion_diaria_turno['Fecha'].apply(
                lambda x: f"{dias_semana[x.strftime('%A')]}<br>{x.day}/{x.month}"
            )
            
            # Funcion para formatear valores con k y M
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
                title='Facturacion Total por Dia (por Turno)',
                labels={'Importe': 'Facturacion ($)', 'Fecha_Label': 'Dia y Fecha', 'Turno': 'Turno'},
                barmode='stack',
                color_discrete_map=color_map,
                text='Texto'
            )

            total_por_dia = facturacion_diaria_turno.groupby('Fecha_Label', as_index=False)['Importe'].sum()
            total_por_dia['Total_Label'] = total_por_dia['Importe'].apply(
                lambda v: f"${v:,.0f}" if v < 1000 else f"${v/1000:.1f}k" if v < 1000000 else f"${v/1000000:.1f}M"
            )
            fig_barras.add_trace(
                go.Scatter(
                    x=total_por_dia['Fecha_Label'],
                    y=total_por_dia['Importe'],
                    mode='text',
                    text=total_por_dia['Total_Label'],
                    textposition='top center',
                    textfont=dict(color='#1C2833', size=12, family='Arial', weight='bold'),
                    showlegend=False,
                    hoverinfo='skip'
                )
            )
            
            # Configurar el texto dentro de las barras (horizontal, numeros oscuros)
            fig_barras.update_traces(
                selector=dict(type='bar'),
                textposition='inside',
                textfont=dict(color='#1C2833', size=11, family='Arial', weight='bold')
            )
        else:
            # Calcular importe total (Cantidad * Importe unitario)
            df_temp = df_tickets_filtrado.copy()
            df_temp['Importe_Total'] = df_temp['Cantidad'] * df_temp['Importe']
            # Facturacion sin turno
            facturacion_diaria = df_temp.groupby('Fecha')['Importe_Total'].sum().reset_index()
            facturacion_diaria = facturacion_diaria.rename(columns={'Importe_Total': 'Importe'})
            facturacion_diaria['Fecha'] = pd.to_datetime(facturacion_diaria['Fecha'])
            facturacion_diaria = facturacion_diaria.sort_values('Fecha')
            
            # Crear rango completo de fechas (incluyendo dias faltantes)
            fecha_min = facturacion_diaria['Fecha'].min()
            fecha_max = facturacion_diaria['Fecha'].max()
            todas_fechas = pd.date_range(start=fecha_min, end=fecha_max, freq='D')
            
            # Reindexar con todas las fechas
            facturacion_diaria = facturacion_diaria.set_index('Fecha').reindex(todas_fechas).reset_index()
            facturacion_diaria = facturacion_diaria.rename(columns={'index': 'Fecha'})
            facturacion_diaria['Importe'] = facturacion_diaria['Importe'].fillna(0)
            
            # Crear etiquetas de fecha con dia de la semana en espanol
            dias_semana = {
                'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'Miercoles',
                'Thursday': 'Jueves', 'Friday': 'Viernes', 'Saturday': 'Sabado', 'Sunday': 'Domingo'
            }
            facturacion_diaria['Fecha_Label'] = facturacion_diaria['Fecha'].apply(
                lambda x: f"{dias_semana[x.strftime('%A')]}<br>{x.day}/{x.month}"
            )
            
            # Funcion para formatear valores con k y M
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
                title='Facturacion Total por Dia',
                labels={'Importe': 'Facturacion ($)', 'Fecha_Label': 'Dia y Fecha'},
                text='Texto'
            )

            total_por_dia = facturacion_diaria[['Fecha_Label', 'Importe']].copy()
            total_por_dia['Total_Label'] = total_por_dia['Importe'].apply(
                lambda v: f"${v:,.0f}" if v < 1000 else f"${v/1000:.1f}k" if v < 1000000 else f"${v/1000000:.1f}M"
            )
            fig_barras.add_trace(
                go.Scatter(
                    x=total_por_dia['Fecha_Label'],
                    y=total_por_dia['Importe'],
                    mode='text',
                    text=total_por_dia['Total_Label'],
                    textposition='top center',
                    textfont=dict(color='#1C2833', size=12, family='Arial', weight='bold'),
                    showlegend=False,
                    hoverinfo='skip'
                )
            )
            
            # Configurar colores modernos y texto oscuro dentro de las barras (horizontal)
            fig_barras.update_traces(
                selector=dict(type='bar'),
                marker_color='#5DADE2',
                textposition='inside',
                textfont=dict(color='#1C2833', size=11, family='Arial', weight='bold')
            )
        
        fig_barras.update_layout(
            showlegend=True,
            xaxis_title='Dia y Fecha'
        )
        st.plotly_chart(fig_barras, use_container_width=True)
    else:
        st.warning("No hay datos de facturacion disponibles")
    
    st.markdown("-------------")
    
    # Grafico de torta: % de facturacion por familia
    st.subheader("Facturacion por Familia")
    if 'Codigo' in df_tickets_filtrado.columns and 'Importe' in df_tickets_filtrado.columns:
        df_tickets_temp = df_tickets_filtrado.copy()
        df_consumos_temp = df_consumos.copy()
        df_con_familia = _agregar_familia(df_tickets_temp, df_consumos_temp)
        
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
            title='Distribucion de Facturacion por Familia',
            hole=0.4,
            custom_data=['Familia']
        )
        fig_torta.update_traces(
            textposition='inside',
            text=facturacion_familia['Familia'],
            hovertemplate='<b>%{customdata[0]}</b><br>Facturacion: $%{value:,.2f}<extra></extra>'
        )
        st.plotly_chart(fig_torta, use_container_width=True)
        
        # Mostrar tabla de resumen con formato
        tabla_familia = facturacion_familia[['Familia', 'Importe', 'Porcentaje']].copy()
        tabla_familia = tabla_familia.rename(
            columns={'Importe': 'Facturacion ($)', 'Porcentaje': '% del Total'}
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
            _format_table(
                tabla_familia,
                currency_cols=['Facturacion ($)'],
                percent_cols=['% del Total']
            ),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.warning("No hay datos de codigo para vincular con familias")

# ========== VISTA: BUSCADOR DE PRODUCTOS EN TICKETS ==========
elif menu_opcion == "Buscador de Productos en Tickets":
    st.header("Buscador de Productos en Tickets")
    st.markdown("Busca un producto y visualiza todos los tickets donde aparece, junto con los demas productos de cada ticket.")
    
    # Verificar que tenemos las columnas necesarias
    if 'Descripcion' not in df_tickets_filtrado.columns or 'Numero' not in df_tickets_filtrado.columns:
        st.error("Faltan columnas necesarias (Descripcion o Numero) en los datos")
    else:
        # Selector de producto
        productos_disponibles = sorted(df_tickets_filtrado['Descripcion'].dropna().unique().tolist())
        
        if len(productos_disponibles) == 0:
            st.warning("No hay productos disponibles en el periodo seleccionado")
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
            
            st.markdown("-------------")
            
            # Buscar todos los tickets que contienen el producto seleccionado
            tickets_con_producto = df_tickets_filtrado[
                df_tickets_filtrado['Descripcion'] == producto_seleccionado
            ]['Numero'].unique()
            
            if len(tickets_con_producto) == 0:
                st.info(f"No se encontraron tickets con el producto '{producto_seleccionado}'")
            else:
                # Filtrar todos los datos de esos tickets
                df_tickets_completos = df_tickets_filtrado[
                    df_tickets_filtrado['Numero'].isin(tickets_con_producto)
                ].copy()
                
                # Calcular estadisticas
                total_tickets = len(tickets_con_producto)
                total_items_producto = df_tickets_filtrado[
                    df_tickets_filtrado['Descripcion'] == producto_seleccionado
                ]['Cantidad'].sum()
                
                # Calcular facturacion del producto
                if 'Importe' in df_tickets_filtrado.columns and 'Cantidad' in df_tickets_filtrado.columns:
                    df_producto = df_tickets_filtrado[df_tickets_filtrado['Descripcion'] == producto_seleccionado].copy()
                    df_producto['Total'] = df_producto['Cantidad'] * df_producto['Importe']
                    facturacion_producto = df_producto['Total'].sum()
                else:
                    facturacion_producto = 0
                
                # Mostrar metricas principales
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Tickets encontrados", f"{total_tickets:,}")
                with col2:
                    st.metric("Cantidad vendida", f"{int(total_items_producto):,}")
                with col3:
                    if facturacion_producto > 0:
                        st.metric("Facturacion total", f"${facturacion_producto:,.2f}")
                
                st.markdown("-------------")
                
                # Ordenar por fecha y hora
                if 'Fecha' in df_tickets_completos.columns and 'Hora' in df_tickets_completos.columns:
                    df_tickets_completos['Fecha_dt'] = pd.to_datetime(df_tickets_completos['Fecha'])
                    df_tickets_completos['Hora_str'] = df_tickets_completos['Hora'].astype(str)
                    df_tickets_completos = df_tickets_completos.sort_values(['Fecha_dt', 'Hora_str'], ascending=[False, False])
                
                # Agrupar por ticket y mostrar
                st.subheader("Detalle de Tickets")
                
                for i, numero_ticket in enumerate(tickets_con_producto[:50]):  # Limitar a 50 tickets para rendimiento
                    df_ticket = df_tickets_completos[df_tickets_completos['Numero'] == numero_ticket].copy()
                    
                    # Informacion del ticket
                    fecha = df_ticket['Fecha'].iloc[0] if 'Fecha' in df_ticket.columns else "N/A"
                    hora = df_ticket['Hora'].iloc[0] if 'Hora' in df_ticket.columns else "N/A"
                    turno = df_ticket['Turno'].iloc[0] if 'Turno' in df_ticket.columns else "N/A"
                    
                    # Calcular total del ticket
                    if 'Importe' in df_ticket.columns and 'Cantidad' in df_ticket.columns:
                        df_ticket['Total_Item'] = df_ticket['Cantidad'] * df_ticket['Importe']
                        total_ticket = df_ticket['Total_Item'].sum()
                    else:
                        total_ticket = 0
                    
                    # Expandir con informacion del ticket
                    with st.expander(
                        f"Ticket #{numero_ticket} - {fecha} {hora} - Total: ${total_ticket:,.2f}",
                        expanded=(i < 3)  # Expandir los primeros 3
                    ):
                        # Informacion adicional
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.write(f"**Fecha:** {fecha}")
                        with col2:
                            st.write(f"**Hora:** {hora}")
                        with col3:
                            st.write(f"**° Turno:** {turno}")
                        
                        st.markdown("-------------")
                        st.write("**Productos en este ticket:**")
                        
                        # Preparar tabla de productos
                        columnas_mostrar = ['Descripcion', 'Cantidad']
                        if 'Importe' in df_ticket.columns:
                            columnas_mostrar.append('Importe')
                        if 'Total_Item' in df_ticket.columns:
                            columnas_mostrar.append('Total_Item')
                        
                        df_display = df_ticket[columnas_mostrar].copy()
                        
                        # Renombrar columnas para mejor presentacion
                        if 'Total_Item' in df_display.columns:
                            df_display = df_display.rename(columns={'Total_Item': 'Total'})
                        
                        # Resaltar el producto buscado
                        def highlight_producto(row):
                            if row['Descripcion'] == producto_seleccionado:
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
                
                # Mostrar aviso si hay mas tickets
                if len(tickets_con_producto) > 50:
                    st.info(f"Mostrando los primeros 50 tickets de {len(tickets_con_producto)} encontrados. Ajusta los filtros de fecha para ver menos resultados.")

# ========== VISTA: PRODUCTOS MAS VENDIDOS ==========
elif menu_opcion == "Productos mas vendidos":
    st.header("Productos mas vendidos")
    
    # Selector de cantidad de productos
    cantidad_productos = st.selectbox(
        "Cantidad de productos a mostrar",
        options=[5, 10, 15, 20, 25, 30],
        index=3,  # Por defecto 20
        key="cant_prod_1"
    )
    
    if 'Descripcion' in df_tickets_filtrado.columns:
        
        if 'Cantidad' in df_tickets_filtrado.columns:
            top_cantidad = df_tickets_filtrado.groupby('Descripcion')['Cantidad'].sum().reset_index()
            top_cantidad = top_cantidad.sort_values('Cantidad', ascending=False).head(cantidad_productos)
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                fig = px.bar(
                    top_cantidad,
                    x='Cantidad',
                    y='Descripcion',
                    orientation='h',
                    title=f'Top {cantidad_productos} Productos Mas Vendidos',
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
        st.warning("No hay columna Descripcion en los datos")

# ========== VISTA: PRODUCTOS MENOS VENDIDOS ==========
elif menu_opcion == "Productos menos vendidos":
    st.header("Productos menos vendidos")
    
    # Selector de cantidad de productos
    cantidad_productos = st.selectbox(
        "Cantidad de productos a mostrar",
        options=[5, 10, 15, 20, 25, 30],
        index=3,  # Por defecto 20
        key="cant_prod_2"
    )
    
    if 'Descripcion' in df_tickets_filtrado.columns:
        
        if 'Cantidad' in df_tickets_filtrado.columns:
            bottom_cantidad = df_tickets_filtrado.groupby('Descripcion')['Cantidad'].sum().reset_index()
            bottom_cantidad = bottom_cantidad.sort_values('Cantidad', ascending=True).head(cantidad_productos)
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                fig = px.bar(
                    bottom_cantidad,
                    x='Cantidad',
                    y='Descripcion',
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
        st.warning("No hay columna Descripcion en los datos")

# ========== VISTA: PRODUCTOS MEJOR FACTURACION ==========
elif menu_opcion == "Productos mejor facturacion":
    st.header("Productos mejor facturacion")
    
    # Selector de cantidad de productos
    cantidad_productos = st.selectbox(
        "Cantidad de productos a mostrar",
        options=[5, 10, 15, 20, 25, 30],
        index=3,  # Por defecto 20
        key="cant_prod_3"
    )
    
    if 'Descripcion' in df_tickets_filtrado.columns:
        
        if 'Importe' in df_tickets_filtrado.columns and 'Cantidad' in df_tickets_filtrado.columns:
            # Calcular importe total (Cantidad * Importe unitario)
            df_temp = df_tickets_filtrado.copy()
            df_temp['Importe_Total'] = df_temp['Cantidad'] * df_temp['Importe']
            
            top_facturacion = df_temp.groupby('Descripcion').agg({
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
                    y='Descripcion',
                    orientation='h',
                    title=f'Top {cantidad_productos} Productos por Ingresos',
                    color='Importe',
                    color_continuous_scale='Oranges'
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.dataframe(
                    top_facturacion.rename(columns={'Importe': 'Facturacion Total ($)'}),
                    use_container_width=True,
                    hide_index=True
                )
    else:
        st.warning("No hay columna Descripcion en los datos")

# ========== VISTA: PRODUCTOS PEOR FACTURACION ==========
elif menu_opcion == "Productos peor facturacion":
    st.header("Productos peor facturacion")
    
    # Selector de cantidad de productos
    cantidad_productos = st.selectbox(
        "Cantidad de productos a mostrar",
        options=[5, 10, 15, 20, 25, 30],
        index=3,  # Por defecto 20
        key="cant_prod_4"
    )
    
    if 'Descripcion' in df_tickets_filtrado.columns:
        
        if 'Importe' in df_tickets_filtrado.columns and 'Cantidad' in df_tickets_filtrado.columns:
            # Calcular importe total (Cantidad * Importe unitario)
            df_temp = df_tickets_filtrado.copy()
            df_temp['Importe_Total'] = df_temp['Cantidad'] * df_temp['Importe']
            
            bottom_facturacion = df_temp.groupby('Descripcion').agg({
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
                    y='Descripcion',
                    orientation='h',
                    title=f'Top {cantidad_productos} Productos con Menor Facturacion',
                    color='Importe',
                    color_continuous_scale='Reds_r'
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.dataframe(
                    bottom_facturacion.rename(columns={'Importe': 'Facturacion Total ($)'}),
                    use_container_width=True,
                    hide_index=True
                )
    else:
        st.warning("No hay columna Descripcion en los datos")

# ========== VISTA: RELACIONES POR PRODUCTO ==========
elif menu_opcion == "Relaciones por producto":
    st.header("Relaciones por producto")
    
    if 'Numero' in df_tickets_filtrado.columns and 'Descripcion' in df_tickets_filtrado.columns:
        
        # Analisis por Producto
        st.subheader("Analisis de Combos por Producto")
        
        # Selector de cantidad de combos para producto
        cantidad_combos_producto = st.selectbox(
            "Cantidad de combinaciones a mostrar",
            options=[5, 10, 15, 20],
            index=1,  # Por defecto 10
            key="cantidad_combos_producto"
        )
        
        productos_disponibles = sorted(df_tickets_filtrado['Descripcion'].dropna().unique().tolist())
        producto_seleccionado = st.selectbox(
            "Selecciona un producto para ver con que se vende",
            productos_disponibles,
            key="producto_combo"
        )
        
        # Checkbox para omitir productos de la misma familia
        omitir_misma_familia = st.checkbox(
            "Omitir productos de la misma familia",
            value=False,
            key="omitir_familia"
        )
        
        # Multiselect para omitir familias especificas
        if 'Descripcion' in df_tickets_filtrado.columns:
            df_temp_familias = _agregar_familia(df_tickets_filtrado.copy(), df_consumos.copy()).copy()
            df_temp_familias = df_temp_familias.dropna(subset=['Familia'])
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
                df_tickets_filtrado['Descripcion'] == producto_seleccionado
            ]['Numero'].unique()
            
            # Calcular cuantos tickets tienen SOLO este producto (solo en el ticket)
            tickets_solo = 0
            for ticket_num in tickets_con_producto:
                productos_en_ticket = df_tickets_filtrado[
                    df_tickets_filtrado['Numero'] == ticket_num
                ]['Descripcion'].nunique()
                if productos_en_ticket == 1:
                    tickets_solo += 1
            
            # Mostrar metrica de tickets solo
            col_metric1, col_metric2 = st.columns(2)
            with col_metric1:
                st.metric("Total de tickets con este producto", len(tickets_con_producto))
            with col_metric2:
                st.metric("Solo en el ticket", tickets_solo)
            
            st.markdown("-------------")
            
            # Obtener todos los productos en esos tickets (excepto el producto seleccionado)
            df_combos = df_tickets_filtrado[
                (df_tickets_filtrado['Numero'].isin(tickets_con_producto)) &
                (df_tickets_filtrado['Descripcion'] != producto_seleccionado)
            ].copy()
            
            # Si el checkbox esta marcado, filtrar por familia
            if omitir_misma_familia and 'Descripcion' in df_tickets_filtrado.columns:
                df_temp = _agregar_familia(
                    df_tickets_filtrado[df_tickets_filtrado['Descripcion'] == producto_seleccionado].copy(),
                    df_consumos.copy()
                ).copy()
                df_temp = df_temp.dropna(subset=['Familia'])
                
                if len(df_temp) > 0 and 'Familia' in df_temp.columns:
                    familia_producto = df_temp['Familia'].iloc[0]
                    df_combos = _agregar_familia(df_combos.copy(), df_consumos.copy()).copy()
                    df_combos = df_combos[df_combos['Familia'] != familia_producto]
            
            # Aplicar filtro de familias a omitir
            if len(familias_omitir) > 0 and 'Descripcion' in df_tickets_filtrado.columns:
                if 'Familia' not in df_combos.columns:
                    df_combos = _agregar_familia(df_combos.copy(), df_consumos.copy()).copy()
                
                # Filtrar productos que NO esten en las familias a omitir
                df_combos = df_combos[~df_combos['Familia'].isin(familias_omitir)]
            
            if len(df_combos) > 0:
                # Contar frecuencia de cada producto
                combos_frecuencia = df_combos.groupby('Descripcion').size().reset_index(name='Veces')
                combos_frecuencia = combos_frecuencia.sort_values('Veces', ascending=False).head(cantidad_combos_producto)
                
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    fig_combos = px.bar(
                        combos_frecuencia,
                        x='Veces',
                        y='Descripcion',
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
        st.warning("Faltan columnas necesarias para analisis de combos")

# ========== VISTA: RELACIONES POR FAMILIA ==========
elif menu_opcion == "Relaciones por familia":
    st.header("Relaciones por familia")
    
    if 'Numero' in df_tickets_filtrado.columns and 'Descripcion' in df_tickets_filtrado.columns:
        
        # Analisis por Familia
        st.subheader("Analisis de Combos por Familia")
        
        # Selector de cantidad de combos para familia
        cantidad_combos_familia = st.selectbox(
            "Cantidad de combinaciones a mostrar",
            options=[5, 10, 15, 20],
            index=1,  # Por defecto 10
            key="cantidad_combos_familia"
        )
        
        if 'Descripcion' in df_tickets_filtrado.columns:
            # Usar el matching por nombre/descripcion para obtener familia, aunque no haya codigo confiable
            df_con_familia = _agregar_familia(df_tickets_filtrado.copy(), df_consumos.copy()).copy()
            if 'Cantidad' in df_con_familia.columns:
                df_con_familia['Cantidad'] = pd.to_numeric(df_con_familia['Cantidad'], errors='coerce')
            df_con_familia = df_con_familia.dropna(subset=['Familia'])
            
            familias_disponibles = sorted(df_con_familia['Familia'].dropna().unique().tolist())
            if len(familias_disponibles) == 0:
                st.warning("No hay familias disponibles para este periodo")
            else:
                familia_combo_seleccionada = st.selectbox(
                    "Selecciona una familia para analisis de combos",
                    familias_disponibles,
                    key="familia_combo"
                )
            
            if familia_combo_seleccionada:
                # Obtener productos de la familia seleccionada
                df_familia_combo = df_con_familia[df_con_familia['Familia'] == familia_combo_seleccionada]
                
                # Encontrar top 5 mas vendidos de la familia
                top5_familia_combo = df_familia_combo.groupby('Descripcion')['Cantidad'].sum().reset_index()
                top5_familia_combo = top5_familia_combo.sort_values('Cantidad', ascending=False).head(5)
                
                st.write(f"**Top 5 Productos de {familia_combo_seleccionada}:**")
                for producto in top5_familia_combo['Descripcion'].tolist():
                    st.write(f"? {producto}")
                
                st.markdown("-------------")
                
                # Analizar combinaciones para cada producto del top 5
                st.write(f"**Combinaciones de los Top 5 de {familia_combo_seleccionada}:**")
                
                for producto in top5_familia_combo['Descripcion'].tolist():
                    with st.expander(f"Combinaciones de: {producto}"):
                        # Encontrar tickets con este producto
                        tickets_producto = df_con_familia[
                            df_con_familia['Descripcion'] == producto
                        ]['Numero'].unique()
                        
                        # Productos que aparecen en esos tickets (excepto el producto actual)
                        df_combos_familia = df_con_familia[
                            (df_con_familia['Numero'].isin(tickets_producto)) &
                            (df_con_familia['Descripcion'] != producto)
                        ]
                        
                        if len(df_combos_familia) > 0:
                            # Contar por producto (sin importar la familia)
                            combos_por_producto = df_combos_familia.groupby('Descripcion').size().reset_index(name='Veces')
                            combos_por_producto = combos_por_producto.sort_values('Veces', ascending=False).head(cantidad_combos_familia)
                            
                            col1, col2 = st.columns([2, 1])
                            
                            with col1:
                                fig = px.bar(
                                    combos_por_producto,
                                    x='Veces',
                                    y='Descripcion',
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
            st.warning("No hay datos de codigo para vincular con familias")
    else:
        st.warning("Faltan columnas necesarias para analisis de combos")

# ========== VISTA: ANLISIS POR FAMILIA ==========
elif menu_opcion == "Analisis por Familia":
    st.header("Analisis por Familia")
    
    if 'Codigo' in df_tickets_filtrado.columns and 'Importe' in df_tickets_filtrado.columns:
        df_tickets_temp = df_tickets_filtrado.copy()
        df_consumos_temp = df_consumos.copy()
        df_con_familia = _agregar_familia(df_tickets_temp, df_consumos_temp)
        
        # Grafico de torta: % de facturacion por familia (fijo)
        st.subheader("Distribucion de Facturacion por Familia")
        
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
            title='Porcentaje de Facturacion por Familia',
            hole=0.4,
            custom_data=['Familia']
        )
        fig_familia.update_traces(
            textposition='inside',
            text=facturacion_familia['Familia'],
            hovertemplate='<b>%{customdata[0]}</b><br>Facturacion: $%{value:,.2f}<extra></extra>'
        )
        st.plotly_chart(fig_familia, use_container_width=True)
        
        st.markdown("-------------")
        
        # Selector de familia
        familias_disponibles = sorted(df_con_familia['Familia'].dropna().unique().tolist())
        
        if len(familias_disponibles) > 0:
            familia_seleccionada = st.selectbox(
                "Selecciona una familia para analisis detallado",
                familias_disponibles,
                key="familia_sel"
            )
        else:
            st.warning("No hay familias disponibles para esta sucursal")
            familia_seleccionada = None
        
        if familia_seleccionada:
            df_familia = df_con_familia[df_con_familia['Familia'] == familia_seleccionada]
            
            st.subheader(f"Analisis Detallado: {familia_seleccionada}")
            
            # Grafico de torta: % de productos dentro de la familia
            st.markdown("Y Distribucion de Productos en la Familia")
            
            # Calcular importe total (Cantidad * Importe unitario)
            df_familia['Importe_Total'] = df_familia['Cantidad'] * df_familia['Importe']
            productos_familia = df_familia.groupby('Descripcion')['Importe_Total'].sum().reset_index()
            productos_familia = productos_familia.rename(columns={'Importe_Total': 'Importe'})
            total_familia = productos_familia['Importe'].sum()
            productos_familia['Porcentaje'] = (productos_familia['Importe'] / total_familia * 100).round(2)
            productos_familia = productos_familia.sort_values('Importe', ascending=False)
            
            # Crear columna con nombre y porcentaje para la leyenda
            productos_familia['Producto_Label'] = productos_familia.apply(
                lambda row: f"{row['Descripcion']} ({row['Porcentaje']:.1f}%)", axis=1
            )
            
            fig_torta_familia = px.pie(
                productos_familia,
                values='Importe',
                names='Producto_Label',
                title=f'Distribucion de Facturacion en {familia_seleccionada}',
                hole=0.4,
                custom_data=['Descripcion']
            )
            fig_torta_familia.update_traces(
                textposition='inside',
                text=productos_familia['Descripcion'],
                hovertemplate='<b>%{customdata[0]}</b><br>Facturacion: $%{value:,.2f}<extra></extra>'
            )
            st.plotly_chart(fig_torta_familia, use_container_width=True)
            
            st.markdown("-------------")
            
            # Lista completa de productos con cantidad y facturacion
            st.markdown("### Lista Completa de Productos")
            
            if 'Cantidad' in df_familia.columns:
                # Calcular importe total (Cantidad * Importe unitario)
                df_familia['Importe_Total'] = df_familia['Cantidad'] * df_familia['Importe']
                
                productos_completos = df_familia.groupby('Descripcion').agg({
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
                    st.metric("Total Facturacion", f"${total_importe_familia:,.2f}")
                
                st.markdown("")  # Espacio
                
                # Calcular porcentajes
                productos_completos['% Facturacion'] = (productos_completos['Importe_Total'] / total_importe_familia * 100).round(2)
                
                # Ordenar por facturacion descendente
                productos_completos = productos_completos.sort_values('Importe_Total', ascending=False)
                
                # Formatear valores solo en la capa visual; mantener los numeros como numeric para ordenar bien
                tabla_display = productos_completos[['Descripcion', 'Cantidad', 'Importe_Total', '% Facturacion']].copy()
                tabla_display = tabla_display.rename(
                    columns={
                        'Descripcion': 'Producto',
                        'Cantidad': 'Cantidad Vendida',
                        'Importe_Total': 'Facturacion ($)',
                        '% Facturacion': '% facturado sobre total de la familia'
                    }
                )
                
                # Usar el mismo estilo que la tabla de facturacion
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
                    _format_table(
                        tabla_display,
                        currency_cols=['Facturacion ($)'],
                        percent_cols=['% facturado sobre total de la familia'],
                        int_cols=['Cantidad Vendida']
                    ),
                    use_container_width=True,
                    hide_index=True,
                    height=600
                )
    else:
        st.warning("No hay datos suficientes para analisis por familia")

# ========== VISTA: RANKING DE PRODUCTOS ==========
elif menu_opcion == "Ranking de productos":
    st.header("Ranking de productos")
    
    if 'Descripcion' in df_tickets_filtrado.columns and 'Cantidad' in df_tickets_filtrado.columns and 'Importe' in df_tickets_filtrado.columns:
        # Calcular importe total por producto
        df_temp = df_tickets_filtrado.copy()
        df_temp['Importe_Total'] = df_temp['Cantidad'] * df_temp['Importe']
        
        # Agrupar por producto
        ranking_productos = df_temp.groupby('Descripcion').agg({
            'Cantidad': 'sum',
            'Importe_Total': 'sum'
        }).reset_index()
        
        # Calcular porcentaje de facturacion
        facturacion_total_periodo = ranking_productos['Importe_Total'].sum()
        ranking_productos['% Facturacion'] = (ranking_productos['Importe_Total'] / facturacion_total_periodo * 100).round(2)
        
        # Ordenar de mas vendido a menos vendido
        ranking_productos = ranking_productos.sort_values('Cantidad', ascending=False)
        
        # Agregar columna de ranking
        ranking_productos.insert(0, 'Ranking', range(1, len(ranking_productos) + 1))
        
        # Mostrar metricas del periodo
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total de Productos", f"{len(ranking_productos):,}")
        with col2:
            cantidad_total = ranking_productos['Cantidad'].sum()
            st.metric("Cantidad Total Vendida", f"{cantidad_total:,.0f}")
        with col3:
            st.metric("Facturacion Total", f"${facturacion_total_periodo:,.2f}")
        
        st.markdown("-------------")
        
        # Nota explicativa
        st.info("**Nota:** El ranking se basa en la cantidad total vendida de cada producto durante el periodo seleccionado.")
        
        # Buscador de producto
        buscar_producto = st.text_input("Buscar producto", placeholder="Escribe el nombre del producto...", key="buscar_ranking")
        
        # Formatear valores para la tabla
        tabla_ranking = ranking_productos.copy()
        
        # Filtrar por busqueda si hay texto
        if buscar_producto:
            tabla_ranking = tabla_ranking[tabla_ranking['Descripcion'].str.contains(buscar_producto, case=False, na=False)]
        
        tabla_ranking = tabla_ranking.rename(columns={
            'Ranking': '#',
            'Descripcion': 'Producto',
            'Cantidad': 'Cantidad Vendida',
            'Importe_Total': 'Facturacion Total',
            '% Facturacion': '% del Total'
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
                _format_table(
                    tabla_ranking,
                    currency_cols=['Facturacion Total'],
                    percent_cols=['% del Total'],
                    int_cols=['Cantidad Vendida']
                ),
                use_container_width=True,
                hide_index=True,
                height=600
            )
        else:
            st.warning(f"No se encontraron productos que coincidan con '{buscar_producto}'")
    else:
        st.warning("Faltan columnas necesarias para el ranking de productos")

# ========== VISTA: CREACI"N DE COMBOS ==========
elif menu_opcion == "Creacion de Combos":
    st.header("Creacion de Combos")
    
    if 'Descripcion' in df_tickets_filtrado.columns:
        st.write("Selecciona una o mas familias para ver los productos mas y menos vendidos de cada una.")
        
        # Usar el matching por nombre/descripcion para obtener familias cuando el codigo no es confiable
        df_con_familia = _agregar_familia(df_tickets_filtrado.copy(), df_consumos.copy()).copy()
        if 'Cantidad' in df_con_familia.columns:
            df_con_familia['Cantidad'] = pd.to_numeric(df_con_familia['Cantidad'], errors='coerce')
        df_con_familia = df_con_familia.dropna(subset=['Familia'])
        
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
            st.info("Selecciona al menos una familia para comenzar")
        else:
            st.markdown("-------------")
            
            # Por cada familia seleccionada, mostrar top mas y menos vendidos
            for familia in familias_seleccionadas:
                st.subheader(f"{familia}")
                
                # Filtrar productos de esta familia
                df_familia = df_con_familia[df_con_familia['Familia'] == familia]
                
                if len(df_familia) > 0 and 'Cantidad' in df_familia.columns:
                    # Agrupar por producto y sumar cantidades
                    productos_familia = df_familia.groupby('Descripcion')['Cantidad'].sum().reset_index()
                    productos_familia = productos_familia.sort_values('Cantidad', ascending=False)
                    
                    # Top mas vendidos
                    top_mas = productos_familia.head(cantidad_top).copy()
                    
                    # Top menos vendidos
                    top_menos = productos_familia.tail(cantidad_top).sort_values('Cantidad', ascending=True).copy()
                    
                    # Mostrar ambas tablas en columnas
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown(f"**Top {cantidad_top} Mas Vendidos**")
                        st.dataframe(
                            _format_table(
                                top_mas.rename(columns={'Descripcion': 'Producto', 'Cantidad': 'Cantidad Vendida'}),
                                int_cols=['Cantidad Vendida']
                            ),
                            use_container_width=True,
                            hide_index=True
                        )
                    
                    with col2:
                        st.markdown(f"**Top {cantidad_top} Menos Vendidos**")
                        st.dataframe(
                            _format_table(
                                top_menos.rename(columns={'Descripcion': 'Producto', 'Cantidad': 'Cantidad Vendida'}),
                                int_cols=['Cantidad Vendida']
                            ),
                            use_container_width=True,
                            hide_index=True
                        )
                    
                    st.markdown("-------------")
                else:
                    st.warning(f"No hay datos de cantidad para la familia {familia}")
    else:
        st.warning("Faltan columnas necesarias para analisis de combos")

# ========== VISTA: ANALISIS DE TICKETS ==========
elif menu_opcion == "Analisis de tickets":
    st.header("Analisis de tickets")
    st.caption(
        "Pasadena: se considera 'comida' a los tickets que incluyen productos de las familias "
        "COCINA, PLATO DEL DIA, COMIDA(S) o ENSALADAS."
    )
    st.caption(
        "Junin: se considera 'comida' a los tickets que incluyen productos de las familias "
        "ALMUERZO o ENSALADAS (Junin no usa COCINA ni PLATO DEL DIA; agrupa sus platos principales "
        "bajo la familia ALMUERZO)."
    )
    st.markdown("Calcula ticket promedio total, ticket promedio de comida y ticket promedio sin comida.")

    metricas_tickets = _calcular_metricas_tickets(df_tickets_filtrado, df_consumos)

    col1, col2, col3 = st.columns(3)
    with col1:
        _metric_con_confiabilidad("Ticket promedio total", f"${metricas_tickets['ticket_promedio_total']:,.2f}", metricas_tickets['confiabilidad_ticket_total']['confiabilidad_pct'])
    with col2:
        _metric_con_confiabilidad("Ticket promedio comida", f"${metricas_tickets['ticket_promedio_comida']:,.2f}", metricas_tickets['confiabilidad_ticket_comida']['confiabilidad_pct'])
    with col3:
        _metric_con_confiabilidad("Ticket promedio sin comida", f"${metricas_tickets['ticket_promedio_sin_comida']:,.2f}", metricas_tickets['confiabilidad_ticket_sin_comida']['confiabilidad_pct'])

    st.markdown("-------------")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Tickets totales", f"{metricas_tickets['total_tickets']:,}")
    with c2:
        st.metric("Tickets con comida", f"{metricas_tickets['tickets_comida']:,}")
    with c3:
        st.metric("Tickets sin comida", f"{metricas_tickets['tickets_sin_comida']:,}")

    st.markdown("-------------")
    st.subheader("Evolucion diaria del ticket promedio")
    st.caption("Evolucion diaria del ticket promedio total, ticket promedio comida y ticket promedio sin comida, calculados sobre el periodo y filtros actualmente seleccionados en el panel lateral (sucursal, rango de fechas y turno).")

    if 'Fecha' not in df_tickets_filtrado.columns or df_tickets_filtrado.empty:
        st.warning("No hay datos disponibles para proyectar.")
    else:
        df_proy_base = df_tickets_filtrado.copy()
        df_proy_base['Fecha_dt'] = pd.to_datetime(df_proy_base['Fecha'])
        fechas_unicas = sorted(df_proy_base['Fecha_dt'].dt.date.unique())

        filas_proyeccion = []
        for fecha_dia in fechas_unicas:
            df_ese_dia = df_proy_base[df_proy_base['Fecha_dt'].dt.date == fecha_dia]
            metricas_dia = _calcular_metricas_tickets(df_ese_dia, df_consumos)
            filas_proyeccion.append({
                'Fecha': fecha_dia,
                'Ticket promedio total': metricas_dia['ticket_promedio_total'],
                'Ticket promedio comida': metricas_dia['ticket_promedio_comida'],
                'Ticket promedio sin comida': metricas_dia['ticket_promedio_sin_comida'],
                'Cantidad de tickets': metricas_dia['total_tickets'],
                'Tickets comida': metricas_dia['tickets_comida'],
                'Tickets sin comida': metricas_dia['tickets_sin_comida'],
            })

        df_proyeccion = pd.DataFrame(filas_proyeccion)

        if df_proyeccion.empty:
            st.warning("No hay datos suficientes para generar la proyeccion.")
        else:
            fig_proyeccion = px.line(
                df_proyeccion,
                x='Fecha',
                y=['Ticket promedio total', 'Ticket promedio comida', 'Ticket promedio sin comida'],
                title='Evolucion del Ticket Promedio por Dia',
                labels={'value': 'Ticket Promedio ($)', 'Fecha': 'Fecha', 'variable': 'Metrica'},
                markers=True,
                color_discrete_map={
                    'Ticket promedio total': '#5DADE2',
                    'Ticket promedio comida': '#58D68D',
                    'Ticket promedio sin comida': '#F8B739',
                }
            )
            fig_proyeccion.update_traces(hovertemplate='%{y:$,.2f}<extra>%{fullData.name}</extra>')
            fig_proyeccion.update_layout(hovermode='x unified', legend_title_text='Metrica')
            st.plotly_chart(fig_proyeccion, use_container_width=True)

            st.markdown("-------------")
            st.subheader("Detalle diario")
            st.dataframe(_format_table(df_proyeccion, currency_cols=['Ticket promedio total', 'Ticket promedio comida', 'Ticket promedio sin comida']), use_container_width=True, hide_index=True)

    st.markdown("-------------")

    st.header("Analisis por cubiertos")
    st.markdown("Calcula facturacion por cubierto total, de comida y sin comida.")

    f1, f2, f3 = st.columns(3)
    with f1:
        _metric_con_confiabilidad("Facturacion por cubierto total", f"${metricas_tickets['facturacion_por_cubierto_total']:,.2f}", metricas_tickets['confiabilidad_facturacion_cubierto_total']['confiabilidad_pct'])
    with f2:
        _metric_con_confiabilidad("Facturacion por cubierto (comida)", f"${metricas_tickets['facturacion_por_cubierto_comida']:,.2f}", metricas_tickets['confiabilidad_facturacion_cubierto_comida']['confiabilidad_pct'])
    with f3:
        _metric_con_confiabilidad("Facturacion por cubierto (sin comida)", f"${metricas_tickets['facturacion_por_cubierto_sin_comida']:,.2f}", metricas_tickets['confiabilidad_facturacion_cubierto_sin_comida']['confiabilidad_pct'])

    st.markdown("-------------")

    g1, g2, g3 = st.columns(3)
    with g1:
        st.metric("Cubiertos totales", f"{metricas_tickets['cubiertos_total']:,.0f}")
    with g2:
        st.metric("Cubiertos (comida)", f"{metricas_tickets['cubiertos_comida']:,.0f}")
    with g3:
        st.metric("Cubiertos (sin comida)", f"{metricas_tickets['cubiertos_sin_comida']:,.0f}")

    st.markdown("-------------")

    st.subheader("Cubiertos con y sin comida")
    cubiertos_comida_val = metricas_tickets['cubiertos_comida']
    cubiertos_sin_comida_val = metricas_tickets['cubiertos_sin_comida']
    cubiertos_pie_total = cubiertos_comida_val + cubiertos_sin_comida_val
    if cubiertos_pie_total > 0:
        df_cubiertos_pie = pd.DataFrame({
            'Categoria': ['Con comida', 'Sin comida'],
            'Cubiertos': [cubiertos_comida_val, cubiertos_sin_comida_val]
        })
        df_cubiertos_pie['Porcentaje'] = (df_cubiertos_pie['Cubiertos'] / cubiertos_pie_total * 100).round(2)
        df_cubiertos_pie['Categoria_Label'] = df_cubiertos_pie.apply(
            lambda row: f"{row['Categoria']} ({row['Porcentaje']:.1f}%)", axis=1
        )
        df_cubiertos_pie['Slice_Label'] = df_cubiertos_pie.apply(
            lambda row: f"{row['Categoria']}<br>{row['Cubiertos']:,.0f}", axis=1
        )

        fig_torta_cubiertos = px.pie(
            df_cubiertos_pie,
            values='Cubiertos',
            names='Categoria_Label',
            title='Distribucion de Cubiertos (con y sin comida)',
            hole=0.4,
            custom_data=['Categoria'],
            color_discrete_sequence=['#58D68D', '#EC7063']
        )
        fig_torta_cubiertos.update_traces(
            textposition='inside',
            text=df_cubiertos_pie['Slice_Label'],
            hovertemplate='<b>%{customdata[0]}</b><br>Cubiertos: %{value:,.0f}<extra></extra>'
        )
        st.plotly_chart(fig_torta_cubiertos, use_container_width=True)
    else:
        st.info("No hay datos de cubiertos para graficar.")

    st.markdown("-------------")

    st.subheader("Cubiertos promedio y mediana por ticket")

    h1, h2, h3 = st.columns(3)
    with h1:
        _metric_con_confiabilidad("Cubiertos promedio (total)", f"{metricas_tickets['cubiertos_promedio_total']:,.2f}", metricas_tickets['confiabilidad_cubiertos_total']['confiabilidad_pct'])
    with h2:
        _metric_con_confiabilidad("Cubiertos promedio (comida)", f"{metricas_tickets['cubiertos_promedio_comida']:,.2f}", metricas_tickets['confiabilidad_cubiertos_comida']['confiabilidad_pct'])
    with h3:
        _metric_con_confiabilidad("Cubiertos promedio (sin comida)", f"{metricas_tickets['cubiertos_promedio_sin_comida']:,.2f}", metricas_tickets['confiabilidad_cubiertos_sin_comida']['confiabilidad_pct'])

    i1, i2, i3 = st.columns(3)
    with i1:
        st.metric("Cubiertos mediana (total)", f"{metricas_tickets['cubiertos_mediana_total']:,.2f}")
    with i2:
        st.metric("Cubiertos mediana (comida)", f"{metricas_tickets['cubiertos_mediana_comida']:,.2f}")
    with i3:
        st.metric("Cubiertos mediana (sin comida)", f"{metricas_tickets['cubiertos_mediana_sin_comida']:,.2f}")

    st.markdown("-------------")
    st.subheader("Numero de cubiertos por ticket (mesa)")
    st.caption("Cantidad de tickets (mesas) segun la cantidad de cubiertos que tienen. Solo se incluyen tickets con cubiertos registrados (mayor a 0). Los valores de 10 cubiertos o mas se agrupan en la categoria '10+'.")

    df_distribucion_cubiertos = _calcular_distribucion_cubiertos_por_ticket(df_tickets_filtrado, df_consumos)

    if df_distribucion_cubiertos.empty:
        st.info("No hay datos de cubiertos para graficar.")
    else:
        fig_distribucion_cubiertos = px.bar(
            df_distribucion_cubiertos,
            x='Cubiertos_Label',
            y='Cantidad de tickets',
            title='Numero de Cubiertos por Ticket (Mesa)',
            labels={'Cubiertos_Label': 'Cantidad de cubiertos', 'Cantidad de tickets': 'Cantidad de tickets'},
            color='Cantidad de tickets',
            color_continuous_scale='Blues',
            text='Cantidad de tickets'
        )
        fig_distribucion_cubiertos.update_traces(textposition='outside')
        fig_distribucion_cubiertos.update_layout(xaxis_type='category', showlegend=False)
        st.plotly_chart(fig_distribucion_cubiertos, use_container_width=True)

        st.dataframe(
            df_distribucion_cubiertos[['Cubiertos_Label', 'Cantidad de tickets']].rename(columns={'Cubiertos_Label': 'Cubiertos'}),
            use_container_width=True,
            hide_index=True
        )

    st.markdown("-------------")
    st.subheader("Evolucion diaria de la facturacion por cubierto")
    st.caption("Evolucion diaria de la facturacion por cubierto (total, comida y sin comida), calculada sobre el periodo y filtros actualmente seleccionados en el panel lateral (sucursal, rango de fechas y turno).")

    if 'Fecha' not in df_tickets_filtrado.columns or df_tickets_filtrado.empty:
        st.warning("No hay datos disponibles para proyectar.")
    else:
        filas_cubierto = []
        for fecha_dia in fechas_unicas:
            df_ese_dia = df_proy_base[df_proy_base['Fecha_dt'].dt.date == fecha_dia]
            metricas_dia = _calcular_metricas_tickets(df_ese_dia, df_consumos)
            filas_cubierto.append({
                'Fecha': fecha_dia,
                'Facturacion por cubierto total': metricas_dia['facturacion_por_cubierto_total'],
                'Facturacion por cubierto comida': metricas_dia['facturacion_por_cubierto_comida'],
                'Facturacion por cubierto sin comida': metricas_dia['facturacion_por_cubierto_sin_comida'],
                'Cantidad de cubiertos': metricas_dia['cubiertos_total'],
                'Cubiertos comida': metricas_dia['cubiertos_comida'],
                'Cubiertos sin comida': metricas_dia['cubiertos_sin_comida'],
            })
        df_cubierto_proyeccion = pd.DataFrame(filas_cubierto)

        if df_cubierto_proyeccion.empty:
            st.warning("No hay datos suficientes para generar la proyeccion por cubierto.")
        else:
            fig_cubierto = px.line(
                df_cubierto_proyeccion,
                x='Fecha',
                y=['Facturacion por cubierto total', 'Facturacion por cubierto comida', 'Facturacion por cubierto sin comida'],
                title='Evolucion de Facturacion por Cubierto por Dia',
                labels={'value': 'Facturacion por Cubierto ($)', 'Fecha': 'Fecha', 'variable': 'Metrica'},
                markers=True,
                color_discrete_map={
                    'Facturacion por cubierto total': '#5DADE2',
                    'Facturacion por cubierto comida': '#58D68D',
                    'Facturacion por cubierto sin comida': '#F8B739',
                }
            )
            fig_cubierto.update_traces(hovertemplate='%{y:$,.2f}<extra>%{fullData.name}</extra>')
            fig_cubierto.update_layout(hovermode='x unified', legend_title_text='Metrica')
            st.plotly_chart(fig_cubierto, use_container_width=True)

            st.markdown("-------------")
            st.subheader("Detalle diario - Facturacion por cubierto")
            st.dataframe(_format_table(df_cubierto_proyeccion, currency_cols=['Facturacion por cubierto total', 'Facturacion por cubierto comida', 'Facturacion por cubierto sin comida']), use_container_width=True, hide_index=True)

    st.caption(
        "Confiabilidad de cada promedio: verde = confiable (>=90%), amarillo = medio confiable (70-89.9%), "
        "rojo = no confiable (<70%). Confiabilidad = 100 x (1 - margen de error al 95% / promedio)."
    )

    st.caption(
        "Regla aplicada: un ticket es 'con comida' si contiene al menos un producto de las familias de comida "
        "de su sucursal (ver detalle por local abajo). Facturacion comida = suma de las lineas de esas familias "
        "(no el total del ticket). Ticket promedio comida = facturacion comida / cantidad de tickets con comida. "
        "Ticket promedio sin comida = facturacion de las demas lineas / cantidad de tickets sin comida. "
        "Cubiertos = suma de la cantidad de la familia CUBIERTOS agrupada por ticket (una o mas lineas por ticket), "
        "clasificada segun si el ticket es con, sin comida, o el total general. Facturacion por cubierto = "
        "facturacion de la clase / cubiertos de esa clase. Promedio y mediana de cubiertos se calculan sobre la "
        "cantidad de cubiertos por ticket dentro de cada categoria."
    )

# ========== VISTA: NEGOCIO SIN REGALOS ==========
elif menu_opcion == "Negocio sin regalos":
    st.header("Negocio sin regalos")
    st.markdown("Selecciona un producto para simular como quedaria el negocio si ese producto no existiera. Se excluyen TODOS los tickets que contienen el producto seleccionado (como si esos tickets nunca hubieran existido) y se recalculan las mismas metricas de Analisis de tickets sobre los tickets restantes.")

    if 'Descripcion' not in df_tickets_filtrado.columns or 'Numero' not in df_tickets_filtrado.columns or df_tickets_filtrado.empty:
        st.warning("No hay datos disponibles para simular.")
    else:
        productos_disponibles_negocio = sorted(df_tickets_filtrado['Descripcion'].dropna().unique().tolist())
        if len(productos_disponibles_negocio) == 0:
            st.warning("No hay productos disponibles en el periodo seleccionado.")
        else:
            producto_a_excluir = st.selectbox(
                "Selecciona el producto a excluir del negocio",
                productos_disponibles_negocio,
                index=0,
                key="producto_excluir_negocio"
            )

            tickets_con_producto_excluir = df_tickets_filtrado[
                df_tickets_filtrado['Descripcion'] == producto_a_excluir
            ]['Numero'].unique()

            df_tickets_sin_producto = df_tickets_filtrado[
                ~df_tickets_filtrado['Numero'].isin(tickets_con_producto_excluir)
            ].copy()

            df_tickets_filtrado_calc = df_tickets_filtrado.copy()
            if 'Cantidad' not in df_tickets_filtrado_calc.columns:
                df_tickets_filtrado_calc['Cantidad'] = 1
            df_tickets_filtrado_calc['Cantidad'] = pd.to_numeric(df_tickets_filtrado_calc['Cantidad'], errors='coerce').fillna(0)
            df_tickets_filtrado_calc['Importe'] = pd.to_numeric(df_tickets_filtrado_calc['Importe'], errors='coerce').fillna(0)
            df_tickets_filtrado_calc['Importe_Total_Linea'] = df_tickets_filtrado_calc['Cantidad'] * df_tickets_filtrado_calc['Importe']

            df_tickets_sin_producto_calc = df_tickets_filtrado_calc[
                ~df_tickets_filtrado_calc['Numero'].isin(tickets_con_producto_excluir)
            ]

            facturacion_total_original = df_tickets_filtrado_calc['Importe_Total_Linea'].sum()
            facturacion_total_sin_producto = df_tickets_sin_producto_calc['Importe_Total_Linea'].sum()
            facturacion_perdida = facturacion_total_original - facturacion_total_sin_producto

            st.markdown("-------------")

            st.subheader("Impacto de excluir este producto")
            imp1, imp2, imp3 = st.columns(3)
            with imp1:
                st.metric("Facturacion total (sin este producto)", f"${facturacion_total_sin_producto:,.2f}")
            with imp2:
                st.metric("Facturacion perdida (tickets excluidos)", f"${facturacion_perdida:,.2f}")
            with imp3:
                st.metric("Tickets excluidos", f"{len(tickets_con_producto_excluir):,}")
            st.caption("Facturacion total sin este producto = suma de Importe de todas las lineas de los tickets que NO contienen el producto seleccionado. Facturacion perdida = facturacion total original menos la facturacion sin el producto (equivale a la suma de Importe de los tickets excluidos).")

            st.markdown("-------------")

            metricas_tickets_negocio = _calcular_metricas_tickets(df_tickets_sin_producto, df_consumos)

            col1n, col2n, col3n = st.columns(3)
            with col1n:
                _metric_con_confiabilidad("Ticket promedio total", f"${metricas_tickets_negocio['ticket_promedio_total']:,.2f}", metricas_tickets_negocio['confiabilidad_ticket_total']['confiabilidad_pct'])
            with col2n:
                _metric_con_confiabilidad("Ticket promedio comida", f"${metricas_tickets_negocio['ticket_promedio_comida']:,.2f}", metricas_tickets_negocio['confiabilidad_ticket_comida']['confiabilidad_pct'])
            with col3n:
                _metric_con_confiabilidad("Ticket promedio sin comida", f"${metricas_tickets_negocio['ticket_promedio_sin_comida']:,.2f}", metricas_tickets_negocio['confiabilidad_ticket_sin_comida']['confiabilidad_pct'])

            st.markdown("-------------")

            c1n, c2n, c3n = st.columns(3)
            with c1n:
                st.metric("Tickets totales", f"{metricas_tickets_negocio['total_tickets']:,}")
            with c2n:
                st.metric("Tickets con comida", f"{metricas_tickets_negocio['tickets_comida']:,}")
            with c3n:
                st.metric("Tickets sin comida", f"{metricas_tickets_negocio['tickets_sin_comida']:,}")

            st.markdown("-------------")
            st.subheader("Evolucion diaria del ticket promedio")
            st.caption("Evolucion diaria del ticket promedio total, ticket promedio comida y ticket promedio sin comida, calculados sobre el periodo y filtros actualmente seleccionados en el panel lateral (sucursal, rango de fechas y turno).")

            if 'Fecha' not in df_tickets_sin_producto.columns or df_tickets_sin_producto.empty:
                st.warning("No hay datos disponibles para proyectar.")
            else:
                df_proy_base_negocio = df_tickets_sin_producto.copy()
                df_proy_base_negocio['Fecha_dt'] = pd.to_datetime(df_proy_base_negocio['Fecha'])
                fechas_unicas_negocio = sorted(df_proy_base_negocio['Fecha_dt'].dt.date.unique())

                filas_proyeccion_negocio = []
                for fecha_dia_negocio in fechas_unicas_negocio:
                    df_ese_dia_negocio = df_proy_base_negocio[df_proy_base_negocio['Fecha_dt'].dt.date == fecha_dia_negocio]
                    metricas_dia_negocio = _calcular_metricas_tickets(df_ese_dia_negocio, df_consumos)
                    filas_proyeccion_negocio.append({
                        'Fecha': fecha_dia_negocio,
                        'Ticket promedio total': metricas_dia_negocio['ticket_promedio_total'],
                        'Ticket promedio comida': metricas_dia_negocio['ticket_promedio_comida'],
                        'Ticket promedio sin comida': metricas_dia_negocio['ticket_promedio_sin_comida'],
                        'Cantidad de tickets': metricas_dia_negocio['total_tickets'],
                        'Tickets comida': metricas_dia_negocio['tickets_comida'],
                        'Tickets sin comida': metricas_dia_negocio['tickets_sin_comida'],
                    })

                df_proyeccion_negocio = pd.DataFrame(filas_proyeccion_negocio)

                if df_proyeccion_negocio.empty:
                    st.warning("No hay datos suficientes para generar la proyeccion.")
                else:
                    fig_proyeccion_negocio = px.line(
                        df_proyeccion_negocio,
                        x='Fecha',
                        y=['Ticket promedio total', 'Ticket promedio comida', 'Ticket promedio sin comida'],
                        title='Evolucion del Ticket Promedio por Dia',
                        labels={'value': 'Ticket Promedio ($)', 'Fecha': 'Fecha', 'variable': 'Metrica'},
                        markers=True,
                        color_discrete_map={
                            'Ticket promedio total': '#5DADE2',
                            'Ticket promedio comida': '#58D68D',
                            'Ticket promedio sin comida': '#F8B739',
                        }
                    )
                    fig_proyeccion_negocio.update_traces(hovertemplate='%{y:$,.2f}<extra>%{fullData.name}</extra>')
                    fig_proyeccion_negocio.update_layout(hovermode='x unified', legend_title_text='Metrica')
                    st.plotly_chart(fig_proyeccion_negocio, use_container_width=True)

                    st.markdown("-------------")
                    st.subheader("Detalle diario")
                    st.dataframe(_format_table(df_proyeccion_negocio, currency_cols=['Ticket promedio total', 'Ticket promedio comida', 'Ticket promedio sin comida']), use_container_width=True, hide_index=True)

            st.markdown("-------------")

            st.header("Analisis por cubiertos")
            st.markdown("Calcula facturacion por cubierto total, de comida y sin comida.")

            f1n, f2n, f3n = st.columns(3)
            with f1n:
                _metric_con_confiabilidad("Facturacion por cubierto total", f"${metricas_tickets_negocio['facturacion_por_cubierto_total']:,.2f}", metricas_tickets_negocio['confiabilidad_facturacion_cubierto_total']['confiabilidad_pct'])
            with f2n:
                _metric_con_confiabilidad("Facturacion por cubierto (comida)", f"${metricas_tickets_negocio['facturacion_por_cubierto_comida']:,.2f}", metricas_tickets_negocio['confiabilidad_facturacion_cubierto_comida']['confiabilidad_pct'])
            with f3n:
                _metric_con_confiabilidad("Facturacion por cubierto (sin comida)", f"${metricas_tickets_negocio['facturacion_por_cubierto_sin_comida']:,.2f}", metricas_tickets_negocio['confiabilidad_facturacion_cubierto_sin_comida']['confiabilidad_pct'])

            st.markdown("-------------")

            g1n, g2n, g3n = st.columns(3)
            with g1n:
                st.metric("Cubiertos totales", f"{metricas_tickets_negocio['cubiertos_total']:,.0f}")
            with g2n:
                st.metric("Cubiertos (comida)", f"{metricas_tickets_negocio['cubiertos_comida']:,.0f}")
            with g3n:
                st.metric("Cubiertos (sin comida)", f"{metricas_tickets_negocio['cubiertos_sin_comida']:,.0f}")

            st.markdown("-------------")

            st.subheader("Cubiertos con y sin comida")
            cubiertos_comida_val_negocio = metricas_tickets_negocio['cubiertos_comida']
            cubiertos_sin_comida_val_negocio = metricas_tickets_negocio['cubiertos_sin_comida']
            cubiertos_pie_total_negocio = cubiertos_comida_val_negocio + cubiertos_sin_comida_val_negocio
            if cubiertos_pie_total_negocio > 0:
                df_cubiertos_pie_negocio = pd.DataFrame({
                    'Categoria': ['Con comida', 'Sin comida'],
                    'Cubiertos': [cubiertos_comida_val_negocio, cubiertos_sin_comida_val_negocio]
                })
                df_cubiertos_pie_negocio['Porcentaje'] = (df_cubiertos_pie_negocio['Cubiertos'] / cubiertos_pie_total_negocio * 100).round(2)
                df_cubiertos_pie_negocio['Categoria_Label'] = df_cubiertos_pie_negocio.apply(
                    lambda row: f"{row['Categoria']} ({row['Porcentaje']:.1f}%)", axis=1
                )
                df_cubiertos_pie_negocio['Slice_Label'] = df_cubiertos_pie_negocio.apply(
                    lambda row: f"{row['Categoria']}<br>{row['Cubiertos']:,.0f}", axis=1
                )

                fig_torta_cubiertos_negocio = px.pie(
                    df_cubiertos_pie_negocio,
                    values='Cubiertos',
                    names='Categoria_Label',
                    title='Distribucion de Cubiertos (con y sin comida)',
                    hole=0.4,
                    custom_data=['Categoria'],
                    color_discrete_sequence=['#58D68D', '#EC7063']
                )
                fig_torta_cubiertos_negocio.update_traces(
                    textposition='inside',
                    text=df_cubiertos_pie_negocio['Slice_Label'],
                    hovertemplate='<b>%{customdata[0]}</b><br>Cubiertos: %{value:,.0f}<extra></extra>'
                )
                st.plotly_chart(fig_torta_cubiertos_negocio, use_container_width=True)
            else:
                st.info("No hay datos de cubiertos para graficar.")

            st.markdown("-------------")

            st.subheader("Cubiertos promedio y mediana por ticket")

            h1n, h2n, h3n = st.columns(3)
            with h1n:
                _metric_con_confiabilidad("Cubiertos promedio (total)", f"{metricas_tickets_negocio['cubiertos_promedio_total']:,.2f}", metricas_tickets_negocio['confiabilidad_cubiertos_total']['confiabilidad_pct'])
            with h2n:
                _metric_con_confiabilidad("Cubiertos promedio (comida)", f"{metricas_tickets_negocio['cubiertos_promedio_comida']:,.2f}", metricas_tickets_negocio['confiabilidad_cubiertos_comida']['confiabilidad_pct'])
            with h3n:
                _metric_con_confiabilidad("Cubiertos promedio (sin comida)", f"{metricas_tickets_negocio['cubiertos_promedio_sin_comida']:,.2f}", metricas_tickets_negocio['confiabilidad_cubiertos_sin_comida']['confiabilidad_pct'])

            i1n, i2n, i3n = st.columns(3)
            with i1n:
                st.metric("Cubiertos mediana (total)", f"{metricas_tickets_negocio['cubiertos_mediana_total']:,.2f}")
            with i2n:
                st.metric("Cubiertos mediana (comida)", f"{metricas_tickets_negocio['cubiertos_mediana_comida']:,.2f}")
            with i3n:
                st.metric("Cubiertos mediana (sin comida)", f"{metricas_tickets_negocio['cubiertos_mediana_sin_comida']:,.2f}")

            st.markdown("-------------")
            st.subheader("Evolucion diaria de la facturacion por cubierto")
            st.caption("Evolucion diaria de la facturacion por cubierto (total, comida y sin comida), calculada sobre el periodo y filtros actualmente seleccionados en el panel lateral (sucursal, rango de fechas y turno).")

            if 'Fecha' not in df_tickets_sin_producto.columns or df_tickets_sin_producto.empty:
                st.warning("No hay datos disponibles para proyectar.")
            else:
                filas_cubierto_negocio = []
                for fecha_dia_negocio in fechas_unicas_negocio:
                    df_ese_dia_negocio = df_proy_base_negocio[df_proy_base_negocio['Fecha_dt'].dt.date == fecha_dia_negocio]
                    metricas_dia_negocio = _calcular_metricas_tickets(df_ese_dia_negocio, df_consumos)
                    filas_cubierto_negocio.append({
                        'Fecha': fecha_dia_negocio,
                        'Facturacion por cubierto total': metricas_dia_negocio['facturacion_por_cubierto_total'],
                        'Facturacion por cubierto comida': metricas_dia_negocio['facturacion_por_cubierto_comida'],
                        'Facturacion por cubierto sin comida': metricas_dia_negocio['facturacion_por_cubierto_sin_comida'],
                        'Cantidad de cubiertos': metricas_dia_negocio['cubiertos_total'],
                        'Cubiertos comida': metricas_dia_negocio['cubiertos_comida'],
                        'Cubiertos sin comida': metricas_dia_negocio['cubiertos_sin_comida'],
                    })
                df_cubierto_proyeccion_negocio = pd.DataFrame(filas_cubierto_negocio)

                if df_cubierto_proyeccion_negocio.empty:
                    st.warning("No hay datos suficientes para generar la proyeccion por cubierto.")
                else:
                    fig_cubierto_negocio = px.line(
                        df_cubierto_proyeccion_negocio,
                        x='Fecha',
                        y=['Facturacion por cubierto total', 'Facturacion por cubierto comida', 'Facturacion por cubierto sin comida'],
                        title='Evolucion de Facturacion por Cubierto por Dia',
                        labels={'value': 'Facturacion por Cubierto ($)', 'Fecha': 'Fecha', 'variable': 'Metrica'},
                        markers=True,
                        color_discrete_map={
                            'Facturacion por cubierto total': '#5DADE2',
                            'Facturacion por cubierto comida': '#58D68D',
                            'Facturacion por cubierto sin comida': '#F8B739',
                        }
                    )
                    fig_cubierto_negocio.update_traces(hovertemplate='%{y:$,.2f}<extra>%{fullData.name}</extra>')
                    fig_cubierto_negocio.update_layout(hovermode='x unified', legend_title_text='Metrica')
                    st.plotly_chart(fig_cubierto_negocio, use_container_width=True)

                    st.markdown("-------------")
                    st.subheader("Detalle diario - Facturacion por cubierto")
                    st.dataframe(_format_table(df_cubierto_proyeccion_negocio, currency_cols=['Facturacion por cubierto total', 'Facturacion por cubierto comida', 'Facturacion por cubierto sin comida']), use_container_width=True, hide_index=True)

            st.caption(
                "Confiabilidad de cada promedio: verde = confiable (>=90%), amarillo = medio confiable (70-89.9%), "
                "rojo = no confiable (<70%). Confiabilidad = 100 x (1 - margen de error al 95% / promedio)."
            )

            st.caption(
                "Regla aplicada: un ticket es 'con comida' si contiene al menos un producto de las familias de comida "
                "de su sucursal (ver detalle por local abajo). Facturacion comida = suma de las lineas de esas familias "
                "(no el total del ticket). Ticket promedio comida = facturacion comida / cantidad de tickets con comida. "
                "Ticket promedio sin comida = facturacion de las demas lineas / cantidad de tickets sin comida. "
                "Cubiertos = suma de la cantidad de la familia CUBIERTOS agrupada por ticket (una o mas lineas por ticket), "
                "clasificada segun si el ticket es con, sin comida, o el total general. Facturacion por cubierto = "
                "facturacion de la clase / cubiertos de esa clase. Promedio y mediana de cubiertos se calculan sobre la "
                "cantidad de cubiertos por ticket dentro de cada categoria."
            )

# ========== VISTA: ANLISIS DE REGALOS ==========
elif menu_opcion == "Analisis de regalos":
    st.header("Analisis de regalos")
    
    if 'Numero' in df_tickets_filtrado.columns and 'Descripcion' in df_tickets_filtrado.columns:
        # Obtener todos los productos
        productos_disponibles = sorted(df_tickets_filtrado['Descripcion'].dropna().unique().tolist())
        
        # Filtrar productos que contengan "regalo" (por defecto)
        productos_regalo = [p for p in productos_disponibles if 'regalo' in p.lower()]
        
        # Determinar el indice por defecto
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
        
        st.markdown("-------------")
        
        # Buscar tickets que contienen el producto regalo seleccionado
        tickets_con_regalo = df_tickets_filtrado[
            df_tickets_filtrado['Descripcion'] == producto_regalo_seleccionado
        ]['Numero'].unique()
        
        if len(tickets_con_regalo) > 0:
            # Filtrar todos los productos en esos tickets
            df_productos_en_tickets = df_tickets_filtrado[
                df_tickets_filtrado['Numero'].isin(tickets_con_regalo)
            ].copy()
            
            # Calcular importe total por producto
            if 'Cantidad' in df_productos_en_tickets.columns and 'Importe' in df_productos_en_tickets.columns:
                df_productos_en_tickets['Importe_Total'] = df_productos_en_tickets['Cantidad'] * df_productos_en_tickets['Importe']
                
                # Agrupar por producto
                resumen_productos = df_productos_en_tickets.groupby('Descripcion').agg({
                    'Cantidad': 'sum',
                    'Importe_Total': 'sum'
                }).reset_index()
                
                # Ordenar por facturacion descendente
                resumen_productos = resumen_productos.sort_values('Importe_Total', ascending=False)
                
                # Calcular totales
                facturacion_total_tickets = resumen_productos['Importe_Total'].sum()
                cantidad_regalo = resumen_productos[
                    resumen_productos['Descripcion'] == producto_regalo_seleccionado
                ]['Cantidad'].sum()
                promedio_valor_ticket = (
                    facturacion_total_tickets / len(tickets_con_regalo)
                    if len(tickets_con_regalo) > 0 else 0.0
                )
                costo_total = cantidad_regalo * costo_unitario
                
                # Mostrar metricas
                col1, col2, col3, col4, col5 = st.columns(5)
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
                    st.metric("Promedio valor ticket", f"${promedio_valor_ticket:,.2f}")
                with col5:
                    st.metric("Costo total", f"${costo_total:,.2f}")
                
                st.markdown("-------------")
                
                # Formatear tabla solo en la capa visual; mantener los valores numericos para ordenar
                tabla_productos = resumen_productos.copy()
                
                tabla_productos = tabla_productos.rename(columns={
                    'Descripcion': 'Producto',
                    'Cantidad': 'Cantidad Vendida',
                    'Importe_Total': 'Facturacion en estos Tickets'
                })
                
                # Mostrar tabla
                st.subheader("Productos vendidos en tickets con el regalo")
                st.dataframe(
                    _format_table(
                        tabla_productos,
                        currency_cols=['Facturacion en estos Tickets'],
                        int_cols=['Cantidad Vendida']
                    ),
                    use_container_width=True,
                    hide_index=True,
                    height=500
                )
            else:
                st.warning("Faltan columnas de Cantidad o Importe")
        else:
            st.info(f"No se encontraron tickets con el producto '{producto_regalo_seleccionado}'")
    else:
        st.warning("Faltan columnas necesarias para el analisis de regalos")

# Footer
st.markdown("-------------")
st.caption("DataKinga Dashboard v1.0 - Datos actualizados en tiempo real")










