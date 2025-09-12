# Define the agent state
from typing import Optional, TypedDict, List, Annotated, Sequence
from langchain_core.messages import BaseMessage
from langchain_core.documents import Document

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], "The messages in the conversation"]
    # To store retrieved docs from any source
    documents: Optional[List[Document]]
