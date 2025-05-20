"""
Main Flask application for VoiceVite.

Handles web form submissions, CSV uploads, voice training, and initiates outbound calls.
"""
import os
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, jsonify, session
from werkzeug.utils import secure_filename
import logging

from config import config
from src.airtable_integration.client import AirtableClient
from src.utils.csv_parser import parse_csv_to_guests
from src.voice_cloning.eleven_labs_handler import ElevenLabsHandler
from src.call_handling.vapi_handler import VapiHandler
from src.voice_cloning.lmnt_handler import create_custom_voice

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
app.config['UPLOAD_FOLDER'] = config.UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload size
app.config['ALLOWED_EXTENSIONS'] = {'wav', 'mp3', 'mp4', 'm4a', 'webm'}  # For voice uploads

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize clients
airtable_client = AirtableClient(personal_access_token=config.AIRTABLE_PERSONAL_ACCESS_TOKEN, base_id=config.AIRTABLE_BASE_ID)
eleven_labs_handler = ElevenLabsHandler(api_key=config.ELEVENLABS_API_KEY)
vapi_handler = VapiHandler(api_key=config.VAPI_API_KEY)

def allowed_file(filename, allowed_extensions=config.ALLOWED_EXTENSIONS):
    """Checks if the uploaded file has an allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def initiate_vapi_call(event_id, guest_id, guest_name, phone_number, voice_sample_id, event_details, voice_choice='male'):
    """Initiates a Vapi call to a guest with the specified voice and event details."""
    try:
        call_id = vapi_handler.make_outbound_call(
            phone_number=phone_number,
            assistant_id=config.VAPI_ASSISTANT_ID,
            guest_name=guest_name,
            event_details=event_details,
            guest_id_airtable=guest_id,
            voice_choice=voice_choice
        )

        if call_id:
            airtable_client.update_guest_call_status(guest_id, 'Called - Initiated')
            logger.debug(f"Vapi call initiated to {phone_number}: {call_id}")
        else:
            airtable_client.update_guest_call_status(guest_id, 'Failed - API Error')
    except Exception as e:
        logger.error(f"Error initiating Vapi call to {phone_number}: {e}")
        airtable_client.update_guest_call_status(guest_id, 'Failed - API Error')

@app.route('/', methods=['GET', 'POST'])
def index():
    """Handles Step 1: Event Details (Part 1)."""
    if request.method == 'POST':
        host_name = request.form.get('host_name')
        event_type = request.form.get('event_type')
        event_date = request.form.get('event_date')
        event_time = request.form.get('event_time')
        duration = request.form.get('duration')

        if not all([host_name, event_type, event_date, event_time, duration]):
            flash('Please fill in all required fields.', 'error')
            return redirect(url_for('index'))

        session['event_details'] = {
            'host_name': host_name,
            'event_type': event_type,
            'event_date': event_date,
            'event_time': event_time,
            'duration': duration
        }
        return redirect(url_for('voice_selection'))

    return render_template('index.html')

@app.route('/voice-selection', methods=['GET', 'POST'])
def voice_selection():
    """Handles Step 2: Voice Selection."""
    if request.method == 'POST':
        voice_choice = request.form.get('voice_choice')
        if not voice_choice:
            flash('Please select a voice option.', 'error')
            return redirect(url_for('voice_selection'))
        session['voice_choice'] = voice_choice
        if voice_choice == 'custom':
            return redirect(url_for('voice_training'))
        return redirect(url_for('event_details_step2'))

    return render_template('voice_selection.html')

@app.route('/voice-training', methods=['GET', 'POST'])
def voice_training():
    """Handles voice training for custom voice selection using LMNT API."""
    if request.method == 'POST':
        try:
            # Check if either file upload or recording is provided
            has_upload = 'audio' in request.files and request.files['audio'].filename != ''
            has_recording = 'audio_blob' in request.files and request.files['audio_blob'].filename != ''

            if not (has_upload or has_recording):
                flash('Please either upload an audio file or record your voice.', 'error')
                return redirect(url_for('voice_training'))

            if has_upload and has_recording:
                flash('Please choose only one option: upload an audio file or record your voice.', 'error')
                return redirect(url_for('voice_training'))

            # Get host name from session for voice naming
            host_name = session.get('event_details', {}).get('host_name', 'CustomVoice')

            # Handle file upload
            if has_upload:
                audio_file = request.files['audio']
                if not allowed_file(audio_file.filename, app.config['ALLOWED_EXTENSIONS']):
                    flash('Invalid audio file type. Supported formats: WAV, MP3, MP4, M4A, WEBM', 'error')
                    return redirect(url_for('voice_training'))

                filename = secure_filename(audio_file.filename)
                audio_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                audio_file.save(audio_path)

            # Handle recording
            else:
                audio_blob = request.files['audio_blob']
                filename = f"{host_name}_recording.wav"
                audio_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                audio_blob.save(audio_path)

            lmnt_api_key = os.getenv('LMNT_API_KEY')
            if not lmnt_api_key:
                flash('LMNT API key not set. Please configure it in .env.', 'error')
                logger.error("LMNT API key not set")
                return redirect(url_for('voice_training'))

            # Create voice using LMNT API
            voice_id = create_custom_voice(audio_path, host_name, lmnt_api_key)
            if voice_id:
                session['voice_sample_id'] = voice_id
                logger.debug(f"Set session['voice_sample_id'] to: {voice_id}")
                flash('Custom voice created successfully!', 'success')
                return redirect(url_for('event_details_step2'))
            else:
                flash('Failed to create custom voice.', 'error')
                return redirect(url_for('voice_training'))

        except Exception as e:
            logger.error(f"Error processing voice training: {str(e)}")
            flash(f'Error processing voice training: {str(e)}', 'error')
            return redirect(url_for('voice_training'))

    return render_template('voice_training.html')

@app.route('/event-details-step2', methods=['GET', 'POST'])
def event_details_step2():
    """Handles Step 3: Event Details (Part 2) and Submission."""
    logger.debug(f"Session data in event_details_step2: {session}")
    if request.method == 'POST':
        location = request.form.get('location')
        user_email = request.form.get('email')
        cultural_preferences = request.form.get('cultural_prefs')
        special_instructions = request.form.get('special_instructions')
        rsvp_deadline = request.form.get('rsvp_deadline')
        guest_input_method = request.form.get('guest_input_method')

        if not all([location, user_email, rsvp_deadline, guest_input_method]):
            flash('Please fill in all required fields.', 'error')
            return redirect(url_for('event_details_step2'))

        # Retrieve previous data from session
        voice_choice = session.get('voice_choice')
        voice_sample_id = session.get('voice_sample_id') if voice_choice == 'custom' else (
            'male_voice_id' if voice_choice == 'male' else 'female_voice_id'  # Replace with actual voice IDs
        )
        logger.debug(f"Retrieved voice_sample_id: {voice_sample_id}")
        event_details_part1 = session.get('event_details', {})

        # Prepare event details for Vapi call
        event_details = {
            "eventId": "",
            "voiceSampleId": voice_sample_id,
            "hostName": event_details_part1.get('host_name'),
            "eventType": event_details_part1.get('event_type'),
            "eventDate": event_details_part1.get('event_date'),
            "eventTime": event_details_part1.get('event_time'),
            "location": location,
            "culturalPreferences": cultural_preferences or "",
            "duration": event_details_part1.get('duration'),
            "specialInstructions": special_instructions or "",
            "rsvpDeadline": rsvp_deadline
        }

        # Prepare event data for Airtable
        event_data = {
            'HostName': event_details_part1.get('host_name'),
            'EventType': event_details_part1.get('event_type'),
            'EventDate': event_details_part1.get('event_date'),
            'EventTime': event_details_part1.get('event_time'),
            'Duration': event_details_part1.get('duration'),
            'Location': location,
            'CulturalPreferences': cultural_preferences,
            'SpecialInstructions': special_instructions,
            'RSVPDeadline': rsvp_deadline,
            'UserEmail': user_email,
            'VoiceSampleID': voice_sample_id,
            'Status': 'Pending',
            'GuestListCSVPath': None
        }

        if guest_input_method == 'manual':
            guest_names = request.form.getlist('guest_name[]')
            guest_phones = request.form.getlist('guest_phone[]')
            if not guest_names or not guest_phones or len(guest_names) != len(guest_phones):
                flash('Please provide both name and phone number for each guest.', 'error')
                return redirect(url_for('event_details_step2'))
            
            # Validate phone numbers
            for name, phone in zip(guest_names, guest_phones):
                if not name or not phone:
                    flash('Guest name and phone number cannot be empty.', 'error')
                    return redirect(url_for('event_details_step2'))
                if not phone.startswith('+') or not phone[1:].isdigit():
                    flash('Phone number must be in E.164 format (e.g., +919876543210).', 'error')
                    return redirect(url_for('event_details_step2'))
            
            event_data['GuestListCSVPath'] = None
            event_id = airtable_client.create_event(event_data)
            if not event_id:
                flash('Failed to create event in Airtable.', 'error')
                return redirect(url_for('event_details_step2'))
            event_details["eventId"] = event_id
            
            # Add multiple guests
            guests = [{'GuestName': name, 'PhoneNumber': phone} for name, phone in zip(guest_names, guest_phones)]
            guest_ids = airtable_client.add_guests_batch(event_id, guests)
            if not guest_ids:
                flash('Failed to add guests to Airtable.', 'error')
                return redirect(url_for('event_details_step2'))
            
            # Initiate Vapi calls for each guest
            for guest, guest_id in zip(guests, guest_ids):
                initiate_vapi_call(
                    event_id, guest_id, guest['GuestName'], guest['PhoneNumber'],
                    voice_sample_id, event_details, voice_choice
                )
            flash(f'{len(guests)} guests added manually.', 'info')
        else:  # CSV Upload
            if 'guest_list' not in request.files:
                flash('No guest list file part', 'error')
                return redirect(url_for('event_details_step2'))
            file = request.files['guest_list']
            if file.filename == '':
                flash('No selected file for guest list', 'error')
                return redirect(url_for('event_details_step2'))
            if file and allowed_file(file.filename, config.ALLOWED_EXTENSIONS):
                filename = secure_filename(file.filename)
                csv_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(csv_path)
                event_data['GuestListCSVPath'] = csv_path
                event_id = airtable_client.create_event(event_data)
                if not event_id:
                    flash('Failed to create event in Airtable.', 'error')
                    return redirect(url_for('event_details_step2'))
                event_details["eventId"] = event_id
                guests = parse_csv_to_guests(csv_path)
                if not guests:
                    flash('No valid guests found in CSV.', 'error')
                    return redirect(url_for('event_details_step2'))
                guest_ids = airtable_client.add_guests_batch(event_id, guests)
                flash(f'{len(guests)} guests processed from CSV.', 'info')
                for guest, guest_id in zip(guests, guest_ids):
                    initiate_vapi_call(
                        event_id, guest_id, guest['GuestName'], guest['PhoneNumber'],
                        voice_sample_id, event_details, voice_choice
                    )
            else:
                flash('Invalid file type. Please upload a CSV file.', 'error')
                return redirect(url_for('event_details_step2'))

        # Clear session data after successful submission
        session.pop('voice_choice', None)
        session.pop('voice_sample_id', None)
        session.pop('event_details', None)
        return redirect(url_for('success', event_id=event_id))

    return render_template('event_details_step2.html')

@app.route('/vapi/callback', methods=['POST'])
def vapi_callback():
    """Handles Vapi callback to log RSVP responses."""
    data = request.json
    logger.debug(f"Vapi callback received: {data}")

    call_status = data.get("status")
    guest_id = data.get("metadata", {}).get("guestId")
    event_id = data.get("metadata", {}).get("eventId")
    response = data.get("transcription")

    if call_status == "ended":
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

@app.route('/webhook', methods=['POST'])
def webhook():
    """Webhook endpoint to log Vapi events."""
    event_data = request.get_json()
    logger.debug("-------------------------------------------------")
    logger.debug(f"Received Vapi event: {event_data}")

    message = event_data.get('message', event_data)
    event_type = message.get('type')

    if event_type == 'status-update':
        status = message.get('status')
        if status == 'ended':
            call_details = message.get('call')
            ended_reason = message.get('endedReason')
            logger.debug(f"Call ended: {call_details} due to {ended_reason}")
    elif event_type == 'end-of-call-report':
        call_details = message.get('call')
        analysis = message.get('analysis', {})
        guest_id = call_details.get('metadata', {}).get('guestId')
        event_id = call_details.get('metadata', {}).get('eventId')
        class Response:
            def __init__(self, summary, structured_data):
                self.summary = summary
                self.structuredData = structured_data

        response = Response(
            summary=analysis.get('summary', ''),
            structured_data=analysis.get('structuredData', {})
        )
        logger.debug(f"Call Report: {analysis}")
        logger.debug(f"Structured Data: {response.structuredData}")
        if guest_id and event_id and response:
            airtable_client.log_rsvp(guest_id, event_id, response)
            airtable_client.update_guest_call_status(guest_id, "Called - RSVP Received")
            logger.debug(f"RSVP logged for guest {guest_id} and event {event_id}")
        else:
            logger.debug("Missing guest_id, event_id, or response data in end-of-call-report")

    return jsonify({'status': 'Event received'}), 200

if __name__ == '__main__':
    app.run(debug=config.DEBUG, port=5000)