# Utiliser une image Python officielle légère
FROM python:3.11-slim

# Définir le répertoire de travail
WORKDIR /app

# Installer les dépendances système nécessaires pour ChromaDB, la compilation et curl
RUN apt-get update && apt-get install -y build-essential curl && rm -rf /var/lib/apt/lists/*

# Copier les requirements et installer
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code source
COPY . .

# Définir le PYTHONPATH pour que Python trouve les modules
ENV PYTHONPATH=/app

# Commande par défaut
CMD ["python", "rag_pipeline.py"]