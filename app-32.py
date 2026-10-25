import os
import re
import uuid
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, send_file

import logic_semaforo

# El Word es opcional: si falta python-docx o algo falla al importar, la app arranca igual
# y la página final muestra el motivo en lugar de caerse el servidor.
try:
    import docx_semaforo
    ERROR_IMPORT_DOCX = None
except Exception as e:
    docx_semaforo = None
    ERROR_IMPORT_DOCX = f"{type(e).__name__}: {e}"

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "cambia-esta-clave-en-produccion")
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 25 MB por solicitud

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CARPETA = logic_semaforo.carpeta_guardado(DATA_DIR)
FOTOS_DIR = os.path.join(DATA_DIR, "fotos")
os.makedirs(FOTOS_DIR, exist_ok=True)

EXTENSIONES_PERMITIDAS = {".jpg", ".jpeg", ".png", ".webp"}


def guardar_foto(archivo, prefijo):
    if not archivo or not archivo.filename:
        return None
    ext = os.path.splitext(archivo.filename)[1].lower()
    if ext not in EXTENSIONES_PERMITIDAS:
        ext = ".jpg"
    slug = re.sub(r"[^A-Za-z0-9_-]", "_", prefijo)[:60]
    nombre = f"{slug}_{uuid.uuid4().hex[:8]}{ext}"
    ruta = os.path.join(FOTOS_DIR, nombre)
    archivo.save(ruta)
    return ruta


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        return render_template("semaforo_form.html", logic_semaforo=logic_semaforo, datetime=datetime)

    f = request.form
    vivienda = f.get("vivienda", "").strip() or "Sin Identificar"

    # Recorre todos los espacios definidos en logic_semaforo.ESPACIOS_REGULARES
    # (sala, comedor, cocina, cuarto, baño y las cuatro fachadas).
    colapso = f.get("colapso", logic_semaforo.COLAPSO_NINGUNO)
    if colapso not in logic_semaforo.OPC_COLAPSO:
        colapso = logic_semaforo.COLAPSO_NINGUNO
    hay_colapso = colapso != logic_semaforo.COLAPSO_NINGUNO

    # Con colapso (posible, parcial o total) no se evalúan los espacios: el resultado es ROJO.
    espacios = {}
    for clave, _ in ([] if hay_colapso else logic_semaforo.ESPACIOS_REGULARES):
        ruta_foto = guardar_foto(request.files.get(f"foto_{clave}"), f"{vivienda}_{clave}")
        estructural_marcado = f.getlist(f"estructural_{clave}")
        cantidades_estructural = {}
        for valor in estructural_marcado:
            cantidades_estructural[valor] = f.get(f"cant_estructural_{clave}_{valor}") or "1"
        no_estructural_marcado = f.getlist(f"no_estructural_{clave}")
        cantidades_no_estructural = {}
        for valor in no_estructural_marcado:
            cantidades_no_estructural[valor] = f.get(f"cant_no_estructural_{clave}_{valor}") or "1"
        espacios[clave] = {
            "estructural": estructural_marcado,
            "cantidades_estructural": cantidades_estructural,
            "no_estructural": no_estructural_marcado,
            "cantidades_no_estructural": cantidades_no_estructural,
            "nota": f.get(f"nota_{clave}", ""),
            "foto": ruta_foto,
        }

    fotos_colapso_fachadas = {}
    if hay_colapso:
        techo = {"marcado": [], "nota": "", "foto": None}
        ruta_foto_colapso = guardar_foto(request.files.get("foto_colapso"), f"{vivienda}_colapso")
        # Con colapso se permiten igual las fotos de las 4 fachadas
        for clave, _ in logic_semaforo.FACHADAS:
            ruta = guardar_foto(request.files.get(f"foto_colapso_{clave}"), f"{vivienda}_{clave}")
            if ruta:
                fotos_colapso_fachadas[clave] = ruta
    else:
        ruta_foto_techo = guardar_foto(request.files.get("foto_techo"), f"{vivienda}_techo")
        techo = {
            "marcado": f.getlist("techo"),
            "nota": f.get("nota_techo", ""),
            "foto": ruta_foto_techo,
        }
        ruta_foto_colapso = None

    # Acciones recomendadas (selección múltiple + texto libre para "Otra")
    inspeccion = [v for v in f.getlist("accion_inspeccion") if v in logic_semaforo._MAPA_INSPECCION]
    otra_inspeccion = f.get("otra_inspeccion", "").strip()
    if otra_inspeccion and "otra" not in inspeccion:
        inspeccion.append("otra")
    medidas = [v for v in f.getlist("accion_medida") if v in logic_semaforo._MAPA_MEDIDAS]
    otra_medida = f.get("otra_medida", "").strip()
    if otra_medida and "otra" not in medidas:
        medidas.append("otra")

    datos = {
        "vivienda": vivienda,
        "ocupante": f.get("ocupante", "").strip(),
        "cedula": f.get("cedula", "").strip(),
        "telefono": f.get("telefono", "").strip(),
        "adultos": f.get("adultos", "0"),
        "menores": f.get("menores", "0"),
        "parroquia": f.get("parroquia", ""),
        "tipologia": f.get("tipologia", ""),
        "tecnologia_constructiva": f.get("tecnologia_constructiva", ""),
        "niveles": f.get("niveles", ""),
        "ocupacion": f.get("ocupacion", ""),
        "tenencia": f.get("tenencia", ""),
        "fecha": f.get("fecha") or datetime.now().strftime("%d/%m/%Y"),
        "latitud": f.get("latitud", ""),
        "longitud": f.get("longitud", ""),
        "inspector": f.get("inspector", ""),
        "foto_colapso": ruta_foto_colapso,
        "fotos_colapso_fachadas": fotos_colapso_fachadas,
        "acciones": {
            "inspeccion": inspeccion,
            "otra_inspeccion": otra_inspeccion,
            "medidas": medidas,
            "otra_medida": otra_medida,
        },
        "generales": {
            "colapso": colapso,
            "inclinacion": f.get("inclinacion", ""),
            "asentamiento": f.get("asentamiento", ""),
            "riesgo_caida": f.get("riesgo_caida", ""),
            "vecino_riesgo": f.get("vecino_riesgo", ""),
            "servicios": f.get("servicios", ""),
        },
        "espacios": espacios,
        "techo": techo,
        "observaciones_generales": f.get("observaciones_generales", ""),
    }

    ruta_pdf, color_hex, etiqueta = logic_semaforo.generar_pdf(datos, CARPETA)

    # Word sobre la hoja membretada de la ficha. Si falla, el PDF sigue funcionando.
    nombre_docx = None
    error_docx = None
    try:
        if docx_semaforo is None:
            raise RuntimeError(ERROR_IMPORT_DOCX)
        ruta_docx, _, _ = docx_semaforo.generar_docx(datos, CARPETA)
        nombre_docx = os.path.basename(ruta_docx)
    except Exception as e:
        app.logger.exception("No se pudo generar el Word del semáforo: %s", e)
        error_docx = f"{type(e).__name__}: {e}"

    return render_template(
        "semaforo_listo.html",
        nombre_archivo=os.path.basename(ruta_pdf),
        nombre_docx=nombre_docx,
        error_docx=error_docx,
        color_hex=color_hex,
        etiqueta=etiqueta,
    )


@app.route("/descargar/<nombre_archivo>")
def descargar(nombre_archivo):
    ruta = os.path.join(CARPETA, nombre_archivo)
    return send_file(ruta, as_attachment=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
