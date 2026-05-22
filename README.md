# MVALORACION — Control Operativo de Valoración Financiera

> Plataforma web para revisión diaria de insumos, valoraciones, causaciones y operaciones de portafolio. Detecta errores operativos, variaciones anormales y diferencias de precios antes de la entrega de información final.

---

## Índice

1. [Descripción](#1-descripción)
2. [Arquitectura](#2-arquitectura)
3. [Requisitos](#3-requisitos)
4. [Instalación rápida (PC corporativo)](#4-instalación-rápida-pc-corporativo)
5. [Configuración completa](#5-configuración-completa)
6. [Estructura de archivos esperada](#6-estructura-de-archivos-esperada)
7. [Uso diario](#7-uso-diario)
8. [Módulos de la aplicación](#8-módulos-de-la-aplicación)
9. [API REST](#9-api-rest)
10. [Solución de problemas corporativos](#10-solución-de-problemas-corporativos)
11. [Para el agente Copilot — Setup automático](#11-para-el-agente-copilot--setup-automático)

---

## 1. Descripción

MVALORACION es una aplicación web local que corre en el PC del analista de valoración. Sirve para:

| Módulo | Qué hace |
|---|---|
| **Insumos** | Revisa archivos SP, SW, SV, MX, TP, NOTAS de Infovalmer. Detecta precios faltantes, variaciones anormales vs día anterior. |
| **Porfin 596/575** | Verifica posiciones y causaciones exportadas desde Porfin. Detecta títulos sin precio, valoraciones negativas, diferencias causación MER vs TIR. |
| **Verificación** | Recalcula valoración manual con precios Infovalmer y compara contra lo que reportó Porfin. Detecta diferencias con umbral configurable. |
| **Mitra** | Revisa archivo base Mitra (fiduciaria). Valida precios DI/DF, causaciones, fuentes de precio. |
| **Análisis** | 7 gráficas: scatter precio vs TIR, histograma valores, concentración top-10, distribución por vencimiento, box TIR por portafolio. |
| **Variaciones** | Compara dos fechas del 596. Detecta variaciones de valor mercado por encima del umbral. |
| **Operaciones 583** | Informe de operaciones del día. Cobros de interés/dividendo, compras/ventas, ajustes de causación. |

---

## 2. Arquitectura

```
MVALORACION/
├── app/                        ← Backend Python (FastAPI)
│   ├── api_main.py             ← Servidor principal, rutas de config y upload
│   ├── config.py               ← Lectura/escritura de config.yaml
│   └── routers/
│       ├── porfin.py           ← 596, 575, 583, verificación, fondos, variaciones
│       ├── mitra.py            ← Archivo Mitra / revisión bolsa
│       └── insumos.py          ← SP, SW, SV, MX, TP, NOTAS, monedas
├── frontend/                   ← HTML/JS (Plotly, sin frameworks)
│   ├── index.html              ← Dashboard principal
│   ├── porfin.html             ← Porfin 596/575/583 + Análisis + Variaciones
│   ├── mitra.html              ← Revisión Mitra
│   └── insumos.html            ← Revisión de insumos
├── data/                       ← Datos locales (NO se sube a git)
│   ├── Especies.csv            ← Catálogo maestro LLAVE → TIPO
│   ├── FCPE.xlsx               ← Referencia FCPE
│   └── YYYYMMDD/               ← Una carpeta por fecha
│       ├── 596YYYYMMDD.CSV
│       ├── SKCLI575*.CSV
│       ├── 583YYYYMMDD.CSV
│       └── MITRA_*.xlsx
├── config.yaml                 ← Configuración local (NO se sube a git)
├── config.yaml.example         ← Plantilla de configuración con documentación
├── requirements.txt            ← Dependencias Python
├── run.py                      ← Punto de entrada del servidor
├── setup.ps1                   ← Script de instalación automática
└── MVALORACION.bat             ← Lanzador de un clic (generado por setup.ps1)
```

**Stack:**
- Backend: Python 3.10+ · FastAPI · Uvicorn · Pandas · NumPy · OpenPyXL · PyYAML
- Frontend: HTML5 · JavaScript vanilla · Plotly.js 2.27
- Sin base de datos: los datos son archivos CSV/Excel del día, las observaciones se guardan en JSON junto a los datos.

---

## 3. Requisitos

### PC corporativo
- Windows 10 / 11 (64-bit)
- Python **3.10 o superior** — [python.org/downloads](https://www.python.org/downloads/)
- Acceso a la unidad `J:\VALORACION\...` (o ruta equivalente con los archivos Infovalmer)
- Acceso a los archivos 596, 575, 583 exportados desde Porfin
- Acceso al archivo Mitra (Excel)
- Conexión a internet **solo** para la instalación inicial de paquetes pip (o instalación offline — ver sección 10)

### Paquetes Python (se instalan solos con `setup.ps1`)
```
pandas >= 2.0
numpy >= 1.24
openpyxl >= 3.1
fastapi >= 0.110
uvicorn[standard] >= 0.27
pydantic >= 2.0
python-multipart >= 0.0.9
PyYAML >= 6.0
holidays >= 0.45
```

---

## 4. Instalación rápida (PC corporativo)

### Paso 1 — Obtener el código

**Opción A — con Git:**
```powershell
git clone https://github.com/<org>/MVALORACION.git
cd MVALORACION
```

**Opción B — sin Git (descarga ZIP):**
1. Ir a GitHub → botón verde **Code** → **Download ZIP**
2. Extraer en `C:\MVALORACION\`
3. Abrir PowerShell en esa carpeta

### Paso 2 — Ejecutar el instalador

```powershell
powershell -ExecutionPolicy Bypass -File setup.ps1
```

El script automáticamente:
- ✅ Detecta la versión de Python instalada
- ✅ Crea el entorno virtual `venv/`
- ✅ Instala todas las dependencias
- ✅ Genera `config.yaml` con rutas por defecto
- ✅ Crea `MVALORACION.bat` (lanzador doble clic)
- ✅ Crea acceso directo en el escritorio
- ✅ Verifica que todo importa correctamente

### Paso 3 — Configurar rutas

Editar `config.yaml` (se crea en la raíz del proyecto):

```yaml
data_dir: "C:\\MVALORACION\\data"
infovalmer_dir: "J:\\VALORACION\\VALORACION_ESPECIAL\\Bolsa\\INFOVALMER"
ref_especies: "C:\\MVALORACION\\data\\Especies.csv"
port: 8000
```

Ver [Sección 5](#5-configuración-completa) para todas las opciones.

### Paso 4 — Iniciar

```
Doble clic en MVALORACION.bat
```
o desde PowerShell:
```powershell
python run.py
```

Abrir en el navegador: **http://localhost:8000**

---

## 5. Configuración completa

El archivo `config.yaml` (en la raíz del proyecto) controla todo el comportamiento. Está documentado en `config.yaml.example`.

```yaml
# ── Rutas principales ──────────────────────────────────────────────────────
data_dir: "C:\\MVALORACION\\data"
# Carpeta donde van las subcarpetas diarias (YYYYMMDD/) con los archivos 596, 575, 583, Mitra.
# También aquí van los catálogos maestros (Especies.csv, FCPE.xlsx, etc.)

infovalmer_dir: "J:\\VALORACION\\VALORACION_ESPECIAL\\Bolsa\\INFOVALMER"
# Directorio raíz de Infovalmer. Estructura: <infovalmer_dir>\<YYYYMMDD>\SP<mmddyy>.001
# Si la unidad J: no existe, mapear la carpeta de red o ajustar la ruta.

# ── Catálogos de referencia ────────────────────────────────────────────────
ref_especies:   "C:\\MVALORACION\\data\\Especies.csv"
ref_fcpe:       "C:\\MVALORACION\\data\\FCPE.xlsx"
ref_fiduciaria: "C:\\MVALORACION\\data\\FIDUCIARIA0210.xlsx"
ref_fondos:     "C:\\MVALORACION\\data\\FONDOS.xlsx"
ref_fcp:        "C:\\MVALORACION\\data\\FCP.xlsx"

# ── Umbrales de alerta ─────────────────────────────────────────────────────
umbral_variacion_pct:      5.0    # % variación precio para alerta
umbral_dif_causacion:      1.0    # COP dif causación para alerta
umbral_dif_valoracion:     1000.0 # COP dif valoración (verificación)
umbral_dif_valoracion_pct: 1.0    # % dif valoración (verificación)

# ── Servidor ───────────────────────────────────────────────────────────────
port:   8000
host:   "0.0.0.0"    # "127.0.0.1" = solo local | "0.0.0.0" = red interna
reload: true         # false en producción

# ── Proxy (entorno corporativo) ────────────────────────────────────────────
proxy:    ""         # "http://proxy.empresa.com:8080"
ssl_cert: ""         # "C:\\certs\\corporativo.pem"
ssl_verify: true
```

### Parámetros del instalador (setup.ps1)

| Parámetro | Descripción | Ejemplo |
|---|---|---|
| `-PythonExe` | Ruta explícita al python.exe | `-PythonExe "C:\Python312\python.exe"` |
| `-ProxyUrl` | Proxy corporativo para pip | `-ProxyUrl "http://proxy:8080"` |
| `-DataDir` | Directorio de datos | `-DataDir "D:\Datos\Valoracion"` |
| `-InfovalmerDir` | Ruta archivos Infovalmer | `-InfovalmerDir "\\srv\infovalmer"` |
| `-Port` | Puerto del servidor | `-Port 8080` |
| `-NoVenv` | Instalar en Python global | `-NoVenv` |
| `-Force` | Recrear el venv | `-Force` |

Ejemplo con proxy corporativo:
```powershell
powershell -ExecutionPolicy Bypass -File setup.ps1 `
  -ProxyUrl "http://proxy.empresa.com:8080" `
  -DataDir "D:\Valoracion\data" `
  -Port 8080
```

---

## 6. Estructura de archivos esperada

### Directorio `data/` (configurado en `data_dir`)

```
data/
├── Especies.csv                  ← REQUERIDO para verificación de valoración
│                                    Columnas: LLAVE;TIPO  (sep ";", latin-1)
├── FCPE.xlsx                     ← Opcional: fondos capital privado
├── FIDUCIARIA0210.xlsx           ← Opcional: referencia fiduciaria
├── FONDOS.xlsx                   ← Opcional: catálogo fondos
├── FCP.xlsx                      ← Opcional: fondos capital privado
│
├── 20260515/                     ← Carpeta del día (formato YYYYMMDD)
│   ├── 59620260515.CSV           ← Porfin 596 — posiciones y valoraciones
│   ├── SKCLI575_20260515.CSV     ← Porfin 575 — causaciones
│   ├── 58320260515.CSV           ← Porfin 583 — operaciones (OPCIONAL)
│   ├── MITRA_20260515.xlsx       ← Archivo Mitra / revisión bolsa
│   ├── obs_porfin596_20260515.json    ← Observaciones (generado por la app)
│   └── obs_porfin575_20260515.json    ← Observaciones (generado por la app)
│
└── 20260516/
    └── ...
```

### Archivos Infovalmer (`infovalmer_dir`)

```
J:\VALORACION\VALORACION_ESPECIAL\Bolsa\INFOVALMER\
└── 20260515\
    ├── SP051526.001              ← Precios renta fija BVC (fixed-width)
    ├── SW051526.001              ← Precios secundarios
    ├── SV051526.001              ← Tasas de referencia
    ├── MX051526.txt              ← Renta fija internacional
    ├── MX051526_RV.txt           ← Renta variable (ETFs, ADRs)
    ├── NOTAS_ESTRUCTURADAS_20260515.txt
    └── titulos_participativos_valoracion_20260515.txt
```

> **Nota sobre nombres de archivo:** Los archivos SP/SW/SV usan el sufijo `MMDDYY` (ej: `SP051526.001` para el 15-may-2026). Los archivos MX usan el mismo sufijo pero extensión `.txt`.

### Naming de archivos Porfin

| Archivo | Patrón | Descripción |
|---|---|---|
| 596 | `596YYYYMMDD.CSV` o `596*.CSV` | Posiciones de portafolio |
| 575 | `SKCLI575*.CSV` o `*575*.CSV` | Causaciones |
| 583 | `583YYYYMMDD.CSV` o `*583*.CSV` | Informe de operaciones |

---

## 7. Uso diario

### Flujo típico

```
1. Abrir MVALORACION.bat (doble clic)
2. Ir a http://localhost:8000
3. En "Porfin 596/575":
   a. Clic en ⬆ Cargar → seleccionar fecha YYYYMMDD
   b. Cargar archivo 596 (posiciones)
   c. Cargar archivo 575 (causaciones)
   d. Cargar archivo 583 (operaciones, opcional pero recomendado)
   e. Revisar KPIs: sin precio, valor mercado total, causación
   f. Tab "Errores" → verificar no haya ALTO
   g. Tab "TIR/DV" → revisar títulos valorando a TIR cuando no corresponde
   h. Tab "Verificación" → clic en "Calcular verificación"
   i. Tab "Análisis" → revisar gráficas de concentración y distribución
4. En "Insumos":
   a. Seleccionar fecha
   b. Revisar SP/SW/MX — variaciones de precio vs día anterior
5. En "Mitra":
   a. Cargar archivo Mitra del día
   b. Revisar causaciones DI/DF y diferencias vs Porfin
6. Exportar Excel de revisión: botón "📥 Excel"
```

### Atajos útiles

| Acción | Cómo |
|---|---|
| Tema claro/oscuro | Botón 🌙/☀ en la barra de navegación |
| Buscar en tabla | Campo "Buscar" en la barra de filtros |
| Filtrar solo alertas | Checkbox "Solo alertas" |
| Agregar observación | Clic en campo OBS → escribir → Enter |
| Exportar CSV | Botón "⬇ CSV" |
| Exportar Excel completo | Botón "📥 Excel" |
| Comparar fechas | Tab "Variaciones" → seleccionar fecha inicio y fin |

---

## 8. Módulos de la aplicación

### Dashboard (`/`)
Resumen del día: estado de archivos cargados, KPIs globales, accesos directos a módulos.

### Porfin 596/575 (`/porfin.html`)
| Tab | Contenido |
|---|---|
| Posiciones 596 | Tabla completa con alertas de sin-precio, obs manuales, filtros |
| Causaciones 575 | Detalle causación MER vs TIR, diferencias, obs |
| Fondos | Agrupación por fondo: valor mercado, causación, delta, alertas. Gráfica Caus Mer vs TIR |
| TIR/DV | Títulos valorando a TIR/curva propia. Detecta METODO=DV, FUENTE=1DV, Mét=TC |
| Verificación | Recalcula valor manual con precios Infovalmer. Gráficas de distribución de diferencias |
| Operaciones 583 | Compras/ventas, cobros interés/dividendo, inc/ret capital. Gráficas por tipo |
| Errores | Posiciones sin precio, valoraciones negativas, nominal cero. Gráficas por severidad |
| Portafolios | Distribución por portafolio con gráfica de barras y pie |
| Monedas | Distribución por moneda (valor y posiciones) |
| **📊 Análisis** | Scatter precio vs TIR, histograma valores, por clase, Vlr vs Nominal, por vencimiento, concentración top-10, box TIR |
| **📅 Variaciones** | Comparación entre dos fechas: top variaciones absolutas y %, histograma distribución |

### Insumos (`/insumos.html`)
Precios Infovalmer por proveedor: SP (BVC), SW (secundarios), SV (tasas), MX (internacional), TP (participativos), NOTAS (estructuradas), monedas.

### Mitra (`/mitra.html`)
Archivo base Mitra: posiciones, precios DI/DF, causaciones calculadas vs reportadas, diferencias vs Porfin, variaciones entre fechas.

---

## 9. API REST

La aplicación expone una API REST documentada en **http://localhost:8000/api/docs**

### Endpoints principales

```
GET  /api/porfin/fechas                     → fechas disponibles
GET  /api/porfin/resumen/{fecha}            → KPIs del día
GET  /api/porfin/posiciones/{fecha}         → tabla 596 con filtros
GET  /api/porfin/causaciones/{fecha}        → tabla 575
GET  /api/porfin/errores/{fecha}            → errores detectados
GET  /api/porfin/fondos/{fecha}             → agrupación por fondo
GET  /api/porfin/fondos/{fecha}/{fondo}     → detalle de un fondo
GET  /api/porfin/monedas/{fecha}            → distribución por moneda
GET  /api/porfin/variaciones/{fi}/{ff}      → variaciones entre fechas
GET  /api/porfin/alertas_tir/{fecha}        → títulos valorando a TIR
GET  /api/porfin/verificacion/{fecha}       → verificación vs Infovalmer
GET  /api/porfin/verificacion_causacion/{fecha}  → verificación causación
GET  /api/porfin/operaciones/{fecha}        → informe operaciones 583
GET  /api/porfin/excel/{fecha}              → descarga Excel de revisión
POST /api/porfin/observaciones/{fecha}      → guardar obs manual
GET  /api/insumos/fechas                    → fechas con insumos
GET  /api/insumos/sp/{fecha}               → precios SP
GET  /api/insumos/mx/{fecha}               → precios MX
GET  /api/mitra/resumen/{fecha}             → resumen Mitra
GET  /api/mitra/posiciones/{fecha}          → posiciones Mitra
GET  /api/config                            → configuración actual
POST /api/config                            → actualizar configuración
POST /api/upload/{modulo}                   → subir archivo (porfin/mitra/insumos)
```

---

## 10. Solución de problemas corporativos

### Error: pip falla por SSL (certificado corporativo)

```powershell
# Opción 1: pasar certificado corporativo
setup.ps1 -ProxyUrl "http://proxy:8080"

# Opción 2: deshabilitar verificación SSL (solo si no hay alternativa)
pip install -r requirements.txt --trusted-host pypi.org --trusted-host files.pythonhosted.org
```

### Error: Python no encontrado

```powershell
# Indicar la ruta explícita
setup.ps1 -PythonExe "C:\Users\usuario\AppData\Local\Programs\Python\Python312\python.exe"
```

### Error: Puerto 8000 ocupado

Editar `config.yaml`:
```yaml
port: 8080
```
O usar otro puerto en el bat:
```
python run.py --port 8080
```

### La unidad J: no está disponible

1. Mapear la carpeta de red como unidad J: en Windows
2. O editar `config.yaml`:
   ```yaml
   infovalmer_dir: "\\\\servidor\\valoracion\\INFOVALMER"
   ```
3. O copiar los archivos Infovalmer diariamente a la carpeta `data/YYYYMMDD/`

### Instalación offline (sin internet)

```powershell
# En un PC con internet, descargar los wheels:
pip download -r requirements.txt -d wheels/

# Copiar la carpeta wheels/ al PC sin internet y ejecutar:
pip install --no-index --find-links=wheels/ -r requirements.txt
```

### Acceso desde otro equipo de la red

1. `config.yaml`: `host: "0.0.0.0"`
2. Abrir puerto en Firewall de Windows:
   ```powershell
   netsh advfirewall firewall add rule name="MVALORACION" dir=in action=allow protocol=TCP localport=8000
   ```
3. El colega accede a: `http://<IP-del-PC>:8000`

---

## 11. Para el agente Copilot — Setup automático

> Esta sección es una guía de instrucciones paso a paso para que un agente de GitHub Copilot (o cualquier asistente de código) realice la instalación completa desde cero.

### Contexto del proyecto

- **Repositorio:** `https://github.com/<org>/MVALORACION`
- **Lenguaje principal:** Python 3.10+
- **Framework backend:** FastAPI + Uvicorn
- **Frontend:** HTML/JS vanilla + Plotly.js (sin npm, sin node)
- **OS objetivo:** Windows 10/11 corporativo
- **Sin base de datos:** datos en archivos CSV/Excel/JSON locales

---

### Instrucciones para el agente

#### Paso 1 — Clonar el repositorio

```powershell
git clone https://github.com/<org>/MVALORACION.git C:\MVALORACION
cd C:\MVALORACION
```

#### Paso 2 — Ejecutar el instalador automático

```powershell
# Instalación estándar
powershell -ExecutionPolicy Bypass -File setup.ps1

# Con proxy corporativo
powershell -ExecutionPolicy Bypass -File setup.ps1 -ProxyUrl "http://proxy.empresa.com:8080"

# Con python en ruta no estándar
powershell -ExecutionPolicy Bypass -File setup.ps1 -PythonExe "C:\Python312\python.exe"
```

El instalador hace todo automáticamente. Si termina con `✓ INSTALACIÓN COMPLETA`, continuar al paso 3.

#### Paso 3 — Ajustar config.yaml según el entorno

Editar `C:\MVALORACION\config.yaml`. Las rutas críticas a configurar:

```yaml
# OBLIGATORIO: directorio de datos del día
data_dir: "C:\\MVALORACION\\data"

# OBLIGATORIO si se usa verificación de precios Infovalmer
infovalmer_dir: "J:\\VALORACION\\VALORACION_ESPECIAL\\Bolsa\\INFOVALMER"

# OBLIGATORIO para verificación de valoración manual
ref_especies: "C:\\MVALORACION\\data\\Especies.csv"

# Puerto (cambiar si 8000 está ocupado)
port: 8000
```

Ver `config.yaml.example` para la documentación completa de cada parámetro.

#### Paso 4 — Crear estructura de datos

```powershell
# Crear carpeta de datos si no existe
New-Item -ItemType Directory -Force "C:\MVALORACION\data"

# Copiar catálogos de referencia (pedirlos al área de valoración):
# - Especies.csv  (LLAVE;TIPO, sep=";", encoding latin-1)
# - FCPE.xlsx
# - FIDUCIARIA0210.xlsx
# - FONDOS.xlsx
# - FCP.xlsx
```

#### Paso 5 — Verificar instalación

```powershell
cd C:\MVALORACION
venv\Scripts\python.exe -c "
import sys
sys.path.insert(0, 'app')
from routers import porfin, mitra, insumos
from config import get_config
cfg = get_config()
print('OK — config:', cfg['data_dir'])
"
```

Debe imprimir `OK — config: C:\MVALORACION\data`

#### Paso 6 — Iniciar el servidor

```powershell
# Opción A: doble clic en MVALORACION.bat (generado por setup.ps1)

# Opción B: PowerShell
cd C:\MVALORACION
venv\Scripts\python.exe run.py
```

Abrir navegador: **http://localhost:8000**

---

### Checklist de verificación (para el agente)

El agente debe confirmar cada ítem antes de dar la instalación por completa:

```
[ ] 1. git clone exitoso — carpeta C:\MVALORACION existe y tiene app/, frontend/, run.py
[ ] 2. setup.ps1 terminó con "✓ INSTALACIÓN COMPLETA"
[ ] 3. venv/Scripts/python.exe existe
[ ] 4. import fastapi, uvicorn, pandas, numpy, openpyxl, yaml — todos OK
[ ] 5. config.yaml existe en la raíz del proyecto
[ ] 6. config.yaml tiene data_dir apuntando a una carpeta existente o creada
[ ] 7. python run.py arranca sin errores (mensaje: "MVALORACION iniciando en http://localhost:8000")
[ ] 8. http://localhost:8000 responde con la página de inicio (Dashboard)
[ ] 9. http://localhost:8000/api/docs carga la documentación Swagger
[ ] 10. (Opcional) config.yaml tiene infovalmer_dir y ref_especies configurados
```

---

### Troubleshooting para el agente

| Síntoma | Diagnóstico | Solución |
|---|---|---|
| `python: command not found` | Python no está en PATH | Usar `-PythonExe` en setup.ps1 o instalar Python |
| `SSL: CERTIFICATE_VERIFY_FAILED` | Proxy corporativo con inspección SSL | Agregar `-ProxyUrl` y obtener certificado .pem corporativo |
| `ModuleNotFoundError: No module named 'fastapi'` | venv no activado o paquetes no instalados | Ejecutar `venv\Scripts\pip install -r requirements.txt` |
| `OSError: [Errno 98] Address already in use` | Puerto 8000 ocupado | Cambiar `port: 8001` en config.yaml |
| `FileNotFoundError: config.yaml` | setup.ps1 no se ejecutó | Ejecutar setup.ps1 o copiar config.yaml.example como config.yaml |
| Tab "Verificación" no muestra precios | Infovalmer no disponible o ruta incorrecta | Verificar `infovalmer_dir` en config.yaml |
| Tab "Verificación" muestra "Sin tipo activo" | Especies.csv no configurado | Configurar `ref_especies` y verificar que el archivo existe |

---

## Contribuir / Actualizar

```powershell
# Actualizar desde GitHub
git pull origin main

# Si se agregan nuevas dependencias
venv\Scripts\pip install -r requirements.txt --upgrade
```

---

## Licencia

Uso interno — Sapienza Inversiones. No distribuir.

---

*Generado con Claude Code · Última actualización: 2026-05-22*
