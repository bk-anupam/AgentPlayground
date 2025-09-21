from typing import TypedDict, List, Annotated, Sequence, Literal, Dict, Any, Optional
from langchain_core.messages import BaseMessage


class Email(TypedDict):
    """A structured representation of a single email."""
    id: str
    sender: str
    subject: str
    body: str
    received_at: str


class UserPreferences(TypedDict):
    """User-defined rules and settings for the agent."""
    priority_senders: List[str]
    auto_archive_rules: Dict[str, Any]
    approval_required_for: List[str]  # e.g., ["send_email", "create_event"]


class EmailAgentState(TypedDict):
    """
    The central state for the email agent. It's passed between nodes in the graph,
    accumulating data as the agent processes emails.
    """
    # --- Batch Processing State ---
    # The list of emails fetched for this run
    inbox: List[Email]
    # The index of the email currently being processed            
    current_email_index: int            
    # IDs of emails successfully processed in this run
    processed_email_ids: List[str]      

    # --- Per-Email Processing State (cleared for each new email) ---
    # The email object currently under analysis
    current_email: Optional[Email] 
    classification: Optional[Literal["priority", "meeting", "task", "invoice", "newsletter", "spam", "other"]]
    summary: Optional[str]
    # For invoices, contact info, etc.
    extracted_data: Optional[Dict[str, Any]]      

    # --- Core Reasoning State ---
    messages: Annotated[Sequence[BaseMessage], "The conversation history for the current email"]    
    # User-defined rules and settings
    user_preferences: UserPreferences   
