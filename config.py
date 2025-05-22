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
    VAPI_ASSISTANT_ID = os.getenv('VAPI_ASSISTANT_ID')
    ELEVENLABS_API_KEY = os.getenv('ELEVENLABS_API_KEY')
    AIRTABLE_PERSONAL_ACCESS_TOKEN = os.getenv('AIRTABLE_PERSONAL_ACCESS_TOKEN')
    GROK_API_KEY = os.getenv('GROK_API_KEY') # Or your preferred LLM API key
    LMNT_API_KEY = os.getenv('LMNT_API_KEY')

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

    # Database Configuration
    # Example for PostgreSQL: 'postgresql://user:password@host:port/database'
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')

    # Ensure essential configurations are present
    if not SECRET_KEY:
        raise ValueError("No FLASK_SECRET_KEY set for Flask application. Please set it in .env or as an environment variable.")
    if not VAPI_API_KEY:
        print("Warning: VAPI_API_KEY is not set. Vapi integration will not work.")
    if not ELEVENLABS_API_KEY:
        print("Warning: ELEVENLABS_API_KEY is not set. ElevenLabs integration will not work.")
    if not AIRTABLE_PERSONAL_ACCESS_TOKEN or not AIRTABLE_BASE_ID:
        print("Warning: AIRTABLE_PERSONAL_ACCESS_TOKEN or AIRTABLE_BASE_ID is not set. Airtable integration will not work.")
    if not LMNT_API_KEY:
        print("Warning: LMNT_API_KEY is not set. LMNT voice cloning integration will not work.")
    if not SQLALCHEMY_DATABASE_URI:
        print("Warning: DATABASE_URL is not set. Database integration will not work.")

# Create an instance of the config
config = Config()

if __name__ == '__main__':
    # This part is for testing the config loading
    print(f"Flask Secret Key: {'*' * len(config.SECRET_KEY) if config.SECRET_KEY else 'Not set'}")
    print(f"Flask Debug Mode: {config.DEBUG}")
    print(f"Vapi API Key: {'Set' if config.VAPI_API_KEY else 'Not set'}")
    print(f"ElevenLabs API Key: {'Set' if config.ELEVENLABS_API_KEY else 'Not set'}")
    print(f"Airtable Personal Access Token: {'Set' if config.AIRTABLE_PERSONAL_ACCESS_TOKEN else 'Not set'}")
    print(f"Airtable Base ID: {config.AIRTABLE_BASE_ID if config.AIRTABLE_BASE_ID else 'Not set'}")
    print(f"Events Table: {config.AIRTABLE_TABLE_NAME_EVENTS}")
    print(f"Guests Table: {config.AIRTABLE_TABLE_NAME_GUESTS}")
    print(f"RSVPs Table: {config.AIRTABLE_TABLE_NAME_RSVPS}")
    print(f"Upload Folder: {config.UPLOAD_FOLDER}")
    os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
    print(f"Upload folder '{config.UPLOAD_FOLDER}' ensured.")
    print(f"SQLAlchemy Database URI: {'Set' if config.SQLALCHEMY_DATABASE_URI else 'Not set'}")