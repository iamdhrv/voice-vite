"""
Vapi Handler for VoiceVite.

Handles interactions with the Vapi API to initiate outbound calls,
manage call flows, and process responses for RSVPs.
"""
import requests
import json
from config import config # Assuming your config.py is in the root
# from src.airtable_integration.client import AirtableClient # To be uncommented

class VapiHandler:
    """A client to interact with the Vapi API for making calls."""

    def __init__(self, api_key: str):
        """
        Initializes the VapiHandler with the Vapi API key.

        Args:
            api_key (str): The Vapi API key.
        """
        if not api_key:
            raise ValueError("Vapi API key is required.")
        self.api_key = api_key
        self.base_url = "https://api.vapi.ai" # Confirm Vapi's base URL
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        # self.airtable_client = AirtableClient(config.AIRTABLE_API_KEY, config.AIRTABLE_BASE_ID) # Uncomment

    def create_assistant_if_not_exists(self, name: str, model_config: dict, voice_config: dict) -> str | None:
        """
        Creates a Vapi assistant if one with the given name doesn't already exist.
        This is a simplified example; Vapi might have different ways to manage assistants or voices.

        Args:
            name (str): Name for the assistant.
            model_config (dict): Configuration for the LLM (e.g., provider, model, messages).
            voice_config (dict): Configuration for the voice (e.g., provider, voice_id).

        Returns:
            str | None: The Assistant ID if created or found, else None.
        """
        # This is a placeholder. Vapi's actual assistant creation might be different.
        # You might pre-configure assistants in Vapi's dashboard or use a more specific API.
        # For this MVP, we might assume an assistant is configured with the cloned voice.
        print(f"Attempting to ensure assistant '{name}' exists with voice: {voice_config.get('voice_id')}")
        # In a real scenario, you'd list assistants and find by name or create new.
        # For now, let's assume we use a pre-existing assistant ID or a generic one.
        # Or, if Vapi allows dynamic assistant creation with specific voice IDs from ElevenLabs:
        assistant_payload = {
            "name": name,
            "model": model_config, # e.g., { "provider": "openai", "model": "gpt-3.5-turbo", "messages": [...] }
            "voice": voice_config, # e.g., { "provider": "elevenlabs", "voiceId": "your_elevenlabs_voice_id" }
            "firstMessage": "Hello! This is a call from VoiceVite.", # Initial greeting
            # Add other necessary assistant parameters like serverUrl for webhooks
            "serverUrl": f"{config.APP_BASE_URL}/webhook/vapi" # Replace with your actual ngrok/deployed URL
        }
        # response = requests.post(f"{self.base_url}/assistant", headers=self.headers, json=assistant_payload)
        # if response.status_code == 201:
        #     return response.json().get('id')
        # print(f"Error creating/finding Vapi assistant: {response.text}")
        # return None
        return "mock_assistant_id_for_cloned_voice" # Placeholder

    def make_outbound_call(self, phone_number: str, assistant_id: str, guest_name: str, event_details: dict, guest_id_airtable: str) -> str | None:
        """
        Makes an outbound call to a specific phone number using a Vapi assistant.

        Args:
            phone_number (str): The recipient's phone number in E.164 format.
            assistant_id (str): The ID of the Vapi assistant to use for the call.
            guest_name (str): The name of the guest to personalize the call.
            event_details (dict): Dictionary containing event information for script personalization.
            guest_id_airtable (str): The Airtable record ID for the guest, to be passed as metadata.

        Returns:
            str | None: The Call ID if the call was initiated successfully, else None.
        """
        # Script generation would happen here or be passed in.
        # For MVP, let's assume a simple script incorporating guest_name and event_details.
        # Example: "Hello {guest_name}, you're invited to {event_details['EventType']} on {event_details['EventDate']}. Can you make it?"
        
        # The actual script/prompting logic would be part of the assistant's configuration on Vapi's side,
        # potentially using variables passed in the call payload.

        payload = {
            "assistantId": assistant_id,
            "phoneNumberId": "your_vapi_phone_number_id", # This needs to be a Vapi provisioned Phone Number ID
            "customer": {
                "number": phone_number
            },
            "metadata": { # Custom data to be sent with webhooks
                "guest_name": guest_name,
                "event_type": event_details.get('EventType'),
                "event_date": event_details.get('EventDate'),
                "airtable_guest_id": guest_id_airtable,
                "airtable_event_id": event_details.get('EventID') # Assuming EventID is available
            }
            # You might be able to pass variables to the assistant for personalization
            # "assistant": {
            #     "variables": {
            #         "guestName": guest_name,
            #         "eventType": event_details.get('EventType'),
            #         "eventDate": event_details.get('EventDate')
            #     }
            # }
        }

        try:
            response = requests.post(f"{self.base_url}/call/phone", headers=self.headers, json=payload)
            response.raise_for_status() # Raise an exception for HTTP errors
            call_data = response.json()
            print(f"Call initiated to {phone_number}: {call_data}")
            # self.airtable_client.update_guest_call_status(guest_id_airtable, 'Called - Initiated') # Uncomment
            return call_data.get('id') # Or appropriate Call ID field
        except requests.exceptions.RequestException as e:
            print(f"Error making outbound call to {phone_number} via Vapi: {e}")
            if e.response is not None:
                print(f"Vapi Response: {e.response.text}")
            # self.airtable_client.update_guest_call_status(guest_id_airtable, 'Failed - API Error') # Uncomment
            return None

    def initiate_calls_for_event(self, event_id_airtable: str):
        """
        Retrieves event details and guest list from Airtable, then initiates calls.

        Args:
            event_id_airtable (str): The Airtable record ID for the event.
        """
        # event_record = self.airtable_client.get_event(event_id_airtable) # Uncomment
        # if not event_record or 'fields' not in event_record:
        #     print(f"Event {event_id_airtable} not found or invalid.")
        #     return
        # event_details = event_record['fields']
        # event_details['EventID'] = event_id_airtable # Add EventID for metadata

        # guests = self.airtable_client.get_guests_for_event(event_id_airtable) # Uncomment
        # if not guests:
        #     print(f"No guests found for event {event_id_airtable}.")
        #     return

        # # Assume voice_sample_id from event_details is the ElevenLabs voice ID
        # elevenlabs_voice_id = event_details.get('VoiceSampleID')
        # if not elevenlabs_voice_id:
        #     print("VoiceSampleID not found in event details. Cannot make calls.")
        #     return
        
        # # This is a simplified assistant creation/retrieval. 
        # # In a real app, you'd manage assistants more robustly.
        # assistant_name = f"VoiceVite_Event_{event_id_airtable[:8]}"
        # model_cfg = { # Example model config, customize as needed
        #     "provider": "openai", 
        #     "model": "gpt-3.5-turbo", 
        #     "messages": [
        #         {"role": "system", "content": "You are a friendly assistant calling to invite a guest to an event. Be polite and gather their RSVP (Yes, No, or Maybe)."}
        #     ]
        # }
        # voice_cfg = {"provider": "elevenlabs", "voiceId": elevenlabs_voice_id}
        # assistant_id = self.create_assistant_if_not_exists(assistant_name, model_cfg, voice_cfg)
        
        # if not assistant_id:
        #     print(f"Failed to get or create Vapi assistant for event {event_id_airtable}.")
        #     return

        # print(f"Using Vapi Assistant ID: {assistant_id} for event {event_id_airtable}")

        # for guest_record in guests:
        #     guest = guest_record['fields']
        #     guest_id = guest_record['id']
        #     phone_number = guest.get('PhoneNumber')
        #     guest_name = guest.get('GuestName', 'Valued Guest') # Default if name is missing

        #     if not phone_number:
        #         print(f"Skipping guest {guest_name} (ID: {guest_id}) due to missing phone number.")
        #         self.airtable_client.update_guest_call_status(guest_id, 'Failed - No Phone')
        #         continue
            
        #     print(f"Initiating call to {guest_name} at {phone_number} for event {event_details.get('EventType')}")
        #     call_id = self.make_outbound_call(phone_number, assistant_id, guest_name, event_details, guest_id)
        #     if call_id:
        #         print(f"Call to {guest_name} initiated. Call ID: {call_id}")
        #         # Airtable status updated within make_outbound_call or here
        #     else:
        #         print(f"Failed to initiate call to {guest_name}.")
        #         # Airtable status updated within make_outbound_call
        pass # Placeholder for the above commented logic

    def parse_rsvp_from_transcript(self, transcript: str) -> str:
        """
        Parses an RSVP response from a call transcript (simple version).
        This would ideally use an LLM for more robust understanding.

        Args:
            transcript (str): The transcript of the guest's response.

        Returns:
            str: RSVP status ('Yes', 'No', 'Maybe', 'No Response').
        """
        # This is a very basic parser. For production, use NLP/LLM.
        lower_transcript = transcript.lower()
        if "yes" in lower_transcript or "i can" in lower_transcript or "i'll be there" in lower_transcript:
            return "Yes"
        elif "no" in lower_transcript or "can't make it" in lower_transcript or "unable to" in lower_transcript:
            return "No"
        elif "maybe" in lower_transcript or "not sure" in lower_transcript or "possibly" in lower_transcript:
            return "Maybe"
        return "No Response" # Default if unclear

# Example Usage (for testing purposes)
if __name__ == '__main__':
    if not config.VAPI_API_KEY:
        print("Vapi API Key not found in config. Please set it.")
    else:
        vapi_handler = VapiHandler(api_key=config.VAPI_API_KEY)
        print("VapiHandler initialized.")

        # --- Test making a call (replace with actual data) ---
        # Ensure you have a Vapi provisioned phone number ID and an assistant ID.
        # You'll also need a live phone number to test with.
        # test_phone_number = "+1XXXXXXXXXX"  # Your test phone number in E.164
        # test_assistant_id = "your_vapi_assistant_id" # Pre-configured assistant on Vapi
        # test_guest_name = "Test Guest"
        # test_event_details = {
        #     'EventType': 'Test Party',
        #     'EventDate': '2024-12-31',
        #     'EventID': 'recMockEventID'
        # }
        # test_airtable_guest_id = "recMockGuestID"

        # print(f"\n--- Testing Outbound Call to {test_phone_number} ---")
        # call_id = vapi_handler.make_outbound_call(
        #     phone_number=test_phone_number, 
        #     assistant_id=test_assistant_id, 
        #     guest_name=test_guest_name,
        #     event_details=test_event_details,
        #     guest_id_airtable=test_airtable_guest_id
        # )
        # if call_id:
        #     print(f"Call initiated successfully. Call ID: {call_id}")
        # else:
        #     print("Failed to initiate call.")

        # --- Test initiating calls for an event (requires Airtable setup and data) ---
        # print("\n--- Testing Initiate Calls for Event (requires Airtable data) ---")
        # mock_airtable_event_id = "YOUR_AIRTABLE_EVENT_ID_HERE" # Replace with a real Event ID from your Airtable
        # if mock_airtable_event_id != "YOUR_AIRTABLE_EVENT_ID_HERE":
        #     vapi_handler.initiate_calls_for_event(mock_airtable_event_id)
        # else:
        #     print("Skipping initiate_calls_for_event test. Provide a valid Airtable Event ID.")
        pass