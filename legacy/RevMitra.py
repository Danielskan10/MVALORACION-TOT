#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BACKEND_MITRA.py
API REST para consulta histórica de datos Mitra (precios, valoraciones, monedas, UVR, variaciones).
"""
import os, re, logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional
from functools import lru_cache

import pandas as pd
import numpy as np
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("mitra_api")

BASE_DIR = Path("./MVALORACION")
os.makedirs(BASE_DIR, exist_ok=True)

app = FastAPI(title="Mitra Historical Data API", version="1.0.0", docs_url="/docs")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ──────────────────────────────────────────────────────────────────────
# MODELOS DE RESPUESTA
# ──────────────────────────────────────────────────────────────────────
class HistoryPoint(BaseModel):
    date: str
    precio_t: Optional[float] = None
    precio_y: Optional[float] = None
    valoracion_di: Optional[float] = None
    valoracion_df: Optional[float] = None
    causacion: Optional[float] = None
    fuente: Optional[str] = None
    moneda_factor: Optional[float] = None

class VariationRecord(BaseModel):
    id: str
    tipo_producto: Optional[str] = None
    precio_inicio: Optional[float] = None
    precio_fin: Optional[float] = None
    variacion_abs: Optional[float] = None
    variacion_pct: Optional[float] = None
    valoracion_inicio: Optional[float] = None
    valoracion_fin: Optional[float] = None

class MonedaUVRPoint(BaseModel):
    date: str
    uvr: Optional[float] = None
    usd: Optional[float] = None
    eur: Optional[float] = None
    brl: Optional[float] = None

class SummaryItem(BaseModel):
    file_type: str
    total_filas: int
    promedio_precios: Optional[float] = None
    monedas_distintas: List[str] = Field(default_factory=list)

# ──────────────────────────────────────────────────────────────────────
# MOTOR DE DATOS
# ──────────────────────────────────────────────────────────────────────
class MitraEngine:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self._index = {}
        self._build_index()

    def _build_index(self):
        patron = re.compile(r"(\d{8})")
        for fp in self.base_dir.rglob("*.xlsx"):
            m = patron.search(fp.stem)
            if m:
                fecha = m.group(1)
                tipo = self._clasificar(fp.stem.upper())
                self._index.setdefault(fecha, {})[tipo] = fp

    @staticmethod
    def _clasificar(stem: str) -> str:
        if "MITRA" in stem or "FIDU" in stem: return "MITRA_BASE"
        if stem.startswith("MONEDAS"): return "MONEDAS"
        if stem.startswith("SP"): return "SP"
        if stem.startswith("SW"): return "SW"
        if stem.startswith("MX_RV"): return "MX_RV"
        if stem.startswith("MX"): return "MX"
        if stem.startswith("NOTAS"): return "NOTAS"
        if stem.startswith("TP"): return "TP"
        return "OTROS"

    @staticmethod
    def _first_column(df: pd.DataFrame, *names: str, default: str = ""):
        for name in names:
            if name in df.columns:
                return df[name]
        return default

    def fechas_disponibles(self) -> List[str]:
        return sorted(self._index.keys())

    @lru_cache(maxsize=64)
    def cargar_mitra_base(self, fecha: str) -> Optional[pd.DataFrame]:
        path = self._index.get(fecha, {}).get("MITRA_BASE")
        if not path or not path.exists(): return None
        df = pd.read_excel(path, engine="openpyxl")
        df.columns = [c.upper().strip().replace(" ", " ") for c in df.columns]
        # Normalizar columnas clave
        df["ID"] = self._first_column(df, "CÓDIGO ISIN CONTRATO", "CODIGO ISIN CONTRATO", "ISIN", "NÍVEL 3 - PRODUCTO", "NIVEL 3 - PRODUCTO")
        df["TIPO"] = self._first_column(df, "TIPO DE PRODUCTO", "TIPO_PROD")
        df["PRECIO_T"] = pd.to_numeric(df.get("PRECIO_T"), errors="coerce")
        df["PRECIO_Y"] = pd.to_numeric(df.get("PRECIO_Y"), errors="coerce")
        df["VALORACION_DF"] = pd.to_numeric(df.get("VALORACION_DF"), errors="coerce")
        df["VALORACION_DI"] = pd.to_numeric(df.get("VALORACION_DI"), errors="coerce")
        df["CAUSACION"] = pd.to_numeric(self._first_column(df, "CAUSACION", "DI - DF"), errors="coerce")
        df["FUENTE"] = self._first_column(df, "FUENTE_PRECIO", "MARCADO ACTIVO")
        df["MONEDA_FACTOR"] = pd.to_numeric(df.get("MONEDA PRODUCTO"), errors="coerce")
        df = df[df["ID"].astype(str).str.strip().ne("")]
        return df

    @lru_cache(maxsize=32)
    def cargar_monedas(self, fecha: str) -> Optional[pd.DataFrame]:
        path = self._index.get(fecha, {}).get("MONEDAS")
        if not path or not path.exists(): return None
        df = pd.read_excel(path, engine="openpyxl")
        df.columns = df.columns.str.upper().str.strip()
        if "MONEDA" in df.columns and "PRECIO HOY" in df.columns:
            return df.set_index("MONEDA")["PRECIO HOY"]
        return None

    def obtener_historico(self, titulo_id: str, desde: str, hasta: str) -> List[HistoryPoint]:
        resultados = []
        fechas = sorted([f for f in self._index.keys() if desde <= f <= hasta])
        for f in fechas:
            df = self.cargar_mitra_base(f)
            if df is None: continue
            row = df[df["ID"].astype(str).str.upper().str.contains(titulo_id.upper(), na=False)]
            if row.empty: continue
            r = row.iloc[0]
            resultados.append(HistoryPoint(
                date=f,
                precio_t=float(r["PRECIO_T"]) if pd.notna(r["PRECIO_T"]) else None,
                precio_y=float(r["PRECIO_Y"]) if pd.notna(r["PRECIO_Y"]) else None,
                valoracion_di=float(r["VALORACION_DI"]) if pd.notna(r["VALORACION_DI"]) else None,
                valoracion_df=float(r["VALORACION_DF"]) if pd.notna(r["VALORACION_DF"]) else None,
                causacion=float(r["CAUSACION"]) if pd.notna(r["CAUSACION"]) else None,
                fuente=str(r["FUENTE"]) if pd.notna(r["FUENTE"]) else None,
                moneda_factor=float(r["MONEDA_FACTOR"]) if pd.notna(r["MONEDA_FACTOR"]) else None,
            ))
        return resultados

    def calcular_variaciones(self, inicio: str, fin: str, filtro: Optional[str] = None) -> List[VariationRecord]:
        if inicio == fin: raise HTTPException(400, "Fechas deben ser distintas")
        df_i = self.cargar_mitra_base(inicio)
        df_f = self.cargar_mitra_base(fin)
        if df_i is None or df_f is None: raise HTTPException(404, "Falta datos en una de las fechas")
        
        # Cruce por ID
        df_i = df_i.set_index("ID")
        df_f = df_f.set_index("ID")
        comunes = df_i.index.intersection(df_f.index)
        if filtro:
            comunes = comunes[comunes.astype(str).str.upper().str.contains(filtro.upper(), na=False)]
        
        res = []
        for idx in comunes:
            fila_i = df_i.loc[idx]
            fila_f = df_f.loc[idx]
            if isinstance(fila_i, pd.DataFrame):
                fila_i = fila_i.iloc[0]
            if isinstance(fila_f, pd.DataFrame):
                fila_f = fila_f.iloc[0]
            pi, pf = fila_i["PRECIO_T"], fila_f["PRECIO_T"]
            vi, vf = fila_i["VALORACION_DF"], fila_f["VALORACION_DF"]
            tipo = fila_i["TIPO"]
            if pd.isna(pi) or pd.isna(pf) or pi == 0: continue
            var_abs = pf - pi
            var_pct = (var_abs / abs(pi)) * 100
            res.append(VariationRecord(
                id=str(idx), tipo_producto=tipo,
                precio_inicio=round(float(pi), 6), precio_fin=round(float(pf), 6),
                variacion_abs=round(var_abs, 6), variacion_pct=round(var_pct, 4),
                valoracion_inicio=float(vi) if pd.notna(vi) else None,
                valoracion_fin=float(vf) if pd.notna(vf) else None
            ))
        return res

    def historial_monedas_uvrs(self, desde: str, hasta: str) -> List[MonedaUVRPoint]:
        res = []
        fechas = sorted([f for f in self._index.keys() if desde <= f <= hasta])
        for f in fechas:
            dfm = self.cargar_monedas(f)
            if dfm is None: continue
            res.append(MonedaUVRPoint(
                date=f,
                uvr=float(dfm.get("UVR", np.nan)) if pd.notna(dfm.get("UVR", np.nan)) else None,
                usd=float(dfm.get("USD", np.nan)) if pd.notna(dfm.get("USD", np.nan)) else None,
                eur=float(dfm.get("EUR", np.nan)) if pd.notna(dfm.get("EUR", np.nan)) else None,
                brl=float(dfm.get("BRL", np.nan)) if pd.notna(dfm.get("BRL", np.nan)) else None,
            ))
        return res

    def resumen_por_archivo(self, fecha: str) -> List[SummaryItem]:
        res = []
        for tipo, path in self._index.get(fecha, {}).items():
            if tipo == "MONEDAS" or tipo == "OTROS": continue
            try:
                df = pd.read_excel(path, engine="openpyxl")
                col_precio = next((c for c in df.columns if "PRECIO" in c.upper() or "VALOR" in c.upper()), None)
                col_moneda = next((c for c in df.columns if "MONEDA" in c.upper()), None)
                precios = pd.to_numeric(df[col_precio], errors="coerce").dropna() if col_precio else pd.Series()
                monedas = df[col_moneda].dropna().unique().tolist() if col_moneda else []
                res.append(SummaryItem(
                    file_type=tipo, total_filas=len(df),
                    promedio_precios=round(precios.mean(), 6) if not precios.empty else None,
                    monedas_distintas=[str(m) for m in monedas]
                ))
            except: continue
        return res

engine = MitraEngine(BASE_DIR)

# ──────────────────────────────────────────────────────────────────────
# ENDPOINTS
# ──────────────────────────────────────────────────────────────────────
@app.get("/api/fechas")
def get_fechas(): return {"fechas": engine.fechas_disponibles()}

@app.get("/api/historico/{titulo_id}")
def get_historico(titulo_id: str, desde: str = Query(...), hasta: str = Query(...)):
    return engine.obtener_historico(titulo_id, desde, hasta)

@app.get("/api/variaciones")
def get_variaciones(inicio: str = Query(...), fin: str = Query(...), filtro: Optional[str] = None):
    return engine.calcular_variaciones(inicio, fin, filtro)

@app.get("/api/monedas_uvrs")
def get_monedas(desde: str = Query(...), hasta: str = Query(...)):
    return engine.historial_monedas_uvrs(desde, hasta)

@app.get("/api/resumen/{fecha}")
def get_resumen(fecha: str):
    return engine.resumen_por_archivo(fecha)

if __name__ == "__main__":
    import argparse
    import uvicorn
    parser = argparse.ArgumentParser(description="API REST historica Mitra")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()
    logger.info("🚀 Backend Mitra iniciando en http://%s:%s", args.host, args.port)
    logger.info("📂 Escaneando: %s", BASE_DIR.resolve())
    uvicorn.run(app, host=args.host, port=args.port, reload=args.reload)
