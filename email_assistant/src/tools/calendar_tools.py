from abc import ABC, abstractmethod
from typing import List, Dict, Any
from datetime import datetime
import requests
from langchain_core.tools import tool
from email_assistant.src.logger import logger
from email_assistant.src.tools.outlook_fetcher import OutlookFetcher

class BaseCalendarTool(ABC):
    """Abstract base class for calendar tools."""

    @abstractmethod
    def check_availability(
        self, 
        attendees: List[str], 
        start_time: str, 
        end_time: str
    ) -> List[Dict[str, Any]]:
        """Checks calendar availability for a list of attendees within a specified time window.
        Use this tool to find out when a group of people are free or busy to help with scheduling.

        Args:
            attendees: A list of email addresses for the people to check.
            start_time: The start of the time window to check, in ISO 8601 format (e.g., '2024-08-01T09:00:00Z').
            end_time: The end of the time window to check, in ISO 8601 format (e.g., '2024-08-01T17:00:00Z').

        Returns:
            A list of schedule information for each attendee, including their availability and busy slots."""
        pass

    @abstractmethod
    def create_event(
        self, 
        subject: str, 
        attendees: List[str], 
        start_time: str, 
        end_time: str, 
        body: str = None
    ) -> Dict[str, Any]:
        """Creates a new event on the user's primary calendar and sends invitations to attendees.
        Use this tool when you have all the necessary information to schedule a meeting or appointment.

        Args:
            subject: The title or subject of the event.
            attendees: A list of email addresses of people to invite to the event.
            start_time: The start time of the event in ISO 8601 format (e.g., '2024-08-01T10:00:00Z').
            end_time: The end time of the event in ISO 8601 format (e.g., '2024-08-01T11:00:00Z').
            body: Optional. The description or body of the event, can contain HTML.

        Returns:
            A dictionary representing the created event object from the Graph API."""
        pass

    @abstractmethod
    def update_event(
        self, 
        event_id: str, 
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Updates an existing calendar event using its unique event ID.
        Use this tool to modify an event, for example, to change the time, subject, or add attendees.

        Args:
            event_id: The unique identifier of the event to be updated.
            updates: A dictionary containing the fields to update. The keys and values should match the 
                     Graph API's event resource format. For example, to change the subject, you would pass
                     {'subject': 'New Subject'}. To change the time, pass {'start': {'dateTime': '...'}, 'end': {'dateTime': '...'}}.

        Returns:
            A dictionary representing the fully updated event object."""
        pass


class OutlookCalendarTool(BaseCalendarTool):
    """Concrete implementation of calendar tools for Microsoft Outlook."""
    
    def __init__(self, fetcher: OutlookFetcher):
        self.fetcher = fetcher
        self.base_url = "https://graph.microsoft.com/v1.0"


    def _get_access_token(self) -> str:
        """Acquires an access token silently using the fetcher's authenticated state."""
        if not self.fetcher.app or not self.fetcher.account:
            raise Exception("Outlook fetcher is not connected. Cannot get access token.")
        
        result = self.fetcher.app.acquire_token_silent(
            scopes=self.fetcher.SCOPES,
            account=self.fetcher.account
        )
        if not result or "access_token" not in result:
            logger.error("Could not acquire access token silently for calendar tool.")
            # Attempting a refresh with the device flow is complex here.
            # The initial connection via the fetcher should handle it.
            raise Exception("Authentication failed. Could not get access token for calendar tool.")
        return result["access_token"]


    def _make_api_call(self, method: str, endpoint: str, json_data: Dict = None) -> Dict[str, Any]:
        """Helper function to make API calls to Microsoft Graph."""
        try:
            access_token = self._get_access_token()
            headers = {'Authorization': 'Bearer ' + access_token, 'Content-Type': 'application/json'}
            url = f"{self.base_url}{endpoint}"
            response = requests.request(method, url, headers=headers, json=json_data)
            response.raise_for_status() # Raises an HTTPError for bad responses (4xx or 5xx)
            return response.json() if response.content else {}
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP Error during API call to {endpoint}: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred during API call to {endpoint}: {e}")
            raise


    def check_availability(
        self, 
        attendees: List[str], 
        start_time: str, 
        end_time: str
    ) -> List[Dict[str, Any]]:
        logger.info(f"Checking availability for {attendees} from {start_time} to {end_time}")
        endpoint = "/me/calendar/getSchedule"
        schedules = [{"email": attendee, "availabilityViewInterval": "15"} for attendee in attendees]
        payload = {
            "schedules": schedules,
            "startTime": {"dateTime": start_time, "timeZone": "UTC"},
            "endTime": {"dateTime": end_time, "timeZone": "UTC"},
            "availabilityViewInterval": 15
        }
        response_data = self._make_api_call("POST", endpoint, json_data=payload)
        return response_data.get('value', [])


    def create_event(
        self, 
        subject: str, 
        attendees: List[str], 
        start_time: str, 
        end_time: str, 
        body: str = None
    ) -> Dict[str, Any]:
        logger.info(f"Creating event '{subject}' from {start_time} to {end_time}")

        # --- Pre-execution Validation ---
        # Validate the date strings before making the API call.
        # This provides an immediate feedback loop to the LLM if it hallucinates.
        try:
            datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        except ValueError as e:
            error_message = f"Invalid date format for start_time or end_time. Dates must be in ISO 8601 format. Error: {e}"
            logger.error(error_message)
            raise ValueError(error_message)

        endpoint = "/me/events"
        event = {
            "subject": subject,
            "body": {"contentType": "HTML", "content": body or ""},
            "start": {"dateTime": start_time, "timeZone": "UTC"},
            "end": {"dateTime": end_time, "timeZone": "UTC"},
            "attendees": [{"emailAddress": {"address": attendee}, "type": "required"} for attendee in attendees]
        }
        return self._make_api_call("POST", endpoint, json_data=event)


    def update_event(
        self, 
        event_id: str, 
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        logger.info(f"Updating event {event_id} with updates: {updates}")
        endpoint = f"/me/events/{event_id}"
        return self._make_api_call("PATCH", endpoint, json_data=updates)
