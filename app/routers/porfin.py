#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROUTER PORFIN (596 / 575)
Revisión de precios cargados, valoración según circular 575/596,
causaciones, errores y variaciones.
"""
from __future__ import annotations

import re
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

import pandas as pd
import numpy as np
from fastapi import APIRouter, Query, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
import io
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_data_dir

logger = logging.getLogger("porfin")
router = APIRouter()

_ROOT    = Path(__file__).parent.parent.parent
BASE_DIR = _ROOT / "data"
RAW_DIR  = _ROOT / "data"

# ── Constantes de valoración (Circular 575 / 596) ───────────────────────
TIPOS_PRECIO_LIMPIO = {
    "ACCION", "ADR", "ETF", "ACCION INTERNACIONAL", "ESTRATEGIA",
}
TIPOS_FIC = {"FIC", "FCP", "FONDO", "FICDE"}
TIPOS_FM  = {"FM", "FONDO MUTUO", "FONDOCRENA"}

UMBRAL_VAR_PCT = 5.0        # % variación anormal en precio
UMBRAL_DIF_VALORACION = 1.0  # Diferencia mínima en valoración para alertar (COP)


# ── Utilidades ──────────────────────────────────────────────────────────
def _num(x) -> Optional[float]:
    if pd.isna(x):
        return None
    try:
        return float(str(x).replace(",", ".").strip())
    except Exception:
        return None


def _dirs_busqueda(fecha: str) -> List[Path]:
    base = get_data_dir()
    return [base / fecha, base]


def _buscar_archivo_596(fecha: str) -> Optional[Path]:
    for d in _dirs_busqueda(fecha):
        if not d.exists():
            continue
        for f in list(d.glob("*.CSV")) + list(d.glob("*.csv")):
            if any(p.lower() in f.stem.lower() for p in ["596", "skcli"]):
                return f
    return None


def _buscar_archivo_575(fecha: str) -> Optional[Path]:
    for d in _dirs_busqueda(fecha):
        if not d.exists():
            continue
        for f in list(d.glob("*.CSV")) + list(d.glob("*.csv")):
            if "575" in f.stem or "fun" in f.stem.lower():
                return f
    return None


def _buscar_revision(fecha: str) -> Optional[Path]:
    for d in _dirs_busqueda(fecha):
        if not d.exists():
            continue
        for f in list(d.glob(f"*Revision*{fecha}*.xlsx")) + list(d.glob(f"*ISINES*{fecha}*.xlsx")) + list(d.glob("*Revision*.xlsx")) + list(d.glob("*ISINES*.xlsx")):
            return f
    return None


def _leer_csv_robusto(path: Path) -> pd.DataFrame:
    for sep in [",", ";", "|", "\t"]:
        try:
            df = pd.read_csv(path, sep=sep, dtype=str, encoding="latin-1", on_bad_lines="skip")
            if len(df.columns) > 2:
                df.columns = df.columns.str.strip().str.upper()
                return df
        except Exception:
            continue
    return pd.DataFrame()


def _cargar_precios_sp(fecha: str) -> Dict[str, float]:
    """Devuelve {isin: precio} desde SP (fuente Infovalmer)."""
    precios = {}
    for d in [BASE_DIR, RAW_DIR]:
        p = d / f"SP_{fecha}.xlsx"
        if p.exists():
            df = pd.read_excel(p, dtype=str, engine="openpyxl")
            df.columns = df.columns.str.strip().str.upper()
            for col_id in ["ISIN", "NEMO", "CODIGO ISIN"]:
                if col_id in df.columns:
                    for col_p in ["PRECIO_VALOR_CALCULADO", "ULTIMO_PRECIO", "PRECIO"]:
                        if col_p in df.columns:
                            for _, row in df.iterrows():
                                v = _num(row.get(col_p))
                                k = str(row.get(col_id, "")).strip().upper()
                                if k and v is not None:
                                    precios[k] = v
                            break
                    break
    return precios


def _cargar_precios_tp(fecha: str) -> Dict[str, float]:
    precios = {}
    for d in [BASE_DIR, RAW_DIR]:
        p = d / f"TP_{fecha}.xlsx"
        if not p.exists():
            p = d / f"titulos_participativos_valoracion{fecha}.txt"
        if p.exists():
            if p.suffix == ".xlsx":
                df = pd.read_excel(p, dtype=str, engine="openpyxl")
                df.columns = df.columns.str.strip().str.upper()
                col_id = next((c for c in ["ISIN", "CODIGO", "ID"] if c in df.columns), None)
                col_p  = next((c for c in ["PRECIO", "VALOR"] if c in df.columns), None)
                if col_id and col_p:
                    for _, row in df.iterrows():
                        v = _num(row.get(col_p))
                        k = str(row.get(col_id, "")).strip().upper()
                        if k and v is not None:
                            precios[k] = v
            else:
                with open(p, "r", encoding="latin-1", errors="ignore") as f:
                    for ln in f:
                        if len(ln) >= 29:
                            isin  = ln[7:19].strip().upper()
                            precio = _num(ln[19:29])
                            if isin and precio is not None:
                                precios[isin] = precio
    return precios


def _valorar_titulo(row: pd.Series, precio_t: Optional[float], moneda_t: float = 1.0) -> Optional[float]:
    """Valoración según tipo de activo (Circular 575/596)."""
    if precio_t is None:
        return None
    tipo = str(row.get("TIPO_PRODUCTO", row.get("TIPO", ""))).strip().upper()
    nominal = _num(row.get("NOMINAL", row.get("VLR_MER_OR", row.get("VALOR_NOMINAL", 0))))
    if nominal is None or nominal == 0:
        return None

    tipo_upper = tipo.upper()
    if any(t in tipo_upper for t in TIPOS_FM):
        return nominal * moneda_t * precio_t
    if any(t in tipo_upper for t in TIPOS_FIC):
        return nominal * precio_t
    if any(t in tipo_upper for t in TIPOS_PRECIO_LIMPIO):
        return nominal * moneda_t * precio_t
    # Renta fija por defecto → precio / 100
    return nominal * moneda_t * (precio_t / 100.0)


# ── Endpoints ───────────────────────────────────────────────────────────
@router.get("/fechas")
def get_fechas():
    patron = re.compile(r"(\d{8})")
    fechas = set()
    for d in [RAW_DIR, BASE_DIR]:
        for ext in ["*.xlsx", "*.csv", "*.CSV"]:
            for f in d.glob(ext):
                m = patron.search(f.stem)
                if m:
                    fechas.add(m.group(1))
    return {"fechas": sorted(fechas)}


@router.get("/resumen/{fecha}")
def resumen_porfin(fecha: str):
    """
    Resumen general de la carga 596 para una fecha:
    - Total posiciones
    - Posiciones con/sin precio
    - Distribución por tipo
    - Alertas de valoración
    """
    path_596 = _buscar_archivo_596(fecha)
    if not path_596:
        # Buscar revisión pre-generada
        path_rev = _buscar_revision(fecha)
        if path_rev:
            df = pd.read_excel(path_rev, dtype=str, engine="openpyxl")
            df.columns = df.columns.str.strip().str.upper()
        else:
            return {"error": f"No se encontró archivo 596 ni revisión para {fecha}",
                    "fecha": fecha, "total": 0}
    else:
        df = _leer_csv_robusto(path_596)

    if df.empty:
        return {"error": "Archivo vacío", "fecha": fecha}

    # Normalizar columnas clave
    for alias, canonical in [
        ("TIPO DE PRODUCTO", "TIPO"), ("TIPO_PRODUCTO", "TIPO"),
        ("VLR MER. HOY", "VALORACION_HOY"), ("VLR. MER. HOY", "VALORACION_HOY"),
        ("VLR MER. ANT", "VALORACION_ANT"), ("VLR. MER. ANT", "VALORACION_ANT"),
        ("VALOR NOMINAL", "NOMINAL"), ("VLR NOMINAL", "NOMINAL"),
    ]:
        if alias in df.columns and canonical not in df.columns:
            df = df.rename(columns={alias: canonical})

    total = len(df)

    # Tipos
    tipo_dist = {}
    if "TIPO" in df.columns:
        tipo_dist = df["TIPO"].fillna("SIN TIPO").value_counts().to_dict()

    # Valoración
    val_hoy = pd.to_numeric(df.get("VALORACION_HOY", pd.Series()), errors="coerce")
    val_ant = pd.to_numeric(df.get("VALORACION_ANT", pd.Series()), errors="coerce")

    variaciones = []
    if not val_hoy.empty and not val_ant.empty:
        diff = (val_hoy - val_ant).abs()
        pct  = ((val_hoy - val_ant) / val_ant.abs().replace(0, np.nan) * 100)
        alertas = df[pct.abs() > UMBRAL_VAR_PCT].copy()
        alertas["VAR_PCT"] = pct[alertas.index].round(4)
        alertas["VAR_ABS"] = diff[alertas.index].round(2)
        variaciones = alertas.replace({float("nan"): None}).head(100).to_dict(orient="records")

    return {
        "fecha": fecha,
        "total_posiciones": total,
        "distribucion_tipo": tipo_dist,
        "suma_valoracion_hoy": round(float(val_hoy.sum()), 2) if not val_hoy.empty else None,
        "suma_valoracion_ant": round(float(val_ant.sum()), 2) if not val_ant.empty else None,
        "alertas_variacion": variaciones[:20],
        "total_alertas": len(variaciones),
    }


@router.get("/posiciones/{fecha}")
def posiciones_porfin(
    fecha: str,
    tipo: Optional[str] = Query(None, description="Filtro por tipo de activo"),
    busqueda: Optional[str] = Query(None, description="Buscar por ISIN/NEMO"),
    solo_alertas: bool = Query(False, description="Sólo posiciones con alerta"),
):
    """Lista completa de posiciones del 596 con precios y valoraciones."""
    path = _buscar_archivo_596(fecha)
    path_rev = _buscar_revision(fecha)

    if path_rev:
        df = pd.read_excel(path_rev, dtype=str, engine="openpyxl")
        df.columns = df.columns.str.strip().str.upper()
        df["FUENTE_ARCHIVO"] = "REVISION"
    elif path:
        df = _leer_csv_robusto(path)
        df["FUENTE_ARCHIVO"] = "596"
    else:
        return []

    # Normalizar aliases
    rename_map = {
        "TIPO DE PRODUCTO": "TIPO", "TIPO_PRODUCTO": "TIPO",
        "VLR MER. HOY": "VALORACION_HOY", "VLR. MER. HOY": "VALORACION_HOY",
        "VLR MER. ANT": "VALORACION_ANT", "VLR. MER. ANT": "VALORACION_ANT",
        "VALOR NOMINAL": "NOMINAL", "VLR NOMINAL": "NOMINAL",
        "NEMOTÉCNICO BOL": "NEMO", "NEMOTECNICO BOL": "NEMO",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    # Cargar precios de Infovalmer
    precios_sp = _cargar_precios_sp(fecha)
    precios_tp = _cargar_precios_tp(fecha)

    # Asignar precio
    def _get_precio(row):
        isin = str(row.get("ISIN", "")).strip().upper()
        nemo = str(row.get("NEMO", "")).strip().upper()
        return precios_sp.get(isin) or precios_sp.get(nemo) or precios_tp.get(isin) or precios_tp.get(nemo)

    df["PRECIO_INFOVALMER"] = df.apply(_get_precio, axis=1)

    # Valoración calculada
    df["VALORACION_CALCULADA"] = df.apply(lambda r: _valorar_titulo(r, r["PRECIO_INFOVALMER"]), axis=1)
    df["VALORACION_HOY_NUM"] = pd.to_numeric(df.get("VALORACION_HOY", pd.Series(dtype=str)), errors="coerce")
    df["DIF_VALORACION"] = (df["VALORACION_CALCULADA"] - df["VALORACION_HOY_NUM"]).round(2)

    # Observaciones
    def _obs(row):
        obs = []
        if pd.isna(row.get("PRECIO_INFOVALMER")):
            obs.append("SIN PRECIO INFOVALMER")
        dif = row.get("DIF_VALORACION")
        if dif is not None and not pd.isna(dif) and abs(dif) > UMBRAL_DIF_VALORACION:
            obs.append(f"DIF VALORACION: {dif:,.2f}")
        return " | ".join(obs) if obs else "OK"

    df["OBSERVACION"] = df.apply(_obs, axis=1)

    # Filtros
    if tipo:
        if "TIPO" in df.columns:
            df = df[df["TIPO"].astype(str).str.upper().str.contains(tipo.upper(), na=False)]
    if busqueda:
        mask = pd.Series(False, index=df.index)
        for c in ["ISIN", "NEMO", "TITULO"]:
            if c in df.columns:
                mask = mask | df[c].astype(str).str.upper().str.contains(busqueda.upper(), na=False)
        df = df[mask]
    if solo_alertas:
        df = df[df["OBSERVACION"] != "OK"]

    cols_salida = [c for c in [
        "ISIN", "NEMO", "TIPO", "NOMINAL", "VALORACION_HOY", "VALORACION_ANT",
        "PRECIO_INFOVALMER", "VALORACION_CALCULADA", "DIF_VALORACION", "OBSERVACION",
        "FUENTE_ARCHIVO"
    ] if c in df.columns]

    return df[cols_salida].replace({float("nan"): None}).head(1000).to_dict(orient="records")


@router.get("/causaciones/{fecha}")
def causaciones_porfin(fecha: str, fecha_ant: Optional[str] = Query(None)):
    """
    Revisa causaciones del 575: DI vs DF, signos, diferencias con Porfin.
    """
    path_575 = _buscar_archivo_575(fecha)
    if not path_575:
        return {"error": f"No se encontró archivo 575 para {fecha}"}

    df = _leer_csv_robusto(path_575)
    if df.empty:
        return {"error": "Archivo 575 vacío"}

    # Aliases
    rename_map = {
        "VLR NOMINAL": "NOMINAL", "VALOR NOMINAL": "NOMINAL",
        "VLR MER. ANT": "VALORACION_ANT", "VLR MER. HOY": "VALORACION_HOY",
        "CAUSACIÓN MER": "CAUSACION", "CAUSACION MER": "CAUSACION",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    for c in ["VALORACION_HOY", "VALORACION_ANT", "CAUSACION", "NOMINAL"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", "."), errors="coerce")

    if "VALORACION_HOY" in df.columns and "VALORACION_ANT" in df.columns:
        df["CAUSACION_CALCULADA"] = (df["VALORACION_HOY"] - df["VALORACION_ANT"]).round(2)
        if "CAUSACION" in df.columns:
            df["DIF_CAUSACION"] = (df["CAUSACION"] - df["CAUSACION_CALCULADA"]).round(2)
            df["ALERTA_CAUSACION"] = df["DIF_CAUSACION"].abs() > UMBRAL_DIF_VALORACION

    alertas = df[df.get("ALERTA_CAUSACION", pd.Series(False, index=df.index))] if "ALERTA_CAUSACION" in df.columns else pd.DataFrame()

    return {
        "fecha": fecha,
        "total_registros": len(df),
        "total_alertas": len(alertas),
        "suma_causacion": round(float(df["CAUSACION"].sum()), 2) if "CAUSACION" in df.columns else None,
        "suma_causacion_calculada": round(float(df["CAUSACION_CALCULADA"].sum()), 2) if "CAUSACION_CALCULADA" in df.columns else None,
        "alertas": alertas.replace({float("nan"): None}).head(100).to_dict(orient="records"),
        "detalle": df.replace({float("nan"): None}).head(500).to_dict(orient="records"),
    }


@router.get("/variaciones/{fecha_inicio}/{fecha_fin}")
def variaciones_porfin(fecha_inicio: str, fecha_fin: str, umbral: float = Query(5.0)):
    """Variaciones de valoración entre dos fechas en 596."""
    def _cargar(fecha):
        p = _buscar_archivo_596(fecha) or _buscar_revision(fecha)
        if not p:
            return pd.DataFrame()
        if p.suffix == ".xlsx":
            df = pd.read_excel(p, dtype=str, engine="openpyxl")
        else:
            df = _leer_csv_robusto(p)
        df.columns = df.columns.str.strip().str.upper()
        for alias, canon in [
            ("VLR MER. HOY", "VALORACION_HOY"), ("VLR. MER. HOY", "VALORACION_HOY"),
            ("NEMOTÉCNICO BOL", "NEMO"), ("NEMOTECNICO BOL", "NEMO"),
            ("TIPO DE PRODUCTO", "TIPO"),
        ]:
            if alias in df.columns and canon not in df.columns:
                df = df.rename(columns={alias: canon})
        return df

    df_i = _cargar(fecha_inicio)
    df_f = _cargar(fecha_fin)
    if df_i.empty or df_f.empty:
        return []

    col_id = next((c for c in ["ISIN", "NEMO"] if c in df_i.columns and c in df_f.columns), None)
    if not col_id:
        return []

    df_i[col_id] = df_i[col_id].astype(str).str.strip().str.upper()
    df_f[col_id] = df_f[col_id].astype(str).str.strip().str.upper()
    df_i["VAL_I"] = pd.to_numeric(df_i.get("VALORACION_HOY", pd.Series()), errors="coerce")
    df_f["VAL_F"] = pd.to_numeric(df_f.get("VALORACION_HOY", pd.Series()), errors="coerce")

    merged = df_i[[col_id, "VAL_I"]].merge(df_f[[col_id, "VAL_F"]], on=col_id, how="inner")
    merged = merged.dropna(subset=["VAL_I", "VAL_F"])
    merged = merged[merged["VAL_I"] != 0]
    merged["VAR_ABS"] = (merged["VAL_F"] - merged["VAL_I"]).round(2)
    merged["VAR_PCT"] = ((merged["VAR_ABS"] / merged["VAL_I"].abs()) * 100).round(4)
    merged["ANORMAL"] = merged["VAR_PCT"].abs() > umbral
    merged = merged.rename(columns={col_id: "ID"})
    return merged.replace({float("nan"): None}).sort_values("VAR_PCT", key=abs, ascending=False).to_dict(orient="records")


@router.get("/errores/{fecha}")
def errores_porfin(fecha: str):
    """
    Detección automática de errores: precios faltantes, tipos no reconocidos,
    nominales en cero, valoraciones negativas.
    """
    path = _buscar_archivo_596(fecha) or _buscar_revision(fecha)
    if not path:
        return {"error": f"No se encontró archivo para {fecha}"}

    if path.suffix == ".xlsx":
        df = pd.read_excel(path, dtype=str, engine="openpyxl")
    else:
        df = _leer_csv_robusto(path)
    df.columns = df.columns.str.strip().str.upper()

    for alias, canon in [
        ("TIPO DE PRODUCTO", "TIPO"), ("VLR MER. HOY", "VALORACION_HOY"),
        ("VALOR NOMINAL", "NOMINAL"), ("NEMOTÉCNICO BOL", "NEMO"),
    ]:
        if alias in df.columns and canon not in df.columns:
            df = df.rename(columns={alias: canon})

    errores: List[Dict] = []

    # Sin precio Infovalmer
    precios_sp = _cargar_precios_sp(fecha)
    precios_tp = _cargar_precios_tp(fecha)
    precios_todos = {**precios_sp, **precios_tp}

    if "ISIN" in df.columns:
        sin_precio = df[~df["ISIN"].astype(str).str.upper().isin(precios_todos.keys())]
        for _, row in sin_precio.iterrows():
            isin = str(row.get("ISIN", "")).strip()
            if isin and isin.upper() != "NAN":
                errores.append({
                    "tipo_error": "SIN PRECIO",
                    "isin": isin,
                    "nemo": row.get("NEMO", ""),
                    "tipo_activo": row.get("TIPO", ""),
                    "detalle": "No se encontró precio en SP ni TP",
                    "severidad": "ALTO",
                })

    # Valoración negativa
    if "VALORACION_HOY" in df.columns:
        val = pd.to_numeric(df["VALORACION_HOY"].astype(str).str.replace(",", "."), errors="coerce")
        neg = df[val < 0]
        for _, row in neg.iterrows():
            errores.append({
                "tipo_error": "VALORACION NEGATIVA",
                "isin": row.get("ISIN", ""),
                "nemo": row.get("NEMO", ""),
                "tipo_activo": row.get("TIPO", ""),
                "detalle": f"Valoración: {row.get('VALORACION_HOY', '')}",
                "severidad": "ALTO",
            })

    # Nominal cero o nulo
    if "NOMINAL" in df.columns:
        nom = pd.to_numeric(df["NOMINAL"].astype(str).str.replace(",", "."), errors="coerce")
        sin_nom = df[nom.isna() | (nom == 0)]
        for _, row in sin_nom.head(50).iterrows():
            errores.append({
                "tipo_error": "NOMINAL CERO/NULO",
                "isin": row.get("ISIN", ""),
                "nemo": row.get("NEMO", ""),
                "tipo_activo": row.get("TIPO", ""),
                "detalle": "Nominal igual a cero o nulo",
                "severidad": "MEDIO",
            })

    resumen_severidad = {
        "ALTO": len([e for e in errores if e["severidad"] == "ALTO"]),
        "MEDIO": len([e for e in errores if e["severidad"] == "MEDIO"]),
        "BAJO": len([e for e in errores if e["severidad"] == "BAJO"]),
    }

    return {
        "fecha": fecha,
        "total_errores": len(errores),
        "resumen_severidad": resumen_severidad,
        "errores": errores[:200],
    }
