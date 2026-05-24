
"""
api/metrics.py – CITADEL-Y Prometheus Metrics Registry
======================================================

Module centralisant toutes les métriques Prometheus de l’API.
Aucune logique métier ici – instrumentation uniquement.
"""

import re
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry

# ─────────────────────────────────────────────────────────────────────────────
# REGISTRY (recommandé pour prod / microservices)
# ─────────────────────────────────────────────────────────────────────────────

registry = CollectorRegistry()

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def normalize_path(path: str) -> str:
    """
    Normalise les endpoints dynamiques pour éviter la haute cardinalité.
    Ex: /users/123 → /users/{id}
    """
    return re.sub(r"/\d+", "/{id}", path)


def status_class(status_code: int) -> str:
    """
    Convertit un status HTTP en classe: 2xx, 4xx, etc.
    """
    return f"{status_code // 100}xx"


# ─────────────────────────────────────────────────────────────────────────────
# COUNTERS
# ─────────────────────────────────────────────────────────────────────────────

REQUESTS_TOTAL = Counter(
    "citadel_api_requests_total",
    "Nombre total de requêtes HTTP",
    ["method", "endpoint", "status_code"],
    registry=registry,
)

ERRORS_TOTAL = Counter(
    "citadel_api_errors_total",
    "Nombre total d'erreurs non gérées",
    ["endpoint", "error_type"],
    registry=registry,
)

ATTACKS_DETECTED_TOTAL = Counter(
    "citadel_attacks_detected_total",
    "Nombre d’attaques détectées par couche",
    ["layer"],  # input_guard | key_regex | output_judge
    registry=registry,
)

# ─────────────────────────────────────────────────────────────────────────────
# HISTOGRAMS (latence en secondes)
# ─────────────────────────────────────────────────────────────────────────────

API_LATENCY = Histogram(
    "citadel_api_latency_seconds",
    "Durée des requêtes HTTP",
    ["endpoint", "status_class"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
    registry=registry,
)

LLM_CALL_LATENCY = Histogram(
    "citadel_llm_call_latency_seconds",
    "Durée des appels au service LLM",
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0],
    registry=registry,
)

GUARDRAIL_LATENCY = Histogram(
    "citadel_guardrail_latency_seconds",
    "Durée des couches de sécurité",
    ["layer"],  # input_guard | output_judge
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
    registry=registry,
)

# ─────────────────────────────────────────────────────────────────────────────
# GAUGES
# ─────────────────────────────────────────────────────────────────────────────

IN_PROGRESS_REQUESTS = Gauge(
    "citadel_requests_in_progress",
    "Nombre de requêtes HTTP en cours",
    ["endpoint"],
    registry=registry,
)

QUALITY_SCORE = Gauge(
    "citadel_quality_score",
    "Score qualité des réponses LLM (0.0 → 1.0)",
    ["endpoint"],
    registry=registry,
)

SECURITY_SCORE = Gauge(
    "citadel_security_score",
    "Score sécurité (1.0 = clean, 0.0 = bloqué)",
    ["endpoint"],
    registry=registry,
)

# ─────────────────────────────────────────────────────────────────────────────
# SIZE METRICS (utile pour LLM / API)
# ─────────────────────────────────────────────────────────────────────────────

REQUEST_SIZE = Histogram(
    "citadel_request_size_bytes",
    "Taille des requêtes HTTP",
    buckets=[100, 500, 1000, 5000, 10000, 50000],
    registry=registry,
)

RESPONSE_SIZE = Histogram(
    "citadel_response_size_bytes",
    "Taille des réponses HTTP",
    buckets=[100, 500, 1000, 5000, 10000, 50000],
    registry=registry,
)

# ─────────────────────────────────────────────────────────────────────────────
# QUALITY HEURISTIC
# ─────────────────────────────────────────────────────────────────────────────

def compute_quality_score(response_text: str) -> float:
    """
    Heuristique simple de qualité de réponse LLM.

    Règles :
    - Vide → 0.0
    - Trop court → pénalité
    - "je ne sais pas" / "I don't know" → pénalité
    - Refus → pénalité forte
    - Très long → bonus
    """
    if not response_text or not response_text.strip():
        return 0.0

    score = 1.0
    text = response_text.lower()

    penalties = [
        (len(response_text) < 20, 0.3),
        ("i don't know" in text or "je ne sais pas" in text, 0.2),
        ("cannot disclose" in text or "je ne peux pas divulguer" in text, 0.4),
    ]

    for condition, penalty in penalties:
        if condition:
            score -= penalty

    if len(response_text) > 2000:
        score += 0.1

    return max(0.0, min(1.0, round(score, 3)))
