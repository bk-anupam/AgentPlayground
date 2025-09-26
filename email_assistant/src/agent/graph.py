from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from functools import partial
from email_assistant.src.agent.state import EmailAgentState
from email_assistant.src.logger import logger
from email_assistant.src.config import config
from email_assistant.src.agent.nodes import (
    fetch_emails_node, 
    select_next_email_node, 
    update_run_state_node, 
    classify_email_node,
    simple_triage_node
)
from email_assistant.src.agent.planner_nodes import (
    meeting_planner,
    task_planner,
    invoice_planner,
    general_planner
)
from email_assistant.src.agent.plan_step_node import plan_step_node
from email_assistant.src.agent.tools import placeholder_tool
from email_assistant.src.tools.email_fetcher import BaseEmailFetcher
from email_assistant.src.tools.outlook_fetcher import OutlookFetcher
from email_assistant.src.tools.calendar_tools import OutlookCalendarTool
from langchain_core.runnables.graph_png import PngDrawer
from email_assistant.src.utils import get_tools

def check_for_emails_node(state: EmailAgentState) -> EmailAgentState:
    """Dummy node to serve as the entry point for the email processing loop."""
    return state


# Conditional Edge Functions
def did_fetch_emails(state: EmailAgentState) -> str:
    """
    Checks if the fetch_emails_node actually retrieved any emails.
    """
    logger.info("---COND: CHECKING IF EMAILS WERE FETCHED---")
    if state.get('inbox') and len(state.get('inbox')) > 0:
        logger.info("Emails fetched successfully. Starting processing.")
        return "continue"
    else:
        logger.info("No new emails found. Ending workflow.")
        return "end"


def has_emails_to_process(state: EmailAgentState) -> str:
    """
    Determines the next step based on batch status and fetch cycle limit.
    """
    logger.info("---COND: CHECKING FOR MORE EMAILS---")
    current_index = state.get('current_email_index', 0)
    inbox_size = len(state.get('inbox', []))

    # Check if there are emails left in the current batch
    if current_index < inbox_size:
        logger.info(f"Emails to process in batch. Current index: {current_index}, Inbox size: {inbox_size}")
        return "continue"

    # If batch is finished, check if we should fetch a new one
    fetch_emails_run_count = state.get('fetch_emails_run_count', 0)
    if fetch_emails_run_count < config.max_fetch_cycles:
        logger.info(f"Batch finished. Fetch count {fetch_emails_run_count}/{config.max_fetch_cycles}. Fetching new batch.")
        return "fetch_new"
    else:
        logger.info(f"Batch finished and fetch limit of {config.max_fetch_cycles} reached. Ending workflow.")
        return "end_workflow"


def route_after_classification(state: EmailAgentState) -> str:
    """
    Routes to the appropriate specialized planner based on classification.
    """
    classification = state.get('classification')
    logger.info(f"---COND: ROUTING BASED ON CLASSIFICATION: {classification}---")
    
    if classification == "meeting":
        return "meeting_planner"
    elif classification == "task":
        return "task_planner"
    elif classification == "invoice":
        return "invoice_planner"
    elif classification in ["spam", "newsletter"]:
        return "simple_triage"
    else: # "priority", "other", or None
        return "general_planner"


def should_continue(state: EmailAgentState) -> str:
    """Determines whether to continue the reasoning loop or finish."""
    logger.info("---COND: CHECKING FOR TOOL CALLS---")
    if not state.get('messages'):
        return "end_of_email"
    last_message = state['messages'][-1]
    # Check if the last message is an AIMessage and if it has tool calls
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        logger.info("Tool call detected, routing to tool execution.")
        return "execute_tools"
    logger.info("No tool call, finishing email processing.")
    return "end_of_email"


def build_agent_workflow_graph(email_fetcher: BaseEmailFetcher = None) -> StateGraph:
    """
    Builds and compiles the LangGraph workflow for the email agent.
    """
    workflow = StateGraph(EmailAgentState)
    # instantiate nodes with partial dependencies
    fetch_emails_node_runnable = partial(fetch_emails_node, email_fetcher=email_fetcher)
    
    # Define tools
    tools = get_tools(email_fetcher)    
    # Add nodes
    workflow.add_node("fetch_emails", fetch_emails_node_runnable)
    workflow.add_node("check_for_emails", check_for_emails_node)
    workflow.add_node("select_next_email", select_next_email_node)
    workflow.add_node("classify_email", classify_email_node)
    workflow.add_node("simple_triage", simple_triage_node)
    workflow.add_node("update_run_state", update_run_state_node)
    # Planner nodes
    workflow.add_node("meeting_planner", meeting_planner)
    workflow.add_node("task_planner", task_planner)
    workflow.add_node("invoice_planner", invoice_planner)
    workflow.add_node("general_planner", general_planner)
    # Core reasoning nodes
    workflow.add_node("plan_step", plan_step_node)
    workflow.add_node("execute_tools", ToolNode(tools))
    # Set the entry point
    workflow.set_entry_point("fetch_emails")
    # Core Graph Edges
    workflow.add_conditional_edges(
        "fetch_emails",
        did_fetch_emails,
        {
            "continue": "check_for_emails", 
            "end": END
        }
    )
    workflow.add_conditional_edges(
        "check_for_emails",
        has_emails_to_process,
        {
            "continue": "select_next_email", 
            "fetch_new": "fetch_emails", 
            "end_workflow": END
        }
    )
    workflow.add_edge("select_next_email", "classify_email")
    # Routing after classification
    workflow.add_conditional_edges(
        "classify_email",
        route_after_classification,
        {
            "meeting_planner": "meeting_planner",
            "task_planner": "task_planner",
            "invoice_planner": "invoice_planner",
            "general_planner": "general_planner",
            "simple_triage": "simple_triage"
        }
    )
    # Edges from simple triage back to the main loop
    workflow.add_edge("simple_triage", "update_run_state")
    # Connect planners to the main reasoning step
    workflow.add_edge("meeting_planner", "plan_step")
    workflow.add_edge("task_planner", "plan_step")
    workflow.add_edge("invoice_planner", "plan_step")
    workflow.add_edge("general_planner", "plan_step")
    # The core reasoning loop
    workflow.add_conditional_edges(
        "plan_step",
        should_continue,
        {
            "execute_tools": "execute_tools",
            "end_of_email": "update_run_state"
        }
    )
    workflow.add_edge("execute_tools", "plan_step")
    # After processing an email, loop back to check for the next one
    workflow.add_edge("update_run_state", "check_for_emails")
    # Compile the graph
    agent_workflow_graph = workflow.compile()
    logger.info("Email agent workflow graph compiled successfully!")
    return agent_workflow_graph


def draw_agent_graph(email_agent):
    drawable_graph = email_agent.get_graph()
    drawer = PngDrawer()
    drawer.draw(drawable_graph, "email_agent_workflow_graph.png")
    logger.info("Graph visualization saved to email_agent_workflow_graph.png")


if __name__ == '__main__':
    # Add this block to verify the GCP identity on startup
    from email_assistant.src.utils import get_gcp_identity
    gcp_identity = get_gcp_identity()
    logger.info(f"Agent is executing with GCP identity: {gcp_identity}")
    email_fetcher = OutlookFetcher()
    email_agent = build_agent_workflow_graph(email_fetcher=email_fetcher)        
    draw_agent_graph(email_agent)
    # Initialize the agent state with empty/default values
    initial_state: EmailAgentState = {
        "fetch_emails_run_count": 0,
        "inbox": [],
        "current_email_index": 0,
        "processed_email_ids": [],
        "current_email": None,
        "classification": None,
        "summary": None,
        "extracted_data": None,
        "messages": [],
        "user_preferences": None,
        "email_actions_client": None
    }
    # Run the graph with the initial state
    final_state = email_agent.invoke(initial_state, config={"recursion_limit": 50})
    logger.info("Final Agent State after run:")
    logger.info(final_state)
