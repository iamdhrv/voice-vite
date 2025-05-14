"""
Configuration settings for the VoiceVite application.

Loads environment variables from a .env file and makes them accessible.
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Application configuration class."""
    # Flask settings
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'your_default_secret_key_here')
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')

    # API Keys
    VAPI_API_KEY = os.getenv('VAPI_API_KEY')
    ELEVENLABS_API_KEY = os.getenv('ELEVENLABS_API_KEY')
    AIRTABLE_API_KEY = os.getenv('AIRTABLE_API_KEY')
    GROK_API_KEY = os.getenv('GROK_API_KEY') # Or your preferred LLM API key

    # Airtable Configuration
    AIRTABLE_BASE_ID = os.getenv('AIRTABLE_BASE_ID')
    AIRTABLE_TABLE_NAME_EVENTS = os.getenv('AIRTABLE_TABLE_NAME_EVENTS', 'Events')
    AIRTABLE_TABLE_NAME_GUESTS = os.getenv('AIRTABLE_TABLE_NAME_GUESTS', 'Guests')
    AIRTABLE_TABLE_NAME_RSVPS = os.getenv('AIRTABLE_TABLE_NAME_RSVPS', 'RSVPs')

    # Data paths
    UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data')
    ALLOWED_EXTENSIONS = {'csv'}

    # Voice Cloning settings
    VOICE_TRAINING_DURATION = 30 # seconds

    # Ensure essential configurations are present
    if not SECRET_KEY:
        raise ValueError("No FLASK_SECRET_KEY set for Flask application. Please set it in .env or as an environment variable.")
    if not VAPI_API_KEY:
        print("Warning: VAPI_API_KEY is not set. Vapi integration will not work.")
    if not ELEVENLABS_API_KEY:
        print("Warning: ELEVENLABS_API_KEY is not set. ElevenLabs integration will not work.")
    if not AIRTABLE_API_KEY or not AIRTABLE_BASE_ID:
        print("Warning: AIRTABLE_API_KEY or AIRTABLE_BASE_ID is not set. Airtable integration will not work.")

# Create an instance of the config
config = Config()

if __name__ == '__main__':
    # This part is for testing the config loading
    print(f"Flask Secret Key: {'*' * len(config.SECRET_KEY) if config.SECRET_KEY else 'Not set'}")
    print(f"Flask Debug Mode: {config.DEBUG}")
    print(f"Vapi API Key: {'Set' if config.VAPI_API_KEY else 'Not set'}")
    print(f"ElevenLabs API Key: {'Set' if config.ELEVENLABS_API_KEY else 'Not set'}")
    print(f"Airtable API Key: {'Set' if config.AIRTABLE_API_KEY else 'Not set'}")
    print(f"Airtable Base ID: {config.AIRTABLE_BASE_ID if config.AIRTABLE_BASE_ID else 'Not set'}")
    print(f"Events Table: {config.AIRTABLE_TABLE_NAME_EVENTS}")
    print(f"Guests Table: {config.AIRTABLE_TABLE_NAME_GUESTS}")
    print(f"RSVPs Table: {config.AIRTABLE_TABLE_NAME_RSVPS}")
    print(f"Upload Folder: {config.UPLOAD_FOLDER}")
    os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
    print(f"Upload folder '{config.UPLOAD_FOLDER}' ensured.")