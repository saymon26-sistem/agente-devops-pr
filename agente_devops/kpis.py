"""Cálculo de KPIs alineados con la medida de rendimiento (Performance) del PEAS."""

from __future__ import annotations

from statistics import mean
from typing import Dict, List

from . import config
from .agente import ARQUITECTO, BLOQUEAR, CORREGIR, MERGE


def calcular_kpis(resultados: List[Dict]) -> Dict[str, float]:
    """
    Cada resultado debe tener: accion, accion_esperada, defecto_real.

    * precision_decision:  decisiones que coinciden con el oráculo experto.
    * tasa_merge_auto:     PRs fusionados sin intervención humana.
    * tasa_escalamiento:   PRs enviados a un arquitecto senior.
    * defectos_escapados:  PRs con defecto real que se fusionaron (debe ser 0).
    * recall_defectos:     defectos reales detenidos antes de producción.
    * ciclo_prom_min:      tiempo de ciclo promedio simulado (minutos).
    * reduccion_ciclo:     contra una línea base en que todo PR lo revisa un senior.
    """
    n = len(resultados)
    if n == 0:
        raise ValueError("No hay resultados para calcular KPIs")

    con_defecto = [r for r in resultados if r["defecto_real"]]
    escapados = [r for r in con_defecto if r["accion"] == MERGE]
    ciclo = mean(config.TIEMPO_CICLO_MIN[r["accion"]] for r in resultados)
    base = config.TIEMPO_CICLO_MIN[ARQUITECTO]

    return {
        "casos": n,
        "precision_decision": round(sum(r["accion"] == r["accion_esperada"] for r in resultados) / n, 4),
        "tasa_merge_auto": round(sum(r["accion"] == MERGE for r in resultados) / n, 4),
        "tasa_correcciones": round(sum(r["accion"] == CORREGIR for r in resultados) / n, 4),
        "tasa_escalamiento": round(sum(r["accion"] == ARQUITECTO for r in resultados) / n, 4),
        "tasa_bloqueo": round(sum(r["accion"] == BLOQUEAR for r in resultados) / n, 4),
        "defectos_escapados": len(escapados),
        "recall_defectos": round(1 - len(escapados) / len(con_defecto), 4) if con_defecto else 1.0,
        "ciclo_prom_min": round(ciclo, 1),
        "reduccion_ciclo": round(1 - ciclo / base, 4),
    }
