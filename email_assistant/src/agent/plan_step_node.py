from email_assistant.src.agent.state import EmailAgentState
from langchain_core.messages import AIMessage, ToolMessage
from email_assistant.src.llm_factory import llm
from email_assistant.src.logger import logger
from email_assistant.src.utils import get_tools

def plan_step_node(state: EmailAgentState) -> EmailAgentState:
    """
    The core reasoning node for the ReAct agent.
    """
    logger.info("---NODE: PLANNING STEP---")
    # Get the current messages and email_fetcher from the state
    messages = state.get('messages', [])
    # The email_fetcher is needed to determine which tools are available
    email_fetcher = state.get('email_fetcher')
    
    tools = get_tools(email_fetcher)
    llm_with_tools = llm.bind_tools(tools)

    # Invoke the LLM with the message history and tools
    try:
        response = llm_with_tools.invoke(messages)
        logger.info(f"LLM response: {response.content}")

        # Return a dictionary where the key matches the state field.
        # The `add_messages` reducer on the `messages` field will handle appending.
        return {"messages": [response]}

    except Exception as e:
        logger.error(f"Error during planning step: {e}")
        # If the LLM fails, append an empty AIMessage. This ensures the
        # `should_continue` node receives the expected message type and can route to the end.
        error_message = AIMessage(content=f"LLM failed to respond. Error: {e}")
        return {"messages": [error_message]}
