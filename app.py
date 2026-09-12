import os
import re
import uuid
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, send_file

import logic_semaforo

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

    espacios = {}
    for clave, _ in logic_semaforo.ESPACIOS_REGULARES:
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

    ruta_foto_techo = guardar_foto(request.files.get("foto_techo"), f"{vivienda}_techo")
    techo = {
        "marcado": f.getlist("techo"),
        "nota": f.get("nota_techo", ""),
        "foto": ruta_foto_techo,
    }

    datos = {
        "vivienda": vivienda,
        "propietario": f.get("propietario", "").strip(),
        "cedula": f.get("cedula", "").strip(),
        "telefono": f.get("telefono", "").strip(),
        "adultos": f.get("adultos", "0"),
        "menores": f.get("menores", "0"),
        "parroquia": f.get("parroquia", ""),
        "tipologia": f.get("tipologia", ""),
        "tecnologia_constructiva": f.get("tecnologia_constructiva", ""),
        "ocupacion": f.get("ocupacion", ""),
        "fecha": f.get("fecha") or datetime.now().strftime("%d/%m/%Y"),
        "latitud": f.get("latitud", ""),
        "longitud": f.get("longitud", ""),
        "inspector": f.get("inspector", ""),
        "generales": {
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
    return render_template("semaforo_listo.html", nombre_archivo=os.path.basename(ruta_pdf), color_hex=color_hex, etiqueta=etiqueta)


@app.route("/descargar/<nombre_archivo>")
def descargar(nombre_archivo):
    ruta = os.path.join(CARPETA, nombre_archivo)
    return send_file(ruta, as_attachment=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
