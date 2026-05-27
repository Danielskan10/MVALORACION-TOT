#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MVALORACION — Módulo Insumos   (puerto 8001)
"""
from __future__ import annotations

import os
import sys
import json
import queue
import logging
import collections
import threading
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from config import get_config, update_config
import router as insumos_router

# ── Directorio de logs (junto al módulo) ─────────────────────────────────────
_LOGS_DIR = Path(__file__).parent / "logs"
_LOGS_DIR.mkdir(exist_ok=True)

_LOG_FILE = _LOGS_DIR / "insumos.log"   # rota en 5 MB × 5 archivos

# ── Buffer en memoria (últimas 1000 entradas) ─────────────────────────────────
_LOG_BUFFER: collections.deque = collections.deque(maxlen=1000)

# ── Colas SSE — cada cliente conectado recibe su propia cola ─────────────────
_SSE_QUEUES: list[queue.Queue] = []
_SSE_LOCK   = threading.Lock()

# ── Formato unificado ─────────────────────────────────────────────────────────
_FMT_CONSOLE = logging.Formatter(
    "%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
_FMT_FILE = logging.Formatter(
    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


# ── Handler: buffer en memoria + push a SSE ───────────────────────────────────
class _BufHandler(logging.Handler):
    def emit(self, record: logging.LogRecord):
        entry = {
            "ts":    self.formatter.formatTime(record, "%H:%M:%S"),
            "ts_iso": datetime.now().isoformat(timespec="seconds"),
            "level": record.levelname,
            "name":  record.name,
            "msg":   record.getMessage(),
        }
        _LOG_BUFFER.append(entry)
        # Push a todos los clientes SSE conectados
        dead = []
        with _SSE_LOCK:
            for q in _SSE_QUEUES:
                try:
                    q.put_nowait(entry)
                except queue.Full:
                    dead.append(q)
            for q in dead:
                _SSE_QUEUES.remove(q)

    def format(self, record):
        return _FMT_CONSOLE.format(record)


# ── Handler: consola (solo módulo insumos) ────────────────────────────────────
class _ConsoleHandler(logging.StreamHandler):
    def emit(self, record: logging.LogRecord):
        if record.name.startswith("insumos"):
            super().emit(record)


# ── Silenciar loggers externos ────────────────────────────────────────────────
for _ext in ("uvicorn", "uvicorn.error", "uvicorn.access",
             "fastapi", "multipart", "httpx"):
    logging.getLogger(_ext).setLevel(logging.WARNING)
    logging.getLogger(_ext).propagate = False

# ── Logger raíz del módulo ────────────────────────────────────────────────────
logger = logging.getLogger("insumos")
logger.setLevel(logging.INFO)
logger.propagate = False

# Consola
_ch = _ConsoleHandler(sys.stdout)
_ch.setFormatter(_FMT_CONSOLE)
logger.addHandler(_ch)

# Buffer + SSE
_bh = _BufHandler()
_bh.setFormatter(_FMT_CONSOLE)
logger.addHandler(_bh)

# Archivo rotante (5 MB × 5 = máx 25 MB en disco)
try:
    _fh = RotatingFileHandler(
        _LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5,
        encoding="utf-8",
    )
    _fh.setFormatter(_FMT_FILE)
    logger.addHandler(_fh)
    # También capturar WARNING+ de uvicorn al archivo (para ver errores de red)
    _uv_log = logging.getLogger("uvicorn.error")
    _uv_log.addHandler(_fh)
except Exception as _e:
    print(f"[WARN] No se pudo crear log en disco: {_e}")


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


# ── Logs endpoints ────────────────────────────────────────────────────────────

@app.get("/api/logs", tags=["System"])
def get_logs(
    limit: int  = Query(500, description="Últimas N entradas del buffer"),
    level: str  = Query("",  description="Filtrar por nivel: INFO/WARNING/ERROR"),
    q:     str  = Query("",  description="Buscar texto en el mensaje"),
):
    """Buffer en memoria — últimas 1000 entradas, filtrable."""
    rows = list(_LOG_BUFFER)
    if level:
        rows = [r for r in rows if r["level"] == level.upper()]
    if q:
        ql = q.lower()
        rows = [r for r in rows if ql in r["msg"].lower()]
    return rows[-limit:]


@app.get("/api/logs/stream", tags=["System"])
def logs_stream():
    """
    SSE — push en tiempo real de cada log nuevo.
    El navegador mantiene la conexión abierta; cada línea llega al instante.
    """
    q: queue.Queue = queue.Queue(maxsize=500)
    with _SSE_LOCK:
        _SSE_QUEUES.append(q)

    # Enviar las últimas 50 entradas del buffer como "histórico inicial"
    recent = list(_LOG_BUFFER)[-50:]

    def _stream():
        try:
            # Primero el histórico reciente (para que el cliente tenga contexto)
            for entry in recent:
                yield f"data: {json.dumps(entry, ensure_ascii=False)}\n\n"
            # Luego el streaming en tiempo real
            while True:
                try:
                    entry = q.get(timeout=25)
                    yield f"data: {json.dumps(entry, ensure_ascii=False)}\n\n"
                except queue.Empty:
                    # Heartbeat cada 25s para mantener la conexión viva
                    yield ": heartbeat\n\n"
        except GeneratorExit:
            pass
        finally:
            with _SSE_LOCK:
                if q in _SSE_QUEUES:
                    _SSE_QUEUES.remove(q)

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/logs/file", tags=["System"])
def logs_download(archivo: str = Query("insumos.log")):
    """Descarga el archivo de log del disco (log actual o rotados .log.1, .log.2…)."""
    # Solo permitir nombres seguros dentro de _LOGS_DIR
    safe = Path(archivo).name
    path = _LOGS_DIR / safe
    if not path.exists():
        # Si piden el principal y no existe aún, devolver buffer como texto
        content = "\n".join(
            f"{r['ts_iso']} | {r['level']:<8} | {r['msg']}"
            for r in _LOG_BUFFER
        )
        return StreamingResponse(
            iter([content]),
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{safe}"'},
        )
    return FileResponse(
        str(path),
        media_type="text/plain; charset=utf-8",
        filename=safe,
        headers={"Content-Disposition": f'attachment; filename="{safe}"'},
    )


@app.get("/api/logs/archivos", tags=["System"])
def logs_archivos():
    """Lista todos los archivos de log disponibles en disco."""
    archivos = []
    for f in sorted(_LOGS_DIR.glob("insumos.log*")):
        stat = f.stat()
        archivos.append({
            "nombre":    f.name,
            "bytes":     stat.st_size,
            "kb":        round(stat.st_size / 1024, 1),
            "modificado": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        })
    return {"dir": str(_LOGS_DIR), "archivos": archivos}


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
                        f"  [{_fecha}] {proveedor}: {len(df):,} filas -> pkl + excel OK"
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
    reload = bool(cfg.get("reload", False))

    print()
    print("=" * 54)
    print("  MVALORACION -- Insumos")
    print(f"  URL   ->  http://localhost:{port}")
    print(f"  API   ->  http://localhost:{port}/api/docs")
    print(f"  Logs  ->  {_LOG_FILE}")
    print("=" * 54)
    print()

    def _delayed_convert():
        time.sleep(2)
        _auto_convertir()

    threading.Thread(target=_delayed_convert, daemon=True).start()

    logger.info(f"Servidor iniciando en http://{host}:{port}  |  logs -> {_LOG_FILE}")
    uvicorn.run("main:app", host=host, port=port, reload=reload,
                log_level="warning")
