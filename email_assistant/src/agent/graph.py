from langgraph.graph import StateGraph, END
from functools import partial
from email_assistant.src.agent.state import EmailAgentState
from email_assistant.src.logger import logger
from email_assistant.src.agent.nodes import (
    fetch_emails_node, 
    select_next_email_node, 
    update_run_state_node, 
    classify_email_node,
    simple_triage_node
)
from email_assistant.src.tools.email_fetcher import BaseEmailFetcher


def meeting_planner(state: EmailAgentState) -> EmailAgentState:
    logger.info("---NODE: ROUTED TO MEETING PLANNER---")
    return state

def task_planner(state: EmailAgentState) -> EmailAgentState:
    logger.info("---NODE: ROUTED TO TASK PLANNER---")
    return state

def general_planner(state: EmailAgentState) -> EmailAgentState:
    logger.info("---NODE: ROUTED TO GENERAL PLANNER---")
    return state

# Conditional Edge Functions
def has_emails_to_process(state: EmailAgentState) -> str:
    """Determines if there are more emails to process in the inbox."""
    logger.info("---COND: CHECKING FOR MORE EMAILS---")
    current_index = state.get('current_email_index', 0)
    inbox_size = len(state.get('inbox', []))
    
    if current_index < inbox_size:
        logger.info(f"Emails to process. Current index: {current_index}, Inbox size: {inbox_size}")
        return "continue"
    
    logger.info("No more emails to process.")
    return "end"

def route_after_classification(state: EmailAgentState) -> str:
    """Routes to the appropriate specialized planner based on classification."""
    classification = state.get('classification')
    logger.info(f"---COND: ROUTING BASED ON CLASSIFICATION: {classification}---")
    
    if classification == "meeting":
        return "meeting_planner"
    elif classification == "task":
        return "task_planner"
    elif classification in ["spam", "newsletter"]:
        return "simple_triage"
    else: # "priority", "invoice", "other", or None
        return "general_planner"

# Graph Definition
def build_agent_workflow_graph(email_fetcher: BaseEmailFetcher = None) -> StateGraph:
    """
    Builds and compiles the LangGraph for the email agent.
    """
    workflow = StateGraph(EmailAgentState)

    fetch_emails_node_runnable = partial(fetch_emails_node, email_fetcher=email_fetcher)
    # Add nodes
    workflow.add_node("fetch_emails", fetch_emails_node_runnable)
    workflow.add_node("select_next_email", select_next_email_node)
    workflow.add_node("classify_email", classify_email_node)
    workflow.add_node("meeting_planner", meeting_planner)
    workflow.add_node("task_planner", task_planner)
    workflow.add_node("general_planner", general_planner)
    workflow.add_node("simple_triage", simple_triage_node)
    workflow.add_node("update_run_state", update_run_state_node)

    # Set the entry point
    workflow.set_entry_point("fetch_emails")

    # Add core edges
    workflow.add_conditional_edges(
        "fetch_emails",
        has_emails_to_process,
        {
            "continue": "select_next_email",
            "end": END
        }
    )
    workflow.add_edge("select_next_email", "classify_email")

    # Add classification routing
    workflow.add_conditional_edges(
        "classify_email",
        route_after_classification,
        {
            "meeting_planner": "meeting_planner",
            "task_planner": "task_planner",
            "general_planner": "general_planner",
            "simple_triage": "simple_triage"
        }
    )

    # Edges from planners back to the main loop
    workflow.add_edge("meeting_planner", "update_run_state")
    workflow.add_edge("task_planner", "update_run_state")
    workflow.add_edge("general_planner", "update_run_state")
    workflow.add_edge("simple_triage", "update_run_state")

    # After a run, loop back to check for more emails
    workflow.add_edge("update_run_state", "fetch_emails")

    # Compile the graph
    agent_workflow_graph = workflow.compile()
    logger.info("Graph compiled successfully!")
    return agent_workflow_graph


if __name__ == '__main__':
    # This allows running the file directly to build and visualize the graph
    agent_graph = build_agent_workflow_graph()        
    try:
        agent_graph.get_graph().draw_mermaid_png(output_file_path="rag_agent_graph.png")
        logger.info("Saved graph visualization to rag_agent_graph.png")
    except Exception as e:
        logger.warning(f"Could not save graph visualization: {e}")
