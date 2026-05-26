#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROUTER INSUMOS
Proveedores de precios: SP/SW/TP (Infovalmer J: drive), MX, MX_RV, NOTAS, SB, indicadores, monedas.
"""
from __future__ import annotations

import re
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

import pandas as pd
import numpy as np
from fastapi import APIRouter, Query, HTTPException
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_data_dir, get_config

logger = logging.getLogger("insumos")
router = APIRouter()

_ROOT = Path(__file__).parent.parent.parent


# ── Utilidades ──────────────────────────────────────────────────────────

def _base_dir() -> Path:
    return get_data_dir()


def _num(x):
    try:
        return float(str(x).replace(",", ".").replace(" ", "").strip())
    except Exception:
        return None


def _fecha_valida(nombre: str) -> bool:
    if not re.fullmatch(r"\d{8}", str(nombre)):
        return False
    try:
        dt = datetime.strptime(str(nombre), "%Y%m%d")
        return 2020 <= dt.year <= 2030
    except ValueError:
        return False


def _dir_tiene_insumos(d: Path, fecha: str) -> bool:
    try:
        sf = datetime.strptime(fecha, "%Y%m%d").strftime("%m%d%y")
    except ValueError:
        return False
    nombres = (
        f"SP{sf}.001",
        f"SW{sf}.001",
        f"SV{sf}.001",
        f"SB{sf}.001",
        f"MX{sf}.txt",
        f"MX{sf}_RV.txt",
        f"NOTAS_ESTRUCTURADAS_{fecha}.csv",
        f"titulos_participativos_valoracion_{fecha}.txt",
        f"monedas_matriz_info_{fecha}.csv",
    )
    return any((d / nombre).is_file() for nombre in nombres)


def _fechas_disponibles() -> List[str]:
    fechas = set()

    base = _base_dir()
    if base.exists():
        for d in base.iterdir():
            if d.is_dir() and _fecha_valida(d.name) and _dir_tiene_insumos(d, d.name):
                fechas.add(d.name)

    infovalmer_base = _get_infovalmer_base()
    if infovalmer_base.exists():
        hoy = datetime.today()
        for i in range(-7, 75):
            fecha = (hoy - timedelta(days=i)).strftime("%Y%m%d")
            d = infovalmer_base / fecha
            if d.is_dir() and _dir_tiene_insumos(d, fecha):
                fechas.add(fecha)

    return sorted(fechas)


def _dirs(fecha: str) -> List[Path]:
    base = _base_dir()
    infovalmer_base = _get_infovalmer_base()
    dirs = [base / fecha, infovalmer_base / fecha, base]
    seen = set()
    unique = []
    for d in dirs:
        key = str(d).lower()
        if key not in seen:
            seen.add(key)
            unique.append(d)
    return unique


def _find_file(fecha: str, patterns: List[str]) -> Optional[Path]:
    """Busca archivo por patrones regex en nombre, sin importar extensión."""
    for d in _dirs(fecha):
        if not d.exists():
            continue
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


# ── Infovalmer J: drive ────────────────────────────────────────────────

def _get_infovalmer_base() -> Path:
    """Obtiene la ruta base de Infovalmer desde config.yaml"""
    cfg = get_config()
    base = Path(cfg.get("infovalmer_dir", ""))
    if not base or not base.exists():
        base = Path(r"J:\VALORACION\VALORACION_ESPECIAL\Bolsa\INFOVALMER")
    return base


def _sufijo_fecha(fecha_str: str) -> str:
    """20260514 → 051426  (MMDDYY)"""
    return datetime.strptime(fecha_str, "%Y%m%d").strftime("%m%d%y")


def _infovalmer_dir(fecha: str) -> Path:
    base = _get_infovalmer_base()
    return base / fecha


def _parse_num(s: str):
    try:
        return float(str(s).strip().replace("\xa0", "").replace(" ", "").replace(",", "."))
    except Exception:
        return None


CACHE_PROVEEDORES = ("SP", "SW", "TP", "SV", "MX", "MX_RV", "NOTAS", "SB", "MONEDAS")


def _cache_dir(fecha: str) -> Path:
    return _base_dir() / fecha / "cache_insumos"


def _cache_path(fecha: str, proveedor: str, ext: str = "pkl") -> Path:
    return _cache_dir(fecha) / f"{proveedor}_{fecha}.{ext}"


def _leer_cache(fecha: str, proveedor: str) -> Optional[pd.DataFrame]:
    path = _cache_path(fecha, proveedor, "pkl")
    if not path.exists():
        return None
    try:
        return pd.read_pickle(path)
    except Exception as e:
        logger.warning(f"No se pudo leer cache {path}: {e}")
        return None


def _guardar_cache(fecha: str, proveedor: str, df: pd.DataFrame, export_excel: bool = True) -> Dict[str, Any]:
    cdir = _cache_dir(fecha)
    cdir.mkdir(parents=True, exist_ok=True)
    pkl = _cache_path(fecha, proveedor, "pkl")
    df.to_pickle(pkl)

    xlsx = _cache_path(fecha, proveedor, "xlsx")
    excel_ok = False
    if export_excel:
        try:
            df.to_excel(xlsx, index=False)
            excel_ok = True
        except Exception as e:
            logger.warning(f"No se pudo exportar Excel {xlsx}: {e}")

    return {
        "proveedor": proveedor,
        "filas": int(len(df)),
        "pkl": str(pkl),
        "xlsx": str(xlsx) if excel_ok else None,
        "cache_ok": True,
    }


def _cache_status(fecha: str) -> Dict[str, Any]:
    detalle = {}
    total_ok = 0
    for proveedor in CACHE_PROVEEDORES:
        pkl = _cache_path(fecha, proveedor, "pkl")
        xlsx = _cache_path(fecha, proveedor, "xlsx")
        ok = pkl.exists()
        total_ok += int(ok)
        detalle[proveedor] = {
            "cache": ok,
            "excel": xlsx.exists(),
            "pkl": str(pkl),
            "xlsx": str(xlsx),
        }
    return {
        "fecha": fecha,
        "cache_dir": str(_cache_dir(fecha)),
        "total": len(CACHE_PROVEEDORES),
        "convertidos": total_ok,
        "completo": total_ok == len(CACHE_PROVEEDORES),
        "proveedores": detalle,
    }


def cargar_sp(fecha: str, use_cache: bool = True) -> pd.DataFrame:
    """SP = Bolsa de Valores de Colombia, precios renta fija local (fixed-width .001).
    Columnas según legacy Revisiones_Valoracion:
      l[0:7]   = Numero_Secuencia
      l[7:20]  = NEMO
      l[20:32] = ISIN
      l[51:59] = Emision
      l[59:67] = Vcto
      l[67:75] = Vcto2
      l[75:77] = Tipo_Tasa
      l[77:81] = Plazo
      l[81:84] = Base
      l[86:89] = Moneda
      l[96:105]= P_SUCIO  ← precio principal para valoración
      l[122:129]= P_LIMPIO (alternativo)
      l[179:187]= Tasa
    Filtro de líneas válidas: l[51:53] empieza con "20" (fecha emisión).
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
        with open(path, "r", encoding="latin-1", errors="ignore") as f:
            for ln in f:
                ln = ln.rstrip("\n")
                if len(ln) < 107 or not ln[51:53].startswith("20"):
                    continue
                p_sucio  = _parse_num(ln[96:105])
                p_limpio = _parse_num(ln[122:129]) if len(ln) >= 129 else None
                precio   = p_sucio if p_sucio is not None else p_limpio
                if precio is None:
                    continue
                isin = ln[20:32].strip().upper()
                nemo = ln[7:20].strip().upper()
                filas.append({
                    "Numero_Secuencia": ln[0:7].strip(),
                    "NEMO":             nemo,
                    "ISIN":             isin,
                    "Emision":          ln[51:59].strip(),
                    "Vcto":             ln[59:67].strip(),
                    "Tipo_Tasa":        ln[75:77].strip(),
                    "Plazo":            ln[77:81].strip(),
                    "Base":             ln[81:84].strip(),
                    "Moneda":           ln[86:89].strip(),
                    "P_SUCIO":          p_sucio,
                    "P_LIMPIO":         p_limpio,
                    "Tasa":             _parse_num(ln[179:187]) if len(ln) >= 187 else None,
                    "PRECIO":           precio,
                    "ID":               isin if isin else nemo,
                    "FUENTE":           "SP",
                })
    except Exception as e:
        logger.error(f"Error cargando SP: {e}")
        return pd.DataFrame()
    return pd.DataFrame(filas)


def cargar_sw(fecha: str, use_cache: bool = True) -> pd.DataFrame:
    """SW = Precios secundarios / swap (regex .001)."""
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
        with open(path, "r", encoding="latin-1", errors="ignore") as f:
            for ln in f:
                m = patron.match(ln.strip())
                if not m:
                    continue
                nums = re.findall(r"[-+]?\d[\d,.]*", m.group("valor"))
                precio = _parse_num(nums[-1]) if nums else None
                if precio is None:
                    continue
                nemo = m.group("nemo").strip().upper()
                filas.append({
                    "Numero_Secuencia": m.group("sec"),
                    "Tipo_Registro":    m.group("tipo"),
                    "NEMO":             nemo,
                    "ISIN":             "",
                    "PRECIO":           precio,
                    "ID":               nemo,
                    "FUENTE":           "SW",
                })
    except Exception as e:
        logger.error(f"Error cargando SW: {e}")
        return pd.DataFrame()
    return pd.DataFrame(filas)


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
        with open(path, "r", encoding="latin-1", errors="ignore") as f:
            for ln in f:
                ln = ln.rstrip("\n")
                if len(ln) < 29:
                    continue
                precio_txt = ln[29:].strip()
                precio = _parse_num(precio_txt)
                if precio is None:
                    continue
                isin = ln[6:19].strip().upper()
                cod  = ln[0:6].strip().upper()
                filas.append({
                    "Codigo":      cod,
                    "Fecha":       ln[19:29].strip(),
                    "ISIN":        isin,
                    "Precio":      precio,
                    "PRECIO":      precio,
                    "ID":          isin if isin else cod,
                    "FUENTE":      "TP",
                })
    except Exception as e:
        logger.error(f"Error cargando TP: {e}")
        return pd.DataFrame()
    return pd.DataFrame(filas)


def cargar_sv(fecha: str, use_cache: bool = True) -> pd.DataFrame:
    """SV = Tasas de interés de referencia (Infovalmer SV{MMDDYY}.001).
    Columnas según legacy:
      l[0:5]  = Codigo
      l[5:6]  = Tipo
      l[6:14] = Fecha
      l[14:18]= Plazo
      l[18:33]= Tasa
    Filtro: l[6:8] empieza con "20" (año de la fecha).
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
        with open(path, "r", encoding="latin-1", errors="ignore") as f:
            for ln in f:
                ln = ln.rstrip("\n")
                if len(ln) < 18 or not ln[6:8].startswith("20"):
                    continue
                tasa = _parse_num(ln[18:33]) if len(ln) >= 33 else None
                filas.append({
                    "Codigo": ln[0:5].strip(),
                    "Tipo":   ln[5:6].strip(),
                    "Fecha":  ln[6:14].strip(),
                    "Plazo":  ln[14:18].strip(),
                    "Tasa":   tasa,
                    "ID":     ln[0:5].strip(),
                    "PRECIO": tasa,
                    "FUENTE": "SV",
                })
    except Exception as e:
        logger.error(f"Error cargando SV: {e}")
        return pd.DataFrame()
    return pd.DataFrame(filas)


# ── Cargadores específicos ──────────────────────────────────────────────

def cargar_mx(fecha: str, use_cache: bool = True) -> pd.DataFrame:
    """MX = bonos renta fija internacional (Infovalmer)"""
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
        # Filtrar solo filas con fecha válida
        if "Fecha Valoracion" in df.columns:
            df = df[df["Fecha Valoracion"].str.match(r"\d{4}/\d{2}/\d{2}", na=False)]
        df["FUENTE"] = "MX"
        df["ID"] = df.get("ISIN", pd.Series(dtype=str)).str.strip()
        df["PRECIO"] = pd.to_numeric(
            df.get("Precio Sucio", df.get("Precio Limpio", pd.Series())).str.replace(",", "."),
            errors="coerce")
        return df
    except Exception as e:
        logger.error(f"Error cargando MX: {e}")
        return pd.DataFrame()


def cargar_mx_rv(fecha: str, use_cache: bool = True) -> pd.DataFrame:
    """MX_RV = renta variable internacional (ETFs, ADRs)"""
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
            df.get("Precio", pd.Series()).str.replace(",", "."), errors="coerce")
        return df
    except Exception as e:
        logger.error(f"Error cargando MX_RV: {e}")
        return pd.DataFrame()


def cargar_notas(fecha: str, use_cache: bool = True) -> pd.DataFrame:
    """NOTAS = notas estructuradas"""
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
        df["PRECIO"] = pd.to_numeric(
            df.get("Precio Sucio", df.get("Precio Limpio", pd.Series())).str.replace(",", "."),
            errors="coerce")
        return df
    except Exception as e:
        logger.error(f"Error cargando NOTAS: {e}")
        return pd.DataFrame()


def cargar_sb(fecha: str, use_cache: bool = True) -> pd.DataFrame:
    """SB = betas y curvas de descuento (Infovalmer .001)"""
    if use_cache:
        cached = _leer_cache(fecha, "SB")
        if cached is not None:
            return cached
    path = _find_file(fecha, [r"^SB\d{6}\.001$"])
    if not path:
        return pd.DataFrame()
    filas = []
    try:
        with open(path, "r", encoding="latin-1", errors="ignore") as f:
            for ln in f:
                ln = ln.rstrip("\n")
                if len(ln) > 20 and ln[5:6] == "D":
                    try:
                        filas.append({
                            "ID": ln[14:20].strip(),
                            "CURVA": ln[14:20].strip(),
                            "TASA_1": ln[20:31].strip(),
                            "TASA_2": ln[31:42].strip(),
                            "TASA_3": ln[42:53].strip(),
                            "TASA_4": ln[53:64].strip(),
                            "FUENTE": "SB",
                        })
                    except Exception:
                        continue
        df = pd.DataFrame(filas)
        df["PRECIO"] = pd.to_numeric(df["TASA_1"], errors="coerce")
        return df
    except Exception as e:
        logger.error(f"Error cargando SB: {e}")
        return pd.DataFrame()


def cargar_indicadores(fecha: str) -> pd.DataFrame:
    """Indicadores RF del día — archivo {fecha}.csv (Consulta Renta Fija).
    Nombre exacto según legacy: {yyyymmdd}.csv en carpeta downloads / data."""
    # Busca {fecha}.csv primero (nombre exacto legacy), luego fallback genérico
    path = _find_file(fecha, [rf"^{fecha}\.csv$", r"indicadores.*\.csv"])
    if not path:
        return pd.DataFrame()
    try:
        df = _read_csv_auto(path)
        if df.empty:
            return pd.DataFrame()
        df.columns = [str(c).strip() for c in df.columns]
        # Normalizar columna INDICADOR / PRECIO si existen
        ind_col = next((c for c in df.columns if c.upper() == "INDICADOR"), None)
        pre_col = next((c for c in df.columns if c.upper() == "PRECIO"), None)
        df["FUENTE"] = "IND_RF"
        if ind_col:
            df["ID"] = df[ind_col].astype(str).str.strip().str.upper()
        if pre_col:
            df["PRECIO"] = pd.to_numeric(df[pre_col].astype(str).str.replace(",", "."), errors="coerce")
        return df
    except Exception as e:
        logger.error(f"Error cargando indicadores RF: {e}")
        return pd.DataFrame()


def cargar_indicadores_rv(fecha: str) -> pd.DataFrame:
    """Indicadores RV del día — archivo RV{mmdd}.csv (Consulta Renta Variable).
    Nombre exacto según legacy: RV{mmdd}.csv donde mmdd = mes+día de fecha."""
    mmdd = fecha[4:8]  # yyyyMMDD → tomar [4:8] = MMDD
    path = _find_file(fecha, [rf"^RV{mmdd}\.csv$", r"RV\d{4}\.csv", r"rv.*\.csv"])
    if not path:
        return pd.DataFrame()
    try:
        df = _read_csv_auto(path)
        if df.empty:
            return pd.DataFrame()
        df.columns = [str(c).strip() for c in df.columns]
        ind_col = next((c for c in df.columns if c.upper() == "INDICADOR"), None)
        pre_col = next((c for c in df.columns if c.upper() == "PRECIO"), None)
        df["FUENTE"] = "IND_RV"
        if ind_col:
            df["ID"] = df[ind_col].astype(str).str.strip().str.upper()
        if pre_col:
            df["PRECIO"] = pd.to_numeric(df[pre_col].astype(str).str.replace(",", "."), errors="coerce")
        return df
    except Exception as e:
        logger.error(f"Error cargando indicadores RV: {e}")
        return pd.DataFrame()


def cargar_monedas(fecha: str, use_cache: bool = True) -> pd.DataFrame:
    """Tasas de cambio del día"""
    if use_cache:
        cached = _leer_cache(fecha, "MONEDAS")
        if cached is not None:
            return cached
    path = _find_file(fecha, [r"monedas_matriz_info.*\.csv"])
    if not path:
        # Intentar desde eurofxref
        path = _find_file(fecha, [r"eurofxref.*\.csv"])
    if not path:
        return pd.DataFrame()
    try:
        # Formato especial: primera columna es la moneda, separador mixto
        with open(path, "r", encoding="latin-1") as f:
            lines = f.readlines()
        filas = []
        for ln in lines:
            parts = re.split(r"[;,]", ln.strip())
            if len(parts) >= 2 and parts[0].strip():
                moneda = parts[0].strip()
                # Buscar la tasa (RATE es la última columna útil)
                tasa = None
                for p in reversed(parts):
                    try:
                        tasa = float(p.replace(",", ".").strip())
                        break
                    except Exception:
                        continue
                if tasa and tasa > 0:
                    filas.append({"MONEDA": moneda, "TASA_COP": tasa, "FUENTE": "TC"})
        return pd.DataFrame(filas)
    except Exception as e:
        logger.error(f"Error cargando monedas: {e}")
        return pd.DataFrame()


CARGADORES = {
    "SP":     cargar_sp,
    "SW":     cargar_sw,
    "TP":     cargar_tp,
    "SV":     cargar_sv,
    "MX":     cargar_mx,
    "MX_RV":  cargar_mx_rv,
    "NOTAS":  cargar_notas,
    "SB":     cargar_sb,
    "IND_RF": cargar_indicadores,
    "IND_RV": cargar_indicadores_rv,
}


# ── Endpoints ───────────────────────────────────────────────────────────

@router.get("/cache/{fecha}")
def estado_cache(fecha: str):
    return _cache_status(fecha)


@router.post("/convertir/{fecha}")
def convertir_insumos(
    fecha: str,
    force: bool = Query(False, description="Regenerar aunque ya exista cache"),
    excel: bool = Query(True, description="Exportar tambien archivos Excel"),
):
    """Convierte archivos crudos de Infovalmer a cache local rapido."""
    raw_loaders = {
        "SP": cargar_sp,
        "SW": cargar_sw,
        "TP": cargar_tp,
        "SV": cargar_sv,
        "MX": cargar_mx,
        "MX_RV": cargar_mx_rv,
        "NOTAS": cargar_notas,
        "SB": cargar_sb,
        "MONEDAS": cargar_monedas,
    }
    resultados = []
    for proveedor, loader in raw_loaders.items():
        pkl = _cache_path(fecha, proveedor, "pkl")
        if pkl.exists() and not force:
            cached = _leer_cache(fecha, proveedor)
            resultados.append({
                "proveedor": proveedor,
                "filas": int(len(cached)) if cached is not None else None,
                "cache_ok": True,
                "omitido": True,
                "pkl": str(pkl),
                "xlsx": str(_cache_path(fecha, proveedor, "xlsx")),
            })
            continue
        try:
            df = loader(fecha, use_cache=False)
            resultados.append(_guardar_cache(fecha, proveedor, df, export_excel=excel))
        except Exception as e:
            logger.exception(f"Error convirtiendo {proveedor} {fecha}")
            resultados.append({"proveedor": proveedor, "filas": 0, "cache_ok": False, "error": str(e)})

    return {
        "ok": all(r.get("cache_ok") for r in resultados),
        "fecha": fecha,
        "status": _cache_status(fecha),
        "resultados": resultados,
    }


@router.get("/fechas")
def get_fechas():
    return {"fechas": _fechas_disponibles()}


@router.get("/resumen/{fecha}")
def resumen_proveedores(fecha: str):
    """Cuántos títulos / curvas tiene cada proveedor."""
    resultado = []
    for nombre, fn in CARGADORES.items():
        try:
            df = fn(fecha)
            precios = pd.to_numeric(df.get("PRECIO", pd.Series()), errors="coerce").dropna() if not df.empty else pd.Series()
            resultado.append({
                "proveedor": nombre,
                "total": len(df),
                "con_precio": int(precios.count()),
                "sin_precio": int(len(df) - precios.count()),
                "precio_promedio": round(float(precios.mean()), 6) if not precios.empty else None,
                "precio_max": round(float(precios.max()), 6) if not precios.empty else None,
                "precio_min": round(float(precios.min()), 6) if not precios.empty else None,
                "disponible": not df.empty,
            })
        except Exception as e:
            resultado.append({"proveedor": nombre, "error": str(e), "total": 0,
                              "con_precio": 0, "sin_precio": 0, "disponible": False})
    return resultado


@router.get("/archivos_disponibles/{fecha}")
def archivos_disponibles(fecha: str):
    resultado = {}
    for nombre, fn in CARGADORES.items():
        try:
            df = fn(fecha)
            resultado[nombre] = {"disponible": not df.empty, "filas": len(df)}
        except Exception as e:
            resultado[nombre] = {"disponible": False, "error": str(e)}
    # También reportar monedas
    try:
        dfm = cargar_monedas(fecha)
        resultado["MONEDAS"] = {"disponible": not dfm.empty, "filas": len(dfm)}
    except Exception:
        resultado["MONEDAS"] = {"disponible": False}
    return resultado


@router.get("/mx/{fecha}")
def get_mx(
    fecha: str,
    tipo: Optional[str] = Query(None, description="Filtrar por Tipo de Instrumento"),
    moneda: Optional[str] = Query(None, description="Filtrar por Moneda"),
    busqueda: Optional[str] = Query(None),
    limit: int = Query(500),
):
    """Tabla completa de MX con todos los campos de Infovalmer."""
    df = cargar_mx(fecha)
    if df.empty:
        return []
    if tipo:
        col = next((c for c in df.columns if "tipo" in c.lower()), None)
        if col:
            df = df[df[col].str.upper().str.contains(tipo.upper(), na=False)]
    if moneda:
        col = next((c for c in df.columns if c.strip().lower() == "moneda"), None)
        if col:
            df = df[df[col].str.upper().str.contains(moneda.upper(), na=False)]
    if busqueda:
        mask = df.apply(lambda r: r.astype(str).str.upper().str.contains(busqueda.upper(), na=False).any(), axis=1)
        df = df[mask]
    return df.replace({float("nan"): None}).head(limit).to_dict(orient="records")


@router.get("/mx_rv/{fecha}")
def get_mx_rv(fecha: str, limit: int = Query(500)):
    """ETFs y acciones internacionales."""
    df = cargar_mx_rv(fecha)
    if df.empty:
        return []
    return df.replace({float("nan"): None}).head(limit).to_dict(orient="records")


@router.get("/notas/{fecha}")
def get_notas(fecha: str, limit: int = Query(200)):
    df = cargar_notas(fecha)
    if df.empty:
        return []
    return df.replace({float("nan"): None}).head(limit).to_dict(orient="records")


@router.get("/sp/{fecha}")
def get_sp(
    fecha: str,
    busqueda: Optional[str] = Query(None),
    limit: int = Query(1000),
):
    """Precios BVC renta fija local (Infovalmer SP)."""
    df = cargar_sp(fecha)
    if df.empty:
        return []
    if busqueda:
        mask = df.apply(lambda r: r.astype(str).str.upper().str.contains(busqueda.upper(), na=False).any(), axis=1)
        df = df[mask]
    return df.replace({float("nan"): None}).head(limit).to_dict(orient="records")


@router.get("/sw/{fecha}")
def get_sw(
    fecha: str,
    busqueda: Optional[str] = Query(None),
    limit: int = Query(1000),
):
    """Precios secundarios SW (Infovalmer)."""
    df = cargar_sw(fecha)
    if df.empty:
        return []
    if busqueda:
        mask = df.apply(lambda r: r.astype(str).str.upper().str.contains(busqueda.upper(), na=False).any(), axis=1)
        df = df[mask]
    return df.replace({float("nan"): None}).head(limit).to_dict(orient="records")


@router.get("/tp/{fecha}")
def get_tp(
    fecha: str,
    busqueda: Optional[str] = Query(None),
    limit: int = Query(1000),
):
    """Precios títulos participativos TP (Infovalmer)."""
    df = cargar_tp(fecha)
    if df.empty:
        return []
    if busqueda:
        mask = df.apply(lambda r: r.astype(str).str.upper().str.contains(busqueda.upper(), na=False).any(), axis=1)
        df = df[mask]
    return df.replace({float("nan"): None}).head(limit).to_dict(orient="records")


@router.get("/sv/{fecha}")
def get_sv(
    fecha: str,
    busqueda: Optional[str] = Query(None),
    limit: int = Query(500),
):
    """Tasas de interés de referencia SV (Infovalmer)."""
    df = cargar_sv(fecha)
    if df.empty:
        return []
    if busqueda:
        busq = busqueda.upper()
        mask = df.apply(lambda r: r.astype(str).str.upper().str.contains(busq, na=False).any(), axis=1)
        df = df[mask]
    return df.replace({float("nan"): None}).head(limit).to_dict(orient="records")


@router.get("/indicadores_rf/{fecha}")
def get_indicadores_rf(fecha: str, limit: int = Query(500)):
    """Indicadores Renta Fija — {fecha}.csv"""
    df = cargar_indicadores(fecha)
    if df.empty:
        return []
    return df.replace({float("nan"): None}).head(limit).to_dict(orient="records")


@router.get("/indicadores_rv/{fecha}")
def get_indicadores_rv(fecha: str, limit: int = Query(500)):
    """Indicadores Renta Variable — RV{mmdd}.csv"""
    df = cargar_indicadores_rv(fecha)
    if df.empty:
        return []
    return df.replace({float("nan"): None}).head(limit).to_dict(orient="records")


@router.get("/monedas/{fecha}")
def get_monedas(fecha: str):
    """Tasas de cambio disponibles."""
    df = cargar_monedas(fecha)
    if df.empty:
        return []
    return df.replace({float("nan"): None}).to_dict(orient="records")


@router.get("/variaciones/{fecha_inicio}/{fecha_fin}")
def variaciones_entre_fechas(
    fecha_inicio: str,
    fecha_fin: str,
    proveedor: str = Query("SP", description="SP, SW, TP, MX, MX_RV, NOTAS"),
    umbral_pct: float = Query(5.0),
):
    """Variación de precios de un proveedor entre dos fechas."""
    fn = CARGADORES.get(proveedor.upper())
    if not fn:
        raise HTTPException(400, f"Proveedor no válido. Opciones: {list(CARGADORES.keys())}")

    df_i = fn(fecha_inicio)
    df_f = fn(fecha_fin)
    if df_i.empty or df_f.empty:
        return []

    for df in [df_i, df_f]:
        df["ID"] = df["ID"].astype(str).str.strip().str.upper()
        df["PRECIO"] = pd.to_numeric(df.get("PRECIO", pd.Series()), errors="coerce")

    merged = (
        df_i[["ID", "PRECIO"]].rename(columns={"PRECIO": "PRECIO_INICIO"})
        .merge(df_f[["ID", "PRECIO"]].rename(columns={"PRECIO": "PRECIO_FIN"}), on="ID", how="inner")
    )
    merged = merged.dropna(subset=["PRECIO_INICIO", "PRECIO_FIN"])
    merged = merged[merged["PRECIO_INICIO"] != 0]

    merged["VAR_ABS"] = (merged["PRECIO_FIN"] - merged["PRECIO_INICIO"]).round(6)
    merged["VAR_PCT"] = ((merged["VAR_ABS"] / merged["PRECIO_INICIO"].abs()) * 100).round(4)
    merged["ANORMAL"] = merged["VAR_PCT"].abs() > umbral_pct
    merged = merged.sort_values("VAR_PCT", key=abs, ascending=False)
    return merged.replace({float("nan"): None}).to_dict(orient="records")


@router.get("/comparacion/{fecha}")
def comparar_proveedores(
    fecha: str,
    proveedores: str = Query("MX,NOTAS", description="Proveedores a cruzar"),
):
    """Cruza proveedores por ISIN y calcula diferencias de precio."""
    seleccionados = [p.strip().upper() for p in proveedores.split(",") if p.strip().upper() in CARGADORES]
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
    for nombre, df in list(frames.items())[1:]:
        base = base.merge(df, on="ID", how="outer")

    precio_cols = [c for c in base.columns if c.startswith("PRECIO_")]
    if len(precio_cols) >= 2:
        precios = base[precio_cols]
        base["PRECIO_MAX"] = precios.max(axis=1).round(6)
        base["PRECIO_MIN"] = precios.min(axis=1).round(6)
        base["DIF_ABS"] = (base["PRECIO_MAX"] - base["PRECIO_MIN"]).round(6)
        base["DIF_PCT"] = ((base["DIF_ABS"] / base["PRECIO_MIN"].abs()) * 100).round(4)
        base["FUENTES"] = precios.notna().sum(axis=1).astype(int)

    return base.replace({float("nan"): None}).to_dict(orient="records")


@router.get("/alertas/{fecha}")
def get_alertas_precio(
    fecha: str,
    umbral_pct: float = Query(5.0),
):
    """Detecta ISINs con variación anormal de precio entre fechas disponibles."""
    fechas = _fechas_disponibles()
    idx = fechas.index(fecha) if fecha in fechas else -1
    if idx <= 0:
        return {"alertas": [], "msg": "No hay fecha anterior disponible"}

    fecha_ant = fechas[idx - 1]
    alertas = []
    for nombre, fn in CARGADORES.items():
        if nombre in ("SB", "IND", "TP"):
            continue
        try:
            df_h = fn(fecha)
            df_a = fn(fecha_ant)
            if df_h.empty or df_a.empty:
                continue
            df_h["ID"] = df_h["ID"].astype(str).str.strip().str.upper()
            df_a["ID"] = df_a["ID"].astype(str).str.strip().str.upper()
            df_h["PRECIO"] = pd.to_numeric(df_h.get("PRECIO", pd.Series()), errors="coerce")
            df_a["PRECIO"] = pd.to_numeric(df_a.get("PRECIO", pd.Series()), errors="coerce")
            merged = df_h[["ID", "PRECIO"]].merge(
                df_a[["ID", "PRECIO"]], on="ID", suffixes=("_HOY", "_ANT"))
            merged = merged.dropna().query("PRECIO_ANT != 0")
            merged["VAR_PCT"] = ((merged["PRECIO_HOY"] - merged["PRECIO_ANT"]) / merged["PRECIO_ANT"].abs() * 100).round(4)
            anorm = merged[merged["VAR_PCT"].abs() > umbral_pct]
            for _, r in anorm.iterrows():
                alertas.append({
                    "ISIN": r["ID"], "FUENTE": nombre,
                    "PRECIO_HOY": round(r["PRECIO_HOY"], 6),
                    "PRECIO_ANT": round(r["PRECIO_ANT"], 6),
                    "VAR_PCT": round(r["VAR_PCT"], 4),
                })
        except Exception as e:
            logger.error(f"Error alertas {nombre}: {e}")

    alertas.sort(key=lambda x: abs(x["VAR_PCT"]), reverse=True)
    return {"total": len(alertas), "fecha_ant": fecha_ant, "alertas": alertas}


@router.get("/tipos_instrumento/{fecha}")
def tipos_instrumento(fecha: str):
    """Distribución de tipos de instrumento en MX."""
    df = cargar_mx(fecha)
    if df.empty:
        return []
    col = next((c for c in df.columns if "tipo" in c.lower() and "instrumento" in c.lower()), None)
    if not col:
        return []
    counts = df[col].str.strip().value_counts().reset_index()
    counts.columns = ["tipo", "cantidad"]
    return counts.to_dict(orient="records")


@router.get("/curvas/{fecha}")
def get_curvas(fecha: str):
    """Curvas de descuento del SB (Infovalmer)."""
    df = cargar_sb(fecha)
    if df.empty:
        return []
    return df.replace({float("nan"): None}).to_dict(orient="records")
