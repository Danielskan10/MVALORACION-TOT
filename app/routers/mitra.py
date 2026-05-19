#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROUTER MITRA
Revisión del archivo base Mitra: VALORACION_DI/DF, causaciones, fuentes de precio,
diferencias vs Porfin, observaciones, monedas.
"""
from __future__ import annotations

import re
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

import pandas as pd
import numpy as np
from fastapi import APIRouter, Query, HTTPException

logger = logging.getLogger("mitra")
router = APIRouter()

_ROOT    = Path(__file__).parent.parent.parent
BASE_DIR = _ROOT / "data"
RAW_DIR  = _ROOT / "data"

UMBRAL_VAR_PRECIO  = 5.0    # %
UMBRAL_DIF_CAUSAC  = 1.0    # COP

# ── Utilidades ──────────────────────────────────────────────────────────
def _num(x) -> Optional[float]:
    if pd.isna(x):
        return None
    try:
        return float(str(x).replace(",", ".").strip())
    except Exception:
        return None


def _dirs_busqueda(fecha: str) -> List[Path]:
    return [BASE_DIR / fecha, BASE_DIR]


def _buscar_mitra(fecha: str) -> Optional[Path]:
    for d in _dirs_busqueda(fecha):
        if not d.exists():
            continue
        for ext in ["*.xlsx", "*.csv", "*.CSV"]:
            for f in d.glob(ext):
                stem = f.stem.upper()
                if "MITRA" in stem or "FIDU" in stem or "FIDUCIARIA" in stem:
                    return f
        for f in d.glob("*Revision*bolsa*.xlsx"):
            return f
    return None


def _buscar_revision_bolsa(fecha: str) -> Optional[Path]:
    for d in _dirs_busqueda(fecha):
        if not d.exists():
            continue
        for f in list(d.glob(f"*bolsa*{fecha}*.xlsx")) + list(d.glob("*bolsa*.xlsx")) + list(d.glob("*Revision_cargue_bolsa*.xlsx")):
            return f
    return None


def _leer_excel_robusto(path: Path) -> pd.DataFrame:
    for sheet in [0, "Hoja1", "Sheet1", "MITRA", "DATA"]:
        try:
            df = pd.read_excel(path, sheet_name=sheet, dtype=str, engine="openpyxl")
            df.columns = df.columns.str.strip().str.upper()
            if len(df) > 0:
                return df
        except Exception:
            continue
    return pd.DataFrame()


def _normalizar_mitra(df: pd.DataFrame) -> pd.DataFrame:
    aliases = {
        "CÓDIGO ISIN CONTRATO": "ISIN", "CODIGO ISIN CONTRATO": "ISIN",
        "NÍVEL 3 - PRODUTO": "TITULO", "NIVEL 3 - PRODUTO": "TITULO",
        "NÍVEL 3 - PRODUCTO": "TITULO", "NIVEL 3 - PRODUCTO": "TITULO",
        "TIPO DE PRODUCTO": "TIPO", "TIPO_PRODUCTO": "TIPO",
        "MARCADO ACTIVO": "MARCADO_ACTIVO",
        "FUENTE_PRECIO": "FUENTE", "FUENTE PRECIO": "FUENTE",
        "VALOR NOMINAL DI": "NOMINAL_DI", "VALOR NOMINAL DF": "NOMINAL_DF",
        "FINANCEIRO ATIVO DI": "FINANCIERO_DI", "FINANCIERO ACTIVO DI": "FINANCIERO_DI",
        "FINANCEIRO ATIVO DF": "FINANCIERO_DF", "FINANCIERO ACTIVO DF": "FINANCIERO_DF",
        "MONEDA PRODUCTO": "MONEDA",
        "DI - DF": "CAUSACION",
    }
    df = df.rename(columns={k: v for k, v in aliases.items() if k in df.columns})

    # Numéricos
    for c in ["PRECIO_T", "PRECIO_Y", "VALORACION_DI", "VALORACION_DF",
              "CAUSACION", "NOMINAL_DI", "NOMINAL_DF", "FINANCIERO_DI", "FINANCIERO_DF",
              "MONEDA_DI", "MONEDA_DF", "MONEDA"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", "."), errors="coerce")

    return df


# ── Endpoints ───────────────────────────────────────────────────────────
@router.get("/fechas")
def get_fechas():
    patron = re.compile(r"(\d{8})")
    fechas = set()
    for d in [RAW_DIR, BASE_DIR]:
        for ext in ["*.xlsx", "*.csv"]:
            for f in d.glob(ext):
                m = patron.search(f.stem)
                if m:
                    fechas.add(m.group(1))
    return {"fechas": sorted(fechas)}


@router.get("/resumen/{fecha}")
def resumen_mitra(fecha: str):
    """
    Resumen del archivo Mitra para una fecha:
    - Total posiciones, tipos de activo
    - Suma de causaciones DI/DF
    - Alertas (variaciones de precio, diferencias de causación)
    - Fuentes de precio utilizadas
    """
    path = _buscar_mitra(fecha) or _buscar_revision_bolsa(fecha)
    if not path:
        return {"error": f"No se encontró archivo Mitra para {fecha}", "fecha": fecha}

    df = _leer_excel_robusto(path)
    if df.empty:
        return {"error": "Archivo vacío", "fecha": fecha}

    df = _normalizar_mitra(df)

    total = len(df)
    tipo_dist = df["TIPO"].fillna("SIN TIPO").value_counts().to_dict() if "TIPO" in df.columns else {}
    fuente_dist = df["FUENTE"].fillna("SIN FUENTE").value_counts().to_dict() if "FUENTE" in df.columns else {}

    suma_val_di = round(float(df["VALORACION_DI"].sum()), 2) if "VALORACION_DI" in df.columns else None
    suma_val_df = round(float(df["VALORACION_DF"].sum()), 2) if "VALORACION_DF" in df.columns else None
    suma_causac = round(float(df["CAUSACION"].sum()), 2) if "CAUSACION" in df.columns else None

    # Causación calculada
    if "VALORACION_DF" in df.columns and "VALORACION_DI" in df.columns:
        df["CAUSACION_CALC"] = df["VALORACION_DF"] - df["VALORACION_DI"]
        if "CAUSACION" in df.columns:
            df["DIF_CAUSACION"] = (df["CAUSACION"] - df["CAUSACION_CALC"]).abs()
            n_alertas_causac = int((df["DIF_CAUSACION"] > UMBRAL_DIF_CAUSAC).sum())
        else:
            n_alertas_causac = 0
    else:
        n_alertas_causac = 0

    # Variaciones de precio
    n_alertas_precio = 0
    if "PRECIO_T" in df.columns and "PRECIO_Y" in df.columns:
        pct = ((df["PRECIO_T"] - df["PRECIO_Y"]).abs() / df["PRECIO_Y"].abs().replace(0, np.nan) * 100)
        n_alertas_precio = int((pct > UMBRAL_VAR_PRECIO).sum())

    # Sin precio
    n_sin_precio = int(df["PRECIO_T"].isna().sum()) if "PRECIO_T" in df.columns else 0

    return {
        "fecha": fecha,
        "archivo": path.name,
        "total_posiciones": total,
        "distribucion_tipo": tipo_dist,
        "fuentes_precio": fuente_dist,
        "suma_valoracion_di": suma_val_di,
        "suma_valoracion_df": suma_val_df,
        "suma_causacion": suma_causac,
        "alertas_causacion": n_alertas_causac,
        "alertas_precio": n_alertas_precio,
        "sin_precio": n_sin_precio,
    }


@router.get("/posiciones/{fecha}")
def posiciones_mitra(
    fecha: str,
    tipo: Optional[str] = Query(None),
    fuente: Optional[str] = Query(None),
    busqueda: Optional[str] = Query(None),
    solo_alertas: bool = Query(False),
    marcado_curva: bool = Query(False),
):
    """Lista detallada de posiciones Mitra con precios, valoraciones y observaciones."""
    path = _buscar_mitra(fecha) or _buscar_revision_bolsa(fecha)
    if not path:
        return []

    df = _leer_excel_robusto(path)
    if df.empty:
        return []

    df = _normalizar_mitra(df)

    # Causación calculada
    if "VALORACION_DF" in df.columns and "VALORACION_DI" in df.columns:
        df["CAUSACION_CALC"] = (df["VALORACION_DF"] - df["VALORACION_DI"]).round(2)
        if "CAUSACION" in df.columns:
            df["DIF_CAUSACION"] = (df["CAUSACION"] - df["CAUSACION_CALC"]).round(2)

    # Variación precio
    if "PRECIO_T" in df.columns and "PRECIO_Y" in df.columns:
        df["VAR_PRECIO_PCT"] = ((df["PRECIO_T"] - df["PRECIO_Y"]).abs() /
                                df["PRECIO_Y"].abs().replace(0, np.nan) * 100).round(4)
        df["ALERTA_PRECIO"] = df["VAR_PRECIO_PCT"] > UMBRAL_VAR_PRECIO

    # Observación automática
    def _obs(row):
        obs = []
        if pd.isna(row.get("PRECIO_T")):
            obs.append("SIN PRECIO")
        if row.get("ALERTA_PRECIO", False):
            obs.append(f"VAR PRECIO {row.get('VAR_PRECIO_PCT', 0):.2f}%")
        dif_c = row.get("DIF_CAUSACION")
        if dif_c is not None and not pd.isna(dif_c) and abs(dif_c) > UMBRAL_DIF_CAUSAC:
            obs.append(f"DIF CAUSACION {dif_c:,.2f}")
        marcado = str(row.get("MARCADO_ACTIVO", "")).upper()
        if "CURVA" in marcado or "TIR" in marcado:
            obs.append("TITULO A TIR/CURVA")
        return " | ".join(obs) if obs else "OK"

    df["OBSERVACION"] = df.apply(_obs, axis=1)

    # Filtros
    if tipo and "TIPO" in df.columns:
        df = df[df["TIPO"].astype(str).str.upper().str.contains(tipo.upper(), na=False)]
    if fuente and "FUENTE" in df.columns:
        df = df[df["FUENTE"].astype(str).str.upper().str.contains(fuente.upper(), na=False)]
    if busqueda:
        mask = pd.Series(False, index=df.index)
        for c in ["ISIN", "TITULO", "NEMO"]:
            if c in df.columns:
                mask = mask | df[c].astype(str).str.upper().str.contains(busqueda.upper(), na=False)
        df = df[mask]
    if solo_alertas:
        df = df[df["OBSERVACION"] != "OK"]
    if marcado_curva and "MARCADO_ACTIVO" in df.columns:
        df = df[df["MARCADO_ACTIVO"].astype(str).str.upper().str.contains("CURVA|TIR", na=False)]

    cols_salida = [c for c in [
        "ISIN", "TITULO", "TIPO", "FUENTE", "MONEDA",
        "PRECIO_T", "PRECIO_Y", "VAR_PRECIO_PCT",
        "VALORACION_DI", "VALORACION_DF", "CAUSACION", "CAUSACION_CALC", "DIF_CAUSACION",
        "MARCADO_ACTIVO", "OBSERVACION",
    ] if c in df.columns]

    return df[cols_salida].replace({float("nan"): None}).head(1000).to_dict(orient="records")


@router.get("/causaciones/{fecha}")
def causaciones_mitra(fecha: str):
    """Detalle de causaciones: DI/DF, calculadas, diferencias, alertas por tipo."""
    path = _buscar_mitra(fecha) or _buscar_revision_bolsa(fecha)
    if not path:
        return {"error": f"No se encontró archivo Mitra para {fecha}"}

    df = _leer_excel_robusto(path)
    if df.empty:
        return {"error": "Vacío"}

    df = _normalizar_mitra(df)

    if "VALORACION_DI" not in df.columns or "VALORACION_DF" not in df.columns:
        return {"error": "Sin columnas VALORACION_DI/VALORACION_DF"}

    df["CAUSACION_CALC"] = (df["VALORACION_DF"] - df["VALORACION_DI"]).round(2)

    por_tipo: Dict = {}
    if "TIPO" in df.columns:
        grp = df.groupby("TIPO").agg(
            count=("CAUSACION_CALC", "count"),
            suma_causacion_calc=("CAUSACION_CALC", "sum"),
            suma_valoracion_di=("VALORACION_DI", "sum"),
            suma_valoracion_df=("VALORACION_DF", "sum"),
        ).reset_index()
        for c in ["suma_causacion_calc", "suma_valoracion_di", "suma_valoracion_df"]:
            grp[c] = grp[c].round(2)
        por_tipo = grp.replace({float("nan"): None}).to_dict(orient="records")

    alertas = []
    if "CAUSACION" in df.columns:
        df["DIF_CAUSACION"] = (df["CAUSACION"] - df["CAUSACION_CALC"]).round(2)
        alertas_df = df[df["DIF_CAUSACION"].abs() > UMBRAL_DIF_CAUSAC]
        cols = [c for c in ["ISIN", "TITULO", "TIPO", "CAUSACION", "CAUSACION_CALC", "DIF_CAUSACION"] if c in alertas_df.columns]
        alertas = alertas_df[cols].replace({float("nan"): None}).head(200).to_dict(orient="records")

    return {
        "fecha": fecha,
        "suma_causacion_total": round(float(df["CAUSACION_CALC"].sum()), 2),
        "suma_valoracion_di": round(float(df["VALORACION_DI"].sum()), 2),
        "suma_valoracion_df": round(float(df["VALORACION_DF"].sum()), 2),
        "por_tipo": por_tipo,
        "total_alertas_causacion": len(alertas),
        "alertas": alertas,
    }


@router.get("/diferencias_porfin/{fecha}")
def diferencias_porfin_mitra(fecha: str):
    """
    Compara causaciones Mitra vs Porfin (575):
    calcula DIF_CAUSACION_PORFIN por título.
    """
    from routers.porfin import _buscar_archivo_575, _leer_csv_robusto as _csv

    path_mitra = _buscar_mitra(fecha)
    path_575   = _buscar_archivo_575(fecha)

    if not path_mitra:
        return {"error": f"Sin archivo Mitra para {fecha}"}
    if not path_575:
        return {"error": f"Sin archivo 575 para {fecha}"}

    df_m = _normalizar_mitra(_leer_excel_robusto(path_mitra))
    df_p = _csv(path_575)
    df_p.columns = df_p.columns.str.strip().str.upper()

    # Causación calculada Mitra
    if "VALORACION_DI" in df_m.columns and "VALORACION_DF" in df_m.columns:
        df_m["CAUSACION_MITRA"] = (df_m["VALORACION_DF"] - df_m["VALORACION_DI"]).round(2)
    else:
        df_m["CAUSACION_MITRA"] = df_m.get("CAUSACION", pd.Series(dtype=float))

    # Causación Porfin
    for alias, canon in [
        ("CAUSACIÓN MER", "CAUSACION_PORFIN"), ("CAUSACION MER", "CAUSACION_PORFIN"),
        ("VLR MER. HOY", "VAL_HOY_PORFIN"), ("VLR MER. ANT", "VAL_ANT_PORFIN"),
    ]:
        if alias in df_p.columns and canon not in df_p.columns:
            df_p = df_p.rename(columns={alias: canon})

    if "CAUSACION_PORFIN" not in df_p.columns and "VAL_HOY_PORFIN" in df_p.columns:
        df_p["VAL_HOY_PORFIN"] = pd.to_numeric(df_p["VAL_HOY_PORFIN"].astype(str).str.replace(",", "."), errors="coerce")
        df_p["VAL_ANT_PORFIN"] = pd.to_numeric(df_p["VAL_ANT_PORFIN"].astype(str).str.replace(",", "."), errors="coerce")
        df_p["CAUSACION_PORFIN"] = (df_p["VAL_HOY_PORFIN"] - df_p["VAL_ANT_PORFIN"]).round(2)
    else:
        df_p["CAUSACION_PORFIN"] = pd.to_numeric(
            df_p.get("CAUSACION_PORFIN", pd.Series(dtype=str)).astype(str).str.replace(",", "."), errors="coerce"
        )

    # Clave de cruce
    col_id_m = next((c for c in ["ISIN", "TITULO"] if c in df_m.columns), None)
    col_id_p = next((c for c in ["ISIN", "TITULO", "NEMOTÉCNICO", "NEMO"] if c in df_p.columns), None)
    if not col_id_m or not col_id_p:
        return {"error": "No se encontró columna ID común entre Mitra y 575"}

    df_m["_KEY"] = df_m[col_id_m].astype(str).str.strip().str.upper()
    df_p["_KEY"] = df_p[col_id_p].astype(str).str.strip().str.upper()

    merged = df_m[["_KEY", "CAUSACION_MITRA"]].merge(
        df_p[["_KEY", "CAUSACION_PORFIN"]], on="_KEY", how="outer"
    )
    merged = merged.dropna(subset=["CAUSACION_MITRA", "CAUSACION_PORFIN"])
    merged["DIF_CAUSACION_PORFIN"] = (merged["CAUSACION_MITRA"] - merged["CAUSACION_PORFIN"]).round(2)
    merged["ALERTA"] = merged["DIF_CAUSACION_PORFIN"].abs() > UMBRAL_DIF_CAUSAC
    merged = merged.rename(columns={"_KEY": "ID"})

    return {
        "fecha": fecha,
        "total_cruzados": len(merged),
        "total_alertas": int(merged["ALERTA"].sum()),
        "suma_causacion_mitra": round(float(merged["CAUSACION_MITRA"].sum()), 2),
        "suma_causacion_porfin": round(float(merged["CAUSACION_PORFIN"].sum()), 2),
        "diferencia_total": round(float(merged["DIF_CAUSACION_PORFIN"].sum()), 2),
        "detalle": merged.replace({float("nan"): None}).sort_values("DIF_CAUSACION_PORFIN", key=abs, ascending=False).to_dict(orient="records"),
    }


@router.get("/variaciones/{fecha_inicio}/{fecha_fin}")
def variaciones_mitra(fecha_inicio: str, fecha_fin: str, umbral: float = Query(5.0)):
    """Variación de precios Mitra entre dos fechas."""
    def _cargar(fecha):
        p = _buscar_mitra(fecha)
        if not p:
            return pd.DataFrame()
        df = _leer_excel_robusto(p)
        return _normalizar_mitra(df)

    df_i = _cargar(fecha_inicio)
    df_f = _cargar(fecha_fin)
    if df_i.empty or df_f.empty:
        return []

    col_id = next((c for c in ["ISIN", "TITULO"] if c in df_i.columns and c in df_f.columns), None)
    if not col_id:
        return []

    df_i[col_id] = df_i[col_id].astype(str).str.strip().str.upper()
    df_f[col_id] = df_f[col_id].astype(str).str.strip().str.upper()

    merged = df_i[[col_id, "PRECIO_T", "VALORACION_DF"]].rename(
        columns={"PRECIO_T": "PRECIO_I", "VALORACION_DF": "VAL_I"}
    ).merge(
        df_f[[col_id, "PRECIO_T", "VALORACION_DF"]].rename(
            columns={"PRECIO_T": "PRECIO_F", "VALORACION_DF": "VAL_F"}
        ),
        on=col_id, how="inner"
    )

    merged = merged.dropna(subset=["PRECIO_I", "PRECIO_F"])
    merged = merged[merged["PRECIO_I"] != 0]
    merged["VAR_PRECIO_ABS"] = (merged["PRECIO_F"] - merged["PRECIO_I"]).round(6)
    merged["VAR_PRECIO_PCT"] = ((merged["VAR_PRECIO_ABS"] / merged["PRECIO_I"].abs()) * 100).round(4)
    merged["ANORMAL"] = merged["VAR_PRECIO_PCT"].abs() > umbral
    merged = merged.rename(columns={col_id: "ID"})

    return merged.replace({float("nan"): None}).sort_values("VAR_PRECIO_PCT", key=abs, ascending=False).to_dict(orient="records")


@router.get("/monedas/{fecha}")
def monedas_mitra(fecha: str):
    """Tasas de cambio utilizadas en Mitra para una fecha."""
    for d in [BASE_DIR, RAW_DIR]:
        for f in list(d.glob(f"Monedas_{fecha}*.xlsx")) + list(d.glob(f"monedas_matriz_info_{fecha}*.csv")):
            if f.suffix == ".xlsx":
                df = pd.read_excel(f, dtype=str, engine="openpyxl")
            else:
                df = pd.read_csv(f, dtype=str, encoding="latin-1")
            df.columns = df.columns.str.strip().str.upper()
            return df.replace({float("nan"): None}).to_dict(orient="records")
    return []
