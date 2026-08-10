import logging, sys
from logging.handlers import RotatingFileHandler

class ConsoleColorFormatter(logging.Formatter):
    COL = {
        logging.DEBUG: "\033[36m",
        logging.INFO: "\033[32m",
        logging.WARNING: "\033[33m",
        logging.ERROR: "\033[31m",
        logging.CRITICAL: "\033[35m",
    }
    RESET = "\033[0m"

    def format(self, record):
        if sys.stderr.isatty():
            prefix = self.COL.get(record.levelno, "")
            record.msg = f" {prefix}{record.getMessage()}{self.RESET}\n"
        else:
            record.msg = f" {record.getMessage()}\n"
        return super().format(record)