# Gemini Agent Context: Email Assistant Project

This document provides essential context about the `email_assistant` project for the Gemini coding assistant.

### 1. Project Overview

The Email Management Agent is a system built with LangChain and LangGraph to intelligently triage, process, and manage incoming emails. Its goal is to automate routine tasks, extract key information, and facilitate timely responses, while keeping the user in control via a human-in-the-loop mechanism.

### 2. Core Technologies

- **Orchestration:** LangChain & LangGraph
- **Email Providers:** Gmail API, Microsoft Graph API
- **Authentication:**
    - Google: `google-auth-oauthlib`, `google-auth`
    - Microsoft: `msal` (Microsoft Authentication Library)
- **Security:** Google Secret Manager for storing all API credentials and tokens.
- **Logging:** Standard Python `logging` module, configured in `src/logger.py`.

### 3. Architecture & Design Principles

The agent's architecture is modular and event-driven, based on a state machine managed by LangGraph.

- **Batch Processing:** The agent fetches and processes a batch of emails in a single execution cycle.
- **Provider Agnostic Fetching:** An abstract base class, `BaseEmailFetcher`, defines a common interface for fetching emails. Concrete implementations like `GmailFetcher` and `OutlookFetcher` handle the specifics for each provider. This makes the system extensible.
- **Specialized Routing:** Emails are classified (e.g., `meeting`, `task`, `invoice`) and routed to specialized sub-graphs for tailored processing.
- **Cyclical Reasoning (ReAct Pattern):** For complex tasks, the agent uses a `plan -> execute -> observe` loop, allowing it to use tools iteratively and adjust its plan based on the results.
- **Human-in-the-Loop:** Critical actions, such as sending an email or creating a calendar event, require explicit user approval before execution.
- **Secure Credential Management:** All secrets (client IDs, tokens) are stored in Google Secret Manager, not in local files. The application fetches them at runtime.

### 4. Core Components & State

#### `EmailAgentState` (Defined in `src/state.py`)

This `TypedDict` is the central data structure (the "state") that is passed between all nodes in the LangGraph. It holds the agent's memory for the current run.

- `inbox: List[Email]`: The batch of emails fetched for the current run.
- `current_email_index: int`: Pointer to the email currently being processed from the `inbox`.
- `current_email: Optional[Email]`: The email object currently under analysis.
- `classification: Optional[Literal[...]]`: The category assigned to the `current_email`.
- `messages: Annotated[Sequence[BaseMessage], ...]`: The conversation history for the current email's reasoning loop. This is where the ReAct pattern is implemented.
- `user_preferences: UserPreferences`: User-defined rules to guide agent behavior.

#### Email Fetching Layer (Defined in `src/tools/`)

- **`BaseEmailFetcher` (`email_fetcher.py`):** The abstract base class that mandates `connect`, `fetch_raw_unread_emails`, and `parse_email` methods.
- **`GmailFetcher` (`email_fetcher.py`):**
    - Implements `BaseEmailFetcher` for Gmail.
    - Uses `google-auth-oauthlib` for the OAuth2 flow.
    - Stores/retrieves credentials from Google Secret Manager secrets: `gmail-credentials` (client config) and `gmail-token` (user auth token).
- **`OutlookFetcher` (`outlook_fetcher.py`):**
    - Implements `BaseEmailFetcher` for Microsoft Outlook.
    - Uses `msal` and the device flow for authentication.
    - Stores/retrieves credentials from Google Secret Manager secrets: `outlook_credentials` (app client ID) and `outlook-token-cache` (user auth token).

### 5. LangGraph Workflow

The workflow is designed as a main loop that processes emails one by one from the fetched batch.

1.  **`fetch_emails`**: Entry point. Instantiates a fetcher, gets emails, and populates `state.inbox`.
2.  **`select_next_email`**: Selects the next email from the inbox to process.
3.  **`classify_email`**: An LLM call to categorize the email.
4.  **Router**: A conditional edge that sends the email to a specialized sub-graph based on its classification.
5.  **Planner & Execution Loop**:
    - **`plan_step`**: The core reasoning step where the LLM decides what to do next (call a tool, ask for human approval, or finish).
    - **`execute_tools`**: A `ToolNode` that runs the function requested by the LLM.
    - **`human_review`**: A node that pauses the graph to wait for user input.
6.  **`update_run_state`**: Marks the email as processed and cleans up the state for the next iteration.
7.  The loop continues until all emails in the `inbox` are processed.

### 6. File Structure Guide

- `/docs`: Contains the high-level design (`email_agent_design.md`) and requirements (`requirements.md`).
- `/src`: Main source code.
    - `state.py`: Defines the core `EmailAgentState`.
    - `logger.py`: Configures the project-wide logger.
    - `test_fetcher.py`: A utility script to test the `GmailFetcher` and `OutlookFetcher` functionality directly.
    - `/tools`: Contains agent tools.
        - `email_fetcher.py`: Home of `BaseEmailFetcher` and `GmailFetcher`.
        - `outlook_fetcher.py`: Home of `OutlookFetcher`.
