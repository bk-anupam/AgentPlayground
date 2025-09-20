import logging
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get log level from environment variable, default to INFO
log_level_name = os.getenv('LOG_LEVEL', 'INFO').upper()
log_level = logging.getLevelName(log_level_name)

if not isinstance(log_level, int):
    log_level = logging.INFO

log_format = '%(asctime)s-[%(module)s.%(funcName)s:%(lineno)d]-%(levelname)s - %(message)s'

logger = logging.getLogger("email_assistant")
logger.setLevel(log_level)

if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(log_format))
    logger.addHandler(console_handler)