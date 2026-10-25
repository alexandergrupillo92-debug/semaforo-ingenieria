import os
from datetime import datetime
from itertools import zip_longest
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    CondPageBreak, Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

try:
    from PIL import Image as PILImage, ImageOps
except ImportError:
    PILImage = None
    ImageOps = None

try:
    _RESAMPLE = PILImage.Resampling.LANCZOS
except AttributeError:
    _RESAMPLE = PILImage.LANCZOS

RUTA_MEMBRETE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "membrete_fondo.jpg")
CARPETA_TEMP_FOTOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "_temp_fotos_pdf")
LADO_PX_FOTO = 700  # resolución máxima por lado; de sobra para imprimir a 8x8cm (~220dpi)


def recortar_cuadrado(ruta_foto):
    """Recorta una foto al centro para dejarla cuadrada (1:1), corrige la rotación
    de cámara (EXIF) y la redimensiona a un tamaño moderado (900x900 px) antes de
    guardarla. Esto evita que fotos pesadas de cámara (varios MB, 4000x3000px o más)
    hagan lenta —o cuelguen— la generación del PDF. Devuelve la ruta del archivo
    optimizado, o la ruta original si algo falla."""
    if PILImage is None:
        return ruta_foto
    try:
        os.makedirs(CARPETA_TEMP_FOTOS, exist_ok=True)
        im = PILImage.open(ruta_foto)
        if ImageOps is not None:
            im = ImageOps.exif_transpose(im)  # corrige fotos que salen giradas
        im = im.convert("RGB")
        w, h = im.size
        lado = min(w, h)
        izq = (w - lado) // 2
        arriba = (h - lado) // 2
        recorte = im.crop((izq, arriba, izq + lado, arriba + lado))
        if lado > LADO_PX_FOTO:
            recorte = recorte.resize((LADO_PX_FOTO, LADO_PX_FOTO), _RESAMPLE)
        nombre = f"cuad_{os.path.splitext(os.path.basename(ruta_foto))[0]}.jpg"
        ruta_salida = os.path.join(CARPETA_TEMP_FOTOS, nombre)
        recorte.save(ruta_salida, "JPEG", quality=78, optimize=True)
        return ruta_salida
    except Exception:
        return ruta_foto

OPC_TIPOLOGIA = ["Unifamiliar", "Bifamiliar", "Multifamiliar", "Comercial"]
OPC_OCUPACION = ["Habitada", "Desocupada"]
OPC_TENENCIA = ["Propia", "Alquilada", "Prestada", "Cuidada"]
OPC_TECNOLOGIA = [
    "Kit Estructural", "Concreto Armado", "Estructura Aporticada",
    "Construcción Mixta", "Construcción Improvisada",
]
OPC_INCLINACION = ["Ninguna", "Leve", "Moderada", "Severa"]
OPC_ASENTAMIENTO = [
    "No se observa",
    "Grietas en piso o patio",
    "Hundimiento leve (patio, alejado de la vivienda)",
    "Hundimiento severo (en la vivienda o junto a ella)",
]
# Referencias a las opciones de asentamiento que afectan el color del semáforo
ASENT_GRIETAS = OPC_ASENTAMIENTO[1]
ASENT_LEVE = OPC_ASENTAMIENTO[2]
ASENT_SEVERO = OPC_ASENTAMIENTO[3]
OPC_SI_NO = ["No", "Sí"]
OPC_SERVICIOS = ["Operativos", "Parcialmente interrumpidos", "Totalmente interrumpidos"]
OPC_CANTIDAD_PERSONAS = [str(i) for i in range(0, 16)]
OPC_NIVELES = [str(i) for i in range(1, 11)]

# Colapso de la estructura: cualquier opción distinta de "Sin colapso" da ROJO de inmediato
# y el formulario omite la evaluación por espacio.
OPC_COLAPSO = ["Sin colapso", "Posible", "Parcial", "Total"]
COLAPSO_NINGUNO = OPC_COLAPSO[0]
_MOTIVO_COLAPSO = {
    "Posible": "Posible colapso de la estructura. Se omitió la evaluación por espacio.",
    "Parcial": "Colapso parcial de la estructura. Se omitió la evaluación por espacio.",
    "Total": "Colapso total de la estructura. Se omitió la evaluación por espacio.",
}

# Acciones recomendadas (selección múltiple)
OPC_INSPECCION = [
    ("estructura", "Estructura"),
    ("geologia", "Geología o Geotecnia"),
    ("instalaciones", "Instalaciones"),
    ("otra", "Otra"),
]
OPC_MEDIDAS = [
    ("acordonar", "Acordonar"),
    ("cerrar_calles", "Cerrar calles"),
    ("apuntalar", "Apuntalar"),
    ("desconectar_gas", "Desconectar gas"),
    ("desconectar_electricidad", "Desconectar electricidad"),
    ("otra", "Otra"),
]
_MAPA_INSPECCION = dict(OPC_INSPECCION)
_MAPA_MEDIDAS = dict(OPC_MEDIDAS)

# Las cuatro fachadas se evalúan como cualquier otro espacio: daño estructural,
# no estructural, cantidades, nota y foto, y cuentan para el color del semáforo.
ESPACIOS_REGULARES = [
    ("sala", "Sala"), ("comedor", "Comedor"), ("cocina", "Cocina"),
    ("cuarto", "Cuarto(s)"), ("banio", "Baño(s)"),
    ("fachada_principal", "Fachada principal"),
    ("fachada_posterior", "Fachada posterior"),
    ("fachada_lat_der", "Fachada lateral derecha"),
    ("fachada_lat_izq", "Fachada lateral izquierda"),
]
FACHADAS = [(c, n) for c, n in ESPACIOS_REGULARES if c.startswith("fachada_")]

OPC_ESTRUCTURAL = [
    ("col_leve", "Columna: grietas leves"),
    ("col_severo", "Columna: grietas severas o acero expuesto"),
    ("col_colapso", "Columna: colapso"),
    ("viga_leve", "Viga de carga / coronamiento: grietas leves"),
    ("viga_severo", "Viga de carga / coronamiento: grietas severas o acero expuesto"),
    ("viga_colapso", "Viga de carga / coronamiento: colapso"),
]
OPC_NO_ESTRUCTURAL = [
    ("fisuras", "Fisuras leves en pared o friso"),
    ("grietas", "Grietas visibles en pared"),
    ("desprendimiento", "Desprendimiento de friso o revestimiento"),
    ("colapso", "Colapso parcial o total de pared"),
]
OPC_TECHO = [
    ("leve", "Daño leve (goteras, láminas sueltas)"),
    ("parcial", "Desprendimiento parcial"),
    ("colapso", "Colapso"),
]

_MAPA_ESTRUCTURAL = dict(OPC_ESTRUCTURAL)
_MAPA_NO_ESTRUCTURAL = dict(OPC_NO_ESTRUCTURAL)
_MAPA_TECHO = dict(OPC_TECHO)
_RANGO_ESTRUCTURAL = {
    "col_leve": 1, "col_severo": 2, "col_colapso": 3,
    "viga_leve": 1, "viga_severo": 2, "viga_colapso": 3,
}
_RANGO_TECHO = {"leve": 1, "parcial": 2, "colapso": 3}

COLOR_ROJO, ETIQ_ROJO = "#C0392B", "ROJO — NO HABITABLE HASTA SER REPARADA"
COLOR_AMARILLO, ETIQ_AMARILLO = "#D68910", "AMARILLO — REPARABLE / ACCESO RESTRINGIDO"
COLOR_VERDE, ETIQ_VERDE = "#27AE60", "VERDE — HABITABLE"


def colapso_activo(generales):
    """True si el inspector marcó colapso posible, parcial o total."""
    return (generales or {}).get("colapso") in OPC_COLAPSO[1:]


def acciones_recomendadas(datos):
    """Devuelve (lista_inspeccion, lista_medidas) ya con texto legible."""
    a = datos.get("acciones") or {}

    def armar(marcadas, mapa, otra_texto):
        salida = []
        for v in marcadas:
            if v == "otra":
                salida.append(f"Otra: {otra_texto}" if otra_texto else "Otra")
            elif v in mapa:
                salida.append(mapa[v])
        return salida

    return (
        armar(a.get("inspeccion", []), _MAPA_INSPECCION, a.get("otra_inspeccion", "")),
        armar(a.get("medidas", []), _MAPA_MEDIDAS, a.get("otra_medida", "")),
    )


def fotos_colapso(datos):
    """Fotos que se permiten cuando hay colapso: la del colapso y las 4 fachadas.
    Devuelve [(nombre, ruta)] solo con las que existen en disco."""
    salida = []
    if datos.get("foto_colapso") and os.path.isfile(datos["foto_colapso"]):
        salida.append(("Colapso de la estructura", datos["foto_colapso"]))
    por_fachada = datos.get("fotos_colapso_fachadas") or {}
    for clave, nombre in FACHADAS:
        ruta = por_fachada.get(clave)
        if ruta and os.path.isfile(ruta):
            salida.append((nombre, ruta))
    return salida


def filas_datos_generales(datos):
    """Filas de la tabla de DATOS GENERALES, compartidas por el PDF y el Word para que
    sean idénticos. Cada fila es [(etiqueta, valor)] (fila completa) o [izq, der].
    valor puede ser texto o ("link", url, texto)."""
    g = datos["generales"]
    adultos = int(datos.get("adultos") or 0)
    menores = int(datos.get("menores") or 0)
    lat = (datos.get("latitud") or "").strip()
    lon = (datos.get("longitud") or "").strip()
    inspector = (datos.get("inspector") or "").strip()
    gps = ("link", f"https://www.google.com/maps?q={lat},{lon}", f"Ver ubicación satelital ({lat}, {lon})") if lat and lon else "No registrada"
    colapsado = colapso_activo(g)

    izq = [
        ("PARROQUIA:", (datos.get("parroquia", "") + ", Brión")),
        ("OCUPANTE:", datos.get("ocupante") or "Sin Identificar"),
        ("TELÉFONO:", datos.get("telefono") or "No registrado"),
        ("CÉDULA DEL BENEFICIARIO:", datos.get("cedula") or "No registrada"),
        ("PERSONAS QUE HABITAN:", f"{adultos + menores} ({adultos} adultos, {menores} menores)"),
        ("NÚMERO DE NIVELES:", datos.get("niveles") or "No registrado"),
        ("OCUPACIÓN ACTUAL:", datos.get("ocupacion", "")),
        ("TENENCIA:", datos.get("tenencia") or "No registrada"),
        ("FECHA:", datos.get("fecha", "")),
    ]
    if inspector:
        izq.append(("INSPECTOR:", inspector))
    der = [
        ("TECNOLOGÍA CONSTRUCTIVA:", datos.get("tecnologia_constructiva", "")),
        ("TIPOLOGÍA:", datos.get("tipologia", "")),
        ("UBICACIÓN GPS:", gps),
        ("COLAPSO DE LA ESTRUCTURA:", g.get("colapso") or COLAPSO_NINGUNO),
    ]
    if not colapsado:
        der.extend([
            ("ASENTAMIENTO DEL TERRENO:", g["asentamiento"]),
            ("INCLINACIÓN / DESPLOME:", g["inclinacion"]),
            ("ESTRUCTURA VECINA EN RIESGO:", g["vecino_riesgo"]),
            ("RIESGO DE CAÍDA (cables, tanques, muros):", g["riesgo_caida"]),
            ("SERVICIOS BÁSICOS:", g["servicios"]),
        ])
    filas = [[("DIRECCIÓN:", datos.get("vivienda", ""))]]
    filas += [[a, b] for a, b in zip_longest(izq, der)]
    return filas


def carpeta_guardado(preferida):
    os.makedirs(preferida, exist_ok=True)
    return preferida


def ruta_pdf(identificador, carpeta):
    slug = "".join(c if c.isalnum() else "_" for c in identificador)[:60]
    fecha_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(carpeta, f"Semaforo_{slug}_{fecha_str}.pdf")


def calcular_semaforo(espacios, techo_marcado, generales):
    """espacios: dict clave -> {"estructural": [..], "no_estructural": [..],
                                 "cantidades_estructural": {valor: cantidad}}
       techo_marcado: lista de valores marcados para techo
       generales: dict con 'inclinacion' y 'asentamiento'

    Recorre TODOS los espacios de ESPACIOS_REGULARES (incluidas las fachadas), el techo,
    la inclinación de la vivienda y el asentamiento del terreno. El color final es
    siempre el más grave entre todos los factores (rojo > amarillo > verde).

    Si generales["colapso"] es Posible, Parcial o Total, el resultado es ROJO de inmediato
    y no se evalúa nada más.
    """
    if colapso_activo(generales):
        return COLOR_ROJO, ETIQ_ROJO, _MOTIVO_COLAPSO[generales["colapso"]]

    hay_colapso = False
    elementos_estructurales_graves = 0  # suma de columnas/vigas individuales con daño severo (no colapso)
    espacios_con_dano_no_estructural_relevante = []  # grietas o desprendimiento (no fisuras leves solas)
    hay_fisuras_leves = False
    hay_grietas_leves_estructura = False  # columna o viga con grietas leves (no severas)
    hay_dano_pared_cualquiera = False  # cualquier daño en pared/friso, incluyendo fisuras leves

    for clave, nombre in ESPACIOS_REGULARES:
        datos = espacios.get(clave, {"estructural": [], "no_estructural": [], "cantidades_estructural": {}})
        cantidades = datos.get("cantidades_estructural", {})

        for v in datos["estructural"]:
            try:
                cant = max(1, int(cantidades.get(v, 1) or 1))
            except (TypeError, ValueError):
                cant = 1
            if v.endswith("_colapso"):
                hay_colapso = True
            elif v.endswith("_severo"):
                elementos_estructurales_graves += cant
            elif v.endswith("_leve"):
                hay_grietas_leves_estructura = True

        no_estr = datos["no_estructural"]
        if "colapso" in no_estr:
            hay_colapso = True
        if "grietas" in no_estr or "desprendimiento" in no_estr:
            espacios_con_dano_no_estructural_relevante.append(nombre)
            hay_dano_pared_cualquiera = True
        elif "fisuras" in no_estr:
            hay_fisuras_leves = True
            hay_dano_pared_cualquiera = True

    sev_techo = max([_RANGO_TECHO.get(v, 0) for v in techo_marcado], default=0)
    if sev_techo == 3:
        hay_colapso = True
    elif sev_techo == 2:
        espacios_con_dano_no_estructural_relevante.append("Techo/Cubierta")
        hay_dano_pared_cualquiera = True
    elif sev_techo == 1:
        hay_fisuras_leves = True

    inclinacion = generales.get("inclinacion")
    asentamiento = generales.get("asentamiento")
    inclinacion_severa = inclinacion == "Severa"
    inclinacion_moderada = inclinacion == "Moderada"
    hundimiento_severo = asentamiento == ASENT_SEVERO
    hundimiento_leve = asentamiento == ASENT_LEVE
    grietas_terreno = asentamiento == ASENT_GRIETAS

    # ---- ROJO: cualquiera de estas condiciones decide el color
    motivos_rojo = []
    if hay_colapso:
        motivos_rojo.append("Se detectó colapso estructural en al menos un elemento.")
    if inclinacion_severa:
        motivos_rojo.append("Inclinación o desplome severo de la vivienda.")
    if hundimiento_severo:
        motivos_rojo.append("Hundimiento severo del terreno en o junto a la vivienda.")
    if elementos_estructurales_graves >= 3:
        motivos_rojo.append(
            f"Se detectaron {elementos_estructurales_graves} elementos estructurales (columnas/vigas) con daño severo — daño generalizado."
        )
    if motivos_rojo:
        return COLOR_ROJO, ETIQ_ROJO, " ".join(motivos_rojo)

    # ---- AMARILLO
    motivos_amarillo = []
    if elementos_estructurales_graves >= 1:
        motivos_amarillo.append(
            f"Se detectaron {elementos_estructurales_graves} elemento(s) estructural(es) con daño severo (aislado). Se recomienda evaluación técnica formal antes de usar esa zona."
        )
    if espacios_con_dano_no_estructural_relevante:
        motivos_amarillo.append(
            "Daño no estructural relevante (grietas o desprendimiento) en: "
            + ", ".join(espacios_con_dano_no_estructural_relevante) + "."
        )
    if hay_grietas_leves_estructura and hay_dano_pared_cualquiera:
        motivos_amarillo.append(
            "Se detectaron grietas leves en columna(s) o viga(s) junto con daño en pared o friso (grietas o fisuras). La combinación amerita evaluación técnica antes de considerar la vivienda plenamente habitable."
        )
    if inclinacion_moderada:
        motivos_amarillo.append("Inclinación o desplome moderado de la vivienda.")
    if grietas_terreno:
        motivos_amarillo.append("Grietas en piso o patio por asentamiento del terreno.")
    if hundimiento_leve:
        motivos_amarillo.append("Hundimiento leve del terreno en el patio, alejado de la vivienda.")
    if motivos_amarillo:
        return COLOR_AMARILLO, ETIQ_AMARILLO, " ".join(motivos_amarillo)

    # ---- VERDE
    if hay_fisuras_leves:
        return COLOR_VERDE, ETIQ_VERDE, \
            "Se registran fisuras leves superficiales en paredes o friso; no comprometen la habitabilidad."
    return COLOR_VERDE, ETIQ_VERDE, "Sin daño relevante."


# Paleta y medidas del Word (docx_semaforo.py) para que el PDF sea igual
_AZUL = "#1A365D"
_GRIS_ETQ = "#E2E8F0"
_BORDE_SUAVE = "#CBD5E0"
_ANCHO_UTIL = 17.9 * cm
_LINEAS_MEMBRETE = [
    "SECRETARÍA PARA LA TRANSFORMACIÓN DE LAS CIUDADES HUMANAS Y SERVICIOS",
    "DIRECCIÓN DE INGENIERÍA MUNICIPAL",
    "DIRECCIÓN DE HÁBITAT Y VIVIENDA · RIF G-20002924-2",
]


def _estilos_pdf():
    base = getSampleStyleSheet()["Normal"]
    azul = colors.HexColor(_AZUL)

    def st(nombre, **kw):
        kw.setdefault("fontName", "Helvetica")
        kw.setdefault("fontSize", 9)
        kw.setdefault("leading", 11)
        return ParagraphStyle(nombre, parent=base, **kw)

    return {
        "titulo": st("Titulo", fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=azul, alignment=1, spaceAfter=2),
        "sec": st("Sec", fontName="Helvetica-Bold", fontSize=10, leading=13, textColor=azul, spaceBefore=8, spaceAfter=4),
        "etq": st("Etq", fontName="Helvetica-Bold", textColor=azul),
        "val": st("Val"),
        "link": st("Link", textColor=colors.HexColor("#1155CC")),
        "th": st("Th", fontName="Helvetica-Bold", textColor=colors.white, alignment=1),
        "tb": st("Tb"),
        "rojo": st("Rojo", fontName="Helvetica-Bold", textColor=colors.HexColor("#C0392B")),
        "amar": st("Amar", fontName="Helvetica-Bold", textColor=colors.HexColor("#D68910")),
        "verde": st("Verde", fontName="Helvetica-Bold", textColor=colors.HexColor("#27AE60")),
        "pie_foto": st("PieFoto", fontName="Helvetica-Bold", textColor=azul, alignment=1),
        "nota": st("Nota", fontName="Helvetica-Oblique", fontSize=7.5, leading=9, textColor=colors.HexColor("#5D6D7E")),
        "res": st("Res", fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=colors.white),
        "motivo": st("Motivo", leading=12),
    }


def _tabla_datos_pdf(datos, est):
    filas = filas_datos_generales(datos)
    anchos = [3.88 * cm, 5.07 * cm, 3.88 * cm, 5.07 * cm]
    data, cmds = [], []
    for i, fila in enumerate(filas):
        if len(fila) == 1:
            etq, val = fila[0]
            data.append([Paragraph(etq, est["etq"]), Paragraph(escape(str(val)), est["val"]), "", ""])
            cmds += [("SPAN", (1, i), (3, i)), ("BACKGROUND", (0, i), (0, i), colors.HexColor(_GRIS_ETQ))]
            continue
        row = []
        for j, item in enumerate(fila):
            if item is None:
                row += ["", ""]
                continue
            etq, val = item
            row.append(Paragraph(etq, est["etq"]))
            if isinstance(val, tuple) and val[0] == "link":
                row.append(Paragraph(f'<link href="{val[1]}"><u>{escape(val[2])}</u></link>', est["link"]))
            else:
                row.append(Paragraph(escape(str(val)), est["val"]))
            cmds.append(("BACKGROUND", (j * 2, i), (j * 2, i), colors.HexColor(_GRIS_ETQ)))
        data.append(row)
    t = Table(data, colWidths=anchos)
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor(_BORDE_SUAVE)),
        ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor(_AZUL)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ] + cmds))
    return t


def _con_cantidades(valores, mapa, cantidades):
    partes = []
    for v in valores:
        texto = mapa[v]
        cant = cantidades.get(v)
        if cant and str(cant).strip() not in ("", "1"):
            texto += f" (x{cant})"
        partes.append(texto)
    return ", ".join(partes)


def generar_pdf(datos, carpeta):
    """PDF con el mismo diseño, letra (Arial/Helvetica), colores y datos que el Word."""
    archivo_salida = ruta_pdf(datos.get("vivienda", "SIN_NOMBRE"), carpeta)
    doc = SimpleDocTemplate(
        archivo_salida, pagesize=letter,
        leftMargin=1.3 * cm, rightMargin=1.3 * cm,
        topMargin=4.9 * cm, bottomMargin=2.6 * cm,
    )

    def dibujar_fondo(c, doc_):
        ancho, alto = letter
        if os.path.isfile(RUTA_MEMBRETE):
            c.drawImage(RUTA_MEMBRETE, 0, 0, width=ancho, height=alto, preserveAspectRatio=False, mask="auto")
        # Líneas completas del membrete (Secretaría, Ingeniería, Hábitat y Vivienda) en TODAS las páginas,
        # como en el encabezado del Word. Van justo debajo de la franja del membrete.
        c.setFillColor(colors.HexColor("#4A5568"))
        c.setFont("Helvetica", 7)
        y = alto - 100
        for linea in _LINEAS_MEMBRETE:
            c.drawCentredString(ancho / 2, y, linea)
            y -= 9.5

    est = _estilos_pdf()
    azul = colors.HexColor(_AZUL)
    borde = colors.HexColor(_BORDE_SUAVE)
    g = datos["generales"]
    colapsado = colapso_activo(g)
    info_techo = datos.get("techo", {"marcado": [], "nota": "", "foto": None})

    elementos = [
        Paragraph("EVALUACIÓN RÁPIDA DE DAÑOS POST-SÍSMICO (SEMÁFORO)", est["titulo"]),
        Paragraph("I. DATOS GENERALES", est["sec"]),
        _tabla_datos_pdf(datos, est),
        CondPageBreak(4 * cm),  # el título no queda solo al final de una hoja
        Paragraph("II. EVALUACIÓN POR ESPACIO", est["sec"]),
    ]

    fotos_galeria = list(fotos_colapso(datos)) if colapsado else []

    if colapsado:
        elementos.append(Paragraph("No se realizó la evaluación por espacio porque se reportó colapso de la estructura.", est["val"]))
    else:
        filas = [[Paragraph(h, est["th"]) for h in ["Espacio", "Daño estructural", "Daño no estructural", "Nota / ubicación"]]]
        for clave, nombre in ESPACIOS_REGULARES:
            info = datos["espacios"].get(clave, {"estructural": [], "no_estructural": [], "cantidades_estructural": {}, "cantidades_no_estructural": {}, "nota": "", "foto": None})
            sev = max([_RANGO_ESTRUCTURAL.get(v, 0) for v in info["estructural"]], default=0)
            t_e = _con_cantidades(info["estructural"], _MAPA_ESTRUCTURAL, info.get("cantidades_estructural", {})) or "Sin daño"
            t_n = _con_cantidades(info["no_estructural"], _MAPA_NO_ESTRUCTURAL, info.get("cantidades_no_estructural", {})) or "Sin daño"
            st_e = est["rojo"] if sev >= 2 else (est["amar"] if sev == 1 else est["verde"])
            st_n = est["rojo"] if "colapso" in info["no_estructural"] else (est["amar"] if info["no_estructural"] else est["verde"])
            filas.append([
                Paragraph(nombre, est["tb"]), Paragraph(t_e, st_e), Paragraph(t_n, st_n),
                Paragraph(escape(info.get("nota") or "-"), est["tb"]),
            ])
            if info.get("foto") and os.path.isfile(info["foto"]):
                fotos_galeria.append((nombre, info["foto"]))

        t_t = ", ".join(_MAPA_TECHO[v] for v in info_techo["marcado"]) if info_techo["marcado"] else "Sin daño"
        st_t = est["rojo"] if ("colapso" in info_techo["marcado"] or "parcial" in info_techo["marcado"]) else (est["amar"] if info_techo["marcado"] else est["verde"])
        filas.append([Paragraph("TECHO / CUBIERTA", est["tb"]), Paragraph("—", est["tb"]), Paragraph(t_t, st_t), Paragraph(escape(info_techo.get("nota") or "-"), est["tb"])])
        if info_techo.get("foto") and os.path.isfile(info_techo["foto"]):
            fotos_galeria.append(("Techo / Cubierta", info_techo["foto"]))

        t_esp = Table(filas, colWidths=[3.0 * cm, 5.2 * cm, 5.2 * cm, 4.5 * cm], repeatRows=1)
        t_esp.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), azul),
            ("GRID", (0, 0), (-1, -1), 0.5, borde),
            ("BOX", (0, 0), (-1, -1), 0.75, azul),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ]))
        elementos.append(t_esp)

    elementos.append(Spacer(1, 10))

    color_hex, etiqueta, motivo = calcular_semaforo(datos["espacios"], info_techo["marcado"], g)
    caja = Table(
        [[Paragraph(f"RESOLUCIÓN: {etiqueta}", est["res"])],
         [Paragraph(f"<b>Motivo:</b> {escape(motivo)}", est["motivo"])]],
        colWidths=[_ANCHO_UTIL],
    )
    caja.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), colors.HexColor(color_hex)),
        ("BOX", (0, 0), (-1, -1), 2, colors.HexColor(color_hex)),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    elementos.append(KeepTogether([
        caja, Spacer(1, 4),
        Paragraph("Esta clasificación es una evaluación visual preliminar. La decisión de demolición corresponde exclusivamente a una evaluación estructural formal.", est["nota"]),
    ]))

    inspeccion, medidas = acciones_recomendadas(datos)
    if inspeccion or medidas:
        bloque = [Paragraph("ACCIONES RECOMENDADAS", est["sec"])]
        if inspeccion:
            bloque.append(Paragraph("<b>Inspección detallada:</b> " + escape(", ".join(inspeccion)), est["val"]))
        if medidas:
            bloque.append(Spacer(1, 3))
            bloque.append(Paragraph("<b>Medidas de prevención:</b> " + escape(", ".join(medidas)), est["val"]))
        elementos.append(KeepTogether(bloque))

    observaciones = (datos.get("observaciones_generales") or "").strip()
    if observaciones:
        elementos.append(Paragraph("OBSERVACIONES GENERALES", est["sec"]))
        for linea in observaciones.splitlines():
            elementos.append(Paragraph(escape(linea) or "&nbsp;", est["val"]))

    if fotos_galeria:
        elementos.extend([PageBreak(), Paragraph("III. REGISTRO FOTOGRÁFICO", est["sec"]), Spacer(1, 4)])
        LADO_GALERIA = 8.0 * cm  # fotos cuadradas (recorte centrado), 2 por fila
        celdas = []
        for etiqueta_foto, ruta_foto in fotos_galeria:
            try:
                img_flowable = Image(recortar_cuadrado(ruta_foto), width=LADO_GALERIA, height=LADO_GALERIA)
            except Exception:
                img_flowable = Paragraph("(no se pudo cargar la imagen)", est["tb"])
            celdas.append([img_flowable, Paragraph(etiqueta_foto, est["pie_foto"])])

        filas_galeria = []
        for i in range(0, len(celdas), 2):
            grupo = celdas[i:i + 2]
            filas_galeria.append([c[0] for c in grupo] + [""] * (2 - len(grupo)))
            filas_galeria.append([c[1] for c in grupo] + [""] * (2 - len(grupo)))
        t_galeria = Table(filas_galeria, colWidths=[8.95 * cm, 8.95 * cm])
        t_galeria.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        elementos.append(t_galeria)

    doc.build(elementos, onFirstPage=dibujar_fondo, onLaterPages=dibujar_fondo)
    return archivo_salida, color_hex, etiqueta
