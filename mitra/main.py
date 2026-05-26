#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MVALORACION — Módulo Mitra
Servidor FastAPI independiente. Puerto por defecto: 8003.

Uso:
    cd mitra
    python main.py
    -> http://localhost:8003
"""
from __future__ import annotations

import os
import logging
import collections
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from config import get_config, update_config, get_data_dir
import router as mitra_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger("mitra")

_LOG_BUFFER: collections.deque = collections.deque(maxlen=500)

class _BufHandler(logging.Handler):
    def emit(self, record):
        _LOG_BUFFER.append({
            "ts":    self.formatTime(record, "%H:%M:%S"),
            "level": record.levelname,
            "msg":   record.getMessage(),
        })

logging.getLogger().addHandler(_BufHandler())

app = FastAPI(
    title="MVALORACION — Mitra",
    description="Conciliacion DI/DF, causaciones y diferencias vs Porfin",
    version="2.0.0",
    docs_url="/api/docs",
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(mitra_router.router, prefix="/api/mitra", tags=["Mitra"])


class ConfigUpdate(BaseModel):
    data_dir:             Optional[str]   = None
    umbral_variacion_pct: Optional[float] = None
    umbral_dif_causacion: Optional[float] = None
    host:                 Optional[str]   = None
    port:                 Optional[int]   = None


@app.get("/api/config", tags=["Config"])
def get_config_endpoint():
    cfg = get_config()
    cfg["data_dir_exists"] = os.path.isdir(cfg.get("data_dir", ""))
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
    port = int(cfg.get("port", 8003))
    logger.info(f"Mitra arrancando -> http://{host}:{port}")
    uvicorn.run("main:app", host=host, port=port, reload=bool(cfg.get("reload", True)))
