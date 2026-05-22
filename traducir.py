#!/usr/bin/env python3
"""
EPUB Translator — inglés → español (castellano) con Google Gemini
Uso CLI: python traducir.py <archivo.epub>
Uso web: importar y llamar a translate_epub(path, api_key=..., progress_cb=...)
"""

import sys
import os
import re
import json
import zipfile
import shutil
import time
from datetime import date
from pathlib import Path
from xml.etree import ElementTree as ET
from bs4 import BeautifulSoup
from google import genai
from google.genai import types
from tqdm import tqdm

# ── Excepciones ────────────────────────────────────────────────────────────────

class TraductorError(Exception): pass
class APIKeyError(TraductorError): pass
class LimiteDiarioError(TraductorError): pass
class CuotaAgotadaError(TraductorError): pass

# ── Configuración ──────────────────────────────────────────────────────────────

GEMINI_MODEL    = "gemini-3.1-flash-lite"
MAX_CHUNK_CHARS = 8000
REQUEST_DELAY   = 5
MAX_RETRIES     = 10
DAILY_REQ_LIMIT = 500
DAILY_WARN_AT   = DAILY_REQ_LIMIT * 0.9
TEMPERATURE     = 0.2
TOP_P           = 0.95
PREV_CTX_CHARS  = 800

# ──────────────────────────────────────────────────────────────────────────────

BLOCK_TAGS = [
    "p", "h1", "h2", "h3", "h4", "h5", "h6",
    "li", "td", "th", "blockquote", "figcaption",
    "cite", "dt", "dd", "title"
]
SKIP_TAGS = {"script", "style", "code", "pre", "kbd", "var", "samp"}


def load_api_key_from_file() -> str | None:
    key_file = Path(__file__).parent / "API_KEY.txt"
    if key_file.exists():
        key = key_file.read_text(encoding="utf-8").strip()
        if key and key not in ("TU_API_KEY_AQUI", "MI_API_KEY", ""):
            return key
    return None


def setup_gemini(api_key: str | None = None):
    key = api_key or load_api_key_from_file() or os.environ.get("GEMINI_API_KEY", "")
    if not key or key in ("MI_API_KEY", "TU_API_KEY_AQUI"):
        raise APIKeyError(
            "No hay API key configurada.\n"
            "Edita API_KEY.txt con tu clave de Google AI Studio."
        )
    return genai.Client(api_key=key)


# ── Contador diario ────────────────────────────────────────────────────────────

COUNTER_FILE = Path(__file__).parent / ".daily_requests.json"

def load_daily_counter() -> int:
    if not COUNTER_FILE.exists():
        return 0
    try:
        data = json.loads(COUNTER_FILE.read_text(encoding="utf-8"))
        if data.get("date") == str(date.today()):
            return data.get("count", 0)
    except Exception:
        pass
    return 0

def save_daily_counter(count: int):
    COUNTER_FILE.write_text(
        json.dumps({"date": str(date.today()), "count": count}),
        encoding="utf-8"
    )

def check_daily_limit(count: int):
    if count >= DAILY_REQ_LIMIT:
        raise LimiteDiarioError(
            f"Límite diario alcanzado ({DAILY_REQ_LIMIT} peticiones). "
            "El progreso está guardado. Vuelve a ejecutar mañana para continuar."
        )
    if count >= DAILY_WARN_AT:
        remaining = DAILY_REQ_LIMIT - count
        print(f"\n  ⚠ Quedan solo {remaining} peticiones para el límite diario.")

# ──────────────────────────────────────────────────────────────────────────────


def strip_markdown_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()


def parse_retry_delay(error: Exception) -> float | None:
    match = re.search(r'retry[^\d]*(\d+(?:\.\d+)?)s', str(error), re.IGNORECASE)
    return float(match.group(1)) + 2 if match else None


def is_daily_quota_exhausted(error: Exception) -> bool:
    return "PerDay" in str(error) or "per_day" in str(error).lower()


def build_prompt(html: str, prev_context: str = "") -> str:
    context_block = ""
    if prev_context.strip():
        context_block = (
            "FRAGMENTO ANTERIOR YA TRADUCIDO (úsalo solo como referencia de tono, "
            "estilo y vocabulario para mantener la coherencia; no lo repitas ni lo traduzcas):\n"
            f"{prev_context.strip()}\n\n"
            "---\n\n"
        )
    return (
        "Eres un traductor literario experto. Traduce el siguiente fragmento HTML "
        "del inglés al español de España (castellano).\n\n"

        "SOBRE EL IDIOMA:\n"
        "- Usa español de España (castellano). Nunca uses expresiones, léxico ni "
        "construcciones propias del español latinoamericano.\n"
        "- Usa el tuteo salvo que el contexto exija tratamiento de usted.\n\n"

        "SOBRE LA FIDELIDAD:\n"
        "- Traduce de forma fiel y literal siempre que el resultado sea natural en "
        "castellano. No parafrasees ni amplíes el significado.\n"
        "- Conserva la estructura de las frases originales en la medida de lo posible.\n"
        "- No omitas ni añadas contenido que no esté en el original.\n"
        "- Mantén el mismo registro (formal, coloquial, técnico, etc.) que el original.\n\n"

        "SOBRE EL TONO Y EL ESTILO:\n"
        "- Preserva el tono, los matices y la voz narrativa del original con precisión.\n"
        "- Mantén el ritmo y la cadencia de las frases en la medida de lo posible.\n"
        "- Si el original es ambiguo, traduce preservando esa ambigüedad; no la resuelvas.\n"
        "- El resultado debe sonar natural en castellano pero sin alejarse del original.\n\n"

        "SOBRE LOS NOMBRES Y TÉRMINOS:\n"
        "- Conserva en su forma original todos los nombres propios de personas, "
        "lugares, organizaciones y marcas.\n"
        "- Conserva en su forma original los títulos de obras (libros, películas, etc.).\n"
        "- Conserva las palabras en otros idiomas que aparezcan en el original.\n\n"

        "SOBRE EL HTML:\n"
        "- Mantén TODOS los tags HTML y sus atributos exactamente igual, sin modificarlos.\n"
        "- Traduce ÚNICAMENTE el texto visible entre los tags.\n"
        "- No añadas explicaciones, comentarios ni formato markdown.\n"
        "- Devuelve ÚNICAMENTE el HTML con el texto traducido, nada más.\n\n"

        f"{context_block}"
        f"FRAGMENTO A TRADUCIR:\n{html}"
    )


def translate_html_block(model, html: str, daily_count: list, prev_context: str = "") -> str:
    check_daily_limit(daily_count[0])
    prompt = build_prompt(html, prev_context)
    config = types.GenerateContentConfig(
        temperature=TEMPERATURE,
        top_p=TOP_P,
    )

    for attempt in range(MAX_RETRIES):
        try:
            response = model.models.generate_content(
                model=GEMINI_MODEL, contents=prompt, config=config
            )
            daily_count[0] += 1
            save_daily_counter(daily_count[0])
            return strip_markdown_fences(response.text)
        except (LimiteDiarioError, CuotaAgotadaError):
            raise
        except Exception as e:
            if is_daily_quota_exhausted(e):
                raise CuotaAgotadaError(
                    "Cuota diaria de la API agotada. "
                    "El progreso está guardado. Vuelve a ejecutar mañana."
                )
            wait = parse_retry_delay(e) or (attempt + 1) * 10
            print(f"\n    ⚠ Error (intento {attempt + 1}/{MAX_RETRIES}): esperando {wait:.0f}s...")
            time.sleep(wait)

    print("    ✗ Bloque no traducido tras varios intentos, se mantiene el original.")
    return html


def has_translatable_text(element) -> bool:
    if element.name in SKIP_TAGS:
        return False
    for parent in element.parents:
        if hasattr(parent, 'name') and parent.name in SKIP_TAGS:
            return False
    return bool(element.get_text(strip=True))


def translate_xhtml_file(model, content: str, daily_count: list) -> str:
    is_xml = content.lstrip().startswith("<?xml") or 'xmlns' in content[:300]
    parser = "xml" if is_xml else "html.parser"

    try:
        soup = BeautifulSoup(content, parser)
    except Exception:
        soup = BeautifulSoup(content, "html.parser")

    blocks = [b for b in soup.find_all(BLOCK_TAGS) if has_translatable_text(b)]
    if not blocks:
        return content

    chunks: list[list] = []
    current: list = []
    current_len: int = 0

    for block in blocks:
        block_str = str(block)
        if current and current_len + len(block_str) > MAX_CHUNK_CHARS:
            chunks.append(current)
            current = [block]
            current_len = len(block_str)
        else:
            current.append(block)
            current_len += len(block_str)
    if current:
        chunks.append(current)

    prev_context = ""

    with tqdm(chunks, desc="    chunks", unit="chunk", leave=False,
              bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]") as pbar:
        for chunk in pbar:
            pbar.set_postfix_str(f"peticiones hoy: {daily_count[0]}/{DAILY_REQ_LIMIT}")
            combined_html = "\n".join(str(b) for b in chunk)
            translated_html = translate_html_block(model, combined_html, daily_count, prev_context)

            try:
                t_soup = BeautifulSoup(translated_html, "html.parser")
                t_blocks = t_soup.find_all(BLOCK_TAGS)

                if len(t_blocks) == len(chunk):
                    for original, translated in zip(chunk, t_blocks):
                        original.replace_with(translated)
                else:
                    matched = min(len(t_blocks), len(chunk))
                    for j in range(matched):
                        chunk[j].replace_with(t_blocks[j])
                    pbar.write(f"    ⚠ desajuste: {matched}/{len(chunk)} bloques reemplazados")

                prev_context = t_soup.get_text(separator=" ", strip=True)[-PREV_CTX_CHARS:]

            except Exception as e:
                pbar.write(f"    ✗ error al aplicar traducción: {e}")

            time.sleep(REQUEST_DELAY)

    return str(soup)


def find_content_files(epub_dir: Path) -> list[Path]:
    opf_path = None

    container = epub_dir / "META-INF" / "container.xml"
    if container.exists():
        try:
            tree = ET.parse(container)
            root = tree.getroot()
            for elem in root.iter():
                if elem.tag.endswith("rootfile"):
                    full_path = elem.get("full-path")
                    if full_path:
                        opf_path = epub_dir / full_path
                        break
        except ET.ParseError:
            pass

    if not opf_path or not opf_path.exists():
        opf_files = list(epub_dir.rglob("*.opf"))
        opf_path = opf_files[0] if opf_files else None

    if not opf_path:
        return sorted(list(epub_dir.rglob("*.xhtml")) + list(epub_dir.rglob("*.html")))

    opf_dir = opf_path.parent
    content_files = []

    try:
        tree = ET.parse(opf_path)
        root = tree.getroot()
        for elem in root.iter():
            if elem.tag.endswith("item"):
                media_type = elem.get("media-type", "")
                href = elem.get("href", "")
                if media_type in ("application/xhtml+xml", "text/html") and href:
                    fpath = (opf_dir / href).resolve()
                    if fpath.exists():
                        content_files.append(fpath)
    except ET.ParseError as e:
        print(f"⚠ Error parseando OPF: {e}. Usando búsqueda genérica.")
        content_files = sorted(list(epub_dir.rglob("*.xhtml")) + list(epub_dir.rglob("*.html")))

    return content_files


def repack_epub(source_dir: Path, output_path: Path):
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zout:
        mimetype = source_dir / "mimetype"
        if mimetype.exists():
            zout.write(mimetype, "mimetype", compress_type=zipfile.ZIP_STORED)
        for file in sorted(source_dir.rglob("*")):
            if file.is_file() and file.name != "mimetype":
                zout.write(file, file.relative_to(source_dir))


# ── Sistema de checkpoint ──────────────────────────────────────────────────────

def checkpoint_path(input_path: Path) -> Path:
    return input_path.parent / f".{input_path.stem}.progress"

def load_progress(input_path: Path) -> set[str]:
    cp = checkpoint_path(input_path)
    if not cp.exists():
        return set()
    return set(cp.read_text(encoding="utf-8").splitlines())

def save_progress(input_path: Path, done_files: set[str]):
    cp = checkpoint_path(input_path)
    cp.write_text("\n".join(sorted(done_files)), encoding="utf-8")

def clear_progress(input_path: Path):
    cp = checkpoint_path(input_path)
    if cp.exists():
        cp.unlink()

# ──────────────────────────────────────────────────────────────────────────────


def translate_epub(
    input_path_str: str,
    api_key: str | None = None,
    progress_cb=None   # callable(porcentaje: int, mensaje: str) | None
) -> Path:
    """
    Traduce un EPUB y devuelve la ruta del archivo traducido.
    Lanza TraductorError (o subclases) en caso de error.
    """
    def _progress(pct: int, msg: str):
        if progress_cb:
            progress_cb(pct, msg)

    input_path = Path(input_path_str).resolve()

    if not input_path.exists():
        raise TraductorError(f"No se encuentra el archivo: {input_path}")
    if input_path.suffix.lower() != ".epub":
        raise TraductorError("El archivo debe tener extensión .epub")

    stem        = input_path.stem
    parent      = input_path.parent
    output_path = parent / f"{stem}_es.epub"
    tmp_eng     = parent / f"_tmp_{stem}_eng"
    tmp_es      = parent / f"_tmp_{stem}_es"

    model       = setup_gemini(api_key)   # lanza APIKeyError si falla
    daily_count = [load_daily_counter()]

    _progress(0, f"Peticiones usadas hoy: {daily_count[0]}/{DAILY_REQ_LIMIT}")
    check_daily_limit(daily_count[0])

    done_files = load_progress(input_path)
    resuming   = bool(done_files)

    if resuming:
        if not tmp_es.exists():
            if tmp_eng.exists():
                _progress(1, "Carpeta de trabajo perdida, recreando desde copia en inglés...")
                shutil.copytree(tmp_eng, tmp_es)
            else:
                _progress(1, "Extrayendo EPUB de nuevo...")
                with zipfile.ZipFile(input_path, "r") as z:
                    z.extractall(tmp_eng)
                shutil.copytree(tmp_eng, tmp_es)
        _progress(2, f"Reanudando ({len(done_files)} archivos ya completados)")
    else:
        for d in (tmp_eng, tmp_es):
            if d.exists():
                shutil.rmtree(d)
        _progress(1, "Extrayendo EPUB...")
        with zipfile.ZipFile(input_path, "r") as z:
            z.extractall(tmp_eng)
        _progress(2, "Creando copia de trabajo...")
        shutil.copytree(tmp_eng, tmp_es)

    content_files = find_content_files(tmp_es)
    total = len(content_files)
    _progress(3, f"{total} archivos de contenido encontrados")

    start_time = time.time()
    file_bar = tqdm(
        content_files, unit="archivo",
        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} archivos  [{elapsed}<{remaining}]"
    )

    for i, filepath in enumerate(file_bar):
        file_key = filepath.name
        file_bar.set_postfix_str(filepath.name[:40])

        pct = 3 + int((i / total) * 95)
        _progress(pct, f"Traduciendo {filepath.name} ({i+1}/{total})")

        if file_key in done_files:
            file_bar.write(f"  ⏭  {filepath.name} (ya traducido)")
            continue

        try:
            content    = filepath.read_text(encoding="utf-8", errors="replace")
            translated = translate_xhtml_file(model, content, daily_count)
            filepath.write_text(translated, encoding="utf-8")

            done_files.add(file_key)
            save_progress(input_path, done_files)

        except KeyboardInterrupt:
            file_bar.write("\n⏸  Interrupción manual. Progreso guardado.")
            raise
        except (LimiteDiarioError, CuotaAgotadaError):
            raise
        except Exception as e:
            file_bar.write(f"  ✗ Error en {filepath.name}: {e}")

    _progress(98, "Empaquetando EPUB traducido...")
    repack_epub(tmp_es, output_path)
    clear_progress(input_path)

    elapsed = time.time() - start_time
    mins, secs = divmod(int(elapsed), 60)
    print(f"✅  Completado en {mins}m {secs}s → {output_path.name}")

    _progress(100, "¡Traducción completada!")
    return output_path


# ── Entrada CLI ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python traducir.py <archivo.epub>")
        sys.exit(1)

    try:
        result = translate_epub(sys.argv[1])
        print(f"💾  Guardado en: {result}")
    except APIKeyError as e:
        print(f"\n⛔ {e}")
        sys.exit(1)
    except LimiteDiarioError as e:
        print(f"\n⛔ {e}")
        sys.exit(0)
    except CuotaAgotadaError as e:
        print(f"\n⛔ {e}")
        sys.exit(0)
    except TraductorError as e:
        print(f"\n⛔ {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n⏸  Progreso guardado. Vuelve a ejecutar para continuar.")
        sys.exit(0)
