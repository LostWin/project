import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

print("Testing ChromaDB and Embeddings...")
from model_loader import get_embeddings_model
from langchain_community.vectorstores import Chroma

embeddings = get_embeddings_model()
print("Embeddings loaded. Creating local Chroma in test_db/...")
db_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_db")
if os.path.exists(db_dir):
    import shutil
    shutil.rmtree(db_dir)

db = Chroma(
    persist_directory=db_dir,
    embedding_function=embeddings,
    collection_name="test_collection"
)
print("Chroma created. Adding text...")
db.add_texts(["Hello world"])
print("Text added. Querying...")
res = db.similarity_search("Hello", k=1)
print("Query success! Result:", res[0].page_content)
