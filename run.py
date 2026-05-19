#!/usr/bin/env python3
"""
Arranque rápido de MVALORACION.
Ejecutar desde la raíz del proyecto:
    python run.py
Abre:  http://localhost:8000
"""
import sys
from pathlib import Path

# Agrega app/ al path para que los imports funcionen
sys.path.insert(0, str(Path(__file__).parent / "app"))

import uvicorn

if __name__ == "__main__":
    print("🚀  MVALORACION  →  http://localhost:8000")
    uvicorn.run("api_main:app", host="0.0.0.0", port=8000, reload=True,
                reload_dirs=[str(Path(__file__).parent / "app")])
