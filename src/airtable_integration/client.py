"""
Airtable Client for VoiceVite.

Handles interactions with Airtable for event management.
"""
from pyairtable import Table
from config import config

class AirtableClient:
    """A client to interact with Airtable for managing events, guests, and RSVPs."""

    def __init__(self, personal_access_token: str, base_id: str):
        if not personal_access_token or not base_id:
            raise ValueError("Airtable personal access token and base ID are required.")
        
        self.events_table = Table(personal_access_token, base_id, config.AIRTABLE_TABLE_NAME_EVENTS)
        self.guests_table = Table(personal_access_token, base_id, config.AIRTABLE_TABLE_NAME_GUESTS)
        self.rsvps_table = Table(personal_access_token, base_id, config.AIRTABLE_TABLE_NAME_RSVPS)

    def create_event(self, event_data: dict) -> str | None:
        try:
            print(f"Creating event with data: {event_data}")
            record = self.events_table.create(event_data)
            print(f"Event created with ID: {record['id']}")
            return record['id']
        except Exception as e:
            print(f"Error creating event in Airtable: {e}")
            return None

    def add_guest(self, event_id: str, guest_data: dict) -> str | None:
        try:
            guest_data['EventID'] = [event_id]  # Linked field expects a list
            guest_data['CallStatus'] = 'Not Called'
            print(f"Adding guest with data: {guest_data}")
            record = self.guests_table.create(guest_data)
            print(f"Guest added with ID: {record['id']}")
            return record['id']
        except Exception as e:
            print(f"Error adding guest to Airtable: {e}")
            return None

    def add_guests_batch(self, event_id: str, guests_data: list[dict]) -> list[str]:
        try:
            for guest in guests_data:
                guest['EventID'] = [event_id]  # Linked field expects a list
                guest['CallStatus'] = 'Not Called'
            print(f"Adding guests batch with data: {guests_data}")
            records = self.guests_table.batch_create(guests_data)
            return [record['id'] for record in records]
        except Exception as e:
            print(f"Error adding guests batch to Airtable: {e}")
            return []

    def update_guest_call_status(self, guest_id: str, status: str):
        try:
            self.guests_table.update(guest_id, {'CallStatus': status})
        except Exception as e:
            print(f"Error updating guest call status in Airtable: {e}")

    def log_rsvp(self, guest_id: str, event_id: str, response: object) -> str | None:
        try:
            rsvp_data = {
                'GuestID': [guest_id],  # Linked field expects a list
                'EventID': [event_id],  # Linked field expects a list
                'Summary': response.summary,
                'Response': response.structuredData['rsvp_response'],
                'SpecialRequest': response.structuredData['special_request'],
                'ReminderRequest': response.structuredData['reminder_call_details'],
            }
            print(f"Logging RSVP with data: {rsvp_data}")
            record = self.rsvps_table.create(rsvp_data)
            return record['id']
        except Exception as e:
            print(f"Error logging RSVP in Airtable: {e}")
            return None