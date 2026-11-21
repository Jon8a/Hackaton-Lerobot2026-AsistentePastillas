"""
PastiBot - pastillero robótico para residencias (hackathon LeRobot Bilbao)

  pip install fastapi uvicorn      (en el mismo entorno donde está lerobot)
  python server.py                 -> robot real
  python server.py --sim           -> sin robot (cada pastilla tarda unos segundos)

Abrid http://localhost:8000
"""
import argparse
import shutil
import sys
from collections import Counter

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend import config
from backend.robot import RobotBusy, RobotRunner
from backend.storage import Storage

storage = Storage(config.DATA_FILE)
runner = RobotRunner(on_step_done=storage.consume, on_finish=storage.log_job)
app = FastAPI(title="PastiBot")


class ServeReq(BaseModel):
    resident_id: str
    moment: str
    force: bool = False


class StockReq(BaseModel):
    stock: int


class ScheduleReq(BaseModel):
    schedule: dict[str, dict[str, int]]


class ResetReq(BaseModel):
    scope: str = "day"


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "simulate": runner.sim,
        "busy": runner.active is not None,
        "active_job": runner.active.id if runner.active else None,
        "lerobot_found": runner.sim or shutil.which(config.LEROBOT_ROLLOUT) is not None,
        "pills": list(config.PILLS.keys()),
    }


@app.get("/api/state")
def state():
    return storage.overview()


@app.post("/api/serve")
def serve(req: ServeReq):
    r = storage.resident(req.resident_id)
    if not r:
        raise HTTPException(404, "No existe ese residente")
    if req.moment not in config.MOMENT_IDS:
        raise HTTPException(400, "Toma desconocida")
    picks = storage.picks_for(r, req.moment)
    if not picks:
        raise HTTPException(400, f"{r['name']} no tiene pastillas en esta toma")

    served = storage.served_at(r["id"], req.moment)
    if served and not req.force:
        raise HTTPException(409, f"Esta toma ya se sirvió a las {served}")

    for key, n in Counter(picks).items():
        if storage.data["stock"].get(key, 0) < n:
            raise HTTPException(400, f"No quedan suficientes pastillas de {config.PILLS[key]['name']}")

    try:
        job = runner.start(picks, resident=r, moment=req.moment, forced=req.force)
    except RobotBusy:
        raise HTTPException(409, "El robot está ocupado")
    return job.to_dict()


@app.get("/api/jobs/{job_id}")
def job(job_id: str):
    j = runner.jobs.get(job_id)
    if not j:
        raise HTTPException(404, "No existe ese trabajo")
    return j.to_dict()


@app.post("/api/stop")
def stop():
    return {"ok": True, "stopped": runner.stop()}


@app.put("/api/pills/{key}")
def set_stock(key: str, req: StockReq):
    if key not in config.PILLS:
        raise HTTPException(404, "Pastilla desconocida")
    storage.set_stock(key, req.stock)
    return {"ok": True}


@app.put("/api/residents/{rid}")
def set_schedule(rid: str, req: ScheduleReq):
    if not storage.resident(rid):
        raise HTTPException(404, "No existe ese residente")
    storage.set_schedule(rid, req.schedule)
    return {"ok": True}


@app.post("/api/reset")
def reset(req: ResetReq):
    if runner.active:
        raise HTTPException(409, "Espera a que el robot termine")
    storage.reset("all" if req.scope == "all" else "day")
    return {"ok": True}


# La interfaz (va al final para no tapar las rutas /api)
app.mount("/", StaticFiles(directory=config.FRONTEND_DIR, html=True), name="frontend")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="PastiBot")
    ap.add_argument("--sim", action="store_true", help="simular el robot")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    runner.sim = args.sim
    if not args.sim and shutil.which(config.LEROBOT_ROLLOUT) is None:
        print(f"AVISO: no encuentro '{config.LEROBOT_ROLLOUT}'. Activa el entorno de lerobot "
              f"o arranca con --sim.", file=sys.stderr)
    print(f"PastiBot en http://localhost:{args.port}  ({'SIMULACIÓN' if args.sim else 'ROBOT REAL'})")
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
