import logging
from flask_socketio import SocketIO
import json
from datetime import datetime

socketio = None

class SocketIOHandler(logging.Handler):
    def emit(self, record):
        global socketio
        if socketio:
            log_entry = {
                'level': record.levelname,
                'message': record.getMessage(),
                'module': record.module,
                'timestamp': datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')
            }
            socketio.emit('log', json.dumps(log_entry))

def init_socketio(app):
    global socketio
    socketio = SocketIO(app, cors_allowed_origins="*")
    return socketio

def get_socketio_logger(name='socketio_logger'):
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.addHandler(SocketIOHandler())
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger