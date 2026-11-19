"""
Batería de pruebas del AgenteDevOps: 7 escenarios (rutinarios, ambiguos y críticos).

Uso:
    python simulacion.py                 # tabla de decisiones + KPIs
    python simulacion.py --sensibilidad  # además, análisis de sensibilidad de w_r
    python simulacion.py --json salida.json
"""

from __future__ import annotations

import argparse
import json
import logging
from typing import Dict, List

from agente_devops import ARQUITECTO, BLOQUEAR, CORREGIR, MERGE, AgenteDevOps, SensoresPR
from agente_devops import config
from agente_devops.kpis import calcular_kpis

# Cada caso: (tipo, sensores, decisión esperada por un revisor experto, ¿defecto real?)
CASOS: List[Dict] = [
    {"tipo": "Rutinario", "esperada": MERGE, "defecto_real": False,
     "sensores": SensoresPR("PR-101", 3, ["README.md"], 42, 0, 0.85,
                            titulo="Corrige typo en README")},
    {"tipo": "Rutinario", "esperada": MERGE, "defecto_real": False,
     "sensores": SensoresPR("PR-102", 150, ["src/reportes/exportar.py", "tests/test_exportar.py"],
                            58, 0, 0.85, titulo="Exportar reportes a CSV")},
    {"tipo": "Crítico", "esperada": CORREGIR, "defecto_real": True,
     "sensores": SensoresPR("PR-103", 200, ["src/carrito/descuentos.py"], 60, 12, 0.80,
                            titulo="Nuevo cálculo de descuentos")},
    {"tipo": "Crítico", "esperada": BLOQUEAR, "defecto_real": True,
     "sensores": SensoresPR("PR-104", 80, ["src/db/consultas.py", "config/settings.py"],
                            40, 0, 0.82, alertas_criticas=2,
                            titulo="Conexión a BD de reportes")},
    {"tipo": "Ambiguo", "esperada": ARQUITECTO, "defecto_real": False,
     "sensores": SensoresPR("PR-105", 1200, ["src/auth/oauth.py", "src/auth/tokens.py",
                                              "src/auth/middleware.py"],
                            130, 0, 0.82, titulo="Migración de sesiones a OAuth2")},
    {"tipo": "Ambiguo", "esperada": CORREGIR, "defecto_real": True,
     "sensores": SensoresPR("PR-106", 300, ["src/notificaciones/email.py"], 35, 0, 0.55,
                            titulo="Plantillas de correo")},
    {"tipo": "Ambiguo", "esperada": CORREGIR, "defecto_real": True,
     "sensores": SensoresPR("PR-107", 60, ["src/utils/archivos.py"], 50, 0, 0.78,
                            alertas_altas=1, titulo="Carga de archivos con subprocess")},
]


def ejecutar(agente: AgenteDevOps) -> List[Dict]:
    resultados = []
    for caso in CASOS:
        percepcion = caso["sensores"].a_percepcion()
        registro = agente.procesar_evento(percepcion)
        resultados.append({
            "id": percepcion.id_evento,
            "titulo": caso["sensores"].titulo,
            "tipo": caso["tipo"],
            "diagnostico": registro["diagnostico"],
            "p_defecto": agente.probabilidad_defecto(percepcion.datos_sensores),
            "tabla_utilidades": registro["tabla_utilidades"],
            "accion": registro["accion"],
            "accion_esperada": caso["esperada"],
            "defecto_real": caso["defecto_real"],
            "sugerencias": registro["efecto"]["sugerencias"],
        })
    return resultados


def imprimir(resultados: List[Dict], kpis: Dict) -> None:
    abrev = {MERGE: "MERGE", CORREGIR: "CORREG", ARQUITECTO: "ARQUIT", BLOQUEAR: "BLOQ"}
    print("\n" + "=" * 100)
    print(f"{'PR':<7} {'Tipo':<10} {'Diagnóstico':<14} {'P_def':>6}  "
          f"{'U(MERGE)':>9} {'U(CORREG)':>9} {'U(ARQUIT)':>9} {'U(BLOQ)':>9}  Decisión  OK")
    print("-" * 100)
    for r in resultados:
        t = r["tabla_utilidades"]
        ok = "✔" if r["accion"] == r["accion_esperada"] else "✘"
        print(f"{r['id']:<7} {r['tipo']:<10} {r['diagnostico']:<14} {r['p_defecto']:>6.3f}  "
              f"{t[MERGE]:>9.2f} {t[CORREGIR]:>9.2f} {t[ARQUITECTO]:>9.2f} {t[BLOQUEAR]:>9.2f}  "
              f"{abrev[r['accion']]:<8}  {ok}")
    print("=" * 100)
    print("KPIs:")
    for k, v in kpis.items():
        print(f"  {k:<20} {v}")


def sensibilidad() -> Dict[float, Dict]:
    """¿Cómo cambian las decisiones si el equipo valora menos el riesgo?"""
    salida = {}
    print("\nAnálisis de sensibilidad del peso de riesgo w_r")
    for w_r in (50, 100, 200, 400, 800):
        pesos = dict(config.PESOS_UTILIDAD, riesgo=float(w_r))
        res = ejecutar(AgenteDevOps("sens", pesos))
        k = calcular_kpis(res)
        salida[w_r] = k
        print(f"  w_r={w_r:<4} precisión={k['precision_decision']:.2f} "
              f"merge_auto={k['tasa_merge_auto']:.2f} escapados={k['defectos_escapados']} "
              f"ciclo={k['ciclo_prom_min']} min")
    return salida


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sensibilidad", action="store_true")
    parser.add_argument("--json", help="Guardar resultados y KPIs en un archivo JSON")
    parser.add_argument("-v", "--verbose", action="store_true", help="Traza de cada decisión")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(message)s")

    agente = AgenteDevOps()
    resultados = ejecutar(agente)
    kpis = calcular_kpis(resultados)
    imprimir(resultados, kpis)
    sens = sensibilidad() if args.sensibilidad else None

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({"resultados": resultados, "kpis": kpis, "sensibilidad": sens},
                      f, ensure_ascii=False, indent=2)
        print(f"\nResultados guardados en {args.json}")


if __name__ == "__main__":
    main()
