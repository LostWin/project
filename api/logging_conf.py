import logging
from pythonjsonlogger import jsonlogger
import sys
from elasticsearch_logger import setup_elasticsearch_logging

def setup_logging():
    formatter = jsonlogger.JsonFormatter(
        fmt='%(asctime)s %(name)s %(levelname)s %(message)s'
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    es_handler = setup_elasticsearch_logging()
    es_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = []
    root.addHandler(console_handler)
    root.addHandler(es_handler)
    root.setLevel(logging.INFO)
    logging.getLogger('elastic_transport.transport').setLevel(logging.WARNING)