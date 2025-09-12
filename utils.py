from typing import Optional
import re
import json
import unicodedata # Added for character category checking
import codecs
from logger import logger
from langdetect import detect, LangDetectException, DetectorFactory
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from typing import List 
from datetime import datetime
from google.cloud import firestore
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver

def _devanagari_to_ascii_digits(devanagari_string: str) -> str:
    """Converts Devanagari numerals in a string to ASCII digits."""
    mapping = {
        '०': '0', '१': '1', '२': '2', '३': '3', '४': '4',
        '५': '5', '६': '6', '७': '7', '८': '8', '९': '9'
    }
    return "".join(mapping.get(char, char) for char in devanagari_string)


def extract_date_from_text(text: str, return_date_format: str = "%Y-%m-%d") -> Optional[str]:
    """
    Attempts to extract a date from the given text and returns it in return_date_format.
    Args:
        text (str): The text to search for a date.
        return_date_format (str): The format to return the date in. Default is "%Y-%m-%d"(YYYY-MM-DD).
    Returns:
        str or None: The extracted date in return_date_format if found, otherwise None.
    """
    # Specific date patterns to avoid ambiguity
    date_patterns = [
        (r"(\d{4})-(\d{2})-(\d{2})", "%Y-%m-%d"),  # YYYY-MM-DD
        (r"([०-९]{4})-([०-९]{2})-([०-९]{2})", "%Y-%m-%d"), # YYYY-MM-DD (Devanagari)

        (r"(\d{2})/(\d{2})/(\d{4})", "%d/%m/%Y"), # DD/MM/YYYY
        (r"([०-९]{2})/([०-९]{2})/([०-९]{4})", "%d/%m/%Y"), # DD/MM/YYYY (Devanagari)

        (r"(\d{2})\.(\d{2})\.(\d{4})", "%d.%m.%Y"), # DD.MM.YYYY
        (r"([०-९]{2})\.([०-९]{2})\.([०-९]{4})", "%d.%m.%Y"), # DD.MM.YYYY (Devanagari)

        (r"(\d{1,2})\.(\d{1,2})\.(\d{4})", "%d.%m.%Y"), # D.M.YYYY, DD.M.YYYY, D.MM.YYYY
        (r"([०-९]{1,2})\.([०-९]{1,2})\.([०-९]{4})", "%d.%m.%Y"), # D.M.YYYY (Devanagari)

        (r"(\d{1,2})/(\d{1,2})/(\d{4})", "%d/%m/%Y"), # D/M/YYYY, DD/M/YYYY, D/MM/YYYY
        (r"([०-९]{1,2})/([०-९]{1,2})/([०-९]{4})", "%d/%m/%Y"), # D/M/YYYY (Devanagari)

        (r"(\d{1,2})-(\d{1,2})-(\d{4})", "%d-%m-%Y"), # D-M-YYYY, DD-M-YYYY, D-MM-YYYY
        (r"([०-९]{1,2})-([०-९]{1,2})-([०-९]{4})", "%d-%m-%Y"), # D-M-YYYY (Devanagari)

        (r"(\d{2})\.(\d{2})\.(\d{2})", "%d.%m.%y"), # DD.MM.YY
        (r"([०-९]{2})\.([०-९]{2})\.([०-९]{2})", "%d.%m.%y"), # DD.MM.YY (Devanagari)

        (r"(\d{2})/(\d{2})/(\d{2})", "%d/%m/%y"), # DD/MM/YY
        (r"([०-९]{2})/([०-९]{2})/([०-९]{2})", "%d/%m/%y"), # DD/MM/YY (Devanagari)

        (r"(\d{2})-(\d{2})-(\d{2})", "%d-%m-%y"), # DD-MM-YY
        (r"([०-९]{2})-([०-९]{2})-([०-९]{2})", "%d-%m-%y"), # DD-MM-YY (Devanagari)

        (r"(\d{1,2})\.(\d{1,2})\.(\d{2})", "%d.%m.%y"), # D.M.YY, DD.M.YY, D.MM.YY
        (r"([०-९]{1,2})\.([०-९]{1,2})\.([०-९]{2})", "%d.%m.%y"), # D.M.YY (Devanagari)

        (r"(\d{1,2})/(\d{1,2})/(\d{2})", "%d/%m/%y"), # D/M/YY, DD/M/YY, D/MM/YY
        (r"([०-९]{1,2})/([०-९]{1,2})/([०-९]{2})", "%d/%m/%y"), # D/M/YY (Devanagari)

        (r"(\d{1,2})-(\d{1,2})-(\d{2})", "%d-%m-%y"), # D-M-YY, DD-M-YY, D-MM-YY
        (r"([०-९]{1,2})-([०-९]{1,2})-([०-९]{2})", "%d-%m-%y"), # D-M-YY (Devanagari)
        # Add other common formats if needed (e.g., "January 21, 1969")
    ]

    for pattern, date_format in date_patterns:
        match = re.search(pattern, text)
        if match:
            matched_date_str = match.group(0)
            ascii_date_str = _devanagari_to_ascii_digits(matched_date_str)
            try:
                # Attempt to parse the date using the specified format
                date_obj = datetime.strptime(ascii_date_str, date_format)
                return date_obj.strftime(return_date_format)
            except ValueError as e:
                logger.warning(f"Date format '{date_format}' matched for '{matched_date_str}' (converted to '{ascii_date_str}'), but couldn't parse. Error: {e}")                
            except Exception as e:
                    logger.error(f"Unexpected error parsing date '{matched_date_str}' (converted to '{ascii_date_str}') with format '{date_format}': {e}")                    

    logger.info(f"No date pattern matched in text: '{text[:100]}...'")
    return None 


def detect_text_language(text: str, default_lang: str = 'en') -> str:
    """
    Detects the language of the user question using langdetect.
    Falls back to default_lang if detection fails.
    """    
    DetectorFactory.seed = 0  # Set seed for reproducibility
    try:
        if not text.strip():
            logger.warning("Empty text provided for language detection. Defaulting to '%s'.", default_lang)
            return default_lang
        detected_lang = detect(text)
        logger.info(f"Detected language '{detected_lang}' for text.")
        return detected_lang
    except LangDetectException as lang_err:
        logger.warning(f"Could not detect language for text: {lang_err}. Defaulting to '{default_lang}'.")
        return default_lang
    except Exception as e:
        logger.error(f"Error during language detection for user question: {e}", exc_info=True)
        return default_lang