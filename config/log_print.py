import logging
from datetime import datetime


def log(name, message, log_type='warning', only_console=False):
    if only_console:
        return
    log = logging.getLogger(name)
    if log_type == 'warning':
        log.warning(message)
    elif log_type == "error":
        log.error(message)
    elif log_type == "critical":
        log.critical(message)
    else:
        log.warning(message)
    return True
