"""
Ejecuta el AgenteDevOps sobre un JSON de sensores y produce:

* comentario.md  -> comentario que se publica en el PR
* decision.json  -> decisión, etiqueta y tabla de utilidades
* código de salida 1 si la decisión es "Bloquear despliegue" o "Solicitar correcciones"
  (así el check del PR queda en rojo y GitHub impide el merge).

Uso:
    python -m scripts.revisar_pr ejemplos/pr_secreto_expuesto.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agente_devops import BLOQUEAR, CORREGIR, AgenteDevOps, SensoresPR



def construir_comentario(sensores: SensoresPR, registro: dict, p_defecto: float) -> str:
    efecto = registro["efecto"]
    filas = "\n".join(
        f"| {'**' + accion + '** ← elegida' if accion == registro['accion'] else accion} | {u:.2f} |"
        for accion, u in sorted(registro["tabla_utilidades"].items(), key=lambda x: -x[1])
    )
    sugerencias = "\n".join(f"- {s}" for s in efecto["sugerencias"]) or "- Sin observaciones."
    return f"""## Agente DevOps: revisión automática

**Decisión:** {registro['accion']}
{efecto['mensaje']}

**Diagnóstico:** `{registro['diagnostico']}` · **P(defecto):** {p_defecto:.1%}

| Sensor | Lectura |
|---|---|
| Líneas modificadas | {sensores.lineas_modificadas} ({len(sensores.archivos)} archivos) |
| Pruebas | {sensores.tests_totales - sensores.tests_fallidos}/{sensores.tests_totales} pasan |
| Cobertura | {sensores.cobertura:.1%} |
| Análisis estático | {sensores.alertas_criticas} críticas · {sensores.alertas_altas} altas · {sensores.alertas_medias} medias |
| Módulo crítico | {'Sí' if sensores.toca_modulo_critico else 'No'} |

<details><summary>Función de utilidad U(s, a)</summary>

| Acción | U |
|---|---|
{filas}

</details>

### Sugerencias
{sugerencias}

<sub>Agente basado en utilidad · Hurtado Systems</sub>
"""


def main() -> int:
    p = argparse.ArgumentParser(description="Revisión de PR con el AgenteDevOps")
    p.add_argument("sensores", help="JSON de sensores")
    p.add_argument("--comentario", default="comentario.md")
    p.add_argument("--decision", default="decision.json")
    args = p.parse_args()

    try:
        sensores = SensoresPR.desde_json(args.sensores)
    except (OSError, ValueError, TypeError) as exc:
        print(f"Error leyendo sensores: {exc}", file=sys.stderr)
        return 2

    agente = AgenteDevOps()
    percepcion = sensores.a_percepcion()
    registro = agente.procesar_evento(percepcion)
    p_def = agente.probabilidad_defecto(percepcion.datos_sensores)

    comentario = construir_comentario(sensores, registro, p_def)
    Path(args.comentario).write_text(comentario, encoding="utf-8")
    Path(args.decision).write_text(json.dumps({
        "accion": registro["accion"],
        "diagnostico": registro["diagnostico"],
        "etiqueta": registro["efecto"]["etiqueta"],
        "p_defecto": p_def,
        "tabla_utilidades": registro["tabla_utilidades"],
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(comentario)
    return 1 if registro["accion"] in (BLOQUEAR, CORREGIR) else 0


if __name__ == "__main__":
    sys.exit(main())
