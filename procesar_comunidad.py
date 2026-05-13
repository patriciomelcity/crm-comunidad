#!/usr/bin/env python3
"""
procesar_comunidad.py
Procesa archivos ZIP de ventas y sube datos de clientes Comunidad a Supabase.

Uso:
  python procesar_comunidad.py                          # procesa ZIPs en carpeta actual
  python procesar_comunidad.py ventas_jun2026.zip       # un solo ZIP (actualización diaria)
  python procesar_comunidad.py C:/ruta/carpeta/         # todos los ZIPs de una carpeta
  python procesar_comunidad.py --clientes listado.xlsx  # solo actualiza metadatos (tel, email)
  python procesar_comunidad.py archivo.zip --clientes listado.xlsx  # ambos

Para la carga histórica inicial, apuntar a la carpeta con todos los ZIPs:
  python procesar_comunidad.py "C:/ruta/analisis clientes comunidad" --clientes "C:/ruta/MEL CITY S.A_Listado_de_clientes.xlsx"
"""

import sys
import io
import re
import zipfile
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ── Supabase ────────────────────────────────────────────────────────────────
SUPA_URL = "https://cclzkqzrwhedkkmigfis.supabase.co"
SUPA_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNjbHprcXpyd2hlZGtrbWlnZmlzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzM5NjMxNDEsImV4cCI6MjA4OTUzOTE0MX0"
    ".WRdKrnZ_ZxzFwj4fXIoi_LUWlABcSoEP9ec3X7lHV58"
)
HEADERS = {
    "apikey": SUPA_KEY,
    "Authorization": f"Bearer {SUPA_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates",
}

# ── Constantes del archivo de ventas ────────────────────────────────────────
# Los ZIPs tienen un Excel con fila 0-1 = título, fila 2 = headers, datos desde fila 3
COL_REFERENCIA  = 0   # 'Encabezado' en filas de datos reales
COL_NRO_COMP    = 9   # Nro. comprobante (para deduplicar)
COL_TIPO_COMP   = 8   # Tipo comprob. (FCA, FCB, RE…)
COL_TIPO_CLI    = 14  # Tipo de cliente
COL_RAZON       = 18  # Razón social
COL_VENDEDOR    = 28  # Vendedor
COL_TOTAL       = 55  # Total comprobante (col 56 = Usuario)

TIPOS_OK = {"FCA", "FCB", "RE"}

# ── Constantes del listado de clientes ──────────────────────────────────────
CLI_RAZON    = 6
CLI_TIPO     = 11
CLI_TEL      = 13
CLI_TEL2     = 14
CLI_EMAIL    = 15
CLI_VENDEDOR = 33


# ── Utilidades ───────────────────────────────────────────────────────────────

def zip_info(path: Path):
    """Extrae (mes 'YYYY-MM', fecha_fin datetime) del nombre del ZIP."""
    dates = re.findall(r"(\d{2}-\d{2}-\d{4})", path.name)
    if not dates:
        return None, None
    # Usa la segunda fecha (fin del período) si existe, si no la única
    raw = dates[1] if len(dates) >= 2 else dates[0]
    d, m, y = raw.split("-")
    return f"{y}-{m}", datetime(int(y), int(m), int(d))


def str_val(v):
    s = str(v).strip()
    return None if s in ("nan", "None", "") else s


def upsert(table: str, records: list):
    if not records:
        return
    resp = requests.post(
        f"{SUPA_URL}/rest/v1/{table}",
        headers=HEADERS,
        json=records,
    )
    if resp.status_code not in (200, 201):
        print(f"  ❌ Error en {table}: {resp.status_code} — {resp.text[:300]}")
    return resp.status_code


# ── Procesamiento de ZIPs ────────────────────────────────────────────────────

def read_ventas_from_zip(zip_path: Path):
    """Lee un ZIP y devuelve {razon_social: importe_total} para clientes Comunidad."""
    with zipfile.ZipFile(zip_path) as z:
        excels = [f for f in z.namelist() if f.lower().endswith(".xlsx")]
        if not excels:
            return {}
        with z.open(excels[0]) as f:
            df = pd.read_excel(f, header=None)

    data = df.iloc[3:].copy()
    data.columns = range(len(df.columns))

    # Solo filas de tipo "Encabezado"
    data = data[data[COL_REFERENCIA] == "Encabezado"]
    # Solo comprobantes válidos
    data = data[data[COL_TIPO_COMP].isin(TIPOS_OK)]
    # Solo clientes Comunidad
    mask = data[COL_TIPO_CLI].astype(str).str.lower().str.contains("comunidad", na=False)
    data = data[mask]
    # Dedup por número de comprobante
    data = data.drop_duplicates(subset=[COL_NRO_COMP], keep="first")

    data[COL_TOTAL] = pd.to_numeric(data[COL_TOTAL], errors="coerce").fillna(0)
    result = data.groupby(data[COL_RAZON].astype(str).str.strip())[COL_TOTAL].sum()
    return result.to_dict()


def process_zips(zip_files: list):
    """
    Para cada mes, usa solo el ZIP con la fecha fin más tardía
    (evita doble conteo cuando hay un ZIP parcial + uno completo del mismo mes).
    """
    # Selección: por mes, queda el ZIP con mayor end_date
    best: dict[str, tuple[Path, datetime]] = {}
    for zp in zip_files:
        mes, end = zip_info(zp)
        if mes and end:
            if mes not in best or end > best[mes][1]:
                best[mes] = (zp, end)

    print(f"\n{'─'*55}")
    print(f"  Meses a procesar: {len(best)}")
    print(f"{'─'*55}")

    for mes, (zp, _) in sorted(best.items()):
        print(f"\n  → {mes}  ({zp.name})")
        ventas = read_ventas_from_zip(zp)
        if not ventas:
            print("    (sin datos Comunidad)")
            continue

        total = sum(ventas.values())
        print(f"    {len(ventas)} clientes | ${total:,.0f}")

        records = [
            {"razon_social": k, "mes": mes, "importe": round(float(v), 2)}
            for k, v in ventas.items()
        ]
        sc = upsert("ventas_comunidad", records)
        if sc in (200, 201):
            print(f"    ✓ {len(records)} registros subidos")


# ── Actualización de metadatos de clientes ───────────────────────────────────

def process_clientes(xlsx_path: Path):
    print(f"\n{'─'*55}")
    print(f"  Leyendo {xlsx_path.name} …")
    print(f"{'─'*55}")

    df = pd.read_excel(xlsx_path, header=None)
    data = df.iloc[3:].copy()
    data.columns = range(len(df.columns))

    mask = data[CLI_TIPO].astype(str).str.lower().str.contains("comunidad", na=False)
    data = data[mask]

    records = []
    seen = set()
    for _, row in data.iterrows():
        razon = str_val(row[CLI_RAZON])
        if not razon or razon in seen:
            continue
        seen.add(razon)
        records.append({
            "razon_social": razon,
            "tipo_cliente":  str_val(row[CLI_TIPO]),
            "vendedor":      str_val(row[CLI_VENDEDOR]),
            "telefono":      str_val(row[CLI_TEL]),
            "telefono2":     str_val(row[CLI_TEL2]),
            "email":         str_val(row[CLI_EMAIL]),
        })

    print(f"  {len(records)} clientes Comunidad encontrados")
    sc = upsert("clientes_comunidad", records)
    if sc in (200, 201):
        print(f"  ✓ Metadatos actualizados en Supabase")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    args = list(sys.argv[1:])

    # --clientes flag
    clientes_file = None
    if "--clientes" in args:
        idx = args.index("--clientes")
        if idx + 1 < len(args):
            clientes_file = Path(args[idx + 1])
            args = args[:idx] + args[idx + 2:]
        else:
            print("Error: --clientes requiere un archivo .xlsx")
            sys.exit(1)

    # Determinar fuente de ZIPs
    if not args:
        folder = Path(__file__).parent
        zip_files = sorted(folder.glob("MEL CITY*.zip"))
    else:
        target = Path(args[0])
        if target.is_dir():
            zip_files = sorted(target.glob("MEL CITY*.zip"))
        elif target.suffix.lower() == ".zip":
            zip_files = [target]
        else:
            print(f"Error: '{target}' no es un archivo ZIP ni una carpeta.")
            sys.exit(1)

    print("\n" + "═" * 55)
    print("  PROCESADOR COMUNIDAD CLEANCITI")
    print("═" * 55)

    if zip_files:
        process_zips(zip_files)
    elif not clientes_file:
        print("  ⚠️  No se encontraron archivos ZIP.")

    if clientes_file:
        process_clientes(clientes_file)

    print(f"\n{'═'*55}")
    print("  ✅ Listo!")
    print("═" * 55 + "\n")


if __name__ == "__main__":
    main()
