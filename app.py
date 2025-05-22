"""
Main Flask application for VoiceVite.

Handles web form submissions, CSV uploads, voice training, and initiates outbound calls.
"""
import os
from datetime import datetime, date, time # Added for type conversion
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, jsonify, session
from werkzeug.utils import secure_filename
import logging

from config import config
from src.airtable_integration.client import AirtableClient # Kept for now, but usage will be phased out
# postgres_client is already imported from a previous subtask.
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
    # 'event_id' is Postgres int ID, 'guest_id' is Postgres int ID
    # 'event_details' is the event_details_for_vapi dict

    try:
        # The vapi_handler.make_outbound_call now expects guest_id_db as an int.
        # event_details should be event_details_for_vapi which has eventId as string.
        call_id = vapi_handler.make_outbound_call(
            phone_number=phone_number,
            assistant_id=config.VAPI_ASSISTANT_ID, # Ensure config is imported/available
            guest_name=guest_name,
            event_details=event_details, # This is event_details_for_vapi
            guest_id_db=guest_id, # Pass the integer PostgreSQL guest_id
            voice_choice=voice_choice
        )

        if call_id:
            # Use postgres_client for status updates
            updated_guest = postgres_client.update_guest_call_status(guest_id, 'Called - Initiated')
            if not updated_guest:
                logger.error(f"Failed to update guest {guest_id} status to 'Called - Initiated' in DB.")
            logger.debug(f"Vapi call initiated to {phone_number} for guest ID {guest_id}: {call_id}")
        else:
            # Use postgres_client for status updates
            updated_guest = postgres_client.update_guest_call_status(guest_id, 'Failed - API Error')
            if not updated_guest:
                logger.error(f"Failed to update guest {guest_id} status to 'Failed - API Error' in DB after failed call.")
            # Original log: logger.debug(f"Vapi call initiation failed for {phone_number} for guest {guest_id}")
            # Keep or adjust logging as needed.
    except Exception as e:
        logger.error(f"Error initiating Vapi call to {phone_number} for guest {guest_id}: {e}")
        # Use postgres_client for status updates
        updated_guest = postgres_client.update_guest_call_status(guest_id, 'Failed - API Error')
        if not updated_guest:
            logger.error(f"Failed to update guest {guest_id} status to 'Failed - API Error' in DB after exception.")


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

        # Prepare event_data for SQLAlchemy model
        db_event_data = {
            'host_name': event_details_part1.get('host_name'),
            'event_type': event_details_part1.get('event_type'),
            'event_date': event_details_part1.get('event_date'), # Will be converted
            'event_time': event_details_part1.get('event_time'), # Will be converted
            'duration': event_details_part1.get('duration'),
            'location': location,
            'cultural_preferences': cultural_preferences,
            'special_instructions': special_instructions,
            'rsvp_deadline': rsvp_deadline, # Will be converted
            'user_email': user_email,
            'voice_sample_id': voice_sample_id,
            'status': 'Pending', # Default status
            'guest_list_csv_path': None # Will be updated if CSV is uploaded
        }

        # Convert date/time strings to Python date/time objects
        try:
            if isinstance(db_event_data['event_date'], str):
                db_event_data['event_date'] = datetime.strptime(db_event_data['event_date'], '%Y-%m-%d').date()
            if isinstance(db_event_data['event_time'], str):
                time_str = db_event_data['event_time']
                # Model expects `time`. Vapi might send HH:MM:SS, forms usually HH:MM.
                if len(time_str.split(':')) == 3: # HH:MM:SS
                     db_event_data['event_time'] = datetime.strptime(time_str, '%H:%M:%S').time()
                else: # HH:MM
                     db_event_data['event_time'] = datetime.strptime(time_str, '%H:%M').time()
            if isinstance(db_event_data['rsvp_deadline'], str):
                db_event_data['rsvp_deadline'] = datetime.strptime(db_event_data['rsvp_deadline'], '%Y-%m-%d').date()
        except ValueError as e:
            logger.error(f"Date/Time conversion error: {e}")
            flash('Invalid date or time format. Please use YYYY-MM-DD for dates and HH:MM for times.', 'error')
            return redirect(url_for('event_details_step2'))
        
        # Event creation logic moved down to happen after guest_list_csv_path is determined.

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
                    flash('Phone number must be in E.164 format (e.g., +19876543210).', 'error') # Corrected example
                    return redirect(url_for('event_details_step2'))
            
            db_event_data['guest_list_csv_path'] = None # Explicitly set for manual path
            created_event = postgres_client.create_event(db_event_data)
            if not created_event:
                flash('Failed to create event in database.', 'error')
                return redirect(url_for('event_details_step2'))
            event_id = created_event.id # Use the new PostgreSQL event ID
            event_details["eventId"] = str(event_id) # Update event_details for Vapi, ensure string
            
            # Prepare guests data for SQLAlchemy
            db_guests_data = [{'guest_name': name, 'phone_number': phone} for name, phone in zip(guest_names, guest_phones)]
            # event_id is the new PostgreSQL event_id
            created_guests = postgres_client.add_guests_batch(event_id, db_guests_data)

            if not created_guests or len(created_guests) != len(db_guests_data):
                flash('Failed to add some or all guests to the database.', 'error')
                # Optionally update event status to 'failed' or 'partial_success'
                postgres_client.update_event_status(event_id, "Failed - Guest Creation Issue")
                return redirect(url_for('event_details_step2'))
            
            # guest_ids = [guest.id for guest in created_guests] # This is a list of new PostgreSQL guest IDs

            # Initiate Vapi calls for each guest
            for guest_obj in created_guests: # guest_obj is a Guest model instance
                initiate_vapi_call(
                    event_id, # This is created_event.id (PostgreSQL int ID)
                    guest_obj.id, # This is the PostgreSQL guest ID (int)
                    guest_obj.guest_name,
                    guest_obj.phone_number,
                    voice_sample_id,
                    event_details, # This dict now contains event_details["eventId"] = str(created_event.id)
                    voice_choice
                )
            flash(f'{len(created_guests)} guests added manually.', 'info')
        else:  # CSV Upload
            if 'guest_list' not in request.files:
                flash('No guest list file part', 'error')
                return redirect(url_for('event_details_step2'))
            file = request.files['guest_list']
            if file.filename == '':
                flash('No selected file for guest list', 'error')
                return redirect(url_for('event_details_step2'))
            
            # Ensure only CSV allowed here, config.ALLOWED_EXTENSIONS is for voice samples
            if file and allowed_file(file.filename, {"csv"}): 
                filename = secure_filename(file.filename)
                csv_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(csv_path)
                
                db_event_data['guest_list_csv_path'] = csv_path # Set CSV path before creating event
                created_event = postgres_client.create_event(db_event_data)
                if not created_event:
                    flash('Failed to create event in database (CSV flow).', 'error')
                    return redirect(url_for('event_details_step2'))
                event_id = created_event.id # PostgreSQL event ID (int)
                event_details["eventId"] = str(event_id) # Update Vapi event_details (string)

                parsed_guest_list = parse_csv_to_guests(csv_path) # [{'GuestName': ..., 'PhoneNumber': ...}]
                if not parsed_guest_list:
                    flash('No valid guests found in CSV. Event created but no guests added.', 'warning')
                    postgres_client.update_event_status(event_id, "Pending - No Guests from CSV")
                    # Clear session and redirect to success, as event IS created
                    session.pop('voice_choice', None)
                    session.pop('voice_sample_id', None)
                    session.pop('event_details', None)
                    return redirect(url_for('success', event_id=event_id))

                # Map keys from parse_csv_to_guests to Guest model keys
                db_guests_data_csv = [{'guest_name': g['GuestName'], 'phone_number': g['PhoneNumber']} for g in parsed_guest_list]
                created_guests_csv = postgres_client.add_guests_batch(event_id, db_guests_data_csv)

                if not created_guests_csv or len(created_guests_csv) != len(db_guests_data_csv):
                    flash('Failed to add some or all guests from CSV to the database. Event created.', 'warning')
                    postgres_client.update_event_status(event_id, "Pending - CSV Guest Import Issue")
                    # Proceed to call for successfully added guests if any
                
                flash(f'{len(created_guests_csv)} guests processed from CSV.', 'info')

                for guest_obj in created_guests_csv: # guest_obj is a Guest model instance
                    initiate_vapi_call(
                        event_id, # This is created_event.id (PostgreSQL int ID)
                        guest_obj.id, # PostgreSQL guest ID (int)
                        guest_obj.guest_name,
                        guest_obj.phone_number,
                        voice_sample_id,
                        event_details, # Contains event_details["eventId"] = str(created_event.id)
                        voice_choice
                    )
            else:
                flash('Invalid file type for guest list. Please upload a CSV file.', 'error')
                return redirect(url_for('event_details_step2'))

        # Clear session data after successful submission
        # event_id here is the PostgreSQL integer ID from created_event.id
        logger.info(f"Preparing to clear session for Event ID: {event_id}.") # event_id is already defined from event creation
        session.pop('voice_choice', None)
        session.pop('voice_sample_id', None)
        session.pop('event_details', None) # This was the original session dict for event step 1
        session.pop('csv_guests_to_process', None) # If this was used and might not be cleared
        session.pop('created_guests_csv_for_vapi_ids', None) # If this was used

        logger.info(f"Session cleared for Event ID: {event_id}. Redirecting to success page.")
        return redirect(url_for('success', event_id=event_id)) # event_id is the PostgreSQL int ID

    return render_template('event_details_step2.html')

@app.route('/vapi/callback', methods=['POST'])
def vapi_callback():
    data = request.json
    logger.debug(f"Vapi callback received: {data}")

    metadata = data.get("metadata", {})
    guest_id_str = metadata.get("guestId") # Keep as string initially for logging
    event_id_str = metadata.get("eventId") # Keep as string initially for logging

    try:
        if not guest_id_str or not event_id_str:
            logger.error("Vapi callback missing guestId or eventId in metadata.")
            return jsonify({"status": "error", "message": "Missing guestId or eventId"}), 400

        guest_id = int(guest_id_str)
        event_id = int(event_id_str)
    except (ValueError, TypeError) as e:
        logger.error(f"Vapi callback: Error converting IDs to int: {e}. guestId='{guest_id_str}', eventId='{event_id_str}'")
        return jsonify({"status": "error", "message": "Invalid guestId or eventId format"}), 400

    call_status = data.get("status")
    # The original code used 'response = data.get("transcription")'
    # Let's assume 'transcription' or a part of it forms the RSVP response.
    # Vapi payload might have structured data for RSVPs if available.
    # For this part, we'll keep it simple based on the old logic:
    raw_response_data = data.get("transcription") # Or check data.get("structuredData") or similar from Vapi docs

    if call_status == "ended":
        if raw_response_data: # Check if there's any response data
            # Determine RSVP response text (e.g. Yes, No, Maybe)
            # This logic might need to be more sophisticated based on actual Vapi output
            rsvp_response_text = str(raw_response_data).strip().capitalize()
            # Normalize common positive/negative/maybe responses
            processed_response_lower = rsvp_response_text.lower()
            if "yes" in processed_response_lower:
                final_rsvp_status = "Yes"
            elif "no" in processed_response_lower:
                final_rsvp_status = "No"
            elif "maybe" in processed_response_lower or "not sure" in processed_response_lower:
                final_rsvp_status = "Maybe"
            else:
                final_rsvp_status = "No Response" # Default if transcription is not a clear RSVP

            db_rsvp_data = {'response': final_rsvp_status, 'summary': raw_response_data}
            # If Vapi provides more structured data for summary, special_request, etc., add them here:
            # e.g., db_rsvp_data['summary'] = data.get('summary', raw_response_data) # Use transcription as summary if no other summary

            created_rsvp = postgres_client.create_rsvp(guest_id, event_id, db_rsvp_data)
            if created_rsvp:
                logger.info(f"RSVP '{final_rsvp_status}' logged for Guest ID {guest_id}, Event ID {event_id}.")
                updated_guest = postgres_client.update_guest_call_status(guest_id, "Called - RSVP Received")
                if not updated_guest:
                    logger.error(f"Failed to update guest {guest_id} status after RSVP.")
            else:
                logger.error(f"Failed to log RSVP for Guest ID {guest_id}. Response: {final_rsvp_status}, Summary: {raw_response_data}")
                # Optionally update guest status to something like "RSVP Log Failed"
                # postgres_client.update_guest_call_status(guest_id, "RSVP Log Failed")
        else: # No response data from transcription
            logger.info(f"Call ended for Guest ID {guest_id} but no response data in transcription.")
            # Update status to "Called - No Response" or similar, rather than "Failed"
            updated_guest = postgres_client.update_guest_call_status(guest_id, "Called - No Response")
            if not updated_guest:
                 logger.error(f"Failed to update guest {guest_id} status to 'Called - No Response'.")
            # Optionally, create an RSVP record indicating "No Response" explicitly
            db_rsvp_data = {'response': 'No Response', 'summary': 'Call ended, no transcription received.'}
            postgres_client.create_rsvp(guest_id, event_id, db_rsvp_data)

    elif call_status == "failed":
        logger.info(f"Call failed for Guest ID {guest_id}. Updating status.")
        updated_guest = postgres_client.update_guest_call_status(guest_id, "Failed - API Error")
        if not updated_guest:
            logger.error(f"Failed to update guest {guest_id} status after failed call.")
        # Optionally, create an RSVP record indicating "Call Failed"
        failure_summary = data.get('summary', data.get('errorMessage', 'Vapi call failed'))
        db_rsvp_data = {'response': 'Call Failed', 'summary': failure_summary}
        postgres_client.create_rsvp(guest_id, event_id, db_rsvp_data)
    
    return jsonify({"status": "Callback processed"}), 200

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
    event_data = request.get_json()
    logger.debug("-------------------------------------------------")
    logger.debug(f"Received Vapi event: {event_data}")

    message = event_data.get('message', event_data) # Handle if data is already the message
    event_type = message.get('type')

    if event_type == 'status-update':
        status = message.get('status')
        call_details = message.get('call', {}) # Ensure call_details is a dict
        metadata = call_details.get('metadata', {})
        
        guest_id_str = metadata.get('guestId')
        # event_id_str = metadata.get('eventId') # EventId might not be needed for just status update

        if status == 'failed' and guest_id_str:
            try:
                guest_id = int(guest_id_str)
                logger.info(f"Webhook status-update: Call failed for Guest ID {guest_id}. Updating status.")
                # Check current status before overwriting, to prevent changing "Called - RSVP Received" to "Failed - API Error"
                guest = postgres_client.get_guest_by_id(guest_id)
                if guest and guest.call_status not in ["Called - RSVP Received"]:
                    updated_guest = postgres_client.update_guest_call_status(guest_id, "Failed - API Error")
                    if not updated_guest:
                        logger.error(f"Webhook status-update: Failed to update guest {guest_id} status after failed call.")
                elif guest:
                    logger.info(f"Webhook status-update: Guest {guest_id} status is '{guest.call_status}', not changing to 'Failed - API Error'.")
                else:
                    logger.warning(f"Webhook status-update: Guest {guest_id} not found for status update.")
            except (ValueError, TypeError) as e:
                logger.error(f"Webhook status-update: Error converting guestId '{guest_id_str}' to int: {e}")
        # Add other status updates here if necessary e.g. for 'ringing', 'in-progress'

    elif event_type == 'end-of-call-report':
        call_details = message.get('call', {}) # Ensure dict
        analysis = message.get('analysis', {}) # Ensure dict
        metadata = call_details.get('metadata', {})

        guest_id_str = metadata.get('guestId')
        event_id_str = metadata.get('eventId')

        if not guest_id_str or not event_id_str:
            logger.error("Webhook end-of-call-report missing guestId or eventId.")
            return jsonify({'status': 'Error', 'message': 'Missing guestId or eventId'}), 400 # Or just log and return 200

        try:
            guest_id = int(guest_id_str)
            event_id = int(event_id_str)
        except (ValueError, TypeError) as e:
            logger.error(f"Webhook end-of-call-report: Error converting IDs to int: {e}. guestId='{guest_id_str}', eventId='{event_id_str}'")
            return jsonify({'status': 'Error', 'message': 'Invalid guestId or eventId format'}), 400 # Or just log

        structured_data = analysis.get('structuredData', {})
        db_rsvp_data = {
            'response': str(structured_data.get('rsvp_response', 'No Response')).strip().capitalize(),
            'summary': analysis.get('summary', ''),
            'special_request': structured_data.get('special_request'),
            'reminder_request': structured_data.get('reminder_call_details')
        }
        # Normalize response if needed, similar to vapi_callback
        if db_rsvp_data['response'].lower() not in ["yes", "no", "maybe"]:
            db_rsvp_data['response'] = "No Response"

        if not guest_id or not event_id: # Should be caught by earlier check, but as a safeguard
            logger.error("Webhook end-of-call-report: guest_id or event_id is null after conversion attempt.")
            return jsonify({'status': 'Event received, but critical ID missing after conversion'}), 200


        created_rsvp = postgres_client.create_rsvp(guest_id, event_id, db_rsvp_data)
        if created_rsvp:
            logger.info(f"RSVP logged via webhook for Guest ID {guest_id}, Event ID {event_id}. Response: {db_rsvp_data['response']}")
            updated_guest = postgres_client.update_guest_call_status(guest_id, "Called - RSVP Received")
            if not updated_guest:
                logger.error(f"Webhook end-of-call-report: Failed to update guest {guest_id} status after RSVP.")
        else:
            logger.error(f"Webhook end-of-call-report: Failed to log RSVP for Guest ID {guest_id}.")
            # Optionally update status to "RSVP Log Failed"
            # postgres_client.update_guest_call_status(guest_id, "RSVP Log Failed")

    return jsonify({'status': 'Event received'}), 200

if __name__ == '__main__':
    app.run(debug=config.DEBUG, port=5000)