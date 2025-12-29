import logging
from flask_socketio import SocketIO
import json
from datetime import datetime

socketio = None
flask_app = None

class SocketIOHandler(logging.Handler):
    def emit(self, record):
        global socketio, flask_app
        if socketio and flask_app:
            log_entry = {
                'level': record.levelname,
                'message': record.getMessage(),
                'module': record.module,
                'timestamp': datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')
            }
            # Force immediate emission - don't use threads, just emit directly
            try:
                socketio.emit('log', json.dumps(log_entry), namespace='/')
            except Exception as e:
                # Fail silently if emit fails
                pass

def init_socketio(app):
    global socketio, flask_app
    # Use threading mode explicitly
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading', logger=False, engineio_logger=False)
    flask_app = app
    return socketio

def get_socketio_logger(name='socketio_logger'):
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.addHandler(SocketIOHandler())
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger