import asyncio
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from logger import logger
from web_content_extraction_agent.process_tavily_extract_output import process_tavily_tools
from web_content_extraction_agent.config import Config  
from langchain_mcp_adapters.client import MultiServerMCPClient
from web_content_extraction_agent.state import AgentState


class WebContentExtractionAgent:
    def __init__(self, config: Config):
        self.config = config
        self.llm = None
        self.tools = []
        self.mcp_client = None
    

    async def get_mcp_server_tools(self, config_instance: Config):
        """
        Returns a list of MCP server tools.
        """
        if config_instance.DEV_MODE:
            tavily_mcp_command = f"export TAVILY_API_KEY='{config_instance.TAVILY_API_KEY}' && " \
                                "source /home/bk_anupam/.nvm/nvm.sh > /dev/null 2>&1 && " \
                                "nvm use v22.14.0 > /dev/null 2>&1 && " \
                                "npx --quiet -y tavily-mcp@0.2.1"
        else:
            tavily_mcp_command = f"export TAVILY_API_KEY='{config_instance.TAVILY_API_KEY}' && " \
                                "npx --quiet -y tavily-mcp@0.2.1"

        mcp_client = MultiServerMCPClient(
            {
                "tavily-mcp": {
                    "command": "bash",
                    "args": [
                        "-c",
                        tavily_mcp_command
                    ],
                    "transport": "stdio",
                },
            }
        )
        tools = await mcp_client.get_tools()
        return tools


    async def initialize(self):
        """Initialize the LLM and tools"""        
        self.llm = ChatGoogleGenerativeAI(
            model=self.config.MODEL_NAME,
            google_api_key=self.config.GOOGLE_API_KEY,  
            temperature=0,
            max_tokens=4096
        )        
        # Get MCP tools
        self.tools = await self.get_mcp_server_tools(self.config)                        
        # Bind tools to LLM
        self.llm_with_tools = self.llm.bind_tools(self.tools)
        logger.info(f"Initiailized LLM ({self.config.MODEL_NAME}) and {len(self.tools)} tools.")
    

    def create_agent_node(self):
        """Create the main agent node that uses the LLM"""
        async def agent_node(state: AgentState) -> AgentState:
            # Get the last message or create initial prompt
            if not state["messages"]:                
                system_prompt = (
                    "I need you to extract the hindi murli content for date 2025-09-08 "
                    "from the website: https://www.babamurli.com/. To achieve this we "
                    "need to proceed step by step.\n\n"
                    "Step 1: Use available tools to find the url for the web page that "
                    "contains hindi murli for 2025-09-08 from the website: "
                    "https://www.babamurli.com/. Start by exploring the website structure "
                    "using tavily-map tool to understand how they organize their content. "
                    "Use the following arguments for tavily-map:\n"
                    '{\n'
                    '  "url": "https://www.babamurli.com/",\n'
                    '  "limit": 30,\n'
                    '  "max_depth": 2,\n'
                    '  "instructions": "Find pages related to Hindi Murli content, daily murli, or date-specific content"\n'
                    '}\n\n'
                    "Step 2: Once you have found the correct url, your ONLY action should be "
                    "to call tavily-extract with the provided URL. The tool call would "
                    "return the murli contents from that URL.\n\n"
                    "Please start with Step 1."
                )
                
                state["messages"] = [HumanMessage(content=system_prompt)]
            
            # If a tool just ran, add a specific guiding prompt based on which tool was executed.
            # This makes the agent more robust, especially for 'flash' models.
            if state["messages"] and isinstance(state["messages"][-1], ToolMessage):
                last_tool_message = state["messages"][-1]                
                if last_tool_message.name == "tavily-map":
                    # Inject the tool's output directly into the guiding prompt.
                    guiding_prompt = (
                        f"The `tavily-map` tool has returned the following site map:\n\n"
                        f"```\n{last_tool_message.content}\n```\n\n"
                        "Please analyze this site map and proceed with the next step of the plan: "
                        "find the specific URL for the hindi murli for date 2025-09-08 and then call the `tavily-extract` tool with that single URL."
                    )
                    state["messages"].append(HumanMessage(content=guiding_prompt))
                elif last_tool_message.name == "tavily-extract":
                    # After processing, the clean content is in state['documents'].
                    # We use this clean content to prompt the LLM for the final answer.
                    extracted_content = ""
                    if state.get("documents"):
                        extracted_content = "\n\n".join([doc.page_content for doc in state["documents"]])

                    guiding_prompt = (
                        f"The `tavily-extract` tool has run and the content has been processed. Here is the extracted page content:\n\n"
                        f"```\n{extracted_content}\n```\n\n"
                        "This is the final step. Please present the extracted hindi murli content to the user as your final answer. "
                        "Do not call any more tools."
                    )
                    state["messages"].append(HumanMessage(content=guiding_prompt))
            
            # Ensure we have messages to send
            if not state["messages"]:
                logger.error("No messages to send to LLM")
                return state
                
            # Get response from LLM using the processed messages
            response = await self.llm_with_tools.ainvoke(state["messages"])
            state["messages"].append(response)            
            return state
        
        return agent_node
    

    def create_tool_node(self):
        """Create the tool execution node"""
        return ToolNode(self.tools)


    def create_process_tool_output_node(self):
        """Create a node to process the output of tools, specifically tavily-extract."""
        def process_tool_output_node(state: AgentState) -> AgentState:
            last_message = state["messages"][-1]
            if not isinstance(last_message, ToolMessage):
                return state

            if last_message.name == "tavily-extract":
                logger.info(f"Processing output from tool: {last_message.name}")
                updated_state = process_tavily_tools(last_message.name, last_message.content, state)
                # Merge the updated state
                state["documents"] = updated_state.get("documents", [])
                logger.info(f"Updated state with {len(state['documents'])} processed documents.")
            
            return state
        return process_tool_output_node
    

    def should_continue(self, state: AgentState) -> str:
        """Determine whether to continue or end based on the last message"""
        last_message = state["messages"][-1]        
        # If the last message has tool calls, execute them
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return "tools"        
        # Check if we have successfully extracted content
        messages_content = " ".join([msg.content for msg in state["messages"] if hasattr(msg, 'content') and msg.content])        
        # If tavily-extract has been called and content is present, we're done
        if "tavily-extract" in messages_content and any("बापदादा" in msg.content.lower() for msg in state["messages"] if hasattr(msg, 'content') and msg.content):
            return "end"        
        # Continue the conversation
        return "continue"
    

    def create_graph(self):
        """Create the complete LangGraph workflow"""
        workflow = StateGraph(AgentState)        
        # Create nodes
        agent_node = self.create_agent_node()
        tool_node = self.create_tool_node()
        process_tool_output_node = self.create_process_tool_output_node()
        # Add nodes to the graph
        workflow.add_node("agent", agent_node)
        workflow.add_node("tools", tool_node)
        workflow.add_node("process_tool_output", process_tool_output_node)
        # Set entry point
        workflow.set_entry_point("agent")        
        # Add conditional edges
        workflow.add_conditional_edges(
            "agent",
            self.should_continue,
            {
                "continue": "agent",
                "tools": "tools",
                "end": END
            }
        )        
        # After tools, go to processing node, then back to the agent
        workflow.add_edge("tools", "process_tool_output")
        workflow.add_edge("process_tool_output", "agent")
        # Compile with memory
        memory = MemorySaver()
        agent_graph = workflow.compile(checkpointer=memory)        
        return agent_graph    


async def execute_agent_graph(agent_graph: StateGraph, config_dict):
    # Run the agent
    final_state = None
    # The key difference between ainvoke and astream lies in what they return and when they return it.
    # ainvoke: Runs the entire graph and returns only the final result after the graph has completely finished.
    # astream: Runs the entire graph but returns an asynchronous iterator that yields the output of each step 
    #          along the way, as it happens.
    # Return Value: An AsyncIterator. You loop over it with async for.
    # Execution: Each iteration of the loop gives you an event dictionary, which contains the name of the node 
    #            that just ran and the resulting state of the graph at that moment.
    async for event in agent_graph.astream({"messages": []}, config_dict):
        for node_name, node_state in event.items():
            logger.info(f"Executing node: {node_name}")
            
            if "messages" in node_state:
                last_message = node_state["messages"][-1]
                
                if hasattr(last_message, 'content') and last_message.content:
                    content_preview = f"{last_message.content}"
                    logger.info(f"Message: {content_preview}")
                
                if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                    for tool_call in last_message.tool_calls:
                        logger.info(f"Tool Call: {tool_call['name']} with args: {tool_call['args']}")
                
                final_state = node_state
    
    logger.info("Extraction process complete.")
    if final_state:
        # Look for the final extracted content
        for message in reversed(final_state["messages"]):
            if hasattr(message, 'content') and message.content and "बापदादा" in message.content.lower():
                logger.info("Hindi Murli content successfully extracted!")
                logger.info(f"Content preview: {message.content[:500]}...")
                break
        else:
            logger.warning("Content extraction may not have completed successfully.")
            logger.warning("Check the conversation flow above for any errors.")
        
        logger.info("\n--- Final State Messages ---")
        for m in final_state['messages']:
            m.pretty_print()


# Main execution function
async def main():    
    config = Config()    
    agent = WebContentExtractionAgent(config)
    await agent.initialize()    
    # Create the graph
    app = agent.create_graph()  
    # Configuration for the run
    config_dict = {"configurable": {"thread_id": "hindi_murli_extraction_session"}}    
    await execute_agent_graph(app, config_dict)
    

if __name__ == "__main__":
    asyncio.run(main())
