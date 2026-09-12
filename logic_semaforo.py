import os
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable, Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

try:
    from PIL import Image as PILImage
except ImportError:
    PILImage = None

RUTA_MEMBRETE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "membrete_fondo.jpg")
CARPETA_TEMP_FOTOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "_temp_fotos_pdf")


def recortar_cuadrado(ruta_foto):
    """Recorta una foto al centro para dejarla cuadrada (1:1) y la guarda como
    archivo temporal. Devuelve la ruta del recorte, o la ruta original si falla."""
    if PILImage is None:
        return ruta_foto
    try:
        os.makedirs(CARPETA_TEMP_FOTOS, exist_ok=True)
        im = PILImage.open(ruta_foto)
        im = im.convert("RGB")
        w, h = im.size
        lado = min(w, h)
        izq = (w - lado) // 2
        arriba = (h - lado) // 2
        recorte = im.crop((izq, arriba, izq + lado, arriba + lado))
        nombre = f"cuad_{os.path.splitext(os.path.basename(ruta_foto))[0]}.jpg"
        ruta_salida = os.path.join(CARPETA_TEMP_FOTOS, nombre)
        recorte.save(ruta_salida, "JPEG", quality=88)
        return ruta_salida
    except Exception:
        return ruta_foto

OPC_TIPOLOGIA = ["Unifamiliar", "Bifamiliar", "Multifamiliar", "Comercial"]
OPC_OCUPACION = ["Habitada", "Desocupada"]
OPC_TECNOLOGIA = ["Kit Estructural", "Concreto Armado", "Estructura Aporticada"]
OPC_INCLINACION = ["Ninguna", "Leve", "Moderada", "Severa"]
OPC_ASENTAMIENTO = ["No se observa", "Grietas en piso o patio", "Hundimiento visible"]
OPC_SI_NO = ["No", "Sí"]
OPC_SERVICIOS = ["Operativos", "Parcialmente interrumpidos", "Totalmente interrumpidos"]
OPC_CANTIDAD_PERSONAS = [str(i) for i in range(0, 16)]

ESPACIOS_REGULARES = [
    ("sala", "Sala"), ("comedor", "Comedor"), ("cocina", "Cocina"),
    ("cuarto", "Cuarto(s)"), ("banio", "Baño(s)"),
]

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
       generales: dict con 'inclinacion'
    """
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

    inclinacion_severa = generales.get("inclinacion") == "Severa"

    if hay_colapso or inclinacion_severa:
        color_hex, etiqueta, motivo = "#C0392B", "ROJO — NO HABITABLE HASTA SER REPARADA", \
            "Se detectó colapso estructural en al menos un elemento, o inclinación severa de la vivienda."
    elif elementos_estructurales_graves >= 3:
        color_hex, etiqueta, motivo = "#C0392B", "ROJO — NO HABITABLE HASTA SER REPARADA", \
            f"Se detectaron {elementos_estructurales_graves} elementos estructurales (columnas/vigas) con daño severo — daño generalizado."
    elif elementos_estructurales_graves >= 1:
        color_hex, etiqueta, motivo = "#D68910", "AMARILLO — REPARABLE / ACCESO RESTRINGIDO", \
            f"Se detectaron {elementos_estructurales_graves} elemento(s) estructural(es) con daño severo (aislado). Se recomienda evaluación técnica formal antes de usar esa zona."
    elif espacios_con_dano_no_estructural_relevante:
        color_hex, etiqueta, motivo = "#D68910", "AMARILLO — REPARABLE / ACCESO RESTRINGIDO", \
            "Daño no estructural relevante (grietas o desprendimiento) en: " + ", ".join(espacios_con_dano_no_estructural_relevante) + "."
    elif hay_grietas_leves_estructura and hay_dano_pared_cualquiera:
        color_hex, etiqueta, motivo = "#D68910", "AMARILLO — REPARABLE / ACCESO RESTRINGIDO", \
            "Se detectaron grietas leves en columna(s) o viga(s) junto con daño en pared o friso (grietas o fisuras). La combinación amerita evaluación técnica antes de considerar la vivienda plenamente habitable."
    elif hay_fisuras_leves:
        color_hex, etiqueta, motivo = "#27AE60", "VERDE — HABITABLE", \
            "Se registran fisuras leves superficiales en paredes o friso; no comprometen la habitabilidad."
    else:
        color_hex, etiqueta, motivo = "#27AE60", "VERDE — HABITABLE", "Sin daño relevante."

    return color_hex, etiqueta, motivo


def generar_pdf(datos, carpeta):
    archivo_salida = ruta_pdf(datos.get("vivienda", "SIN_NOMBRE"), carpeta)
    doc = SimpleDocTemplate(
        archivo_salida, pagesize=letter,
        leftMargin=1.3 * cm, rightMargin=1.3 * cm,
        topMargin=4.6 * cm, bottomMargin=2.6 * cm,
    )

    def dibujar_fondo(c, doc_):
        ancho, alto = letter
        if os.path.isfile(RUTA_MEMBRETE):
            c.drawImage(RUTA_MEMBRETE, 0, 0, width=ancho, height=alto, preserveAspectRatio=False, mask="auto")

    styles = getSampleStyleSheet()
    c_azul = colors.HexColor("#16294A")
    c_oro = colors.HexColor("#D4AC0D")

    # Tamaños de fuente aumentados respecto al original (8->9.5, 10->11.5, 13->15, etc.)
    st_sec = ParagraphStyle("Sec", parent=styles["Normal"], fontName="Times-Bold", fontSize=11.5, textColor=c_azul)
    st_etq = ParagraphStyle("Etq", parent=styles["Normal"], fontName="Times-Bold", fontSize=9.5, textColor=colors.HexColor("#5B5346"))
    st_val = ParagraphStyle("Val", parent=styles["Normal"], fontName="Times-Roman", fontSize=9.5, textColor=colors.black)
    st_link = ParagraphStyle("Link", parent=styles["Normal"], fontName="Times-Roman", fontSize=9.5, textColor=colors.HexColor("#1155CC"))
    st_th = ParagraphStyle("Th", parent=styles["Normal"], fontName="Times-Bold", fontSize=9.5, textColor=c_oro, alignment=1)
    st_tb = ParagraphStyle("Tb", parent=styles["Normal"], fontName="Times-Roman", fontSize=9.5, leading=12)
    st_alerta = ParagraphStyle("Alerta", parent=styles["Normal"], fontName="Times-Bold", fontSize=9.5, textColor=colors.HexColor("#C0392B"))
    st_ok = ParagraphStyle("Ok", parent=styles["Normal"], fontName="Times-Bold", fontSize=9.5, textColor=colors.HexColor("#27AE60"))
    st_leve = ParagraphStyle("Leve", parent=styles["Normal"], fontName="Times-Bold", fontSize=9.5, textColor=colors.HexColor("#D68910"))
    st_pie_foto = ParagraphStyle("PieFoto", parent=styles["Normal"], fontName="Times-Bold", fontSize=9.5, textColor=c_azul, alignment=1)
    st_nota = ParagraphStyle("Nota", parent=styles["Normal"], fontName="Times-Italic", fontSize=8.5, textColor=colors.HexColor("#5D6D7E"))

    elementos = [
        Paragraph(
            "SECRETARÍA PARA LA TRANSFORMACIÓN DE LAS CIUDADES, HÁBITAT Y SERVICIOS · "
            "INGENIERÍA MUNICIPAL · DIRECCIÓN DE HÁBITAT Y VIVIENDA · RIF G-20002924-2",
            ParagraphStyle("Dep", parent=styles["Normal"], fontName="Times-Bold", fontSize=9, textColor=c_azul, leading=11),
        ),
        Spacer(1, 4),
        Paragraph("EVALUACIÓN RÁPIDA DE DAÑOS POST-SÍSMICO (SEMÁFORO)", ParagraphStyle("Tit", parent=styles["Normal"], fontName="Times-Bold", fontSize=15, textColor=c_azul)),
        Spacer(1, 10),
        Paragraph("I. DATOS GENERALES", st_sec),
        HRFlowable(width="100%", thickness=1, color=c_oro, spaceBefore=3, spaceAfter=6),
    ]

    f = lambda l, v: [Paragraph(l, st_etq), Paragraph(str(v), st_val)]
    filas_gen = [
        f("VIVIENDA / DIRECCIÓN:", datos.get("vivienda", "")),
        f("PROPIETARIO:", datos.get("propietario") or "Sin Identificar"),
        f("CÉDULA DEL BENEFICIARIO:", datos.get("cedula") or "No registrada"),
        f("TELÉFONO:", datos.get("telefono") or "No registrado"),
        f("PARROQUIA:", datos.get("parroquia", "") + ", Brión"),
        f("TIPOLOGÍA:", datos.get("tipologia", "")),
        f("TECNOLOGÍA CONSTRUCTIVA:", datos.get("tecnologia_constructiva", "")),
        f("OCUPACIÓN ACTUAL:", datos.get("ocupacion", "")),
        f("PERSONAS QUE HABITAN LA VIVIENDA:", f"{int(datos.get('adultos') or 0) + int(datos.get('menores') or 0)} ({datos.get('adultos') or 0} adultos, {datos.get('menores') or 0} menores)"),
        f("FECHA:", datos.get("fecha", "")),
    ]
    lat = (datos.get("latitud") or "").strip()
    lon = (datos.get("longitud") or "").strip()
    if lat and lon:
        enlace = f'<link href="https://www.google.com/maps?q={lat},{lon}"><u>Ver ubicación satelital ({lat}, {lon})</u></link>'
        filas_gen.append([Paragraph("UBICACIÓN GPS:", st_etq), Paragraph(enlace, st_link)])
    else:
        filas_gen.append(f("UBICACIÓN GPS:", "No registrada"))
    if (datos.get("inspector") or "").strip():
        filas_gen.append(f("INSPECTOR:", datos["inspector"].strip()))

    filas_gen.extend([
        f("INCLINACIÓN / DESPLOME:", datos["generales"]["inclinacion"]),
        f("ASENTAMIENTO DEL TERRENO:", datos["generales"]["asentamiento"]),
        f("RIESGO DE CAÍDA (cables, tanques, muros):", datos["generales"]["riesgo_caida"]),
        f("ESTRUCTURA VECINA EN RIESGO:", datos["generales"]["vecino_riesgo"]),
        f("SERVICIOS BÁSICOS:", datos["generales"]["servicios"]),
    ])
    t_gen = Table(filas_gen, colWidths=[6.5 * cm, 11.5 * cm])
    t_gen.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7E9")), ("PADDING", (0, 0), (-1, -1), 4)]))
    elementos.extend([t_gen, Spacer(1, 14), Paragraph("II. EVALUACIÓN POR ESPACIO", st_sec), HRFlowable(width="100%", thickness=1, color=c_oro, spaceBefore=3, spaceAfter=6)])

    fotos_galeria = []

    filas = [[Paragraph(h, st_th) for h in ["Espacio", "Daño estructural", "Daño no estructural", "Nota / ubicación"]]]
    for clave, nombre in ESPACIOS_REGULARES:
        info = datos["espacios"].get(clave, {"estructural": [], "no_estructural": [], "cantidades_estructural": {}, "cantidades_no_estructural": {}, "nota": "", "foto": None})
        cantidades = info.get("cantidades_estructural", {})
        cantidades_no_estr = info.get("cantidades_no_estructural", {})
        sev_estr = max([_RANGO_ESTRUCTURAL.get(v, 0) for v in info["estructural"]], default=0)

        partes_estr = []
        for v in info["estructural"]:
            texto_item = _MAPA_ESTRUCTURAL[v]
            cant = cantidades.get(v)
            if cant and str(cant).strip() not in ("", "1"):
                texto_item += f" (x{cant})"
            partes_estr.append(texto_item)
        texto_estr = ", ".join(partes_estr) if partes_estr else "Sin daño"

        partes_no_estr = []
        for v in info["no_estructural"]:
            texto_item = _MAPA_NO_ESTRUCTURAL[v]
            cant = cantidades_no_estr.get(v)
            if cant and str(cant).strip() not in ("", "1"):
                texto_item += f" (x{cant})"
            partes_no_estr.append(texto_item)
        texto_no_estr = ", ".join(partes_no_estr) if partes_no_estr else "Sin daño"

        st_estr = st_alerta if sev_estr >= 2 else (st_leve if sev_estr == 1 else st_ok)
        st_no_estr = st_alerta if "colapso" in info["no_estructural"] else (st_leve if info["no_estructural"] else st_ok)

        filas.append([
            Paragraph(nombre, st_tb),
            Paragraph(texto_estr, st_estr),
            Paragraph(texto_no_estr, st_no_estr),
            Paragraph(info.get("nota") or "-", st_tb),
        ])
        if info.get("foto") and os.path.isfile(info["foto"]):
            fotos_galeria.append((nombre, info["foto"]))

    info_techo = datos.get("techo", {"marcado": [], "nota": "", "foto": None})
    texto_techo = ", ".join(_MAPA_TECHO[v] for v in info_techo["marcado"]) if info_techo["marcado"] else "Sin daño"
    st_techo = st_alerta if "colapso" in info_techo["marcado"] or "parcial" in info_techo["marcado"] else (st_leve if info_techo["marcado"] else st_ok)
    filas.append([Paragraph("TECHO / CUBIERTA", st_tb), Paragraph("—", st_tb), Paragraph(texto_techo, st_techo), Paragraph(info_techo.get("nota") or "-", st_tb)])
    if info_techo.get("foto") and os.path.isfile(info_techo["foto"]):
        fotos_galeria.append(("Techo / Cubierta", info_techo["foto"]))

    t_esp = Table(filas, colWidths=[3.3 * cm, 5.0 * cm, 5.0 * cm, 4.7 * cm])
    t_esp.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), c_azul), ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D5D8DC")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    elementos.extend([t_esp, Spacer(1, 16)])

    color_hex, etiqueta, motivo = calcular_semaforo(datos["espacios"], info_techo["marcado"], datos["generales"])
    caja = [
        [Paragraph(f"RESOLUCIÓN: {etiqueta}", ParagraphStyle("R", parent=styles["Normal"], fontName="Times-Bold", fontSize=13.5, textColor=colors.white))],
        [Paragraph(f"<b>Motivo:</b> {motivo}", ParagraphStyle("M", parent=styles["Normal"], fontName="Times-Roman", fontSize=10, textColor=colors.black, leading=13))],
    ]
    t_semaforo = Table(caja, colWidths=[17.9 * cm])
    t_semaforo.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), colors.HexColor(color_hex)),
        ("BOX", (0, 0), (-1, -1), 2, colors.HexColor(color_hex)),
        ("PADDING", (0, 0), (-1, -1), 10),
    ]))
    elementos.append(t_semaforo)
    elementos.extend([
        Spacer(1, 6),
        Paragraph("Esta clasificación es una evaluación visual preliminar. La decisión de demolición corresponde exclusivamente a una evaluación estructural formal.", st_nota),
    ])

    observaciones = (datos.get("observaciones_generales") or "").strip()
    if observaciones:
        elementos.extend([
            Spacer(1, 14),
            Paragraph("OBSERVACIONES GENERALES", st_sec),
            HRFlowable(width="100%", thickness=1, color=c_oro, spaceBefore=3, spaceAfter=6),
            Paragraph(observaciones.replace("\n", "<br/>"), st_val),
        ])

    if fotos_galeria:
        elementos.extend([
            PageBreak(),
            Paragraph("III. REGISTRO FOTOGRÁFICO", st_sec),
            HRFlowable(width="100%", thickness=1, color=c_oro, spaceBefore=3, spaceAfter=10),
        ])
        # Fotos cuadradas (recorte centrado) de tamaño fijo 8x8 cm, 2 columnas x 2 filas por página
        LADO_GALERIA = 8.0 * cm
        celdas = []
        for etiqueta_foto, ruta_foto in fotos_galeria:
            try:
                ruta_cuadrada = recortar_cuadrado(ruta_foto)
                img_flowable = Image(ruta_cuadrada, width=LADO_GALERIA, height=LADO_GALERIA)
            except Exception:
                img_flowable = Paragraph("(no se pudo cargar la imagen)", st_tb)
            celdas.append([img_flowable, Paragraph(etiqueta_foto, st_pie_foto)])

        filas_galeria = []
        for i in range(0, len(celdas), 2):
            grupo = celdas[i:i + 2]
            filas_galeria.append([c[0] for c in grupo] + [""] * (2 - len(grupo)))
            filas_galeria.append([c[1] for c in grupo] + [""] * (2 - len(grupo)))
        t_galeria = Table(filas_galeria, colWidths=[8.95 * cm, 8.95 * cm], rowHeights=None)
        t_galeria.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
        elementos.append(t_galeria)

    doc.build(elementos, onFirstPage=dibujar_fondo, onLaterPages=dibujar_fondo)
    return archivo_salida, color_hex, etiqueta
