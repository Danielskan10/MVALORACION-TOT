# MVALORACION

Plataforma de revisión y control operativo de valoración financiera — **Skandia Colombia**.

---

## Arquitectura

```
MVALORACION/
│
├── app/                        # Backend FastAPI
│   ├── api_main.py             # Servidor, rutas estáticas, /api/logs
│   ├── config.py               # Carga/guarda config.yaml
│   └── routers/
│       ├── insumos.py          # Precios Infovalmer (SP, SW, SV, MX, NOTAS…)
│       ├── porfin.py           # Valoración Porfin 596/575
│       └── mitra.py            # Conciliación Mitra
│
├── modules/                    # Frontend modular — un módulo = una carpeta
│   └── insumos/
│       ├── index.html          # HTML limpio, sin lógica inline
│       ├── app.js              # Toda la lógica JS del módulo
│       ├── style.css           # CSS propio del módulo
│       └── router.py           # Copia de referencia del router backend
│
├── shared/                     # Recursos compartidos entre módulos
│   ├── design.css              # Tokens Skandia, dark/light, componentes
│   └── nav.js                  # toggleTheme(), apiFetch(), getPL(), fmtNum()…
│
├── frontend/                   # HTML en transición (legacy → módulos)
│   ├── index.html              # Dashboard principal
│   ├── porfin.html
│   ├── mitra.html
│   └── shared.css
│
├── config.yaml.example         # Plantilla — copiar a config.yaml
├── requirements.txt
└── run.py
```

---

## Módulos

| Módulo | Ruta | Descripción |
|--------|------|-------------|
| **Dashboard** | `/` | Resumen, configuración global, health, logs |
| **Insumos** | `/insumos.html` | Precios Infovalmer, alertas, curvas renta fija |
| **Porfin** | `/porfin.html` | Verificación valoración/causación FIC |
| **Mitra** | `/mitra.html` | Conciliación DI/DF, diferencias vs Porfin |

---

## Instalación

```powershell
git clone https://github.com/Danielskan10/MVALORACION-TOT.git
cd MVALORACION-TOT
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item config.yaml.example config.yaml
# Editar config.yaml con rutas locales
```

---

## Configuración (`config.yaml`)

```yaml
data_dir:        "C:/ruta/a/data"
infovalmer_dir:  "J:/VALORACION/.../INFOVALMER"  # Base con subcarpetas YYYYMMDD
ref_especies:    "C:/ruta/Especies.xlsx"
ref_fcpe:        "C:/ruta/FCPE.xlsx"
ref_fiduciaria:  "C:/ruta/Fiduciaria.xlsx"
ref_fondos:      "C:/ruta/Fondos.xlsx"
ref_fcp:         "C:/ruta/FCP.xlsx"

umbral_variacion_pct:       0.5
umbral_dif_causacion:    1000.0
umbral_dif_valoracion:  100000.0
umbral_dif_valoracion_pct: 0.01

host: "0.0.0.0"
port: 8000
```

La configuración **nunca se sube al repo** (`.gitignore`).
Usa ⚙️ Configuración en el Dashboard para editarla desde el navegador.

---

## Arrancar

```powershell
cd app
python api_main.py
# → http://localhost:8000
```

---

## API principales

| Endpoint | Descripción |
|----------|-------------|
| `GET /api/config` | Lee configuración |
| `POST /api/config` | Actualiza configuración |
| `GET /api/logs` | Últimas entradas de log |
| `GET /api/insumos/fechas` | Fechas disponibles |
| `GET /api/insumos/proveedores/{fecha}` | Proveedores con datos esa fecha |
| `GET /api/insumos/datos/{fecha}/{prov}` | Datos crudos por proveedor |
| `GET /api/insumos/alertas/{fecha}` | Variaciones de precio del día |
| `GET /api/insumos/alertas_multidia/{fecha}` | Alertas persistentes N días |
| `GET /api/insumos/historico/{isin}` | Serie histórica de un ISIN |
| `GET /api/insumos/sp_curvas/{fecha}` | Curva TIR vs Plazo |
| `POST /api/insumos/convertir/{fecha}` | Convierte archivos Infovalmer |
| `GET /api/docs` | Swagger UI |

---

## Diseño

- **Colores Skandia**: Verde `#00A65A` · Negro `#0F0F0F`
- **Tema**: Dark (default) / Light — persiste en `localStorage`
- **Gráficas**: Plotly.js interactivo, adaptado al tema
- **Fuente**: Inter

---

## Estructura Infovalmer

```
infovalmer_dir/
  20260514/
    SP*.001        ← Renta fija BVC (ancho fijo)
    SW*.001        ← Swaps BVC
    SV*.001        ← Renta variable BVC
    SB*.001        ← Bonos BVC
    MX*.txt        ← Mercado externo (tab-separated)
    MX*_RV.txt     ← RV externa
    NOTAS*.csv     ← Notas estructuradas
```

---

## No se sube al repo

`config.yaml` · `data/` · `examples/` · `venv/` · `*.xlsx` · `.claude/`
