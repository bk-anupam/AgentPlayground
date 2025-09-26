from langchain_core.tools import tool

@tool
def placeholder_tool():
    """A placeholder tool that does nothing."""
    return "This is a placeholder tool."
