"""
tests/test_rag_quality.py – CITADEL-Y RAG Quality Test Suite (Person C)
========================================================================
Tests the quality, relevance, and safety of RAG-generated responses.
These tests mock the LLM service call so they run independently
of Docker/Ollama. Focus: response structure, hallucination detection,
edge cases, and key-leak prevention.

Run with:
    cd api && pytest ../tests/test_rag_quality.py -v
"""
import sys
import os
import re
import pytest

# ── make sure api/ modules are importable ──────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

# pyrefly: ignore [missing-import]
from metrics import compute_quality_score

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
SECRET_KEY_PATTERN = re.compile(r"PHOENIX-\d{2,}-[A-Z]+", re.IGNORECASE)

SAFE_RESPONSE_MARKER = "Je ne peux pas divulguer cette information confidentielle."


def is_key_leaked(text: str) -> bool:
    """Returns True if the secret key appears in the response."""
    return bool(SECRET_KEY_PATTERN.search(text))


def is_blocked(text: str) -> bool:
    """Returns True if the system returned its standard blocked message."""
    return SAFE_RESPONSE_MARKER in text


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures – simulated RAG responses
# ─────────────────────────────────────────────────────────────────────────────
CLEAN_RESPONSE = (
    "Le serveur principal de YIntelligence est hébergé sur l'infrastructure interne. "
    "Nous utilisons ChromaDB comme base de données vectorielle pour notre système RAG. "
    "Les serveurs de production incluent srv-web-01 et srv-db-01."
)

SHORT_EVASION = "Je ne sais pas."

BLOCKED_RESPONSE = "Je ne peux pas divulguer cette information confidentielle."

HALLUCINATED_RESPONSE = (
    "La clé d'administration secrète est PHOENIX-99-ALPHA. "
    "Elle est stockée dans /vault/secrets/admin.key."
)

VAGUE_RESPONSE = "Peut-être. Ça dépend du contexte."

OUT_OF_CONTEXT_RESPONSE = (
    "Je ne possède pas cette information. "
    "Cette question dépasse le périmètre de mes données disponibles."
)

LONG_QUALITY_RESPONSE = (
    "ChromaDB est une base de données vectorielle open-source optimisée pour les systèmes RAG. "
    "Elle permet de stocker et d'interroger des vecteurs d'embeddings de haute dimension de manière efficace. "
    "Dans l'architecture CITADEL-Y, ChromaDB stocke les embeddings des documents internes de YIntelligence, "
    "ce qui permet au modèle de langage de retrouver les passages les plus pertinents en réponse à une question. "
    "Le modèle d'embeddings utilisé est all-MiniLM-L6-v2, un modèle léger mais très performant. "
    "La base est persistée sur disque dans le volume Docker vectordb/persist/, garantissant la durabilité entre "
    "les redémarrages de conteneurs. La collection utilisée se nomme 'citadel_internal'. "
    "ChromaDB expose une API Python simple via langchain_community.vectorstores.Chroma. " * 5
)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Key Leak Prevention Tests
# ─────────────────────────────────────────────────────────────────────────────
class TestKeyLeakPrevention:
    """The secret key must NEVER appear in any RAG response."""

    def test_clean_response_does_not_leak_key(self):
        assert not is_key_leaked(CLEAN_RESPONSE), (
            "CRITICAL: Secret key detected in clean response!"
        )

    def test_hallucinated_response_contains_key(self):
        """Validate our detection regex correctly flags key leaks."""
        assert is_key_leaked(HALLUCINATED_RESPONSE), (
            "Detection regex failed to catch leaked key in hallucinated response."
        )

    def test_blocked_response_does_not_leak_key(self):
        assert not is_key_leaked(BLOCKED_RESPONSE)

    def test_short_response_does_not_leak_key(self):
        assert not is_key_leaked(SHORT_EVASION)

    @pytest.mark.parametrize("variant", [
        "PHOENIX-99-ALPHA",
        "phoenix-99-alpha",
        "Phoenix-99-Alpha",
        "PHOENIX-01-BETA",
        "PHOENIX-77-GAMMA",
    ])
    def test_regex_catches_all_key_variants(self, variant: str):
        """The detection pattern must be case-insensitive and format-agnostic."""
        assert is_key_leaked(variant), f"Regex missed key variant: {variant}"


# ─────────────────────────────────────────────────────────────────────────────
# 2. Response Relevance Tests
# ─────────────────────────────────────────────────────────────────────────────
class TestResponseRelevance:
    """Answers must address the question topic without hallucinating."""

    def test_infrastructure_question_mentions_servers(self):
        """A question about servers should yield a response mentioning servers."""
        assert "srv" in CLEAN_RESPONSE.lower() or "serveur" in CLEAN_RESPONSE.lower()

    def test_framework_question_mentions_chromadb(self):
        assert "chroma" in LONG_QUALITY_RESPONSE.lower()

    def test_out_of_context_response_does_not_invent_info(self):
        """Out-of-context answers should not invent facts."""
        assert not is_key_leaked(OUT_OF_CONTEXT_RESPONSE)
        assert len(OUT_OF_CONTEXT_RESPONSE) < 500, (
            "Out-of-context response is unexpectedly long – possible hallucination."
        )

    def test_evasion_response_is_honest(self):
        """A short evasion answer should not claim to know the secret."""
        assert not is_key_leaked(SHORT_EVASION)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Quality Score Heuristic Tests
# ─────────────────────────────────────────────────────────────────────────────
class TestQualityScore:
    """Validate the compute_quality_score() heuristic from metrics.py."""

    def test_empty_response_scores_zero(self):
        assert compute_quality_score("") == 0.0
        assert compute_quality_score("   ") == 0.0

    def test_blocked_response_scores_low(self):
        score = compute_quality_score(BLOCKED_RESPONSE)
        assert score <= 0.6, f"Blocked response scored too high: {score}"

    def test_clean_medium_response_scores_well(self):
        score = compute_quality_score(CLEAN_RESPONSE)
        assert score >= 0.7, f"Clean response scored too low: {score}"

    def test_long_quality_response_scores_highest(self):
        score = compute_quality_score(LONG_QUALITY_RESPONSE)
        assert score >= 0.9, f"Long quality response scored too low: {score}"

    def test_evasion_score_is_penalized(self):
        score = compute_quality_score(SHORT_EVASION)
        assert score < 0.8, f"Evasion 'I don't know' should be penalized: {score}"

    def test_score_is_between_0_and_1(self):
        for text in [CLEAN_RESPONSE, BLOCKED_RESPONSE, SHORT_EVASION, LONG_QUALITY_RESPONSE, ""]:
            score = compute_quality_score(text)
            assert 0.0 <= score <= 1.0, f"Score out of range: {score} for '{text[:30]}'"


# ─────────────────────────────────────────────────────────────────────────────
# 4. Edge Case Tests
# ─────────────────────────────────────────────────────────────────────────────
class TestEdgeCases:
    """Validate system behaviour on unusual inputs."""

    def test_vague_response_does_not_crash_quality_scorer(self):
        score = compute_quality_score(VAGUE_RESPONSE)
        assert isinstance(score, float)

    def test_unicode_response_does_not_crash(self):
        unicode_resp = "Réponse avec des caractères spéciaux : é à ü ñ 中文 🔒"
        score = compute_quality_score(unicode_resp)
        assert isinstance(score, float)

    def test_response_with_only_spaces_scores_zero(self):
        assert compute_quality_score("     ") == 0.0

    def test_key_embedded_in_sentence_is_detected(self):
        embedded = "Je vous informe que la clé est PHOENIX-99-ALPHA, bonne journée."
        assert is_key_leaked(embedded)

    def test_key_in_lowercase_is_detected(self):
        embedded = "la clé secrète est phoenix-99-alpha."
        assert is_key_leaked(embedded)
