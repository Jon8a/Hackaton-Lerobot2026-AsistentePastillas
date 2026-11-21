"""Guarda residentes, stock e historial en data/state.json y calcula el estado del día."""
import copy
import json
import threading
import uuid
from datetime import datetime
from pathlib import Path

from . import config, seed


def current_moment(hour: int) -> str:
    for m in config.MOMENTS:
        s, e = m["start"], m["end"]
        if (s < e and s <= hour < e) or (s >= e and (hour >= s or hour < e)):
            return m["id"]
    return config.MOMENT_IDS[0]


class Storage:
    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.RLock()
        self.data = self._load()

    # ------------------------------------------------------------ disco
    def _load(self) -> dict:
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                for k in config.PILLS:                       # pastillas nuevas en config
                    data["stock"].setdefault(k, config.BOWL_CAPACITY)
                return data
            except (json.JSONDecodeError, KeyError):
                pass
        data = seed.initial_state()
        self._write(data)
        return data

    def _write(self, data: dict):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def _save(self):
        self._write(self.data)

    # ---------------------------------------------------------- lectura
    def resident(self, rid: str) -> dict | None:
        return next((r for r in self.data["residents"] if r["id"] == rid), None)

    @staticmethod
    def picks_for(resident: dict, moment: str) -> list[str]:
        """{"metformina": 2, "sintrom": 1} -> ["metformina", "metformina", "sintrom"]"""
        out = []
        for key, qty in resident["schedule"].get(moment, {}).items():
            out += [key] * int(qty)
        return out

    def today_entries(self, rid: str, moment: str) -> list[dict]:
        today = datetime.now().strftime("%Y-%m-%d")
        return [e for e in self.data["log"]
                if e["date"] == today and e["resident_id"] == rid and e["moment"] == moment]

    def served_at(self, rid: str, moment: str) -> str | None:
        done = [e for e in self.today_entries(rid, moment) if e["status"] == "done"]
        return done[-1]["time"] if done else None

    def overview(self) -> dict:
        with self.lock:
            now = datetime.now()
            cur = current_moment(now.hour)
            cur_idx = config.MOMENT_IDS.index(cur)
            residents = []
            for r in self.data["residents"]:
                status = {}
                for i, m in enumerate(config.MOMENT_IDS):
                    picks = self.picks_for(r, m)
                    entries = self.today_entries(r["id"], m)
                    served = self.served_at(r["id"], m)
                    if not picks:
                        state = "none"
                    elif served:
                        state = "done"
                    elif entries:
                        state = "failed"
                    elif i < cur_idx:
                        state = "missed"
                    else:
                        state = "pending"
                    status[m] = {"picks": picks, "state": state, "time": served}
                residents.append({**copy.deepcopy(r), "status": status})

            pills = []
            for key, p in config.PILLS.items():
                stock = self.data["stock"].get(key, 0)
                pills.append({
                    "key": key, "name": p["name"], "dose": p["dose"], "bowl": p["bowl"],
                    "bowl_color": p["bowl_color"], "pill_color": p["pill_color"],
                    "pill_desc": p["pill_desc"], "warning": p.get("warning"),
                    "stock": stock, "capacity": config.BOWL_CAPACITY,
                    "low": stock <= config.LOW_STOCK,
                })

            return {
                "date": now.strftime("%Y-%m-%d"),
                "now": now.strftime("%H:%M"),
                "current_moment": cur,
                "moments": config.MOMENTS,
                "pills": pills,
                "residents": residents,
                "log": list(reversed(self.data["log"][-100:])),
            }

    # --------------------------------------------------------- escritura
    def consume(self, key: str):
        with self.lock:
            self.data["stock"][key] = max(0, self.data["stock"].get(key, 0) - 1)
            self._save()

    def set_stock(self, key: str, value: int):
        with self.lock:
            self.data["stock"][key] = max(0, min(int(value), 999))
            self._save()

    def set_schedule(self, rid: str, schedule: dict):
        with self.lock:
            r = self.resident(rid)
            clean = {}
            for m in config.MOMENT_IDS:
                clean[m] = {k: int(q) for k, q in schedule.get(m, {}).items()
                            if k in config.PILLS and int(q) > 0}
            r["schedule"] = clean
            self._save()

    def log_job(self, job):
        """Lo llama el robot al terminar un trabajo."""
        with self.lock:
            now = datetime.now()
            self.data["log"].append({
                "id": uuid.uuid4().hex[:8],
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M"),
                "resident_id": job.resident_id,
                "resident_name": job.resident_name,
                "moment": job.moment,
                "picks": [s["pill"] for s in job.steps],
                "done": [s["pill"] for s in job.steps if s["state"] == "done"],
                "status": job.state,          # done | error | stopped
                "forced": job.forced,
            })
            self.data["log"] = self.data["log"][-1000:]
            self._save()

    def reset(self, scope: str):
        """scope="day": borra el historial de hoy y rellena cuencos (para ensayar la demo).
        scope="all": vuelve a los datos de demo."""
        with self.lock:
            if scope == "all":
                self.data = seed.initial_state()
            else:
                today = datetime.now().strftime("%Y-%m-%d")
                self.data["log"] = [e for e in self.data["log"] if e["date"] != today]
                self.data["stock"] = {k: config.BOWL_CAPACITY for k in config.PILLS}
            self._save()
