-- ============================================================
-- DATAKINGA - Supabase table creation
-- Run this in the Supabase SQL Editor before first deploy
-- ============================================================

-- tickets_detalle
CREATE TABLE IF NOT EXISTS public.tickets_detalle (
    id          BIGSERIAL PRIMARY KEY,
    numero      TEXT,
    tipo        TEXT,
    sucursal    TEXT,
    mesa        TEXT,
    mozo        TEXT,
    nombre      TEXT,
    codigo      TEXT,
    descripcion TEXT,
    cantidad    NUMERIC,
    importe     NUMERIC,
    turno       TEXT,
    fecha       DATE,
    hora        TEXT
);

-- Unique constraint to prevent duplicate ticket lines
CREATE UNIQUE INDEX IF NOT EXISTS idx_tickets_numero_codigo
    ON public.tickets_detalle (numero, codigo);

-- Index for dashboard queries (filter by sucursal + fecha)
CREATE INDEX IF NOT EXISTS idx_tickets_sucursal_fecha
    ON public.tickets_detalle (sucursal, fecha);


-- consumos
CREATE TABLE IF NOT EXISTS public.consumos (
    id          BIGSERIAL PRIMARY KEY,
    familia     TEXT,
    codigo      TEXT        NOT NULL,
    articulo    TEXT        NOT NULL,
    sucursal    TEXT        NOT NULL,
    fecha_carga TIMESTAMPTZ DEFAULT NOW()
);

-- Unique constraint used by upsert ON CONFLICT
CREATE UNIQUE INDEX IF NOT EXISTS idx_consumos_codigo_articulo_sucursal
    ON public.consumos (codigo, articulo, sucursal);

-- Index for dashboard queries
CREATE INDEX IF NOT EXISTS idx_consumos_sucursal
    ON public.consumos (sucursal);

-- ============================================================
-- RLS Policies (run after table creation)
-- Allows the anon key to read/write (internal app, no user auth)
-- ============================================================

ALTER TABLE public.tickets_detalle ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.consumos ENABLE ROW LEVEL SECURITY;

-- Allow full access via anon key (internal scraper + dashboard)
CREATE POLICY IF NOT EXISTS "allow_all_tickets"
    ON public.tickets_detalle
    FOR ALL
    TO anon
    USING (true)
    WITH CHECK (true);

CREATE POLICY IF NOT EXISTS "allow_all_consumos"
    ON public.consumos
    FOR ALL
    TO anon
    USING (true)
    WITH CHECK (true);
