from email_assistant.src.config import config
from email_assistant.src.logger import logger

class LLMFactory:
    """A factory class for creating instances of langchain chat models."""

    @staticmethod
    def get_instance():
        """
        Creates and returns a chat model instance based on the configuration.

        Returns:
            An instance of a langchain chat model.
        
        Raises:
            ValueError: If the model provider is not supported or the API key is missing.
        """
        provider = config.model_provider
        model_name = config.llm_model_name
        temperature = config.temperature

        logger.info(f"Creating LLM instance for provider: {provider}, model: {model_name}")

        if provider == "google":
            from langchain_google_genai import ChatGoogleGenerativeAI
            if not config.google_api_key:
                raise ValueError("GOOGLE_API_KEY is not set for the 'google' provider.")
            return ChatGoogleGenerativeAI(model=model_name, temperature=temperature, google_api_key=config.google_api_key)
        
        elif provider == "openai":
            from langchain_openai import ChatOpenAI
            if not config.openai_api_key:
                raise ValueError("OPENAI_API_KEY is not set for the 'openai' provider.")
            return ChatOpenAI(model_name=model_name, temperature=temperature, openai_api_key=config.openai_api_key)

        elif provider == "anthropic":
            from langchain_anthropic import ChatAnthropic
            if not config.anthropic_api_key:
                raise ValueError("ANTHROPIC_API_KEY is not set for the 'anthropic' provider.")
            return ChatAnthropic(model_name=model_name, temperature=temperature, anthropic_api_key=config.anthropic_api_key)
        
        else:
            raise ValueError(f"Unsupported model provider: {provider}")

# Singleton instance of the LLM
llm = LLMFactory.get_instance()
logger.info("LLM singleton instance created successfully.")