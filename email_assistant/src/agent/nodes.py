from email_assistant.src.tools.email_fetcher import BaseEmailFetcher
from email_assistant.src.agent.state import EmailAgentState, UserPreferences
from email_assistant.src.logger import logger
from email_assistant.src.config import config
from email_assistant.src.llm_factory import llm

def load_user_preferences() -> UserPreferences:
    """Load user preferences with default values. This can be extended to load from config files or database."""
    return UserPreferences(
        # Empty list - can be populated from config
        priority_senders=[],  
        # Empty dict - can be populated with rules
        auto_archive_rules={},  
        # Default critical actions
        approval_required_for=["send_email", "create_event", "create_task"]  
    )


# Node Functions
def fetch_emails(
        state: EmailAgentState,
        email_fetcher: BaseEmailFetcher = None
) -> EmailAgentState:
    """Fetches unread emails using the OutlookFetcher and initializes the state."""
    logger.info("---NODE: FETCHING EMAILS---")
    logger.info(f"Connecting to Outlook and fetching up to {config.max_emails_to_fetch} unread emails...")

    # Initialize user preferences if not already set
    if 'user_preferences' not in state or state['user_preferences'] is None:
        state['user_preferences'] = load_user_preferences()
        logger.info("Initialized user preferences in agent state")

    try:
        fetched_emails = email_fetcher.get_emails(max_count=config.max_emails_to_fetch)
    except Exception as e:
        logger.error("Failed to fetch emails: %s", e)
        fetched_emails = []

    # Update the state
    state['inbox'] = fetched_emails
    state['current_email_index'] = 0
    # Reset for the new batch
    state['processed_email_ids'] = [] 
    logger.info(f"Fetched {len(fetched_emails)} emails.")
    return state


def select_next_email(state: EmailAgentState) -> EmailAgentState:
    """Selects the next email from the inbox and prepares the state for processing."""
    logger.info("---NODE: SELECTING NEXT EMAIL---")
    current_index = state.get('current_email_index', 0)
    inbox = state.get('inbox', [])
    if current_index < len(inbox):
        # Set the current email
        state['current_email'] = inbox[current_index]
        state['current_email_index'] = current_index + 1
        # Clear per-email state fields for the new email
        state['classification'] = None
        state['summary'] = None
        state['extracted_data'] = None
        state['messages'] = []  # Reset conversation history for new email
        logger.info(f"Selected email {current_index + 1}/{len(inbox)}: {state['current_email']['subject']}")
    else:
        logger.warning("No more emails to process, but select_next_email was called")

    return state


def update_run_state(state: EmailAgentState) -> EmailAgentState:
    """Updates the run state after processing an email - clears per-email fields and tracks processed emails."""
    logger.info("---NODE: UPDATING RUN STATE---")

    # Add the current email ID to processed list if it exists
    current_email = state.get('current_email')
    if current_email and 'id' in current_email:
        processed_ids = state.get('processed_email_ids', [])
        if current_email['id'] not in processed_ids:
            processed_ids.append(current_email['id'])
            state['processed_email_ids'] = processed_ids
            logger.info(f"Added email ID {current_email['id']} to processed list")

    # Clear per-email fields for the next iteration
    state['current_email'] = None
    state['classification'] = None
    state['summary'] = None
    state['extracted_data'] = None
    # Reset conversation history
    state['messages'] = []

    logger.info("Cleared per-email state fields for next iteration")
    return state


def classify_email_node(state: EmailAgentState) -> EmailAgentState:
    """Classifies the current email using LLM integration."""
    logger.info("---NODE: CLASSIFYING EMAIL---")

    current_email = state.get('current_email')
    if not current_email:
        logger.warning("No current email to classify")
        state['classification'] = "other"
        return state

    email_subject = current_email.get('subject', '')
    email_body = current_email.get('body', '')

    prompt = f"""
    Classify the following email into exactly one of these categories: priority, meeting, task, invoice, newsletter, spam, other.

    Email Subject: {email_subject}
    Email Body: {email_body}

    Respond with only the category name, nothing else.
    """

    try:
        response = llm.invoke(prompt)
        classification = response.content.strip().lower()

        valid_categories = {"priority", "meeting", "task", "invoice", "newsletter", "spam", "other"}
        if classification not in valid_categories:
            logger.warning(f"Invalid classification '{classification}' from LLM, defaulting to 'other'")
            classification = "other"

        state['classification'] = classification
        logger.info(f"Email classified as: {classification}")

    except Exception as e:
        logger.error(f"Failed to classify email: {e}")
        state['classification'] = "other"  # Default classification on error

    return state