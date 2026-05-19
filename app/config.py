#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

import yaml

logger = logging.getLogger("config")

_ROOT = Path(__file__).parent.parent
_CONFIG_FILE = _ROOT / "config.yaml"

_DEFAULTS: Dict[str, Any] = {
    "data_dir": str(_ROOT / "data"),
    "umbral_variacion_pct": 5.0,
    "umbral_dif_causacion": 1.0,
    "port": 8000,
    # Archivos de referencia
    "ref_especies":    str(_ROOT / "data" / "Especies.csv"),
    "ref_fcpe":        str(_ROOT / "data" / "FCPE.xlsx"),
    "ref_fiduciaria":  str(_ROOT / "data" / "FIDUCIARIA0210.xlsx"),
    "ref_fondos":      str(_ROOT / "data" / "FONDOS.xlsx"),
    "ref_fcp":         str(_ROOT / "data" / "FCP.xlsx"),
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
