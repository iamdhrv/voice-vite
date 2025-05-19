"""
Main Flask application for VoiceVite.

Handles web form submissions, CSV uploads, voice training, and initiates outbound calls.
"""
import os
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, jsonify
from werkzeug.utils import secure_filename

from config import config
from src.airtable_integration.client import AirtableClient
from src.utils.csv_parser import parse_csv_to_guests
from src.voice_cloning.eleven_labs_handler import ElevenLabsHandler
from src.call_handling.vapi_handler import VapiHandler

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
app.config['UPLOAD_FOLDER'] = config.UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload size

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize clients
airtable_client = AirtableClient(personal_access_token=config.AIRTABLE_PERSONAL_ACCESS_TOKEN, base_id=config.AIRTABLE_BASE_ID)
eleven_labs_handler = ElevenLabsHandler(api_key=config.ELEVENLABS_API_KEY)
vapi_handler = VapiHandler(api_key=config.VAPI_API_KEY)

def allowed_file(filename):
    """Checks if the uploaded file has an allowed extension (CSV)."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in config.ALLOWED_EXTENSIONS

def initiate_vapi_call(event_id, guest_id, guest_name, phone_number, voice_sample_id, event_details):
    """Initiates a Vapi call to a guest with the specified voice and event details."""
    try:
        call_id = vapi_handler.make_outbound_call(
            phone_number=phone_number,
            assistant_id=config.VAPI_ASSISTANT_ID,
            guest_name=guest_name,
            event_details=event_details,
            guest_id_airtable=guest_id
        )

        if call_id:
            airtable_client.update_guest_call_status(guest_id, 'Called - Initiated')
            print(f"Vapi call initiated to {phone_number}: {call_id}")
        else:
            airtable_client.update_guest_call_status(guest_id, 'Failed - API Error')
    except Exception as e:
        print(f"Error initiating Vapi call to {phone_number}: {e}")
        airtable_client.update_guest_call_status(guest_id, 'Failed - API Error')

@app.route('/', methods=['GET', 'POST'])
def index():
    """Handles the main page with the event creation form and CSV upload."""
    if request.method == 'POST':
        voice_sample_id = request.form.get('voice_sample_id')
        if not voice_sample_id:
            flash('Voice training must be completed before creating an event.', 'error')
            return redirect(request.url)

        host_name = request.form.get('host_name')
        event_type = request.form.get('event_type')
        event_date = request.form.get('event_date')
        event_time = request.form.get('event_time')
        duration = request.form.get('duration')
        location = request.form.get('location')
        cultural_preferences = request.form.get('cultural_prefs')
        special_instructions = request.form.get('special_instructions')
        rsvp_deadline = request.form.get('rsvp_deadline')
        user_email = request.form.get('email')
        guest_input_method = request.form.get('guest_input_method')

        # Prepare event details for Vapi call using form data
        event_details = {
            "eventId": "",  # Will be populated after creating the event
            "voiceSampleId": voice_sample_id,
            "hostName": host_name,
            "eventType": event_type,
            "eventDate": event_date,
            "eventTime": event_time,
            "location": location,
            "culturalPreferences": cultural_preferences or "",
            "duration": duration,
            "specialInstructions": special_instructions or "",
            "rsvpDeadline": rsvp_deadline
        }

        # Use field names exactly as defined in Airtable
        event_data = {
            'HostName': host_name,
            'EventType': event_type,
            'EventDate': event_date,
            'EventTime': event_time,
            'Duration': duration,
            'Location': location,
            'CulturalPreferences': cultural_preferences,
            'SpecialInstructions': special_instructions,
            'RSVPDeadline': rsvp_deadline,
            'UserEmail': user_email,
            'VoiceSampleID': voice_sample_id,
            'Status': 'Pending',
            'GuestListCSVPath': None
        }

        if guest_input_method == 'single':
            guest_name = request.form.get('guest_name')
            guest_phone = request.form.get('guest_phone')
            if not guest_name:
                flash('Please provide a guest name.', 'error')
                return redirect(request.url)
            if not guest_phone:
                flash('Please provide a guest phone number.', 'error')
                return redirect(request.url)
            if not guest_phone.startswith('+') or not guest_phone[1:].isdigit():
                flash('Phone number must be in E.164 format (e.g., +919876543210).', 'error')
                return redirect(request.url)
            event_data['GuestListCSVPath'] = None
            event_id = airtable_client.create_event(event_data)
            if not event_id:
                flash('Failed to create event in Airtable.', 'error')
                return redirect(request.url)
            print(f"Created event with ID: {event_id}")  # Debug
            event_details["eventId"] = event_id  # Update eventId in event_details
            guest_id = airtable_client.add_guest(event_id, {'GuestName': guest_name, 'PhoneNumber': guest_phone})
            if not guest_id:
                flash('Failed to add guest to Airtable.', 'error')
                return redirect(request.url)
            # Initiate Vapi call with full event details
            initiate_vapi_call(event_id, guest_id, guest_name, guest_phone, voice_sample_id, event_details)
        else:
            if 'guest_list' not in request.files:
                flash('No guest list file part', 'error')
                return redirect(request.url)
            file = request.files['guest_list']
            if file.filename == '':
                flash('No selected file for guest list', 'error')
                return redirect(request.url)
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                csv_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(csv_path)
                event_data['GuestListCSVPath'] = csv_path
                event_id = airtable_client.create_event(event_data)
                if not event_id:
                    flash('Failed to create event in Airtable.', 'error')
                    return redirect(request.url)
                print(f"Created event with ID: {event_id}")  # Debug
                event_details["eventId"] = event_id  # Update eventId in event_details
                guests = parse_csv_to_guests(csv_path)
                if not guests:
                    flash('No valid guests found in CSV.', 'error')
                    return redirect(request.url)
                guest_ids = airtable_client.add_guests_batch(event_id, guests)
                flash(f'{len(guests)} guests processed from CSV.', 'info')
                for guest, guest_id in zip(guests, guest_ids):
                    initiate_vapi_call(event_id, guest_id, guest['GuestName'], guest['PhoneNumber'], voice_sample_id, event_details)
            else:
                flash('Invalid file type. Please upload a CSV file.', 'error')
                return redirect(request.url)

        return redirect(url_for('success', event_id=event_id))

    return render_template('index.html')

@app.route('/voice-training', methods=['POST'])
def voice_training():
    """Handles the uploaded audio file for voice training."""
    try:
        if 'audio' not in request.files:
            return jsonify({"status": "error", "message": "No audio file provided"}), 400

        audio_file = request.files['audio']
        if audio_file.filename == '':
            return jsonify({"status": "error", "message": "No selected audio file"}), 400

        # Save the audio file
        filename = secure_filename(audio_file.filename)
        audio_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        audio_file.save(audio_path)

        # Use a pre-made voice since cloning isn't available
        voice_id = eleven_labs_handler.get_default_voice_id()

        return jsonify({"status": "success", "voice_sample_id": voice_id}), 200
    except Exception as e:
        print(f"Error processing voice training: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/vapi/callback', methods=['POST'])
def vapi_callback():
    """Handles Vapi callback to log RSVP responses."""
    data = request.json
    print(f"Vapi callback received: {data}")

    call_status = data.get("status")
    guest_id = data.get("metadata", {}).get("guestId")
    event_id = data.get("metadata", {}).get("eventId")
    response = data.get("transcription")  # Vapi SDK uses 'transcription' for voice input

    if call_status == "ended":  # Vapi SDK uses 'ended' for completed calls
        if response:
            rsvp_response = response.lower()
            if rsvp_response not in ["yes", "no", "maybe"]:
                rsvp_response = "No Response"
            airtable_client.log_rsvp(guest_id, event_id, rsvp_response.capitalize())
            airtable_client.update_guest_call_status(guest_id, "Called - RSVP Received")
        else:
            airtable_client.update_guest_call_status(guest_id, "Failed - No Response")
    elif call_status == "failed":
        airtable_client.update_guest_call_status(guest_id, "Failed - API Error")

    return "", 200

@app.route('/success')
def success():
    """Displays a success message after form submission."""
    event_id = request.args.get('event_id')
    return render_template('success.html', event_id=event_id)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serves uploaded files."""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# Add webhook endpoint to log Vapi events
@app.route('/webhook', methods=['POST'])
def webhook():
    """Webhook endpoint to log Vapi events."""
    # Log the entire event data
    event_data = request.get_json()
    print("-------------------------------------------------")
    print(f"Received Vapi event: {event_data}")

    # Handle specific event types
    message = event_data.get('message', event_data)  # Fallback to event_data if message is not present
    event_type = message.get('type')

    if event_type == 'status-update':
        status = message.get('status')
        if status == 'ended':
            call_details = message.get('call')
            ended_reason = message.get('endedReason')
            print(f"Call ended: {call_details} due to {ended_reason}")
    elif event_type == 'end-of-call-report':
        call_details = message.get('call')
        analysis = message.get('analysis', {})
        guest_id = call_details.get('metadata', {}).get('guestId')
        event_id = call_details.get('metadata', {}).get('eventId')
        # Create a response object that matches the expected structure for log_rsvp
        class Response:
            def __init__(self, summary, structured_data):
                self.summary = summary
                self.structuredData = structured_data

        response = Response(
            summary=analysis.get('summary', ''),
            structured_data=analysis.get('structuredData', {})
        )
        print(f"Call Report: {analysis}")
        print(f"Structured Data: {response.structuredData}")
        # Log RSVP to Airtable
        if guest_id and event_id and response:
            airtable_client.log_rsvp(guest_id, event_id, response)
            airtable_client.update_guest_call_status(guest_id, "Called - RSVP Received")
            print(f"RSVP logged for guest {guest_id} and event {event_id}")
        else:
            print("Missing guest_id, event_id, or response data in end-of-call-report")

    return jsonify({'status': 'Event received'}), 200

if __name__ == '__main__':
    app.run(debug=config.DEBUG, port=5000)