#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Configuración local del módulo Insumos.
Lee y escribe config.yaml en la misma carpeta del módulo.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

import yaml

logger = logging.getLogger("insumos.config")

_MODULE_DIR  = Path(__file__).parent
_CONFIG_FILE = _MODULE_DIR / "config.yaml"

_DEFAULTS: Dict[str, Any] = {
    # Directorio donde se guardan los .pkl / .xlsx procesados
    "data_dir":       str(_MODULE_DIR / "data"),
    # Carpeta base de Infovalmer (subcarpetas YYYYMMDD)
    "infovalmer_dir": r"J:\VALORACION\VALORACION_ESPECIAL\Bolsa\INFOVALMER",
    # Umbrales de alerta
    "umbral_variacion_pct": 0.5,
    # Servidor
    "host":   "0.0.0.0",
    "port":   8001,
    "reload": True,
    # Proxies / SSL (opcional)
    "proxy":      "",
    "ssl_verify": True,
}


def _load() -> Dict[str, Any]:
    if _CONFIG_FILE.exists():
        try:
            with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            return {**_DEFAULTS, **data}
        except Exception as e:
            logger.warning(f"Error leyendo config.yaml: {e}")
    return dict(_DEFAULTS)


def _save(cfg: Dict[str, Any]) -> None:
    with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)


def get_config() -> Dict[str, Any]:
    return _load()


def update_config(updates: Dict[str, Any]) -> Dict[str, Any]:
    cfg = _load()
    cfg.update(updates)
    _save(cfg)
    return cfg


def get_data_dir() -> Path:
    cfg = _load()
    p = Path(cfg.get("data_dir", _DEFAULTS["data_dir"]))
    p.mkdir(parents=True, exist_ok=True)
    return p
