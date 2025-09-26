from langchain_core.messages import SystemMessage, HumanMessage
from email_assistant.src.agent.state import EmailAgentState
from email_assistant.src.logger import logger
from email_assistant.src.prompts.prompt_manager import prompt_manager
from datetime import datetime

# --- Specialist Planner Nodes ---

def meeting_planner(state: EmailAgentState) -> dict:
    """
    Planner node for meeting-related emails.
    """
    logger.info("---NODE: MEETING PLANNER---")    
    current_email = state.get('current_email')
    if not current_email:
        logger.warning("Meeting planner called without a current email in state.")
        return {}

    # The SystemMessage defines the agent's role and tools.
    system_prompt_template = prompt_manager.get_prompt("CALENDAR_EVENT_SYSTEM_PROMPT")
    system_message = SystemMessage(
        content=system_prompt_template.format(current_date=datetime.now().strftime("%Y-%m-%d"))
    )    

    # The HumanMessage provides the specific data (the email) for the agent to act on.
    human_message_template = prompt_manager.get_prompt("CALENDAR_EVENT_HUMAN_PROMPT")
    human_message_content = human_message_template.format(
        email_subject=current_email.get('subject', ''),
        sender=current_email.get('sender', ''),
        email_body=current_email.get('body', '')
    )    
    human_message = HumanMessage(content=human_message_content)

    # The planner's job is to prepare the initial messages for the reasoning loop.
    return {"messages": [system_message, human_message]}


def task_planner(state: EmailAgentState) -> dict:
    """Planner node for task-related emails."""
    logger.info("---NODE: TASK PLANNER---")
    
    current_email = state.get('current_email')
    if not current_email:
        logger.warning("Task planner called without a current email in state.")
        return {}

    system_prompt_template = prompt_manager.get_prompt("TASK_PLANNER_SYSTEM_PROMPT")
    system_message = SystemMessage(content=system_prompt_template.format())

    human_message_template = prompt_manager.get_prompt("TASK_PLANNER_HUMAN_PROMPT")
    human_message_content = human_message_template.format(
        email_subject=current_email.get('subject', ''),
        sender=current_email.get('sender', ''),
        email_body=current_email.get('body', '')
    )
    human_message = HumanMessage(content=human_message_content)

    return {"messages": [system_message, human_message]}


def invoice_planner(state: EmailAgentState) -> dict:
    """Planner node for invoice-related emails."""
    logger.info("---NODE: INVOICE PLANNER---")
    
    current_email = state.get('current_email')
    if not current_email:
        logger.warning("Invoice planner called without a current email in state.")
        return {}

    system_prompt_template = prompt_manager.get_prompt("INVOICE_PLANNER_SYSTEM_PROMPT")
    system_message = SystemMessage(content=system_prompt_template.format())

    human_message_template = prompt_manager.get_prompt("INVOICE_PLANNER_HUMAN_PROMPT")
    human_message_content = human_message_template.format(
        email_subject=current_email.get('subject', ''),
        sender=current_email.get('sender', ''),
        email_body=current_email.get('body', '')
    )
    human_message = HumanMessage(content=human_message_content)

    return {"messages": [system_message, human_message]}


def general_planner(state: EmailAgentState) -> dict:
    """A general-purpose planner for other email types."""
    logger.info("---NODE: GENERAL PLANNER---")
    
    current_email = state.get('current_email')
    if not current_email:
        logger.warning("General planner called without a current email in state.")
        return {}

    system_prompt_template = prompt_manager.get_prompt("GENERAL_PLANNER_SYSTEM_PROMPT")
    system_message = SystemMessage(content=system_prompt_template.format())

    human_message_template = prompt_manager.get_prompt("GENERAL_PLANNER_HUMAN_PROMPT")
    human_message_content = human_message_template.format(
        email_subject=current_email.get('subject', ''),
        sender=current_email.get('sender', ''),
        email_body=current_email.get('body', '')
    )
    human_message = HumanMessage(content=human_message_content)

    return {"messages": [system_message, human_message]}
