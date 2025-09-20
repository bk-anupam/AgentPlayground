import sys
from email_assistant.src.tools.email_fetcher import GmailFetcher
from email_assistant.src.tools.outlook_fetcher import OutlookFetcher
from email_assistant.src.logger import logger

def test_gmail_fetcher():
    """
    Tests the GmailFetcher class by connecting to the API and fetching emails.
    """
    logger.info("--- Starting GmailFetcher Test ---")
    
    # This test now relies on Google Secret Manager for credentials.
    # Ensure you have run 'gcloud auth application-default login' and created the secrets.
    fetcher = GmailFetcher()
    
    # The first time you run this, it will open a browser for authentication.
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

def test_outlook_fetcher():
    """
    Tests the OutlookFetcher class by connecting to the API and fetching emails.
    """
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

if __name__ == "__main__":
    if len(sys.argv) > 1:
        provider = sys.argv[1].lower()
        if provider == 'gmail':
            test_gmail_fetcher()
        elif provider == 'outlook':
            test_outlook_fetcher()
        else:
            logger.error(f"Invalid provider '{provider}'. Please use 'gmail' or 'outlook'.")
    else:
        logger.info("Please specify a provider to test. Usage: python test_fetcher.py [gmail|outlook]")
