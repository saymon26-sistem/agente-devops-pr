"""
Recolecta los SENSORES de un Pull Request dentro de GitHub Actions y los
guarda en un JSON que luego consume ``revisar_pr.py``.

Ejemplo:
    git diff --numstat origin/main...HEAD > diff.txt
    python -m scripts.recolectar_sensores --id PR-12 --diff diff.txt \
        --junit reporte.xml --cobertura coverage.json --bandit bandit.json \
        --salida sensores.json
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from agente_devops.sensores import SensoresPR, leer_bandit, leer_cobertura, leer_junit, leer_numstat


def recolectar(args: argparse.Namespace) -> SensoresPR:
    lineas, archivos = leer_numstat(Path(args.diff).read_text(encoding="utf-8")) if args.diff else (0, [])
    totales, fallidos = leer_junit(args.junit) if args.junit and Path(args.junit).exists() else (0, 0)
    cobertura = leer_cobertura(args.cobertura) if args.cobertura and Path(args.cobertura).exists() else 0.0
    alertas = leer_bandit(args.bandit) if args.bandit and Path(args.bandit).exists() else {}
    return SensoresPR(
        id_pr=args.id, lineas_modificadas=lineas, archivos=archivos,
        tests_totales=totales, tests_fallidos=fallidos, cobertura=cobertura,
        rama_destino=args.rama, titulo=args.titulo, **alertas,
    )


def main() -> None:
    p = argparse.ArgumentParser(description="Recolector de sensores del PR")
    p.add_argument("--id", required=True)
    p.add_argument("--diff", help="Salida de git diff --numstat")
    p.add_argument("--junit", help="Reporte JUnit XML de pytest")
    p.add_argument("--cobertura", help="coverage.json de coverage.py")
    p.add_argument("--bandit", help="Reporte JSON de Bandit")
    p.add_argument("--rama", default="main")
    p.add_argument("--titulo", default="")
    p.add_argument("--salida", default="sensores.json")
    args = p.parse_args()

    sensores = recolectar(args)
    Path(args.salida).write_text(json.dumps(asdict(sensores), ensure_ascii=False, indent=2),
                                 encoding="utf-8")
    print(f"Sensores guardados en {args.salida}")


if __name__ == "__main__":
    main()
