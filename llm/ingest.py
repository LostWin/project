import os
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

VECTOR_DB_PATH = "/app/chroma_db"
DOCS_PATH = "/app/documents"

def ingest():
    loader = DirectoryLoader(DOCS_PATH, glob="**/*.txt", loader_cls=TextLoader)
    documents = loader.load()
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    docs = text_splitter.split_documents(documents)
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    Chroma.from_documents(docs, embeddings, persist_directory=VECTOR_DB_PATH)
    print(f"Ingestion terminée : {len(docs)} chunks.")

if __name__ == "__main__":
    ingest()