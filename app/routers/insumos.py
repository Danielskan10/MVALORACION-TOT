#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROUTER INSUMOS
Comparación de proveedores de precios: SP, TP, SW, MX, NOTAS
Variaciones diarias, conteos, diferencias entre fuentes
"""
from __future__ import annotations

import re
import logging
from pathlib import Path
from functools import lru_cache
from typing import Optional, List, Dict, Any

import pandas as pd
import numpy as np
from fastapi import APIRouter, Query, HTTPException
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_data_dir

logger = logging.getLogger("insumos")
router = APIRouter()

def _base_dir() -> Path:
    return get_data_dir()

# Para compatibilidad con código que usa BASE_DIR directamente
_ROOT    = Path(__file__).parent.parent.parent
BASE_DIR = _ROOT / "data"

# ── Utilidades ──────────────────────────────────────────────────────────
def _num(x):
    try:
        return float(str(x).replace(",", ".").strip())
    except Exception:
        return None


def _fechas_disponibles() -> List[str]:
    base = _base_dir()
    patron = re.compile(r"^(\d{8})$")
    fechas = set()
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


def _buscar_archivo(fecha: str, prefijos: List[str], dirs: Optional[List[Path]] = None) -> Optional[Path]:
    base = _base_dir()
    fecha_dirs = [base / fecha, base]
    dirs = dirs or fecha_dirs
    for d in dirs:
        if not d.exists():
            continue
        for pref in prefijos:
            for ext in [".xlsx", ".csv", ".txt", ".001"]:
                p = d / f"{pref}_{fecha}{ext}"
                if p.exists():
                    return p
                p2 = d / f"{pref}{fecha}{ext}"
                if p2.exists():
                    return p2
                # Sin fecha en nombre (para archivos ya dentro de la carpeta fecha)
                p3 = d / f"{pref}{ext}"
                if p3.exists():
                    return p3
    return None


def _leer_excel_flexible(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path, engine="openpyxl", dtype=str)
    df.columns = df.columns.str.strip().str.upper()
    return df


def _leer_csv_flexible(path: Path) -> pd.DataFrame:
    for sep in [",", ";", "|", "\t"]:
        try:
            df = pd.read_csv(path, sep=sep, dtype=str, encoding="latin-1", on_bad_lines="skip")
            if len(df.columns) > 1:
                df.columns = df.columns.str.strip().str.upper()
                return df
        except Exception:
            continue
    return pd.DataFrame()


def _normalizar_precio(df: pd.DataFrame, cols_precio: List[str]) -> pd.Series:
    for c in cols_precio:
        if c in df.columns:
            return pd.to_numeric(df[c].str.replace(",", ".", regex=False), errors="coerce")
    return pd.Series(dtype=float)


def _col_id(df: pd.DataFrame) -> Optional[str]:
    for c in ["ISIN", "CODIGO ISIN", "NEMO", "NEMOTECNICO", "NEMOTÉCNICO", "LLAVE", "TITULO"]:
        if c in df.columns:
            return c
    return None


# ── Carga de cada proveedor ─────────────────────────────────────────────
def cargar_sp(fecha: str) -> pd.DataFrame:
    """SP = proveedor acciones / renta fija (Infovalmer .001 convertido a xlsx)"""
    path = _buscar_archivo(fecha, ["SP"])
    if not path:
        return pd.DataFrame()
    df = _leer_excel_flexible(path) if path.suffix == ".xlsx" else pd.DataFrame()
    if df.empty and path.suffix in [".001", ".txt"]:
        filas = []
        with open(path, "r", encoding="latin-1", errors="ignore") as f:
            for ln in f:
                if len(ln) > 168:
                    filas.append({
                        "ISIN": ln[8:20].strip(),
                        "NEMO": ln[20:32].strip(),
                        "PRECIO_T": ln[110:129].strip(),
                        "PRECIO_LIMPIO": ln[168:187].strip() if len(ln) > 187 else "",
                        "FUENTE": "SP",
                    })
        df = pd.DataFrame(filas)
    else:
        col_id = _col_id(df)
        precio = _normalizar_precio(df, ["PRECIO_VALOR_CALCULADO", "ULTIMO_PRECIO", "PRECIO", "VALOR"])
        df = df.rename(columns={col_id: "ID"}) if col_id else df
        df["PRECIO_T"] = precio
        df["FUENTE"] = "SP"
    if "ID" not in df.columns and "ISIN" in df.columns:
        df["ID"] = df["ISIN"]
    elif "ID" not in df.columns and "NEMO" in df.columns:
        df["ID"] = df["NEMO"]
    return df[df["ID"].astype(str).str.strip().ne("")]


def cargar_sw(fecha: str) -> pd.DataFrame:
    """SW = proveedor monedas/swaps"""
    path = _buscar_archivo(fecha, ["SW"])
    if not path:
        return pd.DataFrame()
    if path.suffix == ".xlsx":
        df = _leer_excel_flexible(path)
        col_id = _col_id(df)
        precio = _normalizar_precio(df, ["VALOR", "PRECIO", "PRECIO_T"])
        df["ID"] = df[col_id] if col_id else ""
        df["PRECIO_T"] = precio
    else:
        patron = re.compile(r"^(\d+)([A-Z])([A-Z0-9\-]+)\s+(\d{4}-\d{2}-\d{2})(.+)$")
        filas = []
        with open(path, "r", encoding="latin-1", errors="ignore") as f:
            for ln in f:
                m = patron.match(ln.strip())
                if m:
                    val = re.sub(r"[^\d.]", "", m.group(5))
                    filas.append({"ID": m.group(3), "NEMO": m.group(3),
                                  "PRECIO_T": float(val) if val else None, "FUENTE": "SW"})
        df = pd.DataFrame(filas)
    df["FUENTE"] = "SW"
    return df[df["ID"].astype(str).str.strip().ne("")]


def cargar_mx(fecha: str) -> pd.DataFrame:
    """MX = bonos renta fija"""
    path = _buscar_archivo(fecha, ["MX", "MX_RV"])
    if not path:
        return pd.DataFrame()
    if path.suffix == ".xlsx":
        df = _leer_excel_flexible(path)
    else:
        df = _leer_csv_flexible(path)
    col_id = _col_id(df)
    precio = _normalizar_precio(df, ["PRECIO", "PRECIO_T", "ULTIMO_PRECIO", "VALOR"])
    df["ID"] = df[col_id] if col_id else ""
    df["PRECIO_T"] = precio
    df["FUENTE"] = "MX"
    return df[df["ID"].astype(str).str.strip().ne("")]


def cargar_tp(fecha: str) -> pd.DataFrame:
    """TP = títulos participativos"""
    path = _buscar_archivo(fecha, ["TP"])
    if not path:
        return pd.DataFrame()
    if path.suffix == ".xlsx":
        df = _leer_excel_flexible(path)
        col_id = _col_id(df)
        precio = _normalizar_precio(df, ["PRECIO", "PRECIO_T", "VALOR"])
        df["ID"] = df[col_id] if col_id else ""
        df["PRECIO_T"] = precio
    else:
        filas = []
        with open(path, "r", encoding="latin-1", errors="ignore") as f:
            for ln in f:
                if len(ln) >= 29:
                    filas.append({"ID": ln[7:19].strip(), "ISIN": ln[7:19].strip(),
                                  "PRECIO_T": _num(ln[19:29].strip()), "FUENTE": "TP"})
        df = pd.DataFrame(filas)
    df["FUENTE"] = "TP"
    return df[df["ID"].astype(str).str.strip().ne("")]


def cargar_notas(fecha: str) -> pd.DataFrame:
    """NOTAS = notas estructuradas"""
    path = _buscar_archivo(fecha, ["NOTAS_ESTRUCTURADAS", "NOTAS"])
    if not path:
        return pd.DataFrame()
    df = _leer_excel_flexible(path) if path.suffix == ".xlsx" else _leer_csv_flexible(path)
    col_id = _col_id(df)
    precio = _normalizar_precio(df, ["PRECIO", "PRECIO_T", "VALOR"])
    df["ID"] = df[col_id] if col_id else ""
    df["PRECIO_T"] = precio
    df["FUENTE"] = "NOTAS"
    return df[df["ID"].astype(str).str.strip().ne("")]


CARGADORES = {"SP": cargar_sp, "SW": cargar_sw, "MX": cargar_mx, "TP": cargar_tp, "NOTAS": cargar_notas}


# ── Endpoints ───────────────────────────────────────────────────────────
@router.get("/fechas")
def get_fechas():
    return {"fechas": _fechas_disponibles()}


@router.get("/resumen/{fecha}")
def resumen_proveedores(fecha: str):
    """Cuántos títulos tiene cada proveedor en una fecha."""
    resultado = []
    for nombre, fn in CARGADORES.items():
        try:
            df = fn(fecha)
            precios = pd.to_numeric(df.get("PRECIO_T", pd.Series()), errors="coerce").dropna()
            resultado.append({
                "proveedor": nombre,
                "total_titulos": len(df),
                "con_precio": int(precios.count()),
                "sin_precio": int(len(df) - precios.count()),
                "precio_promedio": round(precios.mean(), 6) if not precios.empty else None,
                "precio_max": round(precios.max(), 6) if not precios.empty else None,
                "precio_min": round(precios.min(), 6) if not precios.empty else None,
            })
        except Exception as e:
            resultado.append({"proveedor": nombre, "error": str(e),
                              "total_titulos": 0, "con_precio": 0, "sin_precio": 0})
    return resultado


@router.get("/comparacion/{fecha}")
def comparar_proveedores(
    fecha: str,
    proveedores: str = Query("SP,SW,MX,TP", description="Proveedores a comparar separados por coma"),
):
    """
    Cruza los proveedores seleccionados por ID y calcula diferencias de precio.
    Devuelve tabla con precio de cada fuente y variación entre ellas.
    """
    seleccionados = [p.strip().upper() for p in proveedores.split(",") if p.strip().upper() in CARGADORES]
    if len(seleccionados) < 1:
        raise HTTPException(400, "Selecciona al menos un proveedor válido")

    frames: Dict[str, pd.DataFrame] = {}
    for nombre in seleccionados:
        df = CARGADORES[nombre](fecha)
        if df.empty:
            continue
        df["ID"] = df["ID"].astype(str).str.strip().str.upper()
        df["PRECIO_T"] = pd.to_numeric(df.get("PRECIO_T", pd.Series()), errors="coerce")
        frames[nombre] = df[["ID", "PRECIO_T"]].rename(columns={"PRECIO_T": f"PRECIO_{nombre}"})

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
        base["FUENTES_DISPONIBLES"] = precios.notna().sum(axis=1).astype(int)

    return base.replace({float("nan"): None}).to_dict(orient="records")


@router.get("/variaciones/{fecha_inicio}/{fecha_fin}")
def variaciones_entre_fechas(
    fecha_inicio: str,
    fecha_fin: str,
    proveedor: str = Query("SP", description="Proveedor: SP, SW, MX, TP, NOTAS"),
    umbral_pct: float = Query(5.0, description="Umbral % para marcar variación anormal"),
):
    """Variación de precios de un proveedor entre dos fechas."""
    if proveedor.upper() not in CARGADORES:
        raise HTTPException(400, f"Proveedor no válido. Opciones: {list(CARGADORES.keys())}")
    fn = CARGADORES[proveedor.upper()]

    df_i = fn(fecha_inicio)
    df_f = fn(fecha_fin)
    if df_i.empty or df_f.empty:
        return []

    df_i["ID"] = df_i["ID"].astype(str).str.strip().str.upper()
    df_f["ID"] = df_f["ID"].astype(str).str.strip().str.upper()
    df_i["PRECIO_T"] = pd.to_numeric(df_i.get("PRECIO_T", pd.Series()), errors="coerce")
    df_f["PRECIO_T"] = pd.to_numeric(df_f.get("PRECIO_T", pd.Series()), errors="coerce")

    merged = df_i[["ID", "PRECIO_T"]].rename(columns={"PRECIO_T": "PRECIO_INICIO"}).merge(
        df_f[["ID", "PRECIO_T"]].rename(columns={"PRECIO_T": "PRECIO_FIN"}), on="ID", how="inner"
    )
    merged = merged.dropna(subset=["PRECIO_INICIO", "PRECIO_FIN"])
    merged = merged[merged["PRECIO_INICIO"] != 0]

    merged["VAR_ABS"] = (merged["PRECIO_FIN"] - merged["PRECIO_INICIO"]).round(6)
    merged["VAR_PCT"] = ((merged["VAR_ABS"] / merged["PRECIO_INICIO"].abs()) * 100).round(4)
    merged["ANORMAL"] = merged["VAR_PCT"].abs() > umbral_pct

    merged = merged.sort_values("VAR_PCT", key=abs, ascending=False)
    return merged.replace({float("nan"): None}).to_dict(orient="records")


@router.get("/titulos/{fecha}")
def listar_titulos(
    fecha: str,
    proveedor: str = Query("SP"),
    busqueda: Optional[str] = Query(None),
):
    """Lista todos los títulos de un proveedor para una fecha."""
    if proveedor.upper() not in CARGADORES:
        raise HTTPException(400, "Proveedor inválido")
    df = CARGADORES[proveedor.upper()](fecha)
    if df.empty:
        return []
    if busqueda:
        mask = df["ID"].astype(str).str.upper().str.contains(busqueda.upper(), na=False)
        df = df[mask]
    df["PRECIO_T"] = pd.to_numeric(df.get("PRECIO_T", pd.Series()), errors="coerce")
    cols = [c for c in ["ID", "ISIN", "NEMO", "PRECIO_T", "FUENTE"] if c in df.columns]
    return df[cols].replace({float("nan"): None}).head(500).to_dict(orient="records")


@router.get("/archivos_disponibles/{fecha}")
def archivos_disponibles(fecha: str):
    """Qué archivos fuente existen para esa fecha."""
    resultado = {}
    for nombre, fn in CARGADORES.items():
        try:
            df = fn(fecha)
            resultado[nombre] = {"disponible": not df.empty, "filas": len(df)}
        except Exception as e:
            resultado[nombre] = {"disponible": False, "error": str(e)}
    return resultado
