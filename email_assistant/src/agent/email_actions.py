from abc import ABC, abstractmethod
from typing import Any, Dict
import requests
from googleapiclient.errors import HttpError
from email_assistant.src.logger import logger


class BaseEmailActions(ABC):
    """Abstract base class for email actions across different providers."""

    @abstractmethod
    def mark_as_spam(self, email_id: str) -> Dict[str, Any]:
        """Marks an email as spam."""
        pass

    # Future actions like archive, move_to_folder, etc., would be defined here
    # @abstractmethod
    # def archive_email(self, email_id: str) -> Dict[str, Any]:
    #     pass


class GmailActions(BaseEmailActions):
    """Concrete implementation of email actions for the Gmail API."""

    def __init__(self, service: Any):
        if not service:
            raise ValueError("Gmail service client is required.")
        self.service = service

    def mark_as_spam(self, email_id: str) -> Dict[str, Any]:
        """
        Marks a Gmail email as spam by adding the 'SPAM' label and removing 'INBOX' and 'UNREAD'.
        """
        logger.info(f"---GMAIL ACTION: Marking email {email_id} as spam---")
        try:
            body = {
                'addLabelIds': ['SPAM'],
                'removeLabelIds': ['INBOX', 'UNREAD']
            }
            result = self.service.users().messages().modify(userId='me', id=email_id, body=body).execute()
            logger.info(f"Successfully marked email {email_id} as spam. Result: {result}")
            return {"status": "success", "email_id": email_id, "result": result}
        except HttpError as error:
            logger.error(f"An error occurred while marking email {email_id} as spam: {error}")
            return {"status": "error", "email_id": email_id, "error": str(error)}
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
            return {"status": "error", "email_id": email_id, "error": str(e)}


class OutlookActions(BaseEmailActions):
    """Concrete implementation of email actions for the Microsoft Graph API."""

    GRAPH_API_ENDPOINT = "https://graph.microsoft.com/v1.0"

    def __init__(self, client: requests.Session):
        if not client:
            raise ValueError("Outlook client (requests.Session) is required.")
        self.client = client

    def mark_as_spam(self, email_id: str) -> Dict[str, Any]:
        """Moves an Outlook email to the 'junkemail' folder."""
        logger.info(f"---OUTLOOK ACTION: Moving email {email_id} to Junk folder---")
        move_endpoint = f"{self.GRAPH_API_ENDPOINT}/me/messages/{email_id}/move"
        payload = {"destinationId": "junkemail"}
        try:
            response = self.client.post(move_endpoint, json=payload)
            response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
            logger.info(f"Successfully moved email {email_id} to Junk folder.")
            return {"status": "success", "email_id": email_id, "result": response.json()}
        except requests.exceptions.RequestException as e:
            logger.error(f"An error occurred moving email {email_id} to Junk: {e}")
            return {"status": "error", "email_id": email_id, "error": str(e)}
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
            return {"status": "error", "email_id": email_id, "error": str(e)}