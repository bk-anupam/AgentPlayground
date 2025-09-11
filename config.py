import os
from dotenv import load_dotenv

# Load environment variables from a .env file for local development.
# This line does nothing if the .env file is not found.
load_dotenv()

class Config:
    """
    Configuration class for the application.
    Reads settings from environment variables for better security and flexibility.
    """
    # Read boolean value for DEV_MODE, defaulting to True if not set.
    DEV_MODE: bool = os.getenv('DEV_MODE', 'True').lower() in ('true', '1', 't')

    # Read API keys from environment variables. They will be None if not set.
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY")
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY")

    # Read the model name, providing a default value.
    MODEL_NAME: str = os.getenv("MODEL_NAME", "gemini-2.5-flash")

    # Fail fast if required secrets are not configured.
    if not TAVILY_API_KEY or not GOOGLE_API_KEY:
        raise ValueError("TAVILY_API_KEY and GOOGLE_API_KEY must be set in the environment or a .env file.")