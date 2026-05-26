#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MVALORACION — Módulo Porfin
Servidor FastAPI independiente. Puerto por defecto: 8002.

Uso:
    cd porfin
    python main.py
    -> http://localhost:8002
"""
from __future__ import annotations

import os
import shutil
import logging
import collections
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from config import get_config, update_config, get_data_dir
import router as porfin_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger("porfin")

_LOG_BUFFER: collections.deque = collections.deque(maxlen=500)
_FMT = logging.Formatter()

class _BufHandler(logging.Handler):
    def emit(self, record):
        _LOG_BUFFER.append({
            "ts":    _FMT.formatTime(record, "%H:%M:%S"),
            "level": record.levelname,
            "msg":   record.getMessage(),
        })

logging.getLogger().addHandler(_BufHandler())

app = FastAPI(
    title="MVALORACION — Porfin",
    description="Verificacion de valoracion y causacion Porfin 596/575",
    version="2.0.0",
    docs_url="/api/docs",
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(porfin_router.router, prefix="/api/porfin", tags=["Porfin"])


class ConfigUpdate(BaseModel):
    data_dir:                  Optional[str]   = None
    umbral_dif_causacion:      Optional[float] = None
    umbral_dif_valoracion:     Optional[float] = None
    umbral_dif_valoracion_pct: Optional[float] = None
    ref_especies:              Optional[str]   = None
    ref_fcpe:                  Optional[str]   = None
    ref_fiduciaria:            Optional[str]   = None
    ref_fondos:                Optional[str]   = None
    ref_fcp:                   Optional[str]   = None
    host:                      Optional[str]   = None
    port:                      Optional[int]   = None


@app.get("/api/config", tags=["Config"])
def get_config_endpoint():
    cfg = get_config()
    cfg["data_dir_exists"] = os.path.isdir(cfg.get("data_dir", ""))
    for key in ["ref_especies", "ref_fcpe", "ref_fiduciaria", "ref_fondos", "ref_fcp"]:
        path = cfg.get(key, "")
        cfg[f"{key}_exists"] = os.path.isfile(path) if path else False
    return cfg


@app.post("/api/config", tags=["Config"])
def update_config_endpoint(body: ConfigUpdate):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        return {"ok": False, "msg": "Sin cambios"}
    return {"ok": True, "config": update_config(updates)}


@app.get("/api/logs", tags=["System"])
def get_logs(limit: int = 200):
    return list(_LOG_BUFFER)[-limit:]


@app.post("/api/upload", tags=["Upload"])
async def upload_archivo(fecha: str = Form(...), file: UploadFile = File(...)):
    data_dir = get_data_dir()
    dest_dir = data_dir / fecha
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / file.filename
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    logger.info(f"Upload porfin -> {dest}")
    return {"ok": True, "path": str(dest), "size": dest.stat().st_size}


FRONTEND = Path(__file__).parent / "frontend"
app.mount("/static", StaticFiles(directory=str(FRONTEND)), name="static")


@app.get("/", include_in_schema=False)
def root():
    return FileResponse(str(FRONTEND / "index.html"))


@app.get("/{path:path}", include_in_schema=False)
def catch_all(path: str):
    f = FRONTEND / path
    if f.exists() and f.is_file():
        return FileResponse(str(f))
    return FileResponse(str(FRONTEND / "index.html"))


if __name__ == "__main__":
    cfg  = get_config()
    host = cfg.get("host", "0.0.0.0")
    port = int(cfg.get("port", 8002))
    logger.info(f"Porfin arrancando -> http://{host}:{port}")
    uvicorn.run("main:app", host=host, port=port, reload=bool(cfg.get("reload", True)))
