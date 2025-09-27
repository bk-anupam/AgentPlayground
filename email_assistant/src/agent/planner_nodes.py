from langchain_core.messages import BaseMessage
from email_assistant.src.agent.state import EmailAgentState
from email_assistant.src.logger import logger
from email_assistant.src.prompts.prompt_manager import prompt_manager
from datetime import datetime

# --- Specialist Planner Nodes ---

def meeting_planner(state: EmailAgentState) -> dict[str, list[BaseMessage]]:
    """
    Planner node for meeting-related emails.
    """
    logger.info("---NODE: MEETING PLANNER---")    
    current_email = state.get('current_email')
    if not current_email:
        logger.warning("Meeting planner called without a current email in state.")
        return {}

    # Use the dedicated method to get the combined chat prompt template
    chat_prompt_template = prompt_manager.get_meeting_planner_chat_prompt()
    
    # Format the template with all required variables to get the list of messages
    messages = chat_prompt_template.format_messages(
        current_date=datetime.now().strftime("%Y-%m-%d"),
        email_subject=current_email.get('subject', ''),
        sender=current_email.get('sender', ''),
        email_body=current_email.get('body', '')
    )
    # The planner's job is to prepare the initial messages for the reasoning loop.
    return {"messages": messages}


def task_planner(state: EmailAgentState) -> dict:
    """Planner node for task-related emails."""
    logger.info("---NODE: TASK PLANNER---")
    
    current_email = state.get('current_email')
    if not current_email:
        logger.warning("Task planner called without a current email in state.")
        return {}

    chat_prompt_template = prompt_manager.get_task_planner_chat_prompt()
    messages = chat_prompt_template.format_messages(
        email_subject=current_email.get('subject', ''),
        sender=current_email.get('sender', ''),
        email_body=current_email.get('body', '')
    )

    return {"messages": messages}


def invoice_planner(state: EmailAgentState) -> dict:
    """Planner node for invoice-related emails."""
    logger.info("---NODE: INVOICE PLANNER---")
    
    current_email = state.get('current_email')
    if not current_email:
        logger.warning("Invoice planner called without a current email in state.")
        return {}

    chat_prompt_template = prompt_manager.get_invoice_planner_chat_prompt()
    messages = chat_prompt_template.format_messages(
        email_subject=current_email.get('subject', ''),
        sender=current_email.get('sender', ''),
        email_body=current_email.get('body', '')
    )

    return {"messages": messages}


def general_planner(state: EmailAgentState) -> dict:
    """A general-purpose planner for other email types."""
    logger.info("---NODE: GENERAL PLANNER---")
    
    current_email = state.get('current_email')
    if not current_email:
        logger.warning("General planner called without a current email in state.")
        return {}

    chat_prompt_template = prompt_manager.get_general_planner_chat_prompt()
    messages = chat_prompt_template.format_messages(
        email_subject=current_email.get('subject', ''),
        sender=current_email.get('sender', ''),
        email_body=current_email.get('body', '')
    )

    return {"messages": messages}
