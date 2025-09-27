# Gemini Agent Context: Email Assistant Project

This document provides essential context about the `email_assistant` project for the Gemini coding assistant. Its purpose is to enable a coding assistant to quickly understand the project's design, architecture, and key components.

### 1. Project Overview

The Email Management Agent is a system built with LangChain and LangGraph to intelligently triage, process, and manage incoming emails. Its goal is to automate routine tasks, extract key information, and facilitate timely responses, while keeping the user in control via robust human-in-the-loop mechanisms.

### 2. Core Technologies

- **Orchestration:** LangChain & LangGraph
- **LLM:** Google Gemini
- **Email Providers:** Microsoft Graph API (primary), Gmail API
- **Authentication:** `msal` (Microsoft) for device flow, `google-auth-oauthlib` (Google)
- **Security:** Google Secret Manager for all API credentials and user tokens.
- **Configuration:** `prompts.yaml` for prompts, managed by a `PromptManager`.

### 3. Architecture & Design Principles

The agent's architecture is a modular, event-driven state machine managed by LangGraph.

- **Specialized Planners:** After an initial classification, emails are routed to specialized sub-graphs (e.g., `meeting_planner`, `task_planner`). This is a core design pattern.
- **Cyclical Reasoning (ReAct):** For complex tasks, the agent uses a `plan -> execute -> observe` loop, allowing it to use tools iteratively and adjust its plan based on results.
- **Human-in-the-Loop (Dual Mechanism):**
    - **Information Gathering:** The agent uses an `ask_user_for_input` tool to pause the workflow and ask the user for clarification when it lacks information to proceed. This treats the user as a queryable tool.
    - **Action Approval:** A dedicated `human_review` node is planned for getting explicit user consent before executing critical actions like sending an email or deleting a calendar event.
- **Provider-Agnostic Layers:** Abstract base classes like `BaseEmailFetcher` and `BaseEmailActions` define common interfaces, allowing for concrete implementations (`OutlookFetcher`, `GmailActions`) to be used interchangeably.
- **Secure Credential Management:** All secrets (client IDs, tokens) are stored in Google Secret Manager, not in local files.

### 4. Core Components & State

#### `EmailAgentState` (Defined in `src/agent/state.py`)

This `TypedDict` is the central data structure passed between all nodes in the LangGraph. It holds the agent's memory for the current run.

```python
class EmailAgentState(TypedDict):
    # --- Batch Processing State ---
    inbox: List[Email]
    current_email_index: int
    processed_email_ids: List[str]
    fetch_emails_run_count: Optional[int]

    # --- Per-Email Processing State ---
    current_email: Optional[Email]
    classification: Optional[Literal["priority", "meeting", "task", "invoice", "newsletter", "spam", "other"]]
    summary: Optional[str]
    extracted_data: Optional[Dict[str, Any]]

    # --- Core Reasoning State ---
    messages: Annotated[Sequence[BaseMessage], add_messages]

    # --- Configuration & Services ---
    user_preferences: UserPreferences
    email_actions_client: Optional[BaseEmailActions] = None
    email_fetcher: Optional[BaseEmailFetcher] = None
```

#### Email Fetching & Tools

- **`OutlookFetcher` (`src/tools/outlook_fetcher.py`):** The primary concrete implementation for fetching emails.
    - Uses `msal` with a **device flow** for authentication.
    - Caches the user token in Google Secret Manager (`outlook-token-cache`).
    - **Crucially, it also requests `Calendars.ReadWrite` scope**, as the `OutlookCalendarTool` depends on its authenticated state.
- **`OutlookCalendarTool` (`src/tools/calendar_tools.py`):** The concrete implementation for calendar actions.
    - It is initialized with an `OutlookFetcher` instance to handle authentication.
    - It performs **pre-execution validation** on date formats before making API calls to fail fast and provide better feedback to the LLM.

### 5. LangGraph Workflow

The workflow is a main loop that processes emails one by one from the fetched batch.

1.  **`fetch_emails`**: Entry point. Instantiates a fetcher (`OutlookFetcher`), gets emails, and populates `state.inbox`.
2.  **`select_next_email`**: Selects the next email from the inbox to process.
3.  **`classify_email`**: An LLM call to categorize the email.
4.  **Router**: A conditional edge that sends the email to a specialized planner (`meeting_planner`, `task_planner`, etc.) based on its classification.
5.  **Reasoning Loop**:
    - **`plan_step`**: The core reasoning step where the LLM decides what to do next (call a tool, ask for human input, or finish).
    - **`execute_tools`**: A `ToolNode` that runs the function requested by the LLM (e.g., `create_event`, `ask_user_for_input`). The output is fed back to `plan_step`.
6.  **`update_run_state`**: Marks the email as processed and cleans up the state for the next iteration.
7.  The loop continues until all emails in the `inbox` are processed.

### 6. File Structure Guide

- `/docs`: Contains the high-level design (`email_agent_design.md`) and requirements (`requirements.md`).
- `/src`: Main source code.
    - `config.py`: Holds application-level configuration variables.
    - `llm_factory.py`: Initializes and configures the Gemini LLM instance.
    - `logger.py`: Configures the project-wide logger.
    - `utils.py`: Contains shared utility functions (e.g., `get_tools`).
    - `/agent`: Core agent logic and LangGraph definition.
        - `state.py`: Defines the central `EmailAgentState` TypedDict.
        - `graph.py`: Builds and compiles the main LangGraph workflow, connecting all nodes and edges.
        - `nodes.py`: Implements the primary graph nodes (e.g., `fetch_emails`, `classify_email`, `update_run_state`).
        - `planner_nodes.py`: Implements the specialized planner nodes that kick off the reasoning loop (e.g., `meeting_planner`).
        - `plan_step_node.py`: Contains the core ReAct reasoning node where the LLM decides the next action.
        - `email_actions.py`: Implements provider-specific actions like marking emails as spam.
    - `/prompts`: Manages all LLM prompts.
        - `prompts.yaml`: Contains the raw text for all system and human prompts.
        - `prompt_manager.py`: A singleton class that loads, manages, and provides formatted prompts to the agent.
    - `/tools`: Contains tools for interacting with external services.
        - `email_fetcher.py`: Defines the `BaseEmailFetcher` interface and `GmailFetcher`.
        - `outlook_fetcher.py`: Defines the `OutlookFetcher` for Microsoft Graph API.
        - `calendar_tools.py`: Defines the `OutlookCalendarTool` for creating and managing calendar events.