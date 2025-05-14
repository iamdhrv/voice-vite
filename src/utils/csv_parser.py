"""
CSV Parsing utility for VoiceVite.

Handles reading and validating guest data from uploaded CSV files.
"""
import csv

def parse_csv_to_guests(csv_file_path: str) -> list[dict]:
    """
    Parses a CSV file containing guest information.

    Expected CSV format:
    Header: GuestName,PhoneNumber (or Name,Phone)
    Rows: John Doe,+1234567890

    Args:
        csv_file_path (str): The path to the CSV file.

    Returns:
        list[dict]: A list of dictionaries, where each dictionary represents a guest
                    with 'GuestName' and 'PhoneNumber' keys. Returns an empty list
                    if the file is not found, is empty, or has parsing errors.
    """
    guests = []
    try:
        with open(csv_file_path, mode='r', encoding='utf-8-sig') as file: # utf-8-sig handles BOM
            reader = csv.DictReader(file)
            
            # Try to determine header names flexibly
            fieldnames = reader.fieldnames
            if not fieldnames:
                print(f"Warning: CSV file '{csv_file_path}' is empty or has no headers.")
                return []

            name_col = None
            phone_col = None

            # Common variations for column names
            name_keys = ['guestname', 'name', 'full name', 'guest name']
            phone_keys = ['phonenumber', 'phone', 'contact number', 'mobile number']

            for field in fieldnames:
                if field.lower().strip().replace(' ', '') in name_keys:
                    name_col = field
                elif field.lower().strip().replace(' ', '') in phone_keys:
                    phone_col = field
            
            if not name_col or not phone_col:
                print(f"Error: CSV file '{csv_file_path}' must contain headers for guest name and phone number.")
                print(f"Expected something like 'GuestName'/'Name' and 'PhoneNumber'/'Phone'. Found: {fieldnames}")
                return []

            for row in reader:
                guest_name = row.get(name_col, '').strip()
                phone_number = row.get(phone_col, '').strip()

                if guest_name and phone_number:
                    guests.append({'GuestName': guest_name, 'PhoneNumber': phone_number})
                elif not guest_name and not phone_number:
                    # Skip entirely empty rows silently
                    continue
                else:
                    print(f"Warning: Skipping row due to missing data in '{csv_file_path}': Name='{guest_name}', Phone='{phone_number}'")
                    
    except FileNotFoundError:
        print(f"Error: CSV file not found at '{csv_file_path}'.")
        return []
    except Exception as e:
        print(f"Error parsing CSV file '{csv_file_path}': {e}")
        return []
    
    if not guests:
        print(f"Warning: No valid guest data found in '{csv_file_path}'.")

    return guests

# Example Usage (for testing purposes)
if __name__ == '__main__':
    import os
    # Create a dummy CSV for testing
    dummy_csv_path = 'dummy_guests.csv'
    dummy_data_valid = [
        ['GuestName', 'PhoneNumber'],
        ['Alice Wonderland', '+11234567890'],
        ['Bob The Builder', '+10987654321'],
        ['Charlie Brown', ''], # Missing phone
        ['', '+15555555555'], # Missing name
        ['Eve Valid', '+17778889999']
    ]
    dummy_data_alt_headers = [
        ['Name', ' Phone '], # Note extra spaces in ' Phone '
        ['Diana Prince', '+12223334444'],
        ['Clark Kent', '+14445556666']
    ]
    dummy_data_empty = [['Name', 'Phone']]
    dummy_data_no_valid_headers = [['Person', 'Contact']]

    def create_dummy_csv(path, data):
        with open(path, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerows(data)

    print("--- Testing with valid CSV ---")
    create_dummy_csv(dummy_csv_path, dummy_data_valid)
    parsed_guests = parse_csv_to_guests(dummy_csv_path)
    print(f"Parsed guests: {parsed_guests}")
    assert len(parsed_guests) == 3 # Alice, Bob, Eve
    os.remove(dummy_csv_path)

    print("\n--- Testing with alternative headers ---")
    create_dummy_csv(dummy_csv_path, dummy_data_alt_headers)
    parsed_guests_alt = parse_csv_to_guests(dummy_csv_path)
    print(f"Parsed guests (alt headers): {parsed_guests_alt}")
    assert len(parsed_guests_alt) == 2 # Diana, Clark
    os.remove(dummy_csv_path)

    print("\n--- Testing with empty data CSV ---")
    create_dummy_csv(dummy_csv_path, dummy_data_empty)
    parsed_guests_empty = parse_csv_to_guests(dummy_csv_path)
    print(f"Parsed guests (empty data): {parsed_guests_empty}")
    assert len(parsed_guests_empty) == 0
    os.remove(dummy_csv_path)

    print("\n--- Testing with CSV with no valid headers ---")
    create_dummy_csv(dummy_csv_path, dummy_data_no_valid_headers)
    parsed_guests_no_valid_headers = parse_csv_to_guests(dummy_csv_path)
    print(f"Parsed guests (no valid headers): {parsed_guests_no_valid_headers}")
    assert len(parsed_guests_no_valid_headers) == 0
    os.remove(dummy_csv_path)

    print("\n--- Testing with non-existent file ---")
    parsed_guests_non_existent = parse_csv_to_guests('non_existent_file.csv')
    print(f"Parsed guests (non-existent): {parsed_guests_non_existent}")
    assert len(parsed_guests_non_existent) == 0

    print("\nAll tests seem to pass based on assertions.")