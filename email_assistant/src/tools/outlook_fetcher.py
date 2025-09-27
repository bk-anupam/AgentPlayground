import json
import os
import re
from typing import List, Dict, Any, Optional, Tuple
import msal
import requests
import google.auth
from google.cloud import secretmanager
from google.api_core import exceptions as google_exceptions
from email_assistant.src.agent.state import Email
from email_assistant.src.logger import logger
from email_assistant.src.tools.email_fetcher import BaseEmailFetcher


class OutlookFetcher(BaseEmailFetcher):
    """A concrete implementation for fetching emails from Microsoft Outlook."""

    SCOPES = [
        "https://graph.microsoft.com/Mail.Read",
        "https://graph.microsoft.com/Calendars.ReadWrite"        
    ]

    CREDENTIALS_SECRET_ID = "outlook_credentials"
    TOKEN_SECRET_ID = "outlook-token-cache"
    GRAPH_API_ENDPOINT = "https://graph.microsoft.com/v1.0"

    def __init__(self):
        self.sm_client = secretmanager.SecretManagerServiceClient()
        self.project_id = self._get_project_id()
        self.token_cache = msal.SerializableTokenCache()
        self.app: Optional[msal.PublicClientApplication] = None
        self.account: Optional[Dict[str, Any]] = None

    def _get_project_id(self) -> Optional[str]:
        try:
            _, project_id = google.auth.default()
            return project_id
        except google.auth.exceptions.DefaultCredentialsError:
            return os.getenv("GOOGLE_CLOUD_PROJECT")


    def _load_cache(self):
        if not self.project_id:
            return
        try:
            path = self.sm_client.secret_version_path(self.project_id, self.TOKEN_SECRET_ID, "latest")
            response = self.sm_client.access_secret_version(request={"name": path})
            self.token_cache.deserialize(response.payload.data.decode("UTF-8"))
            logger.info(f"Successfully loaded token cache from '{self.TOKEN_SECRET_ID}'.")
        except google_exceptions.NotFound:
            logger.info(f"Secret '{self.TOKEN_SECRET_ID}' not found. A new one will be created after login.")
        except Exception as e:
            logger.error(f"Failed to load token cache from Secret Manager: {e}")


    def _save_cache(self):
        if not self.project_id or not self.token_cache.has_state_changed:
            return
        try:
            payload = self.token_cache.serialize().encode("UTF-8")
            parent = self.sm_client.secret_path(self.project_id, self.TOKEN_SECRET_ID)            
            try:
                # Try to add a new version directly
                self.sm_client.add_secret_version(request={"parent": parent, "payload": {"data": payload}})
            except google_exceptions.NotFound:
                # If the secret itself doesn't exist, create it and then add the version.
                logger.info(f"Secret '{self.TOKEN_SECRET_ID}' not found. Creating it now.")
                self.sm_client.create_secret(
                    parent=f"projects/{self.project_id}",
                    secret_id=self.TOKEN_SECRET_ID,
                    secret={
                        "replication": {"automatic": {}}
                    }
                )
                self.sm_client.add_secret_version(request={"parent": parent, "payload": {"data": payload}})
            logger.info(f"Successfully saved token cache to Secret Manager '{self.TOKEN_SECRET_ID}'.")
        except Exception as e:
            logger.error(f"Failed to save token cache to Secret Manager: {e}")


    def connect(self) -> Optional[requests.Session]:
        """Connects to MS Graph API using MSAL and credentials from Secret Manager."""
        if not self.project_id:
            logger.error("Google Cloud Project ID not found. Please set GOOGLE_CLOUD_PROJECT or run 'gcloud auth application-default login'.")
            return None

        try:
            creds_path = self.sm_client.secret_version_path(self.project_id, self.CREDENTIALS_SECRET_ID, "latest")
            response = self.sm_client.access_secret_version(request={"name": creds_path})
            ms_creds = json.loads(response.payload.data.decode("UTF-8"))
            # Use the 'common' authority to allow both personal (Outlook.com) and work/school accounts.
            # This is more flexible for a public client application and resolves the authority validation error.
            authority = "https://login.microsoftonline.com/common"
            self.app = msal.PublicClientApplication(
                ms_creds['client_id'], 
                authority=authority, 
                token_cache=self.token_cache,
                client_capabilities=["CP1"] # This capability is required to signal device code flow support
            )
        except google_exceptions.NotFound:
            logger.error(f"Secret '{self.CREDENTIALS_SECRET_ID}' not found. Please create it with your Azure App client_id.")
            return None
        except Exception as e:
            logger.error(f"Failed to initialize MSAL application: {e}")
            return None

        self._load_cache()
        accounts = self.app.get_accounts()
        if accounts:
            self.account = accounts[0]

        result = None
        if self.account:
            logger.info("Account found in cache. Attempting to acquire token silently.")
            result = self.app.acquire_token_silent(self.SCOPES, account=self.account)

        if not result:
            logger.info("Silent token acquisition failed. Starting device flow authentication.")
            flow = self.app.initiate_device_flow(scopes=self.SCOPES)
            if "message" not in flow:
                logger.error(f"Failed to create device flow. Response: {flow}")
                return None
            
            print(flow["message"]) # Instruct user to authenticate
            # The acquire_token_by_device_flow method is blocking. It polls the token endpoint
            # until authentication is complete or it times out. We increase the timeout
            # to give ample time for browser interaction, especially with MFA like Windows Hello.
            # The timeout is in seconds.
            result = self.app.acquire_token_by_device_flow(flow, timeout=300)
            # After successful device flow, get the account and store it
            accounts = self.app.get_accounts()
            if accounts:
                self.account = accounts[0]

        self._save_cache()

        if "access_token" in result:
            logger.info("Successfully acquired MS Graph access token to connect to Outlook.")
            session = requests.Session()
            session.headers.update({"Authorization": f"Bearer {result['access_token']}"})
            return session
        else:
            logger.error(f"Failed to acquire access token: {result.get('error_description')}")
            return None


    def fetch_raw_unread_emails(self, service: requests.Session, max_count: int = 10) -> List[Dict[str, Any]]:
        """
        Fetches unread emails using the Microsoft Graph API.
        """
        query_params = {
            "$filter": "isRead eq false",
            "$top": max_count,
            "$select": "id,receivedDateTime,subject,from,body",
            "$orderby": "receivedDateTime desc"
        }
        try:
            response = service.get(f"{self.GRAPH_API_ENDPOINT}/me/mailFolders/inbox/messages", params=query_params)
            response.raise_for_status()
            messages = response.json().get("value", [])
            if not messages:
                logger.info("No unread Outlook messages found.")
            logger.info(f"Fetched {len(messages)} unread Outlook messages.")    
            return messages
        except requests.exceptions.RequestException as e:
            logger.error(f"An error occurred fetching Outlook emails: {e}")
            return []


    def parse_email(self, raw_email: Dict[str, Any]) -> Optional[Email]:
        """Parses a raw email message from MS Graph API into a structured Email."""
        try:
            sender_info = raw_email.get("from", {}).get("emailAddress", {})
            sender_email = sender_info.get("address", "N/A")
            
            # The body can be HTML or text. Prefer text.
            body_content = raw_email.get("body", {})
            body = body_content.get("content", "")
            if body_content.get("contentType") == "html":
                # Basic HTML tag stripping
                body = re.sub('<[^<]+?>', '', body)

            return Email(
                id=raw_email.get("id", "N/A"),
                sender=sender_email.strip(),
                subject=raw_email.get("subject", "").strip(),
                body=body.strip(),
                received_at=raw_email.get("receivedDateTime", "").strip(),
            )
        except Exception as e:
            logger.error(f"Error parsing Outlook email with ID {raw_email.get('id', 'N/A')}: {e}")
            return None
        

if __name__ == "__main__":
    logger.info("--- Starting OutlookFetcher Test ---")

    # This test relies on Google Secret Manager for credentials.
    # Ensure you have run 'gcloud auth application-default login' and created the secrets.
    fetcher = OutlookFetcher()

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
