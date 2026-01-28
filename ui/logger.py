import logging
import os
import sys

class MultiLineFormatter(logging.Formatter):
    def format(self, record):
        msg = record.getMessage()
        if msg is None:
            msg = ""
        lines = str(msg).splitlines() or [""]
        base = f"[{self.formatTime(record, self.datefmt)}] [{record.levelname}] "
        rendered = "\n".join(base + line for line in lines)
        if record.exc_info:
            rendered = rendered + "\n" + self.formatException(record.exc_info)
        return rendered

def setup_logger(name="automation", log_file="automation.log", level=logging.INFO):
    """
    Sets up a logger that writes to both file and console.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Avoid adding handlers multiple times
    if logger.hasHandlers():
        return logger
    
    formatter = MultiLineFormatter()
    
    # File Handler
    try:
        file_handler = logging.FileHandler(log_file, mode="w", encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"Failed to create file handler: {e}")
    
    # Stream Handler (Console)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    
    return logger

logger = setup_logger()
