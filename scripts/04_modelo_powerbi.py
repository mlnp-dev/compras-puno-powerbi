"""Escribe el modelo semántico (TMDL) del reporte de Power BI: powerbi/ComprasPuno.SemanticModel.

Lee los CSV que deja scripts/03_preparar_powerbi.R (data/powerbi/). La ruta a esa carpeta queda en el
parámetro de Power Query «CarpetaDatos»; si la carpeta de la actividad se mueve, basta con cambiarlo
en Power BI (Transformar datos > Administrar parámetros).

Uso:  python scripts/04_modelo_powerbi.py
"""
import os
import shutil
import textwrap

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELO = os.path.join(BASE, "powerbi", "ComprasPuno.SemanticModel")
DATOS = os.path.join(BASE, "data", "powerbi") + os.sep


def escribir(ruta, texto):
    """Guarda el texto con tabulaciones (TMDL) a partir de una sangría de 4 espacios."""
    lineas = []
    for l in textwrap.dedent(texto).strip("\n").split("\n"):
        n = len(l) - len(l.lstrip(" "))
        lineas.append("\t" * (n // 4) + " " * (n % 4) + l.lstrip(" "))
    ruta = os.path.join(MODELO, ruta)
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lineas) + "\n")


def columna(nombre, tipo, extra=""):
    nom = f"'{nombre}'" if any(c in nombre for c in " .=:'") else nombre
    resumen = "sum" if tipo in ("double", "decimal") and nombre == "total" else "none"
    bloque = f"""
    column {nom}
        dataType: {tipo}
        summarizeBy: {resumen}
        sourceColumn: {nombre}
"""
    for e in extra.split(";"):
        if e.strip():
            bloque += f"        {e.strip()}\n"
    return bloque


# ---------------------------------------------------------------- archivos fijos
# se reescribe toda la definición (Power BI Desktop la reformatea al guardar)
shutil.rmtree(os.path.join(MODELO, "definition"), ignore_errors=True)
os.makedirs(os.path.join(MODELO, "definition", "tables"), exist_ok=True)
with open(os.path.join(MODELO, "definition.pbism"), "w", encoding="utf-8") as f:
    f.write("""{
  "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
  "version": "4.2",
  "settings": {
    "qnaEnabled": true
  }
}
""")
with open(os.path.join(MODELO, ".platform"), "w", encoding="utf-8") as f:
    f.write("""{
  "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
  "metadata": {
    "type": "SemanticModel",
    "displayName": "ComprasPuno"
  },
  "config": {
    "version": "2.0",
    "logicalId": "7d0f3a52-6c1e-4f4b-9a7e-2b9c51e0a6d1"
  }
}
""")

escribir("definition/database.tmdl", """
database ComprasPuno
    compatibilityLevel: 1702
    compatibilityMode: powerBI
    language: 3082
""")

escribir("definition/model.tmdl", """
model Model
    culture: es-ES
    defaultPowerBIDataSourceVersion: powerBI_V3
    sourceQueryCulture: en-US
    dataAccessOptions
        legacyRedirects
        returnErrorValuesAsNull

    annotation __PBI_TimeIntelligenceEnabled = 0

ref table Compras
ref table Distritos
ref table Métrica
""")

ruta_m = DATOS.replace('"', '""')
escribir("definition/expressions.tmdl", f"""
/// Carpeta con compras.csv y distritos.csv (sale de scripts/03_preparar_powerbi.R)
expression CarpetaDatos = "{ruta_m}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]
""")

escribir("definition/relationships.tmdl", """
relationship 'Compras a Distritos'
    fromColumn: Compras.ubigeo
    toColumn: Distritos.ubigeo
""")

# ---------------------------------------------------------------- medidas
# (nombre, formato, carpeta, DAX, descripción)
MEDIDAS = [
    ("Monto", "\\S\\/ #,0", "Básicas", "SUM ( Compras[total] )",
     "Monto total de las órdenes, con IGV"),
    ("Órdenes", "#,0", "Básicas", "COUNTROWS ( Compras )", "Número de órdenes de compra"),
    ("Ticket promedio", "\\S\\/ #,0", "Básicas", "DIVIDE ( [Monto], [Órdenes] )",
     "Monto promedio por orden"),
    ("Proveedores", "#,0", "Básicas", "DISTINCTCOUNT ( Compras[ruc_proveedor] )",
     "Empresas distintas que recibieron al menos una orden"),
    ("Entidades", "#,0", "Básicas", "DISTINCTCOUNT ( Compras[ruc_entidad] )",
     "Entidades públicas distintas que compraron"),
    ("Meses con compras", "#,0", "Básicas", "DISTINCTCOUNT ( Compras[periodo] )", "Meses con al menos una orden"),
    ("Monto por mes", "\\S\\/ #,0", "Básicas", "DIVIDE ( [Monto], [Meses con compras] )", "Promedio mensual del monto"),
    ("Orden típica", "\\S\\/ #,0", "Básicas", "MEDIAN ( Compras[total] )", "Mediana del monto por orden"),
    ("Monto acumulado", "\\S\\/ #,0", "Comparación anual", """
        VAR m = MAX ( Compras[mes] )
        RETURN
            CALCULATE ( [Monto], Compras[mes] <= m, REMOVEFILTERS ( Compras[mes_nombre] ) )
     """, "Monto desde enero hasta el mes en curso, dentro de cada año"),
]

# variación del último año frente a los mismos meses del año anterior
for nombre, base in [("Monto", "[Monto]"), ("Órdenes", "[Órdenes]"), ("Ticket", "[Ticket promedio]"),
                     ("Proveedores", "[Proveedores]")]:
    MEDIDAS.append((f"Var % {nombre}", "0.0%", "Comparación anual", f"""
        VAR ult = MAX ( Compras[anio] )
        VAR mesmax = CALCULATE ( MAX ( Compras[mes] ), Compras[anio] = ult )
        VAR act = CALCULATE ( {base}, Compras[anio] = ult )
        VAR ant = CALCULATE ( {base}, Compras[anio] = ult - 1, Compras[mes] <= mesmax )
        RETURN
            IF ( NOT ISBLANK ( act ) && NOT ISBLANK ( ant ), DIVIDE ( act - ant, ant ) )
     """, f"Cambio de {nombre.lower()} del último año frente a los mismos meses del año anterior"))
    MEDIDAS.append((f"Etiqueta var {nombre}", "", "Comparación anual", f"""
        VAR v = [Var % {nombre}]
        VAR ult = MAX ( Compras[anio] )
        RETURN
            IF (
                ISBLANK ( v ),
                "Sin año anterior para comparar",
                IF ( v < 0, "▼ ", "▲ " ) & FORMAT ( ABS ( v ), "0.0%" ) & " vs " & ( ult - 1 )
            )
     """, f"Texto con la variación de {nombre.lower()}"))

MEDIDAS += [
    ("Monto regional", "\\S\\/ #,0", "Distrito de Puno", """
        CALCULATE (
            [Monto],
            REMOVEFILTERS ( Distritos ),
            REMOVEFILTERS ( Compras[zona], Compras[distrito], Compras[ubigeo] )
        )
     """, "Monto de toda la región, sin importar el distrito elegido"),
    ("% del monto regional", "0.0%", "Distrito de Puno", "DIVIDE ( [Monto], [Monto regional] )",
     "Qué parte del monto de la región representa la selección"),
    ("Monto distrito de Puno", "\\S\\/ #,0", "Distrito de Puno",
     "CALCULATE ( [Monto], Compras[zona] = \"Distrito de Puno\" )", "Monto de las entidades del distrito de Puno"),
    ("% distrito de Puno", "0.0%", "Distrito de Puno",
     "DIVIDE ( [Monto distrito de Puno], CALCULATE ( [Monto], REMOVEFILTERS ( Compras[zona] ) ) )",
     "Peso del distrito de Puno en el monto"),
    ("% órdenes distrito de Puno", "0.0%", "Distrito de Puno", """
        DIVIDE (
            CALCULATE ( [Órdenes], Compras[zona] = "Distrito de Puno" ),
            CALCULATE ( [Órdenes], REMOVEFILTERS ( Compras[zona] ) )
        )
     """, "Peso del distrito de Puno en las órdenes"),
    ("Veces el segundo distrito", "0.0", "Distrito de Puno", """
        VAR puno = CALCULATE ( [Monto], Compras[zona] = "Distrito de Puno" )
        VAR segundo =
            MAXX (
                FILTER ( ALL ( Distritos[ubigeo] ), Distritos[ubigeo] <> "210101" ),
                CALCULATE ( [Monto], REMOVEFILTERS ( Compras[zona] ) )
            )
        RETURN
            DIVIDE ( puno, segundo )
     """, "Cuántas veces el monto del distrito de Puno supera al del segundo distrito"),
    ("% monto a empresas de Puno", "0.0%", "Distrito de Puno",
     "DIVIDE ( CALCULATE ( [Monto], Compras[origen_proveedor] = \"Puno\" ), [Monto] )",
     "Parte del monto que se llevan empresas con domicilio en Puno"),
    # textos de ayuda (aparecen al pasar el mouse por las tarjetas)
    ("Ayuda monto", "", "Textos de ayuda", """
        "Todo el dinero que pagaron las entidades públicas por sus compras en los Catálogos Electrónicos de Perú Compras (con IGV). Equivale a unos "
            & "S/ " & FORMAT ( [Monto por mes], "#,0" ) & " al mes."
     """, "Explicación de la tarjeta Monto"),
    ("Ayuda órdenes", "", "Textos de ayuda", """
        "Cada orden es una compra concreta: una entidad le pide a una empresa productos del catálogo. Son unas "
            & FORMAT ( DIVIDE ( [Órdenes], [Meses con compras] ), "#,0" ) & " órdenes al mes, emitidas por "
            & FORMAT ( [Entidades], "#,0" ) & " entidades."
     """, "Explicación de la tarjeta Órdenes"),
    ("Ayuda ticket", "", "Textos de ayuda", """
        "Lo que cuesta en promedio una orden. Unas pocas compras muy grandes lo suben: la orden típica (mediana) es de "
            & "S/ " & FORMAT ( [Orden típica], "#,0" ) & ", es decir, la mitad de las órdenes cuesta menos que eso."
     """, "Explicación de la tarjeta Ticket promedio"),
    ("Ayuda proveedores", "", "Textos de ayuda", """
        "Empresas distintas que recibieron al menos una orden. Las empresas con domicilio en Puno se llevan solo el "
            & FORMAT ( [% monto a empresas de Puno], "0.0%" ) & " del dinero."
     """, "Explicación de la tarjeta Proveedores"),
    ("Titular distrito de Puno", "", "Textos de ayuda", """
        VAR segundo =
            TOPN (
                1,
                FILTER ( ALL ( Distritos[ubigeo], Distritos[distrito] ), Distritos[ubigeo] <> "210101" ),
                CALCULATE ( [Monto], REMOVEFILTERS ( Compras[zona] ) ), DESC
            )
        RETURN
            "El distrito de Puno concentra el " & FORMAT ( [% distrito de Puno], "0.0%" )
                & " del monto de la región: " & FORMAT ( [Veces el segundo distrito], "0.0" )
                & " veces lo que compra " & MAXX ( segundo, Distritos[distrito] ) & ", el segundo."
     """, "Frase resumen sobre el distrito de Puno"),
]


# medidas del análisis general (las mismas ideas del Shiny)
MEDIDAS += [
    ("Concentración top 10", "0.0%", "Proveedores", """
        DIVIDE (
            SUMX ( TOPN ( 10, VALUES ( Compras[ruc_proveedor] ), [Monto] ), [Monto] ),
            [Monto]
        )
     """, "Parte del monto que se llevan las 10 empresas que más venden"),
    ("Empresas para el 80%", "#,0", "Proveedores", """
        VAR t = ADDCOLUMNS ( VALUES ( Compras[ruc_proveedor] ), "@m", [Monto] )
        VAR tot = SUMX ( t, [@m] )
        VAR t2 =
            ADDCOLUMNS ( t, "@antes", VAR m = [@m] RETURN SUMX ( FILTER ( t, [@m] > m ), [@m] ) )
        RETURN
            COUNTROWS ( FILTER ( t2, [@antes] < 0.8 * tot ) )
     """, "Cuántas empresas, de mayor a menor, juntan el 80 % del monto (Pareto)"),
    ("Etiqueta Pareto", "", "Proveedores", """
        FORMAT ( [Empresas para el 80%], "#,0" ) & " de " & FORMAT ( [Proveedores], "#,0" ) & " ("
            & FORMAT ( DIVIDE ( [Empresas para el 80%], [Proveedores] ), "0.0%" ) & ")"
     """, "Texto: empresas que hacen el 80 % del monto"),
    ("Peso entidad principal", "0.0%", "Entidades", """
        DIVIDE ( MAXX ( VALUES ( Compras[ruc_entidad] ), [Monto] ), [Monto] )
     """, "Parte del monto que concentra la entidad que más compra"),
    ("Monto por entidad", "\S\/ #,0", "Entidades", "DIVIDE ( [Monto], [Entidades] )",
     "Monto promedio comprado por cada entidad"),
    ("Distritos con compras", "#,0", "Básicas", "DISTINCTCOUNT ( Compras[ubigeo] )",
     "Distritos con al menos una entidad que compró"),
    ("% de órdenes", "0.0%", "Exploración", "DIVIDE ( [Órdenes], CALCULATE ( [Órdenes], ALLSELECTED ( Compras[rango_monto] ) ) )",
     "Parte de las órdenes que cae en cada rango"),
    ("% del monto", "0.0%", "Exploración", "DIVIDE ( [Monto], CALCULATE ( [Monto], ALLSELECTED ( Compras[rango_monto] ) ) )",
     "Parte del monto que cae en cada rango"),
    ("Media por orden", "\S\/ #,0", "Exploración", "AVERAGE ( Compras[total] )", "Media del monto por orden"),
    ("Desviación estándar", "\S\/ #,0", "Exploración", "STDEV.P ( Compras[total] )", "Desviación estándar del monto por orden"),
    ("Mínimo", "\S\/ #,0.00", "Exploración", "MIN ( Compras[total] )", "Orden más pequeña"),
    ("Máximo", "\S\/ #,0", "Exploración", "MAX ( Compras[total] )", "Orden más grande"),
    ("Rango intercuartílico", "\S\/ #,0", "Exploración", "[Percentil 75] - [Percentil 25]",
     "Diferencia entre el percentil 75 y el 25: dónde está la mitad central de las órdenes"),
    ("Coef. de variación", "0.0%", "Exploración", "DIVIDE ( [Desviación estándar], [Media por orden] )",
     "Desviación estándar entre la media: más de 100 % indica mucha dispersión"),
    ("Percentil 25", "\S\/ #,0", "Exploración", "PERCENTILE.INC ( Compras[total], 0.25 )", "Primer cuartil"),
    ("Lectura distribución", "", "Exploración", """
        "La media (S/ " & FORMAT ( [Media por orden], "#,0" ) & ") es "
            & FORMAT ( DIVIDE ( [Media por orden], [Orden típica] ), "0.0" )
            & " veces la mediana (S/ " & FORMAT ( [Orden típica], "#,0" )
            & "): hay muchas compras pequeñas y unas pocas muy grandes que suben el promedio."
     """, "Explica en una frase cómo se reparte el monto de las órdenes"),
    ("Percentil 75", "\S\/ #,0", "Exploración", "PERCENTILE.INC ( Compras[total], 0.75 )", "Tercer cuartil"),
]


def bloque_medida(nombre, formato, carpeta, dax, desc):
    nom = f"'{nombre}'"
    dax = textwrap.dedent(dax).strip("\n")
    if "\n" in dax:
        cuerpo = "```\n" + "\n".join("            " + l for l in dax.split("\n")) + "\n            ```"
    else:
        cuerpo = dax
    txt = f"""
    /// {desc}
    measure {nom} = {cuerpo}
"""
    if formato:
        txt += f"        formatString: {formato}\n"
    txt += f"        displayFolder: {carpeta}\n"
    return txt


cols_compras = [
    ("orden", "string", ""), ("fecha", "dateTime", "formatString: dd/mm/yyyy"),
    ("anio", "int64", "formatString: 0"), ("mes", "int64", "formatString: 0; isHidden"),
    ("mes_nombre", "string", "sortByColumn: mes"), ("periodo", "dateTime", "formatString: mmm yyyy"),
    ("ruc_entidad", "string", ""), ("entidad", "string", ""), ("sector", "string", ""),
    ("provincia", "string", ""), ("distrito", "string", ""), ("ubigeo", "string", "isHidden"),
    ("zona", "string", ""), ("ruc_proveedor", "string", ""), ("proveedor", "string", ""),
    ("tipo_empresa", "string", ""), ("origen_proveedor", "string", ""), ("rubro", "string", ""),
    ("tipo_procedimiento", "string", ""), ("estado", "string", ""), ("rango_monto", "string", ""),
    ("total", "double", "formatString: \\S\\/ #,0.00"),
    ("dia_num", "int64", "formatString: 0; isHidden"), ("dia_semana", "string", "sortByColumn: dia_num"),
]
tipos_m = {"string": "type text", "int64": "Int64.Type", "double": "type number", "dateTime": "type date"}

txt = "table Compras\n"
for m in MEDIDAS:
    txt += bloque_medida(*m)
for c in cols_compras:
    txt += columna(*c)
transf = ", ".join(f'{{"{c}", {tipos_m[t]}}}' for c, t, _ in cols_compras)
txt += f"""
    partition Compras = m
        mode: import
        source =
            let
                Origen = Csv.Document(File.Contents(CarpetaDatos & "compras.csv"), [Delimiter = ",", Columns = {len(cols_compras)}, Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
                Encabezados = Table.PromoteHeaders(Origen, [PromoteAllScalars = true]),
                Tipos = Table.TransformColumnTypes(Encabezados, {{{transf}}}, "en-US")
            in
                Tipos
"""
escribir("definition/tables/Compras.tmdl", txt)

cols_dist = [
    ("ubigeo", "string", ""), ("distrito", "string", "dataCategory: City"), ("provincia", "string", ""),
    ("latitud", "double", "dataCategory: Latitude; formatString: 0.00000"),
    ("longitud", "double", "dataCategory: Longitude; formatString: 0.00000"),
    ("zona", "string", ""), ("lugar", "string", "dataCategory: Place"),
]
txt = "table Distritos\n"
for c in cols_dist:
    txt += columna(*c)
transf = ", ".join(f'{{"{c}", {tipos_m[t]}}}' for c, t, _ in cols_dist)
txt += f"""
    partition Distritos = m
        mode: import
        source =
            let
                Origen = Csv.Document(File.Contents(CarpetaDatos & "distritos.csv"), [Delimiter = ",", Columns = {len(cols_dist)}, Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
                Encabezados = Table.PromoteHeaders(Origen, [PromoteAllScalars = true]),
                Tipos = Table.TransformColumnTypes(Encabezados, {{{transf}}}, "en-US")
            in
                Tipos
"""
escribir("definition/tables/Distritos.tmdl", txt)
# ---------------------------------------------------------------- selector de métrica
# Tabla desconectada: el botón Monto / Órdenes / Empresas elige qué muestran los gráficos.
METRICA = "SELECTEDVALUE ( 'Métrica'[Métrica], \"Monto\" )"
MEDIDAS_METRICA = [
    ("Valor", "Selector", """
        SWITCH (
            SELECTEDVALUE ( 'Métrica'[Métrica], "Monto" ),
            "Órdenes", [Órdenes],
            "Empresas", [Proveedores],
            [Monto]
        )
     """, "Monto, órdenes o empresas según el botón elegido"),
    ("Valor acumulado", "Selector", """
        VAR m = MAX ( Compras[mes] )
        RETURN
            CALCULATE ( [Valor], Compras[mes] <= m, REMOVEFILTERS ( Compras[mes_nombre] ) )
     """, "La métrica elegida, acumulada desde enero dentro de cada año"),
    ("% del total", "Selector", """
        DIVIDE ( [Valor], CALCULATE ( [Valor], ALLSELECTED () ) )
     """, "Parte del total visible que representa el elemento"),
]
TITULOS = [
    ("Título evolución", "\"¿Cómo evoluciona \" & IF ( " + METRICA + " = \"Monto\", \"el gasto\", \"el número de \" & LOWER ( " + METRICA + " ) ) & \"?\""),
    ("Título rubros", "\"Rubros con más \" & LOWER ( " + METRICA + " )"),
    ("Título sectores", METRICA + " & \" por sector de la entidad\""),
    ("Título distritos", "\"Distritos con más \" & LOWER ( " + METRICA + " )"),
    ("Título mapa", METRICA + " & \" por distrito\""),
]
NL, TAB = chr(10), chr(9)
FORMATO_VALOR = "IF ( " + METRICA + " = \"Monto\", \"\\S\\/ #,0\", \"#,0\" )"
extra = ""
for nombre, carpeta, dax, desc in MEDIDAS_METRICA:
    extra += bloque_medida(nombre, "", carpeta, dax, desc).rstrip(NL) + NL
    if nombre == "% del total":
        extra += "        formatString: 0.0%" + NL
    else:
        extra += "        formatStringDefinition = " + FORMATO_VALOR + NL
for nombre, dax in TITULOS:
    extra += bloque_medida(nombre, "", "Textos de ayuda", dax, "Título dinámico según la métrica elegida")
lineas = []
for l in extra.strip(NL).split(NL):
    n = len(l) - len(l.lstrip(" "))
    lineas.append(TAB * (n // 4) + l.lstrip(" "))
ruta = os.path.join(MODELO, "definition", "tables", "Compras.tmdl")
contenido = open(ruta, encoding="utf-8").read()
contenido = contenido.replace("table Compras" + NL, "table Compras" + NL + NL + NL.join(lineas) + NL, 1)
open(ruta, "w", encoding="utf-8", newline=NL).write(contenido)

escribir("definition/tables/Métrica.tmdl", """
table Métrica

    column Métrica
        dataType: string
        summarizeBy: none
        sourceColumn: [Métrica]
        sortByColumn: Orden

    column Orden
        dataType: int64
        isHidden
        formatString: 0
        summarizeBy: none
        sourceColumn: [Orden]

    partition Métrica = calculated
        mode: import
        source = DATATABLE ( "Métrica", STRING, "Orden", INTEGER, { { "Monto", 1 }, { "Órdenes", 2 }, { "Empresas", 3 } } )
""")

print("modelo escrito en", MODELO, "·", len(MEDIDAS), "medidas")
