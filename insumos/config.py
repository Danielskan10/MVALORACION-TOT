#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Configuración del módulo Insumos.
Todo el almacenamiento (PKL + XLSX) vive DENTRO de infovalmer_dir/FECHA/.
No existe carpeta data_dir separada.
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
    # Carpeta base de Infovalmer — subcarpetas YYYYMMDD con los archivos fuente
    # Estructura resultante por fecha:
    #   infovalmer_dir/FECHA/          ← archivos crudos (SP*.001, MX*.txt, …)
    #   infovalmer_dir/FECHA/pkl/      ← cache rápido .pkl por proveedor
    #   infovalmer_dir/FECHA/excel/    ← archivos .xlsx exportados
    "infovalmer_dir": r"J:\VALORACION\VALORACION_ESPECIAL\Bolsa\INFOVALMER",
    # Umbral de variación de precio para alertas (%)
    "umbral_variacion_pct": 3.0,
    # Servidor
    "host":   "0.0.0.0",
    "port":   8001,
    "reload": False,
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
