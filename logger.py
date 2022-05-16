# -*- coding: utf-8 -*-
import os
from loguru import logger

def initialize(config_log):
    """Initializing logger settings."""
    log_path = config_log.get('log_path')
    log_dir = os.path.dirname(log_path)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    logger.add(log_path,
               rotation=config_log.get('rotation'),
               encoding=config_log.get('encoding'),
               enqueue=True,
               retention=config_log.get('retention'))
    logger.info(f"Logging initialized: {log_path}.")
    return True
