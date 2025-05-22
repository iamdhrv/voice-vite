"""
Vapi Handler for VoiceVite.

Handles Vapi outbound calls using direct API requests instead of the Vapi SDK.
"""
import requests # Keep for make_outbound_call if it's not refactored yet.
import json # Keep for make_outbound_call
import logging # Added for logger
from typing import Dict, Optional, Tuple # Tuple added
from datetime import datetime, timedelta

# VAPI SDK Imports
from vapi.client import Vapi
from vapi.types.model import Model as VapiModel, ModelMessagesItem
from vapi.types.voice import Voice as VapiVoice
from vapi.types.assistant_request import AssistantRequest # Not directly used for phone call, but good to be aware
from vapi.types.create_phone_call_payload import Customer as VapiCustomer
from vapi.types.phone_number_request import PhoneNumberRequest # Might be needed for phone_number_id object
from vapi.types.assistant_override import AssistantOverride as VapiAssistantOverride
from vapi.types.background_sound import BackgroundSound as VapiBackgroundSound


logger = logging.getLogger(__name__) # Added logger instance

class VapiHandler:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.vapi.ai"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def make_outbound_call(self, phone_number: str, assistant_id: str, guest_name: str, 
                          event_details: dict, guest_id_db: int, final_script: str, 
                          voice_choice: str = 'male') -> Optional[str]:
        """
        Initiates an outbound call using the Vapi API with event variables and a custom first message.
        
        Args:
            phone_number: The phone number to call in E.164 format
            assistant_id: The ID of the Vapi assistant to use
            guest_name: The name of the guest being called
            event_details: Dictionary containing event information (includes eventId, voiceSampleId, etc.)
            guest_id_db: The PostgreSQL database ID of the guest
            final_script: The finalized and potentially user-edited script content for the main system prompt.
            voice_choice: The voice type ('male', 'female', or 'custom')
            
        Note:
            Uses a fixed phone number ID (bbb6faa5-8983-4411-b7a1-cd4f159fc4ae) for outbound calls
            
        Returns:
            The call ID if successful, None otherwise
        """
        try:
            # Define the generic first message with placeholders for variables
            first_message = (
                "Hello, this is Rohan from VoiceVite, calling on behalf of {hostName}. "
                "I’m here to invite you to a special event. May I speak with {guestName}, please?"
            )

            end_call_message = (
                "Thank you for responding to VoiceVite, {guestName}. Your invitation to {hostName}’s {eventType} "
                "on {eventDate} at {eventTime} is confirmed. We look forward to seeing you at {location}. Goodbye!"
            )

            # Format EventDate into a conversational format (e.g., "Sunday, May 25, 2025")
            event_date_str = event_details.get("eventDate", "2025-05-15")
            event_date = datetime.strptime(event_date_str, "%Y-%m-%d")
            formatted_event_date = event_date.strftime("%A, %B %d, %Y")

            # Format EventTime into a conversational format (e.g., "7:17 AM")
            event_time_str = event_details.get("eventTime", "12:00")
            event_time = datetime.strptime(event_time_str, "%H:%M")
            formatted_event_time = event_time.strftime("%I:%M %p").lstrip("0")

            # Derive ArrivalTime from SpecialInstructions or default to 15 minutes before EventTime
            special_instructions = event_details.get("specialInstructions", "")
            arrival_time = "15 minutes before the event"
            if "arrive" in special_instructions.lower():
                # Extract arrival instruction if present (e.g., "arrive 15 minutes early")
                for part in special_instructions.lower().split():
                    if part.isdigit():
                        minutes = int(part)
                        arrival_time = f"{minutes} minutes before the event"
                        break
            arrival_datetime = event_date.replace(
                hour=event_time.hour, minute=event_time.minute
            ) - timedelta(minutes=15)  # Default to 15 minutes early
            formatted_arrival_time = arrival_time

            # Derive DressCode from SpecialInstructions if available
            dress_code = "not specified"
            if "dress code" in special_instructions.lower():
                dress_code_start = special_instructions.lower().find("dress code") + len("dress code")
                dress_code = special_instructions[dress_code_start:].strip(" :.").split(";")[0].strip()

            # Calculate AlternateDate and AlternateTime (e.g., 1 day later)
            alternate_date = event_date + timedelta(days=1)
            formatted_alternate_date = alternate_date.strftime("%A, %B %d, %Y")
            formatted_alternate_time = formatted_event_time  # Same time as original

            # Map event details to prompt placeholders
            variable_values = {
                "[HostName]": event_details.get("hostName", "the host"),
                "[GuestName]": guest_name,
                "[EventType]": event_details.get("eventType", "an event"),
                "[EventDate]": formatted_event_date,
                "[EventTime]": formatted_event_time,
                "[Location]": event_details.get("location", "a location"),
                "[CulturalPreferences]": event_details.get("culturalPreferences", ""),
                "[SpecialInstructions]": special_instructions,
                "[Duration]": event_details.get("duration", "a few hours"),
                "[RSVPDeadline]": event_details.get("rsvpDeadline", "soon"),
                "[ArrivalTime]": formatted_arrival_time,
                "[DressCode]": dress_code,
                "[AlternateDate]": formatted_alternate_date,
                "[AlternateTime]": formatted_alternate_time
            }

            # Format the first message with the variables
            formatted_first_message = first_message.format(
                hostName=variable_values["[HostName]"],
                guestName=variable_values["[GuestName]"]
            )

            # Format the end-of-call message with the variables
            formatted_end_call_message = end_call_message.format(
                guestName=variable_values["[GuestName]"],
                hostName=variable_values["[HostName]"],
                eventType=variable_values["[EventType]"],
                eventDate=variable_values["[EventDate]"],
                eventTime=variable_values["[EventTime]"],
                location=variable_values["[Location]"]
            )

            # Personalize the final_script for the current guest.
            # It's assumed that event-specific details like [HostName], [EventDate] etc.,
            # were already filled by _generate_event_script before user editing.
            # If final_script might still contain [HostName] etc. that need filling,
            # this personalization step would be more complex.
            # For now, only substituting {{GuestName}} as per primary requirement.
            personalized_script = final_script.replace("{{GuestName}}", guest_name)
            # Example: If final_script could also contain {{EventDate}}, this would be:
            # personalized_script = personalized_script.replace("{{EventDate}}", formatted_event_date)


            # Set voice configuration based on voice choice
            voice_config = {}
            if voice_choice == 'custom':
                voice_config = {
                    "provider": "lmnt",
                    "voiceId": event_details.get("voiceSampleId", "")
                }
            else:
                voice_id = "JBFqnCBsd6RMkjVDRZzb" if voice_choice == 'male' else "XrExE9yKIg1WjnnlVkGX"
                voice_config = {
                    "provider": "11labs",
                    "voiceId": voice_id,
                    "model": "eleven_multilingual_v2"
                }
            
            # Prepare the request payload with assistantOverrides
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
                ],
                "assistantOverrides": {
                    "firstMessage": formatted_first_message,
                    "endCallMessage": formatted_end_call_message,
                    "model": {
                        "provider": "openai",
                        "model": "chatgpt-4o-latest",
                        "messages": [
                            {
                                "role": "system",
                                "content": personalized_script # Use the personalized script
                            }
                        ]
                    },
                    "voice": voice_config
                },
                "metadata": {
                    "guestId": str(guest_id_db), 
                    "eventId": str(event_details.get("eventId")), 
                    "voiceSampleId": event_details.get("voiceSampleId")
                }
            }

            # Conditionally add backgroundSound
            background_music_url = event_details.get("background_music_url")
            if background_music_url: # Check if it's not None and not an empty string
                payload["assistantOverrides"]["backgroundSound"] = {
                    "url": background_music_url,
                    "volume": 0.2,
                    "loop": "false" # As per issue spec
                }

            print(f"Formatted First Message: {formatted_first_message}")
            print(f"Vapi API Key: {self.api_key}")
            print(f"Making outbound call to {phone_number} with payload: {json.dumps(payload, indent=2)}")
            
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
        except FileNotFoundError as e:
            print(f"Error loading prompt file: {e}")
            return None

    def make_single_test_call(self, phone_number: str, script_content: str, event_config: dict) -> tuple[bool, str]:
        try:
            host_name = event_config.get('host_name', 'Your Host')
            guest_name_for_test = "Test User" 

            personalized_script = script_content.replace("{{HostName}}", host_name)
            personalized_script = personalized_script.replace("{{GuestName}}", guest_name_for_test)
            
            test_first_message = f"This is a test call from VoiceVite on behalf of {host_name}. We will now play the invitation script for you."

            voice_sample_id = event_config.get('voice_sample_id')
            voice_config_payload = {}
            default_male_vapi_voice = 'JBFqnCBsd6RMkjVDRZzb' # Standard Vapi male voice
            default_female_vapi_voice = 'XrExE9yKIg1WjnnlVkGX' # Standard Vapi female voice

            if voice_sample_id == default_male_vapi_voice or voice_sample_id == default_female_vapi_voice:
                voice_config_payload = {"provider": "11labs", "voiceId": voice_sample_id, "model": "eleven_multilingual_v2"}
            elif voice_sample_id: 
                 voice_config_payload = {"provider": "lmnt", "voiceId": voice_sample_id}
            else: 
                voice_config_payload = {"provider": "11labs", "voiceId": default_male_vapi_voice, "model": "eleven_multilingual_v2"}

            payload = {
                "name": f"Test Call (Host: {host_name})",
                "assistantId": event_config.get('vapi_assistant_id'),
                "phoneNumberId": "bbb6faa5-8983-4411-b7a1-cd4f159fc4ae", 
                "customers": [{"number": phone_number, "name": guest_name_for_test, "numberE164CheckEnabled": False}],
                "assistantOverrides": {
                    "firstMessage": test_first_message,
                    "model": {
                        "provider": "openai", "model": "chatgpt-4o-latest", # Ensure this model is desired
                        "messages": [{"role": "system", "content": personalized_script}]
                    },
                    "voice": voice_config_payload
                },
                "metadata": {"call_type": "test_call", "description": "Test call from preview page"}
            }

            background_music_url = event_config.get("background_music_url")
            if background_music_url:
                payload["assistantOverrides"]["backgroundSound"] = {"url": background_music_url, "volume": 0.2, "loop": "false"}

            response = requests.post(f"{self.base_url}/call", headers=self.headers, json=payload)
            response.raise_for_status() 
            
            call_data = response.json()
            if 'results' in call_data and call_data['results'] and len(call_data['results']) > 0 and call_data['results'][0].get('id'):
                # This block is for the old requests-based method, will be removed.
                pass # Placeholder to be removed

        # --- Start of SDK-based implementation ---
        try:
            vapi_client = Vapi(api_key=self.api_key)
            
            host_name = event_config.get('host_name', 'Your Host')
            guest_name_for_test = "Test User"

            # Personalize script (assuming {{HostName}} and {{GuestName}} are the only placeholders needed here for test)
            personalized_script = script_content.replace("{{HostName}}", host_name)
            personalized_script = personalized_script.replace("{{GuestName}}", guest_name_for_test)
            
            test_first_message = f"This is a test call from VoiceVite on behalf of {host_name}. We will now play the invitation script for you."

            # Voice Configuration
            voice_sample_id = event_config.get('voice_sample_id')
            default_male_vapi_voice = 'JBFqnCBsd6RMkjVDRZzb'
            default_female_vapi_voice = 'XrExE9yKIg1WjnnlVkGX'
            
            voice_params = {}
            if voice_sample_id == default_male_vapi_voice or voice_sample_id == default_female_vapi_voice:
                voice_params = {"provider": "11labs", "voice_id": voice_sample_id, "model": "eleven_multilingual_v2"}
            elif voice_sample_id:
                voice_params = {"provider": "lmnt", "voice_id": voice_sample_id}
            else: # Default to a standard voice if none is configured
                voice_params = {"provider": "11labs", "voice_id": default_male_vapi_voice, "model": "eleven_multilingual_v2"}
            
            voice_override = VapiVoice(**voice_params)

            # Model Configuration
            model_override = VapiModel(
                provider="openai", 
                model="chatgpt-4o-latest", 
                messages=[ModelMessagesItem(role="system", content=personalized_script)]
            )

            # Background Sound
            background_sound_override = None
            background_music_url = event_config.get("background_music_url")
            if background_music_url:
                background_sound_override = VapiBackgroundSound(url=background_music_url, volume=0.2, loop=False)

            # Assistant Overrides
            assistant_overrides = VapiAssistantOverride(
                first_message=test_first_message,
                model=model_override,
                voice=voice_override,
                background_sound=background_sound_override # Pass None if no music
            )
            
            # Customer
            customer = VapiCustomer(number=phone_number, name=guest_name_for_test)

            # Make the call using SDK
            logger.info(f"Initiating test call to {phone_number} via VAPI SDK...")
            response = vapi_client.call.create_phone_call(
                phone_number_id="bbb6faa5-8983-4411-b7a1-cd4f159fc4ae", # Hardcoded phone number ID
                customer=customer,
                assistant_id=event_config.get('vapi_assistant_id'),
                assistant_overrides=assistant_overrides,
                metadata={"call_type": "test_call", "description": "Test call from preview page"}
            )

            if response and getattr(response, 'id', None):
                logger.info(f"Test call initiated successfully via SDK. Call ID: {response.id}")
                return True, "Test call initiated successfully via SDK."
            else:
                logger.warning(f"VAPI SDK call response for test call did not contain an ID or was unexpected: {response}")
                return False, "Test call initiated via SDK, but response did not confirm call ID."

        except Exception as e:
            logger.error(f"Error making test call via VAPI SDK: {str(e)}")
            return False, f"Error during SDK test call: {str(e)}"