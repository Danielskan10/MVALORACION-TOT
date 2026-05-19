#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROUTER INSUMOS
Proveedores de precios: MX (renta fija internacional), MX_RV (renta variable internacional),
NOTAS (notas estructuradas), SB (betas/curvas), indicadores, monedas.
"""
from __future__ import annotations

import re
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

import pandas as pd
import numpy as np
from fastapi import APIRouter, Query, HTTPException
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_data_dir

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


def _fechas_disponibles() -> List[str]:
    base = _base_dir()
    patron = re.compile(r"^(\d{8})$")
    fechas = set()
    if not base.exists():
        return []
    for d in base.iterdir():
        if d.is_dir() and patron.match(d.name):
            fechas.add(d.name)
    patron2 = re.compile(r"(\d{8})")
    for f in base.glob("*"):
        if f.is_file():
            m = patron2.search(f.stem)
            if m:
                fechas.add(m.group(1))
    return sorted(fechas)


def _dirs(fecha: str) -> List[Path]:
    base = _base_dir()
    return [base / fecha, base]


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


# ── Cargadores específicos ──────────────────────────────────────────────

def cargar_mx(fecha: str) -> pd.DataFrame:
    """MX = bonos renta fija internacional (Infovalmer)"""
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


def cargar_mx_rv(fecha: str) -> pd.DataFrame:
    """MX_RV = renta variable internacional (ETFs, ADRs)"""
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


def cargar_notas(fecha: str) -> pd.DataFrame:
    """NOTAS = notas estructuradas"""
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


def cargar_sb(fecha: str) -> pd.DataFrame:
    """SB = betas y curvas de descuento (Infovalmer .001)"""
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
    """Indicadores RF/RV del día"""
    path = _find_file(fecha, [r"indicadores.*\.csv", r"^" + fecha + r".*\.csv"])
    if not path:
        return pd.DataFrame()
    try:
        df = _read_csv_auto(path)
        if df.empty:
            return pd.DataFrame()
        df.columns = [str(c).strip() for c in df.columns]
        df["FUENTE"] = "IND"
        return df
    except Exception as e:
        logger.error(f"Error cargando indicadores: {e}")
        return pd.DataFrame()


def cargar_monedas(fecha: str) -> pd.DataFrame:
    """Tasas de cambio del día"""
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
    "MX": cargar_mx,
    "MX_RV": cargar_mx_rv,
    "NOTAS": cargar_notas,
    "SB": cargar_sb,
    "IND": cargar_indicadores,
}


# ── Endpoints ───────────────────────────────────────────────────────────

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
    proveedor: str = Query("MX", description="MX, MX_RV, NOTAS"),
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
        if nombre in ("SB", "IND"):
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
