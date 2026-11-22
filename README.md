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
Navegador ──► server.py (FastAPI) ──► robot_worker.py ──► brazo SO-101 + 2 cámaras
                                       (3 modelos ACT cargados en memoria)
```

En vez de un único modelo que tenga que decidir qué pastilla coger, entrenamos **un
modelo ACT por cuenco**. La app decide qué toca y el robot ejecuta, una tras otra, las
políticas necesarias. Así cada modelo solo aprende un movimiento y la elección de
medicamento la hace software determinista, que no se equivoca.

**Arranque instantáneo.** `robot_worker.py` conecta el brazo y las cámaras y carga los
3 modelos **una sola vez** al arrancar. Servir una pastilla solo cuesta lo que dura el movimiento.

**Detección del fin de ciclo.** ACT no sabe cuándo ha terminado: si se le deja, vuelve a
empezar. Nuestro bucle de control vigila las articulaciones en cada paso y corta en cuanto:

1. el brazo se ha alejado de la postura de reposo,
2. la pinza se ha movido (ha cogido y soltado),
3. ha vuelto a reposo y se ha quedado quieto 0,6 s.

Si la pinza no se ha movido se marca como fallo ("no ha cogido nada"), y si pasan 30 s
se para y vuelve a reposo. Todo se ajusta en `CYCLE` dentro de `backend/config.py`.

## Modelos y datos (Hugging Face)

Modelos: **[huggingface.co/Rodrivilla04](https://huggingface.co/Rodrivilla04)** ·
Datasets: **[huggingface.co/Jon8a](https://huggingface.co/Jon8a)**

| Cuenco | Pastilla | Medicamento | Dataset (episodios usados) | Modelo ACT | Checkpoint usado |
|---|---|---|---|---|---|
| 🔵 Azul | blanca | Lisinopril 10 mg | [Jon8a/azul_real_20261121_201034](https://huggingface.co/datasets/Jon8a/azul_real_20261121_201034) (59: episodios 50–109) | [Rodrivilla04/act_azul_final](https://huggingface.co/Rodrivilla04/act_azul_final) | [`checkpoints/010000`](https://huggingface.co/Rodrivilla04/act_azul_final/tree/main/checkpoints/010000) |
| 🟡 Amarillo | naranja | Sintrom 4 mg | [Jon8a/Amarillo_real_20261122_002410](https://huggingface.co/datasets/Jon8a/Amarillo_real_20261122_002410) (100) | [Rodrivilla04/act_amarillo_final](https://huggingface.co/Rodrivilla04/act_amarillo_final) | [`checkpoints/010000`](https://huggingface.co/Rodrivilla04/act_amarillo_final/tree/main/checkpoints/010000) |
| 🟢 Verde | roja | Metformina 850 mg | [Jon8a/verde_real_20261121_234733](https://huggingface.co/datasets/Jon8a/verde_real_20261121_234733) (99) | [Rodrivilla04/act_verde_final](https://huggingface.co/Rodrivilla04/act_verde_final) | [`checkpoints/010000`](https://huggingface.co/Rodrivilla04/act_verde_final/tree/main/checkpoints/010000) |

**Datos.** Grabados por teleoperación (brazo leader → follower) con LeLab, a 30 fps, con dos
cámaras de 640×480: `cabeza` (en la pinza) y `arriba` (cenital). Cada bandeja tiene **3 marcas
fijas** y siempre se coge primero la pastilla más cercana (unos 75 episodios con la secuencia
3 → 2 → 1 pastillas y 25 con una sola). Movimiento continuo, sin pausas, desde la misma postura
de reposo. Los episodios vacíos se quitan antes de entrenar.

**Entrenamiento.** ACT (`resnet18`, `chunk_size` 100), batch 32, aumento de datos de imagen
activado y mixed precision, en [Hugging Face Jobs](https://huggingface.co/docs/huggingface_hub/guides/jobs)
(`a100-large`). Usamos el checkpoint de 10.000 steps.

**Inferencia.** En CPU en el portátil, recalculando cada 50 acciones (`N_ACTION_STEPS`) para
que el modelo corrija con la cámara de la pinza al acercarse a la pastilla.

### Lecciones aprendidas

- **Quitar variación del entorno** fue lo que más ayudó: marcas fijas para las pastillas y
  cámaras y bandejas que no se mueven.
- **Sin pausas en las demostraciones:** ACT no tiene memoria y, si en las grabaciones el brazo
  se para a "mirar", en la prueba se queda atascado en ese punto.
- **Grabar y probar en el mismo ordenador:** calibración, nombres de cámara (`cabeza` ≠ `Cabeza`)
  y driver de cámara tienen que coincidir.
- **Velocidad constante** en todas las grabaciones.

### Enlaces

- [LeRobot](https://github.com/huggingface/lerobot) · [documentación](https://huggingface.co/docs/lerobot)
- [Brazo SO-101 (SO-ARM100)](https://github.com/TheRobotStudio/SO-ARM100)
- [ACT: Action Chunking with Transformers (ALOHA)](https://tonyzhaozh.github.io/aloha/)
- [Hackathon LeRobot Bilbao](https://hackathonbilbao.eus/home-page-es)

## Puesta en marcha

### Portátil Windows (LeLab)

Se ejecuta con el Python de LeLab, que ya tiene LeRobot. **Cerrad LeLab antes**: usa las
cámaras y también el puerto 8000.

```powershell
$py = "$(uv tool dir)\lelab\Scripts\python.exe"
uv pip install --python $py fastapi uvicorn        # solo la primera vez

# Modelos: descargar el checkpoint de cada cuenco en C:\Users\<usuario>\ckpt_<color>
$hf = "$(uv tool dir)\lelab\Scripts\hf.exe"
cd $HOME
foreach ($c in "azul", "amarillo", "verde") {
  & $hf download "Rodrivilla04/act_$($c)_final" --include "checkpoints/010000/pretrained_model/*" --local-dir "ckpt_$c"
}

cd Hackaton-Lerobot2026-AsistentePastillas
& $py server.py --sim          # sin robot: solo la interfaz
& $py server.py --mock-robot   # worker con brazo simulado (prueba la detección de ciclo)
& $py server.py                # con el robot (el brazo en reposo al arrancar)
```

Al arrancar, la consola muestra qué modelo usa cada pastilla. Se coge solo el checkpoint más
alto descargado en `ckpt_<color>`; si no hay ninguno, el repo `Rodrivilla04/act_<color>_final`.

### Linux

```bash
conda activate lerobot
pip install -r requirements.txt
python server.py
```

### Probar un modelo sin la app

```powershell
& $py -m lerobot.scripts.lerobot_rollout `
  --robot.type=so101_follower --robot.port=COM6 --robot.id=robot `
  --robot.calibration_dir="$HOME\.cache\huggingface\lerobot\calibration\robots\so_follower" `
  --robot.cameras='{ cabeza: {type: opencv, index_or_path: 1, width: 640, height: 480, fps: 30}, arriba: {type: opencv, index_or_path: 2, width: 640, height: 480, fps: 30} }' `
  --policy.path="$HOME\ckpt_azul\checkpoints\010000\pretrained_model" `
  --policy.n_action_steps=50 --policy.device=cpu
```

Abrir **http://localhost:8000**. Al arrancar, el estado pone *Cargando robot…* hasta
que el brazo, las cámaras y los 3 modelos están listos.

Puerto (`COM6`), cámaras (`cabeza` = 1, `arriba` = 2), modelos, `N_ACTION_STEPS` (cada cuántas
acciones recalcula ACT; 50 = ~1,7 s) y detección de ciclo: `backend/config.py`. Si el worker diera
problemas, `MODE = "cli"` vuelve al sistema anterior (un `lerobot-rollout` por pastilla).

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
  robot.py             cola de pastillas (worker, CLI o simulación)
  robot_worker.py      proceso del robot: modelos cargados una vez + detección de ciclo
  worker_client.py     arranca el worker y habla con él (JSON por stdin/stdout)
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
| POST | `/api/robot/home` | llevar el brazo a reposo |
| POST | `/api/robot/rest` | guardar la postura actual como reposo |
| POST | `/api/robot/restart` | reiniciar el worker |
| GET | `/api/robot/log` | salida del worker |

## Siguientes pasos

- Un vaso por residente y reconocimiento del residente (tarjeta NFC o cara).
- Detección por visión de que la pastilla ha caído en el vaso.

## Equipo

_Nombres del equipo_ · Hackathon LeRobot Bilbao, noviembre 2026.
