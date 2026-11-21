"""Datos de demo: 4 residentes con pautas distintas. Se cargan la primera vez
(o al pulsar "Restaurar datos de demo" en Ajustes)."""
from . import config

RESIDENTS = [
    {
        "id": "maite", "name": "Maite Etxeberria", "room": "101", "age": 84, "color": "#c2410c",
        "schedule": {
            "desayuno": {"metformina": 1, "lisinopril": 1},
            "comida": {},
            "cena": {"metformina": 1, "sintrom": 1},
        },
    },
    {
        "id": "josu", "name": "Josu Agirre", "room": "102", "age": 79, "color": "#0f766e",
        "schedule": {
            "desayuno": {"lisinopril": 1},
            "comida": {"metformina": 1},
            "cena": {"sintrom": 1},
        },
    },
    {
        "id": "carmen", "name": "Carmen López", "room": "103", "age": 88, "color": "#7c3aed",
        "schedule": {
            "desayuno": {"metformina": 2},
            "comida": {"metformina": 1},
            "cena": {"metformina": 1},
        },
    },
    {
        "id": "andoni", "name": "Andoni Ruiz", "room": "104", "age": 81, "color": "#be185d",
        "schedule": {
            "desayuno": {"lisinopril": 1},
            "comida": {},
            "cena": {"sintrom": 1, "metformina": 1},
        },
    },
]


def initial_state() -> dict:
    import copy
    return {
        "residents": copy.deepcopy(RESIDENTS),
        "stock": {k: config.BOWL_CAPACITY for k in config.PILLS},
        "log": [],
    }
