from typing import TypedDict, List, Dict, Any


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
    # e.g., ["send_email", "create_event"]
    approval_required_for: List[str]