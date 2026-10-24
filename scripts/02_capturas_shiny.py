"""Toma capturas de cada pestaña de la app Shiny (debe estar corriendo en el puerto 8765)."""
import os, sys
from playwright.sync_api import sync_playwright

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "capturas", "shiny")
URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765"
# (texto de la pestaña, nombre del archivo)
PESTANAS = [("Resumen", "resumen"), ("Proveedores", "empresas"), ("Entidades", "entidades"),
            ("Mapa distrital", "mapa"), ("Exploración", "exploracion"), ("Datos", "datos")]

def alto_completo(pag):
    """El contenido se desplaza dentro de un contenedor: se agranda la ventana hasta que entre todo."""
    h = pag.evaluate("""() => Math.max(document.body.scrollHeight,
        ...Array.from(document.querySelectorAll('.bslib-page-main, .main, .tab-content, .bslib-sidebar-layout > .main'))
            .map(e => e.scrollHeight + e.getBoundingClientRect().top))""")
    h = min(int(h) + 40, 3200)
    print("  alto:", h)
    pag.set_viewport_size({"width": 1500, "height": h})
    pag.wait_for_timeout(2500)


with sync_playwright() as p:
    nav = p.chromium.launch(channel="chrome", args=["--no-sandbox", "--disable-gpu"])
    pag = nav.new_page(viewport={"width": 1500, "height": 900}, device_scale_factor=1.25, locale="es-PE")
    errores = []
    pag.on("console", lambda m: errores.append(m.text) if m.type == "error" else None)
    pag.goto(URL, wait_until="networkidle")
    pag.wait_for_timeout(4000)
    for i, (nombre, corto) in enumerate(PESTANAS, 1):
        pag.set_viewport_size({"width": 1500, "height": 900})
        pag.get_by_role("tab", name=nombre).click()
        pag.wait_for_timeout(4500)
        alto_completo(pag)
        archivo = os.path.join(OUT, f"{i:02d}_{corto}.png")
        pag.screenshot(path=archivo, full_page=True)
        print("captura:", archivo)
    # ejemplo de filtro aplicado: solo sector Salud
    pag.get_by_role("tab", name="Resumen").click()
    pag.locator("#sector-selectized").click()
    pag.get_by_text("Salud", exact=True).last.click()
    pag.keyboard.press("Escape")
    pag.wait_for_timeout(800)
    pag.locator("#aplicar").click()
    pag.wait_for_timeout(4500)
    alto_completo(pag)
    pag.screenshot(path=os.path.join(OUT, "07_filtro_salud.png"), full_page=True)
    print("errores de consola:", errores[:5])
    nav.close()
