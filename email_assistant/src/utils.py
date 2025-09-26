import google.auth
import google.auth.transport.requests
import requests
from email_assistant.src.agent.tools import placeholder_tool
from email_assistant.src.logger import logger
from email_assistant.src.tools.calendar_tools import OutlookCalendarTool
from email_assistant.src.tools.email_fetcher import BaseEmailFetcher
from email_assistant.src.tools.outlook_fetcher import OutlookFetcher


def get_tools(email_fetcher: BaseEmailFetcher) -> list:
    """Helper to get the list of tools based on the email fetcher type."""
    tools = [placeholder_tool]
    if isinstance(email_fetcher, OutlookFetcher):
        logger.info("Outlook fetcher detected, initializing Outlook calendar tools.")
        calendar_tool = OutlookCalendarTool(fetcher=email_fetcher)
        tools.extend([
            calendar_tool.check_availability,
            calendar_tool.create_event,
            calendar_tool.update_event
        ])
    return tools



def get_gcp_identity():
    """
    Inspects the application's default credentials to find the authenticated
    user or service account email.
    """
    try:
        # Get the credentials and project from the environment
        credentials, project_id = google.auth.default()

        # For service accounts, the email is directly available
        if hasattr(credentials, 'service_account_email'):
            logger.info(f"Running as service account: {credentials.service_account_email}")
            return credentials.service_account_email

        # For user accounts, we need to inspect the access token
        # Refresh the credentials to make sure we have a valid access token
        credentials.refresh(google.auth.transport.requests.Request())
        
        # Call the tokeninfo endpoint
        token_info_url = f"https://www.googleapis.com/oauth2/v3/tokeninfo?access_token={credentials.token}"
        response = requests.get(token_info_url)
        response.raise_for_status()
        
        token_info = response.json()
        email = token_info.get("email")

        if email:
            logger.info(f"Running as user: {email}")
            return email
        else:
            logger.warning("Could not determine user email from token.")
            return None

    except Exception as e:
        logger.error(f"Failed to determine GCP identity: {e}")
        return None


if __name__ == '__main__':
    # Example of how to use it
    identity = get_gcp_identity()
    if identity:
        print(f"The code is executing as: {identity}")
    else:
        print("Could not determine the GCP identity.")

