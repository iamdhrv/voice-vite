"""
Airtable Client for VoiceVite.

Handles all interactions with the Airtable API, including creating, reading,
and updating records for Events, Guests, and RSVPs.
"""
from airtable import Airtable
from config import config # Assuming your config.py is in the root and accessible

class AirtableClient:
    """A client to interact with Airtable tables for Events, Guests, and RSVPs."""

    def __init__(self, api_key: str, base_id: str):
        """
        Initializes the AirtableClient with API key and Base ID.

        Args:
            api_key (str): The Airtable API key.
            base_id (str): The ID of the Airtable base.
        """
        if not api_key:
            raise ValueError("Airtable API key is required.")
        if not base_id:
            raise ValueError("Airtable Base ID is required.")
        
        self.api_key = api_key
        self.base_id = base_id
        self.events_table = Airtable(base_id, config.AIRTABLE_TABLE_NAME_EVENTS, api_key)
        self.guests_table = Airtable(base_id, config.AIRTABLE_TABLE_NAME_GUESTS, api_key)
        self.rsvps_table = Airtable(base_id, config.AIRTABLE_TABLE_NAME_RSVPS, api_key)

    def create_event(self, event_data: dict) -> str | None:
        """
        Creates a new event record in the Events table.

        Args:
            event_data (dict): A dictionary containing event details.
                               Example: {'EventType': 'Birthday', 'EventDate': '2024-12-25', ...}

        Returns:
            str | None: The ID of the created event record, or None if creation failed.
        """
        try:
            record = self.events_table.insert(event_data)
            return record['id']
        except Exception as e:
            print(f"Error creating event in Airtable: {e}")
            return None

    def get_event(self, event_id: str) -> dict | None:
        """
        Retrieves an event record by its ID.

        Args:
            event_id (str): The ID of the event record.

        Returns:
            dict | None: The event record data, or None if not found or error.
        """
        try:
            record = self.events_table.get(event_id)
            return record
        except Exception as e:
            print(f"Error retrieving event {event_id} from Airtable: {e}")
            return None

    def add_guest(self, event_id_fk: str, guest_data: dict) -> str | None:
        """
        Adds a new guest record linked to an event.

        Args:
            event_id_fk (str): The foreign key (record ID) of the event this guest belongs to.
            guest_data (dict): A dictionary containing guest details.
                               Example: {'GuestName': 'John Doe', 'PhoneNumber': '+1234567890'}

        Returns:
            str | None: The ID of the created guest record, or None if creation failed.
        """
        try:
            guest_data['EventID_FK'] = [event_id_fk] # Link to the event
            record = self.guests_table.insert(guest_data)
            return record['id']
        except Exception as e:
            print(f"Error adding guest to Airtable: {e}")
            return None

    def add_guests_batch(self, event_id_fk: str, guests_data: list[dict]) -> list[str]:
        """
        Adds multiple guest records in a batch, linked to an event.

        Args:
            event_id_fk (str): The foreign key (record ID) of the event these guests belong to.
            guests_data (list[dict]): A list of dictionaries, each containing guest details.

        Returns:
            list[str]: A list of IDs of the created guest records. Empty if all failed.
        """
        created_guest_ids = []
        records_to_insert = []
        for guest in guests_data:
            guest['EventID_FK'] = [event_id_fk]
            records_to_insert.append({'fields': guest})
        
        try:
            # The airtable-python-wrapper's batch_insert expects a list of dicts, each with a 'fields' key
            if records_to_insert:
                created_records = self.guests_table.batch_insert(records_to_insert)
                created_guest_ids = [record['id'] for record in created_records]
        except Exception as e:
            print(f"Error batch adding guests to Airtable: {e}")
        return created_guest_ids

    def get_guests_for_event(self, event_id_fk: str) -> list[dict]:
        """
        Retrieves all guest records linked to a specific event.

        Args:
            event_id_fk (str): The foreign key (record ID) of the event.

        Returns:
            list[dict]: A list of guest records.
        """
        try:
            # Formula to filter by linked record ID. Adjust if your linked field name is different.
            # This assumes 'EventID_FK' is a link to record field in the Guests table.
            formula = f"FIND('{event_id_fk}', ARRAYJOIN({{EventID_FK}}))"
            records = self.guests_table.get_all(formula=formula)
            return records
        except Exception as e:
            print(f"Error retrieving guests for event {event_id_fk} from Airtable: {e}")
            return []

    def find_guest_by_phone(self, phone_number: str, event_id_fk: str | None = None) -> dict | None:
        """
        Finds a guest by their phone number, optionally within a specific event.

        Args:
            phone_number (str): The phone number of the guest.
            event_id_fk (str, optional): The event ID to scope the search. Defaults to None.

        Returns:
            dict | None: The guest record if found, otherwise None.
        """
        try:
            formula_parts = [f"{{PhoneNumber}} = '{phone_number}'"]
            if event_id_fk:
                formula_parts.append(f"FIND('{event_id_fk}', ARRAYJOIN({{EventID_FK}}))")
            
            formula = f"AND({', '.join(formula_parts)})"
            records = self.guests_table.get_all(formula=formula, max_records=1)
            return records[0] if records else None
        except Exception as e:
            print(f"Error finding guest by phone '{phone_number}': {e}")
            return None

    def update_guest_call_status(self, guest_id: str, call_status: str) -> bool:
        """
        Updates the call status for a specific guest.

        Args:
            guest_id (str): The ID of the guest record.
            call_status (str): The new call status (e.g., 'Called', 'Answered').

        Returns:
            bool: True if update was successful, False otherwise.
        """
        try:
            self.guests_table.update(guest_id, {'CallStatus': call_status})
            return True
        except Exception as e:
            print(f"Error updating guest {guest_id} call status to '{call_status}': {e}")
            return False

    def log_rsvp(self, guest_id_fk: str, event_id_fk: str, rsvp_status: str, notes: str = "") -> str | None:
        """
        Logs an RSVP response for a guest.

        Args:
            guest_id_fk (str): The foreign key (record ID) of the guest.
            event_id_fk (str): The foreign key (record ID) of the event.
            rsvp_status (str): The RSVP status (e.g., 'Yes', 'No', 'Maybe').
            notes (str, optional): Additional notes from the RSVP. Defaults to "".

        Returns:
            str | None: The ID of the created RSVP record, or None if creation failed.
        """
        try:
            rsvp_data = {
                'GuestID_FK': [guest_id_fk],
                'EventID_FK': [event_id_fk],
                'RSVP_Status': rsvp_status,
                'Notes': notes
            }
            record = self.rsvps_table.insert(rsvp_data)
            return record['id']
        except Exception as e:
            print(f"Error logging RSVP for guest {guest_id_fk} to Airtable: {e}")
            return None

# Example Usage (for testing purposes)
if __name__ == '__main__':
    # Ensure you have a .env file with your Airtable credentials in the project root
    # or that environment variables are set.
    if not config.AIRTABLE_API_KEY or not config.AIRTABLE_BASE_ID:
        print("Airtable API Key or Base ID not found in config. Please set them.")
    else:
        client = AirtableClient(api_key=config.AIRTABLE_API_KEY, base_id=config.AIRTABLE_BASE_ID)
        print("AirtableClient initialized.")

        # --- Test Event Creation ---
        # print("\n--- Testing Event Creation ---")
        # new_event_data = {
        #     'EventType': 'Test Event',
        #     'EventDate': '2024-07-30',
        #     'Location': 'Virtual',
        #     'UserEmail': 'test@example.com',
        #     'Status': 'Pending'
        # }
        # event_id = client.create_event(new_event_data)
        # if event_id:
        #     print(f"Event created with ID: {event_id}")
        #     retrieved_event = client.get_event(event_id)
        #     print(f"Retrieved event: {retrieved_event}")
        # else:
        #     print("Failed to create event.")

        # --- Test Guest Addition (assuming an event_id exists) ---
        # mock_event_id = "recXXXXXXXXXXXXXX" # Replace with an actual event ID from your base
        # if event_id: # Use the one created above if successful
        #    mock_event_id = event_id
        
        # if mock_event_id != "recXXXXXXXXXXXXXX":
        #     print(f"\n--- Testing Guest Addition to Event ID: {mock_event_id} ---")
        #     guest1_data = {'GuestName': 'Alice Test', 'PhoneNumber': '+1111111111'}
        #     guest1_id = client.add_guest(mock_event_id, guest1_data)
        #     if guest1_id:
        #         print(f"Guest 'Alice Test' added with ID: {guest1_id}")
        #     else:
        #         print("Failed to add guest 'Alice Test'.")

        #     guests_batch_data = [
        #         {'GuestName': 'Bob Batch', 'PhoneNumber': '+2222222222'},
        #         {'GuestName': 'Charlie Batch', 'PhoneNumber': '+3333333333'}
        #     ]
        #     batch_guest_ids = client.add_guests_batch(mock_event_id, guests_batch_data)
        #     if batch_guest_ids:
        #         print(f"Batch guests added with IDs: {batch_guest_ids}")
        #     else:
        #         print("Failed to batch add guests.")

        #     print(f"\n--- Retrieving guests for Event ID: {mock_event_id} ---")
        #     event_guests = client.get_guests_for_event(mock_event_id)
        #     print(f"Guests for event {mock_event_id}: {len(event_guests)} found.")
        #     for g in event_guests:
        #         print(f"  - {g['fields'].get('GuestName')}, Phone: {g['fields'].get('PhoneNumber')}, ID: {g['id']}")

        #     # --- Test RSVP Logging (assuming guest1_id exists) ---
        #     if guest1_id:
        #         print(f"\n--- Testing RSVP Logging for Guest ID: {guest1_id} ---")
        #         rsvp_id = client.log_rsvp(guest1_id, mock_event_id, 'Yes', 'Excited to come!')
        #         if rsvp_id:
        #             print(f"RSVP logged with ID: {rsvp_id}")
        #         else:
        #             print("Failed to log RSVP.")
                
        #         print(f"\n--- Testing Guest Update for Guest ID: {guest1_id} ---")
        #         if client.update_guest_call_status(guest1_id, 'Called - Answered'):
        #             print(f"Guest {guest1_id} status updated.")
        #             updated_guest = client.guests_table.get(guest1_id)
        #             print(f"Updated guest status: {updated_guest['fields'].get('CallStatus')}")
        #         else:
        #             print(f"Failed to update guest {guest1_id} status.")
        # else:
        #     print("\nSkipping guest and RSVP tests as no valid event_id was available.")
        #     print("Please create an event manually or uncomment event creation test and run again.")

        print("\n--- Testing Find Guest by Phone ---")
        # Replace with a phone number and event_id that exists in your test base
        # found_guest = client.find_guest_by_phone('+1111111111', event_id_fk=mock_event_id if 'mock_event_id' in locals() else None)
        # if found_guest:
        #     print(f"Found guest by phone: {found_guest['fields'].get('GuestName')}")
        # else:
        #     print("Guest not found by phone (this is expected if data doesn't exist or tests above are commented).")
        pass # Add more specific tests as needed