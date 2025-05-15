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

def initiate_vapi_call(event_id, guest_id, guest_name, phone_number, voice_sample_id):
    """Initiates a Vapi call to a guest with the specified voice."""
    try:
        call_id = vapi_handler.make_outbound_call(
            phone_number=phone_number,
            assistant_id=config.VAPI_ASSISTANT_ID,
            guest_name=guest_name,
            event_details={
                "eventId": event_id,
                "voiceSampleId": voice_sample_id
            },
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

        event_type = request.form.get('event_type')
        event_date = request.form.get('event_date')
        location = request.form.get('location')
        cultural_preferences = request.form.get('cultural_prefs')
        user_email = request.form.get('email')
        guest_input_method = request.form.get('guest_input_method')

        event_data = {
            'EventType': event_type,
            'EventDate': event_date,
            'Location': location,
            'CulturalPreferences': cultural_preferences,
            'UserEmail': user_email,
            'VoiceSampleID': voice_sample_id,
            'Status': 'Pending'
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
            guest_id = airtable_client.add_guest(event_id, {'GuestName': guest_name, 'PhoneNumber': guest_phone})
            if not guest_id:
                flash('Failed to add guest to Airtable.', 'error')
                return redirect(request.url)
            # Initiate Vapi call
            initiate_vapi_call(event_id, guest_id, guest_name, guest_phone, voice_sample_id)
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
                guests = parse_csv_to_guests(csv_path)
                if not guests:
                    flash('No valid guests found in CSV.', 'error')
                    return redirect(request.url)
                guest_ids = airtable_client.add_guests_batch(event_id, guests)
                flash(f'{len(guests)} guests processed from CSV.', 'info')
                for guest, guest_id in zip(guests, guest_ids):
                    initiate_vapi_call(event_id, guest_id, guest['GuestName'], guest['PhoneNumber'], voice_sample_id)
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

if __name__ == '__main__':
    app.run(debug=config.DEBUG, port=5000)