#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Configuración local del módulo Mitra."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

import yaml

logger = logging.getLogger("mitra.config")

_MODULE_DIR  = Path(__file__).parent
_CONFIG_FILE = _MODULE_DIR / "config.yaml"

_DEFAULTS: Dict[str, Any] = {
    "data_dir":              str(_MODULE_DIR / "data"),
    "umbral_variacion_pct":  5.0,
    "umbral_dif_causacion":  1.0,
    "host":   "0.0.0.0",
    "port":   8003,
    "reload": True,
    "proxy":  "",
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
