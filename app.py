"""
Main Flask application for VoiceVite. (Refactored for PostgreSQL)

Handles web form submissions, CSV uploads, voice training, and initiates outbound calls.
"""
import os
from datetime import datetime, date, time, timedelta # Ensure timedelta is imported
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

# Helper function to generate event script
def _generate_event_script(event: Event, guest_name_placeholder: str = "{{GuestName}}") -> str:
    prompt_template_path = "src/voice_config/VoiceAssitantPrompt.md"
    try:
        with open(prompt_template_path, "r") as file:
            prompt_template = file.read()
    except FileNotFoundError:
        logger.error(f"Prompt template file not found at {prompt_template_path}")
        return "Error: Could not load script template."

    # Standard formatting for dates and times
    event_date_formatted = event.event_date.strftime('%A, %B %d, %Y') if event.event_date else "a future date"
    event_time_formatted = event.event_time.strftime('%I:%M %p').lstrip("0") if event.event_time else "a suitable time"
    rsvp_deadline_formatted = event.rsvp_deadline.strftime('%A, %B %d, %Y') if event.rsvp_deadline else "soon"

    # Derived values
    # ArrivalTime
    formatted_arrival_time = "15 minutes before the event (specific time not set)"
    if event.event_date and event.event_time:
        try:
            event_datetime_obj = datetime.combine(event.event_date, event.event_time)
            arrival_datetime = event_datetime_obj - timedelta(minutes=15)
            formatted_arrival_time = arrival_datetime.strftime('%I:%M %p').lstrip("0")
        except TypeError: # Handle cases where date/time might not be proper objects despite not being None
            logger.warning("Could not combine event.event_date and event.event_time for ArrivalTime calculation.")


    # DressCode
    derived_dress_code = "not specified"
    if event.special_instructions:
        si_lower = event.special_instructions.lower()
        dress_code_marker = "dress code"
        if dress_code_marker in si_lower:
            start_index = si_lower.find(dress_code_marker) + len(dress_code_marker)
            # Remove "is", ":", or "." if they are immediately after "dress code"
            substring_after_marker = event.special_instructions[start_index:].lstrip(": is.").strip()
            # Take text until the next sentence or a significant punctuation like ';'
            potential_dress_code = substring_after_marker.split('.')[0].split(';')[0].strip()
            if potential_dress_code: # Ensure it's not empty
                derived_dress_code = potential_dress_code

    # AlternateDate
    formatted_alternate_date = "the next day"
    if event.event_date:
        try:
            alternate_event_date_obj = event.event_date + timedelta(days=1)
            formatted_alternate_date = alternate_event_date_obj.strftime('%A, %B %d, %Y')
        except TypeError:
             logger.warning("Could not calculate AlternateDate due to event.event_date type.")


    # AlternateTime (same as original event time if available)
    formatted_alternate_time = event_time_formatted # Uses the already formatted event_time_formatted

    variable_values = {
        "[HostName]": event.host_name or "the host",
        "[GuestName]": guest_name_placeholder,
        "[EventType]": event.event_type or "an event",
        "[EventDate]": event_date_formatted,
        "[EventTime]": event_time_formatted,
        "[Location]": event.location or "a location",
        "[CulturalPreferences]": event.cultural_preferences or "",
        "[SpecialInstructions]": event.special_instructions or "", # The full instructions
        "[Duration]": event.duration or "a few hours",
        "[RSVPDeadline]": rsvp_deadline_formatted,
        "[ArrivalTime]": formatted_arrival_time,
        "[DressCode]": derived_dress_code,
        "[AlternateDate]": formatted_alternate_date,
        "[AlternateTime]": formatted_alternate_time
    }

    formatted_prompt = prompt_template
    for placeholder, value in variable_values.items():
        formatted_prompt = formatted_prompt.replace(placeholder, str(value)) # Ensure value is string
    
    return formatted_prompt

def allowed_file(filename, allowed_extensions_set):
    """Checks if the uploaded file has an allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions_set

def initiate_vapi_call(event_id: int, guest_id: int, guest_name: str, phone_number: str, 
                       voice_sample_id: str, event_details_for_vapi: dict, 
                       final_script: str, # New parameter
                       voice_choice: str = 'male'):
    """
    Initiates a Vapi call to a guest with the specified voice and event details.
    Uses PostgreSQL event_id and guest_id (integers).
    """
    try:
        # VapiHandler's make_outbound_call expects guest_id_db (int)
        # Ensure vapi_handler is initialized (it is globally in app.py)
        call_id = vapi_handler.make_outbound_call(
            phone_number=phone_number,
            assistant_id=config.VAPI_ASSISTANT_ID, 
            guest_name=guest_name,
            event_details=event_details_for_vapi,
            guest_id_db=guest_id,
            final_script=final_script,  # Pass the new parameter
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
        # guest_input_method = request.form.get('guest_input_method') # No longer directly needed for validation here
        background_music_url = request.form.get('background_music') 

        if not all([location, user_email, rsvp_deadline_str]): # guest_input_method removed from check
            flash('Please fill in all required fields for this step.', 'error')
            return redirect(url_for('event_details_step2'))

        # Store user_email in session
        session['user_email'] = user_email

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
            'status': 'draft', # CHANGED to 'draft'
            'guest_list_csv_path': None, 
            'background_music_url': background_music_url,
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

        # Handle CSV file saving if provided, but no guest processing here
        guest_input_method = request.form.get('guest_input_method')
        csv_path_to_save = None
        if guest_input_method == 'csv':
            if 'guest_list' in request.files and request.files['guest_list'].filename != '':
                file = request.files['guest_list']
                if file and allowed_file(file.filename, config.ALLOWED_EXTENSIONS):
                    filename = secure_filename(file.filename)
                    csv_path_to_save = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    db_event_data['guest_list_csv_path'] = csv_path_to_save
                    try:
                        file.save(csv_path_to_save)
                        logger.info(f"Guest list CSV (if any) saved to {csv_path_to_save}")
                    except Exception as e:
                        logger.error(f"Failed to save CSV file {csv_path_to_save}: {e}")
                        flash('Error saving guest list CSV file, but proceeding.', 'warning')
                else:
                    flash('Invalid file type for guest list. Only CSV allowed. Proceeding without CSV.', 'warning')
        
        created_event = postgres_client.create_event(db_event_data)
        if not created_event:
            flash('Failed to create event draft in database.', 'error')
            return redirect(url_for('event_details_step2'))
        
        event_id = created_event.id 

        # Fetch the full event object from DB to pass to script generator and template
        event_object_from_db = postgres_client.get_event_by_id(event_id)
        if not event_object_from_db:
            flash('Failed to retrieve event draft from database after creation.', 'error')
            # Consider how to handle this - maybe delete the created_event or set status to failed
            return redirect(url_for('event_details_step2'))

        # Generate the sample script using the helper function
        sample_script = _generate_event_script(event_object_from_db) 

        # Clean up session variables - keep voice_choice and voice_sample_id as they are part of event config
        session.pop('event_details_part1', None)
        # session.pop('user_email', None) # user_email is now in session for dashboard

        return render_template('preview_script.html', 
                               generated_script=sample_script, 
                               event_id=event_id, 
                               event_details=event_object_from_db)

    # GET request or if form validation fails and redirects back
    return render_template('event_details_step2.html')

@app.route('/confirm-and-send-invitations', methods=['POST'])
def confirm_and_send_invitations():
    event_id_str = request.form.get('event_id')
    final_script = request.form.get('final_script')

    if not event_id_str or not final_script:
        flash('Missing event ID or script. Cannot proceed.', 'error')
        # Attempt to redirect back to preview if event_id is available, else index
        return redirect(url_for('preview_script', event_id=event_id_str) if event_id_str else url_for('index'))

    try:
        event_id = int(event_id_str)
    except ValueError:
        flash('Invalid event ID format.', 'error')
        return redirect(url_for('index'))

    # --- 1. Update Event with final script and status ---
    update_payload = {
        'final_invitation_script': final_script,
        'status': 'processing'  # Or 'scheduled' as per original plan notes
    }
    updated_event_obj = postgres_client.update_event_fields(event_id, update_payload)
    
    if not updated_event_obj:
        flash(f'Failed to update event {event_id} with final script and status. Please try again.', 'error')
        return redirect(url_for('dashboard')) # Redirect to dashboard on failure

    # The 'event' variable for subsequent logic should be this updated_event_obj
    event = updated_event_obj 

    # --- 2. Fetch event details (needed for VAPI call, re-fetch for safety) ---
    # This explicit re-fetch is no longer strictly necessary as updated_event_obj IS the event
    # event = postgres_client.get_event_by_id(event_id) 
    # if not event: 
    #     flash(f'Event with ID {event_id} not found after update.', 'error')
    #     return redirect(url_for('dashboard'))

    # --- 3. Process Guest List (from CSV if path exists) ---
    guests_to_call = []
    if event.guest_list_csv_path:
        try:
            parsed_guests_from_csv = parse_csv_to_guests(event.guest_list_csv_path)
            if parsed_guests_from_csv:
                db_guests_data_for_batch = [{'guest_name': g['GuestName'], 'phone_number': g['PhoneNumber']} for g in parsed_guests_from_csv]
                created_guest_objects = postgres_client.add_guests_batch(event_id, db_guests_data_for_batch)
                if created_guest_objects:
                    guests_to_call.extend(created_guest_objects)
                    logger.info(f"Added {len(created_guest_objects)} guests from CSV for event {event_id}.")
                else:
                    # This means add_guests_batch returned None or empty list
                    logger.warning(f"postgres_client.add_guests_batch did not return guests for event {event_id} from CSV: {event.guest_list_csv_path}")
                    flash('Could not process guests from CSV file (add_guests_batch failed).', 'warning')
            else:
                logger.info(f"No valid guests found in CSV file: {event.guest_list_csv_path} for event {event_id}")
                flash('CSV file specified but no valid guests found in it.', 'warning')
        except FileNotFoundError:
            logger.error(f"Guest CSV file not found at path: {event.guest_list_csv_path} for event {event_id}")
            flash('Guest list CSV file not found. Cannot process guests.', 'error')
        except Exception as e: # Catch other parsing or processing errors
            logger.error(f"Error processing CSV {event.guest_list_csv_path} for event {event_id}: {e}")
            flash(f'Error processing guest CSV file: {str(e)}', 'error')
    
    # --- 4. Initiate Calls ---
    if not guests_to_call:
        flash('No guests found to call for this event. Event status set, but no calls initiated.', 'info')
        postgres_client.update_event_status(event_id, "Processed - No Guests")
    else:
        event_date_str = event.event_date.strftime('%Y-%m-%d') if event.event_date else ""
        event_time_str = event.event_time.strftime('%H:%M') if event.event_time else ""
        rsvp_deadline_str = event.rsvp_deadline.strftime('%Y-%m-%d') if event.rsvp_deadline else ""

        event_details_for_vapi = {
            "eventId": str(event.id),
            "voiceSampleId": event.voice_sample_id,
            "hostName": event.host_name,
            "eventType": event.event_type,
            "eventDate": event_date_str,
            "eventTime": event_time_str,
            "location": event.location,
            "culturalPreferences": event.cultural_preferences or "",
            "duration": event.duration,
            "specialInstructions": event.special_instructions or "",
            "rsvpDeadline": rsvp_deadline_str,
            "background_music_url": event.background_music_url or "",
            "final_script": final_script # Added for Step 12
        }
        
        voice_choice = 'custom' 
        if event.voice_sample_id == 'JBFqnCBsd6RMkjVDRZzb': 
            voice_choice = 'male'
        elif event.voice_sample_id == 'XrExE9yKIg1WjnnlVkGX': 
            voice_choice = 'female'

        call_count = 0
        for guest_obj in guests_to_call:
            initiate_vapi_call( 
                event_id=event.id, 
                guest_id=guest_obj.id, 
                guest_name=guest_obj.guest_name, 
                phone_number=guest_obj.phone_number, 
                voice_sample_id=event.voice_sample_id, 
                event_details_for_vapi=event_details_for_vapi, # Does NOT contain final_script for this call
                final_script=final_script, # Pass the final_script from the form
                voice_choice=voice_choice
            )
            call_count += 1
        
        if call_count > 0:
            flash(f'{call_count} guest calls initiated successfully based on your final script!', 'success')
            postgres_client.update_event_status(event_id, "Calls Initiated") 
        else:
            flash('Calls were intended, but none were initiated due to an issue.', 'warning')
            # Keep status as 'processing' or set to a specific error status if needed
            # postgres_client.update_event_status(event_id, "Processed - Call Error") # Example if specific status needed

    # --- 5. Redirect ---
    return redirect(url_for('dashboard'))


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

@app.route('/dashboard', methods=['GET'])
def dashboard():
    if 'user_email' not in session:
        flash('Please complete event creation (step 1 and 2) to associate an email and view the dashboard.', 'info')
        return redirect(url_for('index'))

    user_email = session['user_email']
    
    user_events = postgres_client.get_events_for_user(user_email)
    
    events_data_for_template = []
    if user_events:
        for event_obj in user_events:
            rsvp_summary = postgres_client.get_rsvp_summary_for_event(event_obj.id)
            # Direct count from Guest table for robustness
            guest_count = Guest.query.filter_by(event_id=event_obj.id).count()

            events_data_for_template.append({
                'event': event_obj,
                'rsvp_summary': rsvp_summary,
                'guest_count': guest_count
            })
            
    return render_template('dashboard.html', events_data=events_data_for_template)

@app.route('/send-test-call', methods=['POST'])
def send_test_call():
    if not request.is_json:
        return jsonify({'success': False, 'message': 'Invalid request: Content-Type must be application/json.'}), 415

    data = request.get_json()
    test_phone_number = data.get('test_phone_number')
    script_content = data.get('script_content')
    event_id_str = data.get('event_id')

    if not all([test_phone_number, script_content, event_id_str]):
        return jsonify({'success': False, 'message': 'Missing required fields (test_phone_number, script_content, event_id).'}), 400

    try:
        event_id = int(event_id_str)
    except ValueError:
        return jsonify({'success': False, 'message': 'Invalid event_id format.'}), 400

    event = postgres_client.get_event_by_id(event_id)
    if not event:
        return jsonify({'success': False, 'message': f'Event with ID {event_id} not found.'}), 404

    # Prepare event_config for the test call handler
    event_config_for_test_call = {
        'voice_sample_id': event.voice_sample_id,
        'background_music_url': event.background_music_url,
        'vapi_assistant_id': config.VAPI_ASSISTANT_ID, # Using global VAPI_ASSISTANT_ID from config
        'host_name': event.host_name # Needed for {{HostName}} if user script contains it
        # Add any other details from 'event' object that make_single_test_call might need
        # to substitute placeholders in the script_content, e.g. {{HostName}}
    }

    # Call the handler function (to be created in Step 18)
    # For now, since the handler function doesn't exist, we'll use the placeholder call/response from the task description.
    # This will be replaced by the actual call in Step 18.
    
    # Actual call to the VapiHandler:
    test_call_successful, test_call_message = vapi_handler.make_single_test_call(
        phone_number=test_phone_number,
        script_content=script_content,
        event_config=event_config_for_test_call 
    )

    if test_call_successful:
        return jsonify({'success': True, 'message': test_call_message or 'Test call initiated successfully.'})
    else:
        return jsonify({'success': False, 'message': test_call_message or 'Failed to initiate test call.'}), 500

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
