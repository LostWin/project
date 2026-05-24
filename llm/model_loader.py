import os
from langchain_community.chat_models import ChatOllama
from langchain_huggingface import HuggingFaceEmbeddings

def get_embeddings_model():
    """Charge le modèle d'embeddings localement (gratuit et rapide)."""
    # all-MiniLM-L6-v2 est léger et très performant pour ce type de tâche
    return HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

def get_llm():
    """Charge le modèle local via Ollama."""
    
    model_name = os.getenv("LLM_MODEL", "mistral")
    
    # Déterminer l'URL de base d'Ollama (Docker vs Local)
    if os.path.exists('/.dockerenv'):
        base_url = "http://ollama:11434"
    else:
        base_url = "http://localhost:11434"

    return ChatOllama(
        model=model_name,
        temperature=0.1,
        base_url=base_url
    )