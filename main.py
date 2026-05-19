#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MAIN.PY - Orquestador Central MVALORACION
Ejecuta todo el pipeline, lanza APIs y dashboard desde un solo lugar.
Uso: python main.py --all  (o combina banderas según necesidad)
"""
from __future__ import annotations

import os
import sys
import time
import signal
import logging
import subprocess
import argparse
from pathlib import Path
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    import yaml
except ImportError:
    yaml = None

# ──────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN Y LOGGING
# ──────────────────────────────────────────────────────────────────────
BASE_OUTPUT = Path("./MVALORACION")
CONFIG_FILE = Path("config.yaml")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("mvaloracion_orchestrator")

# ──────────────────────────────────────────────────────────────────────
# ORQUESTADOR
# ──────────────────────────────────────────────────────────────────────
class MValoracionOrchestrator:
    def __init__(self):
        self.config = self._load_config()
        self.processes = []
        self._resolve_paths()
        self._setup_signals()

    def _load_config(self):
        if CONFIG_FILE.exists() and yaml is not None:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        if CONFIG_FILE.exists() and yaml is None:
            logger.warning("config.yaml existe, pero PyYAML no esta instalado. Se usaran valores por defecto.")
        return {}

    def _resolve_paths(self):
        cfg = self.config
        self.fecha_hoy = cfg.get("fechas", {}).get("hoy", "20260429")
        self.sql_mode = cfg.get("modos", {}).get("sql", True)
        self.enable_mitra = cfg.get("modos", {}).get("procesar_mitra", True)
        self.enable_porfin = cfg.get("modos", {}).get("procesar_porfin", False)
        self.enable_uvr = cfg.get("modos", {}).get("extraccion_uvr", True)

        rutas = cfg.get("rutas", {})
        self.infovalmer_dir = Path(rutas.get("base_infovalmer", ""))
        self.mitra_base = Path(rutas.get("base_mitra", ""))
        self.ruta_596 = Path(rutas.get("ruta_596", ""))
        self.especies = Path(rutas.get("especies", ""))
        self.fondos_mutuos = Path(rutas.get("fondos_mutuos", ""))

        # Fallback automático a rutas de usuario
        home = Path.home()
        if not self.mitra_base.exists():
            self.mitra_base = home / "OneDrive - Skandia Colombia/pmitra"
        if not self.especies.exists():
            self.especies = home / "OneDrive - Skandia Colombia/Valoracion General/MREVISION NEW/Especies.csv"
        if not self.fondos_mutuos.exists():
            self.fondos_mutuos = home / "OneDrive - Skandia Colombia/Valoracion General/MREVISION NEW/Fondos Mutuos.xlsx"

    def _setup_signals(self):
        def shutdown(sig, frame):
            logger.info("\n🛑 Recibida señal de apagado. Limpiando procesos...")
            for p in self.processes:
                if p.poll() is None:
                    p.terminate()
            sys.exit(0)
        signal.signal(signal.SIGINT, shutdown)
        signal.signal(signal.SIGTERM, shutdown)

    @staticmethod
    def _script_path(*candidates: str) -> Path | None:
        for candidate in candidates:
            path = Path(candidate)
            if path.exists():
                return path
        return None

    @staticmethod
    def _validate_date(value: str) -> str:
        try:
            datetime.strptime(value, "%Y%m%d")
        except ValueError as exc:
            raise ValueError(f"Fecha invalida '{value}'. Usa formato YYYYMMDD.") from exc
        return value

    def _run_script(self, description: str, candidates: tuple[str, ...], *args: str, required: bool = False) -> bool:
        script = self._script_path(*candidates)
        if script is None:
            msg = f"{description}: no se encontro ninguno de estos scripts: {', '.join(candidates)}"
            if required:
                logger.error(msg)
            else:
                logger.warning(msg)
            return False
        try:
            subprocess.run([sys.executable, str(script), *map(str, args)], check=True)
            return True
        except subprocess.CalledProcessError as exc:
            logger.error("%s fallo con codigo %s", description, exc.returncode)
        except OSError as exc:
            logger.error("%s no pudo ejecutarse: %s", description, exc)
        return False

    # ── PIPELINES ─────────────────────────────────────────────────────
    def run_conversion(self):
        logger.info("📥 Convirtiendo archivos Infovalmer...")
        self._run_script("Conversion Infovalmer", ("convertidor_mvaloracion.py",), self.fecha_hoy)

    def run_uvrs_monedas(self):
        if not self.enable_uvr:
            return
        logger.info("💰 Extrayendo UVR y generando Monedas...")
        self._run_script("Extraccion UVR/Monedas", ("extraer_uvr_monedas.py",), self.fecha_hoy)

    def run_mitra(self):
        if not self.enable_mitra:
            return
        logger.info("🔵 Ejecutando pipeline Mitra...")
        self._run_script(
            "Pipeline Mitra",
            ("pipeline_mitra.py",),
            self.fecha_hoy,
            str(self.mitra_base),
            "SI" if self.sql_mode else "NO",
            required=True,
        )

    def run_porfin(self):
        if not self.enable_porfin:
            return
        if not self.ruta_596.exists():
            logger.error("❌ Ruta 596 no configurada o no existe. Omitiendo Porfin.")
            return
        logger.info("🟢 Ejecutando pipeline Porfin...")
        self._run_script("Pipeline Porfin", ("pipeline_porfin.py",), self.fecha_hoy, str(self.ruta_596), required=True)

    # ── SERVICIOS ─────────────────────────────────────────────────────
    def launch_apis(self):
        cfg = self.config.get("api", {})
        port_m = cfg.get("mitra_port", 8001)
        port_p = cfg.get("porfin_port", 8002)

        logger.info("🌐 Lanzando APIs: Mitra (:%s) | Porfin (:%s)", port_m, port_p)
        for candidates, port in [
            (("backend_mitra.py", "RevMitra.py"), port_m),
            (("backend_porfin.py", "RevPorfin.py"), port_p),
        ]:
            script = self._script_path(*candidates)
            if script:
                p = subprocess.Popen([sys.executable, str(script), "--port", str(port)])
                self.processes.append(p)
                time.sleep(1)
            else:
                logger.warning("⚠️ API omitida. No se encontro ninguno de: %s", ", ".join(candidates))

    def launch_dashboard(self):
        port_d = self.config.get("dashboard_port", 8501)
        logger.info("🖥️ Lanzando Dashboard en :%s", port_d)
        if Path("dashboard_app.py").exists():
            p = subprocess.Popen([
                sys.executable, "-m", "streamlit", "run", "dashboard_app.py",
                "--server.port", str(port_d),
            ])
            self.processes.append(p)
        elif Path("Insumos.py").exists():
            p = subprocess.Popen([sys.executable, "Insumos.py", "--hoy", self.fecha_hoy, "--puerto", str(port_d)])
            self.processes.append(p)
        else:
            logger.warning("⚠️ No se encontro dashboard_app.py ni Insumos.py.")

    # ── CONTROL PRINCIPAL ─────────────────────────────────────────────
    def execute_all(self, run_apis=True, run_dashboard=True):
        self.fecha_hoy = self._validate_date(self.fecha_hoy)
        BASE_OUTPUT.mkdir(exist_ok=True)
        logger.info(f"📅 Fecha operativa: {self.fecha_hoy}")
        logger.info(f"📂 Salida unificada: {BASE_OUTPUT.resolve()}")

        logger.info("🔄 EJECUTANDO PIPELINE COMPLETO...")
        self.run_conversion()
        self.run_uvrs_monedas()
        self.run_mitra()
        self.run_porfin()

        if run_apis:
            self.launch_apis()
        if run_dashboard:
            self.launch_dashboard()

        if self.processes:
            logger.info("✅ Pipeline finalizado. Servicios activos (Ctrl+C para detener).")
            self._keep_alive()
        else:
            logger.info("✅ Pipeline finalizado. No hay servicios activos.")

    def _keep_alive(self):
        try:
            while True:
                self.processes = [p for p in self.processes if p.poll() is None]
                if not self.processes:
                    logger.info("Todos los servicios finalizaron.")
                    return
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("\n👋 Apagando manualmente...")
            sys.exit(0)

# ──────────────────────────────────────────────────────────────────────
# CLI & ENTRY POINT
# ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Orquestador MVALORACION")
    parser.add_argument("--date", type=str, help="Fecha operativa YYYYMMDD (override config.yaml)")
    parser.add_argument("--mitra", action="store_true", help="Solo ejecutar Mitra")
    parser.add_argument("--porfin", action="store_true", help="Solo ejecutar Porfin")
    parser.add_argument("--no-apis", action="store_true", help="No lanzar APIs")
    parser.add_argument("--no-dashboard", action="store_true", help="No lanzar Dashboard")
    parser.add_argument("--all", action="store_true", help="Ejecutar pipeline completo + servicios")
    args = parser.parse_args()

    orch = MValoracionOrchestrator()
    if args.date:
        orch.fecha_hoy = orch._validate_date(args.date)
    if args.mitra:
        orch.enable_mitra = True
        orch.enable_porfin = False
    if args.porfin:
        orch.enable_porfin = True
        orch.enable_mitra = False

    if args.all or (not args.mitra and not args.porfin):
        orch.execute_all(run_apis=not args.no_apis, run_dashboard=not args.no_dashboard)
    else:
        BASE_OUTPUT.mkdir(exist_ok=True)
        orch.run_conversion()
        orch.run_uvrs_monedas()
        if orch.enable_mitra:
            orch.run_mitra()
        if orch.enable_porfin:
            orch.run_porfin()

if __name__ == "__main__":
    main()
