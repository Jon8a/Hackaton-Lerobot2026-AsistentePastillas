"""Arranca robot_worker.py y habla con él (líneas JSON por stdin/stdout)."""
import json
import queue
import subprocess
import sys
import threading
from pathlib import Path

WORKER = Path(__file__).resolve().parent / "robot_worker.py"

REASONS = {
    "done": "ciclo completo",
    "stopped": "parado por el usuario",
    "timeout": "no ha terminado a tiempo",
    "no_grip": "la pinza no se ha movido: no ha cogido nada",
    "unknown_pill": "no hay modelo para esa pastilla",
}


class WorkerClient:
    def __init__(self, mock: bool = False):
        self.mock = mock
        self.proc: subprocess.Popen | None = None
        self.state = "off"           # off | loading | ready | error
        self.msg = ""
        self.log: list[str] = []      # salida del worker (stderr), para depurar
        self._events: queue.Queue = queue.Queue()
        self._write_lock = threading.Lock()

    # ------------------------------------------------------------ arranque
    def start(self):
        cmd = [sys.executable, "-u", str(WORKER)] + (["--mock"] if self.mock else [])
        self.state, self.msg = "loading", "Arrancando…"
        self.proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
        )
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()

    def restart(self):
        self.close()
        self._events = queue.Queue()
        self.start()

    def close(self):
        if self.proc and self.proc.poll() is None:
            self.send({"cmd": "quit"})
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()

    def _read_stdout(self):
        for line in self.proc.stdout:
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                self._add_log(line.rstrip())
                continue
            ev = msg.get("event")
            if ev == "status":
                self.msg = msg.get("msg", "")
                self._add_log(f"· {self.msg}")
            elif ev == "ready":
                self.state, self.msg = "ready", "Listo"
                self._add_log("· Robot listo")
            elif ev == "fatal":
                self.state, self.msg = "error", msg.get("msg", "Error")
                self._add_log(f"ERROR: {self.msg}")
            elif ev == "info":
                self._add_log(f"· {msg.get('msg')}")
            else:                                   # progress / done -> al trabajo en curso
                self._events.put(msg)
        # el proceso ha terminado
        if self.state != "error":
            self.state, self.msg = "error", "El proceso del robot se ha cerrado"
        self._events.put({"event": "dead"})

    def _read_stderr(self):
        for line in self.proc.stderr:
            self._add_log(line.rstrip())

    def _add_log(self, line):
        self.log.append(line)
        del self.log[:-400]

    # ------------------------------------------------------------- órdenes
    def send(self, obj):
        if not self.proc or self.proc.poll() is not None:
            return False
        with self._write_lock:
            try:
                self.proc.stdin.write(json.dumps(obj) + "\n")
                self.proc.stdin.flush()
                return True
            except (BrokenPipeError, OSError):
                return False

    def pick(self, job_id: str, key: str, on_progress=None) -> tuple[bool, str]:
        """Bloquea hasta que el worker termina la pastilla. Devuelve (ok, motivo)."""
        if self.state != "ready":
            return False, f"el robot no está listo ({self.msg})"
        while not self._events.empty():           # restos de un trabajo anterior
            self._events.get_nowait()
        if not self.send({"cmd": "pick", "id": job_id, "pill": key}):
            return False, "no se puede hablar con el proceso del robot"
        while True:
            msg = self._events.get()
            if msg.get("event") == "dead":
                return False, "el proceso del robot se ha cerrado"
            if msg.get("id") != job_id:
                continue
            if msg["event"] == "progress" and on_progress:
                on_progress(msg)
            elif msg["event"] == "done":
                reason = msg.get("reason", "")
                text = REASONS.get(reason, reason)
                return bool(msg.get("ok")), f"{text} ({msg.get('elapsed')} s)"

    def stop(self):
        self.send({"cmd": "stop"})

    def home(self):
        return self.send({"cmd": "home"})

    def set_rest(self):
        return self.send({"cmd": "set_rest"})
