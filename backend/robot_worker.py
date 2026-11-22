"""
Proceso del robot. Lo arranca server.py y se queda vivo:

  1. Conecta el brazo y las cámaras UNA vez.
  2. Carga los modelos ACT de los 3 cuencos UNA vez.
  3. Por cada pastilla ejecuta su modelo en nuestro propio bucle de control y CORTA en
     cuanto detecta que el ciclo ha terminado (ha salido de reposo, ha movido la pinza
     y ha vuelto a reposo), en vez de esperar un tiempo fijo.

Habla con server.py por líneas JSON:
  entrada  {"cmd": "pick", "id": "...", "pill": "lisinopril"}   servir una pastilla
           {"cmd": "stop"}                                       parar ya
           {"cmd": "home"}                                       volver a reposo
           {"cmd": "set_rest"}                                   guardar la postura actual como reposo
           {"cmd": "quit"}
  salida   {"event": "status" | "ready" | "progress" | "done" | "info" | "fatal", ...}

Para probarlo sin robot:  python backend/robot_worker.py --mock
"""
import argparse
import json
import os
import queue
import sys
import threading
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend import config  # noqa: E402

ARM_JOINTS = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll"]
GRIPPER = "gripper"
ALL_JOINTS = ARM_JOINTS + [GRIPPER]

# stdout es SOLO para el protocolo; todo lo que impriman LeRobot/PyTorch va a stderr
_proto = os.fdopen(os.dup(1), "w", buffering=1, encoding="utf-8")
os.dup2(2, 1)
sys.stdout = sys.stderr
_proto_lock = threading.Lock()


def emit(**msg):
    with _proto_lock:
        _proto.write(json.dumps(msg, ensure_ascii=False) + "\n")
        _proto.flush()


def log(text):
    print(f"[worker] {text}", file=sys.stderr, flush=True)


# =========================================================== robot de verdad
class RealHardware:
    """Brazo + cámaras + modelos, con la API de Python de LeRobot."""

    def __init__(self):
        import torch

        # Las rutas de los módulos han cambiado entre versiones de LeRobot: probamos varias
        def _imp(paths, name):
            for mod in paths:
                try:
                    return getattr(__import__(mod, fromlist=[name]), name)
                except (ImportError, AttributeError):
                    continue
            raise ImportError(f"No encuentro {name} en {paths}")

        self.torch = torch
        # registrar los tipos de robot (so100/so101_follower); el nombre del módulo varía con la versión
        import importlib
        for mod in ("lerobot.robots.so_follower", "lerobot.robots.so101_follower", "lerobot.robots.so100_follower"):
            try:
                importlib.import_module(mod)
            except ImportError:
                pass
        RobotConfig =_imp(["lerobot.robots.config", "lerobot.robots"], "RobotConfig")
        make_robot_from_config = _imp(["lerobot.robots.utils", "lerobot.robots"], "make_robot_from_config")
        OpenCVCameraConfig = _imp(["lerobot.cameras.opencv.configuration_opencv", "lerobot.cameras.opencv"],
                                  "OpenCVCameraConfig")
        hw_to_dataset_features = _imp(["lerobot.utils.feature_utils", "lerobot.datasets.utils"],
                                      "hw_to_dataset_features")
        self.build_dataset_frame = _imp(["lerobot.utils.feature_utils", "lerobot.datasets.utils"],
                                        "build_dataset_frame")
        self.predict_action = _imp(["lerobot.common.control_utils", "lerobot.utils.control_utils"],
                                   "predict_action")
        self.make_robot_action = _imp(["lerobot.policies.utils"], "make_robot_action")
        PreTrainedConfig = _imp(["lerobot.configs.policies"], "PreTrainedConfig")
        get_policy_class = _imp(["lerobot.policies.factory"], "get_policy_class")
        make_pre_post_processors = _imp(["lerobot.policies.factory"], "make_pre_post_processors")

        # --- brazo y cámaras
        emit(event="status", msg="Conectando brazo y cámaras…")
        cams = {name: OpenCVCameraConfig(index_or_path=c["index_or_path"], width=c["width"],
                                         height=c["height"], fps=c["fps"], fourcc=c.get("fourcc"))
                for name, c in config.CAMERAS.items()}
        r = config.ROBOT
        robot_cfg = RobotConfig.get_choice_class(r["type"])(
            port=r["port"], id=r["id"], calibration_dir=Path(r["calibration_dir"]), cameras=cams)
        self.robot = make_robot_from_config(robot_cfg)
        self.robot.connect()
        self.ds_features = {
            **hw_to_dataset_features(self.robot.action_features, "action"),
            **hw_to_dataset_features(self.robot.observation_features, "observation", use_video=True),
        }

        # --- modelos
        self.policies = {}
        device = "cuda" if torch.cuda.is_available() else "cpu"
        for i, (key, p) in enumerate(config.PILLS.items(), 1):
            emit(event="status", msg=f"Cargando modelo {i}/{len(config.PILLS)}: {p['policy']}")
            pcfg = PreTrainedConfig.from_pretrained(p["policy"])
            pcfg.device = device
            n_steps = getattr(config, "N_ACTION_STEPS", None)
            if n_steps and hasattr(pcfg, "n_action_steps"):
                # recalcular cada n_steps para corregir con la cámara de la pinza al acercarse
                pcfg.n_action_steps = min(n_steps, getattr(pcfg, "chunk_size", n_steps))
            log(f"{key}: {p['policy']} (n_action_steps={getattr(pcfg, 'n_action_steps', '?')})")
            policy = get_policy_class(pcfg.type).from_pretrained(p["policy"], config=pcfg)
            policy.eval()
            pre, post = make_pre_post_processors(
                pcfg, pretrained_path=p["policy"],
                preprocessor_overrides={"device_processor": {"device": device}})
            self.policies[key] = (policy, pre, post, torch.device(device), p["task"])
        log(f"modelos cargados en {device}")

    def observe(self):
        return self.robot.get_observation()

    def reset_policy(self, key):
        policy, pre, post, *_ = self.policies[key]
        policy.reset()
        for proc in (pre, post):
            if hasattr(proc, "reset"):
                proc.reset()

    def act(self, key, obs):
        policy, pre, post, device, task = self.policies[key]
        frame = self.build_dataset_frame(self.ds_features, obs, prefix="observation")
        action = self.predict_action(frame, policy, device, pre, post, use_amp=False,
                                     task=task, robot_type=self.robot.robot_type)
        return self.make_robot_action(action, self.ds_features)

    def send(self, action):
        self.robot.send_action(action)

    def close(self):
        try:
            self.robot.disconnect()
        except Exception as e:  # noqa: BLE001
            log(f"error al desconectar: {e!r}")


# ===================================================== robot simulado (--mock)
class MockHardware:
    """Imita un brazo que hace el ciclo (salir, coger, soltar, volver) y luego,
    como ACT de verdad, EMPIEZA OTRO. Sirve para probar que cortamos a tiempo."""

    CYCLE_S = 6.0

    def __init__(self):
        emit(event="status", msg="[mock] Conectando brazo simulado…")
        time.sleep(0.5)
        for i, key in enumerate(config.PILLS, 1):
            emit(event="status", msg=f"[mock] Cargando modelo {i}/{len(config.PILLS)}")
            time.sleep(0.3)
        self.pose = {j: 0.0 for j in ARM_JOINTS}
        self.pose[GRIPPER] = 5.0
        self.t0 = None
        self.fail_grip = os.environ.get("MOCK_NO_GRIP") == "1"

    def observe(self):
        return {f"{j}.pos": v for j, v in self.pose.items()}

    def reset_policy(self, key):
        self.t0 = time.perf_counter()

    def act(self, key, obs):
        import math
        t = (time.perf_counter() - self.t0) % self.CYCLE_S      # se repite: como ACT
        phase = t / self.CYCLE_S
        reach = math.sin(math.pi * min(phase / 0.85, 1.0)) * 45   # sale y vuelve en el 85 % del ciclo
        grip = 5.0
        if not self.fail_grip and 0.25 < phase < 0.6:
            grip = 40.0                                          # abre/cierra la pinza
        return {f"{j}.pos": (reach if j in ("shoulder_lift", "elbow_flex") else reach / 3) for j in ARM_JOINTS} \
            | {f"{GRIPPER}.pos": grip}

    def send(self, action):
        for k, v in action.items():
            self.pose[k.removesuffix(".pos")] = v

    def close(self):
        pass


# ============================================================ detector de ciclo
class CycleDetector:
    def __init__(self, rest: dict):
        self.rest = rest
        c = config.CYCLE
        self.leave, self.back, self.hold = c["leave_deg"], c["rest_deg"], c["hold_s"]
        self.min_s = c["min_s"]
        # Para "ha vuelto" solo miramos las articulaciones grandes: la muñeca nunca vuelve exacta
        self.return_joints = c.get("return_joints", ARM_JOINTS)
        self.still_deg = c.get("still_deg", 0.6)
        self.grip_needed = c["grip_range"] if c["require_grip"] else 0
        self.left = False
        self.at_rest_since = None
        self.gmin = self.gmax = None
        self.dist = 0.0
        self.prev = None

    def update(self, obs: dict, t: float) -> bool:
        """True cuando el ciclo ha terminado."""
        self.dist = max(abs(obs[f"{j}.pos"] - self.rest[j]) for j in ARM_JOINTS)
        back_dist = max(abs(obs[f"{j}.pos"] - self.rest[j]) for j in self.return_joints)
        cur = [obs[f"{j}.pos"] for j in ARM_JOINTS]
        speed = 0.0 if self.prev is None else max(abs(a - b) for a, b in zip(cur, self.prev))
        self.prev = cur
        g = obs[f"{GRIPPER}.pos"]
        self.gmin = g if self.gmin is None else min(self.gmin, g)
        self.gmax = g if self.gmax is None else max(self.gmax, g)

        if not self.left:
            # "ha salido" con las articulaciones grandes: al arrancar ACT a veces solo mueve
            # la muñeca unos segundos y eso no cuenta como empezar
            self.left = back_dist > self.leave
            return False
        if t < self.min_s:
            return False
        # Nunca se da por terminado sin haber cogido y soltado (si se atasca, salta max_s)
        if self.grip_range < self.grip_needed:
            self.at_rest_since = None
            return False
        # Vuelta a reposo: las articulaciones grandes cerca de reposo...
        near_rest = back_dist < self.back
        # ...o ya ha cogido y soltado y está quieto "cerca" (por si se queda unos grados desviado)
        settled = (self.grip_range >= self.grip_needed and back_dist < self.back * 2.5
                   and speed < self.still_deg)
        if near_rest or settled:
            if self.at_rest_since is None:
                self.at_rest_since = t
            return t - self.at_rest_since >= self.hold
        self.at_rest_since = None
        return False

    @property
    def grip_range(self):
        return 0.0 if self.gmin is None else self.gmax - self.gmin

    @property
    def phase(self):
        if not self.left:
            return "arrancando"
        return "volviendo" if self.dist < self.leave else "trabajando"


# ======================================================================= bucle
class Worker:
    def __init__(self, hw):
        self.hw = hw
        self.period = 1.0 / config.FPS
        self.stop = threading.Event()
        self.rest = self.capture_pose()
        log(f"postura de reposo: {self.fmt(self.rest)}")

    @staticmethod
    def fmt(pose):
        return ", ".join(f"{k}={v:.0f}" for k, v in pose.items())

    def capture_pose(self):
        obs = self.hw.observe()
        return {j: float(obs[f"{j}.pos"]) for j in ALL_JOINTS}

    def wait_tick(self, t_start):
        dt = self.period - (time.perf_counter() - t_start)
        if dt > 0:
            time.sleep(dt)

    def move_to(self, target: dict, seconds=2.0):
        """Lleva el brazo a una postura poco a poco."""
        start = self.capture_pose()
        steps = max(1, int(seconds * config.FPS))
        for i in range(1, steps + 1):
            if self.stop.is_set():
                return
            t0 = time.perf_counter()
            a = i / steps
            self.hw.send({f"{j}.pos": start[j] + (target[j] - start[j]) * a for j in ALL_JOINTS})
            self.wait_tick(t0)

    def pick(self, job_id, key):
        if key not in getattr(self.hw, "policies", config.PILLS):
            emit(event="done", id=job_id, ok=False, reason="unknown_pill", elapsed=0)
            return
        c = config.CYCLE
        self.stop.clear()
        self.hw.reset_policy(key)
        det = CycleDetector(self.rest)
        t_begin = time.perf_counter()
        last_report = 0.0
        reason = "timeout"
        try:
            while True:
                t0 = time.perf_counter()
                t = t0 - t_begin
                if self.stop.is_set():
                    reason = "stopped"
                    break
                if t > c["max_s"]:
                    reason = "timeout"
                    break
                obs = self.hw.observe()
                if det.update(obs, t):
                    reason = "done"
                    break
                self.hw.send(self.hw.act(key, obs))
                if t - last_report >= 0.5:
                    emit(event="progress", id=job_id, t=round(t, 1), phase=det.phase,
                         dist=round(det.dist, 1), grip=round(det.grip_range, 1))
                    last_report = t
                self.wait_tick(t0)
        except Exception as e:  # noqa: BLE001
            log(traceback.format_exc())
            reason = f"error: {e}"

        elapsed = round(time.perf_counter() - t_begin, 1)
        ok = reason == "done"
        if ok and c["require_grip"] and det.grip_range < c["grip_range"]:
            ok, reason = False, "no_grip"
        if reason in ("timeout", "no_grip") or reason.startswith("error"):
            self.stop.clear()
            self.move_to(self.rest)                      # que no se quede a medias
        elif ok:
            # recolocar en la postura EXACTA de reposo: la siguiente pastilla tiene que
            # empezar igual que en las grabaciones (y así la detección vuelve a funcionar)
            self.move_to(self.rest, seconds=1.0)
        log(f"{key}: {reason} en {elapsed}s (pinza {det.grip_range:.0f})")
        emit(event="done", id=job_id, ok=ok, reason=reason, elapsed=elapsed,
             grip=round(det.grip_range, 1))

    def handle(self, msg):
        cmd = msg.get("cmd")
        if cmd == "pick":
            self.pick(msg.get("id"), msg.get("pill"))
        elif cmd == "home":
            self.stop.clear()
            self.move_to(self.rest)
            emit(event="info", msg="Brazo en reposo")
        elif cmd == "set_rest":
            self.rest = self.capture_pose()
            log(f"nueva postura de reposo: {self.fmt(self.rest)}")
            emit(event="info", msg="Postura de reposo guardada")


def stdin_reader(worker: Worker, q: queue.Queue):
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if msg.get("cmd") == "stop":
            worker.stop.set()           # se atiende al momento, aunque esté en mitad de un ciclo
        else:
            q.put(msg)
    q.put({"cmd": "quit"})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true", help="brazo simulado, sin LeRobot")
    args = ap.parse_args()

    try:
        hw = MockHardware() if args.mock else RealHardware()
        worker = Worker(hw)
    except Exception as e:  # noqa: BLE001
        log(traceback.format_exc())
        emit(event="fatal", msg=f"{type(e).__name__}: {e}")
        return 1

    emit(event="ready", pills=list(config.PILLS), rest=worker.rest)
    q: queue.Queue = queue.Queue()
    threading.Thread(target=stdin_reader, args=(worker, q), daemon=True).start()
    try:
        while True:
            msg = q.get()
            if msg.get("cmd") == "quit":
                break
            worker.handle(msg)
    finally:
        hw.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
