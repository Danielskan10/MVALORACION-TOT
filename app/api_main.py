#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import shutil
import logging
from pathlib import Path
from typing import Any, Dict, Optional

import uvicorn
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from routers import insumos, porfin, mitra
from config import get_config, update_config, get_data_dir

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger("mvaloracion")

app = FastAPI(
    title="MVALORACION",
    description="Plataforma de revisión y control operativo de valoración financiera",
    version="2.0.0",
    docs_url="/api/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(insumos.router, prefix="/api/insumos", tags=["Insumos"])
app.include_router(porfin.router,  prefix="/api/porfin",  tags=["Porfin"])
app.include_router(mitra.router,   prefix="/api/mitra",   tags=["Mitra"])


# ── Config ─────────────────────────────────────────────────────────────────
class ConfigUpdate(BaseModel):
    data_dir:                  Optional[str]   = None
    infovalmer_dir:            Optional[str]   = None
    umbral_variacion_pct:      Optional[float] = None
    umbral_dif_causacion:      Optional[float] = None
    umbral_dif_valoracion:     Optional[float] = None
    umbral_dif_valoracion_pct: Optional[float] = None
    port:                      Optional[int]   = None
    host:                      Optional[str]   = None
    proxy:                     Optional[str]   = None
    ssl_cert:                  Optional[str]   = None
    ref_especies:              Optional[str]   = None
    ref_fcpe:                  Optional[str]   = None
    ref_fiduciaria:            Optional[str]   = None
    ref_fondos:                Optional[str]   = None
    ref_fcp:                   Optional[str]   = None


@app.get("/api/config", tags=["Config"])
def get_config_endpoint():
    cfg = get_config()
    # Enriquecer con existencia de cada ruta
    cfg["data_dir_exists"] = os.path.isdir(cfg.get("data_dir", ""))
    cfg["infovalmer_dir_exists"] = os.path.isdir(cfg.get("infovalmer_dir", ""))
    for key in ["ref_especies", "ref_fcpe", "ref_fiduciaria", "ref_fondos", "ref_fcp"]:
        path = cfg.get(key, "")
        cfg[f"{key}_exists"] = os.path.isfile(path) if path else False
    return cfg


@app.post("/api/config", tags=["Config"])
def update_config_endpoint(body: ConfigUpdate):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        return {"ok": False, "msg": "Sin cambios"}
    cfg = update_config(updates)
    return {"ok": True, "config": cfg}


# ── Upload de archivos ──────────────────────────────────────────────────────
@app.post("/api/upload/{modulo}", tags=["Upload"])
async def upload_archivo(
    modulo: str,
    fecha: str = Form(...),
    file: UploadFile = File(...),
):
    """
    Recibe un archivo y lo guarda en data/{fecha}/.
    modulo: porfin | mitra | insumos
    """
    if modulo not in ("porfin", "mitra", "insumos"):
        raise HTTPException(400, f"Módulo inválido: {modulo}")

    data_dir = get_data_dir()
    dest_dir = data_dir / fecha
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest = dest_dir / file.filename
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    logger.info(f"Upload {modulo} → {dest}")
    return {"ok": True, "path": str(dest), "size": dest.stat().st_size}


# ── Frontend ────────────────────────────────────────────────────────────────
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
FRONTEND_DIR.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/", include_in_schema=False)
def root():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.get("/{page}.html", include_in_schema=False)
def serve_page(page: str):
    f = FRONTEND_DIR / f"{page}.html"
    if f.exists():
        return FileResponse(str(f))
    return FileResponse(str(FRONTEND_DIR / "index.html"))


if __name__ == "__main__":
    logger.info("MVALORACION iniciando en http://localhost:8000")
    uvicorn.run("api_main:app", host="0.0.0.0", port=8000, reload=True)
