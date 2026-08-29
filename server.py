import sys
import os
import json

# Add the libs directory to sys.path so Python can find the modules there
sys.path.append(os.path.join(os.path.dirname(__file__), 'Python313', 'dependencies'))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import subprocess
import threading
import pygetwindow as gw
import time
import re
import urllib.request
import urllib.parse
import urllib.error
from typing import List, Dict, Optional


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins; you can specify particular domains here instead of "*"
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)

gameRunning = False
game_lock = threading.Lock()

# ── Config .conf ──────────────────────────────────────────────
CONF_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.conf")
PLATFORMS = ["NES", "SNES", "GBA", "PS1", "PS2", "PS3", "WIIU", "SWITCH"]
DEFAULT_CONFIG = {"engines": {p: "" for p in PLATFORMS}, "romFolders": {p: "" for p in PLATFORMS}}

# Comando por plataforma — normaliza rutas a formato Windows nativo
def _norm(p: str) -> str:
    return os.path.normpath(p) if p else p

def build_launch_command(platform: str, engine: str, rom: str) -> str:
    engine = _norm(engine)
    rom = _norm(rom)
    p = (platform or "").upper()
    # /wait es clave: sin él, `start` vuelve al instante y gameRunning se libera
    if p == "WIIU":
        return f'start /wait "" "{engine}" -f -g "{rom}"'
    if p == "SWITCH":
        return f'start /wait "" "{engine}" "{rom}"'
    if p in ("PS2", "PS1", "GBA", "NES", "SNES"):
        return f'start /wait "" "{engine}" "{rom}" -fullscreen'
    if p == "PS3":
        # RPCS3: no acepta -fullscreen; abre en fullscreen si así quedó configurado
        return f'start /wait "" "{engine}" --no-gui "{rom}"'
    return f'start /wait "" "{engine}" "{rom}"'

def ensure_config():
    if not os.path.exists(CONF_PATH):
        with open(CONF_PATH, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)
        print(f"[config] creado {CONF_PATH}")

def _migrate_engines(raw):
    if isinstance(raw, dict):
        return {p: (raw.get(p) or "") for p in PLATFORMS}
    return {p: "" for p in PLATFORMS}

def _migrate_roms(raw):
    if isinstance(raw, dict):
        return {p: (raw.get(p) or "") for p in PLATFORMS}
    # legacy: lista -> ignorar
    return {p: "" for p in PLATFORMS}

def load_config():
    ensure_config()
    try:
        with open(CONF_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            data["engines"] = _migrate_engines(data.get("engines"))
            data["romFolders"] = _migrate_roms(data.get("romFolders"))
            return data
    except (json.JSONDecodeError, FileNotFoundError):
        with open(CONF_PATH, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)
        return {"engines": {p: "" for p in PLATFORMS}, "romFolders": {p: "" for p in PLATFORMS}}

def save_config(data: dict):
    data["engines"] = _migrate_engines(data.get("engines"))
    data["romFolders"] = _migrate_roms(data.get("romFolders"))
    with open(CONF_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# crear al importar el módulo (al iniciarse el server)
ensure_config()

class ConfigModel(BaseModel):
    engines: Dict[str, str] = {p: "" for p in PLATFORMS}
    romFolders: Dict[str, str] = {p: "" for p in PLATFORMS}

# ── Libretro Thumbnails ───────────────────────────────────────
LIBRETRO_PLAYLIST = {
    "NES": "Nintendo - Nintendo Entertainment System",
    "SNES": "Nintendo - Super Nintendo Entertainment System",
    "GBA": "Nintendo - Game Boy Advance",
    "PS1": "Sony - PlayStation",
    "PS2": "Sony - PlayStation 2",
    "PS3": "Sony - PlayStation 3",
    "WIIU": "Nintendo - Wii U",
    "SWITCH": "Nintendo - Nintendo Switch",
}
LIBRETRO_BASE = "https://thumbnails.libretro.com"
# Libretro no mantiene una colección completa para PS3.  Cover Century sirve
# como respaldo para esos títulos que no aparecen en Named_Boxarts.
COVERCENTURY_BASE = "https://www.covercentury.com/covers"
# Algunas entradas de Cover Century son escaneos completos (frontal + trasera).
# Para estos casos preferimos una imagen frontal ya catalogada.
KNOWN_FRONT_COVERS = {
    ("PS3", "batman arkham city"): "https://images.launchbox-app.com/92d960f9-0f81-4ebe-b809-2f5a6cc9b9e3.png",
}

SERIAL_TITLES = {
    "SLUS-20946": "Grand Theft Auto - San Andreas",
    "SLUS-20062": "Grand Theft Auto - Vice City",
    "SLUS-20552": "Grand Theft Auto III",
    "SLUS-21423": "God of War II",
    "SLUS-21008": "God of War",
    "SLUS-20312": "Final Fantasy X",
    "SLUS-20672": "Kingdom Hearts",
    "SLUS-21059": "Shadow of the Colossus",
    "SLUS-21242": "Okami",
    "SLUS-20184": "Gran Turismo 3 - A-Spec",
    "SLUS-20712": "Dragon Ball Z - Budokai Tenkaichi 3",
    "SLUS-20943": "Soulcalibur III",
}
SERIAL_RE = re.compile(r'^[A-Z]{4}-\d{4,5}$', re.IGNORECASE)

def _clean_rom_name(name: str) -> str:
    """Quita tags (USA) [En] y extensión para buscar carátula."""
    name = os.path.splitext(name)[0]
    name = re.sub(r'\(.*?\)', '', name)
    name = re.sub(r'\[.*?\]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def _resolve_title(platform: str, rom_file: str) -> str:
    """Si el ROM es un serial (SLUS-20946), devuelve el título real."""
    clean = _clean_rom_name(rom_file)
    key = clean.upper()
    if SERIAL_RE.match(key) and key in SERIAL_TITLES:
        return SERIAL_TITLES[key]
    # intentar buscar en redump si es serial desconocido (cache en memoria)
    if SERIAL_RE.match(key):
        # fallback: intentar redump quicksearch (sin bloquear mucho)
        try:
            url = f"https://redump.org/discs/quicksearch/{urllib.parse.quote(key)}"
            req = urllib.request.Request(url, headers={"User-Agent": "GamerStation/1.0"})
            with urllib.request.urlopen(req, timeout=4) as resp:
                html = resp.read().decode('utf-8', errors='ignore')
                m = re.search(r'<a[^>]+>([^<]*' + re.escape(key) + r'[^<]*)</a>', html, re.IGNORECASE)
                if m:
                    # título suele estar antes del serial
                    title = re.sub(r'\s*\(.*?\)', '', m.group(1)).strip()
                    # limpiar serial del título
                    title = re.sub(re.escape(key), '', title, flags=re.IGNORECASE).strip(' -:')
                    if title:
                        return title
        except Exception:
            pass
    return clean

def _libretro_candidates(platform: str, rom_file: str) -> List[str]:
    """URLs candidatas para la carátula."""
    playlist = LIBRETRO_PLAYLIST.get(platform.upper(), "")
    if not playlist:
        return []
    title = _resolve_title(platform, rom_file)
    clean = _clean_rom_name(rom_file)
    # base names a probar
    base_names = []
    for n in (title, clean):
        if n and n not in base_names:
            base_names.append(n)
    raw_no_ext = os.path.splitext(rom_file)[0]
    if raw_no_ext not in base_names:
        base_names.append(raw_no_ext)
    # expandir con sufijos de región comunes en libretro
    suffixes = ["", " (USA)", " (USA) (En,Ja)", " (Europe)", " (Japan)", " (World)"]

    def _dash_variants(n: str) -> List[str]:
        """Variantes de guiones: libretro usa 'Xrd -Sign -' mientras los ROMs
        suelen tener 'Xrd - Sign'. Genera combinaciones pegadas y envueltas."""
        variants = [n]
        # pegar guiones sueltos: "A - Sign" -> "A -Sign"
        v = re.sub(r'\s+-\s+', ' -', n)
        if v not in variants: variants.append(v)
        # envolver: "A - Sign" -> "A -Sign-"
        v2 = re.sub(r'\s+-\s+([^-\s].*?)$', r' -\1-', n)
        if v2 not in variants: variants.append(v2)
        # todo pegado: "A-Sign"
        v3 = re.sub(r'\s+-\s+', '-', n)
        if v3 not in variants: variants.append(v3)
        # libretro usa ":" donde los ROMs usan "-": "A - B" -> "A: B"
        v4 = re.sub(r'\s+-\s+', ': ', n)
        if v4 not in variants: variants.append(v4)
        return variants

    names = []
    for base in base_names:
        for dv in _dash_variants(base):
            for suf in suffixes:
                v = dv + suf
                if v not in names:
                    names.append(v)
        # fallback: recortar subtítulos "Título - Subtítulo" -> "Título"
        # (libretro a veces no tiene la edición/subtítulo, ej. "Call of Duty 3 - Special Edition")
        short = re.split(r'\s+-\s+', base)[0].strip()
        if short and short != base:
            for suf in suffixes:
                v = short + suf
                if v not in names:
                    names.append(v)
    urls = []
    for n in names:
        enc = urllib.parse.quote(n + ".png")
        urls.append(f"{LIBRETRO_BASE}/{urllib.parse.quote(playlist)}/Named_Boxarts/{enc}")
    return urls

# ── Fallback: listado real de Named_Boxarts (con caché en disco) ──
_boxart_cache: Dict[str, Optional[List[str]]] = {}

def _normalize_for_match(n: str) -> str:
    """Normaliza un título para comparación difusa."""
    n = n.lower()
    n = re.sub(r'\(.*?\)', '', n)
    n = re.sub(r'\[.*?\]', '', n)
    n = re.sub(r'[^a-z0-9]+', ' ', n)
    return re.sub(r'\s+', ' ', n).strip()

def _get_boxart_listing(platform: str) -> Optional[List[str]]:
    """Descarga (una vez por plataforma) el listado de archivos en Named_Boxarts."""
    if platform in _boxart_cache:
        return _boxart_cache[platform]
    playlist = LIBRETRO_PLAYLIST.get(platform.upper(), "")
    if not playlist:
        _boxart_cache[platform] = None
        return None
    # caché en disco para no re-descargar en cada arranque
    cache_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), f".boxarts_{platform}.cache")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                listing = json.load(f)
            _boxart_cache[platform] = listing
            return listing
        except Exception:
            pass
    url = f"{LIBRETRO_BASE}/{urllib.parse.quote(playlist)}/Named_Boxarts/"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GamerStation/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
        # extraer nombres de archivos .png del listado HTML
        listing = re.findall(r'href="([^"]+\.png)"', html, re.IGNORECASE)
        listing = [urllib.parse.unquote(x) for x in listing]
        _boxart_cache[platform] = listing or None
        if listing:
            try:
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(listing, f)
            except Exception:
                pass
        return _boxart_cache[platform]
    except Exception as e:
        print(f"[cover] no se pudo listar boxarts de {platform}: {e}")
        _boxart_cache[platform] = None
        return None

def _fuzzy_boxart_match(platform: str, rom_file: str) -> Optional[str]:
    """Busca el PNG cuyo nombre coincida mejor con el título del ROM."""
    listing = _get_boxart_listing(platform)
    if not listing:
        return None
    target = _normalize_for_match(os.path.splitext(rom_file)[0])
    if not target:
        return None
    target_words = set(target.split())
    best, best_score = None, 0.0
    for fname in listing:
        cand = _normalize_for_match(os.path.splitext(fname)[0])
        if not cand:
            continue
        cand_words = set(cand.split())
        if not cand_words:
            continue
        # Jaccard sobre palabras + bonus por prefijo común
        inter = len(target_words & cand_words)
        union = len(target_words | cand_words)
        score = inter / union if union else 0.0
        if score > best_score:
            best, best_score = fname, score
    if best and best_score >= 0.6:
        return best
    return None

def _covercentury_candidates(platform: str, rom_file: str) -> List[str]:
    """Genera URLs de Cover Century para títulos PS3."""
    if platform.upper() != "PS3":
        return []

    names = []
    for name in (_resolve_title(platform, rom_file), _clean_rom_name(rom_file)):
        if name and name not in names:
            names.append(name)

    urls = []
    known = KNOWN_FRONT_COVERS.get((platform.upper(), _normalize_for_match(names[0]))) if names else None
    if known:
        urls.append(known)

    for name in names:
        # Cover Century usa guiones en lugar de espacios y agrupa por la
        # primera letra del nombre del archivo.
        slug = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-")
        if not slug:
            continue
        url = f"{COVERCENTURY_BASE}/ps3/{slug[0].lower()}/{slug}.jpg"
        if url not in urls:
            urls.append(url)
    return urls

def fetch_cover(platform: str, rom_file: str, dest_dir: str = "./src/img") -> Optional[str]:
    """Descarga carátula si no existe. Retorna path relativo o None."""
    os.makedirs(dest_dir, exist_ok=True)
    title = _resolve_title(platform, rom_file)
    clean = _clean_rom_name(rom_file)
    # si es serial, el archivo destino debe ser el título, no el serial
    dest_name = title if SERIAL_RE.match(clean.upper()) else clean
    for ext in (".png", ".jpg", ".jpeg"):
        if os.path.exists(os.path.join(dest_dir, dest_name + ext)):
            return dest_name + ext
        if os.path.exists(os.path.join(dest_dir, title + ext)):
            return title + ext
        if os.path.exists(os.path.join(dest_dir, rom_file)):
            return rom_file
    # intentar descargar
    for url in _libretro_candidates(platform, rom_file):
        try:
            dest = os.path.join(dest_dir, dest_name + ".png")
            req = urllib.request.Request(url, headers={"User-Agent": "GamerStation/1.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                if resp.status == 200:
                    data = resp.read()
                    if len(data) < 500:
                        continue
                    with open(dest, "wb") as f:
                        f.write(data)
                    print(f"[cover] {platform}/{rom_file} -> {dest_name}.png ({url})")
                    return dest_name + ".png"
        except urllib.error.HTTPError as e:
            if e.code != 404:
                print(f"[cover] HTTP {e.code} {url}")
            continue
        except Exception as e:
            print(f"[cover] error {url}: {e}")
            continue
    # fallback: matching difuso contra el listado real de Named_Boxarts
    match = _fuzzy_boxart_match(platform, rom_file)
    if match:
        url = f"{LIBRETRO_BASE}/{urllib.parse.quote(LIBRETRO_PLAYLIST[platform.upper()])}/Named_Boxarts/{urllib.parse.quote(match)}"
        try:
            dest = os.path.join(dest_dir, dest_name + ".png")
            req = urllib.request.Request(url, headers={"User-Agent": "GamerStation/1.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                if resp.status == 200:
                    data = resp.read()
                    if len(data) >= 500:
                        with open(dest, "wb") as f:
                            f.write(data)
                        print(f"[cover] {platform}/{rom_file} -> {dest_name}.png (fuzzy: {match})")
                        return dest_name + ".png"
        except Exception as e:
            print(f"[cover] error fuzzy {url}: {e}")
    # Cover Century tiene más carátulas de PS3 que el listado de Libretro.
    for url in _covercentury_candidates(platform, rom_file):
        try:
            dest_ext = ".png" if url.lower().endswith(".png") else ".jpg"
            dest = os.path.join(dest_dir, dest_name + dest_ext)
            req = urllib.request.Request(url, headers={"User-Agent": "GamerStation/1.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                if resp.status == 200:
                    data = resp.read()
                    if len(data) < 500:
                        continue
                    with open(dest, "wb") as f:
                        f.write(data)
                    source_name = "LaunchBox" if "launchbox-app.com" in url else "Cover Century"
                    print(f"[cover] {platform}/{rom_file} -> {dest_name}{dest_ext} ({source_name}: {url})")
                    return dest_name + dest_ext
        except urllib.error.HTTPError as e:
            if e.code != 404:
                print(f"[cover] HTTP {e.code} {url}")
            continue
        except Exception as e:
            print(f"[cover] error Cover Century {url}: {e}")
    print(f"[cover] no encontrada para {platform}/{rom_file} (clean={clean}, title={title})")
    return None


@app.post("/get-images/")
async def get_images():
    folder_path = "./src/img/"
    if not os.path.isdir(folder_path):
        return []
    try:
        return os.listdir(folder_path)
    except Exception:
        return []

@app.post("/fetch-cover/")
async def fetch_cover_endpoint(data: dict):
    """Descarga carátula para un ROM. Body: {platform, file}"""
    platform = (data.get("platform") or "").strip()
    file = (data.get("file") or "").strip()
    if not platform or not file:
        return {"error": "platform y file requeridos"}
    result = fetch_cover(platform, file)
    return {"cover": result, "platform": platform, "file": file}

@app.post("/fetch-covers/")
async def fetch_covers_bulk():
    """Descarga carátulas para todos los ROMs sin imagen. Retorna resumen."""
    games = await get_games()
    # imágenes existentes (nombres sin extensión, lower)
    img_dir = "./src/img/"
    existing = set()
    if os.path.isdir(img_dir):
        for f in os.listdir(img_dir):
            existing.add(os.path.splitext(f)[0].lower())
    fetched = []
    missing = []
    for g in games:
        clean = _clean_rom_name(g["file"]).lower()
        raw = os.path.splitext(g["file"])[0].lower()
        if clean in existing or raw in existing or g["name"].lower() in existing:
            continue
        cover = fetch_cover(g["platform"], g["file"])
        if cover:
            fetched.append({"platform": g["platform"], "file": g["file"], "cover": cover})
            existing.add(clean)
        else:
            missing.append({"platform": g["platform"], "file": g["file"]})
    return {"fetched": fetched, "missing": missing, "total": len(games)}

def _fetch_missing_covers_bg(games: list):
    """Hilo en background: descarga carátulas faltantes sin bloquear get_games."""
    try:
        img_dir = "./src/img"
        existing = set()
        if os.path.isdir(img_dir):
            for f in os.listdir(img_dir):
                existing.add(os.path.splitext(f)[0].lower())
        for g in games:
            clean = _clean_rom_name(g["file"]).lower()
            raw = os.path.splitext(g["file"])[0].lower()
            if clean in existing or raw in existing or g["name"].lower() in existing:
                continue
            cover = fetch_cover(g["platform"], g["file"])
            if cover:
                existing.add(clean)
    except Exception as e:
        print(f"[cover bg] error: {e}")

@app.post("/get-games/")
async def get_games():
    """Devuelve ROMs solo de las plataformas que tienen engine + carpeta configurados."""
    cfg = load_config()
    engines = cfg.get("engines", {})
    romFolders = cfg.get("romFolders", {})
    all_games = []
    for plat in PLATFORMS:
        engine = (engines.get(plat) or "").strip()
        folder = (romFolders.get(plat) or "").strip()
        if not engine or not folder:
            continue
        if not os.path.isdir(folder):
            print(f"[get-games] {plat}: carpeta no existe: {folder}")
            continue
        try:
            files = os.listdir(folder)
            # PS1: los juegos pueden ser .cue+.bin (2 archivos) o .iso/.img/.chd (1 archivo).
            # Ocultar el .bin cuando existe un .cue con el mismo nombre (el .cue es el que se lanza),
            # y ocultar archivos auxiliares (.sbi, .m3u de sub-archivos ya listados).
            lower_files = {f.lower() for f in files}
            aux_exts = (".sbi", ".m3u")
            for fname in files:
                fpath = os.path.normpath(os.path.join(folder, fname))
                if os.path.isfile(fpath):
                    base_lower = os.path.splitext(fname)[0].lower()
                    ext = os.path.splitext(fname)[1].lower()
                    if plat == "PS1":
                        if ext == ".bin" and (base_lower + ".cue") in lower_files:
                            continue  # el .cue ya representa este juego
                        if ext in aux_exts:
                            continue  # archivos auxiliares de PS1
                    # ignorar archivos de sistema
                    if fname.lower().endswith((".ini", ".db", ".txt")) and fname.lower() in ("desktop.ini", "thumbs.db"):
                        continue
                    all_games.append({
                        "platform": plat,
                        "file": fname,
                        "path": fpath,
                        "name": os.path.splitext(fname)[0]
                    })
        except Exception as e:
            print(f"[get-games] error {plat}: {e}")
    # lanzar descarga de carátulas faltantes en background (no bloquea)
    if all_games:
        threading.Thread(target=_fetch_missing_covers_bg, args=(list(all_games),), daemon=True).start()
    # fallback legacy ./games/ si no hay nada configurado
    if not all_games:
        legacy = "./games/"
        if os.path.isdir(legacy):
            try:
                for fname in os.listdir(legacy):
                    fpath = os.path.join(legacy, fname)
                    if os.path.isfile(fpath):
                        all_games.append({"platform": "UNKNOWN", "file": fname, "path": fpath, "name": os.path.splitext(fname)[0]})
            except Exception:
                pass
    return all_games

class OpenFileInput(BaseModel):
    file_name: Optional[str] = None
    file_path: Optional[str] = None
    platform: Optional[str] = None

@app.post("/open-file/")
async def open_file(input: OpenFileInput):
        global gameRunning
        # Nuevo flujo: engine + rom con comando por plataforma
        if input.file_path and input.platform:
            # Bloqueo atómico: si ya hay juego corriendo, rechazar
            with game_lock:
                if gameRunning:
                    msg = "Ya hay un juego en ejecución"
                    print(f"[open-file] {msg}")
                    return {"error": msg, "alreadyRunning": True}
                cfg = load_config()
                plat = (input.platform or "").upper()
                engine = (cfg.get("engines", {}).get(plat) or "").strip()
                if not engine or not os.path.exists(engine):
                    msg = f"Engine no configurado para {plat}: {engine}"
                    print(f"[open-file] {msg}")
                    return {"error": msg}
                if not os.path.exists(input.file_path):
                    msg = f"ROM no existe: {input.file_path}"
                    print(f"[open-file] {msg}")
                    return {"error": msg}
                command = build_launch_command(plat, engine, input.file_path)
                print(f"[open-file] {plat}: {command}")
                try:
                    # Marcar como corriendo ANTES de lanzar el thread para evitar race
                    gameRunning = True
                    threading.Thread(target=start_program, args=(command,), daemon=True).start()
                    return {"ok": True, "command": command}
                except Exception as e:
                    gameRunning = False
                    print(f"Error opening file: {e}")
                    return {"error": str(e)}

        # Fallback legacy: games/{file_name}
        with game_lock:
            if gameRunning:
                return {"error": "Ya hay un juego en ejecución", "alreadyRunning": True}
            file_path = input.file_path or (f"games/{input.file_name}" if input.file_name else "")
            if not file_path:
                return {"error": "file_name o file_path requerido"}
            command = f'start /wait "{file_path}"'
            if os.path.exists(file_path):
                try:
                    gameRunning = True
                    threading.Thread(target=start_program, args=(command,), daemon=True).start()
                    return {"ok": True}
                except subprocess.CalledProcessError as e:
                    gameRunning = False
                    print(f"Error opening file: {e}")
                    return {"error": str(e)}
            else:
                print("File does not exist!")
                return {"error": "File does not exist"}

@app.post("/check-game/")
async def check_game():
    print(gameRunning)
    return gameRunning

# ── Config endpoints ──────────────────────────────────────────
@app.get("/config")
async def get_config():
    return load_config()

@app.post("/config")
async def set_config(cfg: ConfigModel):
    data = {"engines": cfg.engines, "romFolders": cfg.romFolders}
    save_config(data)
    return data

@app.post("/browse-file")
async def browse_file():
    """Abre diálogo nativo para elegir un ejecutable (engine) — solo .exe."""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askopenfilename(
            title="Seleccionar engine (.exe)",
            filetypes=[("Ejecutable", "*.exe"), ("Todos los archivos", "*.*")]
        )
        root.destroy()
        return {"path": path or ""}
    except Exception as e:
        return {"path": "", "error": str(e)}

@app.post("/browse-folder")
async def browse_folder():
    """Abre diálogo nativo para elegir carpeta de ROMs."""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askdirectory(title="Seleccionar carpeta de ROMs")
        root.destroy()
        return {"path": path or ""}
    except Exception as e:
        return {"path": "", "error": str(e)}

def start_program(command):
    global gameRunning
    print("Starting program...")
    # gameRunning ya está en True (seteado en open_file bajo lock)
    try:
        process = subprocess.Popen(command, shell=True)
        process.wait()
    finally:
        with game_lock:
            gameRunning = False
        print("Program ended!")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8400, log_level="info")
