#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MVALORACION — Módulo Insumos   (puerto 8001)
"""
from __future__ import annotations

import os
import sys
import logging
import collections
import threading
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from config import get_config, update_config
import router as insumos_router

# ── Logging: solo el módulo insumos, sin ruido de uvicorn / fastapi ──────────
_LOG_BUFFER: collections.deque = collections.deque(maxlen=500)
_FMT = logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s",
                          datefmt="%H:%M:%S")

class _BufHandler(logging.Handler):
    def emit(self, record: logging.LogRecord):
        _LOG_BUFFER.append({
            "ts":    _FMT.formatTime(record, "%H:%M:%S"),
            "level": record.levelname,
            "msg":   record.getMessage(),
        })

class _ConsoleHandler(logging.StreamHandler):
    """Muestra solo registros del módulo insumos en consola."""
    def emit(self, record: logging.LogRecord):
        if record.name.startswith("insumos"):
            super().emit(record)

# Silenciar loggers externos
for _ext in ("uvicorn", "uvicorn.error", "uvicorn.access",
             "fastapi", "multipart", "httpx"):
    logging.getLogger(_ext).setLevel(logging.WARNING)
    logging.getLogger(_ext).propagate = False

# Logger propio
logger = logging.getLogger("insumos")
logger.setLevel(logging.INFO)
logger.propagate = False

_ch = _ConsoleHandler(sys.stdout)
_ch.setFormatter(_FMT)
logger.addHandler(_ch)
logger.addHandler(_BufHandler())

# ── FastAPI ──────────────────────────────────────────────────────────────────
app = FastAPI(
    title="MVALORACION — Insumos",
    description="Precios diarios Infovalmer: SP, SW, SV, MX, NOTAS. Alertas y curvas.",
    version="2.0.0",
    docs_url="/api/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(insumos_router.router, prefix="/api/insumos", tags=["Insumos"])


# ── Config endpoints ─────────────────────────────────────────────────────────
class ConfigUpdate(BaseModel):
    infovalmer_dir:       Optional[str]   = None
    umbral_variacion_pct: Optional[float] = None
    host:                 Optional[str]   = None
    port:                 Optional[int]   = None


@app.get("/api/config", tags=["Config"])
def get_config_endpoint():
    cfg = get_config()
    cfg["infovalmer_dir_exists"] = os.path.isdir(cfg.get("infovalmer_dir", ""))
    return cfg


@app.post("/api/config", tags=["Config"])
def update_config_endpoint(body: ConfigUpdate):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        return {"ok": False, "msg": "Sin cambios"}
    cfg = update_config(updates)
    return {"ok": True, "config": cfg}


@app.get("/api/logs", tags=["System"])
def get_logs(limit: int = 200):
    return list(_LOG_BUFFER)[-limit:]


# ── Frontend estático ────────────────────────────────────────────────────────
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


# ── Conversión automática al inicio ──────────────────────────────────────────
def _auto_convertir():
    """
    Corre en hilo daemon después del arranque.
    Para CADA fecha disponible en Infovalmer (orden desc, máx 2 recientes):
      - Verifica si PKL + XLSX ya existen.
      - Si faltan -> convierte y exporta en:
          infovalmer/FECHA/pkl/PROVEEDOR_FECHA.pkl
          infovalmer/FECHA/excel/PROVEEDOR_FECHA.xlsx
    """
    try:
        from router import (
            _fechas_disponibles, _cache_status, _guardar_cache,
            cargar_sp, cargar_sw, cargar_tp, cargar_sv,
            cargar_mx, cargar_mx_rv, cargar_notas, cargar_sb, cargar_monedas,
        )
        import concurrent.futures

        fechas = _fechas_disponibles()
        if not fechas:
            logger.warning("Auto-conversión: Infovalmer no accesible o sin fechas.")
            return

        # Procesar las 2 fechas más recientes (hoy + anterior)
        for fecha in reversed(fechas[-2:]):
            status = _cache_status(fecha)
            pkl_ok = status["pkl_ok"]
            total  = status["total"]

            if status["completo"] and status["xlsx_ok"] == total:
                logger.info(
                    f"[{fecha}] Cache completo ({pkl_ok}/{total} PKL, "
                    f"{status['xlsx_ok']}/{total} XLSX). Sin conversión."
                )
                continue

            faltantes = [
                p for p, v in status["proveedores"].items()
                if not v["pkl"] or not v["xlsx"]
            ]
            logger.info(
                f"[{fecha}] Convirtiendo {len(faltantes)} proveedores: "
                f"{', '.join(faltantes)}"
            )

            cargadores = {
                "SP": cargar_sp, "SW": cargar_sw, "TP": cargar_tp,
                "SV": cargar_sv, "MX": cargar_mx, "MX_RV": cargar_mx_rv,
                "NOTAS": cargar_notas, "SB": cargar_sb, "MONEDAS": cargar_monedas,
            }

            def _uno(proveedor, _fecha=fecha):
                loader = cargadores.get(proveedor)
                if not loader:
                    return proveedor, 0, False
                try:
                    df = loader(_fecha, use_cache=False)
                    if df.empty:
                        logger.warning(f"  [{_fecha}] {proveedor}: fuente vacía o no encontrada")
                        return proveedor, 0, False
                    _guardar_cache(_fecha, proveedor, df, export_excel=True)
                    logger.info(
                        f"  [{_fecha}] {proveedor}: {len(df):,} filas "
                        f"-> pkl + excel OK"
                    )
                    return proveedor, len(df), True
                except Exception as e:
                    logger.error(f"  [{_fecha}] {proveedor}: {e}")
                    return proveedor, 0, False

            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                resultados = list(pool.map(_uno, faltantes))

            ok = sum(1 for _, _, s in resultados if s)
            logger.info(
                f"[{fecha}] Conversión completada: {ok}/{len(faltantes)} OK. "
                f"PKL -> infovalmer/{fecha}/pkl/   XLSX -> infovalmer/{fecha}/excel/"
            )

    except Exception as e:
        logger.error(f"Auto-conversión falló: {e}", exc_info=True)


# ── Arranque ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    cfg    = get_config()
    host   = cfg.get("host", "0.0.0.0")
    port   = int(cfg.get("port", 8001))
    reload = bool(cfg.get("reload", False))   # reload=False para no perder el hilo de conversión

    # Banner de arranque (solo ASCII para compatibilidad cp1252)
    print()
    print("=" * 54)
    print("  MVALORACION -- Insumos")
    print(f"  URL  ->  http://localhost:{port}")
    print(f"  API  ->  http://localhost:{port}/api/docs")
    print(f"  Host ->  {host}:{port}")
    print("=" * 54)
    print()

    # Lanzar conversión automática en hilo (después de que uvicorn inicie)
    def _delayed_convert():
        import time
        time.sleep(2)   # espera breve a que el servidor esté listo
        _auto_convertir()

    threading.Thread(target=_delayed_convert, daemon=True).start()

    logger.info(f"Servidor iniciando en http://{host}:{port}")
    uvicorn.run("main:app", host=host, port=port, reload=reload,
                log_level="warning")   # <- silencia logs internos de uvicorn
