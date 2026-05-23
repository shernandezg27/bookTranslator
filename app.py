"""
Traductor EPUB — servidor Flask
"""

from flask import Flask, request, jsonify, send_file
from pathlib import Path
import threading
import uuid

app = Flask(__name__, static_folder="static", static_url_path="")

# ── Almacén de trabajos en memoria ─────────────────────────────────────────────
# { job_id: { status, progreso, mensaje, archivo_salida, error } }
jobs: dict[str, dict] = {}


# ── API key ────────────────────────────────────────────────────────────────────

@app.route("/api-key", methods=["GET"])
def get_api_key():
    key_file = Path(__file__).parent / "API_KEY.txt"
    if key_file.exists():
        key = key_file.read_text(encoding="utf-8").strip()
        if key and key not in ("TU_API_KEY_AQUI", "MI_API_KEY", ""):
            return jsonify({"configurada": True, "preview": key[:8] + "..."})
    return jsonify({"configurada": False})


@app.route("/api-key", methods=["POST"])
def set_api_key():
    data = request.get_json()
    if not data or not data.get("key", "").strip():
        return jsonify({"error": "Key vacía"}), 400
    key_file = Path(__file__).parent / "API_KEY.txt"
    key_file.write_text(data["key"].strip(), encoding="utf-8")
    return jsonify({"ok": True})


# ── Traducción ─────────────────────────────────────────────────────────────────

@app.route("/traducir", methods=["POST"])
def traducir():
    if "epub" not in request.files:
        return jsonify({"error": "Falta el archivo epub"}), 400

    archivo = request.files["epub"]
    if not archivo.filename.lower().endswith(".epub"):
        return jsonify({"error": "El archivo debe ser .epub"}), 400

    # API key: campo del formulario o API_KEY.txt (traducir.py lo gestiona)
    api_key = request.form.get("api_key", "").strip() or None

    # Guardar el epub subido
    job_id = uuid.uuid4().hex[:8]
    uploads_dir = Path(__file__).parent / "uploads"
    uploads_dir.mkdir(exist_ok=True)
    epub_path = uploads_dir / archivo.filename  # mismo nombre → checkpoint persiste entre subidas
    archivo.save(epub_path)

    jobs[job_id] = {
        "status": "en_curso",
        "progreso": 0,
        "mensaje": "Iniciando...",
        "archivo_salida": None,
        "error": None,
        "nombre_original": archivo.filename,
    }

    thread = threading.Thread(
        target=_run_translation,
        args=(job_id, epub_path, api_key),
        daemon=True
    )
    thread.start()

    return jsonify({"job_id": job_id})


def _run_translation(job_id: str, epub_path: Path, api_key: str | None):
    import traducir

    def cb(porcentaje: int, mensaje: str):
        jobs[job_id]["progreso"] = porcentaje
        jobs[job_id]["mensaje"] = mensaje

    try:
        output = traducir.translate_epub(str(epub_path), api_key=api_key, progress_cb=cb)
        jobs[job_id].update({
            "status": "completado",
            "progreso": 100,
            "mensaje": "¡Traducción completada!",
            "archivo_salida": str(output),
        })
    except traducir.APIKeyError:
        jobs[job_id].update({
            "status": "error",
            "error": "API key no configurada. Añádela en la sección de configuración.",
        })
    except (traducir.LimiteDiarioError, traducir.CuotaAgotadaError) as e:
        jobs[job_id].update({
            "status": "pausado",
            "mensaje": str(e),
            "error": str(e),
        })
    except Exception as e:
        jobs[job_id].update({
            "status": "error",
            "error": str(e),
        })


# ── Estado y descarga ──────────────────────────────────────────────────────────

@app.route("/estado/<job_id>")
def estado(job_id):
    if job_id not in jobs:
        return jsonify({"error": "Trabajo no encontrado"}), 404
    return jsonify(jobs[job_id])


@app.route("/descargar/<job_id>")
def descargar(job_id):
    if job_id not in jobs:
        return jsonify({"error": "Trabajo no encontrado"}), 404

    job = jobs[job_id]
    if job["status"] != "completado" or not job["archivo_salida"]:
        return jsonify({"error": "El archivo todavía no está listo"}), 400

    output_path = Path(job["archivo_salida"])
    return send_file(str(output_path), as_attachment=True, download_name=output_path.name)


# ── Frontend ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return app.send_static_file("index.html")


# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n  Traductor EPUB iniciado → http://localhost:5000\n")
    app.run(host="127.0.0.1", port=5000, debug=False)
