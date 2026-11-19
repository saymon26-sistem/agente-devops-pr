"""
AgenteDevOps: agente basado en utilidad que revisa Pull Requests.

Ciclo: Sensores -> Modelo del mundo (P_defecto) -> Proyección de las 4 acciones
-> U(s, a) -> argmax -> Actuador.

La decisión NO sale de reglas if/else: las cuatro acciones se evalúan siempre
y gana la de mayor utilidad. El diagnóstico solo etiqueta el PR para el
reporte y alimenta las estimaciones.
"""

from __future__ import annotations

from typing import Any, Dict, List

from . import config
from .base import AgenteBasadoEnUtilidad, EstadoProyectado, Percepcion

MERGE = "Aprobar y fusionar (merge)"
CORREGIR = "Solicitar correcciones"
ARQUITECTO = "Asignar arquitecto senior"
BLOQUEAR = "Bloquear despliegue"
ACCIONES = (MERGE, CORREGIR, ARQUITECTO, BLOQUEAR)


def _acotar(valor: float, minimo: float = 0.0, maximo: float = 1.0) -> float:
    return max(minimo, min(maximo, valor))


class AgenteDevOps(AgenteBasadoEnUtilidad):
    """Agente de revisión de código y gestión de Pull Requests."""

    def __init__(self, nombre_agente: str = "AgenteDevOps-v1",
                 pesos_utilidad: Dict[str, float] | None = None):
        super().__init__(nombre_agente, pesos_utilidad or dict(config.PESOS_UTILIDAD))

    # ------------------------------------------------------------------
    # Modelo del mundo
    # ------------------------------------------------------------------
    @staticmethod
    def factores_riesgo(d: Dict[str, Any]) -> Dict[str, float]:
        """Factores normalizados r_i en [0, 1] a partir de los sensores."""
        r_tests = 1.0 - d["tasa_tests"]
        r_cob = _acotar((config.UMBRAL_COBERTURA + 0.10 - d["cobertura"])
                        / (config.UMBRAL_COBERTURA + 0.10))
        r_tam = _acotar(d["lineas_modificadas"] / config.TAMANO_PR_REFERENCIA)
        r_crit = 1.0 if d["toca_modulo_critico"] else 0.0
        r_seg = _acotar(1.0 * d["alertas_criticas"] + 0.5 * d["alertas_altas"]
                        + 0.15 * d["alertas_medias"])
        if d.get("solo_documentacion"):
            r_tam = r_crit = 0.0
        return {"tests": r_tests, "cobertura": r_cob, "tamano": r_tam,
                "critico": r_crit, "seguridad": r_seg}

    def probabilidad_defecto(self, d: Dict[str, Any]) -> float:
        """P_defecto(s) = min(1, r0 + sum(alpha_i * r_i))."""
        r = self.factores_riesgo(d)
        p = config.RIESGO_BASE + sum(config.COEF_RIESGO[k] * v for k, v in r.items())
        return round(_acotar(p), 4)

    @staticmethod
    def deficit_calidad(d: Dict[str, Any]) -> float:
        """D_q(s): qué tanto incumple el PR los estándares si se fusiona tal cual."""
        deficit_cob = max(0.0, config.UMBRAL_COBERTURA - d["cobertura"]) / config.UMBRAL_COBERTURA
        return round(_acotar(deficit_cob + 0.5 * d["alertas_altas"]
                             + 0.1 * d["alertas_medias"]), 4)

    def actualizar_estado_interno(self, percepcion: Percepcion) -> str:
        d = percepcion.datos_sensores
        if d["alertas_criticas"] > 0:
            return "PR_BLOQUEANTE"
        if d["tasa_tests"] < 1.0:
            return "PR_FALLIDO"
        if d.get("solo_documentacion"):
            return "PR_TRIVIAL"
        p = self.probabilidad_defecto(d)
        if p >= 0.25 or self.deficit_calidad(d) > 0:
            return "PR_RIESGOSO"
        return "PR_ESTANDAR"

    # ------------------------------------------------------------------
    # Modelo de transición: efecto proyectado de cada acción
    # ------------------------------------------------------------------
    def generar_estados_proyectados(
        self, diagnostico: str, percepcion: Percepcion
    ) -> List[EstadoProyectado]:
        d = percepcion.datos_sensores
        p = self.probabilidad_defecto(d)
        dq = self.deficit_calidad(d)
        impacto_prod = 1.0 if percepcion.contexto_critico and d["toca_modulo_critico"] else 0.6
        # Un secreto expuesto o una SQLi ya son un incidente: cualquier acción
        # que no detenga el pipeline deja abierta la ventana de explotación.
        exposicion = 0.5 if d["alertas_criticas"] > 0 else 0.0
        # Hay hallazgos que el autor puede corregir solo con el feedback del bot
        hallazgos_concretos = (d["tasa_tests"] < 1.0 or dq > 0 or d["alertas_criticas"] > 0)
        meta = {"p_defecto": p, "deficit_calidad": dq, "diagnostico": diagnostico}

        return [
            EstadoProyectado(
                nombre_accion=MERGE,
                probabilidad_exito=round(1.0 - p, 4),
                beneficio_operativo=100.0,
                riesgo_impacto=round(_acotar(p * impacto_prod + exposicion), 4),
                costo_intervencion=0.0,
                deficit_calidad=dq,
                # Política dura: nunca fusionar con pruebas rotas o vulnerabilidad crítica
                viola_politica=d["tasa_tests"] < 1.0 or d["alertas_criticas"] > 0,
                metadatos=meta,
            ),
            EstadoProyectado(
                nombre_accion=CORREGIR,
                probabilidad_exito=0.90 if hallazgos_concretos else 0.50,
                beneficio_operativo=40.0,
                riesgo_impacto=round(_acotar(p * 0.10 + exposicion), 4),
                costo_intervencion=0.30,
                metadatos=meta,
            ),
            EstadoProyectado(
                nombre_accion=ARQUITECTO,
                probabilidad_exito=0.97,
                beneficio_operativo=25.0,
                riesgo_impacto=round(_acotar(p * 0.05 + exposicion), 4),
                costo_intervencion=0.80,
                metadatos=meta,
            ),
            EstadoProyectado(
                nombre_accion=BLOQUEAR,
                probabilidad_exito=0.99 if d["alertas_criticas"] > 0 else 0.30,
                beneficio_operativo=0.0,
                riesgo_impacto=0.0,
                costo_intervencion=0.60,
                metadatos=meta,
            ),
        ]

    # ------------------------------------------------------------------
    # Actuadores
    # ------------------------------------------------------------------
    def ejecutar_actuador(
        self, percepcion: Percepcion, accion_elegida: EstadoProyectado
    ) -> Dict[str, Any]:
        """Traduce la decisión en efectos concretos sobre el repositorio."""
        accion = accion_elegida.nombre_accion
        efectos = {
            MERGE: {"etiqueta": "agente:merge-automatico", "estado_check": "success",
                    "mensaje": "PR aprobado: cumple estándares y su riesgo es bajo."},
            CORREGIR: {"etiqueta": "agente:requiere-cambios", "estado_check": "failure",
                       "mensaje": "Se solicitan correcciones antes de fusionar."},
            ARQUITECTO: {"etiqueta": "agente:revision-senior", "estado_check": "neutral",
                         "mensaje": "PR de alto impacto: se asigna a un arquitecto senior."},
            BLOQUEAR: {"etiqueta": "agente:bloqueado", "estado_check": "failure",
                       "mensaje": "Despliegue bloqueado por hallazgo crítico de seguridad."},
        }
        efecto = dict(efectos[accion])
        efecto["sugerencias"] = self.sugerencias(percepcion.datos_sensores)
        return efecto

    @staticmethod
    def sugerencias(d: Dict[str, Any]) -> List[str]:
        """Comentarios técnicos que el agente publica en el PR."""
        s: List[str] = []
        if d["alertas_criticas"]:
            s.append(f"{d['alertas_criticas']} hallazgo(s) crítico(s) (secreto expuesto / SQLi): "
                     "rotar credenciales y usar consultas parametrizadas.")
        if d["tasa_tests"] < 1.0:
            s.append(f"{d['tests_fallidos']} de {d['tests_totales']} pruebas fallan.")
        if d["cobertura"] < config.UMBRAL_COBERTURA:
            s.append(f"Cobertura {d['cobertura']:.0%} por debajo del mínimo "
                     f"{config.UMBRAL_COBERTURA:.0%}: agregar pruebas.")
        if d["alertas_altas"] or d["alertas_medias"]:
            s.append(f"Análisis estático: {d['alertas_altas']} alta(s), "
                     f"{d['alertas_medias']} media(s).")
        if d["lineas_modificadas"] > 400:
            s.append(f"PR grande ({d['lineas_modificadas']} líneas): considerar dividirlo.")
        return s
