import re
from typing import Any, Dict, List, Tuple
from web_content_extraction_agent.state import AgentState
from logger import logger
import utils
from datetime import timezone, datetime
from langchain_core.documents import Document

def _extract_url(tool_content: str) -> str:
    """ Extract URL from the tool content if present. """    
    url = ""
    url_marker = "URL: "
    url_start_idx = tool_content.find(url_marker)
    if url_start_idx != -1:
        url_text_start = url_start_idx + len(url_marker)
        url_end_idx = tool_content.find("\n", url_text_start)
        if url_end_idx == -1:
            url_end_idx = len(tool_content)
        url = tool_content[url_text_start:url_end_idx].strip()
    return url


def _deduplicate_text(extracted_text: str) -> str:
    """ Deduplication logic for Murli content Use the specific phrase "प्रात:मुरली"as a delimiter
    to isolate the unique Murli content, preventing context bloating.    
    """
    keyword = "प्रात:मुरली"        
    # Find all start indices of the keyword
    indices = [m.start() for m in re.finditer(re.escape(keyword), extracted_text)]        
    deduplicated_text = extracted_text # Default to original text
    if len(indices) > 1:
        # If the keyword is found more than once, the unique content is the slice
        # from the beginning of the first occurrence to the beginning of the second.
        start_pos = indices[0]
        end_pos = indices[1]            
        # The content often starts with a date on the same line as the keyword.
        # To include the full line, we find the last newline before the first keyword.
        line_start_pos = extracted_text.rfind('\n', 0, start_pos)
        if line_start_pos == -1:
            line_start_pos = 0 # Keyword is on the very first line        
        deduplicated_text = extracted_text[line_start_pos:end_pos].strip()
        logger.info(f"Deduplicated murli content fetched using tavily-extract. "
                    f"Original length: {len(extracted_text)}, New length: {len(deduplicated_text)}")
    return deduplicated_text


def _extract_tavily_extract_content(tool_content: str) -> Tuple[List[str], List[Dict[str, Any]]]:
    """Extract content from tavily-extract tool output."""
    
    logger.info("Processing tavily-extract tool output (string parsing for extracted content)")    
    docs_content = []
    docs_metadata = []    
    try:
        # Extract main content
        raw_content_marker = "Raw Content: "
        raw_content_start_idx = tool_content.find(raw_content_marker)
        if raw_content_start_idx == -1:
            logger.warning("Could not find 'Raw Content:' marker in tavily-extract output")
            return docs_content, docs_metadata
        
        text_start_pos = raw_content_start_idx + len(raw_content_marker)
        extracted_text = tool_content[text_start_pos:].strip()        
        
        if not extracted_text:
            logger.warning("No extracted text found in tavily-extract output")
            return docs_content, docs_metadata
        
        deduplicated_text = _deduplicate_text(extracted_text)                
        url = _extract_url(tool_content)
        doc_date = utils.extract_date_from_text(deduplicated_text)
        doc_language = utils.detect_text_language(deduplicated_text)        
        docs_content.append(deduplicated_text)        
        metadata = {}
        if url:
            metadata["source"] = url
        if doc_date:
            metadata["date"] = doc_date    
        if doc_language:
            metadata["language"] = doc_language            
        docs_metadata.append(metadata)        
        logger.info("Metadata extracted from tavily-extract output: " + str(metadata))
    except Exception as e:
        logger.error(f"Error processing tavily-extract output: {e}, Content: {tool_content}", exc_info=True)
    
    return docs_content, docs_metadata


def process_tavily_tools(tool_name: str, tool_content: str, state: AgentState) -> Dict[str, Any]:
    """Process Tavily web search tool output."""
    if tool_name == "tavily-extract":
        docs_content, docs_metadata = _extract_tavily_extract_content(tool_content)    

    updated_state = {"documents": []}    

    if docs_content:
        # Add retrieval timestamp and source type to metadata
        retrieval_time = datetime.now(timezone.utc).isoformat()
        for meta in docs_metadata:
            meta['retrieval_time_utc'] = retrieval_time
            meta['source_type'] = 'web'

        tavily_documents = [
            Document(page_content=c, metadata=m)
            for c, m in zip(docs_content, docs_metadata)
        ]
        updated_state["documents"] = tavily_documents                
        logger.info(f"Processed {len(tavily_documents)} documents from {tool_name} and updated agent state.")        
    else:
        logger.warning(f"No document content extracted from Tavily tool {tool_name}.")

    return updated_state