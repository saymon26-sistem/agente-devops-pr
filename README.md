# 🤖 Agente DevOps: revisión inteligente de Pull Requests

[![CI](https://github.com/saymon26-sistem/agente-devops-pr/actions/workflows/ci.yml/badge.svg)](https://github.com/saymon26-sistem/agente-devops-pr/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Cobertura](https://img.shields.io/badge/cobertura-97%25-brightgreen)
![Licencia](https://img.shields.io/badge/licencia-MIT-lightgrey)

Agente inteligente **basado en utilidad** que vive dentro del pipeline de CI/CD de GitHub. Cada vez que llega un Pull Request, el agente lee sus *sensores* (diff, pruebas, cobertura y análisis estático), estima la probabilidad de que el cambio introduzca un defecto y elige la acción que **maximiza la utilidad esperada**:

| Acción | Efecto en GitHub |
|---|---|
| ✅ Aprobar y fusionar | Etiqueta `agente:merge-automatico`, check en verde y merge opcional |
| ✏️ Solicitar correcciones | Comentario con sugerencias técnicas y check en rojo |
| 👀 Asignar arquitecto senior | Etiqueta `agente:revision-senior` y se asigna el revisor |
| ⛔ Bloquear despliegue | Check en rojo, el PR no se puede fusionar |

> **Dilema de utilidad:** acelerar la entrega continua de software frente al riesgo de introducir defectos críticos en producción.

Proyecto 4 del *Taller de Ingeniería de Agentes Inteligentes* (Tecnology Trend, Fundación Universitaria Los Libertadores).

---

## Arquitectura

```
 Sensores (CI)                 Modelo del mundo           Función de utilidad          Actuadores (GitHub)
┌──────────────────┐   ┌──────────────────────────┐   ┌────────────────────────┐   ┌──────────────────────┐
│ git diff --numstat│──▶│ factores r_i ∈ [0,1]     │──▶│ U(s,a) para 4 acciones │──▶│ comentar · etiquetar │
│ pytest (JUnit)    │   │ P_defecto(s)             │   │ argmax_a U(s,a)        │   │ check rojo/verde     │
│ coverage.json     │   │ D_calidad(s)             │   │ penalización política  │   │ merge / revisor      │
│ Bandit (SAST)     │   │ diagnóstico del PR       │   └────────────────────────┘   └──────────────────────┘
└──────────────────┘   └──────────────────────────┘
```

### Función de utilidad

$$U(s,a) = w_e\,P_{\text{éxito}}(a) + w_b\,B(a) - w_r\,R(s,a) - w_c\,C(a) - w_q\,D_q(s,a) - w_p\,\mathbb{1}[\text{viola política}]$$

con $R(s,a) = P_{\text{defecto}}(s)\cdot I(a) + E(s)$ y

$$P_{\text{defecto}}(s) = \min\Big(1,\; r_0 + \sum_i \alpha_i\, r_i(s)\Big)$$

| Peso | Valor | Significado |
|---|---|---|
| $w_e$ | 100 | éxito de la acción |
| $w_b$ | 1 | velocidad de entrega |
| $w_r$ | 400 | riesgo en producción |
| $w_c$ | 30 | costo humano / pipeline |
| $w_q$ | 300 | incumplimiento de estándares |
| $w_p$ | 1000 | política dura (pruebas rotas o vulnerabilidad crítica + merge) |

Las cuatro acciones **se evalúan siempre** y la decisión es el `argmax`. No hay reglas `if/else` decidiendo la acción.

---

## Resultados de la simulación

```
PR      Tipo       Diagnóstico     P_def   U(MERGE) U(CORREG) U(ARQUIT)   U(BLOQ)  Decisión
PR-101  Rutinario  PR_TRIVIAL      0.050     183.00     79.00     97.00     12.00  MERGE   ✔
PR-102  Rutinario  PR_ESTANDAR     0.072     175.35     78.12     96.56     12.00  MERGE   ✔
PR-103  Crítico    PR_FALLIDO      0.170    -857.80    114.20     94.60     12.00  CORREG  ✔
PR-104  Crítico    PR_BLOQUEANTE   0.462   -1157.08    -97.48   -111.24     81.00  BLOQ    ✔
PR-105  Ambiguo    PR_RIESGOSO     0.300      50.00     69.00     92.00     12.00  ARQUIT  ✔
PR-106  Ambiguo    PR_RIESGOSO     0.142      87.48    115.32     95.16     12.00  CORREG  ✔
PR-107  Ambiguo    PR_RIESGOSO     0.263     -39.31    110.48     92.76     12.00  CORREG  ✔
```

| KPI | Valor |
|---|---|
| Precisión de decisión vs. revisor experto | **100 %** |
| Defectos escapados a producción | **0** |
| Tiempo de ciclo promedio | 211 min (−70,6 % frente a revisión senior de todo PR) |

---

## Demo interactiva (Streamlit)

```bash
pip install -r requirements.txt
streamlit run app.py
```

- **Simulador de PR:** mueve los sensores (líneas, pruebas, cobertura, alertas) y mira en vivo $P_{def}$, la utilidad de cada acción y el comentario que se publicaría en GitHub.
- **Pesos ajustables:** cambia $w_r$, $w_q$… en la barra lateral y observa cómo el agente se vuelve más arriesgado o más conservador.
- **Batería de pruebas y sensibilidad:** los 7 casos con sus KPIs y la curva de decisiones frente a $w_r$.

Se puede publicar gratis en [Streamlit Community Cloud](https://streamlit.io/cloud) apuntando a `app.py`.

## Uso

```bash
pip install -r requirements-dev.txt

python simulacion.py --sensibilidad      # 7 escenarios + KPIs + sensibilidad de w_r
pytest --cov                             # 26 pruebas, 97 % de cobertura
python -m scripts.revisar_pr ejemplos/pr_secreto_expuesto.json
```

### Activarlo en tu repositorio

1. Copia `agente_devops/`, `scripts/` y `.github/workflows/agente-pr.yml`.
2. En **Settings → Actions → General** activa *Read and write permissions*.
3. (Opcional) En **Settings → Variables** crea:
   - `AGENTE_AUTOMERGE=true` para que fusione automáticamente los PRs aprobados.
   - `ARQUITECTO_SENIOR=<usuario>` para asignar revisores en los PRs de alto impacto.
4. Activa *branch protection* en `main` exigiendo el check **Agente DevOps**, así un PR bloqueado no puede fusionarse.

---

## Estructura

```
agente_devops/
├── base.py        # Plantilla del taller: Percepcion, EstadoProyectado, AgenteBasadoEnUtilidad
├── sensores.py    # SensoresPR + parsers de git diff, JUnit, coverage y Bandit
├── agente.py      # AgenteDevOps: modelo del mundo, proyección, actuadores
├── kpis.py        # Métricas de desempeño
└── config.py      # Pesos y umbrales calibrados
scripts/
├── recolectar_sensores.py   # Construye la percepción dentro de GitHub Actions
└── revisar_pr.py            # Ejecuta el agente y genera el comentario del PR
app.py             # Demo interactiva en Streamlit
simulacion.py      # Batería de 7 casos de prueba
tests/             # pytest
informe/           # Informe técnico en LaTeX (TikZ)
```

---

**Simon Hurtado** · Ingeniería de Sistemas · *Hurtado Systems*
