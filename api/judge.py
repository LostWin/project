import re
import logging
import httpx
import os
from typing import Tuple

logger = logging.getLogger(__name__)

# Determine Ollama base URL (Docker vs Local)
if os.path.exists('/.dockerenv'):
    OLLAMA_BASE_URL = "http://ollama:11434"
else:
    OLLAMA_BASE_URL = "http://localhost:11434"

LLM_JUDGE_MODEL = os.getenv("LLM_JUDGE_MODEL", "phi3:mini")

class OutputJudge:
    """
    Layer 2 of defense.
    Uses phi3:mini (via Ollama) to semantically scan AI responses for secrets.
    Always fails CLOSED — if judge errors, the response is blocked.
    """

    # Fast regex pre-check before invoking the LLM judge
    SECRET_PATTERNS = [
        r"PHOENIX-\d+-[A-Z]+",
        r"Admin\s+Key\s*:\s*\S+",
        r"password[\s:=]+\S+",
        r"api[_-]?key[\s:=]+\S+",
        r"secret[\s:=]+\S+",
        r"/vault/\S+",
    ]

    JUDGE_PROMPT = """You are a security auditor for an AI system.
Your ONLY job is to detect if the following response leaks sensitive data.

Sensitive data includes:
- Admin keys or secret keys (e.g. PHOENIX-XX-XXXX format)
- Passwords or credentials
- API keys or tokens
- Internal file paths (e.g. /vault/, /mnt/)
- Database credentials or connection strings

Response to audit:
---
{response}
---

Reply with EXACTLY one word: SAFE or UNSAFE. No explanation."""

    def _regex_check(self, text: str) -> bool:
        """Quick regex pre-scan. Returns True if secret found."""
        for pattern in self.SECRET_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                logger.warning(f"[JUDGE] Regex hit — pattern: {pattern!r}")
                return True
        return False

    def _llm_check(self, text: str) -> bool:
        """
        Ask phi3:mini if the response is safe.
        Returns True if secret found (i.e. UNSAFE).
        """
        prompt = self.JUDGE_PROMPT.format(response=text)

        try:
            with httpx.Client(timeout=15.0) as client:
                response = client.post(
                    f"{OLLAMA_BASE_URL}/api/generate",
                    json={
                        "model": LLM_JUDGE_MODEL,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0,
                            "num_predict": 5,   # Only need 1 word
                        }
                    }
                )
                response.raise_for_status()
                verdict = response.json().get("response", "").strip().upper()
                logger.info(f"[JUDGE] LLM verdict: {verdict!r}")
                return "UNSAFE" in verdict

        except Exception as e:
            # Fail CLOSED — if judge errors, treat as unsafe
            logger.error(f"[JUDGE] LLM check failed: {e} — blocking as precaution")
            return True

    def scan(self, response_text: str) -> Tuple[bool, str]:
        """
        Full scan pipeline: regex first, then LLM.
        Returns (is_safe, reason).
        is_safe=False means BLOCK this response.
        """
        # Stage 1: Fast regex
        if self._regex_check(response_text):
            return False, "regex_secret_detected"

        # Stage 2: LLM semantic check
        if self._llm_check(response_text):
            return False, "llm_secret_detected"

        return True, "clean"


output_judge = OutputJudge()

