#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROUTER INSUMOS
Proveedores de precios: SP/SW/TP/SV (Infovalmer J:), MX, MX_RV, NOTAS, SB, monedas.

Optimizaciones:
  - Cache pkl por proveedor/fecha (leer en ~5ms vs segundos)
  - Conversión paralela con ThreadPoolExecutor
  - Búsquedas vectorizadas (no apply axis=1)
  - Endpoint /historico/{isin} dedicado (evita N llamadas en loop desde JS)
  - Endpoint /sp_curvas para scatter TIR vs Plazo (renta fija)
  - Endpoint /alertas_multidia para comparar vs N fechas anteriores
"""
from __future__ import annotations

import re
import time
import logging
import threading
import concurrent.futures
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

import pandas as pd
import numpy as np
from fastapi import APIRouter, Query, HTTPException
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_config

logger = logging.getLogger("insumos")
router = APIRouter()

_ROOT = Path(__file__).parent.parent.parent

# ── Caché en memoria (TTL=600s) ───────────────────────────────────────────────
_MEM_CACHE: Dict[str, Tuple[float, Any]] = {}   # key → (ts, valor)
_MEM_LOCK  = threading.Lock()
_MEM_TTL   = 600   # 10 minutos

def _mem_get(key: str) -> Any:
    with _MEM_LOCK:
        entry = _MEM_CACHE.get(key)
        if entry and (time.time() - entry[0]) < _MEM_TTL:
            return entry[1]
    return None

def _mem_set(key: str, val: Any):
    with _MEM_LOCK:
        _MEM_CACHE[key] = (time.time(), val)

def _mem_invalidate(prefix: str = ""):
    """Invalida entradas cuya clave empiece con prefix (vacía todo si prefix='')."""
    with _MEM_LOCK:
        keys = [k for k in _MEM_CACHE if k.startswith(prefix)]
        for k in keys:
            del _MEM_CACHE[k]


# ═══════════════════════════════════════════════════════════════════════════════
# UTILIDADES BASE
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_num(s) -> Optional[float]:
    try:
        return float(str(s).strip().replace("\xa0", "").replace(" ", "").replace(",", "."))
    except Exception:
        return None


def _fecha_valida(nombre: str) -> bool:
    if not re.fullmatch(r"\d{8}", str(nombre)):
        return False
    try:
        dt = datetime.strptime(str(nombre), "%Y%m%d")
        return 2020 <= dt.year <= 2035
    except ValueError:
        return False


def _sufijo_fecha(fecha_str: str) -> str:
    """20260514 → 051426 (MMDDYY)"""
    return datetime.strptime(fecha_str, "%Y%m%d").strftime("%m%d%y")


# ═══════════════════════════════════════════════════════════════════════════════
# INFOVALMER J: DRIVE
# ═══════════════════════════════════════════════════════════════════════════════

def _get_bases() -> List[Path]:
    """
    Devuelve las carpetas raíz donde buscar fechas, en orden de prioridad:
      1. infovalmer_dir (configurado o default J:)
      2. data_dir legacy (si existe): ruta del módulo/../data  o data_dir en config
    Filtra las que no existen.
    """
    cfg = get_config()
    candidates = []
    # infovalmer configurado
    inf = cfg.get("infovalmer_dir", "")
    if inf:
        candidates.append(Path(inf))
    # default J: drive
    candidates.append(Path(r"J:\VALORACION\VALORACION_ESPECIAL\Bolsa\INFOVALMER"))
    # data_dir legacy junto al repo
    module_dir = Path(__file__).parent
    candidates.append(module_dir.parent / "data")
    candidates.append(module_dir / "data")
    # devolver solo existentes, sin duplicados
    seen, result = set(), []
    for p in candidates:
        k = str(p).lower()
        if k not in seen and p.exists():
            seen.add(k)
            result.append(p)
    return result


def _get_infovalmer_base() -> Path:
    """Primera base disponible (para compatibilidad)."""
    bases = _get_bases()
    return bases[0] if bases else Path(r"J:\VALORACION\VALORACION_ESPECIAL\Bolsa\INFOVALMER")


def _fecha_dir(fecha: str) -> Optional[Path]:
    """Devuelve la carpeta del día buscando en todas las bases."""
    for base in _get_bases():
        d = base / fecha
        if d.exists():
            return d
    return None


def _pkl_dir(fecha: str) -> Path:
    """PKL dentro de la carpeta del día (se crea si no existe)."""
    d = _fecha_dir(fecha)
    if d is None:
        # fallback: crear en la primera base
        bases = _get_bases()
        d = bases[0] / fecha if bases else Path(fecha)
    pkl = d / "pkl"
    pkl.mkdir(parents=True, exist_ok=True)
    return pkl


def _excel_dir(fecha: str) -> Path:
    """Excel dentro de la carpeta del día (se crea si no existe)."""
    d = _fecha_dir(fecha)
    if d is None:
        bases = _get_bases()
        d = bases[0] / fecha if bases else Path(fecha)
    exc = d / "excel"
    exc.mkdir(parents=True, exist_ok=True)
    return exc


def _infovalmer_dir(fecha: str) -> Path:
    """Alias de _fecha_dir para compatibilidad con main.py."""
    return _fecha_dir(fecha) or (_get_infovalmer_base() / fecha)


def _cache_path(fecha: str, proveedor: str) -> Path:
    return _pkl_dir(fecha) / f"{proveedor}_{fecha}.pkl"


def _excel_path(fecha: str, proveedor: str) -> Path:
    return _excel_dir(fecha) / f"{proveedor}_{fecha}.xlsx"


def _dir_tiene_insumos(d: Path, fecha: str) -> bool:
    """True si la carpeta tiene archivos fuente conocidos O pkls ya convertidos."""
    try:
        sf = datetime.strptime(fecha, "%Y%m%d").strftime("%m%d%y")
    except ValueError:
        return False
    fuentes = (
        f"SP{sf}.001", f"SW{sf}.001", f"SV{sf}.001", f"SB{sf}.001",
        f"MX{sf}.txt", f"MX{sf}_RV.txt",
        f"NOTAS_ESTRUCTURADAS_{fecha}.csv",
        f"titulos_participativos_valoracion_{fecha}.txt",
        f"monedas_matriz_info_{fecha}.csv",
        f"eurofxref{fecha}.csv",
        f"Matriz_TC_{fecha}.csv",
    )
    tiene_fuente = any((d / n).is_file() for n in fuentes)
    pkl_d = d / "pkl"
    tiene_pkl = pkl_d.is_dir() and any(pkl_d.glob("*.pkl"))
    return tiene_fuente or tiene_pkl


def _find_file(fecha: str, patterns: List[str]) -> Optional[Path]:
    """Busca archivo fuente en la carpeta del día (todas las bases)."""
    d = _fecha_dir(fecha)
    if d is None or not d.exists():
        return None
    for f in sorted(d.iterdir()):
        if not f.is_file():
            continue
        for pat in patterns:
            if re.search(pat, f.name, re.IGNORECASE):
                return f
    return None


def _read_csv_auto(path: Path, **kwargs) -> pd.DataFrame:
    for sep in [";", ",", "\t", "|"]:
        try:
            df = pd.read_csv(path, sep=sep, dtype=str, encoding="latin-1",
                             on_bad_lines="skip", **kwargs)
            if len(df.columns) > 1:
                df.columns = df.columns.str.strip()
                return df
        except Exception:
            continue
    return pd.DataFrame()


# ═══════════════════════════════════════════════════════════════════════════════
# FECHAS DISPONIBLES
# ═══════════════════════════════════════════════════════════════════════════════

def _fechas_disponibles() -> List[str]:
    """Escanea TODAS las bases configuradas buscando subcarpetas YYYYMMDD con datos."""
    fechas: set = set()
    for base in _get_bases():
        if not base.exists():
            continue
        for d in base.iterdir():
            if d.is_dir() and _fecha_valida(d.name) and _dir_tiene_insumos(d, d.name):
                fechas.add(d.name)
    return sorted(fechas)


# ═══════════════════════════════════════════════════════════════════════════════
# CACHE LOCAL
# ═══════════════════════════════════════════════════════════════════════════════

CACHE_PROVEEDORES = ("SP", "SW", "TP", "SV", "MX", "MX_RV", "NOTAS", "SB", "MONEDAS")


def _leer_cache(fecha: str, proveedor: str) -> Optional[pd.DataFrame]:
    path = _cache_path(fecha, proveedor)
    if not path.exists():
        return None
    try:
        return pd.read_pickle(path)
    except Exception as e:
        logger.warning(f"PKL corrupto {path}: {e}")
        path.unlink(missing_ok=True)
        return None


def _guardar_cache(fecha: str, proveedor: str, df: pd.DataFrame,
                   export_excel: bool = True) -> Dict[str, Any]:
    """
    Guarda PKL en infovalmer/FECHA/pkl/
    Si export_excel=True, guarda XLSX (o CSV para archivos grandes) en infovalmer/FECHA/excel/

    Estrategia por tamaño:
      - <= 50K filas   → XLSX con xlsxwriter (rápido)
      - > 50K filas    → CSV (2-3s) + XLSX en hilo background (no bloquea)
    """
    pkl = _cache_path(fecha, proveedor)
    df.to_pickle(pkl)

    xlsx_path = None
    csv_path  = None
    excel_ok  = False

    if export_excel and not df.empty:
        xlsx_path = _excel_path(fecha, proveedor)
        n = len(df)

        if n <= 50_000:
            # Archivo chico → XLSX directo con xlsxwriter (si disponible) u openpyxl
            try:
                try:
                    df.to_excel(xlsx_path, index=False, engine="xlsxwriter")
                except ImportError:
                    df.to_excel(xlsx_path, index=False, engine="openpyxl")
                excel_ok = True
            except Exception as e:
                logger.warning(f"Excel fallo {xlsx_path}: {e}")
        else:
            # Archivo grande (SP) → CSV inmediato + XLSX en background
            csv_path = xlsx_path.with_suffix(".csv")
            try:
                df.to_csv(csv_path, index=False)
                logger.info(f"[{fecha}] {proveedor}: CSV guardado ({n:,} filas) en {csv_path.name}")
                # XLSX en hilo background (no bloquea la conversión de otros proveedores)
                def _bg_excel(_df=df.copy(), _path=xlsx_path, _prov=proveedor, _fecha=fecha):
                    try:
                        try:
                            _df.to_excel(_path, index=False, engine="xlsxwriter")
                        except ImportError:
                            _df.to_excel(_path, index=False, engine="openpyxl")
                        logger.info(f"[{_fecha}] {_prov}: Excel listo en background -> {_path.name}")
                    except Exception as _e:
                        logger.warning(f"[{_fecha}] {_prov}: Excel background fallo: {_e}")
                import threading
                threading.Thread(target=_bg_excel, daemon=True).start()
                # Reportar como xlsx_path (se generará en background)
                excel_ok = True
            except Exception as e:
                logger.warning(f"CSV fallo {csv_path}: {e}")

    return {
        "proveedor": proveedor,
        "filas":     int(len(df)),
        "pkl":       str(pkl),
        "xlsx":      str(xlsx_path) if excel_ok else None,
        "csv":       str(csv_path)  if csv_path and csv_path.exists() else None,
        "cache_ok":  True,
    }


def _cache_status(fecha: str) -> Dict[str, Any]:
    """Estado completo de PKL + Excel para la fecha dada."""
    detalle = {}
    total_pkl = 0
    total_xlsx = 0
    dia = _infovalmer_dir(fecha)
    for proveedor in CACHE_PROVEEDORES:
        pkl  = _cache_path(fecha, proveedor)
        xlsx = _excel_path(fecha, proveedor)
        ok_pkl  = pkl.exists()
        ok_xlsx = xlsx.exists()
        total_pkl  += int(ok_pkl)
        total_xlsx += int(ok_xlsx)
        detalle[proveedor] = {
            "pkl":        ok_pkl,
            "xlsx":       ok_xlsx,
            "pkl_path":   str(pkl),
            "xlsx_path":  str(xlsx),
        }
    return {
        "fecha":        fecha,
        "infovalmer":   str(dia),
        "pkl_dir":      str(dia / "pkl"),
        "excel_dir":    str(dia / "excel"),
        "total":        len(CACHE_PROVEEDORES),
        "pkl_ok":       total_pkl,
        "xlsx_ok":      total_xlsx,
        "completo":     total_pkl == len(CACHE_PROVEEDORES),
        "proveedores":  detalle,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# PARSERS DE ARCHIVOS INFOVALMER
# ═══════════════════════════════════════════════════════════════════════════════

def cargar_sp(fecha: str, use_cache: bool = True,
              progress_cb=None) -> pd.DataFrame:
    """SP = BVC Renta Fija local (fixed-width .001).
    Layout completo (legacy Revisiones_Valoracion_V2021):
      [0:7]    Numero_Secuencia
      [7:8]    Tipo_Registro
      [8:20]   NEMO
      [20:32]  ISIN
      [32:50]  Numero_Emision
      [50:51]  Estado
      [51:59]  Fecha_Emision  (YYYYMMDD)
      [59:67]  Fecha_Vcto     (YYYYMMDD)
      [67:75]  Fecha_Ult_Precio
      [75:76]  Periodicidad
      [76:77]  Modalidad
      [77:81]  Dias_Vcto / Plazo
      [81:84]  Base_Calculo
      [84:85]  Tipo_Tasa
      [85:89]  Moneda
      [89:105] P_SUCIO  (Precio_Valor_Calculado)
      [105:109] Tipo_Calculo
      [109:110] Base
      [110:129] P_LIMPIO
      [129:137] Fecha_Ult
      [137:156] Rendimiento / TIR alternativo
      [156:168] Codigo_ISIN2
      [168:187] TIR
    Optimizaciones:
      - Loop Python con buffer (más rápido que read_fwf para archivos 50MB+)
      - Progreso cada 50K lineas via progress_cb
      - Para >50K filas: CSV inmediato + Excel en background
    """
    if use_cache:
        cached = _leer_cache(fecha, "SP")
        if cached is not None:
            return cached
    sf = _sufijo_fecha(fecha)
    path = _infovalmer_dir(fecha) / f"SP{sf}.001"
    if not path.exists():
        return pd.DataFrame()

    # Tamaño para estimar progreso
    try:
        file_size = path.stat().st_size
    except Exception:
        file_size = 0

    if progress_cb:
        sz_mb = file_size / 1024 / 1024
        progress_cb({"paso": "SP", "msg": f"Leyendo {sz_mb:.1f} MB...", "pct": 3})

    try:
        filas   = []
        n_total = 0
        n_ok    = 0
        CHUNK   = 50_000   # reportar progreso cada X líneas

        with open(path, "r", encoding="latin-1", errors="ignore", buffering=1<<20) as fh:
            for ln in fh:
                n_total += 1
                # Reporte de progreso cada 50K líneas
                if progress_cb and n_total % CHUNK == 0:
                    # Estimar % basado en bytes leídos (aproximado)
                    pct_est = min(int(n_total * 187 / max(file_size, 1) * 80) + 3, 80)
                    progress_cb({
                        "paso": "SP",
                        "msg":  f"Leyendo... {n_total:,} lineas ({n_ok:,} validas)",
                        "pct":  pct_est,
                    })

                if len(ln) < 107 or ln[51:53] != "20":
                    continue

                # Extraer precio
                p_sucio_s  = ln[89:105].strip()
                p_limpio_s = ln[110:129].strip() if len(ln) >= 129 else ""
                try:
                    p_sucio = float(p_sucio_s.replace(",", ".")) if p_sucio_s else None
                except ValueError:
                    p_sucio = None
                try:
                    p_limpio = float(p_limpio_s.replace(",", ".")) if p_limpio_s else None
                except ValueError:
                    p_limpio = None

                precio = p_sucio if p_sucio is not None else p_limpio
                if precio is None:
                    continue

                try:
                    tir = float(ln[168:187].strip().replace(",", ".")) if len(ln) >= 187 else None
                except ValueError:
                    tir = None

                plazo_raw = ln[77:81].strip()
                isin = ln[20:32].strip().upper()
                nemo = ln[8:20].strip().upper()

                filas.append((
                    nemo, isin,
                    ln[51:59].strip(),   # Emision
                    ln[59:67].strip(),   # Vcto
                    ln[84:85].strip(),   # Tipo_Tasa (col 84:85, no 75:77)
                    int(plazo_raw) if plazo_raw.isdigit() else None,
                    ln[81:84].strip(),   # Base
                    ln[85:89].strip(),   # Moneda
                    p_sucio, p_limpio, tir, precio,
                    isin if isin else nemo,  # ID
                ))
                n_ok += 1

        if progress_cb:
            progress_cb({"paso": "SP", "msg": f"{n_ok:,} titulos validos — guardando cache...", "pct": 85})

        if not filas:
            return pd.DataFrame()

        df = pd.DataFrame(filas, columns=[
            "NEMO","ISIN","Emision","Vcto","Tipo_Tasa","Plazo",
            "Base","Moneda","P_SUCIO","P_LIMPIO","TIR","PRECIO","ID",
        ])
        df["FUENTE"] = "SP"

        logger.info(f"SP {fecha}: {len(df):,} titulos de {n_total:,} lineas")
        _guardar_cache(fecha, "SP", df)

        if progress_cb:
            progress_cb({"paso": "SP", "msg": f"OK — {len(df):,} titulos (Excel en background)", "pct": 100})

        return df

    except Exception as e:
        logger.error(f"Error cargando SP: {e}", exc_info=True)
        return pd.DataFrame()


def cargar_sw(fecha: str, use_cache: bool = True) -> pd.DataFrame:
    """SW = Precios secundarios/swap (.001)."""
    if use_cache:
        cached = _leer_cache(fecha, "SW")
        if cached is not None:
            return cached
    sf = _sufijo_fecha(fecha)
    path = _infovalmer_dir(fecha) / f"SW{sf}.001"
    if not path.exists():
        return pd.DataFrame()
    patron = re.compile(
        r"^(?P<sec>\d+)(?P<tipo>[A-Z])(?P<nemo>[A-Z0-9\-]+)\s+"
        r"(?P<fecha>\d{4}-\d{2}-\d{2})(?P<valor>.*)$"
    )
    filas = []
    try:
        with open(path, "r", encoding="latin-1", errors="ignore") as fh:
            for ln in fh:
                m = patron.match(ln.strip())
                if not m:
                    continue
                nums = re.findall(r"[-+]?\d[\d,.]*", m.group("valor"))
                precio = _parse_num(nums[-1]) if nums else None
                if precio is None:
                    continue
                nemo = m.group("nemo").strip().upper()
                filas.append({
                    "NEMO":           nemo,
                    "Tipo_Registro":  m.group("tipo"),
                    "ISIN":           "",
                    "PRECIO":         precio,
                    "ID":             nemo,
                    "FUENTE":         "SW",
                })
    except Exception as e:
        logger.error(f"Error cargando SW: {e}")
        return pd.DataFrame()
    df = pd.DataFrame(filas)
    _guardar_cache(fecha, "SW", df)
    return df


def cargar_tp(fecha: str, use_cache: bool = True) -> pd.DataFrame:
    """TP = Títulos participativos (fixed-width .txt)."""
    if use_cache:
        cached = _leer_cache(fecha, "TP")
        if cached is not None:
            return cached
    path = _infovalmer_dir(fecha) / f"titulos_participativos_valoracion_{fecha}.txt"
    if not path.exists():
        return pd.DataFrame()
    filas = []
    try:
        with open(path, "r", encoding="latin-1", errors="ignore") as fh:
            for ln in fh:
                ln = ln.rstrip("\n")
                if len(ln) < 29:
                    continue
                precio = _parse_num(ln[29:].strip())
                if precio is None:
                    continue
                isin = ln[6:19].strip().upper()
                cod  = ln[0:6].strip().upper()
                filas.append({
                    "Codigo": cod,
                    "Fecha":  ln[19:29].strip(),
                    "ISIN":   isin,
                    "PRECIO": precio,
                    "ID":     isin if isin else cod,
                    "FUENTE": "TP",
                })
    except Exception as e:
        logger.error(f"Error cargando TP: {e}")
        return pd.DataFrame()
    df = pd.DataFrame(filas)
    _guardar_cache(fecha, "TP", df)
    return df


def cargar_sv(fecha: str, use_cache: bool = True) -> pd.DataFrame:
    """SV = Tasas de interés de referencia (SV{MMDDYY}.001).
      [0:5]  Codigo
      [5:6]  Tipo
      [6:14] Fecha
      [14:18] Plazo
      [18:33] Tasa
    """
    if use_cache:
        cached = _leer_cache(fecha, "SV")
        if cached is not None:
            return cached
    sf = _sufijo_fecha(fecha)
    path = _infovalmer_dir(fecha) / f"SV{sf}.001"
    if not path.exists():
        return pd.DataFrame()
    filas = []
    try:
        with open(path, "r", encoding="latin-1", errors="ignore") as fh:
            for ln in fh:
                ln = ln.rstrip("\n")
                if len(ln) < 18 or not ln[6:8].startswith("20"):
                    continue
                tasa = _parse_num(ln[18:33]) if len(ln) >= 33 else None
                plazo_raw = ln[14:18].strip()
                filas.append({
                    "Codigo": ln[0:5].strip(),
                    "Tipo":   ln[5:6].strip(),
                    "Fecha":  ln[6:14].strip(),
                    "Plazo":  int(plazo_raw) if plazo_raw.isdigit() else plazo_raw,
                    "Tasa":   tasa,
                    "ID":     ln[0:5].strip(),
                    "PRECIO": tasa,
                    "FUENTE": "SV",
                })
    except Exception as e:
        logger.error(f"Error cargando SV: {e}")
        return pd.DataFrame()
    df = pd.DataFrame(filas)
    _guardar_cache(fecha, "SV", df)
    return df


def cargar_mx(fecha: str, use_cache: bool = True) -> pd.DataFrame:
    """MX = Renta fija internacional (Infovalmer MX{MMDDYY}.txt)."""
    if use_cache:
        cached = _leer_cache(fecha, "MX")
        if cached is not None:
            return cached
    path = _find_file(fecha, [r"^MX\d{6}\.txt$", r"^MX_\d{8}"])
    if not path:
        return pd.DataFrame()
    try:
        df = pd.read_csv(path, sep=None, engine="python", dtype=str,
                         encoding="latin-1", on_bad_lines="skip")
        df.columns = df.columns.str.strip()
        if "Fecha Valoracion" in df.columns:
            df = df[df["Fecha Valoracion"].str.match(r"\d{4}/\d{2}/\d{2}", na=False)]
        df["FUENTE"] = "MX"
        df["ID"] = df.get("ISIN", pd.Series(dtype=str)).str.strip()
        precio_col = next(
            (c for c in ["Precio Sucio", "Precio Limpio", "Precio"] if c in df.columns), None
        )
        df["PRECIO"] = pd.to_numeric(
            df[precio_col].str.replace(",", ".") if precio_col else pd.Series(dtype=str),
            errors="coerce",
        )
        _guardar_cache(fecha, "MX", df)
        return df
    except Exception as e:
        logger.error(f"Error cargando MX: {e}")
        return pd.DataFrame()


def cargar_mx_rv(fecha: str, use_cache: bool = True) -> pd.DataFrame:
    """MX_RV = Renta variable internacional (ETFs, ADRs)."""
    if use_cache:
        cached = _leer_cache(fecha, "MX_RV")
        if cached is not None:
            return cached
    path = _find_file(fecha, [r"^MX\d{6}_RV\.txt$", r"MX.*RV"])
    if not path:
        return pd.DataFrame()
    try:
        df = pd.read_csv(path, sep=None, engine="python", dtype=str,
                         encoding="latin-1", on_bad_lines="skip")
        df.columns = df.columns.str.strip()
        if "Fecha Valoracion" in df.columns:
            df = df[df["Fecha Valoracion"].str.match(r"\d{4}/\d{2}/\d{2}", na=False)]
        df["FUENTE"] = "MX_RV"
        df["ID"] = df.get("ISIN", pd.Series(dtype=str)).str.strip()
        df["PRECIO"] = pd.to_numeric(
            df.get("Precio", pd.Series()).str.replace(",", "."), errors="coerce"
        )
        _guardar_cache(fecha, "MX_RV", df)
        return df
    except Exception as e:
        logger.error(f"Error cargando MX_RV: {e}")
        return pd.DataFrame()


def cargar_notas(fecha: str, use_cache: bool = True) -> pd.DataFrame:
    """NOTAS estructuradas."""
    if use_cache:
        cached = _leer_cache(fecha, "NOTAS")
        if cached is not None:
            return cached
    path = _find_file(fecha, [r"NOTAS_ESTRUCTURADAS.*\.csv", r"NOTAS.*\.csv"])
    if not path:
        return pd.DataFrame()
    try:
        df = pd.read_csv(path, sep=None, engine="python", dtype=str,
                         encoding="latin-1", on_bad_lines="skip")
        df.columns = df.columns.str.strip()
        if "Fecha Valoracion" in df.columns:
            df = df[df["Fecha Valoracion"].str.match(r"\d{4}/\d{2}/\d{2}", na=False)]
        df["FUENTE"] = "NOTAS"
        df["ID"] = df.get("ISIN", pd.Series(dtype=str)).str.strip()
        precio_col = next(
            (c for c in ["Precio Sucio", "Precio Limpio"] if c in df.columns), None
        )
        df["PRECIO"] = pd.to_numeric(
            df[precio_col].str.replace(",", ".") if precio_col else pd.Series(dtype=str),
            errors="coerce",
        )
        _guardar_cache(fecha, "NOTAS", df)
        return df
    except Exception as e:
        logger.error(f"Error cargando NOTAS: {e}")
        return pd.DataFrame()


def cargar_sb(fecha: str, use_cache: bool = True) -> pd.DataFrame:
    """SB = Betas y curvas de descuento (SB{MMDDYY}.001)."""
    if use_cache:
        cached = _leer_cache(fecha, "SB")
        if cached is not None:
            return cached
    path = _find_file(fecha, [r"^SB\d{6}\.001$"])
    if not path:
        return pd.DataFrame()
    filas = []
    try:
        with open(path, "r", encoding="latin-1", errors="ignore") as fh:
            for ln in fh:
                ln = ln.rstrip("\n")
                if len(ln) > 20 and ln[5:6] == "D":
                    try:
                        filas.append({
                            "ID":     ln[14:20].strip(),
                            "CURVA":  ln[14:20].strip(),
                            "TASA_1": ln[20:31].strip(),
                            "TASA_2": ln[31:42].strip(),
                            "TASA_3": ln[42:53].strip(),
                            "TASA_4": ln[53:64].strip(),
                            "FUENTE": "SB",
                        })
                    except Exception:
                        continue
        df = pd.DataFrame(filas)
        if not df.empty:
            df["PRECIO"] = pd.to_numeric(df["TASA_1"], errors="coerce")
        _guardar_cache(fecha, "SB", df)
        return df
    except Exception as e:
        logger.error(f"Error cargando SB: {e}")
        return pd.DataFrame()


def cargar_monedas(fecha: str, use_cache: bool = True) -> pd.DataFrame:
    """Tasas de cambio del día (monedas_matriz_info_{fecha}.csv)."""
    if use_cache:
        cached = _leer_cache(fecha, "MONEDAS")
        if cached is not None:
            return cached
    path = _find_file(fecha, [r"monedas_matriz_info.*\.csv"])
    if not path:
        path = _find_file(fecha, [r"eurofxref.*\.csv"])
    if not path:
        return pd.DataFrame()
    try:
        with open(path, "r", encoding="latin-1") as fh:
            lines = fh.readlines()
        filas = []
        for ln in lines:
            parts = re.split(r"[;,]", ln.strip())
            if len(parts) >= 2 and parts[0].strip():
                moneda = parts[0].strip()
                tasa = None
                for p in reversed(parts):
                    try:
                        tasa = float(p.replace(",", ".").strip())
                        break
                    except Exception:
                        continue
                if tasa and tasa > 0:
                    filas.append({"MONEDA": moneda, "TASA_COP": tasa, "FUENTE": "TC"})
        df = pd.DataFrame(filas)
        _guardar_cache(fecha, "MONEDAS", df)
        return df
    except Exception as e:
        logger.error(f"Error cargando monedas: {e}")
        return pd.DataFrame()


# Registro de cargadores
CARGADORES: Dict[str, Any] = {
    "SP":    cargar_sp,
    "SW":    cargar_sw,
    "TP":    cargar_tp,
    "SV":    cargar_sv,
    "MX":    cargar_mx,
    "MX_RV": cargar_mx_rv,
    "NOTAS": cargar_notas,
    "SB":    cargar_sb,
}


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS DE BÚSQUEDA VECTORIZADA
# ═══════════════════════════════════════════════════════════════════════════════

def _buscar_df(df: pd.DataFrame, q: str) -> pd.DataFrame:
    """Búsqueda vectorizada: busca q en todas las columnas string."""
    if not q or df.empty:
        return df
    q_up = q.upper()
    mask = pd.Series(False, index=df.index)
    for col in df.select_dtypes(include="object").columns:
        mask |= df[col].str.upper().str.contains(q_up, na=False, regex=False)
    return df[mask]


def _df_to_records(df: pd.DataFrame, limit: int = 1000) -> List[Dict]:
    """
    Convierte DataFrame a lista de dicts JSON-safe.
    Convierte NaN/inf (numérico o float mezclado en strings) → None.
    """
    import math
    sub = df.head(limit).copy()
    # Columnas numéricas: NaN -> None
    for col in sub.select_dtypes(include=["float64", "float32", "Float64"]).columns:
        sub[col] = sub[col].where(sub[col].notna(), other=None)
    # Columnas string/object: float('nan') mezclado -> None
    for col in sub.columns:
        if sub[col].dtype.kind in ("O", "U", "S"):  # object, unicode, bytes
            sub[col] = sub[col].apply(
                lambda x: None if (isinstance(x, float) and not math.isfinite(x)) else x
            )
    return sub.to_dict(orient="records")


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS — CACHE / CONVERSIÓN
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/cache/{fecha}")
def estado_cache(fecha: str):
    """Estado de cache PKL + Excel por proveedor para la fecha dada."""
    return _cache_status(fecha)


# ── Estado de progreso de conversión (compartido entre hilos) ────────────────
import queue as _queue
_conv_progress: Dict[str, Any] = {}   # fecha → dict con estado actual
_conv_queues:   Dict[str, "_queue.Queue"] = {}


@router.get("/convertir_progreso/{fecha}")
def convertir_progreso_sse(fecha: str):
    """
    SSE: emite eventos de progreso mientras /convertir/{fecha} está corriendo.
    El frontend se conecta antes de llamar POST /convertir.
    Formato: data: {...JSON...}\\n\\n
    """
    from fastapi.responses import StreamingResponse
    import time, json as _json

    q = _conv_queues.setdefault(fecha, _queue.Queue(maxsize=200))

    def _stream():
        timeout = 120   # máximo 2 minutos esperando
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                msg = q.get(timeout=1.0)
                yield f"data: {_json.dumps(msg, ensure_ascii=False)}\n\n"
                if msg.get("done"):
                    break
            except _queue.Empty:
                yield ": ping\n\n"   # keep-alive
        yield "data: {\"done\":true}\n\n"

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/convertir/{fecha}")
def convertir_insumos(
    fecha: str,
    force: bool = Query(False, description="Reconvertir aunque el PKL ya exista"),
):
    """
    Convierte TODOS los archivos de Infovalmer para la fecha dada.
    Emite progreso en tiempo real por /convertir_progreso/{fecha} (SSE).
    SP usa pd.read_fwf vectorizado (10-20x más rápido que loop).
    """
    import json as _json, time as _time

    # Cola de progreso para SSE
    q = _conv_queues.setdefault(fecha, _queue.Queue(maxsize=200))

    def _emit(msg: Dict):
        """Manda evento de progreso a la cola SSE (no bloquea)."""
        try:
            q.put_nowait(msg)
        except _queue.Full:
            pass
        logger.info(f"[{fecha}] {msg.get('proveedor','?')}: {msg.get('msg','')}")

    LOADERS_ORD = [
        # SP primero porque es el más grande
        ("SP",    cargar_sp),
        ("SW",    cargar_sw),
        ("SV",    cargar_sv),
        ("TP",    cargar_tp),
        ("MX",    cargar_mx),
        ("MX_RV", cargar_mx_rv),
        ("NOTAS", cargar_notas),
        ("SB",    cargar_sb),
        ("MONEDAS", cargar_monedas),
    ]
    total_provs = len(LOADERS_ORD)
    resultados  = []

    for idx, (proveedor, loader) in enumerate(LOADERS_ORD):
        pct_base = int(idx / total_provs * 100)
        pct_next = int((idx + 1) / total_provs * 100)

        pkl  = _cache_path(fecha, proveedor)
        xlsx = _excel_path(fecha, proveedor)

        # ── Ya existe y no se fuerza ──────────────────────────────────
        if pkl.exists() and xlsx.exists() and not force:
            cached = _leer_cache(fecha, proveedor)
            n = int(len(cached)) if cached is not None else 0
            _emit({
                "proveedor": proveedor, "pct": pct_next,
                "msg": f"ya existia ({n:,} filas)", "omitido": True,
                "filas": n, "cache_ok": True,
            })
            resultados.append({
                "proveedor": proveedor, "filas": n,
                "cache_ok": True, "omitido": True,
                "pkl": str(pkl), "xlsx": str(xlsx),
            })
            continue

        # ── Progreso interno para SP (es el más pesado) ───────────────
        def _progress_cb(ev: Dict, _pct_base=pct_base, _pct_next=pct_next, _prov=proveedor):
            frac = ev.get("pct", 0) / 100.0
            pct  = int(_pct_base + frac * (_pct_next - _pct_base))
            _emit({"proveedor": _prov, "pct": pct, "msg": ev.get("msg", ""), "paso": ev.get("paso","")})

        _emit({"proveedor": proveedor, "pct": pct_base, "msg": "Iniciando..."})

        try:
            t0 = _time.time()
            # SP acepta progress_cb; el resto no, pero no falla
            if proveedor == "SP":
                df = loader(fecha, use_cache=False, progress_cb=_progress_cb)
            else:
                df = loader(fecha, use_cache=False)

            dt = round(_time.time() - t0, 1)

            if df.empty:
                _emit({
                    "proveedor": proveedor, "pct": pct_next,
                    "msg": "archivo no encontrado o vacio", "error": True,
                })
                resultados.append({
                    "proveedor": proveedor, "filas": 0,
                    "cache_ok": False, "error": "archivo fuente no encontrado o vacío",
                })
                continue

            _emit({"proveedor": proveedor, "pct": pct_next - 2,
                   "msg": f"{len(df):,} filas — guardando Excel..."})

            res = _guardar_cache(fecha, proveedor, df, export_excel=True)
            res["tiempo_s"] = dt

            _emit({
                "proveedor": proveedor, "pct": pct_next,
                "msg": f"OK — {len(df):,} filas en {dt}s",
                "filas": len(df), "cache_ok": True,
            })
            resultados.append(res)

        except Exception as e:
            logger.exception(f"Error convirtiendo {proveedor} {fecha}")
            _emit({"proveedor": proveedor, "pct": pct_next,
                   "msg": f"ERROR: {e}", "error": True})
            resultados.append({
                "proveedor": proveedor, "filas": 0,
                "cache_ok": False, "error": str(e),
            })

    # ── Señal de fin ──────────────────────────────────────────────────
    ok = all(r.get("cache_ok") for r in resultados)
    _emit({"done": True, "pct": 100,
           "msg": f"Completado: {sum(1 for r in resultados if r.get('cache_ok'))} OK / {total_provs}",
           "ok": ok})

    # Invalidar caché en memoria para esta fecha (datos recién convertidos)
    _mem_invalidate(f"resumen:{fecha}")
    _mem_invalidate(f"alertas:{fecha}:")

    return {
        "ok":         ok,
        "fecha":      fecha,
        "status":     _cache_status(fecha),
        "resultados": resultados,
    }


@router.get("/conectividad")
def verificar_conectividad():
    """
    Verifica si la carpeta Infovalmer configurada es accesible.
    Útil para detectar si la VPN está conectada.
    """
    from config import get_config
    cfg  = get_config()
    inf  = cfg.get("infovalmer_dir", "")
    path = Path(inf) if inf else None

    bases_status = []
    for base in _get_bases():
        fechas_en_base = []
        try:
            for d in base.iterdir():
                if d.is_dir() and _fecha_valida(d.name):
                    fechas_en_base.append(d.name)
        except Exception:
            pass
        bases_status.append({
            "ruta":        str(base),
            "accesible":   base.exists(),
            "es_principal": str(base) == inf,
            "fechas":      sorted(fechas_en_base)[-5:],   # últimas 5
            "n_fechas":    len(fechas_en_base),
        })

    principal_ok = path.exists() if path else False
    return {
        "infovalmer_dir":       inf,
        "principal_accesible":  principal_ok,
        "mensaje":              (
            "Carpeta Infovalmer accesible" if principal_ok
            else ("No configurada" if not inf
                  else "No accesible — verifica VPN o ruta")
        ),
        "bases": bases_status,
        "fechas_disponibles": _fechas_disponibles(),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS — FECHAS / RESUMEN
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/fechas")
def get_fechas():
    return {"fechas": _fechas_disponibles()}


@router.get("/inicio/{fecha}")
def get_inicio(
    fecha: str,
    umbral_pct: float = Query(5.0),
    fecha_ant: Optional[str] = Query(None),
):
    """
    Endpoint de arranque: devuelve fechas + resumen + alertas en una sola llamada.
    Reduce los round-trips al cargar la página de 3 a 1.
    """
    import concurrent.futures as _cf

    fechas = _fechas_disponibles()

    # Determinar fecha anterior
    if fecha_ant:
        fa = fecha_ant
    else:
        idx = fechas.index(fecha) if fecha in fechas else -1
        fa  = fechas[idx - 1] if idx > 0 else None

    # Lanzar resumen y alertas en paralelo
    with _cf.ThreadPoolExecutor(max_workers=2) as pool:
        fut_res = pool.submit(resumen_proveedores, fecha)
        if fa:
            fut_alt = pool.submit(get_alertas, fecha, umbral_pct, fa)
        else:
            fut_alt = None

        resumen  = fut_res.result()
        alertas  = fut_alt.result() if fut_alt else {
            "alertas": [], "total": 0, "msg": "Sin fecha anterior",
            "fechas_disponibles": fechas, "fecha_ant": None,
            "criticas": 0, "altas": 0, "medias": 0,
        }

    return {
        "fechas":   fechas,
        "resumen":  resumen,
        "alertas":  alertas,
    }


@router.get("/resumen/{fecha}")
def resumen_proveedores(fecha: str):
    """Cuántos títulos / registros tiene cada proveedor. Paralelo + caché 10min."""
    cache_key = f"resumen:{fecha}"
    cached = _mem_get(cache_key)
    if cached is not None:
        return cached

    def _uno(nombre_fn):
        nombre, fn = nombre_fn
        try:
            df = fn(fecha)
            if df.empty:
                return {"proveedor": nombre, "total": 0, "con_precio": 0,
                        "sin_precio": 0, "precio_promedio": None,
                        "precio_max": None, "precio_min": None, "disponible": False}
            n = len(df)
            if "PRECIO" in df.columns:
                p = pd.to_numeric(df["PRECIO"], errors="coerce").dropna()
                return {
                    "proveedor":       nombre,
                    "total":           n,
                    "con_precio":      int(p.count()),
                    "sin_precio":      int(n - p.count()),
                    "precio_promedio": round(float(p.mean()), 4) if len(p) else None,
                    "precio_max":      round(float(p.max()),  4) if len(p) else None,
                    "precio_min":      round(float(p.min()),  4) if len(p) else None,
                    "disponible":      True,
                }
            return {"proveedor": nombre, "total": n, "con_precio": 0,
                    "sin_precio": n, "precio_promedio": None,
                    "precio_max": None, "precio_min": None, "disponible": True}
        except Exception as e:
            return {"proveedor": nombre, "error": str(e),
                    "total": 0, "con_precio": 0, "sin_precio": 0, "disponible": False}

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        resultado = list(pool.map(_uno, CARGADORES.items()))

    _mem_set(cache_key, resultado)
    return resultado


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS — TABLAS POR PROVEEDOR
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/sp/{fecha}")
def get_sp(fecha: str, busqueda: Optional[str] = Query(None), limit: int = Query(2000)):
    df = cargar_sp(fecha)
    if df.empty:
        return []
    if busqueda:
        df = _buscar_df(df, busqueda)
    return _df_to_records(df, limit)


@router.get("/sw/{fecha}")
def get_sw(fecha: str, busqueda: Optional[str] = Query(None), limit: int = Query(2000)):
    df = cargar_sw(fecha)
    if df.empty:
        return []
    if busqueda:
        df = _buscar_df(df, busqueda)
    return _df_to_records(df, limit)


@router.get("/tp/{fecha}")
def get_tp(fecha: str, busqueda: Optional[str] = Query(None), limit: int = Query(2000)):
    df = cargar_tp(fecha)
    if df.empty:
        return []
    if busqueda:
        df = _buscar_df(df, busqueda)
    return _df_to_records(df, limit)


@router.get("/sv/{fecha}")
def get_sv(fecha: str, busqueda: Optional[str] = Query(None), limit: int = Query(500)):
    df = cargar_sv(fecha)
    if df.empty:
        return []
    if busqueda:
        df = _buscar_df(df, busqueda)
    return _df_to_records(df, limit)


@router.get("/mx/{fecha}")
def get_mx(
    fecha: str,
    tipo: Optional[str] = Query(None),
    moneda: Optional[str] = Query(None),
    busqueda: Optional[str] = Query(None),
    limit: int = Query(1000),
):
    df = cargar_mx(fecha)
    if df.empty:
        return []
    if tipo:
        col = next((c for c in df.columns if "tipo" in c.lower()), None)
        if col:
            df = df[df[col].str.upper().str.contains(tipo.upper(), na=False, regex=False)]
    if moneda:
        col = next((c for c in df.columns if c.strip().lower() == "moneda"), None)
        if col:
            df = df[df[col].str.upper().str.contains(moneda.upper(), na=False, regex=False)]
    if busqueda:
        df = _buscar_df(df, busqueda)
    return _df_to_records(df, limit)


@router.get("/mx_rv/{fecha}")
def get_mx_rv(fecha: str, busqueda: Optional[str] = Query(None), limit: int = Query(500)):
    df = cargar_mx_rv(fecha)
    if df.empty:
        return []
    if busqueda:
        df = _buscar_df(df, busqueda)
    return _df_to_records(df, limit)


@router.get("/notas/{fecha}")
def get_notas(fecha: str, busqueda: Optional[str] = Query(None), limit: int = Query(500)):
    df = cargar_notas(fecha)
    if df.empty:
        return []
    if busqueda:
        df = _buscar_df(df, busqueda)
    return _df_to_records(df, limit)


@router.get("/monedas/{fecha}")
def get_monedas(fecha: str):
    df = cargar_monedas(fecha)
    if df.empty:
        return []
    return _df_to_records(df, 200)


@router.get("/curvas/{fecha}")
def get_curvas(fecha: str):
    df = cargar_sb(fecha)
    if df.empty:
        return []
    return _df_to_records(df, 500)


@router.get("/tipos_instrumento/{fecha}")
def tipos_instrumento(fecha: str):
    df = cargar_mx(fecha)
    if df.empty:
        return []
    col = next((c for c in df.columns if "tipo" in c.lower() and "instrumento" in c.lower()), None)
    if not col:
        return []
    counts = df[col].str.strip().value_counts().reset_index()
    counts.columns = ["tipo", "cantidad"]
    return counts.to_dict(orient="records")


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS — VARIACIONES Y ALERTAS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/variaciones/{fecha_inicio}/{fecha_fin}")
def variaciones_entre_fechas(
    fecha_inicio: str,
    fecha_fin: str,
    proveedor: str = Query("SP"),
    umbral_pct: float = Query(5.0),
):
    """Variación de precios entre dos fechas. Incluye metadatos del título."""
    fn = CARGADORES.get(proveedor.upper())
    if not fn:
        raise HTTPException(400, f"Proveedor inválido: {list(CARGADORES.keys())}")

    df_i = fn(fecha_inicio)
    df_f = fn(fecha_fin)
    if df_i.empty or df_f.empty:
        return []

    # Columnas extra para enriquecer (SP tiene más info)
    extra_cols = [c for c in ["NEMO", "Tipo_Tasa", "Vcto", "Moneda", "Plazo", "TIR"]
                  if c in df_f.columns]

    for df in [df_i, df_f]:
        df["ID"] = df["ID"].astype(str).str.strip().str.upper()
        df["PRECIO"] = pd.to_numeric(df.get("PRECIO", pd.Series()), errors="coerce")

    cols_inicio = ["ID", "PRECIO"] + [c for c in extra_cols if c in df_i.columns]
    cols_fin    = ["ID", "PRECIO"] + extra_cols

    merged = (
        df_i[cols_inicio].rename(columns={"PRECIO": "PRECIO_INICIO"})
        .merge(df_f[cols_fin].rename(columns={"PRECIO": "PRECIO_FIN"}),
               on="ID", how="inner")
    )
    merged = merged.dropna(subset=["PRECIO_INICIO", "PRECIO_FIN"])
    merged = merged[merged["PRECIO_INICIO"] != 0]

    merged["VAR_ABS"] = (merged["PRECIO_FIN"] - merged["PRECIO_INICIO"]).round(6)
    merged["VAR_PCT"] = ((merged["VAR_ABS"] / merged["PRECIO_INICIO"].abs()) * 100).round(4)
    merged["ANORMAL"] = merged["VAR_PCT"].abs() > umbral_pct
    merged = merged.sort_values("VAR_PCT", key=abs, ascending=False)

    return _df_to_records(merged, 5000)


def _alertas_proveedor(nombre: str, fn, fecha: str, fa: str,
                        umbral_pct: float) -> List[Dict[str, Any]]:
    """
    Calcula alertas de UN proveedor de forma vectorizada (sin iterrows).
    Retorna lista de dicts ya lista para serializar.
    """
    META_COLS: Dict[str, List[str]] = {
        "SP":    ["NEMO", "Tipo_Tasa", "Vcto", "Moneda", "Plazo", "TIR"],
        "SW":    ["NEMO", "Tipo_Registro"],
        "SV":    ["Codigo", "Tipo", "Plazo"],
        "MX":    ["ISIN"],
        "MX_RV": ["ISIN"],
        "NOTAS": ["ISIN"],
        "TP":    ["Codigo", "ISIN"],
    }
    meta_extra = META_COLS.get(nombre, [])
    try:
        df_h = fn(fecha)
        df_a = fn(fa)
        if df_h.empty or df_a.empty:
            return []

        cols_h = ["ID", "PRECIO"] + [c for c in meta_extra if c in df_h.columns]
        cols_h = list(dict.fromkeys(cols_h))

        # Descripción si existe
        desc_col = next((c for c in ["Nombre", "Descripcion", "Emisor", "Descripción"]
                         if c in df_h.columns), None)
        if desc_col and "Descripcion" not in cols_h:
            df_h = df_h.copy()
            df_h["Descripcion"] = df_h[desc_col]
            cols_h.append("Descripcion")

        df_h2 = df_h[cols_h].copy()
        df_a2 = df_a[["ID", "PRECIO"]].copy()

        df_h2["ID"] = df_h2["ID"].astype(str).str.strip().str.upper()
        df_a2["ID"] = df_a2["ID"].astype(str).str.strip().str.upper()

        df_h2["PRECIO"] = pd.to_numeric(df_h2["PRECIO"], errors="coerce")
        df_a2["PRECIO"] = pd.to_numeric(df_a2["PRECIO"], errors="coerce")

        merged = df_h2.merge(df_a2, on="ID", suffixes=("_HOY", "_ANT"))
        merged.dropna(subset=["PRECIO_HOY", "PRECIO_ANT"], inplace=True)
        merged = merged[merged["PRECIO_ANT"] != 0]
        if merged.empty:
            return []

        merged["VAR_ABS"] = (merged["PRECIO_HOY"] - merged["PRECIO_ANT"]).round(6)
        merged["VAR_PCT"] = (merged["VAR_ABS"] / merged["PRECIO_ANT"].abs() * 100).round(4)
        anorm = merged[merged["VAR_PCT"].abs() > umbral_pct].copy()
        if anorm.empty:
            return []

        # Severidad vectorizada
        sev_abs = anorm["VAR_PCT"].abs()
        anorm["SEVERIDAD"] = np.where(
            sev_abs > umbral_pct * 3, "CRITICA",
            np.where(sev_abs > umbral_pct * 1.5, "ALTA", "MEDIA")
        )
        anorm["FUENTE"]    = nombre
        anorm["FECHA_HOY"] = fecha
        anorm["FECHA_ANT"] = fa
        anorm["ISIN"]      = anorm["ID"]   # alias

        # Limpiar inf/nan en columnas object y float
        for col in anorm.select_dtypes(include="object").columns:
            anorm[col] = anorm[col].where(anorm[col].notna(), other=None)
        for col in anorm.select_dtypes(include="float").columns:
            anorm[col] = anorm[col].where(np.isfinite(anorm[col]), other=None)

        # Columnas finales a exportar
        out_cols = (["ID", "ISIN", "FUENTE", "PRECIO_HOY", "PRECIO_ANT",
                     "VAR_ABS", "VAR_PCT", "SEVERIDAD", "FECHA_HOY", "FECHA_ANT"]
                    + [c for c in meta_extra if c in anorm.columns]
                    + (["Descripcion"] if "Descripcion" in anorm.columns else []))
        out_cols = list(dict.fromkeys(out_cols))

        return anorm[out_cols].to_dict(orient="records")

    except Exception as e:
        logger.error(f"Error alertas {nombre}: {e}", exc_info=True)
        return []


@router.get("/alertas/{fecha}")
def get_alertas(
    fecha: str,
    umbral_pct: float = Query(5.0),
    fecha_ant: Optional[str] = Query(None, description="Fecha anterior explícita"),
):
    """
    Alertas de variación anormal — vectorizado + paralelo + caché 10 min.
    """
    fechas = _fechas_disponibles()
    if fecha_ant:
        fa = fecha_ant
    else:
        idx = fechas.index(fecha) if fecha in fechas else -1
        if idx <= 0:
            return {"alertas": [], "total": 0, "msg": "Sin fecha anterior disponible",
                    "fechas_disponibles": fechas}
        fa = fechas[idx - 1]

    cache_key = f"alertas:{fecha}:{fa}:{umbral_pct}"
    cached = _mem_get(cache_key)
    if cached is not None:
        cached["fechas_disponibles"] = fechas   # siempre fresco
        return cached

    # Cargar todos los proveedores en paralelo (excepto SB)
    provs = [(n, fn) for n, fn in CARGADORES.items() if n != "SB"]
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(provs)) as pool:
        parciales = list(pool.map(
            lambda x: _alertas_proveedor(x[0], x[1], fecha, fa, umbral_pct),
            provs
        ))

    alertas: List[Dict] = []
    for rows in parciales:
        alertas.extend(rows)

    alertas.sort(key=lambda x: abs(x.get("VAR_PCT") or 0), reverse=True)

    result = {
        "total":              len(alertas),
        "fecha":              fecha,
        "fecha_ant":          fa,
        "fechas_disponibles": fechas,
        "umbral":             umbral_pct,
        "criticas":           sum(1 for a in alertas if a["SEVERIDAD"] == "CRITICA"),
        "altas":              sum(1 for a in alertas if a["SEVERIDAD"] == "ALTA"),
        "medias":             sum(1 for a in alertas if a["SEVERIDAD"] == "MEDIA"),
        "alertas":            alertas,
    }
    _mem_set(cache_key, result)
    return result


@router.get("/alertas_multidia/{fecha}")
def alertas_multidia(
    fecha: str,
    dias: int = Query(5, description="Cuántas fechas anteriores comparar"),
    umbral_pct: float = Query(5.0),
    proveedor: str = Query("SP"),
):
    """Compara un ISIN contra múltiples fechas anteriores (histórico de alertas)."""
    fechas = _fechas_disponibles()
    idx = fechas.index(fecha) if fecha in fechas else -1
    if idx < 0:
        raise HTTPException(404, "Fecha no disponible")

    fn = CARGADORES.get(proveedor.upper())
    if not fn:
        raise HTTPException(400, "Proveedor inválido")

    fechas_ant = fechas[max(0, idx - dias): idx]
    if not fechas_ant:
        return {"series": [], "msg": "Sin fechas anteriores suficientes"}

    df_hoy = fn(fecha)
    if df_hoy.empty:
        return {"series": [], "msg": "Sin datos para fecha seleccionada"}

    df_hoy["ID"] = df_hoy["ID"].astype(str).str.strip().str.upper()
    df_hoy["PRECIO"] = pd.to_numeric(df_hoy.get("PRECIO", pd.Series()), errors="coerce")

    series = []
    for fa in fechas_ant:
        try:
            df_a = fn(fa)
            if df_a.empty:
                continue
            df_a["ID"] = df_a["ID"].astype(str).str.strip().str.upper()
            df_a["PRECIO"] = pd.to_numeric(df_a.get("PRECIO", pd.Series()), errors="coerce")
            merged = df_hoy[["ID", "PRECIO"]].merge(
                df_a[["ID", "PRECIO"]], on="ID", suffixes=("_HOY", "_ANT")
            ).dropna()
            merged = merged[merged["PRECIO_ANT"] != 0]
            merged["VAR_PCT"] = (
                (merged["PRECIO_HOY"] - merged["PRECIO_ANT"])
                / merged["PRECIO_ANT"].abs() * 100
            ).round(4)
            anorm = merged[merged["VAR_PCT"].abs() > umbral_pct]
            series.append({
                "fecha_ant": fa,
                "total":     len(merged),
                "anormales": int(len(anorm)),
                "max_var":   round(float(merged["VAR_PCT"].abs().max()), 4) if len(merged) else 0,
            })
        except Exception:
            continue

    return {"fecha": fecha, "proveedor": proveedor, "umbral": umbral_pct, "series": series}


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT — HISTÓRICO POR ISIN (optimizado: 1 llamada, no N loops)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/historico/{isin}")
def historico_isin(
    isin: str,
    proveedor: str = Query("SP"),
    max_fechas: int = Query(30),
):
    """
    Retorna el precio de un ISIN en todas las fechas disponibles.
    Una sola llamada desde el frontend (antes hacía N llamadas en loop).
    """
    fn = CARGADORES.get(proveedor.upper())
    if not fn:
        raise HTTPException(400, "Proveedor inválido")

    fechas = _fechas_disponibles()
    if not fechas:
        return {"isin": isin, "proveedor": proveedor, "puntos": []}

    isin_up = isin.strip().upper()
    puntos = []

    for fecha in fechas[-max_fechas:]:
        try:
            df = fn(fecha)
            if df.empty:
                continue
            df["ID"] = df["ID"].astype(str).str.strip().str.upper()
            df["PRECIO"] = pd.to_numeric(df.get("PRECIO", pd.Series()), errors="coerce")
            fila = df[df["ID"] == isin_up]
            if fila.empty:
                continue
            precio = fila["PRECIO"].iloc[0]
            if pd.isna(precio):
                continue
            # Metadatos extra si disponibles (SP tiene TIR, Vcto, etc.)
            meta: Dict[str, Any] = {}
            for col in ["TIR", "Vcto", "Tipo_Tasa", "NEMO", "Plazo"]:
                if col in fila.columns:
                    v = fila[col].iloc[0]
                    meta[col] = None if pd.isna(v) else v
            puntos.append({"fecha": fecha, "precio": round(float(precio), 6), **meta})
        except Exception:
            continue

    # Calcular variaciones
    for i, p in enumerate(puntos):
        if i > 0:
            ant = puntos[i - 1]["precio"]
            p["var_abs"] = round(p["precio"] - ant, 6) if ant else None
            p["var_pct"] = round((p["precio"] - ant) / abs(ant) * 100, 4) if ant else None
        else:
            p["var_abs"] = None
            p["var_pct"] = None

    return {
        "isin":      isin_up,
        "proveedor": proveedor,
        "puntos":    puntos,
        "n":         len(puntos),
        "precio_actual": puntos[-1]["precio"] if puntos else None,
        "precio_min":    min(p["precio"] for p in puntos) if puntos else None,
        "precio_max":    max(p["precio"] for p in puntos) if puntos else None,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT — CURVAS DE RENTA FIJA SP (scatter TIR vs Plazo)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/sp_curvas/{fecha}")
def sp_curvas(
    fecha: str,
    tipo_tasa: Optional[str] = Query(None, description="Filtrar por Tipo_Tasa (ej: TV, FV, IPC)"),
):
    """
    Datos del SP preparados para graficar curvas de renta fija:
      - Eje X: Plazo (días)
      - Eje Y: TIR (%)
      - Agrupado por Tipo_Tasa
    Solo incluye registros con Plazo y TIR válidos.
    """
    df = cargar_sp(fecha)
    if df.empty:
        return {"curvas": [], "tipos": []}

    needed = ["ID", "NEMO", "ISIN", "Tipo_Tasa", "Plazo", "TIR", "PRECIO", "Vcto", "Moneda"]
    df = df[[c for c in needed if c in df.columns]].copy()

    df["Plazo"] = pd.to_numeric(df.get("Plazo", pd.Series()), errors="coerce")
    df["TIR"]   = pd.to_numeric(df.get("TIR",   pd.Series()), errors="coerce")
    df = df.dropna(subset=["Plazo", "TIR"])
    df = df[df["Plazo"] > 0]

    tipos = sorted(df["Tipo_Tasa"].dropna().unique().tolist()) if "Tipo_Tasa" in df.columns else []

    if tipo_tasa:
        df = df[df["Tipo_Tasa"].str.upper() == tipo_tasa.upper()]

    # Agrupar por tipo de tasa
    curvas = []
    grupos = df.groupby("Tipo_Tasa") if "Tipo_Tasa" in df.columns else [("ALL", df)]
    for tipo, grupo in grupos:
        grupo = grupo.sort_values("Plazo")
        curvas.append({
            "tipo":   str(tipo),
            "puntos": _df_to_records(grupo, 2000),
        })

    return {"fecha": fecha, "tipos": tipos, "curvas": curvas}


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT — COMPARACIÓN ENTRE PROVEEDORES
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/comparacion/{fecha}")
def comparar_proveedores(
    fecha: str,
    proveedores: str = Query("SP,MX"),
):
    """Cruza múltiples proveedores por ID/ISIN y calcula diferencias de precio."""
    seleccionados = [p.strip().upper() for p in proveedores.split(",")
                     if p.strip().upper() in CARGADORES]
    if len(seleccionados) < 1:
        raise HTTPException(400, "Selecciona al menos un proveedor válido")

    frames: Dict[str, pd.DataFrame] = {}
    for nombre in seleccionados:
        df = CARGADORES[nombre](fecha)
        if df.empty:
            continue
        df["ID"] = df["ID"].astype(str).str.strip().str.upper()
        df["PRECIO"] = pd.to_numeric(df.get("PRECIO", pd.Series()), errors="coerce")
        frames[nombre] = df[["ID", "PRECIO"]].rename(columns={"PRECIO": f"PRECIO_{nombre}"})

    if not frames:
        return []

    base = list(frames.values())[0]
    for df in list(frames.values())[1:]:
        base = base.merge(df, on="ID", how="outer")

    precio_cols = [c for c in base.columns if c.startswith("PRECIO_")]
    if len(precio_cols) >= 2:
        precios = base[precio_cols]
        base["PRECIO_MAX"] = precios.max(axis=1).round(6)
        base["PRECIO_MIN"] = precios.min(axis=1).round(6)
        base["DIF_ABS"]    = (base["PRECIO_MAX"] - base["PRECIO_MIN"]).round(6)
        base["DIF_PCT"]    = (
            (base["DIF_ABS"] / base["PRECIO_MIN"].abs()) * 100
        ).round(4)
        base["FUENTES"] = precios.notna().sum(axis=1).astype(int)

    return _df_to_records(base, 3000)


# ── Endpoints nuevos para módulo modular ────────────────────────────────────

@router.get("/proveedores/{fecha}")
def get_proveedores_disponibles(fecha: str):
    """Lista qué proveedores tienen cache para la fecha dada."""
    disponibles = []
    for nombre, cargador in CARGADORES.items():
        try:
            df = cargador(fecha)
            if not df.empty:
                disponibles.append(nombre)
        except Exception:
            pass
    return {"fecha": fecha, "proveedores": disponibles}


@router.get("/datos/{fecha}/{proveedor}")
def get_datos_proveedor(
    fecha: str,
    proveedor: str,
    busqueda: Optional[str] = Query(None),
    limit: int = Query(500),
):
    """Endpoint genérico: devuelve datos de cualquier proveedor por nombre."""
    prov = proveedor.upper()
    if prov not in CARGADORES:
        raise HTTPException(400, f"Proveedor desconocido: {prov}. Válidos: {list(CARGADORES)}")
    df = CARGADORES[prov](fecha)
    if df.empty:
        return []
    if busqueda:
        df = _buscar_df(df, busqueda)
    return _df_to_records(df, limit)
