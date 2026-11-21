"""
Configuración del pastillero. Es el ÚNICO archivo que hay que tocar para adaptarlo
a vuestro robot y a vuestros modelos.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "state.json"
FRONTEND_DIR = ROOT / "frontend"

# ------------------------------------------------------------------ robot
HF_USER = "ikercioBT"

# En esta versión de LeRobot la inferencia va con lerobot-rollout (lerobot-record no acepta --policy.path)
LEROBOT_ROLLOUT = "lerobot-rollout"

ROBOT = {
    "type": "so101_follower",   # so100_follower o so101_follower (NO so_follower)
    "port": "/dev/ttyACM0",     # follower (el leader está en /dev/ttyACM1)
    "id": "robot",
    "calibration_dir": str(Path("~/.cache/huggingface/lerobot/calibration/robots/so_follower").expanduser()),
}

# Mismos nombres que en el dataset: "Cabeza" (pinza, con mayúscula) y "arriba".
# ⚠ POR CONFIRMAR qué /dev/videoX es cada una (hay video0, video2 y video4)
CAMERAS = (
    "{ Cabeza: {type: opencv, index_or_path: /dev/video2, width: 640, height: 480, fps: 30, fourcc: MJPG}, "
    "arriba: {type: opencv, index_or_path: /dev/video4, width: 640, height: 480, fps: 30, fourcc: MJPG} }"
)

# Segundos que dejamos a la política para cada pastilla (ACT no sabe cuándo ha acabado)
DURATION_S = 20

# Segundos que tarda cada pastilla en modo simulación (--sim)
SIM_STEP_S = 3

# ---------------------------------------------------------------- pastillas
# La clave (metformina, sintrom...) se usa en las pautas y en la API.
# policy: el modelo ACT entrenado para ESE cuenco.
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
        "policy": f"{HF_USER}/act_verde",       # ⚠ nombre provisional
    },
    "sintrom": {
        "name": "Sintrom",
        "dose": "4 mg",
        "bowl": "amarillo",
        "bowl_color": "#f2c230",
        "pill_color": "#f57c1f",
        "pill_desc": "naranja",
        "task": "Coge una pastilla naranja del cuenco amarillo y déjala en el vaso",
        "policy": f"{HF_USER}/act_amarillo",    # ⚠ nombre provisional
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
        "policy": f"{HF_USER}/act_azul",        # ya entrenado
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
