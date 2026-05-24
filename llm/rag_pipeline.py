import os
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from langchain_community.vectorstores import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

from model_loader import get_llm, get_embeddings_model
from dlp_filter import apply_dlp, contains_key, redact_key_from_docs
from system_prompt import SYSTEM_PROMPT

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CitadelRAG:
    def __init__(self, persist_directory=None):
        self.embeddings = get_embeddings_model()
        self.llm = get_llm()
        
        if persist_directory is None:
            # Si le répertoire /app/chroma_db existe, on l'utilise (contexte Docker)
            # Sinon on utilise par défaut vectordb/persist (contexte local)
            if os.path.exists("/app/chroma_db"):
                self.persist_directory = "/app/chroma_db"
            else:
                self.persist_directory = "vectordb/persist"
        else:
            self.persist_directory = persist_directory
            
        self.vector_store = self._init_vector_store()

    def _init_vector_store(self):
        """Initialise ou charge ChromaDB."""
        return Chroma(
            persist_directory=self.persist_directory, 
            embedding_function=self.embeddings,
            collection_name="citadel_internal"
        )

    def add_documents(self, texts: list[str], metadatas: list[dict] = None):
        """Passe les textes dans le DLP puis les indexe."""
        clean_texts = [apply_dlp(text) for text in texts]
        self.vector_store.add_texts(texts=clean_texts, metadatas=metadatas)
        print(f"{len(clean_texts)} documents ajoutés avec succès.")

    def query(self, question: str, prompt_template: str = SYSTEM_PROMPT) -> dict:
        """Pipeline d'inférence RAG avec Instruction Sandwich et filtrage de sécurité."""
        
        # 1. Récupération (Retrieval)
        retriever = self.vector_store.as_retriever(search_kwargs={"k": 5})
        docs = retriever.invoke(question)
        
        # Filtrage de sécurité : éliminer les documents contenant la clé d'administration
        safe_docs = [doc for doc in docs if not contains_key(doc.page_content)]
        context = "\n\n".join([doc.page_content for doc in safe_docs])
        
        # 2. Construction du Prompt (Instruction Sandwich)
        # Les consignes de sécurité sont répétées à la toute fin du prompt
        prompt = ChatPromptTemplate.from_template(prompt_template)
        
        # 3. Chaîne d'exécution LangChain
        chain = (
            {"context": lambda x: context, "question": RunnablePassthrough()}
            | prompt
            | self.llm
            | StrOutputParser()
        )
        
        answer = chain.invoke(question)
        
        return {
            "answer": answer,
            "sources": [doc.page_content for doc in safe_docs]
        }

# --- Service FastAPI (Intégration du travail de Vlad) ---
app = FastAPI(title="CITADEL-Y LLM Service", version="1.0.0")
rag = CitadelRAG()

class QueryRequest(BaseModel):
    message: str

@app.post("/query")
async def handle_query(req: QueryRequest):
    user_question = req.message
    try:
        res = rag.query(user_question)
        raw_answer = res["answer"]
        source_docs = res["sources"]
        
        # Masquage ultime de sécurité sur la réponse générée
        safe_answer = redact_key_from_docs(raw_answer)
        
        return {
            "response": safe_answer, 
            "sources_count": len(source_docs)
        }
    except Exception as e:
        logger.error(f"Erreur lors du traitement de la requête: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- Pour tester le fichier en standalone ou démarrer le serveur ---
if __name__ == "__main__":
    import uvicorn
    # Si exécuté directement, on lance le serveur FastAPI
    uvicorn.run(app, host="0.0.0.0", port=8001)
