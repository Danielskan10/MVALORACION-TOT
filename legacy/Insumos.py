#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MVALORACION_CONVERTIDOR.py
Convierte archivos base de Infovalmer a Excel, extrae UVR y genera Monedas.
TODO se guarda en una única carpeta: ./MVALORACION/
"""

import os
import re
import time
import warnings
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import holidays

# ── Selenium (solo para UVR) ───────────────────────────────────────
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_OK = True
except ImportError:
    SELENIUM_OK = False
    print("⚠️ Selenium no instalado. La extracción de UVR se omitirá.")

warnings.filterwarnings('ignore')

# ============================================================
# 🔧 CONFIGURACIÓN & DETECCIÓN DE USUARIO
# ============================================================
FECHA_HOY_STR = "20260429"          # ← Cambia solo esto (YYYYMMDD)
USER_HOME = Path.home()             # Detecta automáticamente C:\Users\TU_USUARIO\
OUTPUT_DIR  = Path("./MVALORACION") # 📁 Carpeta única de salida
BASE_INFOVALMER = Path("J:/VALORACION/VALORACION_ESPECIAL/Bolsa/INFOVALMER")
FESTIVOS_CO = holidays.Colombia()

# Derivar fechas
FECHA_HOY  = datetime.strptime(FECHA_HOY_STR, "%Y%m%d")
FECHA_AYER = FECHA_HOY - timedelta(days=1)
HOY  = FECHA_HOY.strftime("%Y%m%d")
AYER = FECHA_AYER.strftime("%Y%m%d")

# ============================================================
# 🛠 UTILIDADES COMPARTIDAS
# ============================================================
def sufijo_fecha(fecha_str: str) -> str:
    """20260406 → 040626"""
    return datetime.strptime(fecha_str, "%Y%m%d").strftime("%m%d%y")

def ajustar_a_dia_habil(fecha_str: str) -> str:
    fecha = datetime.strptime(fecha_str, "%Y%m%d").date()
    original = fecha
    while fecha.weekday() >= 5 or fecha in FESTIVOS_CO:
        fecha -= timedelta(days=1)
    if fecha != original:
        print(f"⚠ {original} no hábil → usando {fecha}")
    return fecha.strftime("%Y%m%d")

def parse_num_scalar(x):
    if pd.isna(x): return np.nan
    s = str(x).strip().replace("\u00a0", " ").replace("  ", " ")
    if not s or s.lower() in {"none", "nan", "noaplica", "no aplica"}: return np.nan
    s = s.replace(",", ".") if ("," in s and "." in s) else s.replace(",", ".")
    s = re.sub(r"[^0-9.\-]", "", s)
    try: return float(s)
    except: return np.nan

def exportar_unificado(df, fecha_str, nombre):
    """Guarda en la carpeta única MVALORACION"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ruta = OUTPUT_DIR / f"{nombre}_{fecha_str}.xlsx"
    if ruta.exists():
        print(f"⏭ YA EXISTE → {ruta.name}")
        return str(ruta)
    df.to_excel(ruta, index=False)
    print(f"✔ Generado: {ruta.name}")
    return str(ruta)

def ruta_dia(fecha_str: str) -> Path:
    return BASE_INFOVALMER / fecha_str

# ============================================================
# 📥 LECTORES INFOVALMER (CONVERSIÓN A EXCEL)
# ============================================================
def _fuentes_infovalmer(fecha_str):
    sf = sufijo_fecha(fecha_str)
    base = ruta_dia(fecha_str)
    return {
        "SP": base / f"SP{sf}.001", "SW": base / f"SW{sf}.001",
        "MX": base / f"MX{sf}.txt", "MX_RV": base / f"MX{sf} RV.txt",
        "NOTAS": base / f"NOTAS_ESTRUCTURADAS{fecha_str}.txt",
        "TP": base / f"titulos_participativos_valoracion{fecha_str}.txt",
    }

def leer_SP(fecha_str):
    nombre = f"SP_{fecha_str}"
    fuentes = _fuentes_infovalmer(fecha_str)
    if not fuentes["SP"].exists(): return print(f"❌ SP no existe ({fecha_str})")
    datos = []
    with open(fuentes["SP"], "r", encoding="latin-1", errors="ignore") as f:
        for l in f:
            datos.append([
                l[0:7].strip(), l[7:8].strip(), l[8:20].strip(), l[20:32].strip(),
                l[32:50].strip(), l[50:51].strip(), l[51:59].strip(), l[59:67].strip(),
                l[67:75].strip(), l[75:76].strip(), l[76:77].strip(), l[77:81].strip(),
                l[81:84].strip(), l[84:85].strip(), l[85:89].strip(),
                parse_num_scalar(l[89:105]), l[105:109].strip(), l[109:110].strip(),
                parse_num_scalar(l[110:129]), l[129:137].strip(),
                parse_num_scalar(l[137:156]), l[156:168].strip(), parse_num_scalar(l[168:187])
            ])
    cols = ["Numero_Secuencia","Tipo_Registro","Nemo","ISIN","Numero_Emision","Estado",
            "Fecha_Publicacion","Fecha_Emision","Fecha_Vencimiento","Periodicidad","Modalidad",
            "Dias_Vencimiento","Moneda","Tipo_Tasa","Tipo_Tasa_Ref","Spread","Tipo_Calculo",
            "Base_Calculo","Precio_Valor_Calculado","Fecha_Ultimo_Precio","Ultimo_Precio",
            "Codigo_ISIN2","Precio_Limpio"]
    exportar_unificado(pd.DataFrame(datos, columns=cols), fecha_str, nombre)

def leer_SW(fecha_str):
    nombre = f"SW_{fecha_str}"
    fuentes = _fuentes_infovalmer(fecha_str)
    if not fuentes["SW"].exists(): return print(f"❌ SW no existe ({fecha_str})")
    patron = re.compile(r"^(?P<sec>\d+)(?P<tipo>[A-Z])(?P<nemo>[A-Z0-9\-]+)\s+(?P<fecha>\d{4}-\d{2}-\d{2})(?P<valor>.+)$")
    filas = []
    with open(fuentes["SW"], "r", encoding="latin-1", errors="ignore") as f:
        for l in f:
            m = patron.match(l.strip())
            if m:
                val = re.sub(r"[^\d.]", "", m.group("valor"))
                filas.append([m.group("sec"), m.group("tipo"), m.group("nemo"), m.group("fecha"), float(val) if val else None])
    exportar_unificado(pd.DataFrame(filas, columns=["Secuencia","Tipo","Nemo","Fecha","Valor"]), fecha_str, nombre)

def _leer_txt(fecha_str, tipo, nombre_archivo):
    nombre = f"{tipo}_{fecha_str}"
    fuentes = _fuentes_infovalmer(fecha_str)
    src = fuentes.get(tipo)
    if not src or not src.exists(): return print(f"❌ {tipo} no existe ({fecha_str})")
    header = None if tipo == "NOTAS" else 0
    df = pd.read_csv(src, header=header, dtype=str, encoding="latin-1")
    exportar_unificado(df, fecha_str, nombre)

def leer_MX(fecha_str): _leer_txt(fecha_str, "MX", "")
def leer_MX_RV(fecha_str): _leer_txt(fecha_str, "MX_RV", "")
def leer_NOTAS(fecha_str): _leer_txt(fecha_str, "NOTAS", "")

def leer_TP(fecha_str):
    nombre = f"TP_{fecha_str}"
    fuentes = _fuentes_infovalmer(fecha_str)
    if not fuentes["TP"].exists(): return print(f"❌ TP no existe ({fecha_str})")
    datos = []
    with open(fuentes["TP"], "r", encoding="latin-1", errors="ignore") as f:
        for l in f:
            if len(l) >= 29:
                datos.append([l[0:6].strip(), l[6:7].strip(), l[7:19].strip(), parse_num_scalar(l[19:29]), l[29:].strip()])
    exportar_unificado(pd.DataFrame(datos, columns=["Codigo","Tipo","ISIN","Precio","Descripcion"]), fecha_str, nombre)

def copiar_versiones_sp_sw(fecha_str):
    base = ruta_dia(fecha_str)
    sf = sufijo_fecha(fecha_str)
    if not base.exists(): return
    for pref in ["SP", "SW"]:
        dest = base / f"{pref}{sf}.001"
        if dest.exists(): continue
        candidatos = sorted([f for f in os.listdir(base) if re.match(rf"{pref}{sf}\.\d+$", f)], key=lambda x: int(x.split(".")[-1]), reverse=True)
        if candidatos:
            import shutil
            shutil.copy2(base / candidatos[0], dest)
            print(f"✅ Copiado {candidatos[0]} → {pref}{sf}.001")

def procesar_infovalmer(fecha_str):
    print(f"\n🚀 Procesando Infovalmer {fecha_str}")
    copiar_versiones_sp_sw(fecha_str)
    for fn in [leer_SP, leer_SW, leer_MX, leer_MX_RV, leer_NOTAS, leer_TP]:
        try: fn(fecha_str)
        except Exception as e: print(f"❌ {fn.__name__}: {e}")
    print(f"✅ Infovalmer {fecha_str} listo")

# ============================================================
# 💰 EXTRACCIÓN UVR (SELENIUM)
# ============================================================
def obtener_uvr(fecha_str):
    if not SELENIUM_OK: return None
    fecha_fmt = f"{fecha_str[:4]}/{fecha_str[4:6]}/{fecha_str[6:]}"
    url = "https://suameca.banrep.gov.co/estadisticas-economicas/informacionSerie/100005/unidad_valor_real_uvr"
    opts = Options()
    opts.add_argument("--headless=new"); opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-gpu"); opts.add_argument("--no-sandbox"); opts.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    try:
        driver.get(url)
        wait = WebDriverWait(driver, 40)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "app-root")))
        time.sleep(3)
        boton = wait.until(EC.presence_of_element_located((By.ID, "vistaTabla")))
        driver.execute_script("arguments[0].click();", boton)
        wait.until(EC.presence_of_element_located((By.ID, "highcharts-data-table-0")))
        time.sleep(2)
        html = driver.find_element(By.ID, "highcharts-data-table-0").get_attribute("outerHTML")
    finally:
        driver.quit()
    df = pd.read_html(html)[0]
    row = df[df.iloc[:, 0] == fecha_fmt]
    return float(row.iloc[0, 1]) if not row.empty else None

# ============================================================
# 💱 GENERACIÓN MONEDAS + UVR
# ============================================================
def generar_monedas(fecha_orig, fecha_habil, ayer_habil, uvr_hoy=None, uvr_ayer=None):
    def buscar_csv(fecha):
        for _ in range(30):
            path = ruta_dia(fecha) / f"monedas_matriz_info{fecha}.csv"
            if path.exists(): return path
            fecha = (datetime.strptime(fecha, "%Y%m%d") - timedelta(days=1)).strftime("%Y%m%d")
        return None

    def leer(p):
        df = pd.read_csv(p, sep=None, engine="python", dtype=str)
        df.columns = df.columns.str.strip().str.upper()
        df["RATE"] = pd.to_numeric(df["RATE"], errors="coerce")
        return df

    path_hoy = buscar_csv(fecha_habil)
    path_ayer = buscar_csv(ayer_habil)
    if not path_hoy or not path_ayer:
        return print(f"❌ No se encontró CSV de monedas para {fecha_habil}/{ayer_habil}")

    df_h = leer(path_hoy)
    df_a = leer(path_ayer)

    mapa = {"USD":"USDCOP", "EUR":"EURCOP", "MXN":"MXNCOP", "BRL":"BRLCOP", "GBP":"GBPCOP", "JPY":"JPYCOP", "CAD":"CADUSD"}
    filas = []
    for m, p in mapa.items():
        h_val = df_h.loc[df_h["PAIR"] == p, "RATE"]
        a_val = df_a.loc[df_a["PAIR"] == p, "RATE"]
        filas.append({"Moneda": m, "Precio Hoy": h_val.iloc[0] if not h_val.empty else np.nan,
                      "Precio Ayer": a_val.iloc[0] if not a_val.empty else np.nan})

    filas.append({"Moneda": "COP", "Precio Hoy": 1, "Precio Ayer": 1})
    filas.append({"Moneda": "UVR", "Precio Hoy": uvr_hoy, "Precio Ayer": uvr_ayer})
    df_mon = pd.DataFrame(filas)

    exportar_unificado(df_mon, fecha_orig, f"Monedas_{fecha_orig}")
    print(f"✅ Monedas generado ({fecha_orig}) | UVR Hoy: {uvr_hoy} | UVR Ayer: {uvr_ayer}")

# ============================================================
# 🚀 EJECUCIÓN PRINCIPAL
# ============================================================
if __name__ == "__main__":
    print(f"📂 Usuario detectado: {USER_HOME}")
    print(f"📁 Salida única: {OUTPUT_DIR.resolve()}\n")
    
    AYER_HABIL = ajustar_a_dia_habil(AYER)
    HOY_HABIL  = ajustar_a_dia_habil(HOY)
    AYER_UVR   = (FECHA_HOY - timedelta(days=1)).strftime("%Y%m%d")

    # 1. Convertir archivos Infovalmer
    procesar_infovalmer(AYER)
    procesar_infovalmer(HOY)

    # 2. Extraer UVR
    print("\n🔄 Extrayendo UVR...")
    uvr_h = obtener_uvr(HOY_HABIL) if HOY_HABIL == HOY else None
    uvr_a = obtener_uvr(AYER_UVR)
    print(f"💰 UVR HOY: {uvr_h} | UVR AYER: {uvr_a}")

    # 3. Generar Excel de Monedas + UVR
    print("\n🔄 Generando Monedas...")
    generar_monedas(HOY, HOY_HABIL, AYER_HABIL, uvr_h, uvr_a)

    print(f"\n✅ FINALIZADO. Todos los archivos están en: {OUTPUT_DIR}")