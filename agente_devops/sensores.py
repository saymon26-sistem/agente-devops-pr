"""
Capa de SENSORES: convierte lo que produce el pipeline de CI/CD
(diff, reporte de pruebas, cobertura y análisis estático) en una Percepcion.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from . import config
from .base import Percepcion


@dataclass
class SensoresPR:
    """Lecturas normalizadas de un Pull Request."""

    id_pr: str
    lineas_modificadas: int
    archivos: List[str] = field(default_factory=list)
    tests_totales: int = 0
    tests_fallidos: int = 0
    cobertura: float = 1.0                  # [0, 1]
    alertas_criticas: int = 0               # secretos, SQLi...
    alertas_altas: int = 0
    alertas_medias: int = 0
    rama_destino: str = "main"
    titulo: str = ""

    def __post_init__(self) -> None:
        if self.lineas_modificadas < 0:
            raise ValueError("lineas_modificadas no puede ser negativo")
        if not 0.0 <= self.cobertura <= 1.0:
            raise ValueError("cobertura debe estar en [0, 1]")
        if self.tests_fallidos > self.tests_totales:
            raise ValueError("tests_fallidos no puede superar tests_totales")

    # --- atributos derivados -------------------------------------------------
    @property
    def tasa_tests(self) -> float:
        """Proporción de pruebas que pasan (1.0 si no hay pruebas que fallen)."""
        if self.tests_totales == 0:
            return 1.0
        return 1.0 - self.tests_fallidos / self.tests_totales

    @property
    def toca_modulo_critico(self) -> bool:
        rutas = [a.lower() for a in self.archivos]
        return any(p in r for r in rutas for p in config.PATRONES_CRITICOS)

    @property
    def solo_documentacion(self) -> bool:
        if not self.archivos:
            return False
        return all(any(p in a.lower() for p in config.PATRONES_DOCS)
                   for a in self.archivos)

    def a_percepcion(self) -> Percepcion:
        datos = asdict(self)
        datos.update(
            tasa_tests=self.tasa_tests,
            toca_modulo_critico=self.toca_modulo_critico,
            solo_documentacion=self.solo_documentacion,
        )
        critico = self.toca_modulo_critico or self.rama_destino in ("main", "production")
        return Percepcion(self.id_pr, datos, contexto_critico=critico)

    @classmethod
    def desde_json(cls, ruta: str | Path) -> "SensoresPR":
        datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
        return cls(**datos)


# ---------------------------------------------------------------------------
# Parsers de los artefactos que genera el pipeline
# ---------------------------------------------------------------------------
def leer_numstat(texto: str) -> tuple[int, List[str]]:
    """Interpreta la salida de ``git diff --numstat``."""
    total, archivos = 0, []
    for linea in texto.strip().splitlines():
        partes = linea.split("\t")
        if len(partes) != 3:
            continue
        agregadas, eliminadas, ruta = partes
        # Los binarios aparecen como "-\t-\truta"
        total += (int(agregadas) if agregadas.isdigit() else 0)
        total += (int(eliminadas) if eliminadas.isdigit() else 0)
        archivos.append(ruta)
    return total, archivos


def leer_junit(ruta: str | Path) -> tuple[int, int]:
    """Devuelve (totales, fallidos) a partir de un reporte JUnit XML."""
    # El XML lo genera el propio pipeline (pytest), no es entrada de terceros.
    import xml.etree.ElementTree as ET  # nosec B405

    raiz = ET.parse(ruta).getroot()  # nosec B314
    suites = [raiz] if raiz.tag == "testsuite" else raiz.findall("testsuite")
    totales = sum(int(s.get("tests", 0)) for s in suites)
    fallidos = sum(int(s.get("failures", 0)) + int(s.get("errors", 0)) for s in suites)
    return totales, fallidos


def leer_cobertura(ruta: str | Path) -> float:
    """Lee el porcentaje total de un ``coverage.json`` (coverage.py)."""
    datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    return round(float(datos["totals"]["percent_covered"]) / 100.0, 4)


def leer_bandit(ruta: str | Path) -> Dict[str, int]:
    """Clasifica los hallazgos de Bandit en críticos, altos y medios."""
    datos: Dict[str, Any] = json.loads(Path(ruta).read_text(encoding="utf-8"))
    conteo = {"alertas_criticas": 0, "alertas_altas": 0, "alertas_medias": 0}
    for hallazgo in datos.get("results", []):
        regla = hallazgo.get("test_id", "")
        severidad = hallazgo.get("issue_severity", "LOW").upper()
        if regla in config.REGLAS_CRITICAS_BANDIT:
            conteo["alertas_criticas"] += 1
        elif severidad == "HIGH":
            conteo["alertas_altas"] += 1
        elif severidad == "MEDIUM":
            conteo["alertas_medias"] += 1
    return conteo
