"""
Plantilla base del agente basado en utilidad (Russell & Norvig).

Se conserva la estructura entregada en el taller (Percepcion, EstadoProyectado
y AgenteBasadoEnUtilidad). La única extensión es que la función de utilidad
incluye dos términos adicionales que exige el dominio DevOps:

* ``deficit_calidad``  -> incumplimiento de estándares de calidad (soft).
* ``viola_politica``   -> violación de una política dura de CI/CD (hard).
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


# =====================================================================
# 1. ESTRUCTURAS DE DATOS (SENSORES Y ESTADOS PROYECTADOS)
# =====================================================================
@dataclass
class Percepcion:
    """Datos crudos capturados por los SENSORES del agente en un instante t."""

    id_evento: str
    datos_sensores: Dict[str, Any]
    contexto_critico: bool = False


@dataclass
class EstadoProyectado:
    """Resultado futuro estimado si el agente ejecuta una acción concreta."""

    nombre_accion: str
    probabilidad_exito: float      # [0, 1]
    beneficio_operativo: float     # [0, 100]  velocidad de entrega
    riesgo_impacto: float          # [0, 1]    P(defecto) x impacto
    costo_intervencion: float      # [0, 1]    costo de tiempo humano / pipeline
    deficit_calidad: float = 0.0   # [0, 1]    incumplimiento de estándares
    viola_politica: bool = False   # restricción dura
    metadatos: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for nombre in ("probabilidad_exito", "riesgo_impacto",
                       "costo_intervencion", "deficit_calidad"):
            valor = getattr(self, nombre)
            if not 0.0 <= valor <= 1.0:
                raise ValueError(f"{nombre}={valor} fuera del rango [0, 1]")
        if not 0.0 <= self.beneficio_operativo <= 100.0:
            raise ValueError("beneficio_operativo fuera del rango [0, 100]")


# =====================================================================
# 2. INTERFAZ ABSTRACTA DEL AGENTE BASADO EN UTILIDAD
# =====================================================================
class AgenteBasadoEnUtilidad(ABC):
    """Ciclo de vida de un agente basado en utilidad."""

    PESOS_REQUERIDOS = ("exito", "beneficio", "riesgo", "costo",
                        "calidad", "politica")

    def __init__(self, nombre_agente: str, pesos_utilidad: Dict[str, float]):
        faltantes = [p for p in self.PESOS_REQUERIDOS if p not in pesos_utilidad]
        if faltantes:
            raise ValueError(f"Faltan pesos de utilidad: {faltantes}")
        self.nombre = nombre_agente
        self.pesos = pesos_utilidad
        self.historial_decisiones: List[Dict[str, Any]] = []

    @abstractmethod
    def actualizar_estado_interno(self, percepcion: Percepcion) -> str:
        """PASO 1 (Modelo del mundo): diagnostica el estado real del entorno."""

    @abstractmethod
    def generar_estados_proyectados(
        self, diagnostico: str, percepcion: Percepcion
    ) -> List[EstadoProyectado]:
        """PASO 2 (Modelo de transición): proyecta el efecto de cada acción."""

    def calcular_utilidad(self, estado: EstadoProyectado) -> float:
        """
        PASO 3 (Función de utilidad):

        U = w_e*P_exito + w_b*Beneficio - w_r*Riesgo - w_c*Costo
            - w_q*DeficitCalidad - w_p*[viola_politica]
        """
        p = self.pesos
        utilidad = (
            p["exito"] * estado.probabilidad_exito
            + p["beneficio"] * estado.beneficio_operativo
            - p["riesgo"] * estado.riesgo_impacto
            - p["costo"] * estado.costo_intervencion
            - p["calidad"] * estado.deficit_calidad
            - (p["politica"] if estado.viola_politica else 0.0)
        )
        return round(utilidad, 2)

    def seleccionar_mejor_accion(
        self, percepcion: Percepcion
    ) -> Tuple[EstadoProyectado, Dict[str, float], str]:
        """PASO 4 (Toma de decisiones): elige la acción que maximiza U(s)."""
        diagnostico = self.actualizar_estado_interno(percepcion)
        estados = self.generar_estados_proyectados(diagnostico, percepcion)
        if not estados:
            raise ValueError(f"Sin acciones para el diagnóstico {diagnostico}")

        tabla: Dict[str, float] = {e.nombre_accion: self.calcular_utilidad(e)
                                   for e in estados}
        mejor = max(estados, key=lambda e: tabla[e.nombre_accion])
        return mejor, tabla, diagnostico

    @abstractmethod
    def ejecutar_actuador(
        self, percepcion: Percepcion, accion_elegida: EstadoProyectado
    ) -> Dict[str, Any]:
        """PASO 5 (Actuadores): aplica la acción ganadora sobre el entorno."""

    def procesar_evento(self, percepcion: Percepcion) -> Dict[str, Any]:
        """Orquesta el ciclo Percepción -> Decisión -> Acción y lo registra."""
        mejor, tabla, diagnostico = self.seleccionar_mejor_accion(percepcion)
        logger.info("[%s] %s | diagnóstico=%s | U=%s | decisión=%s",
                    self.nombre, percepcion.id_evento, diagnostico, tabla,
                    mejor.nombre_accion)
        efecto = self.ejecutar_actuador(percepcion, mejor)
        registro = {
            "evento": percepcion.id_evento,
            "diagnostico": diagnostico,
            "accion": mejor.nombre_accion,
            "utilidad": tabla[mejor.nombre_accion],
            "tabla_utilidades": tabla,
            "efecto": efecto,
        }
        self.historial_decisiones.append(registro)
        return registro
