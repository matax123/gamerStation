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
PLATFORMS = ["NES", "SNES", "GBA", "PS1", "PS2", "WIIU", "SWITCH"]
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


@app.post("/get-images/")
async def get_images():
    folder_path = "./src/img/"
    if not os.path.isdir(folder_path):
        return []
    try:
        return os.listdir(folder_path)
    except Exception:
        return []

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
            for fname in os.listdir(folder):
                fpath = os.path.normpath(os.path.join(folder, fname))
                if os.path.isfile(fpath):
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