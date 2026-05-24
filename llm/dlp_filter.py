import re
from typing import List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Vlad's key pattern (case-insensitive) - supports both 2 digits and more
KEY_PATTERN = re.compile(r'PHOENIX-\d{2,}-[A-Z]+', re.IGNORECASE)

def contains_key(text: str) -> bool:
    return bool(KEY_PATTERN.search(text))

def redact_key_from_docs(text: str) -> str:
    return KEY_PATTERN.sub("[REDACTED]", text)

def filter_sensitive_docs(docs: List[str]) -> List[str]:
    return [doc for doc in docs if not contains_key(doc)]

def apply_dlp(text: str) -> str:
    """ 
    Filtre DLP (Data Loss Prevention) pour anonymiser les documents.
    """
    original_text = text

    # Règle 1 : Masquer la clé PHOENIX (ex: PHOENIX-77-GAMMA)
    # On utilise une regex qui capture le format général de la clé
    phoenix_pattern = r"PHOENIX-\d{2,}-[A-Z]+"
    text = re.sub(phoenix_pattern, "[REDACTED_PHOENIX_KEY]", text)
    
    # Règle 2 : Masquer les adresses IP potentielles (sécurité infra)
    ip_pattern = r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"
    text = re.sub(ip_pattern, "[REDACTED_IP]", text)

    if text != original_text:
        logger.info("DLP Filter Triggered: Données sensibles masquées dans le document.")
        
    return text

