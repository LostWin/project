import logging
import threading
from elasticsearch import Elasticsearch
import os
import json

class ElasticsearchHandler(logging.Handler):
    """Envoie les logs à Elasticsearch dans un thread séparé."""
    def __init__(self, hosts, index):
        super().__init__()
        self.client = Elasticsearch(hosts)
        self.index = index

    def emit(self, record):
        try:
            log_entry = self.format(record)
            doc = json.loads(log_entry)
            # Envoi dans un thread pour ne pas bloquer l'API
            t = threading.Thread(target=self._send, args=(doc,))
            t.daemon = True
            t.start()
        except Exception as e:
            import sys
            print(f"ES error: {e}", file=sys.stderr)

    def _send(self, doc):
        try:
            self.client.index(index=self.index, body=doc)
        except Exception as e:
            import sys
            print(f"ES send error: {e}", file=sys.stderr)

def setup_elasticsearch_logging():
    es_host = os.getenv("ELASTICSEARCH_HOST", "http://elasticsearch:9200")
    index_name = "citadel-logs"

    es_handler = ElasticsearchHandler(hosts=es_host, index=index_name)
    formatter = logging.Formatter('%(message)s')
    es_handler.setFormatter(formatter)

    # Retourne directement le handler, plus de queue
    return es_handler