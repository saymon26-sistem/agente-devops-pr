"""Parámetros calibrados del agente. Cambiar aquí, no dentro de la lógica."""

# Pesos de la función de utilidad U(s, a)
PESOS_UTILIDAD = {
    "exito": 100.0,      # w_e: probabilidad de que la acción deje el PR bien resuelto
    "beneficio": 1.0,    # w_b: velocidad de entrega (0-100)
    "riesgo": 400.0,     # w_r: P(defecto) x impacto en producción
    "costo": 30.0,       # w_c: tiempo humano / bloqueo de pipeline
    "calidad": 300.0,    # w_q: incumplimiento de estándares de calidad
    "politica": 1000.0,  # w_p: violación de política dura (nunca se acepta)
}

# Estándares de calidad del equipo
UMBRAL_COBERTURA = 0.70          # cobertura mínima exigida
TAMANO_PR_REFERENCIA = 1000      # líneas a partir de las cuales el tamaño satura

# Coeficientes del modelo de riesgo P_defecto(s)
RIESGO_BASE = 0.05
COEF_RIESGO = {
    "tests": 0.45,
    "cobertura": 0.15,
    "tamano": 0.15,
    "critico": 0.10,
    "seguridad": 0.40,
}

# Rutas que se consideran módulos críticos
PATRONES_CRITICOS = (
    "auth", "login", "security", "seguridad", "payment", "pago",
    "billing", "infra", "terraform", "k8s", "migrations",
    ".github/workflows", "dockerfile",
)

# Extensiones/rutas de documentación (riesgo prácticamente nulo)
PATRONES_DOCS = (".md", ".rst", ".txt", "docs/", "license")

# Reglas de análisis estático que se tratan como CRÍTICAS
# (secretos expuestos e inyección SQL en Bandit)
REGLAS_CRITICAS_BANDIT = {"B105", "B106", "B107", "B608"}

# Tiempo de ciclo simulado por acción (minutos) para el KPI de ciclo
TIEMPO_CICLO_MIN = {
    "Aprobar y fusionar (merge)": 5,
    "Solicitar correcciones": 240,
    "Asignar arquitecto senior": 720,
    "Bloquear despliegue": 30,
}
