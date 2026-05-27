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
import logging
import concurrent.futures
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

import pandas as pd
import numpy as np
from fastapi import APIRouter, Query, HTTPException
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_config

logger = logging.getLogger("insumos")
router = APIRouter()

_ROOT = Path(__file__).parent.parent.parent


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

def _get_infovalmer_base() -> Path:
    cfg = get_config()
    base = Path(cfg.get("infovalmer_dir", ""))
    if not base or not base.exists():
        base = Path(r"J:\VALORACION\VALORACION_ESPECIAL\Bolsa\INFOVALMER")
    return base


def _infovalmer_dir(fecha: str) -> Path:
    """Carpeta cruda del día: infovalmer_base/FECHA/"""
    return _get_infovalmer_base() / fecha


def _pkl_dir(fecha: str) -> Path:
    """Cache PKL: infovalmer_base/FECHA/pkl/"""
    d = _infovalmer_dir(fecha) / "pkl"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _excel_dir(fecha: str) -> Path:
    """Excel exportados: infovalmer_base/FECHA/excel/"""
    d = _infovalmer_dir(fecha) / "excel"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cache_path(fecha: str, proveedor: str) -> Path:
    return _pkl_dir(fecha) / f"{proveedor}_{fecha}.pkl"


def _excel_path(fecha: str, proveedor: str) -> Path:
    return _excel_dir(fecha) / f"{proveedor}_{fecha}.xlsx"


def _dir_tiene_insumos(d: Path, fecha: str) -> bool:
    """Verifica si la carpeta cruda del día tiene al menos un archivo fuente."""
    try:
        sf = datetime.strptime(fecha, "%Y%m%d").strftime("%m%d%y")
    except ValueError:
        return False
    nombres = (
        f"SP{sf}.001", f"SW{sf}.001", f"SV{sf}.001", f"SB{sf}.001",
        f"MX{sf}.txt", f"MX{sf}_RV.txt",
        f"NOTAS_ESTRUCTURADAS_{fecha}.csv",
        f"titulos_participativos_valoracion_{fecha}.txt",
        f"monedas_matriz_info_{fecha}.csv",
    )
    # También acepta si ya tiene PKLs convertidos
    pkl_dir = d / "pkl"
    tiene_pkl = pkl_dir.exists() and any(pkl_dir.glob("*.pkl"))
    return any((d / nombre).is_file() for nombre in nombres) or tiene_pkl


def _find_file(fecha: str, patterns: List[str]) -> Optional[Path]:
    """Busca archivo fuente solo en la carpeta cruda del día."""
    d = _infovalmer_dir(fecha)
    if not d.exists():
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
    """
    Devuelve todas las fechas con archivos en Infovalmer (últimos ~90 días).
    Busca SOLO en infovalmer_base/FECHA/ — ya no hay carpeta data_dir separada.
    """
    fechas: set = set()
    infovalmer_base = _get_infovalmer_base()
    if infovalmer_base.exists():
        # Escanear todas las subcarpetas YYYYMMDD
        for d in infovalmer_base.iterdir():
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
    Si export_excel=True, guarda XLSX en infovalmer/FECHA/excel/
    """
    pkl = _cache_path(fecha, proveedor)
    df.to_pickle(pkl)

    xlsx_path = None
    excel_ok  = False
    if export_excel and not df.empty:
        xlsx_path = _excel_path(fecha, proveedor)
        try:
            df.to_excel(xlsx_path, index=False)
            excel_ok = True
        except Exception as e:
            logger.warning(f"Excel falló {xlsx_path}: {e}")

    return {
        "proveedor": proveedor,
        "filas":     int(len(df)),
        "pkl":       str(pkl),
        "xlsx":      str(xlsx_path) if excel_ok else None,
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

def cargar_sp(fecha: str, use_cache: bool = True) -> pd.DataFrame:
    """SP = BVC Renta Fija local (fixed-width .001).
    Layout por posición de carácter (según legacy Revisiones_Valoracion):
      [0:7]   Numero_Secuencia
      [7:20]  NEMO
      [20:32] ISIN
      [51:59] Emision
      [59:67] Vcto
      [75:77] Tipo_Tasa
      [77:81] Plazo
      [81:84] Base
      [86:89] Moneda
      [96:105] P_SUCIO  ← precio valoración
      [122:129] P_LIMPIO
      [179:187] Tasa (TIR)
    """
    if use_cache:
        cached = _leer_cache(fecha, "SP")
        if cached is not None:
            return cached
    sf = _sufijo_fecha(fecha)
    path = _infovalmer_dir(fecha) / f"SP{sf}.001"
    if not path.exists():
        return pd.DataFrame()
    filas = []
    try:
        with open(path, "r", encoding="latin-1", errors="ignore") as fh:
            for ln in fh:
                ln = ln.rstrip("\n")
                if len(ln) < 107 or not ln[51:53].startswith("20"):
                    continue
                p_sucio  = _parse_num(ln[96:105])
                p_limpio = _parse_num(ln[122:129]) if len(ln) >= 129 else None
                precio   = p_sucio if p_sucio is not None else p_limpio
                if precio is None:
                    continue
                tir      = _parse_num(ln[179:187]) if len(ln) >= 187 else None
                plazo_raw = ln[77:81].strip()
                plazo    = int(plazo_raw) if plazo_raw.isdigit() else None
                isin = ln[20:32].strip().upper()
                nemo = ln[7:20].strip().upper()
                filas.append({
                    "NEMO":       nemo,
                    "ISIN":       isin,
                    "Emision":    ln[51:59].strip(),
                    "Vcto":       ln[59:67].strip(),
                    "Tipo_Tasa":  ln[75:77].strip(),
                    "Plazo":      plazo,
                    "Base":       ln[81:84].strip(),
                    "Moneda":     ln[86:89].strip(),
                    "P_SUCIO":    p_sucio,
                    "P_LIMPIO":   p_limpio,
                    "TIR":        tir,
                    "PRECIO":     precio,
                    "ID":         isin if isin else nemo,
                    "FUENTE":     "SP",
                })
    except Exception as e:
        logger.error(f"Error cargando SP: {e}")
        return pd.DataFrame()
    df = pd.DataFrame(filas)
    _guardar_cache(fecha, "SP", df)
    return df


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
    """Convierte DataFrame a lista de dicts con NaN→None de forma eficiente."""
    return (
        df.head(limit)
        .where(df.head(limit).notna(), other=None)
        .to_dict(orient="records")
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS — CACHE / CONVERSIÓN
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/cache/{fecha}")
def estado_cache(fecha: str):
    """Estado de cache PKL + Excel por proveedor para la fecha dada."""
    return _cache_status(fecha)


@router.post("/convertir/{fecha}")
def convertir_insumos(
    fecha: str,
    force: bool = Query(False, description="Reconvertir aunque el PKL ya exista"),
):
    """
    Convierte TODOS los archivos crudos de Infovalmer para la fecha dada.
    - PKL  → infovalmer/FECHA/pkl/PROVEEDOR_FECHA.pkl
    - XLSX → infovalmer/FECHA/excel/PROVEEDOR_FECHA.xlsx
    - Si el PKL ya existe y force=False, lo omite (no reconvierte).
    - Paralelo con 4 hilos.
    """
    loaders = {
        "SP": cargar_sp, "SW": cargar_sw, "TP": cargar_tp, "SV": cargar_sv,
        "MX": cargar_mx, "MX_RV": cargar_mx_rv, "NOTAS": cargar_notas,
        "SB": cargar_sb, "MONEDAS": cargar_monedas,
    }

    def _uno(item):
        proveedor, loader = item
        pkl = _cache_path(fecha, proveedor)
        xlsx = _excel_path(fecha, proveedor)
        if pkl.exists() and xlsx.exists() and not force:
            cached = _leer_cache(fecha, proveedor)
            return {
                "proveedor": proveedor,
                "filas":     int(len(cached)) if cached is not None else 0,
                "cache_ok":  True,
                "omitido":   True,
                "pkl":       str(pkl),
                "xlsx":      str(xlsx),
            }
        try:
            df = loader(fecha, use_cache=False)
            if df.empty:
                return {"proveedor": proveedor, "filas": 0, "cache_ok": False,
                        "error": "archivo fuente no encontrado o vacío"}
            return _guardar_cache(fecha, proveedor, df, export_excel=True)
        except Exception as e:
            logger.exception(f"Error convirtiendo {proveedor} {fecha}")
            return {"proveedor": proveedor, "filas": 0, "cache_ok": False, "error": str(e)}

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        resultados = list(pool.map(_uno, loaders.items()))

    return {
        "ok":         all(r.get("cache_ok") for r in resultados),
        "fecha":      fecha,
        "status":     _cache_status(fecha),
        "resultados": resultados,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS — FECHAS / RESUMEN
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/fechas")
def get_fechas():
    return {"fechas": _fechas_disponibles()}


@router.get("/resumen/{fecha}")
def resumen_proveedores(fecha: str):
    """Cuántos títulos / registros tiene cada proveedor. Carga desde cache."""
    resultado = []
    for nombre, fn in CARGADORES.items():
        try:
            df = fn(fecha)
            precios = pd.to_numeric(
                df.get("PRECIO", pd.Series()), errors="coerce"
            ).dropna() if not df.empty else pd.Series(dtype=float)
            resultado.append({
                "proveedor":      nombre,
                "total":          len(df),
                "con_precio":     int(precios.count()),
                "sin_precio":     int(len(df) - precios.count()),
                "precio_promedio": round(float(precios.mean()), 6) if len(precios) else None,
                "precio_max":     round(float(precios.max()), 6) if len(precios) else None,
                "precio_min":     round(float(precios.min()), 6) if len(precios) else None,
                "disponible":     not df.empty,
            })
        except Exception as e:
            resultado.append({
                "proveedor": nombre, "error": str(e),
                "total": 0, "con_precio": 0, "sin_precio": 0, "disponible": False,
            })
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


@router.get("/alertas/{fecha}")
def get_alertas(
    fecha: str,
    umbral_pct: float = Query(5.0),
    fecha_ant: Optional[str] = Query(None, description="Fecha anterior explícita"),
):
    """Alertas de variación anormal de precio entre fecha y su anterior."""
    fechas = _fechas_disponibles()
    if fecha_ant:
        fa = fecha_ant
    else:
        idx = fechas.index(fecha) if fecha in fechas else -1
        if idx <= 0:
            return {"alertas": [], "total": 0, "msg": "Sin fecha anterior disponible"}
        fa = fechas[idx - 1]

    alertas = []
    for nombre, fn in CARGADORES.items():
        if nombre in ("SB", "TP"):   # TP/SB no tienen precios comparables día a día
            continue
        try:
            df_h = fn(fecha)
            df_a = fn(fa)
            if df_h.empty or df_a.empty:
                continue
            df_h = df_h[["ID", "PRECIO"]].copy()
            df_a = df_a[["ID", "PRECIO"]].copy()
            df_h["ID"] = df_h["ID"].astype(str).str.strip().str.upper()
            df_a["ID"] = df_a["ID"].astype(str).str.strip().str.upper()
            df_h["PRECIO"] = pd.to_numeric(df_h["PRECIO"], errors="coerce")
            df_a["PRECIO"] = pd.to_numeric(df_a["PRECIO"], errors="coerce")

            merged = df_h.merge(df_a, on="ID", suffixes=("_HOY", "_ANT")).dropna()
            merged = merged[merged["PRECIO_ANT"] != 0]
            merged["VAR_PCT"] = (
                (merged["PRECIO_HOY"] - merged["PRECIO_ANT"])
                / merged["PRECIO_ANT"].abs() * 100
            ).round(4)
            anorm = merged[merged["VAR_PCT"].abs() > umbral_pct]
            for _, r in anorm.iterrows():
                alertas.append({
                    "ISIN":       r["ID"],
                    "FUENTE":     nombre,
                    "PRECIO_HOY": round(r["PRECIO_HOY"], 6),
                    "PRECIO_ANT": round(r["PRECIO_ANT"], 6),
                    "VAR_PCT":    round(r["VAR_PCT"], 4),
                    "SEVERIDAD":  "CRITICA" if abs(r["VAR_PCT"]) > umbral_pct * 3
                                  else "ALTA" if abs(r["VAR_PCT"]) > umbral_pct * 1.5
                                  else "MEDIA",
                })
        except Exception as e:
            logger.error(f"Error alertas {nombre}: {e}")

    alertas.sort(key=lambda x: abs(x["VAR_PCT"]), reverse=True)
    return {
        "total":     len(alertas),
        "fecha":     fecha,
        "fecha_ant": fa,
        "umbral":    umbral_pct,
        "criticas":  sum(1 for a in alertas if a["SEVERIDAD"] == "CRITICA"),
        "altas":     sum(1 for a in alertas if a["SEVERIDAD"] == "ALTA"),
        "medias":    sum(1 for a in alertas if a["SEVERIDAD"] == "MEDIA"),
        "alertas":   alertas,
    }


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
