"""Ejecuta el robot: un trabajo = una lista de pastillas; cada pastilla = una
ejecución de lerobot-rollout con el modelo ACT de su cuenco."""
import os
import signal
import subprocess
import threading
import time
import uuid

from . import config

FINAL_STATES = ("done", "error", "stopped")


class RobotBusy(Exception):
    pass


def build_cmd(key: str) -> list[str]:
    p = config.PILLS[key]
    if "cmd" in p:
        return list(p["cmd"])
    r = config.ROBOT
    return [
        config.LEROBOT_ROLLOUT,
        "--strategy.type=base",                 # ejecuta la política sin grabar nada
        f"--policy.path={p['policy']}",
        f"--robot.type={r['type']}",
        f"--robot.port={r['port']}",
        f"--robot.id={r['id']}",
        f"--robot.calibration_dir={r['calibration_dir']}",
        f"--robot.cameras={config.CAMERAS}",
        f"--task={p['task']}",
        f"--duration={p.get('time', config.DURATION_S)}",
    ]


class Job:
    def __init__(self, picks, resident, moment, forced):
        self.id = uuid.uuid4().hex[:8]
        self.resident_id = resident["id"]
        self.resident_name = resident["name"]
        self.moment = moment
        self.forced = forced
        self.steps = [{"pill": k, "state": "pending"} for k in picks]
        self.state = "running"
        self.current: int | None = None
        self.log: list[str] = []
        self.proc: subprocess.Popen | None = None
        self.stop = False

    def add_log(self, line: str):
        self.log.append(line)
        del self.log[:-300]

    def to_dict(self):
        return {
            "id": self.id, "state": self.state, "current": self.current,
            "resident_id": self.resident_id, "resident_name": self.resident_name,
            "moment": self.moment, "forced": self.forced,
            "steps": self.steps, "log": self.log[-60:],
        }


class RobotRunner:
    def __init__(self, on_step_done=None, on_finish=None):
        self.sim = False
        self.jobs: dict[str, Job] = {}
        self.active: Job | None = None
        self.lock = threading.Lock()
        self.on_step_done = on_step_done
        self.on_finish = on_finish

    def start(self, picks, resident, moment, forced=False) -> Job:
        with self.lock:
            if self.active is not None:
                raise RobotBusy()
            job = Job(picks, resident, moment, forced)
            self.jobs[job.id] = job
            self.active = job
        threading.Thread(target=self._run, args=(job,), daemon=True).start()
        return job

    def stop(self) -> bool:
        job = self.active
        if not job:
            return False
        job.stop = True
        proc = job.proc
        if proc and proc.poll() is None:
            # Linux: Ctrl+C para que lerobot suelte el brazo bien. Windows: terminate.
            if os.name == "posix":
                proc.send_signal(signal.SIGINT)
            else:
                proc.terminate()
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()
        return True

    # ------------------------------------------------------------ interno
    def _run(self, job: Job):
        try:
            for i, step in enumerate(job.steps):
                if job.stop:
                    step["state"] = "skipped"
                    continue
                job.current = i
                step["state"] = "running"
                rc = self._run_step(job, step["pill"])
                if job.stop:
                    step["state"] = "stopped"
                elif rc == 0:
                    step["state"] = "done"
                    if self.on_step_done:
                        self.on_step_done(step["pill"])
                else:
                    step["state"] = "error"
                    job.state = "error"
                    for rest in job.steps[i + 1:]:
                        rest["state"] = "skipped"
                    break
            if job.state != "error":
                job.state = "stopped" if job.stop else "done"
        except Exception as e:  # nunca dejarlo colgado en "running"
            job.add_log(f"ERROR inesperado: {e!r}")
            job.state = "error"
        finally:
            job.current = None
            try:
                if self.on_finish:
                    self.on_finish(job)
            finally:
                with self.lock:
                    self.active = None

    def _run_step(self, job: Job, key: str) -> int:
        cmd = build_cmd(key)
        job.add_log("$ " + " ".join(cmd))
        if self.sim:
            for _ in range(int(config.SIM_STEP_S * 10)):
                if job.stop:
                    return 1
                time.sleep(0.1)
            job.add_log(f"[sim] {config.PILLS[key]['name']} en el vaso")
            return 0
        try:
            job.proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
            )
        except FileNotFoundError:
            job.add_log(f"ERROR: no se encuentra '{cmd[0]}'. ¿Está activado el entorno de lerobot?")
            return -1
        for line in job.proc.stdout:
            job.add_log(line.rstrip())
        rc = job.proc.wait()
        job.proc = None
        job.add_log(f"(terminó con código {rc})")
        return rc
