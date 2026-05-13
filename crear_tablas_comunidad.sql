-- ============================================================
-- COMUNIDAD CLEANCITI — Tablas Supabase
-- Ejecutar en: Supabase → SQL Editor → Run
-- ============================================================

-- Metadatos de clientes (teléfono, email, vendedor, tipo)
CREATE TABLE IF NOT EXISTS clientes_comunidad (
  razon_social  TEXT PRIMARY KEY,
  tipo_cliente  TEXT,
  vendedor      TEXT,
  telefono      TEXT,
  telefono2     TEXT,
  email         TEXT,
  updated_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Ventas mensuales consolidadas (1 fila por cliente×mes)
CREATE TABLE IF NOT EXISTS ventas_comunidad (
  razon_social  TEXT    NOT NULL,
  mes           TEXT    NOT NULL,  -- formato 'YYYY-MM'
  importe       NUMERIC NOT NULL DEFAULT 0,
  updated_at    TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (razon_social, mes)
);

-- Gestiones comerciales (llamadas, WhatsApp, visitas, etc.)
CREATE TABLE IF NOT EXISTS gestiones_comunidad (
  id               BIGSERIAL PRIMARY KEY,
  razon_social     TEXT    NOT NULL,
  vendedor         TEXT,
  tipo             TEXT,   -- 'WhatsApp' | 'Llamada' | 'Visita' | 'Email' | 'Otro'
  resultado        TEXT,   -- 'Positivo' | 'Sin respuesta' | 'Negativo' | 'Pendiente'
  comentario       TEXT,
  fecha_gestion    DATE    NOT NULL DEFAULT CURRENT_DATE,
  fecha_seguimiento DATE,
  created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- ---- RLS (Row Level Security) ----
ALTER TABLE clientes_comunidad   ENABLE ROW LEVEL SECURITY;
ALTER TABLE ventas_comunidad     ENABLE ROW LEVEL SECURITY;
ALTER TABLE gestiones_comunidad  ENABLE ROW LEVEL SECURITY;

-- Acceso total con la anon key (igual que el CRM de cobranzas)
CREATE POLICY "anon_all_clientes"   ON clientes_comunidad   FOR ALL TO anon USING (true) WITH CHECK (true);
CREATE POLICY "anon_all_ventas"     ON ventas_comunidad     FOR ALL TO anon USING (true) WITH CHECK (true);
CREATE POLICY "anon_all_gestiones"  ON gestiones_comunidad  FOR ALL TO anon USING (true) WITH CHECK (true);

-- Índices para filtros frecuentes
CREATE INDEX IF NOT EXISTS idx_ventas_mes          ON ventas_comunidad (mes);
CREATE INDEX IF NOT EXISTS idx_ventas_razon        ON ventas_comunidad (razon_social);
CREATE INDEX IF NOT EXISTS idx_gestiones_razon     ON gestiones_comunidad (razon_social);
CREATE INDEX IF NOT EXISTS idx_gestiones_fecha     ON gestiones_comunidad (fecha_gestion DESC);
CREATE INDEX IF NOT EXISTS idx_clientes_vendedor   ON clientes_comunidad (vendedor);
CREATE INDEX IF NOT EXISTS idx_clientes_tipo       ON clientes_comunidad (tipo_cliente);
