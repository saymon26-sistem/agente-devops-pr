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

st.set_page_config(page_title="Agente DevOps | Revisión de Pull Requests", layout="wide",
                   initial_sidebar_state="expanded")

# ---------------------------------------------------------------------------
# Paleta y estilos
# ---------------------------------------------------------------------------
TINTA, SUAVE, BORDE, FONDO = "#0F172A", "#64748B", "#E2E8F0", "#F8FAFC"
COLORES = {MERGE: "#16A34A", CORREGIR: "#D97706", ARQUITECTO: "#2563EB", BLOQUEAR: "#DC2626"}
CORTOS = {MERGE: "Merge", CORREGIR: "Corregir", ARQUITECTO: "Arquitecto", BLOQUEAR: "Bloquear"}
DESCRIPCION = {
    MERGE: "El PR cumple los estándares y su riesgo es bajo. Se aprueba y se fusiona sin intervención humana.",
    CORREGIR: "Hay hallazgos concretos que el autor puede resolver. Se publica feedback y el check queda en rojo.",
    ARQUITECTO: "Cambio de alto impacto sin fallas evidentes. Se asigna a un arquitecto senior para revisión.",
    BLOQUEAR: "Hallazgo crítico de seguridad. El pipeline se detiene para contener el incidente.",
}

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap');
html, body, [class*="css"], .stMarkdown, .stText, input, textarea, button, select {{
  font-family: 'Inter', system-ui, -apple-system, sans-serif !important;
}}
[data-testid="stAppViewContainer"] {{ background: {FONDO}; }}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stToolbar"], footer {{ display: none !important; }}
.block-container {{ padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1320px; }}

/* Sidebar */
[data-testid="stSidebar"] {{ background: {TINTA}; }}
[data-testid="stSidebar"] * {{ color: #CBD5E1; }}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{ color: #F8FAFC; }}
[data-testid="stSidebar"] .stButton button {{
  background: transparent; border: 1px solid #334155; color: #E2E8F0; border-radius: 10px;
}}
[data-testid="stSidebar"] .stButton button:hover {{ border-color: #60A5FA; color: #FFFFFF; }}
.sb-titulo {{ font-size: .72rem; letter-spacing: .12em; text-transform: uppercase; color: #94A3B8 !important;
  font-weight: 600; margin: .4rem 0 .2rem; }}
.sb-marca {{ font-weight: 800; font-size: 1.05rem; color: #F8FAFC !important; letter-spacing: -.01em; }}
.sb-pie {{ font-size: .78rem; color: #64748B !important; line-height: 1.5; }}

/* Hero */
.hero {{ background: linear-gradient(120deg, #0F172A 0%, #1E3A5F 60%, #1D4ED8 130%); border-radius: 18px;
  padding: 2.1rem 2.4rem; color: #F8FAFC; margin-bottom: 1.4rem; position: relative; overflow: hidden; }}
.hero:after {{ content: ""; position: absolute; right: -80px; top: -80px; width: 320px; height: 320px;
  border-radius: 50%; background: radial-gradient(circle, rgba(96,165,250,.35), transparent 70%); }}
.hero .eyebrow {{ font-size: .75rem; letter-spacing: .16em; text-transform: uppercase; color: #93C5FD; font-weight: 600; }}
.hero h1 {{ font-size: 2.15rem; font-weight: 800; letter-spacing: -.025em; margin: .35rem 0 .5rem; color: #FFFFFF; padding: 0; }}
.hero p {{ color: #CBD5E1; font-size: 1rem; max-width: 760px; margin: 0; }}
.chips {{ margin-top: 1.1rem; display: flex; gap: .5rem; flex-wrap: wrap; }}
.chip {{ border: 1px solid rgba(148,163,184,.35); background: rgba(15,23,42,.35); color: #E2E8F0;
  padding: .28rem .75rem; border-radius: 999px; font-size: .78rem; font-weight: 500; }}

/* Tabs */
div[role="tablist"] {{ gap: .3rem; background: #FFFFFF; padding: .3rem; border-radius: 12px;
  border: 1px solid {BORDE}; width: fit-content; }}
[role="tab"] {{ padding: .45rem 1.15rem !important; border-radius: 9px !important; background: transparent;
  margin: 0 !important; }}
[role="tab"] p {{ font-weight: 600 !important; color: {SUAVE}; font-size: .92rem !important; }}
[role="tab"][aria-selected="true"] {{ background: {TINTA} !important; }}
[role="tab"][aria-selected="true"] p {{ color: #FFFFFF !important; }}
.react-aria-SelectionIndicator, div[data-baseweb="tab-highlight"], div[data-baseweb="tab-border"] {{ display: none !important; }}
[role="tab"] {{ cursor: pointer; }}

/* Tarjetas */
[data-testid="stVerticalBlockBorderWrapper"] {{ background: #FFFFFF; border-radius: 16px !important;
  border: 1px solid {BORDE} !important; box-shadow: 0 1px 2px rgba(15,23,42,.04); }}
.seccion {{ font-size: .72rem; letter-spacing: .12em; text-transform: uppercase; color: {SUAVE};
  font-weight: 700; margin-bottom: .6rem; }}
.titulo-card {{ font-size: 1.05rem; font-weight: 700; color: {TINTA}; margin: -.2rem 0 .8rem; }}

/* Pipeline */
.pipe {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: .6rem; margin: .2rem 0 1.1rem; }}
.paso {{ background: #FFFFFF; border: 1px solid {BORDE}; border-radius: 12px; padding: .75rem .9rem; position: relative; }}
.paso .n {{ font-family: 'JetBrains Mono', monospace; font-size: .7rem; color: #94A3B8; font-weight: 600; }}
.paso .t {{ font-weight: 700; color: {TINTA}; font-size: .9rem; margin-top: .1rem; }}
.paso .v {{ color: {SUAVE}; font-size: .8rem; margin-top: .15rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.paso.activo {{ border-color: var(--c); box-shadow: inset 0 -3px 0 var(--c); }}

/* Decisión */
.decision {{ border-radius: 16px; padding: 1.4rem 1.5rem; background: #FFFFFF; border: 1px solid {BORDE};
  border-left: 6px solid var(--c); margin-bottom: 1rem; }}
.decision .lbl {{ font-size: .72rem; letter-spacing: .14em; text-transform: uppercase; color: {SUAVE}; font-weight: 700; }}
.decision .accion {{ font-size: 1.7rem; font-weight: 800; color: var(--c); letter-spacing: -.02em; margin: .2rem 0 .3rem; }}
.decision .desc {{ color: #334155; font-size: .93rem; }}
.decision .u {{ float: right; text-align: right; }}
.decision .u b {{ font-family: 'JetBrains Mono', monospace; font-size: 1.6rem; color: {TINTA}; display: block; }}
.decision .u span {{ font-size: .72rem; color: {SUAVE}; letter-spacing: .1em; text-transform: uppercase; }}

/* Stats */
.stats {{ display: grid; grid-template-columns: repeat(var(--cols, 3), 1fr); gap: .75rem; margin-bottom: 1rem; }}
.stat {{ background: #FFFFFF; border: 1px solid {BORDE}; border-radius: 14px; padding: .95rem 1.1rem; }}
.stat .k {{ font-size: .72rem; letter-spacing: .1em; text-transform: uppercase; color: {SUAVE}; font-weight: 600; }}
.stat .v {{ font-size: 1.55rem; font-weight: 800; color: {TINTA}; letter-spacing: -.02em; margin-top: .15rem; }}
.stat .s {{ font-size: .8rem; color: {SUAVE}; margin-top: .1rem; }}
.barra {{ height: 6px; background: #EEF2F7; border-radius: 99px; margin-top: .55rem; overflow: hidden; }}
.barra i {{ display: block; height: 100%; border-radius: 99px; }}
.bueno {{ color: #16A34A !important; }}

/* Sugerencias */
.sug {{ border: 1px solid {BORDE}; border-radius: 12px; padding: .7rem .95rem; margin-bottom: .5rem;
  background: #FFFFFF; color: #334155; font-size: .9rem; border-left: 3px solid #94A3B8; }}

/* Fórmulas */
.formula-card {{ background: #FFFFFF; border: 1px solid {BORDE}; border-radius: 14px; padding: 1rem 1.2rem; height: 100%; }}
.formula-card h4 {{ margin: 0 0 .3rem; font-size: .95rem; color: {TINTA}; }}
.formula-card p {{ margin: 0; color: {SUAVE}; font-size: .88rem; }}

[data-testid="stExpander"] {{ background: #FFFFFF; border-radius: 12px; border: 1px solid {BORDE}; }}
</style>
""", unsafe_allow_html=True)


def html(texto: str) -> None:
    """Renderiza HTML sin que la indentación lo convierta en bloque de código."""
    st.markdown("\n".join(l.strip() for l in texto.strip().splitlines()), unsafe_allow_html=True)


@alt.theme.register("devops", enable=True)
def tema_altair() -> alt.theme.ThemeConfig:
    return {"config": {
        "font": "Inter", "view": {"stroke": None},
        "axis": {"labelColor": SUAVE, "titleColor": SUAVE, "gridColor": "#EEF2F7", "domainColor": BORDE,
                 "tickColor": BORDE, "labelFontSize": 12, "titleFontSize": 12, "titleFontWeight": 600},
        "legend": {"labelColor": "#334155", "titleColor": SUAVE, "labelFontSize": 12},
    }}


# ---------------------------------------------------------------------------
# Estado
# ---------------------------------------------------------------------------
ETIQUETAS_PESOS = {
    "exito": ("Éxito de la acción  (w_e)", 0.0, 300.0),
    "beneficio": ("Velocidad de entrega  (w_b)", 0.0, 5.0),
    "riesgo": ("Riesgo en producción  (w_r)", 0.0, 1000.0),
    "costo": ("Costo humano  (w_c)", 0.0, 150.0),
    "calidad": ("Estándares de calidad  (w_q)", 0.0, 800.0),
    "politica": ("Política dura  (w_p)", 0.0, 2000.0),
}
PRESETS = {f"{c['sensores'].id_pr}  —  {c['sensores'].titulo}  ({c['tipo'].lower()})": c for c in CASOS}


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
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    html('<div class="sb-marca">Hurtado Systems</div><div class="sb-pie">Agente DevOps · v1.0</div>')
    st.write("")
    html('<div class="sb-titulo">Pesos de la función de utilidad</div>')
    st.caption("Ajusta lo que el equipo valora. Todas las vistas se recalculan.")
    for k, (etiqueta, minimo, maximo) in ETIQUETAS_PESOS.items():
        st.slider(etiqueta, minimo, maximo, key=f"w_{k}")
    st.button("Restablecer calibración", on_click=restablecer_pesos, width="stretch")
    st.write("")
    html('<div class="sb-pie">Proyecto 4 · Taller de Ingeniería de Agentes Inteligentes<br>'
         'Tecnology Trend · Fundación Universitaria Los Libertadores<br><br>'
         '<b style="color:#E2E8F0">Simon Hurtado</b></div>')

pesos = {k: float(st.session_state[f"w_{k}"]) for k in config.PESOS_UTILIDAD}
agente = AgenteDevOps("AgenteDevOps-demo", pesos)

# ---------------------------------------------------------------------------
# Hero
# ---------------------------------------------------------------------------
html("""
<div class="hero">
  <div class="eyebrow">Agente inteligente · CI/CD</div>
  <h1>Revisión autónoma de Pull Requests</h1>
  <p>Un agente basado en utilidad que lee los sensores del pipeline, estima la probabilidad de defecto y elige
  entre fusionar, pedir correcciones, escalar a un arquitecto o bloquear el despliegue.</p>
  <div class="chips"><span class="chip">Modelo PEAS</span><span class="chip">U(s, a) multiobjetivo</span>
  <span class="chip">GitHub Actions</span><span class="chip">Python</span></div>
</div>
""")


def grafica_utilidades(tabla: dict, elegida: str) -> alt.Chart:
    df = pd.DataFrame({"Acción": [CORTOS[a] for a in tabla], "U": list(tabla.values()), "accion": list(tabla)})
    piso = max(-250.0, min(-20.0, df["U"].min() * 1.1))
    techo = max(60.0, df["U"].max() * 1.2)
    df["U_vis"] = df["U"].clip(lower=piso)
    df["Color"] = df["accion"].map(COLORES)
    df["Elegida"] = df["accion"] == elegida
    df["Etiqueta"] = df["U"].map(lambda u: f"{u:,.1f}" + ("  (recortado)" if u < piso else ""))
    base = alt.Chart(df).encode(y=alt.Y("Acción:N", sort=[CORTOS[a] for a in ACCIONES], title=None,
                                        axis=alt.Axis(labelFontWeight=600, labelColor="#334155", ticks=False, domain=False)))
    barras = base.mark_bar(cornerRadiusEnd=6, height=26).encode(
        x=alt.X("U_vis:Q", title="Utilidad U(s, a)", scale=alt.Scale(domain=[piso, techo])),
        color=alt.Color("Color:N", scale=None),
        opacity=alt.condition("datum.Elegida", alt.value(1.0), alt.value(0.28)),
        tooltip=[alt.Tooltip("Acción:N"), alt.Tooltip("U:Q", format=".2f")],
    )
    textos = base.mark_text(align="left", dx=8, fontWeight=600, color="#334155", font="JetBrains Mono").encode(
        x="U_vis:Q", text="Etiqueta:N")
    cero = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(color="#94A3B8", strokeWidth=1).encode(x="x:Q")
    return (barras + textos + cero).properties(height=210)


tab_sim, tab_bateria, tab_sens, tab_teoria = st.tabs(
    ["Simulador", "Batería de pruebas", "Sensibilidad", "Modelo del agente"])

# ---------------------------------------------------------------------------
# Simulador
# ---------------------------------------------------------------------------
with tab_sim:
    st.selectbox("Escenario", list(PRESETS), key="preset", on_change=cargar_preset)

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
    accion, color = registro["accion"], COLORES[registro["accion"]]
    diag = registro["diagnostico"].replace("PR_", "").capitalize()

    html(f"""
    <div class="pipe" style="--c:{color}">
      <div class="paso"><div class="n">01</div><div class="t">Sensores</div>
        <div class="v">{sensores.lineas_modificadas} líneas · {sensores.cobertura:.0%} cob.</div></div>
      <div class="paso"><div class="n">02</div><div class="t">Modelo del mundo</div>
        <div class="v">P(defecto) = {p_def:.1%}</div></div>
      <div class="paso"><div class="n">03</div><div class="t">Diagnóstico</div><div class="v">{diag}</div></div>
      <div class="paso"><div class="n">04</div><div class="t">Utilidad</div>
        <div class="v">4 acciones evaluadas</div></div>
      <div class="paso activo"><div class="n">05</div><div class="t">Actuador</div>
        <div class="v" style="color:{color};font-weight:600">{CORTOS[accion]}</div></div>
    </div>
    """)

    col_in, col_out = st.columns([1, 1.55], gap="large")

    with col_in:
        with st.container(border=True):
            html('<div class="seccion">Percepción</div><div class="titulo-card">Sensores del Pull Request</div>')
            st.number_input("Líneas modificadas", 0, 5000, key="lineas", step=10)
            st.text_area("Archivos tocados (uno por línea)", key="archivos", height=96,
                         help="Rutas con auth, payment, infra o migrations cuentan como módulo crítico.")
            c1, c2 = st.columns(2)
            c1.number_input("Pruebas totales", 0, 2000, key="totales")
            c2.number_input("Pruebas fallidas", 0, 2000, key="fallidos")
            st.slider("Cobertura de código (%)", 0, 100, key="cobertura")
            html('<div class="seccion" style="margin-top:.4rem">Análisis estático (Bandit)</div>')
            c3, c4, c5 = st.columns(3)
            c3.number_input("Críticas", 0, 20, key="criticas", help="Secretos expuestos, inyección SQL")
            c4.number_input("Altas", 0, 20, key="altas")
            c5.number_input("Medias", 0, 20, key="medias")

    with col_out:
        html(f"""
        <div class="decision" style="--c:{color}">
          <div class="u"><span>Utilidad</span><b>{registro['utilidad']:.2f}</b></div>
          <div class="lbl">Decisión del agente</div>
          <div class="accion">{accion}</div>
          <div class="desc">{DESCRIPCION[accion]}</div>
        </div>
        """)
        color_p = "#16A34A" if p_def < .15 else "#D97706" if p_def < .3 else "#DC2626"
        html(f"""
        <div class="stats">
          <div class="stat"><div class="k">Probabilidad de defecto</div><div class="v">{p_def:.1%}</div>
            <div class="barra"><i style="width:{p_def*100:.0f}%;background:{color_p}"></i></div></div>
          <div class="stat"><div class="k">Diagnóstico</div><div class="v">{diag}</div>
            <div class="s">Estado interno estimado</div></div>
          <div class="stat"><div class="k">Módulo crítico</div>
            <div class="v">{"Sí" if sensores.toca_modulo_critico else "No"}</div>
            <div class="s">{"Impacto en producción alto" if sensores.toca_modulo_critico else "Impacto estándar"}</div></div>
        </div>
        """)
        with st.container(border=True):
            html('<div class="seccion">Función de utilidad</div><div class="titulo-card">U(s, a) por acción</div>')
            st.altair_chart(grafica_utilidades(registro["tabla_utilidades"], accion), width="stretch")

    with st.container(border=True):
        html('<div class="seccion">Modelo de transición</div><div class="titulo-card">Estados proyectados</div>')
        estados = agente.generar_estados_proyectados(registro["diagnostico"], percepcion)
        st.dataframe(pd.DataFrame([{
            "Acción": e.nombre_accion, "P(éxito)": e.probabilidad_exito, "Beneficio": e.beneficio_operativo,
            "Riesgo": e.riesgo_impacto, "Costo": e.costo_intervencion, "Déficit calidad": e.deficit_calidad,
            "Viola política": "Sí" if e.viola_politica else "No", "U(s, a)": agente.calcular_utilidad(e),
        } for e in estados]), hide_index=True, width="stretch",
            column_config={"P(éxito)": st.column_config.ProgressColumn(format="%.2f", min_value=0, max_value=1),
                           "Riesgo": st.column_config.ProgressColumn(format="%.3f", min_value=0, max_value=1),
                           "U(s, a)": st.column_config.NumberColumn(format="%.2f")})

    col_a, col_b = st.columns(2, gap="large")
    with col_a:
        html('<div class="seccion" style="margin-top:.6rem">Feedback para el autor</div>')
        sugerencias = registro["efecto"]["sugerencias"] or ["Sin observaciones: el PR cumple los estándares del equipo."]
        for s in sugerencias:
            html(f'<div class="sug">{s}</div>')
    with col_b:
        html('<div class="seccion" style="margin-top:.6rem">Integración</div>')
        with st.expander("Comentario que el agente publicaría en GitHub"):
            st.markdown(construir_comentario(sensores, registro, p_def), unsafe_allow_html=True)
        with st.expander("Percepción en formato JSON"):
            st.json(asdict(sensores))

# ---------------------------------------------------------------------------
# Batería
# ---------------------------------------------------------------------------
with tab_bateria:
    resultados = ejecutar(AgenteDevOps("bateria", pesos))
    kpis = calcular_kpis(resultados)
    ok = kpis["precision_decision"] == 1.0
    html(f"""
    <div class="stats" style="--cols:4;margin-top:.4rem">
      <div class="stat"><div class="k">Precisión vs. experto</div>
        <div class="v {'bueno' if ok else ''}">{kpis['precision_decision']:.0%}</div>
        <div class="s">{sum(r['accion'] == r['accion_esperada'] for r in resultados)} de {kpis['casos']} decisiones</div></div>
      <div class="stat"><div class="k">Defectos escapados</div>
        <div class="v {'bueno' if kpis['defectos_escapados'] == 0 else ''}">{kpis['defectos_escapados']}</div>
        <div class="s">Recall de defectos {kpis['recall_defectos']:.0%}</div></div>
      <div class="stat"><div class="k">Merge automático</div><div class="v">{kpis['tasa_merge_auto']:.0%}</div>
        <div class="s">Escalamiento {kpis['tasa_escalamiento']:.0%}</div></div>
      <div class="stat"><div class="k">Tiempo de ciclo</div><div class="v">{kpis['ciclo_prom_min']:.0f} min</div>
        <div class="s bueno">{kpis['reduccion_ciclo']:.1%} menos que revisión senior</div></div>
    </div>
    """)
    with st.container(border=True):
        html('<div class="seccion">Casos de prueba</div><div class="titulo-card">Rutinarios, ambiguos y críticos</div>')
        filas = []
        for r in resultados:
            fila = {"PR": r["id"], "Tipo": r["tipo"],
                    "Diagnóstico": r["diagnostico"].replace("PR_", "").capitalize(), "P(defecto)": r["p_defecto"]}
            fila.update({f"U {CORTOS[a]}": r["tabla_utilidades"][a] for a in ACCIONES})
            fila.update({"Decisión": CORTOS[r["accion"]], "Correcta": r["accion"] == r["accion_esperada"]})
            filas.append(fila)
        st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch", column_config={
            "P(defecto)": st.column_config.ProgressColumn(format="%.3f", min_value=0, max_value=1),
            **{f"U {CORTOS[a]}": st.column_config.NumberColumn(format="%.1f") for a in ACCIONES},
            "Correcta": st.column_config.CheckboxColumn()})
        st.caption("Los pesos de la barra lateral también aplican aquí. Baja w_r para ver qué casos empiezan a fallar.")

# ---------------------------------------------------------------------------
# Sensibilidad
# ---------------------------------------------------------------------------
with tab_sens:
    datos = []
    for w_r in range(0, 1001, 50):
        k = calcular_kpis(ejecutar(AgenteDevOps("s", dict(pesos, riesgo=float(w_r)))))
        datos += [{"w_r": w_r, "KPI": "Precisión", "valor": k["precision_decision"]},
                  {"w_r": w_r, "KPI": "Merge automático", "valor": k["tasa_merge_auto"]},
                  {"w_r": w_r, "KPI": "Escalamiento a senior", "valor": k["tasa_escalamiento"]}]
    df = pd.DataFrame(datos)
    with st.container(border=True):
        html('<div class="seccion">Análisis de sensibilidad</div>'
             '<div class="titulo-card">¿Qué pasa si el equipo le da menos importancia al riesgo?</div>')
        linea = alt.Chart(df).mark_line(interpolate="step-after", strokeWidth=2.5).encode(
            x=alt.X("w_r:Q", title="Peso del riesgo w_r"),
            y=alt.Y("valor:Q", title=None, axis=alt.Axis(format="%"), scale=alt.Scale(domain=[0, 1.05])),
            color=alt.Color("KPI:N", legend=alt.Legend(orient="top", title=None),
                            scale=alt.Scale(range=[TINTA, "#16A34A", "#2563EB"])),
            tooltip=["w_r", "KPI", alt.Tooltip("valor:Q", format=".0%")],
        )
        actual = alt.Chart(pd.DataFrame({"x": [pesos["riesgo"]], "t": ["calibración actual"]}))
        regla = actual.mark_rule(strokeDash=[5, 4], color="#94A3B8").encode(x="x:Q")
        rotulo = actual.mark_text(align="left", dx=6, dy=-150, color=SUAVE, fontSize=11).encode(x="x:Q", text="t:N")
        st.altair_chart((linea + regla + rotulo).properties(height=360), width="stretch")
        st.caption("Con w_r bajo el agente fusiona la migración de 1200 líneas en el módulo de autenticación sin "
                   "revisión senior, y con w_r < 100 ni siquiera bloquea un secreto expuesto. Desde w_r ≈ 300 las "
                   "decisiones se estabilizan; la calibración w_r = 400 deja margen de seguridad.")

# ---------------------------------------------------------------------------
# Modelo del agente
# ---------------------------------------------------------------------------
with tab_teoria:
    with st.container(border=True):
        html('<div class="seccion">Función de utilidad</div><div class="titulo-card">Decisión por máxima utilidad esperada</div>')
        st.latex(r"U(s,a) = w_e\,P_{\text{éx}}(a) + w_b\,B(a) - w_r\,R(s,a) - w_c\,C(a) - w_q\,D_q(s,a)"
                 r" - w_p\,\mathbf{1}[\text{viola}(s,a)]")
        st.latex(r"a^{*} = \arg\max_{a}\; U(s,a)")
        st.latex(r"P_{\text{def}}(s) = \min\big(1,\; 0.05 + 0.45\,r_{\text{tests}} + 0.15\,r_{\text{cob}}"
                 r" + 0.15\,r_{\text{tam}} + 0.10\,r_{\text{crit}} + 0.40\,r_{\text{seg}}\big)")

    c1, c2, c3 = st.columns(3)
    for col, titulo, texto in (
        (c1, "Política dura (w_p)", "Nunca se fusiona código con pruebas rotas o con una vulnerabilidad crítica, "
                                    "sin importar cuánto valga la velocidad."),
        (c2, "Exposición E(s)", "Un secreto expuesto ya es un incidente: cualquier acción que no detenga el "
                                "pipeline deja abierta la ventana de explotación."),
        (c3, "Déficit de calidad D_q", "Cobertura bajo 70 % o alertas altas y medias penalizan el merge "
                                       "aunque las pruebas pasen."),
    ):
        with col:
            html(f'<div class="formula-card"><h4>{titulo}</h4><p>{texto}</p></div>')

    st.write("")
    with st.container(border=True):
        html('<div class="seccion">Especificación</div><div class="titulo-card">Modelo PEAS</div>')
        st.dataframe(pd.DataFrame({
            "Componente": ["Performance", "Environment", "Actuators", "Sensors"],
            "Descripción": [
                "Defectos escapados a producción, tiempo de ciclo de aprobación, cumplimiento de estándares de calidad",
                "Repositorios Git, pipelines de CI/CD, pruebas automatizadas, desarrolladores y arquitectos",
                "Aprobar y fusionar, comentar, etiquetar, bloquear el despliegue, asignar revisor",
                "Diff del PR, reporte de pruebas, cobertura de código, alertas de análisis estático",
            ]}), hide_index=True, width="stretch")
