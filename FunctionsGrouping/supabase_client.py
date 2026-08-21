"""
Supabase integration - client and data helpers
"""
import os
import pandas as pd
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# Column name maps: supabase (snake_case) <-> original pandas (Spanish/accented)
TICKETS_COLS_TO_SUPABASE = {
    'Numero': 'numero',
    'Tipo': 'tipo',
    'Sucursal': 'sucursal',
    'Mesa': 'mesa',
    'Mozo': 'mozo',
    'Nombre': 'nombre',
    'Codigo': 'codigo',
    'Descripcion': 'descripcion',
    'Cantidad': 'cantidad',
    'Importe': 'importe',
    'Turno': 'turno',
    'Fecha': 'fecha',
    'Hora': 'hora',
}

TICKETS_COLS_FROM_SUPABASE = {v: k for k, v in TICKETS_COLS_TO_SUPABASE.items()}

# Map original Spanish column names -> normalized ASCII key
TICKETS_NORMALIZE = {
    'Número': 'Numero',
    'Código': 'Codigo',
    'Descripción': 'Descripcion',
}

CONSUMOS_COLS_TO_SUPABASE = {
    'Familia': 'familia',
    'Codigo': 'codigo',
    'Articulo': 'articulo',
    'Sucursal': 'sucursal',
    'Fecha_Carga': 'fecha_carga',
}

CONSUMOS_COLS_FROM_SUPABASE = {v: k for k, v in CONSUMOS_COLS_TO_SUPABASE.items()}


def get_client() -> Client:
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_KEY')
    if not url or not key:
        raise ValueError("Define SUPABASE_URL y SUPABASE_KEY en .env")
    return create_client(url, key)


def get_existing_ticket_keys(client: Client) -> set:
    """Returns set of 'numero|codigo' strings already in Supabase."""
    try:
        response = client.table('tickets_detalle').select('numero,codigo').execute()
        return {f"{r['numero']}|{r['codigo']}" for r in response.data}
    except Exception:
        return set()


def insert_tickets(client: Client, df: pd.DataFrame):
    """Insert new tickets into Supabase, skipping duplicates."""
    if df.empty:
        print("   ℹ️ No hay tickets nuevos para insertar")
        return

    # Normalize accented column names to ASCII
    df = df.rename(columns=TICKETS_NORMALIZE)

    # Get existing keys to avoid duplicates
    existing_keys = get_existing_ticket_keys(client)
    df['_key'] = df['Numero'].astype(str) + '|' + df['Codigo'].astype(str)
    df_new = df[~df['_key'].isin(existing_keys)].drop(columns=['_key'])

    print(f"   Tickets a insertar: {len(df_new)} (de {len(df)} totales)")

    if df_new.empty:
        print("   ℹ️ Todos son duplicados")
        return

    # Rename to supabase column names
    df_new = df_new.rename(columns=TICKETS_COLS_TO_SUPABASE)

    # Convert dates/times to string (JSON serializable)
    for col in ['fecha', 'hora']:
        if col in df_new.columns:
            df_new[col] = df_new[col].astype(str)

    # Drop duplicates within the batch (same numero+codigo) to avoid ON CONFLICT update conflict
    df_new = df_new.drop_duplicates(subset=['numero', 'codigo'], keep='last')
    # Drop duplicates within the batch (same numero+codigo) to avoid ON CONFLICT update conflict
    df_new = df_new.drop_duplicates(subset=['numero', 'codigo'], keep='last')
    records = df_new.where(pd.notnull(df_new), None).to_dict(orient='records')

    # Insert in batches of 500
    batch_size = 500
    inserted = 0
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        client.table('tickets_detalle').upsert(batch, on_conflict='numero,codigo').execute()
        inserted += len(batch)
        print(f"   ✓ Insertados {inserted}/{len(records)}")

    print(f"   ✅ {inserted} tickets insertados en Supabase")


def upsert_consumos(client: Client, df: pd.DataFrame):
    """Upsert consumos (insert or update fecha_carga) by codigo+sucursal."""
    if df.empty:
        print("   ℹ️ No hay consumos para upsertear")
        return

    df = df.rename(columns=CONSUMOS_COLS_TO_SUPABASE)

    for col in ['fecha_carga']:
        if col in df.columns:
            df[col] = df[col].astype(str)

    records = df.where(pd.notnull(df), None).to_dict(orient='records')

    batch_size = 500
    upserted = 0
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        client.table('consumos').upsert(
            batch,
            on_conflict='codigo,articulo,sucursal'
        ).execute()
        upserted += len(batch)
        print(f"   ✓ Upserted {upserted}/{len(records)}")

    print(f"   ✅ {upserted} consumos procesados en Supabase")


def fetch_tickets(client: Client) -> pd.DataFrame:
    """Fetch all tickets from Supabase and rename columns to original names."""
    response = client.table('tickets_detalle').select('*').execute()
    df = pd.DataFrame(response.data)
    if df.empty:
        return df
    return df.rename(columns={
        'numero': 'Número',
        'tipo': 'Tipo',
        'sucursal': 'Sucursal',
        'mesa': 'Mesa',
        'mozo': 'Mozo',
        'nombre': 'Nombre',
        'codigo': 'Código',
        'descripcion': 'Descripción',
        'cantidad': 'Cantidad',
        'importe': 'Importe',
        'turno': 'Turno',
        'fecha': 'Fecha',
        'hora': 'Hora',
    })


def fetch_consumos(client: Client) -> pd.DataFrame:
    """Fetch consumos from Supabase (latest fecha_carga per codigo+sucursal)."""
    response = client.table('consumos').select('*').execute()
    df = pd.DataFrame(response.data)
    if df.empty:
        return df
    df = df.rename(columns={
        'familia': 'Familia',
        'codigo': 'Codigo',
        'articulo': 'Articulo',
        'sucursal': 'Sucursal',
        'fecha_carga': 'Fecha_Carga',
    })
    # Keep only the latest Fecha_Carga per Codigo+Sucursal
    if 'Fecha_Carga' in df.columns:
        df = df.sort_values('Fecha_Carga', ascending=False)
        df = df.drop_duplicates(subset=['Codigo', 'Sucursal'], keep='first')
    return df
