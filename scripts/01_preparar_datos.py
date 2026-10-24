"""Prepara el dataset de compras públicas de la región Puno (Perú Compras).

Entrada
  data/raw/ReportePCBienesAAAAMM.csv  -> órdenes de compra de todo el Perú, un archivo por mes
  data/ref/ruc_ubigeo.csv             -> ubigeo de cada RUC, sacado del padrón reducido de SUNAT
                                         (si no existe, se arma con --padron RUTA_AL_ZIP)
  data/ref/geo/peru_distrital.geojson -> límites distritales INEI (github.com/juaneladio/peru-geojson)
Salida
  data/compras_puno_2025_2026.csv     -> para Shiny
  data/compras_puno_2025_2026.xlsx    -> para Power BI (los números ya van tipados)
  data/ref/geo/puno_distritos.geojson -> solo los 110 distritos de Puno, para los mapas

Una orden se considera "de Puno" cuando el RUC de la entidad compradora tiene domicilio
fiscal en el departamento de Puno (ubigeo 21xxxx), según el padrón de SUNAT. El dataset
de Perú Compras no trae una columna de región.

Uso:  python scripts/01_preparar_datos.py [--padron C:/ruta/padron_reducido_ruc.zip]
"""
import argparse
import glob
import io
import json
import os
import re
import zipfile

import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, "data", "raw")
REF = os.path.join(BASE, "data", "ref")
OUT = os.path.join(BASE, "data")

DEPARTAMENTOS = {
    "01": "AMAZONAS", "02": "ANCASH", "03": "APURIMAC", "04": "AREQUIPA", "05": "AYACUCHO",
    "06": "CAJAMARCA", "07": "CALLAO", "08": "CUSCO", "09": "HUANCAVELICA", "10": "HUANUCO",
    "11": "ICA", "12": "JUNIN", "13": "LA LIBERTAD", "14": "LAMBAYEQUE", "15": "LIMA",
    "16": "LORETO", "17": "MADRE DE DIOS", "18": "MOQUEGUA", "19": "PASCO", "20": "PIURA",
    "21": "PUNO", "22": "SAN MARTIN", "23": "TACNA", "24": "TUMBES", "25": "UCAYALI",
}
PROVINCIAS_PUNO = {
    "2101": "PUNO", "2102": "AZANGARO", "2103": "CARABAYA", "2104": "CHUCUITO",
    "2105": "EL COLLAO", "2106": "HUANCANE", "2107": "LAMPA", "2108": "MELGAR",
    "2109": "MOHO", "2110": "SAN ANTONIO DE PUTINA", "2111": "SAN ROMAN",
    "2112": "SANDIA", "2113": "YUNGUYO",
}
MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Set", "Oct", "Nov", "Dic"]

# Nombres cortos de columnas (el original trae tildes que se rompen según la codificación)
COLUMNAS = ["fecha_proceso", "ruc_proveedor", "proveedor", "ruc_entidad", "entidad",
            "tipo_procedimiento", "orden", "url_orden", "estado", "doc_estado",
            "fecha_formalizacion", "fecha_ultimo_estado", "sub_total", "igv", "total",
            "url_orden_digitalizada", "descripcion_estado", "cesion_derechos", "acuerdo_marco"]


def leer_ordenes():
    partes = []
    for f in sorted(glob.glob(os.path.join(RAW, "ReportePCBienes*.csv"))):
        df = pd.read_csv(f, sep=";", encoding="latin-1", dtype=str)
        df.columns = COLUMNAS
        df["archivo_mes"] = os.path.basename(f)[-10:-4]
        partes.append(df)
    return pd.concat(partes, ignore_index=True)


def armar_ruc_ubigeo(ordenes, ruta_zip):
    """Saca del padrón de SUNAT solo los RUC que aparecen en las órdenes."""
    rucs = set(ordenes["ruc_entidad"]) | set(ordenes["ruc_proveedor"])
    filas = []
    with zipfile.ZipFile(ruta_zip) as z:
        nombre = z.namelist()[0]
        with z.open(nombre) as fh:
            for linea in io.TextIOWrapper(fh, encoding="latin-1", errors="replace"):
                ruc = linea[:11]
                if ruc in rucs:
                    c = linea.rstrip("\n").split("|")
                    # RUC|NOMBRE|ESTADO|CONDICION|UBIGEO|...
                    filas.append((c[0], c[2].strip(), c[3].strip(), c[4].strip()))
    ref = pd.DataFrame(filas, columns=["ruc", "estado_sunat", "condicion_sunat", "ubigeo"])
    os.makedirs(REF, exist_ok=True)
    ref.to_csv(os.path.join(REF, "ruc_ubigeo.csv"), index=False)
    print(f"Padrón SUNAT: {len(ref):,} de {len(rucs):,} RUC encontrados")
    return ref


def clasificar_sector(nombre):
    n = nombre.upper()
    if any(k in n for k in ("SALUD", "REDESS", "REDEES", "HOSPITAL", "RED DE ", "DIRESA")):
        return "Salud"
    if "UNIVERSIDAD" in n:
        return "Universidades"
    if any(k in n for k in ("EDUCACION", "EDUCATIVA", "UGEL")):
        return "Educación"
    if any(k in n for k in ("E.P.S.", "EMP.", "EMPRESA", "SEDA")):
        return "Empresas públicas"
    if "MUNICIP" in n:
        return "Municipalidades"
    if any(k in n for k in ("CORTE", "JUSTICIA", "POLICIA", "INPE", "FISCAL")):
        return "Justicia y seguridad"
    if any(k in n for k in ("GOBIERNO REGIONAL", "DIRECCION", "PROYECTO ESPECIAL", "PROGRAMA REGIONAL")):
        return "Gobierno Regional"
    return "Otras entidades"


def tipo_empresa(ruc, razon_social):
    """Forma societaria a partir del RUC (10 = persona natural) y del final de la razón social."""
    if ruc.startswith("10"):
        return "Persona natural"
    r = razon_social.upper()
    if "INDIVIDUAL DE RESPONSABIL" in r:
        return "E.I.R.L."
    if "ANONIMA CERRADA" in r or "ANÓNIMA CERRADA" in r:
        return "S.A.C."
    if "RESPONSABILIDAD LIMITADA" in r:
        return "S.R.L."
    # últimas letras sin puntos, espacios ni símbolos: "S.R.LTDA." -> "SRLTDA"
    letras = re.sub(r"[^A-Z]", "", r.split("-")[0])[-8:] if "-" in r[-10:] else re.sub(r"[^A-Z]", "", r)[-8:]
    for fin, etiqueta in (("EIRLTDA", "E.I.R.L."), ("EIRL", "E.I.R.L."), ("SRLTDA", "S.R.L."), ("SCRL", "S.R.L."),
                          ("SRL", "S.R.L."), ("SACS", "S.A.C."), ("SAC", "S.A.C."), ("SAA", "S.A.A."), ("SA", "S.A.")):
        if letras.endswith(fin):
            return etiqueta
    return "Otra forma"


def rango_monto(x):
    if x < 1_000:
        return "1. Menos de S/ 1 mil"
    if x < 5_000:
        return "2. S/ 1 mil - 5 mil"
    if x < 30_000:
        return "3. S/ 5 mil - 30 mil"
    if x < 100_000:
        return "4. S/ 30 mil - 100 mil"
    return "5. Más de S/ 100 mil"


def distritos_puno():
    """Recorta el GeoJSON nacional a Puno y devuelve {ubigeo: nombre del distrito}."""
    geo = os.path.join(REF, "geo")
    with open(os.path.join(geo, "peru_distrital.geojson"), encoding="utf-8") as f:
        peru = json.load(f)
    feats = [ft for ft in peru["features"] if ft["properties"]["IDDPTO"] == "21"]
    for ft in feats:
        pr = ft["properties"]
        ft["properties"] = {"ubigeo": pr["IDDIST"], "distrito": pr["NOMBDIST"], "provincia": pr["NOMBPROV"]}
    with open(os.path.join(geo, "puno_distritos.geojson"), "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": feats}, f, ensure_ascii=False)
    nombres = {ft["properties"]["ubigeo"]: ft["properties"]["distrito"] for ft in feats}
    # San Miguel (San Román) se creó en 2016 a partir de Juliaca y no está en ese mapa
    nombres.setdefault("211105", "SAN MIGUEL")
    return nombres


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--padron", help="ruta a padron_reducido_ruc.zip de SUNAT")
    args = ap.parse_args()

    o = leer_ordenes()
    print(f"Órdenes leídas (todo el Perú): {len(o):,}")

    ruta_ref = os.path.join(REF, "ruc_ubigeo.csv")
    if args.padron:
        ref = armar_ruc_ubigeo(o, args.padron)
    else:
        ref = pd.read_csv(ruta_ref, dtype=str)
    ubi = dict(zip(ref["ruc"], ref["ubigeo"].fillna("")))

    o["ubigeo_entidad"] = o["ruc_entidad"].map(ubi).fillna("")
    o = o[o["ubigeo_entidad"].str.startswith("21")].copy()
    print(f"Órdenes de entidades con domicilio en Puno: {len(o):,}")

    # tipos
    for c in ("sub_total", "igv", "total"):
        o[c] = pd.to_numeric(o[c])
    o["fecha_formalizacion"] = pd.to_datetime(o["fecha_formalizacion"])
    o["fecha_ultimo_estado"] = pd.to_datetime(o["fecha_ultimo_estado"])

    # columnas derivadas
    o["fecha"] = o["fecha_formalizacion"].dt.date
    o["anio"] = o["fecha_formalizacion"].dt.year
    o["mes"] = o["fecha_formalizacion"].dt.month
    o["nombre_mes"] = o["mes"].map(lambda m: MESES[m - 1])
    o["periodo"] = o["fecha_formalizacion"].dt.strftime("%Y-%m")
    o["provincia_entidad"] = o["ubigeo_entidad"].str[:4].map(PROVINCIAS_PUNO)
    o["distrito_entidad"] = o["ubigeo_entidad"].map(distritos_puno())

    # un mismo RUC puede venir escrito de varias formas: se usa el nombre más frecuente
    nombre_entidad = o.groupby("ruc_entidad")["entidad"].agg(lambda s: s.value_counts().index[0])
    o["entidad"] = o["ruc_entidad"].map(nombre_entidad).str.strip()
    o["sector"] = o["entidad"].map(clasificar_sector)

    o["proveedor"] = o["proveedor"].str.replace(r"\s+", " ", regex=True).str.strip()
    o["tipo_empresa"] = [tipo_empresa(r, n) for r, n in zip(o["ruc_proveedor"], o["proveedor"])]
    o["ubigeo_proveedor"] = o["ruc_proveedor"].map(ubi).fillna("")
    o["departamento_proveedor"] = o["ubigeo_proveedor"].str[:2].map(DEPARTAMENTOS).fillna("SIN DATO")
    o["origen_proveedor"] = o["departamento_proveedor"].map(
        lambda d: "Puno" if d == "PUNO" else ("Lima y Callao" if d in ("LIMA", "CALLAO")
                                              else ("Persona natural (sin domicilio publicado)" if d == "SIN DATO"
                                                    else "Otras regiones")))
    o["estado"] = o["estado"].str.strip()
    o["rango_monto"] = o["total"].map(rango_monto)
    o["dias_hasta_estado"] = (o["fecha_ultimo_estado"] - o["fecha_formalizacion"]).dt.days
    o["acuerdo_marco"] = o["acuerdo_marco"].str.strip()

    final = o[["orden", "fecha", "anio", "mes", "nombre_mes", "periodo",
               "ruc_entidad", "entidad", "sector", "provincia_entidad", "distrito_entidad", "ubigeo_entidad",
               "ruc_proveedor", "proveedor", "tipo_empresa", "departamento_proveedor", "origen_proveedor",
               "acuerdo_marco", "tipo_procedimiento", "estado",
               "sub_total", "igv", "total", "rango_monto", "dias_hasta_estado"]]
    final = final.sort_values(["fecha", "orden"]).reset_index(drop=True)

    final.to_csv(os.path.join(OUT, "compras_puno_2025_2026.csv"), index=False, encoding="utf-8-sig")
    final.to_excel(os.path.join(OUT, "compras_puno_2025_2026.xlsx"), index=False, sheet_name="compras")
    print(f"\nGuardado: {len(final):,} órdenes | S/ {final['total'].sum():,.0f} | "
          f"{final['ruc_proveedor'].nunique()} proveedores | {final['ruc_entidad'].nunique()} entidades")


if __name__ == "__main__":
    main()
