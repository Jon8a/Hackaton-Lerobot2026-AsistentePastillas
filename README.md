# PastiBot · pastillero robótico para residencias

Interfaz + servidor para que el brazo de LeRobot sirva la medicación de cada residente
según la toma del día (desayuno, comida, cena). Un modelo ACT por cuenco:

| Cuenco | Pastilla | Medicamento |
|---|---|---|
| Verde | roja | Metformina |
| Amarillo | naranja | Sintrom |
| Azul | blanca | Lisinopril |

## Arrancar

```bash
pip install -r requirements.txt     # en el mismo entorno donde está lerobot
python server.py --sim              # sin robot, para desarrollar y ensayar
python server.py                    # con el robot de verdad
```

Abrir **http://localhost:8000**.

## Antes de usar el robot real

Editar solo `backend/config.py`:
- `HF_USER`, `ROBOT` (puerto e id de calibración) y `CAMERAS` (mismos nombres que en la grabación).
- `policy` de cada pastilla → el repo del modelo ACT de ese cuenco.
- `DURATION_S` → lo que tarda una pastilla + un poco de margen.

Probad primero un modelo a mano con `lerobot-rollout ... --policy.path=...`. Si funciona ahí,
funciona aquí: el servidor lanza exactamente ese comando (se ve en "Ver salida del robot").

## Estructura

```
server.py              API (FastAPI) + sirve la interfaz
backend/
  config.py            robot, cámaras, modelos, pastillas, tomas  ← lo que se toca
  seed.py              los 4 residentes de demo
  storage.py           datos en data/state.json, estado del día, stock, historial
  robot.py             cola del robot: una ejecución de lerobot-rollout por pastilla
frontend/
  index.html
  css/styles.css
  js/app.js            cabecera, pestañas, atajos, sondeo
  js/api.js            llamadas al servidor
  js/store.js          estado de la interfaz
  js/ui.js, voice.js   utilidades y voz
  js/views/            panel, servir (ventana), historial, ajustes
data/state.json        se crea solo
```

## API

| Método | Ruta | Para qué |
|---|---|---|
| GET | `/api/health` | robot listo / simulación / ocupado |
| GET | `/api/state` | residentes, estado de cada toma, stock, historial |
| POST | `/api/serve` `{resident_id, moment, force}` | servir una toma (409 si ya se dio, salvo `force`) |
| GET | `/api/jobs/{id}` | progreso pastilla a pastilla |
| POST | `/api/stop` | parada |
| PUT | `/api/pills/{key}` `{stock}` | stock de un cuenco |
| PUT | `/api/residents/{id}` `{schedule}` | pauta de un residente |
| POST | `/api/reset` `{scope: "day"\|"all"}` | reiniciar el día / datos de demo |

## Atajos (para la demo)

`1`–`4` residente · `Enter` servir · `Espacio` **parar robot** · `Esc` cerrar.
Arriba se puede elegir la toma a mano (si presentáis a mediodía y queréis enseñar la cena).
Antes de presentar: Ajustes → **Reiniciar el día**.
