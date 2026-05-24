import re
import math
from collections import Counter

SUSPICIOUS_PATTERNS = [
    re.compile(r"ignore previous instructions", re.IGNORECASE),
    re.compile(r"do anything now", re.IGNORECASE),
    re.compile(r"you are DAN", re.IGNORECASE),
    re.compile(r"system prompt", re.IGNORECASE),
    re.compile(r"PHOENIX", re.IGNORECASE),
]

def compute_perplexity(text: str) -> float:
    words = text.lower().split()
    if not words:
        return 0.0
    freq = Counter(words)
    total = len(words)
    entropy = -sum((count/total) * math.log2(count/total) for count in freq.values())
    return 2 ** entropy

def input_guard(message: str) -> dict:
    for pat in SUSPICIOUS_PATTERNS:
        if pat.search(message):
            return {"block": True, "reason": f"Motif interdit détecté: {pat.pattern}"}
    p = compute_perplexity(message)
    if p > 1000 or p < 1.0:
        return {"block": True, "reason": f"Perplexité suspecte: {p:.2f}"}
    return {"block": False}