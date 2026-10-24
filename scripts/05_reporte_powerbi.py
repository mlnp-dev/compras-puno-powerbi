"""Genera el reporte de Power BI (formato PBIR) en powerbi/ComprasPuno.Report.

Diseño adaptado de dos plantillas de referencia: menú lateral azul marino con las páginas, área clara
con tarjetas blancas, banda oscura arriba, cifras sobre ondas azules o verde azulado y un mapa claro
con burbujas azules. Las páginas siguen la app Shiny: Resumen, Proveedores, Entidades, Mapa,
Exploración (EDA) y Datos, más una ventana emergente con mini gráfico.

Interacción: selector Monto / Órdenes / Empresas, clic que filtra los demás gráficos, ventana
emergente al pasar el mouse y botón para restablecer los filtros.

Requiere el esqueleto (powerbi-report-author scaffold ...), el modelo de scripts/04_modelo_powerbi.py
y las imágenes de scripts/06_recursos_powerbi.py.

Uso:  python scripts/05_reporte_powerbi.py
"""
import hashlib
import itertools
import json
import os
import shutil
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REP = os.path.join(BASE, "powerbi", "ComprasPuno.Report")
DEF = os.path.join(REP, "definition")
PAGES = os.path.join(DEF, "pages")
RECURSOS = os.path.join(BASE, "powerbi", "recursos")
REG = os.path.join(REP, "StaticResources", "RegisteredResources")

SCH_VISUAL = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.9.0/schema.json"
SCH_PAGE = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"
SCH_PAGES = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json"

MEMB = 64                   # franja blanca del membrete institucional (arriba de todo)
W, H = 1280, 720 + MEMB
X0, XF = 216, 1264          # área de trabajo (a la derecha del menú lateral)
ANCHO = XF - X0
AZUL, TEAL, MARINO, CELESTE = "#2F6FED", "#2BB39B", "#14213D", "#9CC3FF"
NARANJA, INDIGO, AMBAR, GRIS = "#F07B3F", "#6366F1", "#F2B544", "#94A3B8"
TEXTO, SUAVE, REJILLA, BLANCO = "#1E293B", "#64748B", "#E8EDF5", "#FFFFFF"
MENU_TXT, MENU_HOVER = "#B8C4DB", "#22355C"
PALETA = [AZUL, TEAL, MARINO, CELESTE, NARANJA, INDIGO, AMBAR, GRIS]
CONTADOR = itertools.count()
IMAGENES = {}

PAGINAS = [("resumen", "Resumen", "▦"), ("proveedores", "Proveedores", "◧"), ("entidades", "Entidades", "▣"),
           ("mapa", "Mapa", "◉"), ("eda", "Exploración", "◔"), ("datos", "Datos", "☰")]


# ---------------------------------------------------------------- expresiones PBIR
def lit(v):
    if isinstance(v, bool):
        s = "true" if v else "false"
    elif isinstance(v, (int, float)):
        s = f"{v}D"
    else:
        s = "'" + str(v).replace("'", "''") + "'"
    return {"expr": {"Literal": {"Value": s}}}


def color(hex_):
    return {"solid": {"color": lit(hex_)}}


def props(**kw):
    return {k: (color(v) if isinstance(v, str) and v.startswith("#") and len(v) == 7 else lit(v))
            for k, v in kw.items()}


def obj(sel=None, **kw):
    o = {"properties": props(**kw)}
    if sel is not None:
        o["selector"] = {"id": sel}
    return [o]


def campo(tabla, nombre, medida=False):
    return {"Measure" if medida else "Column": {"Expression": {"SourceRef": {"Entity": tabla}}, "Property": nombre}}


def proy(tabla, nombre, medida=False, visible=None):
    p = {"field": campo(tabla, nombre, medida), "queryRef": f"{tabla}.{nombre}", "nativeQueryRef": nombre}
    if visible:
        p["displayName"] = visible
    return p


def M(nombre, visible=None):
    return proy("Compras", nombre, True, visible)


def C(nombre, tabla="Compras", visible=None):
    return proy(tabla, nombre, False, visible)


def promedio(tabla, columna):
    return {"field": {"Aggregation": {"Expression": campo(tabla, columna), "Function": 1}},
            "queryRef": f"Avg({tabla}.{columna})", "nativeQueryRef": f"Promedio de {columna}"}


def nid(*partes):
    return hashlib.md5("|".join(map(str, partes)).encode()).hexdigest()[:20]


def imagen(nombre):
    return {"expr": {"ResourcePackageItem": {"PackageName": "RegisteredResources", "PackageType": 1,
                                             "ItemName": IMAGENES[nombre]}}}


def sin_marco(pad=0):
    return {"background": obj(show=False), "border": obj(show=False), "dropShadow": obj(show=False),
            "visualHeader": obj(show=False), "title": obj(show=False),
            "padding": obj(top=pad, bottom=pad, left=pad, right=pad)}


def tarjeta_blanca(titulo=None, subtitulo=None, titulo_medida=None, tooltip=None, pad=12):
    """Contenedor de la plantilla: tarjeta blanca, esquinas redondeadas y sombra suave."""
    vco = {"background": obj(show=True, color=BLANCO, transparency=0),
           "border": obj(show=True, color="#E3E8F0", radius=14, width=1),
           "dropShadow": obj(show=True, color="#1E293B", transparency=90, position="Outer", preset="Custom",
                             shadowBlur=18, shadowDistance=4, angle=90),
           "padding": obj(top=pad, bottom=pad, left=pad + 2, right=pad + 2),
           "visualHeader": obj(show=False)}
    if titulo or titulo_medida:
        t = props(show=True, fontColor=TEXTO, fontSize=12, bold=True, fontFamily="Segoe UI Semibold")
        t["text"] = {"expr": campo("Compras", titulo_medida, True)} if titulo_medida else lit(titulo)
        vco["title"] = [{"properties": t}]
    else:
        vco["title"] = obj(show=False)
    vco["subTitle"] = (obj(show=True, text=subtitulo, fontColor=SUAVE, fontSize=9) if subtitulo
                       else obj(show=False))
    if tooltip:
        vco["visualTooltip"] = [{"properties": {**props(show=True, type="Canvas"), "section": lit(tooltip)}}]
    return vco


def ejes(unidades=0, mostrar_valor=True):
    return {"categoryAxis": [{"properties": props(showAxisTitle=False, fontSize=9, labelColor=SUAVE,
                                                  gridlineShow=False)}],
            "valueAxis": [{"properties": props(show=mostrar_valor, showAxisTitle=False, fontSize=9,
                                               labelColor=SUAVE, labelDisplayUnits=unidades,
                                               gridlineColor=REJILLA, gridlineStyle="dashed")}]}


def orden(pr, direccion="Descending"):
    return {"sort": [{"field": pr["field"], "direction": direccion}], "isDefaultSort": True}


def top_n(tabla, columna, n):
    return {
        "name": "Filtro" + nid("top", tabla, columna, n, next(CONTADOR)),
        "field": campo(tabla, columna), "type": "TopN",
        "filter": {"Version": 2, "From": [
            {"Name": "subquery", "Expression": {"Subquery": {"Query": {
                "Version": 2,
                "From": [{"Name": "c", "Entity": tabla, "Type": 0}] +
                        ([{"Name": "o", "Entity": "Compras", "Type": 0}] if tabla != "Compras" else []),
                "Select": [{"Column": {"Expression": {"SourceRef": {"Source": "c"}}, "Property": columna},
                            "Name": "field"}],
                "OrderBy": [{"Direction": 2, "Expression": {"Aggregation": {
                    "Expression": {"Column": {"Expression": {"SourceRef": {"Source": "c" if tabla == "Compras" else "o"}},
                                              "Property": "total"}}, "Function": 0}}}],
                "Top": n}}}, "Type": 2},
            {"Name": "t", "Entity": tabla, "Type": 0}],
            "Where": [{"Condition": {"In": {
                "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "t"}}, "Property": columna}}],
                "Table": {"SourceRef": {"Source": "subquery"}}}}}]},
        "howCreated": "User"}


# ---------------------------------------------------------------- página
class Pagina:
    def __init__(self, clave, nombre, tooltip=False):
        self.clave, self.id, self.nombre, self.tooltip = clave, nid("pagina", clave), nombre, tooltip
        self.visuales, self.z = [], 1000
        if not tooltip:
            membrete(self)

    def add(self, clave, tipo, x, y, w, h, query=None, objects=None, vco=None, filtros=None, fijo=False):
        # Todo el diseño se corre hacia abajo para dejar sitio al membrete (menos el propio membrete).
        if not self.tooltip and not fijo:
            y += MEMB
        v = {"visualType": tipo}
        if query:
            v["query"] = query
        if objects:
            v["objects"] = objects
        if vco:
            v["visualContainerObjects"] = vco
        if tipo not in ("slicer", "textbox", "image", "actionButton"):
            v["drillFilterOtherVisuals"] = True
        cont = {"$schema": SCH_VISUAL, "name": nid(self.id, clave),
                "position": {"x": x, "y": y, "z": self.z, "height": h, "width": w, "tabOrder": self.z},
                "visual": v}
        if filtros:
            cont["filterConfig"] = {"filters": filtros}
        if tipo == "actionButton":
            cont["howCreated"] = "InsertVisualButton"
        self.z += 100
        self.visuales.append(cont)

    def escribir(self):
        carpeta = os.path.join(PAGES, self.id)
        os.makedirs(os.path.join(carpeta, "visuals"), exist_ok=True)
        fondo = "fondo_tooltip" if self.tooltip else "fondo"
        page = {"$schema": SCH_PAGE, "name": self.id, "displayName": self.nombre,
                "displayOption": "ActualSize" if self.tooltip else "FitToPage",
                "height": 240 if self.tooltip else H, "width": 320 if self.tooltip else W,
                "objects": {"background": [{"properties": {
                    "image": {"image": {"name": lit(fondo + ".png"), "url": imagen(fondo), "scaling": lit("Fill")}},
                    "color": color("#EEF2F8"), "transparency": lit(0)}}],
                    "outspace": [{"properties": {"color": color("#EEF2F8"), "transparency": lit(0)}}]}}
        if self.tooltip:
            page.update({"type": "Tooltip", "visibility": "HiddenInViewMode",
                         "pageBinding": {"name": "Tooltip" + self.id[:12], "type": "Tooltip"}})
        guardar(os.path.join(carpeta, "page.json"), page)
        for v in self.visuales:
            guardar(os.path.join(carpeta, "visuals", v["name"], "visual.json"), v)


def guardar(ruta, datos):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)


def texto(p, clave, x, y, w, h, lineas, fondo=None, pad=0, alinear=None, fijo=False):
    """Cuadro de texto: lineas = [(texto, tamaño, color, fuente)]."""
    parrafos = [{"textRuns": [{"value": t, "textStyle": {"fontFamily": f, "fontSize": f"{s}pt", "color": c}}]}
                for t, s, c, f in lineas]
    if alinear:
        for par in parrafos:
            par["horizontalTextAlignment"] = alinear
    vco = sin_marco(pad)
    if fondo:
        vco["background"] = obj(show=True, color=fondo, transparency=0)
    p.add(clave, "textbox", x, y, w, h, objects={"general": [{"properties": {"paragraphs": parrafos}}]}, vco=vco,
          fijo=fijo)


def imagen_visual(p, clave, nombre, x, y, w, h, ajuste="Fit", fijo=False):
    p.add(clave, "image", x, y, w, h,
          objects={"general": [{"properties": {"imageUrl": imagen(nombre)}}],
                   "imageScaling": [{"properties": props(imageScalingType=ajuste)}]},
          vco=sin_marco(), fijo=fijo)


def membrete(p):
    """Membrete institucional (igual que en el Shiny): logos solo sobre la franja blanca."""
    imagen_visual(p, "m_logo_epg", "logo_epg", 16, 6, 40, 52, fijo=True)
    texto(p, "m_curso", 66, 1, 600, 56,
          [("UNIVERSIDAD NACIONAL DEL ALTIPLANO · ESCUELA DE POSGRADO", 7, "#64748B", "Segoe UI Semibold"),
           ("Business Intelligence and Data Analytics", 13, "#1E3A8A", "Segoe UI Bold"),
           ("Maestría · Actividad Semana 2: Herramientas de analítica y reporting", 8, "#475569", "Segoe UI")],
          fijo=True)
    texto(p, "m_autora", 820, 10, 250, 46,
          [("ELABORADO POR", 7, "#64748B", "Segoe UI Semibold"),
           ("Mary Luz Nina Palacios", 12, "#1E293B", "Segoe UI Semibold")], alinear="right", fijo=True)
    imagen_visual(p, "m_logo_fac", "logo_facultad", 1084, 9, 180, 44, fijo=True)


# ---------------------------------------------------------------- piezas comunes
def boton(p, clave, x, y, w, h, etiqueta, activo=False, destino=None, accion="PageNavigation", icono=None,
          estilo="menu"):
    if estilo == "menu":
        relleno, transp, letra = (TEAL, 0, BLANCO) if activo else (MARINO, 100, MENU_TXT)
        borde, alinear = (TEAL if activo else MARINO), "left"
    else:  # botón con borde (restablecer)
        relleno, transp, letra, borde, alinear = MARINO, 100, "#7FE0CF", TEAL, "center"
    vl = props(show=True, type=accion)
    if destino:
        vl["navigationSection"] = lit(destino)
    objetos = {
        "text": [{"properties": props(show=True)},
                 {"properties": props(text=etiqueta, fontSize=10, fontColor=letra, bold=activo,
                                      fontFamily="Segoe UI Semibold", horizontalAlignment=alinear,
                                      leftMargin=14), "selector": {"id": "default"}},
                 {"properties": props(fontColor=BLANCO), "selector": {"id": "hover"}}],
        "icon": [{"properties": props(show=bool(icono))},
                 {"properties": props(shapeType=icono or "blank", placement="left", lineColor="#7FE0CF"),
                  "selector": {"id": "default"}}],
        "fill": [{"properties": props(show=True)},
                 {"properties": props(fillColor=relleno, transparency=transp), "selector": {"id": "default"}},
                 {"properties": props(fillColor=TEAL if activo else MENU_HOVER, transparency=0),
                  "selector": {"id": "hover"}}],
        "outline": [{"properties": props(show=estilo != "menu")},
                    {"properties": props(lineColor=borde, weight=1), "selector": {"id": "default"}}],
        "shape": [{"properties": props(tileShape="rectangleRounded")},
                  {"properties": props(tileShape="rectangleRounded"), "selector": {"id": "default"}}],
    }
    vco = sin_marco()
    vco["visualLink"] = [{"properties": vl}]
    p.add(clave, "actionButton", x, y, w, h, objects=objetos, vco=vco)


def menu_lateral(p):
    imagen_visual(p, "logo", "logo_puno", 18, 18, 40, 40)
    texto(p, "marca", 62, 14, 136, 58, [("COMPRAS PÚBLICAS", 9, BLANCO, "Segoe UI Black"),
                                       ("Región Puno", 8, "#7FE0CF", "Segoe UI Semibold")])
    texto(p, "menu_tit", 22, 80, 160, 18, [("MENÚ", 7, "#6F7FA3", "Segoe UI Semibold")])
    for i, (clave, nombre, icono) in enumerate(PAGINAS):
        boton(p, "nav_" + clave, 12, 100 + i * 42, 176, 36, f"{icono}   {nombre}", activo=(clave == p.clave),
              destino=nid("pagina", clave))
    boton(p, "reset", 12, 372, 176, 34, "Restablecer filtros", accion="ClearAllSlicers", icono="reset",
          estilo="borde")
    texto(p, "fuente", 18, 640, 170, 66,
          [("Fuente: Perú Compras (Catálogos", 7, "#8392B5", "Segoe UI"),
           ("Electrónicos) y padrón RUC de SUNAT.", 7, "#8392B5", "Segoe UI"),
           ("Órdenes de ene 2025 a sep 2026.", 7, "#8392B5", "Segoe UI")])


def banda(p, titulo, subtitulo, h=84):
    imagen_visual(p, "banda", "banda", X0, 12, ANCHO, h, ajuste="Fill")
    texto(p, "titulo", X0 + 22, 22, 600, h - 20, [(titulo, 17, BLANCO, "Segoe UI Black"),
                                                  (subtitulo, 9, "#AFC2E6", "Segoe UI")])


def selector_metrica(p, x, y, w, h, en_banda=True):
    """Fichas Monto / Órdenes / Empresas: la métrica elegida cambia todos los gráficos."""
    p.add("metrica", "slicer", x, y, w, h,
          query={"queryState": {"Values": {"projections": [C("Métrica", "Métrica")]}}},
          objects={"data": [{"properties": {"mode": lit("Basic")}}],
                   "general": [{"properties": {"orientation": lit(1)}}],
                   "header": [{"properties": props(show=True, text="VER GRÁFICOS POR",
                                                   fontColor="#AFC2E6" if en_banda else SUAVE, textSize=7,
                                                   bold=True)}],
                   "items": [{"properties": props(fontColor=BLANCO if en_banda else TEXTO, textSize=9, bold=True,
                                                  background="#22355C" if en_banda else "#F1F5FB", padding=4)}],
                   "selection": [{"properties": props(singleSelect=True, strictSingleSelect=True,
                                                      selectAllCheckboxEnabled=False)}]},
          vco=sin_marco(2))


def filtros(p, campos, y=106, h=58):
    """Fila de filtros desplegables en tarjetas blancas: campos = [(columna, título)]."""
    n = len(campos)
    w = (ANCHO - 12 * (n - 1)) / n
    for i, (columna, titulo) in enumerate(campos):
        p.add("f_" + columna, "slicer", int(X0 + i * (w + 12)), y, int(w), h,
              query={"queryState": {"Values": {"projections": [C(columna)]}}},
              objects={"data": [{"properties": {"mode": lit("Dropdown")}}],
                       "header": [{"properties": props(show=True, text=titulo, fontColor=SUAVE, textSize=8,
                                                       bold=True)}],
                       "items": [{"properties": props(fontColor=TEXTO, textSize=10)}],
                       "selection": [{"properties": props(selectAllCheckboxEnabled=True)}]},
              vco={**tarjeta_blanca(pad=4), "dropShadow": obj(show=False)})


def tarjeta_ola(p, clave, x, y, w, h, medida, etiqueta, ola, medida_var=None, ayuda=None, unidades=(1, 0),
                tam=20):
    """Cifra grande en blanco sobre una tarjeta con ondas (imagen de fondo + tarjeta transparente)."""
    imagen_visual(p, clave + "_fondo", "ola_" + ola, x, y, w, h, ajuste="Fill")
    q = {"queryState": {"Data": {"projections": [M(medida)]}}}
    if ayuda:
        q["queryState"]["Tooltips"] = {"projections": [M(ayuda, "Qué significa")]}
    transparente = {"fillCustom": obj("default", show=True, fillColor=MARINO, transparency=100),
                    "cardCalloutArea": [{"properties": props(backgroundFillColor=MARINO, backgroundTransparency=100)}],
                    "outline": obj("default", show=False), "accentBar": obj("default", show=False),
                    "layout": obj("default", paddingUniform=0)}
    p.add(clave, "cardVisual", x, y, w, h - (22 if medida_var else 0), query=q,
          objects={"value": obj("default", fontSize=tam, fontColor=BLANCO, bold=True, fontFamily="Segoe UI Black",
                                horizontalAlignment="left", labelDisplayUnits=unidades[0],
                                labelPrecision=unidades[1]),
                   "label": obj("default", show=True, text=etiqueta, fontColor="#E3ECFF", fontSize=9,
                                position="aboveValue", horizontalAlignment="left"),
                   "padding": obj("default", paddingUniform=10), **transparente},
          vco=sin_marco(2))
    if medida_var:
        p.add(clave + "_var", "cardVisual", x + 12, y + h - 26, w - 24, 20,
              query={"queryState": {"Data": {"projections": [M(medida_var)]}}},
              objects={"value": obj("default", fontSize=8, fontColor=BLANCO, bold=True, horizontalAlignment="left"),
                       "label": obj("default", show=False), "padding": obj("default", paddingUniform=0),
                       **transparente},
              vco=sin_marco())


def area(p, clave, x, y, w, h, medida="Valor", titulo=None, titulo_medida=None, subtitulo=None, compacto=False,
         color_area=TEAL):
    objetos = {"dataPoint": [{"properties": {"fill": color(color_area)}}],
               "lineStyles": [{"properties": props(strokeWidth=3, lineChartType="smooth", showMarker=False)}],
               "labels": [{"properties": props(show=False)}], **ejes()}
    if compacto:
        objetos["valueAxis"] = [{"properties": props(show=False, gridlineShow=False)}]
        objetos["categoryAxis"] = [{"properties": props(show=True, showAxisTitle=False, fontSize=7,
                                                        labelColor=SUAVE, gridlineShow=False)}]
    p.add(clave, "areaChart", x, y, w, h,
          query={"queryState": {"Category": {"projections": [C("periodo")]}, "Y": {"projections": [M(medida)]}},
                 "sortDefinition": orden(C("periodo"), "Ascending")},
          objects=objetos,
          vco=sin_marco() if compacto else tarjeta_blanca(titulo, subtitulo, titulo_medida))


def barras(p, clave, x, y, w, h, columna, medida, titulo=None, subtitulo=None, color_barra=AZUL, n=None,
           tabla="Compras", tipo="clusteredBarChart", titulo_medida=None, tooltip=None, etiquetas=True,
           unidades=0):
    objetos = {"labels": [{"properties": props(show=etiquetas, color=TEXTO, fontSize=9,
                                               labelPrecision=0 if unidades == 1 else 1,
                                               labelDisplayUnits=unidades)}],
               "valueAxis": [{"properties": props(show=False, gridlineShow=False)}],
               "categoryAxis": [{"properties": props(showAxisTitle=False, fontSize=9, labelColor=TEXTO,
                                                     maxMarginFactor=45, innerPadding=22)}],
               "dataPoint": [{"properties": {"fill": color(color_barra)}}]}
    if tipo == "clusteredColumnChart":
        objetos["valueAxis"] = [{"properties": props(show=True, showAxisTitle=False, fontSize=8, labelColor=SUAVE,
                                                     gridlineColor=REJILLA, gridlineStyle="dashed")}]
    p.add(clave, tipo, x, y, w, h,
          query={"queryState": {"Category": {"projections": [C(columna, tabla)]}, "Y": {"projections": [M(medida)]}},
                 "sortDefinition": orden(M(medida))},
          objects=objetos, vco=tarjeta_blanca(titulo, subtitulo, titulo_medida, tooltip),
          filtros=[top_n(tabla, columna, n)] if n else None)


def dona(p, clave, x, y, w, h, columna, medida, titulo, subtitulo=None, tooltip=None):
    p.add(clave, "donutChart", x, y, w, h,
          query={"queryState": {"Category": {"projections": [C(columna)]}, "Y": {"projections": [M(medida)]}},
                 "sortDefinition": orden(M(medida))},
          objects={"labels": [{"properties": props(show=True, labelStyle="Percent of total", fontSize=9,
                                                   color=TEXTO, position="outside", percentageLabelPrecision=0)}],
                   "legend": [{"properties": props(show=True, position="Bottom", fontSize=8, labelColor=SUAVE)}],
                   "slices": [{"properties": props(innerRadiusRatio=68)}]},
          vco=tarjeta_blanca(titulo, subtitulo, tooltip=tooltip))


def tabla(p, clave, x, y, w, h, columnas, titulo, subtitulo=None, orden_por=None, n=None, anchos=None):
    objetos = {"columnHeaders": [{"properties": props(fontColor=SUAVE, backColor=BLANCO, fontSize=8, bold=True)}],
               "values": [{"properties": props(fontSize=9, fontColorPrimary=TEXTO, backColorPrimary=BLANCO,
                                               fontColorSecondary=TEXTO, backColorSecondary="#F6F8FC")}],
               "grid": [{"properties": props(gridVertical=False, gridHorizontal=True, gridHorizontalColor=REJILLA,
                                             rowPadding=4)}],
               "total": [{"properties": props(totals=False)}]}
    objetos["values"][0]["properties"].update(props(wordWrap=False))
    if anchos:
        objetos["columnWidth"] = [{"properties": {"value": lit(a)}, "selector": {"metadata": m}} for m, a in anchos]
    q = {"queryState": {"Values": {"projections": columnas}}}
    if orden_por:
        q["sortDefinition"] = orden(orden_por)
    p.add(clave, "tableEx", x, y, w, h, query=q, objects=objetos, vco=tarjeta_blanca(titulo, subtitulo),
          filtros=n)


# ---------------------------------------------------------------- ventana emergente
def pagina_detalle():
    p = Pagina("detalle", "Detalle emergente", tooltip=True)
    p.add("valor", "cardVisual", 8, 6, 304, 72,
          query={"queryState": {"Data": {"projections": [M("Valor"), M("% del total", "Del total")]}}},
          objects={"value": obj("default", fontSize=16, fontColor=TEXTO, bold=True, fontFamily="Segoe UI Black",
                                horizontalAlignment="left"),
                   "label": obj("default", show=True, fontColor=TEAL, fontSize=8, position="aboveValue",
                                horizontalAlignment="left"),
                   "outline": obj("default", show=False), "accentBar": obj("default", show=False),
                   "fillCustom": obj("default", show=False),
                   "cardCalloutArea": [{"properties": props(backgroundTransparency=100)}],
                   "padding": obj("default", paddingUniform=2), "layout": obj("default", paddingUniform=0)},
          vco=sin_marco())
    texto(p, "rotulo", 12, 82, 296, 20, [("Tendencia mes a mes", 8, SUAVE, "Segoe UI Semibold")])
    area(p, "tendencia", 4, 102, 312, 132, compacto=True)
    return p


# ---------------------------------------------------------------- 1. Resumen
def pagina_resumen(tip):
    p = Pagina("resumen", "Resumen")
    menu_lateral(p)
    banda(p, "Resumen de compras públicas", "Órdenes de Catálogos Electrónicos de las entidades de la región Puno")
    selector_metrica(p, XF - 330, 26, 310, 56)
    filtros(p, [("anio", "AÑO"), ("sector", "SECTOR"), ("provincia", "PROVINCIA"), ("rubro", "RUBRO")])
    w = (ANCHO - 36) // 4
    for i, (clave, medida, etq, ola, var, ayuda, uni) in enumerate([
            ("k_monto", "Monto", "Monto total", "azul", "Etiqueta var Monto", "Ayuda monto", (1000000, 2)),
            ("k_ord", "Órdenes", "Órdenes de compra", "teal", "Etiqueta var Órdenes", "Ayuda órdenes", (1, 0)),
            ("k_ticket", "Ticket promedio", "Ticket promedio", "marino", "Etiqueta var Ticket", "Ayuda ticket",
             (1000, 1)),
            ("k_prov", "Proveedores", "Empresas proveedoras", "indigo", "Etiqueta var Proveedores",
             "Ayuda proveedores", (1, 0))]):
        tarjeta_ola(p, clave, X0 + i * (w + 12), 174, w, 94, medida, etq, ola, var, ayuda, uni)
    area(p, "g_mensual", X0, 280, 640, 214, titulo_medida="Título evolución",
         subtitulo="Enero casi no tiene órdenes: arranca el año fiscal")
    dona(p, "g_proc", X0 + 652, 280, ANCHO - 652, 214, "tipo_procedimiento", "Valor", "¿Cómo se compra?",
         "Por tipo de procedimiento", tooltip=tip)
    barras(p, "g_rubros", X0, 506, 520, 206, "rubro", "Valor", titulo_medida="Título rubros",
           subtitulo="Los 5 principales · pasa el mouse para ver su tendencia", color_barra=AZUL, n=5, tooltip=tip)
    barras(p, "g_sector", X0 + 532, 506, ANCHO - 532, 206, "sector", "Valor", titulo_medida="Título sectores",
           subtitulo="Los 5 principales · clic en una barra para filtrar", color_barra=TEAL, n=5, tooltip=tip)
    return p


# ---------------------------------------------------------------- 2. Proveedores
def pagina_proveedores(tip):
    p = Pagina("proveedores", "Proveedores")
    menu_lateral(p)
    banda(p, "Empresas proveedoras", "¿A quién le compra el Estado en Puno y qué tan concentradas están las ventas?")
    filtros(p, [("anio", "AÑO"), ("sector", "SECTOR DE LA ENTIDAD"), ("rubro", "RUBRO"),
                ("origen_proveedor", "DOMICILIO DE LA EMPRESA")])
    w = (ANCHO - 36) // 4
    for i, (clave, medida, etq, ola, uni) in enumerate([
            ("k_prov", "Proveedores", "Empresas que vendieron", "azul", (1, 0)),
            ("k_top10", "Concentración top 10", "Monto en las 10 que más venden", "teal", (0, 1)),
            ("k_pareto", "Etiqueta Pareto", "Empresas que hacen el 80 % del monto", "marino", (0, 0)),
            ("k_local", "% monto a empresas de Puno", "Monto que queda en empresas de Puno", "indigo", (0, 1))]):
        tarjeta_ola(p, clave, X0 + i * (w + 12), 174, w, 94, medida, etq, ola, unidades=uni,
                    tam=14 if clave == "k_pareto" else 20)
    barras(p, "g_top", X0, 280, 640, 214, "proveedor", "Monto", "Las 5 empresas que más vendieron",
           "Monto vendido a entidades de Puno · clic para filtrar", color_barra=AZUL, n=5, tooltip=tip)
    dona(p, "g_origen", X0 + 652, 280, ANCHO - 652, 214, "origen_proveedor", "Monto", "¿De dónde son las empresas?",
         "Monto según su domicilio fiscal (SUNAT)", tooltip=tip)
    p.add("g_disp", "scatterChart", X0, 506, 520, 206,
          query={"queryState": {"Category": {"projections": [C("proveedor")]},
                                "Series": {"projections": [C("origen_proveedor")]},
                                "X": {"projections": [M("Órdenes")]}, "Y": {"projections": [M("Monto")]},
                                "Size": {"projections": [M("Entidades")]}}},
          objects={"categoryAxis": [{"properties": props(showAxisTitle=True, titleText="N.º de órdenes (log)",
                                                         fontSize=8, labelColor=SUAVE, logAxisScale=True,
                                                         gridlineShow=False)}],
                   "valueAxis": [{"properties": props(showAxisTitle=True, titleText="Monto (log)", fontSize=8,
                                                      labelColor=SUAVE, logAxisScale=True, gridlineColor=REJILLA)}],
                   "legend": [{"properties": props(show=True, position="Top", fontSize=8, labelColor=SUAVE)}],
                   "bubbles": [{"properties": props(bubbleSize=-20)}]},
          vco=tarjeta_blanca("Frecuencia frente a monto", "Cada burbuja es una empresa; su tamaño, las entidades a las que vendió"))
    tabla(p, "t_prov", X0 + 532, 506, ANCHO - 532, 206,
          [C("proveedor", visible="Empresa"), C("origen_proveedor", visible="Domicilio"), M("Órdenes"),
           M("Entidades"), M("Monto")], "Detalle por empresa", orden_por=M("Monto"),
          anchos=[("Compras.proveedor", 160), ("Compras.origen_proveedor", 90), ("Compras.Órdenes", 52),
                  ("Compras.Entidades", 58), ("Compras.Monto", 90)])
    return p


# ---------------------------------------------------------------- 3. Entidades
def pagina_entidades(tip):
    p = Pagina("entidades", "Entidades")
    menu_lateral(p)
    banda(p, "Entidades compradoras", "¿Quiénes compran: municipalidades, gobierno regional, hospitales, universidades…?")
    filtros(p, [("anio", "AÑO"), ("sector", "SECTOR"), ("provincia", "PROVINCIA"), ("rubro", "RUBRO")])
    w = (ANCHO - 36) // 4
    for i, (clave, medida, etq, ola, uni) in enumerate([
            ("k_ent", "Entidades", "Entidades que compraron", "azul", (1, 0)),
            ("k_mxe", "Monto por entidad", "Monto promedio por entidad", "teal", (1000, 1)),
            ("k_peso", "Peso entidad principal", "Monto de la entidad que más compra", "marino", (0, 1)),
            ("k_dist", "Distritos con compras", "Distritos con entidades compradoras", "indigo", (1, 0))]):
        tarjeta_ola(p, clave, X0 + i * (w + 12), 174, w, 94, medida, etq, ola, unidades=uni)
    barras(p, "g_top", X0, 280, 640, 214, "entidad", "Monto", "Las 5 entidades que más compran",
           "Monto comprado · clic para filtrar", color_barra=TEAL, n=5, tooltip=tip)
    dona(p, "g_sector", X0 + 652, 280, ANCHO - 652, 214, "sector", "Monto", "¿Qué sectores compran más?",
         "Monto por sector de la entidad", tooltip=tip)
    barras(p, "g_prov", X0, 506, 520, 206, "provincia", "Monto", "Monto por provincia",
           "Las 5 provincias con más monto", color_barra=AZUL, n=5, tooltip=tip)
    tabla(p, "t_ent", X0 + 532, 506, ANCHO - 532, 206,
          [C("entidad", visible="Entidad"), C("sector", visible="Sector"), M("Órdenes"), M("Monto")],
          "Detalle por entidad", orden_por=M("Monto"), anchos=[("Compras.entidad", 230), ("Compras.sector", 110)])
    return p


# ---------------------------------------------------------------- 4. Mapa
def pagina_mapa(tip):
    p = Pagina("mapa", "Mapa")
    menu_lateral(p)
    banda(p, "Mapa de compras por distrito", "Cada punto es un distrito; su tamaño es el valor elegido · clic para filtrar")
    selector_metrica(p, XF - 330, 26, 310, 56)
    p.add("mapa", "azureMap", X0, 106, ANCHO, 384,
          query={"queryState": {
              "Category": {"projections": [{**C("distrito", "Distritos"), "active": True}]},
              "Y": {"projections": [promedio("Distritos", "latitud")]},
              "X": {"projections": [promedio("Distritos", "longitud")]},
              "Size": {"projections": [M("Valor")]}}},
          objects={"mapControls": [{"properties": props(defaultStyle="grayscale_light", autoZoom=True,
                                                        showNavigationControls=True, showLabels=True,
                                                        showStylePicker=False, geocodingCulture="es-ES")}],
                   "bubbleLayer": [{"properties": props(show=True, minBubbleRadius=4, maxRadius=34, bubbleStrokeWidth=2,
                                                        strokeColor=BLANCO, mapTransparency=25,
                                                        markerRangeType="magnitude")}],
                   "dataPoint": [{"properties": {"fill": color(AZUL)}}],
                   "legend": [{"properties": props(show=False)}],
                   "categoryLabels": [{"properties": props(show=False)}]},
          vco=tarjeta_blanca(titulo_medida="Título mapa", tooltip=tip, pad=8))
    barras(p, "g_dist", X0, 502, 420, 210, "distrito", "Valor", titulo_medida="Título distritos",
           subtitulo="Los 5 principales", color_barra=AZUL, n=5, tabla="Distritos", tooltip=tip)
    dona(p, "g_prov", X0 + 432, 502, 290, 210, "provincia", "Valor", "Por provincia", tooltip=tip)
    tabla(p, "t_dist", X0 + 734, 502, ANCHO - 734, 210,
          [C("distrito", visible="Distrito"), C("provincia", visible="Provincia"), M("Valor", "Valor")],
          "Detalle por distrito", orden_por=M("Valor"), anchos=[("Compras.distrito", 90), ("Compras.provincia", 80), ("Compras.Valor", 90)])
    return p


# ---------------------------------------------------------------- 5. Exploración (EDA)
def pagina_eda(tip):
    p = Pagina("eda", "Exploración")
    menu_lateral(p)
    banda(p, "Exploración de datos (EDA)", "Cómo se reparte el monto de las órdenes y cuándo se emiten")
    filtros(p, [("anio", "AÑO"), ("sector", "SECTOR"), ("rubro", "RUBRO")])
    w = (ANCHO - 36) // 4
    for i, (clave, medida, etq, ola, uni) in enumerate([
            ("k_media", "Media por orden", "Media por orden", "azul", (1000, 1)),
            ("k_mediana", "Orden típica", "Mediana (orden típica)", "teal", (1000, 1)),
            ("k_desv", "Desviación estándar", "Desviación estándar", "marino", (1000, 1)),
            ("k_cv", "Coef. de variación", "Coeficiente de variación", "indigo", (0, 0))]):
        tarjeta_ola(p, clave, X0 + i * (w + 12), 174, w, 94, medida, etq, ola, unidades=uni)
    p.add("g_rangos", "clusteredColumnChart", X0, 280, 640, 214,
          query={"queryState": {"Category": {"projections": [C("rango_monto")]},
                                "Y": {"projections": [M("% de órdenes"), M("% del monto")]}},
                 "sortDefinition": orden(C("rango_monto"), "Ascending")},
          objects={"labels": [{"properties": props(show=True, fontSize=8, color=TEXTO, labelPrecision=0)}],
                   "legend": [{"properties": props(show=True, position="Top", fontSize=9, labelColor=SUAVE)}],
                   "dataPoint": [{"properties": {"fill": color(AZUL)}, "selector": {"metadata": "Compras.% de órdenes"}},
                                 {"properties": {"fill": color(TEAL)}, "selector": {"metadata": "Compras.% del monto"}}],
                   "categoryAxis": [{"properties": props(showAxisTitle=False, fontSize=8, labelColor=SUAVE)}],
                   "valueAxis": [{"properties": props(show=False, gridlineShow=False)}]},
          vco=tarjeta_blanca("Órdenes frente a monto por rango", "Muchas órdenes chicas; pocas grandes concentran el dinero"))
    barras(p, "g_dias", X0 + 652, 280, ANCHO - 652, 214, "dia_semana", "Órdenes", "¿Qué días se emiten las órdenes?",
           "Número de órdenes por día de la semana", color_barra=INDIGO, tipo="clusteredColumnChart",
           unidades=1)
    # los días en su orden natural (no por cantidad)
    p.visuales[-1]["visual"]["query"]["sortDefinition"] = orden(C("dia_semana"), "Ascending")
    p.add("t_stats", "cardVisual", X0, 506, 520, 92,
          query={"queryState": {"Data": {"projections": [M("Mínimo"), M("Percentil 25"), M("Percentil 75"),
                                                         M("Rango intercuartílico", "Rango intercuartílico")]}}},
          objects={"value": obj("default", fontSize=12, fontColor=TEXTO, bold=True, horizontalAlignment="left",
                                labelDisplayUnits=1),
                   "label": obj("default", show=True, fontColor=SUAVE, fontSize=8, position="aboveValue",
                                horizontalAlignment="left"),
                   "outline": obj("default", show=False),
                   "accentBar": obj("default", show=True, color=TEAL, position="Left", width=3),
                   "padding": obj("default", paddingUniform=6), "layout": obj("default", paddingUniform=0)},
          vco=tarjeta_blanca(pad=6))
    p.add("t_lectura", "cardVisual", X0, 608, 520, 104,
          query={"queryState": {"Data": {"projections": [M("Lectura distribución")]}}},
          objects={"value": obj("default", fontSize=10, fontColor=TEXTO, bold=False, horizontalAlignment="left",
                                textWrap=True),
                   "label": obj("default", show=True, text="¿CÓMO LEERLO?", fontColor=TEAL, fontSize=8, bold=True,
                                position="aboveValue", horizontalAlignment="left"),
                   "outline": obj("default", show=False),
                   "accentBar": obj("default", show=True, color=NARANJA, position="Left", width=3),
                   "padding": obj("default", paddingUniform=8), "layout": obj("default", paddingUniform=0)},
          vco=tarjeta_blanca(pad=6))
    tabla(p, "t_grandes", X0 + 532, 506, ANCHO - 532, 206,
          [C("fecha", visible="Fecha"), C("entidad", visible="Entidad"), C("rubro", visible="Rubro"),
           M("Monto")], "Las órdenes más grandes", "Posibles valores atípicos", orden_por=M("Monto"),
          n=[top_n("Compras", "orden", 10)],
          anchos=[("Compras.fecha", 76), ("Compras.entidad", 150), ("Compras.rubro", 130), ("Compras.Monto", 90)])
    return p


# ---------------------------------------------------------------- 6. Datos
def pagina_datos():
    p = Pagina("datos", "Datos")
    menu_lateral(p)
    banda(p, "Datos de las órdenes", "Todas las órdenes según los filtros elegidos; se exportan desde las opciones de la tabla")
    filtros(p, [("anio", "AÑO"), ("sector", "SECTOR"), ("provincia", "PROVINCIA"), ("rubro", "RUBRO"),
                ("estado", "ESTADO")])
    tabla(p, "t_datos", X0, 176, ANCHO, 536,
          [C("fecha", visible="Fecha"), C("entidad", visible="Entidad"), C("sector", visible="Sector"),
           C("provincia", visible="Provincia"), C("proveedor", visible="Empresa"), C("rubro", visible="Rubro"),
           C("estado", visible="Estado"), C("orden", visible="Orden"), C("total", visible="Monto (S/)")],
          "Órdenes de compra", orden_por=C("fecha"),
          anchos=[("Compras.fecha", 70), ("Compras.entidad", 170), ("Compras.sector", 100), ("Compras.provincia", 80),
                  ("Compras.proveedor", 160), ("Compras.rubro", 160), ("Compras.estado", 60),
                  ("Compras.orden", 120)])
    return p


# ---------------------------------------------------------------- tema e imágenes
def registrar_recursos():
    if os.path.isdir(REG):
        shutil.rmtree(REG)
    os.makedirs(REG)
    items = []
    for archivo in sorted(os.listdir(RECURSOS)):
        nombre, ext = os.path.splitext(archivo)
        if ext != ".png":
            continue
        datos = open(os.path.join(RECURSOS, archivo), "rb").read()
        reg = f"{nombre}{int(hashlib.md5(datos).hexdigest()[:12], 16)}.png"
        open(os.path.join(REG, reg), "wb").write(datos)
        IMAGENES[nombre] = reg
        items.append({"name": reg, "path": reg, "type": "Image"})
    tema_nombre = "Plantilla-" + hashlib.md5(open(__file__, "rb").read()).hexdigest()[:8] + ".json"
    tema = {"name": tema_nombre, "dataColors": PALETA, "foreground": TEXTO, "foregroundNeutralSecondary": SUAVE,
            "background": BLANCO, "tableAccent": TEAL, "good": TEAL, "bad": "#E5484D", "neutral": AMBAR,
            "textClasses": {"title": {"fontFace": "Segoe UI Semibold", "fontSize": 12, "color": TEXTO},
                            "label": {"fontFace": "Segoe UI", "fontSize": 9, "color": SUAVE},
                            "callout": {"fontFace": "Segoe UI Black", "fontSize": 22, "color": TEXTO},
                            "header": {"fontFace": "Segoe UI Semibold", "fontSize": 12, "color": TEXTO}},
            "visualStyles": {"*": {"*": {"visualHeader": [{"show": False}]}}}}
    guardar(os.path.join(REG, tema_nombre), tema)
    items.append({"name": tema_nombre, "path": tema_nombre, "type": "CustomTheme"})
    ruta = os.path.join(DEF, "report.json")
    rep = json.load(open(ruta, encoding="utf-8"))
    base = rep["themeCollection"]["baseTheme"]
    rep["themeCollection"]["customTheme"] = {"name": tema_nombre, "reportVersionAtImport": base.get("reportVersionAtImport"),
                                             "type": "RegisteredResources"}
    rep["resourcePackages"] = [r for r in rep.get("resourcePackages", []) if r.get("name") != "RegisteredResources"]
    rep["resourcePackages"].append({"name": "RegisteredResources", "type": "RegisteredResources", "items": items})
    # panel de filtros plegado al abrir (los filtros están en la propia página)
    rep.setdefault("objects", {})["outspacePane"] = [{"properties": {"expanded": lit(False)}}]
    ajustes = rep.setdefault("settings", {})
    ajustes["defaultFilterActionIsDataFilter"] = True  # un clic filtra (no solo resalta) los demás gráficos
    ajustes["hideVisualContainerHeader"] = True
    guardar(ruta, rep)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    registrar_recursos()
    for d in os.listdir(PAGES):
        if os.path.isdir(os.path.join(PAGES, d)):
            shutil.rmtree(os.path.join(PAGES, d))
    det = pagina_detalle()
    paginas = [pagina_resumen(det.id), pagina_proveedores(det.id), pagina_entidades(det.id), pagina_mapa(det.id),
               pagina_eda(det.id), pagina_datos(), det]
    for p in paginas:
        p.escribir()
    guardar(os.path.join(PAGES, "pages.json"), {"$schema": SCH_PAGES, "pageOrder": [p.id for p in paginas],
                                                "activePageName": paginas[0].id})
    print("páginas:", ", ".join(f"{p.nombre} ({len(p.visuales)})" for p in paginas))


if __name__ == "__main__":
    main()
