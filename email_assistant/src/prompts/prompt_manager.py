import yaml
from langchain.prompts import ChatPromptTemplate
from pathlib import Path
import os

class PromptManager:
    """
    Manages loading and providing prompts from a YAML file.
    """
    def __init__(self, prompt_filepath: str):
        """
        Initializes the PromptManager by loading prompts from the specified file.
        """
        if not Path(prompt_filepath).is_file():
            raise FileNotFoundError(f"Prompt file not found at: {prompt_filepath}")
        
        self._prompts = self._load_prompts_from_file(prompt_filepath)


    def _load_prompts_from_file(self, filepath: str) -> dict[str, ChatPromptTemplate]:
        """Loads prompts from a YAML file and converts them to ChatPromptTemplate objects."""
        prompts = {}
        with open(filepath, 'r') as f:
            raw_prompts = yaml.safe_load(f)
        
        for name, template_str in raw_prompts.items():
            if isinstance(template_str, str):
                prompts[name] = ChatPromptTemplate.from_template(template_str)
        
        return prompts


    def get_prompt(self, prompt_name: str) -> ChatPromptTemplate:
        """
        Retrieves a prompt template by its name.        
        """
        if prompt_name not in self._prompts:
            raise KeyError(f"Prompt '{prompt_name}' not found in the prompt manager.")
        return self._prompts[prompt_name]


# Define the path to the prompts file relative to the current file's location.
PROMPTS_FILE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "prompts.yaml"))
# Create a single, shared instance of the manager
# This will be executed once when the module is first imported.
prompt_manager = PromptManager(PROMPTS_FILE_PATH)
