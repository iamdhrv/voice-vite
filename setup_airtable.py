"""
Script to set up the Airtable base for VoiceVite.

Creates the Events, Guests, and RSVPs tables with the required fields and relationships.
"""
import os
from pyairtable import Api
from config import config

api = Api(config.AIRTABLE_PERSONAL_ACCESS_TOKEN)
base_id = config.AIRTABLE_BASE_ID

def create_table_if_not_exists(base_obj, table_name: str, fields: list[dict]) -> str:
    try:
        schema = base_obj.schema()
        for table_schema in schema.tables:
            if table_schema.name == table_name:
                print(f"Table '{table_name}' already exists with ID: {table_schema.id}")
                return table_schema.id
        print(f"Creating table '{table_name}' with fields: {fields}")
        created_table_meta = base_obj.create_table(table_name, fields)
        print(f"Created table '{table_name}' with ID: {created_table_meta.id}")
        return created_table_meta.id
    except Exception as e:
        print(f"Error creating table '{table_name}': {e}")
        return None

def main():
    if not config.AIRTABLE_PERSONAL_ACCESS_TOKEN or not config.AIRTABLE_BASE_ID:
        print("Airtable personal access token and base ID are required in config.")
        return

    base_object = api.base(base_id) 

    # Create Events table
    events_fields = [
        {"name": "EventType", "type": "singleLineText"},
        {"name": "EventDate", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
        {"name": "Location", "type": "singleLineText"},
        {"name": "CulturalPreferences", "type": "multilineText"},
        {"name": "UserEmail", "type": "email"},
        {"name": "VoiceSampleID", "type": "singleLineText"},
        {"name": "Status", "type": "singleSelect", "options": {"choices": [
            {"name": "Pending"}, {"name": "Completed"}, {"name": "Failed"}
        ]}},
        {"name": "GuestListCSVPath", "type": "singleLineText"}
    ]
    events_table_id = create_table_if_not_exists(base_object, "Events", events_fields)
    if not events_table_id: return

    # Create Guests table with EventID as multipleRecordLinks
    guests_fields = [
        {
            "name": "EventID",
            "type": "multipleRecordLinks",
            "options": {
                "linkedTableId": events_table_id
            }
        },
        {"name": "GuestName", "type": "singleLineText"},
        {"name": "PhoneNumber", "type": "phoneNumber"},
        {"name": "CallStatus", "type": "singleSelect", "options": {"choices": [
            {"name": "Not Called"}, {"name": "Called - Initiated"},
            {"name": "Called - RSVP Received"}, {"name": "Failed - API Error"}
        ]}}
    ]
    guests_table_id = create_table_if_not_exists(base_object, "Guests", guests_fields)
    if not guests_table_id: return

    # Create RSVPs table with GuestID and EventID as multipleRecordLinks
    rsvps_fields = [
        {
            "name": "GuestID",
            "type": "multipleRecordLinks",
            "options": {
                "linkedTableId": guests_table_id
            }
        },
        {
            "name": "EventID",
            "type": "multipleRecordLinks",
            "options": {
                "linkedTableId": events_table_id
            }
        },
        {
            "name": "Response",
            "type": "singleSelect",
            "options": {"choices": [
                {"name": "Yes"}, {"name": "No"}, {"name": "Maybe"}, {"name": "No Response"}
            ]}
        }
    ]
    rsvps_table_id = create_table_if_not_exists(base_object, "RSVPs", rsvps_fields)
    if not rsvps_table_id: return

    print("\nAirtable base setup script finished successfully.")

if __name__ == "__main__":
    main()