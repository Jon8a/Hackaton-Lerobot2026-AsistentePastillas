# 💊 PastiBot · Dispensador robótico de medicación para residencias

> Proyecto para el **Hackathon LeRobot Bilbao 2026** ([hackathonbilbao.eus](https://hackathonbilbao.eus/home-page-es))
> Brazo **SO-101** + **LeRobot** + políticas **ACT** entrenadas por imitación.

## El problema

En una residencia, el personal de enfermería prepara a mano cada día cientos de pastillas
para muchas personas, cada una con su pauta distinta. Es un trabajo repetitivo y cansado,
y los errores importan: una dosis olvidada o una **dosis doble de Sintrom** (anticoagulante)
puede ser grave.

## La solución

PastiBot es un brazo robótico que prepara el vaso de medicación de cada residente:

1. La enfermera abre la app y elige al residente. La toma (desayuno, comida o cena) se
   selecciona sola según la hora.
2. El robot coge del cuenco correspondiente cada pastilla que le toca y la deja en el vaso.
3. La app lo anuncia en voz alta y lo registra.

Además, la app:
- **Bloquea las dosis dobles.** Repetir una toma exige confirmación, con un aviso específico
  para el Sintrom.
- **Avisa de tomas olvidadas** ("Josu no ha tomado el desayuno").
- **Lleva el stock de cada cuenco** y avisa cuando hay que rellenar.
- **Guarda un historial** de quién tomó qué y a qué hora.
- **Tiene parada de emergencia** con la barra espaciadora.

### Residentes de la demo

| Residente | Desayuno | Comida | Cena |
|---|---|---|---|
| Maite | Metformina + Lisinopril | – | Metformina + Sintrom |
| Josu | Lisinopril | Metformina | Sintrom |
| Carmen | 2 × Metformina | Metformina | Metformina |
| Andoni | Lisinopril | – | Sintrom + Metformina |

## Cómo funciona por dentro

```
Navegador (localhost:8000) ──► server.py (FastAPI) ──► lerobot-rollout + modelo ACT del cuenco
        ▲                            │
        └──── estado cada 0,7 s ─────┘
```

En vez de un único modelo que tenga que decidir qué pastilla coger, entrenamos **un
modelo ACT por cuenco**. La app decide qué toca y lanza, una tras otra, las políticas
necesarias. Así cada modelo solo aprende un movimiento y la elección de medicamento la
hace software determinista, que no se equivoca.

| Cuenco | Pastilla | Medicamento | Dataset | Modelo ACT |
|---|---|---|---|---|
| 🔵 Azul | blanca | Lisinopril 10 mg | [ikercioBT/azul_total_prueba](https://huggingface.co/datasets/ikercioBT/azul_total_prueba) | [ikercioBT/act_azul](https://huggingface.co/ikercioBT/act_azul) |
| 🟢 Verde | roja | Metformina 850 mg | _pendiente_ | [ikercioBT/act_verde](https://huggingface.co/ikercioBT/act_verde) |
| 🟡 Amarillo | naranja | Sintrom 4 mg | _pendiente_ | [ikercioBT/act_amarillo](https://huggingface.co/ikercioBT/act_amarillo) |

Todo está en la cuenta de Hugging Face del equipo: **[huggingface.co/ikercioBT](https://huggingface.co/ikercioBT)**.

**Entrenamiento:** ACT, 50k steps, batch 8, en Hugging Face Jobs (`t4-small`).
**Datos:** ~60–100 episodios por cuenco grabados por teleoperación, con dos cámaras
(`Cabeza` en la pinza y `arriba` cenital, 640×480 a 30 fps).

## Puesta en marcha

```bash
conda activate lerobot
pip install -r requirements.txt
python server.py --sim      # sin robot, para probar la interfaz
python server.py            # con el robot
```

Abrir **http://localhost:8000**.

La configuración del robot, las cámaras y los modelos está en `backend/config.py`.
Cada pastilla ejecuta:

```bash
lerobot-rollout --strategy.type=base --policy.path=ikercioBT/act_azul \
  --robot.type=so101_follower --robot.port=/dev/ttyACM0 --robot.id=robot \
  --robot.calibration_dir=~/.cache/huggingface/lerobot/calibration/robots/so_follower \
  --robot.cameras="{ Cabeza: {...}, arriba: {...} }" --duration=20
```

### Atajos de teclado

`1`–`4` elegir residente · `Enter` servir · `Espacio` **parar robot** · `Esc` cerrar.
Antes de una demo: Ajustes → *Reiniciar el día*.

## Estructura del código

```
server.py              API REST (FastAPI) + sirve la interfaz
backend/
  config.py            robot, cámaras, modelos, pastillas y tomas
  seed.py              residentes de la demo
  storage.py           datos (data/state.json), estado del día, stock, historial
  robot.py             cola del robot: un lerobot-rollout por pastilla
frontend/
  index.html, css/styles.css
  js/app.js            cabecera, pestañas, atajos, sondeo del robot
  js/api.js            llamadas a la API
  js/store.js          estado de la interfaz
  js/views/            panel, servir, historial, ajustes
```

### API

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/health` | robot listo / simulación / ocupado |
| GET | `/api/state` | residentes, estado de cada toma, stock, historial |
| POST | `/api/serve` | servir una toma (`409` si ya se dio, salvo `force`) |
| GET | `/api/jobs/{id}` | progreso pastilla a pastilla |
| POST | `/api/stop` | parada de emergencia |
| PUT | `/api/pills/{key}` | stock de un cuenco |
| PUT | `/api/residents/{id}` | pauta de un residente |
| POST | `/api/reset` | reiniciar el día / datos de demo |

## Siguientes pasos

- Cargar los 3 modelos una sola vez en un proceso persistente, para no tardar en arrancar cada pastilla.
- Un vaso por residente y reconocimiento del residente (tarjeta NFC o cara).
- Detección por visión de que la pastilla ha caído en el vaso.

## Equipo

Humildes · Hackathon LeRobot Bilbao, noviembre 2026.
- Jon Ochoa Cerezo
- Iker Martinez de Lizarduy
- Rodrigo Villaluenga Cadiñanos
