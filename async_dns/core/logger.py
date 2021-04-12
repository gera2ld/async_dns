import logging
import os

logger = logging.getLogger(__package__)
logger.setLevel(os.environ.get('LOGLEVEL') or 'INFO')
handler = logging.StreamHandler()
fmt = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
handler.setFormatter(fmt)
logger.addHandler(handler)
