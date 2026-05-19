#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API PRINCIPAL — MVALORACION
FastAPI sirve los 3 módulos: Insumos, Porfin, Mitra
Ejecutar: python api_main.py   →  http://localhost:8000
"""
from __future__ import annotations

import os
import re
import logging
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from routers import insumos, porfin, mitra

# ── Logging ────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger("mvaloracion")

# ── App ────────────────────────────────────────────────────────────────
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

# ── Routers ────────────────────────────────────────────────────────────
app.include_router(insumos.router, prefix="/api/insumos", tags=["Insumos"])
app.include_router(porfin.router,  prefix="/api/porfin",  tags=["Porfin"])
app.include_router(mitra.router,   prefix="/api/mitra",   tags=["Mitra"])

# ── Archivos estáticos (frontend) ──────────────────────────────────────
# frontend/ está un nivel arriba de app/
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

# ── Entry point ────────────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info("🚀  MVALORACION iniciando en http://localhost:8000")
    uvicorn.run("api_main:app", host="0.0.0.0", port=8000, reload=True)
