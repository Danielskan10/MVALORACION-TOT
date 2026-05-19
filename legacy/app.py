#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lanzador unico de MVALORACION.

Ejecuta:
    py -3 app.py

Abre el dashboard y deja que el usuario seleccione fechas desde el navegador.
"""
from __future__ import annotations

import sys

import Insumos


def main() -> None:
    args = sys.argv[1:]
    if "--lazy" not in args:
        args.append("--lazy")
    sys.argv = ["Insumos.py", *args]
    Insumos.main()


if __name__ == "__main__":
    main()
