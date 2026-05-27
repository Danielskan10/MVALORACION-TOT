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

from config import get_config, update_config, get_data_dir
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
    data_dir:             Optional[str]   = None
    infovalmer_dir:       Optional[str]   = None
    umbral_variacion_pct: Optional[float] = None
    host:                 Optional[str]   = None
    port:                 Optional[int]   = None
    proxy:                Optional[str]   = None
    ssl_verify:           Optional[bool]  = None


@app.get("/api/config", tags=["Config"])
def get_config_endpoint():
    cfg = get_config()
    cfg["data_dir_exists"]       = os.path.isdir(cfg.get("data_dir", ""))
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
    Corre en hilo separado tras el arranque.
    Para la fecha más reciente disponible en Infovalmer:
      - Si todos los PKL ya existen → solo reporta, no reconvierte.
      - Si faltan → convierte los que falten y exporta Excel a la misma
        carpeta de infovalmer del día.
    """
    try:
        from router import (
            _fechas_disponibles, _cache_status, _cache_path,
            _leer_cache, _guardar_cache, _infovalmer_dir,
            cargar_sp, cargar_sw, cargar_tp, cargar_sv,
            cargar_mx, cargar_mx_rv, cargar_notas, cargar_sb, cargar_monedas,
        )
        import concurrent.futures

        fechas = _fechas_disponibles()
        if not fechas:
            logger.warning("Auto-conversión: no se encontraron fechas en Infovalmer ni en data_dir.")
            return

        fecha = fechas[-1]          # la más reciente
        status = _cache_status(fecha)
        conv  = status["convertidos"]
        total = status["total"]

        if status["completo"]:
            logger.info(
                f"Auto-conversión [{fecha}]: cache completo — "
                f"{conv}/{total} proveedores listos. Sin necesidad de reconvertir."
            )
            return

        faltantes = [p for p, v in status["proveedores"].items() if not v["cache"]]
        logger.info(
            f"Auto-conversión [{fecha}]: {conv}/{total} en cache. "
            f"Convirtiendo: {', '.join(faltantes)}"
        )

        cargadores = {
            "SP": cargar_sp, "SW": cargar_sw, "TP": cargar_tp,
            "SV": cargar_sv, "MX": cargar_mx,  "MX_RV": cargar_mx_rv,
            "NOTAS": cargar_notas, "SB": cargar_sb, "MONEDAS": cargar_monedas,
        }
        infovalmer_dia = _infovalmer_dir(fecha)

        def _uno(proveedor):
            loader = cargadores.get(proveedor)
            if not loader:
                return proveedor, 0, False, "sin cargador"
            try:
                df = loader(fecha, use_cache=False)
                if df.empty:
                    return proveedor, 0, False, "archivo no encontrado"
                # PKL en cache_insumos (acceso rápido)
                _guardar_cache(fecha, proveedor, df, export_excel=False)
                # Excel en carpeta infovalmer del día
                if infovalmer_dia.exists():
                    xlsx_path = infovalmer_dia / f"{proveedor}_{fecha}.xlsx"
                    try:
                        df.to_excel(xlsx_path, index=False)
                        logger.info(f"  {proveedor}: {len(df)} filas → {xlsx_path.name}")
                    except Exception as xe:
                        logger.warning(f"  {proveedor}: Excel falló ({xe}), solo PKL.")
                else:
                    logger.warning(
                        f"  {proveedor}: carpeta infovalmer no accesible "
                        f"({infovalmer_dia}), Excel omitido."
                    )
                return proveedor, len(df), True, None
            except Exception as e:
                logger.error(f"  {proveedor}: error — {e}")
                return proveedor, 0, False, str(e)

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            resultados = list(pool.map(_uno, faltantes))

        ok = sum(1 for _, _, s, _ in resultados if s)
        logger.info(
            f"Auto-conversión [{fecha}] completada: "
            f"{ok}/{len(faltantes)} nuevos proveedores convertidos."
        )

    except Exception as e:
        logger.error(f"Auto-conversión falló: {e}")


# ── Arranque ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    cfg    = get_config()
    host   = cfg.get("host", "0.0.0.0")
    port   = int(cfg.get("port", 8001))
    reload = bool(cfg.get("reload", False))   # reload=False para no perder el hilo de conversión

    # Banner de arranque
    print()
    print("=" * 54)
    print("  MVALORACION — Insumos")
    print(f"  URL   →  http://localhost:{port}")
    print(f"  API   →  http://localhost:{port}/api/docs")
    print(f"  Host  →  {host}:{port}")
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
                log_level="warning")   # ← silencia logs internos de uvicorn
