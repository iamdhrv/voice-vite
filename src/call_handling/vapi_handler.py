"""
Vapi Handler for VoiceVite.

Handles Vapi outbound calls using direct API requests instead of the Vapi SDK.
"""
import requests
import json
from typing import Dict, Optional

class VapiHandler:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.vapi.ai"
        self.headers = {
            "Authorization": f"Bearer {api_key}"
            # "Content-Type": "application/json"
        }
    
    def make_outbound_call(self, phone_number: str, assistant_id: str, guest_name: str, 
                          event_details: dict, guest_id_airtable: str) -> Optional[str]:
        """
        Initiates an outbound call using the Vapi API.
        
        Args:
            phone_number: The phone number to call in E.164 format
            assistant_id: The ID of the Vapi assistant to use
            guest_name: The name of the guest being called
            event_details: Dictionary containing event information
            guest_id_airtable: The Airtable ID of the guest
            
        Note:
            Uses a fixed phone number ID (bbb6faa5-8983-4411-b7a1-cd4f159fc4ae) for outbound calls
            
        Returns:
            The call ID if successful, None otherwise
        """
        try:
            # Prepare the request payload
            payload = {
                "name": f"{guest_name} Invitation call",
                "assistantId": assistant_id,
                "phoneNumberId": "bbb6faa5-8983-4411-b7a1-cd4f159fc4ae",
                "customers": [
                    {
                        "numberE164CheckEnabled": False,
                        "number": phone_number,
                        "name": guest_name
                    }
                ]
                # "metadata": {
                #     "guestId": guest_id_airtable,
                #     "eventId": event_details.get("eventId"),
                #     "voiceSampleId": event_details.get("voiceSampleId")
                # }
            }

            print(f"Vapi API Key: {self.api_key}")
            print(f"Making outbound call to {phone_number} with payload: {payload}")
            
            # Make the API request
            response = requests.post(
                f"{self.base_url}/call",
                headers=self.headers,
                json=payload
            )
            
            print(f"Response from Vapi API: {response.text}")
            # Check if the request was successful
            response.raise_for_status()
            call_data = response.json()
            
            # Extract call ID from the nested 'results' array in the response
            if 'results' in call_data and call_data['results'] and len(call_data['results']) > 0:
                call_id = call_data['results'][0]['id']
                print(f"Outbound call initiated to {phone_number}: {call_id}")
                return call_id
            else:
                print(f"No valid call ID found in response for {phone_number}")
                return None
            
        except requests.exceptions.RequestException as e:
            print(f"Error making outbound call to {phone_number}: {e}")
            return None
        except (KeyError, json.JSONDecodeError) as e:
            print(f"Error parsing API response for call to {phone_number}: {e}")
            return None