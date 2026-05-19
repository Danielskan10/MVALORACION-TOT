#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MVALORACION HISTORICAL BACKEND
API REST para consulta histórica de títulos, variaciones seleccionables por fecha,
resúmenes por archivo/moneda/tipo y exportación de datos estructurados para dashboard.
"""

import os
import re
import logging
import glob
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any
from functools import lru_cache

import pandas as pd
import numpy as np
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ──────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN
# ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path("./MVALORACION")
os.makedirs(BASE_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("mvaloracion_api")

app = FastAPI(
    title="MVALORACION Historical API",
    description="Consulta histórica de precios, variaciones y resúmenes por título/archivo",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────────────────────────────
# MODELOS PYDANTIC
# ──────────────────────────────────────────────────────────────────────
class TitleInfo(BaseModel):
    isin: Optional[str] = None
    nemo: Optional[str] = None
    llave: Optional[str] = None
    tipo: Optional[str] = None
    moneda: Optional[str] = None

class PricePoint(BaseModel):
    date: str
    price: Optional[float] = None
    source: str

class VariationRecord(BaseModel):
    id: str
    id_type: str
    price_start: Optional[float] = None
    price_end: Optional[float] = None
    abs_variation: Optional[float] = None
    pct_variation: Optional[float] = None

class SummaryItem(BaseModel):
    file_type: str
    count: int
    avg_price: Optional[float] = None
    currencies: List[str] = []

# ──────────────────────────────────────────────────────────────────────
# MOTOR DE DATOS (SCAN + CACHE + QUERIES)
# ──────────────────────────────────────────────────────────────────────
class MValoracionEngine:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.index: Dict[str, Dict[str, Path]] = {}  # {date: {type: path}}
        self._build_index()

    def _build_index(self):
        patron_fecha = re.compile(r"(\d{8})")
        for fp in self.base_dir.rglob("*.xlsx"):
            m = patron_fecha.search(fp.stem)
            if not m: continue
            fecha = m.group(1)
            tipo = self._clasificar(fp.stem.upper())
            self.index.setdefault(fecha, {})[tipo] = fp

    @staticmethod
    def _clasificar(stem: str) -> str:
        if stem.startswith("SP"): return "SP"
        if stem.startswith("SW"): return "SW"
        if stem.startswith("MX"): return "MX"
        if "MONEDAS" in stem: return "MONEDAS"
        if "MITRA" in stem: return "MITRA"
        if "PORFIN" in stem: return "PORFIN"
        return "OTROS"

    @lru_cache(maxsize=256)
    def cargar_df(self, fecha: str, tipo: str) -> pd.DataFrame:
        path = self.index.get(fecha, {}).get(tipo)
        if not path or not path.exists():
            return pd.DataFrame()
        df = pd.read_excel(path, engine="openpyxl")
        df.columns = df.columns.str.strip().str.upper()
        return df

    def obtener_fechas_disponibles(self) -> List[str]:
        return sorted(self.index.keys())

    def obtener_ids_unicos(self, fecha: Optional[str] = None, tipo: Optional[str] = None) -> List[Dict[str, Any]]:
        fechas = [fecha] if fecha else self.obtener_fechas_disponibles()
        ids_set = set()
        resultados = []
        for f in fechas:
            tipos = [tipo] if tipo else self.index.get(f, {}).keys()
            for t in tipos:
                df = self.cargar_df(f, t)
                if df.empty: continue
                isin = df.get("ISIN") or df.get("CODIGO_ISIN_CONTRATO")
                nemo = df.get("NEMO") or df.get("NEMOTECNICO_BOL")
                llave = df.get("LLAVE")
                tipo_act = df.get("TIPO") or df.get("TIPO_DE_PRODUCTO")
                moneda = df.get("MONEDA") or df.get("MONEDA_PRODUCTO")
                for i in range(len(df)):
                    val_isin = str(isin.iloc[i]) if isin is not None else ""
                    val_nemo = str(nemo.iloc[i]) if nemo is not None else ""
                    val_llave = str(llave.iloc[i]) if llave is not None else ""
                    key = val_isin or val_nemo or val_llave
                    if not key or key in ids_set: continue
                    ids_set.add(key)
                    resultados.append({
                        "id": key,
                        "isin": val_isin if val_isin and val_isin not in {"nan", "None"} else None,
                        "nemo": val_nemo if val_nemo and val_nemo not in {"nan", "None"} else None,
                        "llave": val_llave if val_llave and val_llave not in {"nan", "None"} else None,
                        "tipo": tipo_act.iloc[i] if tipo_act is not None else None,
                        "moneda": moneda.iloc[i] if moneda is not None else None,
                        "fuente": t,
                        "fecha": f
                    })
        return resultados

    def obtener_historico_precios(self, id_busqueda: str, fechas: List[str]) -> List[PricePoint]:
        resultados = []
        for f in sorted(fechas):
            for t in self.index.get(f, {}).keys():
                df = self.cargar_df(f, t)
                if df.empty: continue
                cols_id = [c for c in ["ISIN", "NEMO", "LLAVE", "CODIGO_ISIN_CONTRATO"] if c in df.columns]
                if not cols_id: continue
                col_id = cols_id[0]
                match = df[df[col_id].astype(str).str.upper().str.contains(id_busqueda.upper(), na=False)]
                if match.empty: continue
                col_precio = next((c for c in ["PRECIO", "PRECIO_T", "ULTIMO_PRECIO", "PRECIO_VALOR_CALCULADO", "VALOR"] if c in df.columns), None)
                if not col_precio: continue
                precio = match[col_precio].iloc[0]
                try: precio = float(precio) if pd.notna(precio) else None
                except: precio = None
                resultados.append(PricePoint(date=f, price=precio, source=t))
        return resultados

    def calcular_variaciones(self, fecha_inicio: str, fecha_fin: str, filtro_id: Optional[str] = None) -> List[VariationRecord]:
        if fecha_inicio == fecha_fin:
            raise HTTPException(status_code=400, detail="Fecha inicio y fin deben ser distintas")
        datos_ini = self._mapear_precios(fecha_inicio)
        datos_fin = self._mapear_precios(fecha_fin)
        ids_comunes = set(datos_ini.keys()) & set(datos_fin.keys())
        if filtro_id:
            ids_comunes = {k for k in ids_comunes if filtro_id.upper() in k.upper()}
        resultados = []
        for k in ids_comunes:
            p1, p2 = datos_ini[k], datos_fin[k]
            if p1 is None or p2 is None or p1 == 0: continue
            var_abs = p2 - p1
            var_pct = (var_abs / abs(p1)) * 100
            resultados.append(VariationRecord(
                id=k,
                id_type="ISIN" if k.startswith("CO") else ("NEMO" if len(k) <= 8 else "LLAVE"),
                price_start=round(p1, 6),
                price_end=round(p2, 6),
                abs_variation=round(var_abs, 6),
                pct_variation=round(var_pct, 4)
            ))
        return resultados

    def _mapear_precios(self, fecha: str) -> Dict[str, Optional[float]]:
        mapeo = {}
        for t in self.index.get(fecha, {}).keys():
            df = self.cargar_df(fecha, t)
            if df.empty: continue
            cols_id = [c for c in ["ISIN", "NEMO", "LLAVE", "CODIGO_ISIN_CONTRATO"] if c in df.columns]
            if not cols_id: continue
            col_precio = next((c for c in ["PRECIO", "PRECIO_T", "ULTIMO_PRECIO", "PRECIO_VALOR_CALCULADO", "VALOR"] if c in df.columns), None)
            if not col_precio: continue
            for _, row in df.iterrows():
                clave = str(row[cols_id[0]])
                if pd.isna(clave): continue
                val = row[col_precio]
                try: val = float(val) if pd.notna(val) else None
                except: val = None
                mapeo[clave.strip().upper()] = val
        return mapeo

    def resumen_por_archivo(self, fecha: str) -> List[SummaryItem]:
        resumen = []
        for t, path in self.index.get(fecha, {}).items():
            df = self.cargar_df(fecha, t)
            if df.empty: continue
            col_precio = next((c for c in ["PRECIO", "PRECIO_T", "ULTIMO_PRECIO", "VALOR"] if c in df.columns), None)
            col_moneda = next((c for c in ["MONEDA", "MONEDA_PRODUCTO"] if c in df.columns), None)
            precios = pd.to_numeric(df[col_precio], errors="coerce").dropna() if col_precio else pd.Series()
            monedas = df[col_moneda].dropna().unique().tolist() if col_moneda else []
            resumen.append(SummaryItem(
                file_type=t,
                count=len(df),
                avg_price=round(precios.mean(), 6) if not precios.empty else None,
                currencies=[str(m) for m in monedas]
            ))
        return resumen

# Instancia global
engine = MValoracionEngine(BASE_DIR)

# ──────────────────────────────────────────────────────────────────────
# ENDPOINTS FASTAPI
# ──────────────────────────────────────────────────────────────────────
@app.get("/api/fechas")
def fechas_disponibles():
    return {"fechas": engine.obtener_fechas_disponibles()}

@app.get("/api/titulos")
def titulos(fecha: Optional[str] = Query(None, description="Filtrar por fecha específica"),
            tipo_archivo: Optional[str] = Query(None, description="SP, SW, MX, MITRA, PORFIN")):
    return engine.obtener_ids_unicos(fecha, tipo_archivo)

@app.get("/api/historico/{id_titulo}")
def historico_precios(id_titulo: str,
                      fechas: List[str] = Query(..., description="Lista de fechas YYYYMMDD")):
    return engine.obtener_historico_precios(id_titulo, fechas)

@app.get("/api/variaciones")
def variaciones(fecha_inicio: str = Query(..., description="YYYYMMDD"),
                fecha_fin: str = Query(..., description="YYYYMMDD"),
                id_filtro: Optional[str] = Query(None, description="ISIN/NEMO/LLAVE parcial")):
    return engine.calcular_variaciones(fecha_inicio, fecha_fin, id_filtro)

@app.get("/api/resumen/{fecha}")
def resumen(fecha: str):
    return engine.resumen_por_archivo(fecha)

# ──────────────────────────────────────────────────────────────────────
# INICIO
# ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    print(f"🚀 Iniciando backend en http://0.0.0.0:8000")
    print(f"📂 Escaneando archivos en: {BASE_DIR.resolve()}")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)