"""
Demo interactiva del Agente DevOps de revisión de Pull Requests.

    streamlit run app.py
"""

from __future__ import annotations

from dataclasses import asdict

import altair as alt
import pandas as pd
import streamlit as st

from agente_devops import ACCIONES, ARQUITECTO, BLOQUEAR, CORREGIR, MERGE, AgenteDevOps, SensoresPR
from agente_devops import config
from agente_devops.kpis import calcular_kpis
from scripts.revisar_pr import construir_comentario
from simulacion import CASOS, ejecutar

st.set_page_config(page_title="Agente DevOps · Revisión de PRs", page_icon="🤖", layout="wide")

COLORES = {MERGE: "#2E7D32", CORREGIR: "#EF6C00", ARQUITECTO: "#1F4E79", BLOQUEAR: "#C62828"}
CORTOS = {MERGE: "Merge", CORREGIR: "Corregir", ARQUITECTO: "Arquitecto", BLOQUEAR: "Bloquear"}
ICONOS = {MERGE: "✅", CORREGIR: "✏️", ARQUITECTO: "👀", BLOQUEAR: "⛔"}
ETIQUETAS_PESOS = {
    "exito": ("w_e · éxito", 0.0, 300.0),
    "beneficio": ("w_b · velocidad", 0.0, 5.0),
    "riesgo": ("w_r · riesgo", 0.0, 1000.0),
    "costo": ("w_c · costo humano", 0.0, 150.0),
    "calidad": ("w_q · calidad", 0.0, 800.0),
    "politica": ("w_p · política dura", 0.0, 2000.0),
}
PRESETS = {f"{c['sensores'].id_pr} · {c['tipo']} · {c['sensores'].titulo}": c for c in CASOS}
CAMPOS = ("lineas", "archivos", "totales", "fallidos", "cobertura", "criticas", "altas", "medias")


# ---------------------------------------------------------------------------
# Estado
# ---------------------------------------------------------------------------
def cargar_preset() -> None:
    s: SensoresPR = PRESETS[st.session_state.preset]["sensores"]
    st.session_state.update(
        lineas=s.lineas_modificadas, archivos="\n".join(s.archivos), totales=s.tests_totales,
        fallidos=s.tests_fallidos, cobertura=int(round(s.cobertura * 100)),
        criticas=s.alertas_criticas, altas=s.alertas_altas, medias=s.alertas_medias,
    )


def restablecer_pesos() -> None:
    for k, v in config.PESOS_UTILIDAD.items():
        st.session_state[f"w_{k}"] = v


if "lineas" not in st.session_state:
    st.session_state.preset = next(iter(PRESETS))
    cargar_preset()
    restablecer_pesos()


# ---------------------------------------------------------------------------
# Barra lateral: pesos
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("⚖️ Pesos de U(s, a)")
    st.caption("Cambia lo que el equipo valora y mira cómo cambia el agente.")
    for k, (etiqueta, minimo, maximo) in ETIQUETAS_PESOS.items():
        st.slider(etiqueta, minimo, maximo, key=f"w_{k}")
    st.button("Restablecer calibración", on_click=restablecer_pesos, width="stretch")
    st.divider()
    st.caption("Proyecto 4 · Taller de Agentes Inteligentes\n\n**Simon Hurtado** · Hurtado Systems")

pesos = {k: float(st.session_state[f"w_{k}"]) for k in config.PESOS_UTILIDAD}
agente = AgenteDevOps("AgenteDevOps-demo", pesos)


def grafica_utilidades(tabla: dict, elegida: str, piso: float = -250.0) -> alt.Chart:
    """Barras de U por acción. Los valores muy negativos se recortan pero se rotulan."""
    df = pd.DataFrame({"Acción": [CORTOS[a] for a in tabla], "U": list(tabla.values()),
                       "accion": list(tabla)})
    piso = max(piso, min(-20.0, df["U"].min() * 1.1))
    df["U_vis"] = df["U"].clip(lower=piso)
    df["Color"] = df["accion"].map(COLORES)
    df["Elegida"] = df["accion"] == elegida
    techo = max(50.0, df["U"].max() * 1.15)
    base = alt.Chart(df).encode(y=alt.Y("Acción:N", sort=[CORTOS[a] for a in ACCIONES], title=None))
    barras = base.mark_bar(cornerRadius=4).encode(
        x=alt.X("U_vis:Q", title="Utilidad U(s, a)", scale=alt.Scale(domain=[piso, techo])),
        color=alt.Color("Color:N", scale=None),
        opacity=alt.condition("datum.Elegida", alt.value(1.0), alt.value(0.35)),
        tooltip=[alt.Tooltip("Acción:N"), alt.Tooltip("U:Q", format=".2f")],
    )
    textos = base.mark_text(align="left", dx=6, fontWeight="bold").encode(
        x=alt.X("U_vis:Q"), text=alt.Text("U:Q", format=".2f"))
    cero = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(color="gray").encode(x="x:Q")
    return (barras + textos + cero).properties(height=230)


# ---------------------------------------------------------------------------
# Contenido
# ---------------------------------------------------------------------------
st.title("🤖 Agente DevOps: revisión inteligente de Pull Requests")
st.caption("Agente basado en utilidad que decide si **fusionar**, **pedir correcciones**, "
           "**escalar a un arquitecto** o **bloquear el despliegue**.")

tab_sim, tab_bateria, tab_sens, tab_teoria = st.tabs(
    ["🧪 Simulador de PR", "📋 Batería de pruebas", "📈 Sensibilidad", "📐 Cómo funciona"])

# --- Simulador ---------------------------------------------------------------
with tab_sim:
    st.selectbox("Cargar un caso de prueba", list(PRESETS), key="preset", on_change=cargar_preset)
    col_in, col_out = st.columns([1, 1.35], gap="large")

    with col_in:
        st.subheader("Sensores del PR")
        st.number_input("Líneas modificadas", 0, 5000, key="lineas", step=10)
        st.text_area("Archivos tocados (uno por línea)", key="archivos", height=90,
                     help="Rutas con auth, payment, infra, migrations… cuentan como módulo crítico.")
        c1, c2 = st.columns(2)
        c1.number_input("Pruebas totales", 0, 2000, key="totales")
        c2.number_input("Pruebas fallidas", 0, 2000, key="fallidos")
        st.slider("Cobertura (%)", 0, 100, key="cobertura")
        st.markdown("**Análisis estático (Bandit)**")
        c3, c4, c5 = st.columns(3)
        c3.number_input("Críticas", 0, 20, key="criticas", help="Secretos expuestos, SQLi")
        c4.number_input("Altas", 0, 20, key="altas")
        c5.number_input("Medias", 0, 20, key="medias")

    archivos = [a.strip() for a in st.session_state.archivos.splitlines() if a.strip()]
    try:
        sensores = SensoresPR(
            id_pr="PR-demo", lineas_modificadas=st.session_state.lineas, archivos=archivos,
            tests_totales=st.session_state.totales,
            tests_fallidos=min(st.session_state.fallidos, st.session_state.totales),
            cobertura=st.session_state.cobertura / 100, alertas_criticas=st.session_state.criticas,
            alertas_altas=st.session_state.altas, alertas_medias=st.session_state.medias,
        )
    except ValueError as exc:
        st.error(f"Lectura de sensores inválida: {exc}")
        st.stop()

    percepcion = sensores.a_percepcion()
    registro = agente.procesar_evento(percepcion)
    p_def = agente.probabilidad_defecto(percepcion.datos_sensores)
    accion = registro["accion"]

    with col_out:
        st.subheader("Decisión del agente")
        m1, m2, m3 = st.columns(3)
        m1.metric("Diagnóstico", registro["diagnostico"].replace("PR_", ""))
        m2.metric("P(defecto)", f"{p_def:.1%}")
        m3.metric("Módulo crítico", "Sí" if sensores.toca_modulo_critico else "No")

        mensaje = f"{ICONOS[accion]} **{accion}** · U = {registro['utilidad']:.2f}"
        {MERGE: st.success, CORREGIR: st.warning, ARQUITECTO: st.info, BLOQUEAR: st.error}[accion](mensaje)

        st.altair_chart(grafica_utilidades(registro["tabla_utilidades"], accion), width="stretch")

        estados = agente.generar_estados_proyectados(registro["diagnostico"], percepcion)
        st.dataframe(pd.DataFrame([{
            "Acción": e.nombre_accion, "P_éxito": e.probabilidad_exito, "Beneficio": e.beneficio_operativo,
            "Riesgo": e.riesgo_impacto, "Costo": e.costo_intervencion, "Déficit calidad": e.deficit_calidad,
            "Viola política": "Sí" if e.viola_politica else "No", "U": agente.calcular_utilidad(e),
        } for e in estados]), hide_index=True, width="stretch")

        if registro["efecto"]["sugerencias"]:
            st.markdown("**Sugerencias para el autor**")
            for s in registro["efecto"]["sugerencias"]:
                st.markdown(f"- {s}")

        with st.expander("💬 Comentario que el agente publicaría en GitHub"):
            st.markdown(construir_comentario(sensores, registro, p_def), unsafe_allow_html=True)
        with st.expander("🔎 Percepción (JSON)"):
            st.json(asdict(sensores))

# --- Batería -----------------------------------------------------------------
with tab_bateria:
    resultados = ejecutar(AgenteDevOps("bateria", pesos))
    kpis = calcular_kpis(resultados)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Precisión vs. experto", f"{kpis['precision_decision']:.0%}")
    k2.metric("Defectos escapados", kpis["defectos_escapados"])
    k3.metric("Merge automático", f"{kpis['tasa_merge_auto']:.0%}")
    k4.metric("Tiempo de ciclo", f"{kpis['ciclo_prom_min']:.0f} min",
              f"{-kpis['reduccion_ciclo']:.1%} vs. revisión senior", delta_color="inverse")

    filas = []
    for r in resultados:
        fila = {"PR": r["id"], "Tipo": r["tipo"], "Título": r["titulo"],
                "Diagnóstico": r["diagnostico"].replace("PR_", ""), "P_def": r["p_defecto"]}
        fila.update({f"U({CORTOS[a]})": r["tabla_utilidades"][a] for a in ACCIONES})
        fila.update({"Decisión": CORTOS[r["accion"]], "Esperada": CORTOS[r["accion_esperada"]],
                     "OK": "✔" if r["accion"] == r["accion_esperada"] else "✘"})
        filas.append(fila)
    st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch")
    st.caption("Los pesos de la barra lateral también aplican aquí: bájale a w_r y mira qué casos fallan.")

# --- Sensibilidad --------------------------------------------------------------
with tab_sens:
    st.markdown("¿Qué pasa si el equipo le da menos importancia al riesgo? "
                "Se repite la batería variando **w_r** y dejando fijos los demás pesos de la barra lateral.")
    valores = list(range(0, 1001, 50))
    datos = []
    for w_r in valores:
        k = calcular_kpis(ejecutar(AgenteDevOps("s", dict(pesos, riesgo=float(w_r)))))
        datos += [{"w_r": w_r, "KPI": "Precisión", "valor": k["precision_decision"]},
                  {"w_r": w_r, "KPI": "Merge automático", "valor": k["tasa_merge_auto"]},
                  {"w_r": w_r, "KPI": "Escalamiento", "valor": k["tasa_escalamiento"]}]
    df = pd.DataFrame(datos)
    linea = alt.Chart(df).mark_line(point=True, interpolate="step-after").encode(
        x=alt.X("w_r:Q", title="Peso del riesgo w_r"),
        y=alt.Y("valor:Q", title=None, axis=alt.Axis(format="%"), scale=alt.Scale(domain=[0, 1.05])),
        color=alt.Color("KPI:N", legend=alt.Legend(orient="bottom")),
        tooltip=["w_r", "KPI", alt.Tooltip("valor:Q", format=".0%")],
    )
    actual = alt.Chart(pd.DataFrame({"x": [pesos["riesgo"]]})).mark_rule(
        strokeDash=[4, 4], color="gray").encode(x="x:Q")
    st.altair_chart((linea + actual).properties(height=360), width="stretch")
    st.caption("La línea punteada es el w_r actual. Con w_r bajo el agente fusiona la migración de "
               "1200 líneas en auth sin revisión senior; desde w_r ≈ 300 las decisiones se estabilizan, y la calibración w_r = 400 deja margen de seguridad.")

# --- Teoría -----------------------------------------------------------------
with tab_teoria:
    st.subheader("Función de utilidad")
    st.latex(r"U(s,a) = w_e P_{\text{éx}} + w_b B(a) - w_r R(s,a) - w_c C(a) - w_q D_q(s,a)"
             r" - w_p \mathbf{1}[\text{viola}(s,a)]")
    st.latex(r"a^* = \arg\max_{a \in \{\text{merge},\,\text{corregir},\,\text{arquitecto},\,"
             r"\text{bloquear}\}} U(s,a)")
    st.subheader("Modelo de riesgo (entorno parcialmente observable)")
    st.latex(r"P_{\text{def}}(s) = \min\big(1,\; 0.05 + 0.45\,r_{\text{tests}} + 0.15\,r_{\text{cob}}"
             r" + 0.15\,r_{\text{tam}} + 0.10\,r_{\text{crit}} + 0.40\,r_{\text{seg}}\big)")
    st.latex(r"R(s,a) = \min\big(1,\; P_{\text{def}}(s)\cdot I(a) + E(s)\big)")
    st.markdown(
        "- **Política dura (w_p):** nunca fusionar con pruebas rotas o vulnerabilidad crítica.\n"
        "- **Exposición E(s):** un secreto expuesto ya es un incidente; solo bloquear cierra la ventana.\n"
        "- **Déficit de calidad D_q:** cobertura bajo 70 % o alertas altas/medias penalizan el merge.")
    st.subheader("Modelo PEAS")
    st.table(pd.DataFrame({
        "Componente": ["Performance", "Environment", "Actuators", "Sensors"],
        "Descripción": [
            "Defectos escapados ↓, tiempo de ciclo ↓, estándares de calidad",
            "Repositorios Git, pipelines CI/CD, pruebas automatizadas, desarrolladores",
            "Merge, comentar, etiquetar, bloquear despliegue, asignar revisor",
            "Diff, reporte de pruebas, cobertura, alertas de análisis estático",
        ]}).set_index("Componente"))
