"""
Main Flask application for VoiceVite.

Handles web form submissions, CSV uploads, and initiates voice cloning and call processes.
"""
import os
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from werkzeug.utils import secure_filename

from config import config
# from src.airtable_integration.client import AirtableClient # To be uncommented when implemented
# from src.utils.csv_parser import parse_csv_to_guests # To be uncommented when implemented
# from src.voice_cloning.eleven_labs_handler import ElevenLabsHandler # To be uncommented when implemented
# from src.call_handling.vapi_handler import VapiHandler # To be uncommented when implemented

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
app.config['UPLOAD_FOLDER'] = config.UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload size

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# # Initialize clients (uncomment as they are implemented)
# airtable_client = AirtableClient(api_key=config.AIRTABLE_API_KEY, 
#                                  base_id=config.AIRTABLE_BASE_ID)
# eleven_labs_handler = ElevenLabsHandler(api_key=config.ELEVENLABS_API_KEY)
# vapi_handler = VapiHandler(api_key=config.VAPI_API_KEY)

def allowed_file(filename):
    """Checks if the uploaded file has an allowed extension (CSV)."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in config.ALLOWED_EXTENSIONS

@app.route('/', methods=['GET', 'POST'])
def index():
    """Handles the main page with the event creation form and CSV upload."""
    if request.method == 'POST':
        # --- Event Details --- 
        event_type = request.form.get('event_type')
        event_date = request.form.get('event_date')
        event_time = request.form.get('event_time')
        location = request.form.get('location')
        cultural_preferences = request.form.get('cultural_preferences')
        user_email = request.form.get('user_email')
        
        # --- Voice Sample (Placeholder for actual voice cloning step) ---
        # For MVP, we might assume voice is pre-cloned or handle it separately.
        # This form could collect a reference to a voice ID or trigger a separate process.
        voice_sample_id = "placeholder_voice_id" # This would come from ElevenLabs integration

        # --- Guest List CSV --- 
        if 'guest_list_csv' not in request.files:
            flash('No guest list file part', 'error')
            return redirect(request.url)
        file = request.files['guest_list_csv']
        
        if file.filename == '':
            flash('No selected file for guest list', 'error')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            csv_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(csv_path)
            flash(f'Guest list "{filename}" uploaded successfully!', 'success')

            # --- Process Data (Simulated) ---
            # 1. Save Event to Airtable
            event_data = {
                'EventType': event_type,
                'EventDate': event_date,
                # 'EventTime': event_time, # Combine with date or handle as separate field
                'Location': location,
                'CulturalPreferences': cultural_preferences,
                'UserEmail': user_email,
                'VoiceSampleID': voice_sample_id,
                'GuestListCSVPath': csv_path, # Store path or parse and store guests
                'Status': 'Pending'
            }
            # event_record_id = airtable_client.create_event(event_data) # Uncomment when implemented
            event_record_id = "mock_event_id_123" # Mocked for now
            print(f"Event data to save: {event_data}")
            print(f"Mock Event Record ID: {event_record_id}")

            # 2. Parse CSV and Save Guests to Airtable
            # guests = parse_csv_to_guests(csv_path) # Uncomment when implemented
            # if event_record_id and guests:
            #     airtable_client.add_guests_to_event(event_record_id, guests) # Uncomment when implemented
            #     flash(f'{len(guests)} guests processed from CSV.', 'info')
            print(f"CSV saved to: {csv_path}")

            # 3. (Later) Trigger voice cloning if not done

            # 4. (Later) Trigger outbound calls via Vapi
            # vapi_handler.initiate_calls_for_event(event_record_id) # Uncomment when implemented

            return redirect(url_for('success', event_id=event_record_id))
        else:
            flash('Invalid file type. Please upload a CSV file.', 'error')
            return redirect(request.url)

    return render_template('index.html')

@app.route('/success')
def success():
    """Displays a success message after form submission."""
    event_id = request.args.get('event_id')
    # You could fetch event details here using event_id if needed
    return render_template('success.html', event_id=event_id)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serves uploaded files. For debugging/temporary access if needed."""
    # In a production environment, you'd likely serve static files through Nginx or a CDN.
    # This is mainly for development or if you need to provide a download link for uploaded files.
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# --- Additional routes for voice training, Vapi webhooks, etc. will be added here ---

@app.route('/webhook/vapi', methods=['POST'])
def vapi_webhook():
    """
    Handles incoming webhooks from Vapi (e.g., call status, RSVP data).
    """
    data = request.json
    print(f"Received Vapi webhook: {data}")
    
    # Process the webhook data:
    # - Identify the call (e.g., via a call ID or guest ID passed in metadata)
    # - Extract RSVP status (yes/no/maybe)
    # - Update Airtable (Guests table with call status, RSVPs table with RSVP)
    
    # Example: (This is highly dependent on Vapi's payload structure)
    # call_id = data.get('callId')
    # guest_phone_number = data.get('phoneNumber') # Or some other identifier
    # rsvp_response = data.get('transcript') # Or a specific field for structured response

    # guest_record = airtable_client.find_guest_by_phone(guest_phone_number) # Implement this
    # if guest_record:
    #     parsed_rsvp = parse_rsvp_from_transcript(rsvp_response) # Implement this
    #     airtable_client.log_rsvp(guest_record['id'], guest_record['fields']['EventID_FK'][0], parsed_rsvp) # Implement this
    #     airtable_client.update_guest_call_status(guest_record['id'], 'Called - RSVP Received') # Implement this

    return jsonify({'status': 'success'}), 200

if __name__ == '__main__':
    app.run(debug=config.DEBUG, port=5000)