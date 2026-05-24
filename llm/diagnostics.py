import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

print("Testing model loader...")
from model_loader import get_embeddings_model
emb = get_embeddings_model()
print("Model loaded. Testing query embedding...")
res = emb.embed_query("hello")
print("Successfully embedded query. Length of vector:", len(res))
