"""Pruebas unitarias del AgenteDevOps."""

import json

import pytest

from agente_devops import (ARQUITECTO, BLOQUEAR, CORREGIR, MERGE, AgenteDevOps,
                           EstadoProyectado, SensoresPR)
from agente_devops import config
from agente_devops.kpis import calcular_kpis
from agente_devops.sensores import leer_bandit, leer_cobertura, leer_junit, leer_numstat
from scripts import revisar_pr
from simulacion import CASOS, ejecutar


@pytest.fixture
def agente():
    return AgenteDevOps()


def decidir(agente, sensores):
    return agente.procesar_evento(sensores.a_percepcion())


# --- Casos de la batería -----------------------------------------------------
@pytest.mark.parametrize("caso", CASOS, ids=[c["sensores"].id_pr for c in CASOS])
def test_bateria_coincide_con_oraculo(agente, caso):
    assert decidir(agente, caso["sensores"])["accion"] == caso["esperada"]


def test_kpis_bateria_sin_defectos_escapados(agente):
    kpis = calcular_kpis(ejecutar(agente))
    assert kpis["precision_decision"] == 1.0
    assert kpis["defectos_escapados"] == 0
    assert kpis["reduccion_ciclo"] > 0.5


# --- Propiedades de seguridad ------------------------------------------------
def test_nunca_fusiona_con_vulnerabilidad_critica(agente):
    for lineas in (1, 50, 500):
        s = SensoresPR("X", lineas, ["src/app.py"], 10, 0, 0.95, alertas_criticas=1)
        assert decidir(agente, s)["accion"] != MERGE


def test_nunca_fusiona_con_pruebas_rotas(agente):
    s = SensoresPR("X", 5, ["src/app.py"], 100, 1, 0.99)
    assert decidir(agente, s)["accion"] != MERGE


def test_vulnerabilidad_critica_bloquea(agente):
    s = SensoresPR("X", 20, ["src/db.py"], 10, 0, 0.9, alertas_criticas=1)
    assert decidir(agente, s)["accion"] == BLOQUEAR


def test_riesgo_monotono_en_tamano(agente):
    base = dict(id_pr="X", archivos=["src/a.py"], tests_totales=10, cobertura=0.85)
    p = [agente.probabilidad_defecto(SensoresPR(lineas_modificadas=n, **base)
                                     .a_percepcion().datos_sensores) for n in (10, 300, 900)]
    assert p[0] < p[1] < p[2]


def test_documentacion_es_trivial(agente):
    s = SensoresPR("X", 400, ["docs/guia.md", "README.md"], 10, 0, 0.85)
    r = decidir(agente, s)
    assert r["diagnostico"] == "PR_TRIVIAL" and r["accion"] == MERGE


def test_evalua_las_cuatro_acciones(agente):
    r = decidir(agente, CASOS[0]["sensores"])
    assert set(r["tabla_utilidades"]) == {MERGE, CORREGIR, ARQUITECTO, BLOQUEAR}


def test_historial_y_sugerencias(agente):
    r = decidir(agente, CASOS[5]["sensores"])  # baja cobertura
    assert agente.historial_decisiones[-1]["evento"] == "PR-106"
    assert any("Cobertura" in s for s in r["efecto"]["sugerencias"])


# --- Función de utilidad -----------------------------------------------------
def test_utilidad_formula(agente):
    e = EstadoProyectado("A", 0.5, 50.0, 0.1, 0.2, deficit_calidad=0.1)
    w = config.PESOS_UTILIDAD
    esperado = w["exito"] * .5 + w["beneficio"] * 50 - w["riesgo"] * .1 - w["costo"] * .2 - w["calidad"] * .1
    assert agente.calcular_utilidad(e) == pytest.approx(esperado)


def test_penalizacion_politica(agente):
    ok = EstadoProyectado("A", 1, 100, 0, 0)
    malo = EstadoProyectado("B", 1, 100, 0, 0, viola_politica=True)
    assert agente.calcular_utilidad(ok) - agente.calcular_utilidad(malo) == config.PESOS_UTILIDAD["politica"]


# --- Validaciones / excepciones ---------------------------------------------
def test_pesos_incompletos():
    with pytest.raises(ValueError):
        AgenteDevOps(pesos_utilidad={"exito": 1})


@pytest.mark.parametrize("kwargs", [
    {"lineas_modificadas": -1},
    {"cobertura": 1.5},
    {"tests_totales": 1, "tests_fallidos": 2},
])
def test_sensores_invalidos(kwargs):
    base = {"id_pr": "X", "lineas_modificadas": 1}
    base.update(kwargs)
    with pytest.raises(ValueError):
        SensoresPR(**base)


def test_estado_fuera_de_rango():
    with pytest.raises(ValueError):
        EstadoProyectado("A", 1.2, 10, 0, 0)


def test_kpis_vacio():
    with pytest.raises(ValueError):
        calcular_kpis([])


# --- Parsers de sensores del pipeline ---------------------------------------
def test_parsers(tmp_path):
    lineas, archivos = leer_numstat("10\t2\tsrc/a.py\n-\t-\timg.png\n3\t0\tREADME.md\n")
    assert lineas == 15 and archivos == ["src/a.py", "img.png", "README.md"]

    junit = tmp_path / "r.xml"
    junit.write_text('<testsuites><testsuite tests="10" failures="1" errors="1"/></testsuites>')
    assert leer_junit(junit) == (10, 2)

    cov = tmp_path / "c.json"
    cov.write_text(json.dumps({"totals": {"percent_covered": 87.5}}))
    assert leer_cobertura(cov) == 0.875

    bandit = tmp_path / "b.json"
    bandit.write_text(json.dumps({"results": [
        {"test_id": "B105", "issue_severity": "LOW"},
        {"test_id": "B602", "issue_severity": "HIGH"},
        {"test_id": "B311", "issue_severity": "MEDIUM"},
    ]}))
    assert leer_bandit(bandit) == {"alertas_criticas": 1, "alertas_altas": 1, "alertas_medias": 1}


def test_cli_revisar_pr(tmp_path, monkeypatch):
    sensores = tmp_path / "s.json"
    sensores.write_text(json.dumps({"id_pr": "PR-1", "lineas_modificadas": 3,
                                    "archivos": ["README.md"], "tests_totales": 5,
                                    "cobertura": 0.9}))
    comentario, decision = tmp_path / "c.md", tmp_path / "d.json"
    monkeypatch.setattr("sys.argv", ["revisar_pr", str(sensores), "--comentario", str(comentario),
                                     "--decision", str(decision)])
    assert revisar_pr.main() == 0
    assert json.loads(decision.read_text())["accion"] == MERGE
    assert "Agente DevOps" in comentario.read_text()


def test_recolectar_sensores(tmp_path, monkeypatch):
    from scripts import recolectar_sensores

    diff = tmp_path / "diff.txt"
    diff.write_text("120\t30\tsrc/auth/login.py\n")
    salida = tmp_path / "sensores.json"
    monkeypatch.setattr("sys.argv", ["recolectar", "--id", "PR-9", "--diff", str(diff),
                                     "--salida", str(salida), "--titulo", "Login"])
    recolectar_sensores.main()
    s = SensoresPR.desde_json(salida)
    assert s.lineas_modificadas == 150 and s.toca_modulo_critico
