import unittest
from unittest.mock import patch, MagicMock

from email_assistant.src.agent.graph import build_agent_workflow_graph
from email_assistant.src.tools.outlook_fetcher import OutlookFetcher
from email_assistant.src.agent.state import Email

class TestSimpleTriageFlow(unittest.TestCase):

    @patch('email_assistant.src.agent.email_actions.OutlookActions.mark_as_spam')
    @patch('email_assistant.src.agent.nodes.llm')
    def test_spam_email_is_triaged_and_marked_as_spam(self, mock_llm, mock_mark_as_spam):
        """
        Tests the full flow for a spam email:
        1. Fetch a fake email.
        2. Mock the LLM to classify it as 'spam'.
        3. Verify the simple_triage_node is called.
        4. Verify that the mark_as_spam action is called with the correct email ID.
        """
        # --- 1. Arrange (Setup Mocks) ---

        # Mock the LLM to return 'spam' classification
        # The LLM output is an object with a .content attribute
        mock_llm.invoke.return_value = MagicMock(content="spam")
        # Mock the action client's method to prevent real API calls
        mock_mark_as_spam.return_value = {"status": "success", "email_id": "test-spam-email-123"}
        # Create a fake email object
        test_email = Email(
            id='test-spam-email-123',
            sender='spammer@example.com',
            subject='VIAGRA 100% FREE CLICK NOW',
            body='This is definitely not a scam.',
            received_at='2025-09-22T10:00:00Z'
        )

        # Instantiate a real OutlookFetcher, but we will mock its methods
        email_fetcher = OutlookFetcher()
        # Mock the get_emails method to return the email on the first call, and an empty list thereafter                                                                          │
        email_fetcher.get_emails = MagicMock(side_effect=[[test_email], []])  
        # The `get_emails` method stores the service on the instance, so we mock it here
        email_fetcher.service = MagicMock()

        # --- 2. Act (Run the Graph) ---

        # Build the graph, passing the fetcher directly
        graph = build_agent_workflow_graph(email_fetcher=email_fetcher)
        # Define the inputs for the graph run (empty for this test)
        inputs = {}
        # Invoke the graph
        final_state = graph.invoke(inputs)

        # --- 3. Assert (Check the Results) ---
        # Verify that the LLM was called to classify
        mock_llm.invoke.assert_called_once()
        # Verify that mark_as_spam was called exactly once
        mock_mark_as_spam.assert_called_once()
        # Verify it was called with the correct email ID
        called_args, called_kwargs = mock_mark_as_spam.call_args
        self.assertEqual(called_kwargs.get('email_id'), test_email['id'])

        # Verify the final state of the graph
        self.assertIn('test-spam-email-123', final_state['processed_email_ids'])
        self.assertEqual(len(final_state['inbox']), 0)
        self.assertIsNone(final_state['current_email']) # Should be cleared by the end

if __name__ == '__main__':
    unittest.main()
