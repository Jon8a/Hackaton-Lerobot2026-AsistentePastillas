"""
Configuración del pastillero. Es el ÚNICO archivo que hay que tocar para adaptarlo
a vuestro robot y a vuestros modelos.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "state.json"
FRONTEND_DIR = ROOT / "frontend"

# ------------------------------------------------------------------ robot
import os

WINDOWS = os.name == "nt"

# Cómo se mueve el robot:
#   "worker" -> un proceso carga brazo, cámaras y los 3 modelos UNA vez y corta al acabar el ciclo (rápido)
#   "cli"    -> un lerobot-rollout nuevo por pastilla (lento, pero es el plan B si el worker falla)
MODE = "worker"

HF_USER = "Rodrivilla04"

# MODE = "cli": lerobot-rollout con el MISMO Python que ejecuta server.py (el de LeLab),
# así no hace falta que "lerobot-rollout" esté en el PATH (en Windows no lo está).
ROLLOUT_CMD = [sys.executable, "-m", "lerobot.scripts.lerobot_rollout"]
LEROBOT_ROLLOUT = "lerobot-rollout"      # solo se usa para avisos

ROBOT = {
    "type": "so101_follower",                          # so100_follower o so101_follower (NO so_follower)
    "port": "COM6" if WINDOWS else "/dev/ttyACM0",     # COM6 = follower en el portátil Windows (probado)
    "id": "robot",                                     # el id con el que calibrasteis
    "calibration_dir": str(Path("~/.cache/huggingface/lerobot/calibration/robots/so_follower").expanduser()),
}

# Mismos nombres que en los datasets grabados con LeLab en Windows: "cabeza" (pinza) y "arriba",
# los dos en MINÚSCULA. En el portátil Windows: cabeza = 1, arriba = 2 (probado con lerobot-rollout).
# En Windows sin fourcc (así funcionó); en Linux MJPG para evitar cortes.
CAMERAS = {
    "cabeza": {"index_or_path": 1 if WINDOWS else "/dev/video4", "width": 640, "height": 480, "fps": 30,
               "fourcc": None if WINDOWS else "MJPG"},
    "arriba": {"index_or_path": 2 if WINDOWS else "/dev/video2", "width": 640, "height": 480, "fps": 30,
               "fourcc": None if WINDOWS else "MJPG"},
}

FPS = 30

# ACT calcula 100 acciones (3,3 s) de golpe. Con 50 recalcula cada ~1,7 s y corrige con lo que
# ve la cámara de la pinza al acercarse (es lo que funcionó en las pruebas). Menos = corrige más
# pero va más a tirones en CPU (cada cálculo ~0,5 s).
N_ACTION_STEPS = 50

# --- fin de ciclo (solo MODE = "worker") ---------------------------------
# Damos la pastilla por servida cuando el brazo se ha alejado de reposo, ha movido
# la pinza (ha cogido y soltado) y ha vuelto a reposo y se ha quedado quieto un momento.
# La postura de reposo se toma al arrancar (el brazo tiene que estar en reposo) y se
# puede volver a guardar desde Ajustes.
CYCLE = {
    "leave_deg": 15,        # ha empezado: alguna articulación a más de 15° de reposo
    "rest_deg": 10,         # ha vuelto: las articulaciones de return_joints a menos de 10° de reposo...
    "return_joints": ["shoulder_pan", "shoulder_lift", "elbow_flex"],   # la muñeca no vuelve exacta
    "still_deg": 0.6,       # ...o ya ha cogido/soltado y está quieto (<0,6° por frame) a menos de 25°
    "hold_s": 0.6,          # ...durante 0,6 s seguidos
    "min_s": 3,             # nunca damos por acabado antes de 3 s
    "max_s": 30,            # si en 30 s no ha acabado: error y vuelta a reposo
    "require_grip": True,   # exigir que la pinza se haya movido (si no, no ha cogido nada)
    "grip_range": 10,       # cuánto tiene que moverse la pinza (0-100) para contar
}

# MODE = "cli": segundos fijos por pastilla (ACT no sabe cuándo acaba)
DURATION_S = 20

# Segundos que tarda cada pastilla en modo simulación (--sim)
SIM_STEP_S = 3


def cameras_cli_string() -> str:
    parts = []
    for name, c in CAMERAS.items():
        fourcc = f", fourcc: {c['fourcc']}" if c.get("fourcc") else ""
        parts.append(f"{name}: {{type: opencv, index_or_path: {c['index_or_path']}, width: {c['width']}, "
                     f"height: {c['height']}, fps: {c['fps']}{fourcc}}}")
    return "{ " + ", ".join(parts) + " }"


# ---------------------------------------------------------------- modelos
# Los modelos buenos son los checkpoints descargados en C:\Users\<usuario>\ckpt_<color>:
#   hf download Rodrivilla04/act_<color>_final --include "checkpoints/010000/pretrained_model/*" --local-dir ckpt_<color>
# Se coge solo el checkpoint MÁS ALTO que haya descargado. Si no hay ninguno, se usa el repo del Hub.
# Para forzar uno concreto, poned la ruta a mano en "policy" de PILLS.
CKPT_ROOT = Path.home()


def model_path(color: str) -> str:
    ckpts = sorted((CKPT_ROOT / f"ckpt_{color}" / "checkpoints").glob("*/pretrained_model/config.json"))
    if ckpts:
        return str(ckpts[-1].parent)
    return f"{HF_USER}/act_{color}_final"


# ---------------------------------------------------------------- pastillas
# La clave (metformina, sintrom...) se usa en las pautas y en la API.
# policy: el modelo ACT entrenado para ESE cuenco (carpeta local o repo de Hugging Face).
# Si preferís lanzar vuestro propio script: "cmd": ["python", "mi_script.py"]
PILLS = {
    "metformina": {
        "name": "Metformina",
        "dose": "850 mg",
        "bowl": "verde",
        "bowl_color": "#22a05a",
        "pill_color": "#e23b3b",
        "pill_desc": "roja",
        "task": "Coge una pastilla roja del cuenco verde y déjala en el vaso",
        "policy": model_path("verde"),
    },
    "sintrom": {
        "name": "Sintrom",
        "dose": "4 mg",
        "bowl": "amarillo",
        "bowl_color": "#f2c230",
        "pill_color": "#f57c1f",
        "pill_desc": "naranja",
        "task": "Coge una pastilla naranja del cuenco amarillo y déjala en el vaso",
        "policy": model_path("amarillo"),
        "warning": "Anticoagulante: una dosis doble es peligrosa.",
    },
    "lisinopril": {
        "name": "Lisinopril",
        "dose": "10 mg",
        "bowl": "azul",
        "bowl_color": "#2f6fdb",
        "pill_color": "#ffffff",
        "pill_desc": "blanca",
        "task": "Coge una pastilla blanca del cuenco azul y déjala en el vaso",
        "policy": model_path("azul"),
    },
}

BOWL_CAPACITY = 20      # pastillas que caben en un cuenco (para la barra de stock)
LOW_STOCK = 4           # a partir de aquí avisa

# ------------------------------------------------------------------ tomas
# start/end en horas. La última puede dar la vuelta a medianoche.
MOMENTS = [
    {"id": "desayuno", "label": "Desayuno", "icon": "☀️", "start": 6,  "end": 11, "phrase": "del desayuno"},
    {"id": "comida",   "label": "Comida",   "icon": "🍽️", "start": 11, "end": 16, "phrase": "de la comida"},
    {"id": "cena",     "label": "Cena",     "icon": "🌙", "start": 16, "end": 6,  "phrase": "de la cena"},
]
MOMENT_IDS = [m["id"] for m in MOMENTS]
