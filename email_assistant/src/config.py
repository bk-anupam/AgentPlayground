import os
from dotenv import load_dotenv, find_dotenv
from email_assistant.src.logger import logger

dotenv_path = find_dotenv()
load_dotenv(dotenv_path)  # This loads the variables from .env

class Config:
    """A centralized configuration class to load and manage settings from environment variables."""
    def __init__(self):
        """Initializes the configuration by loading values from the environment."""
        self.max_emails_to_fetch = int(os.getenv('MAX_EMAILS_TO_FETCH', 5))            
        self.model_provider = os.getenv('MODEL_PROVIDER', 'google').lower()
        self.llm_model_name = os.getenv('LLM_MODEL_NAME', 'gemini-2.5-flash')
        self.temperature = float(os.getenv('TEMPERATURE', 0))        
        self.google_api_key = os.getenv('GOOGLE_API_KEY')
        self.max_fetch_cycles = int(os.getenv('MAX_FETCH_CYCLES', 2))
        

# Create a singleton instance of the Config class to be used throughout the application.
config = Config()
logger.info("Configuration singleton instance loaded successfully.")