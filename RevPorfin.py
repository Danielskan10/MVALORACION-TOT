#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BACKEND_PORFIN.py
API REST para consulta histórica de datos Porfin (precios, valoraciones, tipos de activo, variaciones).
"""
import os, re, logging
from pathlib import Path
from datetime import datetime
from typing import List, Optional
from functools import lru_cache

import pandas as pd
import numpy as np
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("porfin_api")

BASE_DIR = Path("./MVALORACION")
os.makedirs(BASE_DIR, exist_ok=True)

app = FastAPI(title="Porfin Historical Data API", version="1.0.0", docs_url="/docs")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ──────────────────────────────────────────────────────────────────────
# MODELOS
# ──────────────────────────────────────────────────────────────────────
class PorfinHistoryPoint(BaseModel):
    date: str
    precio_t: Optional[float] = None
    precio_y: Optional[float] = None
    valoracion: Optional[float] = None
    nominal: Optional[float] = None
    tipo: Optional[str] = None
    llave: Optional[str] = None

class PorfinVariation(BaseModel):
    id: str
    tipo_activo: Optional[str] = None
    precio_inicio: Optional[float] = None
    precio_fin: Optional[float] = None
    var_abs: Optional[float] = None
    var_pct: Optional[float] = None
    valoracion_inicio: Optional[float] = None
    valoracion_fin: Optional[float] = None

# ──────────────────────────────────────────────────────────────────────
# MOTOR
# ──────────────────────────────────────────────────────────────────────
class PorfinEngine:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self._index = {}
        self._build_index()

    def _build_index(self):
        patron = re.compile(r"(\d{8})")
        for fp in self.base_dir.rglob("*.xlsx"):
            m = patron.search(fp.stem)
            if m and ("PORFIN" in fp.stem.upper() or "596" in fp.stem.upper()):
                self._index[m.group(1)] = fp

    def fechas_disponibles(self) -> List[str]:
        return sorted(self._index.keys())

    @staticmethod
    def _first_column(df: pd.DataFrame, *names: str, default: str = ""):
        for name in names:
            if name in df.columns:
                return df[name]
        return default

    @lru_cache(maxsize=64)
    def cargar_porfin(self, fecha: str) -> Optional[pd.DataFrame]:
        path = self._index.get(fecha)
        if not path or not path.exists(): return None
        df = pd.read_excel(path, engine="openpyxl")
        df.columns = df.columns.str.upper().str.strip()
        
        # Normalización de identificadores
        df["ID"] = self._first_column(df, "ISIN", "NEMOTÉCNICO BOL", "NEMOTECNICO BOL", "LLAVE")
        df["TIPO"] = self._first_column(df, "TIPO", "TIPO DE ACTIVO")
        df["LLAVE"] = self._first_column(df, "LLAVE")
        
        # Numéricos
        df["PRECIO_T"] = pd.to_numeric(df.get("PRECIO_T"), errors="coerce")
        df["PRECIO_Y"] = pd.to_numeric(df.get("PRECIO_Y"), errors="coerce")
        df["VALORACION"] = pd.to_numeric(df.get("VALORACION"), errors="coerce")
        df["NOMINAL"] = pd.to_numeric(df.get("VALOR NOMINAL"), errors="coerce")
        df = df[df["ID"].astype(str).str.strip().ne("")]
        return df

    def obtener_historico(self, titulo: str, desde: str, hasta: str) -> List[PorfinHistoryPoint]:
        res = []
        for f in sorted(k for k in self._index.keys() if desde <= k <= hasta):
            df = self.cargar_porfin(f)
            if df is None: continue
            row = df[df["ID"].astype(str).str.upper().str.contains(titulo.upper(), na=False)]
            if row.empty: continue
            r = row.iloc[0]
            res.append(PorfinHistoryPoint(
                date=f,
                precio_t=float(r["PRECIO_T"]) if pd.notna(r["PRECIO_T"]) else None,
                precio_y=float(r["PRECIO_Y"]) if pd.notna(r["PRECIO_Y"]) else None,
                valoracion=float(r["VALORACION"]) if pd.notna(r["VALORACION"]) else None,
                nominal=float(r["NOMINAL"]) if pd.notna(r["NOMINAL"]) else None,
                tipo=str(r["TIPO"]) if pd.notna(r["TIPO"]) else None,
                llave=str(r["LLAVE"]) if pd.notna(r["LLAVE"]) else None
            ))
        return res

    def calcular_variaciones(self, inicio: str, fin: str, filtro: Optional[str] = None) -> List[PorfinVariation]:
        if inicio == fin: raise HTTPException(400, "Fechas distintas requeridas")
        df_i = self.cargar_porfin(inicio)
        df_f = self.cargar_porfin(fin)
        if df_i is None or df_f is None: raise HTTPException(404, "Faltan datos")
        
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
            vi, vf = fila_i["VALORACION"], fila_f["VALORACION"]
            tipo = fila_i["TIPO"]
            if pd.isna(pi) or pd.isna(pf) or pi == 0: continue
            var = pf - pi
            res.append(PorfinVariation(
                id=str(idx), tipo_activo=tipo,
                precio_inicio=round(float(pi), 6), precio_fin=round(float(pf), 6),
                var_abs=round(var, 6), var_pct=round((var/abs(pi))*100, 4),
                valoracion_inicio=float(vi) if pd.notna(vi) else None,
                valoracion_fin=float(vf) if pd.notna(vf) else None
            ))
        return res

    def resumen_por_tipo(self, fecha: str) -> dict:
        df = self.cargar_porfin(fecha)
        if df is None: return {}
        df = df.dropna(subset=["TIPO", "VALORACION"])
        agg = df.groupby("TIPO").agg(
            count=("VALORACION", "size"),
            sum_valor=("VALORACION", "sum"),
            avg_precio=("PRECIO_T", "mean")
        ).reset_index()
        return agg.to_dict(orient="records")

engine = PorfinEngine(BASE_DIR)

# ──────────────────────────────────────────────────────────────────────
# ENDPOINTS
# ──────────────────────────────────────────────────────────────────────
@app.get("/api/fechas")
def get_fechas(): return {"fechas": engine.fechas_disponibles()}

@app.get("/api/historico/{titulo}")
def get_historico(titulo: str, desde: str = Query(...), hasta: str = Query(...)):
    return engine.obtener_historico(titulo, desde, hasta)

@app.get("/api/variaciones")
def get_variaciones(inicio: str = Query(...), fin: str = Query(...), filtro: Optional[str] = None):
    return engine.calcular_variaciones(inicio, fin, filtro)

@app.get("/api/resumen/{fecha}")
def get_resumen(fecha: str): return engine.resumen_por_tipo(fecha)

if __name__ == "__main__":
    import argparse
    import uvicorn
    parser = argparse.ArgumentParser(description="API REST historica Porfin")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8002)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()
    logger.info("🚀 Backend Porfin iniciando en http://%s:%s", args.host, args.port)
    logger.info("📂 Escaneando: %s", BASE_DIR.resolve())
    uvicorn.run(app, host=args.host, port=args.port, reload=args.reload)
