"""
Main Flask application for VoiceVite. (Refactored for PostgreSQL)

Handles web form submissions, CSV uploads, voice training, and initiates outbound calls.
"""
import os
from datetime import datetime, date, time
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, jsonify, session
from werkzeug.utils import secure_filename
import logging
import sys # For CLI table creation

from config import config
# from src.airtable_integration.client import AirtableClient # Deprecated
from src.db_access import postgres_client
from src.utils.csv_parser import parse_csv_to_guests
from src.voice_cloning.eleven_labs_handler import ElevenLabsHandler
from src.call_handling.vapi_handler import VapiHandler
from src.voice_cloning.lmnt_handler import create_custom_voice
from src.database import db, init_app as init_db_app
from src.models import Event, Guest, RSVP # Ensure models are imported

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
app.config['UPLOAD_FOLDER'] = config.UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload size
# ALLOWED_EXTENSIONS_VOICE for voice samples
app.config['ALLOWED_EXTENSIONS_VOICE'] = {'wav', 'mp3', 'mp4', 'm4a', 'webm'} 
# CSV validation will use config.ALLOWED_EXTENSIONS which is {'csv'}

app.config['SQLALCHEMY_DATABASE_URI'] = config.SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # Recommended to disable

# Initialize DB
init_db_app(app)

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize clients (Airtable client is deprecated)
# airtable_client = AirtableClient(personal_access_token=config.AIRTABLE_PERSONAL_ACCESS_TOKEN, base_id=config.AIRTABLE_BASE_ID)
eleven_labs_handler = ElevenLabsHandler(api_key=config.ELEVENLABS_API_KEY)
vapi_handler = VapiHandler(api_key=config.VAPI_API_KEY)

def allowed_file(filename, allowed_extensions_set):
    """Checks if the uploaded file has an allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions_set

def initiate_vapi_call(event_id: int, guest_id: int, guest_name: str, phone_number: str, 
                       voice_sample_id: str, event_details_for_vapi: dict, voice_choice: str = 'male'):
    """
    Initiates a Vapi call to a guest with the specified voice and event details.
    Uses PostgreSQL event_id and guest_id (integers).
    """
    try:
        # VapiHandler's make_outbound_call expects guest_id_db (int)
        call_id = vapi_handler.make_outbound_call(
            phone_number=phone_number,
            assistant_id=config.VAPI_ASSISTANT_ID, 
            guest_name=guest_name,
            event_details=event_details_for_vapi, # This dict should have stringified eventId
            guest_id_db=guest_id, # Pass integer guest_id
            voice_choice=voice_choice
        )

        if call_id:
            postgres_client.update_guest_call_status(guest_id, 'Called - Initiated')
            logger.debug(f"Vapi call initiated to {phone_number} for guest_id {guest_id}: {call_id}")
        else:
            postgres_client.update_guest_call_status(guest_id, 'Failed - API Error')
    except Exception as e:
        logger.error(f"Error initiating Vapi call to {phone_number} for guest_id {guest_id}: {e}")
        if guest_id: 
            postgres_client.update_guest_call_status(guest_id, 'Failed - API Error')

@app.route('/', methods=['GET', 'POST'])
def index():
    """Handles Step 1: Event Details (Part 1)."""
    if request.method == 'POST':
        host_name = request.form.get('host_name')
        event_type = request.form.get('event_type')
        event_date_str = request.form.get('event_date')
        event_time_str = request.form.get('event_time')
        duration = request.form.get('duration')

        if not all([host_name, event_type, event_date_str, event_time_str, duration]):
            flash('Please fill in all required fields.', 'error')
            return redirect(url_for('index'))

        session['event_details_part1'] = {
            'host_name': host_name,
            'event_type': event_type,
            'event_date': event_date_str,
            'event_time': event_time_str,
            'duration': duration
        }
        return redirect(url_for('voice_selection'))

    return render_template('index.html')

@app.route('/voice-selection', methods=['GET', 'POST'])
def voice_selection():
    """Handles Step 2: Voice Selection."""
    if 'event_details_part1' not in session:
        flash('Please complete event details first.', 'error')
        return redirect(url_for('index'))
        
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
    if 'event_details_part1' not in session or session.get('voice_choice') != 'custom':
        flash('Please complete previous steps first.', 'error')
        return redirect(url_for('voice_selection'))

    if request.method == 'POST':
        try:
            has_upload = 'audio' in request.files and request.files['audio'].filename != ''
            has_recording = 'audio_blob' in request.files and request.files['audio_blob'].filename != ''

            if not (has_upload or has_recording):
                flash('Please either upload an audio file or record your voice.', 'error')
                return redirect(url_for('voice_training'))
            if has_upload and has_recording:
                flash('Please choose only one option: upload an audio file or record your voice.', 'error')
                return redirect(url_for('voice_training'))

            host_name = session.get('event_details_part1', {}).get('host_name', 'CustomVoice')
            audio_path = ""

            if has_upload:
                audio_file = request.files['audio']
                if not allowed_file(audio_file.filename, app.config['ALLOWED_EXTENSIONS_VOICE']):
                    flash(f"Invalid audio file type. Supported formats: {', '.join(app.config['ALLOWED_EXTENSIONS_VOICE'])}", 'error')
                    return redirect(url_for('voice_training'))
                filename = secure_filename(f"{host_name}_{audio_file.filename}")
                audio_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                audio_file.save(audio_path)
            else: # has_recording
                audio_blob = request.files['audio_blob']
                filename = f"{host_name}_recording.wav" 
                audio_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                audio_blob.save(audio_path)
            
            if not config.LMNT_API_KEY: 
                flash('LMNT API key not set. Please configure it in .env.', 'error')
                logger.error("LMNT API key not set")
                return redirect(url_for('voice_training'))

            voice_id = create_custom_voice(audio_path, f"{host_name}_VoiceVite", config.LMNT_API_KEY)
            if voice_id:
                session['voice_sample_id'] = voice_id
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
    if 'event_details_part1' not in session or 'voice_choice' not in session:
        flash('Please complete previous steps first.', 'error')
        return redirect(url_for('index'))

    if request.method == 'POST':
        location = request.form.get('location')
        user_email = request.form.get('email')
        cultural_preferences = request.form.get('cultural_prefs')
        special_instructions = request.form.get('special_instructions')
        rsvp_deadline_str = request.form.get('rsvp_deadline')
        guest_input_method = request.form.get('guest_input_method')

        if not all([location, user_email, rsvp_deadline_str, guest_input_method]):
            flash('Please fill in all required fields for this step.', 'error')
            return redirect(url_for('event_details_step2'))

        event_details_part1 = session.get('event_details_part1', {})
        voice_choice = session.get('voice_choice')
        voice_sample_id = session.get('voice_sample_id') if voice_choice == 'custom' else (
            'JBFqnCBsd6RMkjVDRZzb' if voice_choice == 'male' else 'XrExE9yKIg1WjnnlVkGX' # Default Vapi 11labs voices
        )
        
        db_event_data = {
            'host_name': event_details_part1.get('host_name'),
            'event_type': event_details_part1.get('event_type'),
            'event_date': event_details_part1.get('event_date'), # String from session
            'event_time': event_details_part1.get('event_time'), # String from session
            'duration': event_details_part1.get('duration'),
            'location': location,
            'cultural_preferences': cultural_preferences,
            'special_instructions': special_instructions,
            'rsvp_deadline': rsvp_deadline_str, # String from form
            'user_email': user_email,
            'voice_sample_id': voice_sample_id,
            'status': 'Pending',
            'guest_list_csv_path': None
        }

        try:
            if isinstance(db_event_data['event_date'], str):
                db_event_data['event_date'] = datetime.strptime(db_event_data['event_date'], '%Y-%m-%d').date()
            if isinstance(db_event_data['event_time'], str):
                db_event_data['event_time'] = datetime.strptime(db_event_data['event_time'], '%H:%M').time()
            if isinstance(db_event_data['rsvp_deadline'], str):
                db_event_data['rsvp_deadline'] = datetime.strptime(db_event_data['rsvp_deadline'], '%Y-%m-%d').date()
        except ValueError as e:
            logger.error(f"Date/Time conversion error: {e}")
            flash('Invalid date or time format. Please use YYYY-MM-DD for dates and HH:MM for time.', 'error')
            return redirect(url_for('event_details_step2'))

        csv_path_to_save = None 
        if guest_input_method == 'csv':
            if 'guest_list' not in request.files or request.files['guest_list'].filename == '':
                flash('No guest list file selected for CSV upload.', 'error')
                return redirect(url_for('event_details_step2'))
            file = request.files['guest_list']
            # Using config.ALLOWED_EXTENSIONS for CSV as it's {'csv'} from config.py
            if file and allowed_file(file.filename, config.ALLOWED_EXTENSIONS): 
                filename = secure_filename(file.filename) # Use the original filename for the CSV
                csv_path_to_save = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                db_event_data['guest_list_csv_path'] = csv_path_to_save 
            else:
                flash('Invalid file type for guest list. Please upload a CSV file.', 'error')
                return redirect(url_for('event_details_step2'))
        
        created_event = postgres_client.create_event(db_event_data)
        if not created_event:
            flash('Failed to create event in database.', 'error')
            return redirect(url_for('event_details_step2'))
        event_id = created_event.id 

        if guest_input_method == 'csv' and csv_path_to_save:
            try:
                request.files['guest_list'].save(csv_path_to_save) # Save the file
                logger.info(f"Guest list CSV saved to {csv_path_to_save}")
            except Exception as e:
                logger.error(f"Failed to save CSV file {csv_path_to_save}: {e}")
                postgres_client.update_event_status(event_id, "Failed - CSV Save Error")
                flash('Error saving guest list CSV file.', 'error')
                # Not returning here, event is created, but guest processing might fail or be skipped.
        
        event_details_for_vapi = {
            "eventId": str(event_id), 
            "voiceSampleId": voice_sample_id,
            "hostName": db_event_data['host_name'],
            "eventType": db_event_data['event_type'],
            "eventDate": db_event_data['event_date'].strftime('%Y-%m-%d') if db_event_data['event_date'] else "",
            "eventTime": db_event_data['event_time'].strftime('%H:%M') if db_event_data['event_time'] else "",
            "location": db_event_data['location'],
            "culturalPreferences": db_event_data['cultural_preferences'] or "",
            "duration": db_event_data['duration'],
            "specialInstructions": db_event_data['special_instructions'] or "",
            "rsvpDeadline": db_event_data['rsvp_deadline'].strftime('%Y-%m-%d') if db_event_data['rsvp_deadline'] else ""
        }
        
        processed_guests_count = 0
        db_guests_data_for_batch = [] 

        if guest_input_method == 'manual':
            guest_names = request.form.getlist('guest_name[]')
            guest_phones = request.form.getlist('guest_phone[]')
            
            if not guest_names or not any(g_name.strip() for g_name in guest_names): 
                postgres_client.update_event_status(event_id, "Pending - No Manual Guests")
                flash('Event created, but no manual guests were provided to call.', 'info')
            else:
                for name, phone in zip(guest_names, guest_phones):
                    if not name.strip() or not phone.strip(): 
                        logger.warning(f"Skipping manual guest due to empty name or phone for event {event_id}. Name: '{name}', Phone: '{phone}'")
                        continue
                    if not phone.startswith('+') or not phone[1:].isdigit():
                        flash(f'Invalid phone number format for {name}: {phone}. Must be E.164 format (e.g., +19876543210).', 'error')
                        postgres_client.update_event_status(event_id, "Failed - Invalid Phone Format")
                        return redirect(url_for('event_details_step2'))
                    db_guests_data_for_batch.append({'guest_name': name, 'phone_number': phone})
                
                if not db_guests_data_for_batch: 
                     postgres_client.update_event_status(event_id, "Pending - No Valid Manual Guests")
                     flash('No valid manual guests provided after filtering.', 'info')

        elif guest_input_method == 'csv' and csv_path_to_save: 
            parsed_guest_list = parse_csv_to_guests(csv_path_to_save)
            if not parsed_guest_list:
                flash('No valid guests found in CSV. Event created, but no calls made.', 'warning')
                postgres_client.update_event_status(event_id, "Pending - No Guests from CSV")
            else:
                db_guests_data_for_batch = [{'guest_name': g['GuestName'], 'phone_number': g['PhoneNumber']} for g in parsed_guest_list]
        
        if db_guests_data_for_batch:
            created_guests = postgres_client.add_guests_batch(event_id, db_guests_data_for_batch)
            if created_guests:
                processed_guests_count = len(created_guests)
                for guest_obj in created_guests:
                    initiate_vapi_call(event_id, guest_obj.id, guest_obj.guest_name, guest_obj.phone_number, 
                                       voice_sample_id, event_details_for_vapi, voice_choice)
            else: 
                db_op_type = "Manual Guest Batch Add" if guest_input_method == 'manual' else "CSV Guest Batch Add"
                postgres_client.update_event_status(event_id, f"Failed - {db_op_type}")
                flash(f'Failed to add {guest_input_method} guests to the database.', 'error')
        
        # Update event status and flash messages based on processing outcome
        if processed_guests_count > 0:
            postgres_client.update_event_status(event_id, "Calls Initiated")
            flash(f'{processed_guests_count} guest calls initiated successfully!', 'success')
        elif not db_guests_data_for_batch: # If no guests were ultimately processed for calls
            # Status already set for these specific cases earlier, so just check if we need a generic one
            current_event_status_obj = postgres_client.get_event_by_id(event_id)
            if current_event_status_obj and current_event_status_obj.status == 'Pending': # If no specific pending status was set
                 postgres_client.update_event_status(event_id, "Pending - No Guests To Call")
                 flash('Event created, but no guests were available or processed for calls.', 'info')


        session.pop('event_details_part1', None)
        session.pop('voice_choice', None)
        session.pop('voice_sample_id', None)
        return redirect(url_for('success', event_id=event_id))

    return render_template('event_details_step2.html')

@app.route('/vapi/callback', methods=['POST'])
def vapi_callback():
    """Handles Vapi callback to log RSVP responses (simpler callback from Vapi)."""
    data = request.json
    logger.debug(f"Vapi simple callback received: {data}")

    call_status = data.get("status") 
    metadata = data.get("metadata", {})
    guest_id_str = metadata.get("guestId")
    event_id_str = metadata.get("eventId")
    transcription = data.get("summary") or data.get("transcript") 

    if not guest_id_str or not event_id_str:
        logger.error(f"Vapi callback missing guestId or eventId in metadata: {metadata}")
        return jsonify({'status': 'Error', 'message': 'Missing guestId or eventId'}), 400

    try:
        guest_id = int(guest_id_str)
        event_id = int(event_id_str)
    except ValueError:
        logger.error(f"Vapi callback guestId or eventId is not a valid integer: guestId='{guest_id_str}', eventId='{event_id_str}'")
        return jsonify({'status': 'Error', 'message': 'Invalid guestId or eventId format'}), 400
    
    final_rsvp_status = "No Response"
    summary_text = transcription or "No transcription available from Vapi callback."

    if call_status == "success": 
        if transcription:
            processed_response = transcription.lower()
            if "yes" in processed_response: final_rsvp_status = "Yes"
            elif "no" in processed_response: final_rsvp_status = "No"
            elif "maybe" in processed_response or "not sure" in processed_response: final_rsvp_status = "Maybe"
        
        db_rsvp_data = {'response': final_rsvp_status, 'summary': summary_text}
        created_rsvp = postgres_client.create_rsvp(guest_id, event_id, db_rsvp_data)
        if created_rsvp:
            postgres_client.update_guest_call_status(guest_id, "Called - RSVP Received")
            logger.info(f"RSVP '{final_rsvp_status}' logged for guest {guest_id}, event {event_id}. Summary: {summary_text}")
        else:
            logger.error(f"Failed to log RSVP for guest {guest_id}, event {event_id} via vapi_callback")
    
    elif call_status == "failed":
        postgres_client.update_guest_call_status(guest_id, "Failed - API Error")
        failure_reason = data.get('error', {}).get('message', 'Vapi call failed')
        db_rsvp_data = {'response': 'Call Failed', 'summary': failure_reason}
        postgres_client.create_rsvp(guest_id, event_id, db_rsvp_data)
        logger.info(f"Call failed for guest {guest_id}, event {event_id}. Reason: {failure_reason}")
    
    else: 
        logger.info(f"Received Vapi callback status '{call_status}' for guest {guest_id}, event {event_id}. No final RSVP action taken.")
        return jsonify({'status': f'Callback status {call_status} noted, no final RSVP action.'}), 200

    return jsonify({'status': 'Callback processed'}), 200

@app.route('/success')
def success():
    """Displays a success message after form submission."""
    event_id_str = request.args.get('event_id')
    event = None
    event_status_msg = "Status not available."

    if event_id_str:
        try:
            event_id_int = int(event_id_str)
            event_obj = postgres_client.get_event_by_id(event_id_int)
            if event_obj:
                event = event_obj 
                event_status_msg = f"Current event status: {event.status}"
            else:
                flash('Event details not found for the provided ID.', 'error')
        except ValueError:
            flash('Invalid event ID format.', 'error')
    else:
        flash('Event processing possibly initiated. No Event ID provided to success page.', 'info')
        
    return render_template('success.html', event=event, event_status_msg=event_status_msg, event_id_display=event_id_str or "N/A")

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serves uploaded files."""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/webhook', methods=['POST'])
def webhook():
    """Webhook endpoint to log Vapi events, especially end-of-call-report for detailed analysis."""
    event_data = request.get_json()
    logger.debug("-------------------------------------------------")
    logger.debug(f"Received Vapi webhook event: {event_data}")

    message = event_data.get('message', event_data) 
    if not isinstance(message, dict) and isinstance(event_data, dict) and 'type' in event_data : 
        message = event_data

    event_type = message.get('type')

    if event_type == 'status-update': 
        status = message.get('status')
        call_id_vapi = message.get('callId') 
        logger.debug(f"Webhook: Call status-update for Vapi Call ID {call_id_vapi}: {status}")
        if status == 'failed':
            error_message = message.get('error', {}).get('message', 'Unknown Vapi error from status-update')
            logger.error(f"Webhook: Vapi Call ID {call_id_vapi} failed. Reason: {error_message}")
            call_details = message.get('call', {})
            metadata = call_details.get('metadata', {})
            guest_id_str = metadata.get('guestId')
            if guest_id_str:
                try:
                    guest_id = int(guest_id_str)
                    guest = postgres_client.get_guest_by_id(guest_id)
                    if guest and guest.call_status not in ["Called - RSVP Received", "Failed - API Error", "Call Failed"]: 
                        postgres_client.update_guest_call_status(guest_id, "Failed - VAPI Status Update")
                except ValueError:
                    logger.error(f"Invalid guestId '{guest_id_str}' in status-update webhook.")

    elif event_type == 'end-of-call-report':
        call = message.get('call', {}) 
        analysis = message.get('analysis', {})
        metadata = call.get('metadata') if call.get('metadata') is not None else {}
        guest_id_str = metadata.get('guestId')
        event_id_str = metadata.get('eventId')

        if not guest_id_str or not event_id_str:
            logger.error(f"Webhook end-of-call-report missing guestId or eventId in metadata: {metadata}")
            return jsonify({'status': 'Error', 'message': 'Missing guestId or eventId'}), 400
        
        try:
            guest_id = int(guest_id_str)
            event_id = int(event_id_str)
        except ValueError:
            logger.error(f"Webhook end-of-call-report guestId or eventId is not valid: guestId='{guest_id_str}', eventId='{event_id_str}'")
            return jsonify({'status': 'Error', 'message': 'Invalid guestId or eventId format'}), 400

        structured_data = analysis.get('structuredData', {})
        summary = analysis.get('summary', '') 

        rsvp_response_from_vapi = structured_data.get('rsvp_response', 'No Response')
        if not rsvp_response_from_vapi or str(rsvp_response_from_vapi).strip() == "":
             rsvp_response_from_vapi = "No Response"

        db_rsvp_data = {
            'response': rsvp_response_from_vapi.capitalize(),
            'summary': summary, 
            'special_request': structured_data.get('special_request'),
            'reminder_request': structured_data.get('reminder_call_details') 
        }
        
        logger.debug(f"Webhook Call Report Analysis for guest {guest_id}, event {event_id}: {analysis}")
        logger.debug(f"Webhook Structured Data for RSVP: {db_rsvp_data}")
        
        created_rsvp = postgres_client.create_rsvp(guest_id, event_id, db_rsvp_data)
        if created_rsvp:
            postgres_client.update_guest_call_status(guest_id, "Called - RSVP Received")
            logger.info(f"RSVP logged via webhook for guest {guest_id}, event {event_id}. Response: {db_rsvp_data['response']}")
        else:
            logger.error(f"Failed to log RSVP via webhook for guest {guest_id}, event {event_id}")

    return jsonify({'status': 'Webhook event received'}), 200

def create_db_tables():
    """Creates database tables if they don't already exist."""
    with app.app_context():
        db.create_all()
        print("Database tables created successfully (if they didn't already exist)!")

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'create-tables':
        create_db_tables()
    else:
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True) 
        app.run(debug=config.DEBUG, port=5000)
