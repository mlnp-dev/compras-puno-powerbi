# Prepara las dos tablas que lee el reporte de Power BI (carpeta powerbi/).
#
# Entrada
#   data/compras_puno_2025_2026.csv     -> órdenes de compra de Puno (sale de 01_preparar_datos.py)
#   data/ref/geo/puno_distritos.geojson -> límites distritales INEI de la región
# Salida
#   data/powerbi/compras.csv   -> una fila por orden; se dejan fuera las resueltas o nulas (no se ejecutaron),
#                                 igual que el filtro por defecto de la app Shiny
#   data/powerbi/distritos.csv -> un distrito por fila, con latitud y longitud de un punto interior
#                                 (para las burbujas del mapa)
#
# Uso:  Rscript scripts/03_preparar_powerbi.R   (desde la carpeta de la actividad)

suppressMessages({ library(readr); library(dplyr); library(sf) })
sf_use_s2(FALSE)

dir.create("data/powerbi", showWarnings = FALSE)
titulo <- function(x) tools::toTitleCase(tolower(x))
MESES <- c("Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic")

# San Miguel (211105) se creó en 2016 y el mapa del INEI es anterior: en el mapa se suma a Juliaca
ubigeo_mapa <- function(u) ifelse(u == "211105", "211101", u)

compras <- read_csv("data/compras_puno_2025_2026.csv", show_col_types = FALSE,
                    col_types = cols(ruc_entidad = "c", ruc_proveedor = "c", ubigeo_entidad = "c")) |>
  filter(!estado %in% c("RESUELTA", "ORDEN DE COMPRA NULA")) |>
  transmute(
    orden, fecha, anio, mes, mes_nombre = MESES[mes],
    periodo = as.Date(paste0(periodo, "-01")),
    ruc_entidad, entidad = titulo(entidad), sector,
    provincia = titulo(provincia_entidad), distrito = titulo(distrito_entidad),
    ubigeo = ubigeo_mapa(ubigeo_entidad),
    zona = ifelse(distrito_entidad == "PUNO" & ubigeo_entidad == "210101", "Distrito de Puno", "Resto de la región"),
    ruc_proveedor, proveedor, tipo_empresa, origen_proveedor,
    rubro = titulo(acuerdo_marco), tipo_procedimiento, estado = titulo(estado),
    rango_monto, total,
    dia_num = as.integer(format(fecha, "%u")),
    dia_semana = c("Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom")[dia_num]
  )

geo <- st_read("data/ref/geo/puno_distritos.geojson", quiet = TRUE) |> st_make_valid()
pts <- st_coordinates(st_point_on_surface(st_geometry(geo)))
distritos <- tibble(ubigeo = geo$ubigeo, distrito = titulo(geo$distrito), provincia = titulo(geo$provincia),
                    latitud = round(pts[, "Y"], 5), longitud = round(pts[, "X"], 5)) |>
  mutate(zona = ifelse(ubigeo == "210101", "Distrito de Puno", "Resto de la región"),
         # nombre único para el mapa: "Puno, Puno" evita que Azure Maps lo confunda con otro lugar
         lugar = paste0(distrito, ", ", provincia, ", Puno, Perú")) |>
  arrange(ubigeo)

faltan <- setdiff(unique(compras$ubigeo), distritos$ubigeo)
if (length(faltan)) stop("Ubigeos sin distrito en el mapa: ", paste(faltan, collapse = ", "))

write_csv(compras, "data/powerbi/compras.csv", na = "")
write_csv(distritos, "data/powerbi/distritos.csv", na = "")
cat(nrow(compras), "órdenes ·", nrow(distritos), "distritos · monto S/", format(sum(compras$total), big.mark = ","), "\n")
cat("Distrito de Puno:", round(100 * sum(compras$total[compras$zona == "Distrito de Puno"]) / sum(compras$total), 1), "% del monto\n")
