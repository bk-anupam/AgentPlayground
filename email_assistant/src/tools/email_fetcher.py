import base64
import json
import os
import re
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
import msal
import requests

import google.auth
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.cloud import secretmanager
from google.api_core import exceptions as google_exceptions

from email_assistant.src.state import EmailObject, RefinedEmailAgentState
from email_assistant.src.logger import logger

# --- Abstract Base Class ---

class BaseEmailFetcher(ABC):
    """Abstract base class for fetching emails from a provider."""

    @abstractmethod
    def connect(self) -> Any:
        """Connect to the email service and return a service object."""
        pass

    @abstractmethod
    def fetch_raw_unread_emails(self, service: Any, max_count: int) -> List[Dict[str, Any]]:
        """Fetch a list of raw, unread email messages."""
        pass

    @abstractmethod
    def parse_email(self, raw_email: Dict[str, Any]) -> Optional[EmailObject]:
        """Parse a raw email message into a structured EmailObject."""
        pass

    def get_emails(self, max_count: int = 10) -> List[EmailObject]:
        """High-level method to connect, fetch, and parse emails."""
        logger.info(f"Starting email fetch process for max {max_count} emails.")
        service = self.connect()
        if not service:
            return []
        raw_emails = self.fetch_raw_unread_emails(service, max_count)
        parsed_emails = [self.parse_email(email) for email in raw_emails if email]
        # Filter out any None results from parsing failures
        valid_emails = [email for email in parsed_emails if email]
        logger.info(f"Successfully fetched and parsed {len(valid_emails)} emails.")
        return valid_emails


# --- Gmail Implementation ---

class GmailFetcher(BaseEmailFetcher):
    """A concrete implementation for fetching emails from Gmail."""

    # If modifying these scopes, delete the file token.json.
    SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
    CREDENTIALS_SECRET_ID = "gmail-credentials"
    TOKEN_SECRET_ID = "gmail-token"


    def connect(self) -> Optional[Any]:
        """
        Connects to the Gmail API using credentials stored in Google Secret Manager.
        """
        creds = None
        try:
            # Initialize Secret Manager client
            sm_client = secretmanager.SecretManagerServiceClient()
            
            # Get Project ID from environment or ADC
            try:
                _, project_id = google.auth.default()
            except google.auth.exceptions.DefaultCredentialsError:
                project_id = os.getenv("GOOGLE_CLOUD_PROJECT")

            if not project_id:
                logger.error("Google Cloud Project ID not found. Please set the GOOGLE_CLOUD_PROJECT environment variable or run 'gcloud auth application-default login'.")
                return None

            token_secret_path = sm_client.secret_version_path(project_id, self.TOKEN_SECRET_ID, "latest")
            
            # Try to load token from Secret Manager
            try:
                response = sm_client.access_secret_version(request={"name": token_secret_path})
                token_data = json.loads(response.payload.data.decode("UTF-8"))
                creds = Credentials.from_authorized_user_info(token_data, self.SCOPES)
            except google_exceptions.NotFound:
                logger.info(f"Secret '{self.TOKEN_SECRET_ID}' not found. Will proceed with new authorization flow.")
                creds = None

        except Exception as e:
            logger.error(f"Failed to initialize Secret Manager or load token: {e}")
            return None

        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    logger.info("Refreshing expired token.")
                    creds.refresh(Request())
                except Exception as e:
                    logger.error(f"Failed to refresh token: {e}. Please re-authenticate.")
                    creds = None  # Force re-authentication
            else:
                # Fetch credentials from Secret Manager to start the flow
                try:
                    creds_secret_path = sm_client.secret_version_path(project_id, self.CREDENTIALS_SECRET_ID, "latest")
                    response = sm_client.access_secret_version(request={"name": creds_secret_path})
                    creds_data = json.loads(response.payload.data.decode("UTF-8"))
                    
                    flow = InstalledAppFlow.from_client_config(creds_data, self.SCOPES)
                    creds = flow.run_local_server(port=0)
                except google_exceptions.NotFound:
                    logger.error(f"Secret '{self.CREDENTIALS_SECRET_ID}' not found in Secret Manager. Please create it with the content of your credentials.json file.")
                    return None
                except Exception as e:
                    logger.error(f"An error occurred during the OAuth flow: {e}")
                    return None

            # Save the new or refreshed credentials to Secret Manager
            try:
                token_payload = creds.to_json().encode("UTF-8")
                token_parent = sm_client.secret_path(project_id, self.TOKEN_SECRET_ID)
                sm_client.add_secret_version(request={"parent": token_parent, "payload": {"data": token_payload}})
                logger.info(f"Successfully saved new token to Secret Manager '{self.TOKEN_SECRET_ID}'.")
            except Exception as e:
                logger.error(f"Failed to save token to Secret Manager: {e}")

        try:
            service = build("gmail", "v1", credentials=creds)
            logger.info("Successfully connected to Gmail API.")
            return service
        except HttpError as error:
            logger.error(f"An error occurred connecting to Gmail: {error}")
            return None


    def fetch_raw_unread_emails(self, service: Any, max_count: int = 10) -> List[Dict[str, Any]]:
        try:
            results = service.users().messages().list(userId="me", labelIds=["INBOX"], q="is:unread", maxResults=max_count).execute()
            messages = results.get("messages", [])
            
            email_details = []
            if not messages:
                logger.info("No unread messages found.")
            else:
                for message in messages:
                    msg = service.users().messages().get(userId="me", id=message["id"]).execute()
                    email_details.append(msg)
            return email_details
        except HttpError as error:
            logger.error(f"An error occurred fetching emails: {error}")
            return []


    def parse_email(self, raw_email: Dict[str, Any]) -> Optional[EmailObject]:
        """Parses the complex Gmail API message object."""
        try:
            headers = raw_email["payload"]["headers"]
            email_id = raw_email["id"]
            subject = next((i["value"] for i in headers if i["name"] == "Subject"), "")
            sender = next((i["value"] for i in headers if i["name"] == "From"), "")
            received_at = next((i["value"] for i in headers if i["name"] == "Date"), "")

            body = ""
            if "parts" in raw_email["payload"]:
                parts = raw_email["payload"]["parts"]
                # Find the plain text part first
                part = next((p for p in parts if p["mimeType"] == "text/plain"), None)
                if part:
                    data = part["body"]["data"]
                    body = base64.urlsafe_b64decode(data.encode("ASCII")).decode("utf-8")
            elif "body" in raw_email["payload"] and "data" in raw_email["payload"]["body"]:
                data = raw_email["payload"]["body"]["data"]
                body = base64.urlsafe_b64decode(data.encode("ASCII")).decode("utf-8")
            
            # Clean up sender format
            match = re.search(r'<(.+?)>', sender)
            if match:
                sender = match.group(1)

            return EmailObject(
                id=email_id,
                sender=sender.strip(),
                subject=subject.strip(),
                body=body.strip(),
                received_at=received_at.strip(),
            )
        except Exception as e:
            logger.error(f"Error parsing email with ID {raw_email.get('id', 'N/A')}: {e}")
            return None


if __name__ == "__main__":
    logger.info("--- Starting GmailFetcher Test ---")

    # This test relies on Google Secret Manager for credentials.
    # Ensure you have run 'gcloud auth application-default login' and created the secrets.
    fetcher = GmailFetcher()

    # The first time you run this, it will start a device flow for authentication.
    # It will then save the token to Google Secret Manager.
    emails = fetcher.get_emails(max_count=3)

    if emails:
        logger.info(f"Successfully fetched {len(emails)} emails.")
        for i, email in enumerate(emails):
            print("\n" + "="*20 + f" EMAIL {i+1} " + "="*20)
            print(f"ID: {email['id']}")
            print(f"From: {email['sender']}")
            print(f"Subject: {email['subject']}")
            print(f"Body Preview: {email['body'][:200].strip()}...")
            print("="*50)