import yaml
from langchain.prompts import PromptTemplate
from langchain_core.prompts import ChatPromptTemplate
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


    def _load_prompts_from_file(self, file_path: str) -> dict[str, str]:
        """Loads prompts from a YAML file and converts them to PromptTemplate objects."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                prompts = yaml.safe_load(f)
            if not isinstance(prompts, dict):
                print(f"Warning: Prompts file '{file_path}' did not load as a dictionary.")
                return {} 
            return prompts
        except FileNotFoundError:
            print(f"Error: Prompts file not found at '{file_path}'")
            return {} 
        except yaml.YAMLError as e:
            print(f"Error parsing YAML file '{file_path}': {e}")
            return {} 
        except Exception as e:
            print(f"An unexpected error occurred while loading prompts from '{file_path}': {e}")
            return {} 


    def get_prompt(self, prompt_name: str) -> str:
        """
        Retrieves a prompt template by its name.        
        """
        if prompt_name not in self._prompts:
            raise KeyError(f"Prompt '{prompt_name}' not found in the prompt manager.")
        return self._prompts[prompt_name]


    def get_meeting_planner_chat_prompt(self) -> list:
        """
        Returns the chat prompt template for the meeting planner.
        """
        system_prompt_template = self.get_prompt("CALENDAR_EVENT_SYSTEM_PROMPT")
        human_prompt_template = self.get_prompt("CALENDAR_EVENT_HUMAN_PROMPT")
        return ChatPromptTemplate.from_messages([
            ("system", system_prompt_template),
            ("human", human_prompt_template)
        ])


    def get_task_planner_chat_prompt(self) -> list:
        """
        Returns the chat prompt template for the task planner.
        """
        system_prompt_template = self.get_prompt("TASK_PLANNER_SYSTEM_PROMPT")
        human_prompt_template = self.get_prompt("TASK_PLANNER_HUMAN_PROMPT")
        return ChatPromptTemplate.from_messages([
            ("system", system_prompt_template),
            ("human", human_prompt_template)
        ])


    def get_invoice_planner_chat_prompt(self) -> list:
        """
        Returns the chat prompt template for the invoice planner.
        """
        system_prompt_template = self.get_prompt("INVOICE_PLANNER_SYSTEM_PROMPT")
        human_prompt_template = self.get_prompt("INVOICE_PLANNER_HUMAN_PROMPT")
        return ChatPromptTemplate.from_messages([
            ("system", system_prompt_template),
            ("human", human_prompt_template)
        ])


    def get_general_planner_chat_prompt(self) -> list:
        """
        Returns the chat prompt template for the general planner.
        """
        system_prompt_template = self.get_prompt("GENERAL_PLANNER_SYSTEM_PROMPT")
        human_prompt_template = self.get_prompt("GENERAL_PLANNER_HUMAN_PROMPT")
        return ChatPromptTemplate.from_messages([
            ("system", system_prompt_template),
            ("human", human_prompt_template)
        ])

# Define the path to the prompts file relative to the current file's location.
PROMPTS_FILE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "prompts.yaml"))
# Create a single, shared instance of the manager
# This will be executed once when the module is first imported.
prompt_manager = PromptManager(PROMPTS_FILE_PATH)
