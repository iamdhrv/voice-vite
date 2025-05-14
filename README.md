# VoiceVite

VoiceVite is a voice AI agent that creates and delivers personalized function invitations (e.g., weddings, birthdays).

## MVP Features

1.  **Voice Cloning**: Users train the agent by speaking predefined lines (30 seconds) to clone their voice using ElevenLabs.
2.  **Event Details Input**: Users enter event details (event type, date, location, cultural preferences, email) via a web form (Flask).
3.  **Guest List Upload**: Users upload a CSV guest list with names and phone numbers.
4.  **Personalized Outbound Calls**: The agent makes outbound calls to guests using Vapi, delivering a personalized invitation in the user’s cloned voice, addressing each guest by name. Script generation will be handled by Grok.
5.  **RSVP Collection & Logging**: The agent collects voice-based RSVPs (yes/no/maybe) and logs event details, guest list, and RSVPs in Airtable.

## Tech Stack

*   **Voice AI Platform**: Vapi
*   **Voice Cloning**: ElevenLabs
*   **Web Framework**: Flask
*   **Data Storage**: Airtable
*   **Script Generation**: Grok (or a similar LLM)
*   **Programming Language**: Python

## Project Structure

```
VoiceVite/
├── .gitignore
├── README.md
├── requirements.txt
├── app.py                 # Main Flask application
├── config.py              # Configuration for API keys, etc.
├── DESIGN.md              # Design inspirations and theme
├── data/                  # For uploaded CSVs (gitignored)
│   └── .gitkeep
├── docs/
│   ├── api/               # OpenAPI/Swagger specs
│   │   └── .gitkeep
│   └── use-cases/       # Use case documents
│       └── .gitkeep
├── scripts/
│   ├── init_repo.sh       # Script to initialize repo and structure
│   └── .gitkeep
├── src/
│   ├── __init__.py
│   ├── airtable_integration/
│   │   ├── __init__.py
│   │   └── client.py      # Airtable client and functions
│   ├── call_handling/
│   │   ├── __init__.py
│   │   └── vapi_handler.py # Vapi integration for calls and RSVP
│   ├── utils/
│   │   ├── __init__.py
│   │   └── csv_parser.py  # CSV parsing utility
│   └── voice_cloning/
│       ├── __init__.py
│       └── eleven_labs_handler.py # ElevenLabs integration
├── static/
│   ├── css/
│   │   └── style.css
│   ├── js/
│   │   └── script.js
│   └── images/
│       └── .gitkeep
├── templates/
│   ├── index.html         # Main web form page
│   └── success.html       # Success page after form submission
└── tests/
    ├── __init__.py
    ├── test_app.py
    └── .gitkeep
```

## Setup and Installation

1.  **Clone the repository**:
    ```bash
    git clone <repository-url>
    cd VoiceVite
    ```
2.  **Create a virtual environment**:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```
3.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
4.  **Configure API Keys**:
    *   Create a `.env` file in the root directory (this file is gitignored).
    *   Add your API keys to the `.env` file:
        ```env
        VAPI_API_KEY='your_vapi_api_key'
        ELEVENLABS_API_KEY='your_elevenlabs_api_key'
        AIRTABLE_API_KEY='your_airtable_api_key'
        AIRTABLE_BASE_ID='your_airtable_base_id'
        AIRTABLE_TABLE_NAME_EVENTS='Events'
        AIRTABLE_TABLE_NAME_GUESTS='Guests'
        AIRTABLE_TABLE_NAME_RSVPS='RSVPs'
        GROK_API_KEY='your_grok_api_key' # Or other LLM API key
        FLASK_SECRET_KEY='a_very_secret_key_for_flask_sessions'
        ```
    *   Alternatively, set these as environment variables directly.
    *   Update `config.py` to load these variables.

5.  **Set up Airtable**:
    *   Create an Airtable base with three tables: `Events`, `Guests`, and `RSVPs`.
    *   Define the schema as described in the "Airtable Schema" section below.

6.  **Run the Flask application**:
    ```bash
    flask run
    ```
    The application will be available at `http://127.0.0.1:5000`.

## Airtable Schema

### 1. Events Table

*   `EventID` (Primary Key, Autonumber or UUID)
*   `UserID` (Text, or Link to a Users table if you add user accounts)
*   `EventType` (Single Select: Wedding, Birthday, Anniversary, Corporate, Other)
*   `EventDate` (Date)
*   `EventTime` (Time, or include in EventDate if datetime type is used)
*   `Location` (Text)
*   `CulturalPreferences` (Long Text, for notes on tone, language, etc.)
*   `UserEmail` (Email)
*   `VoiceSampleID` (Text, ID from ElevenLabs)
*   `GuestListCSVPath` (Text, path to the uploaded CSV - optional if storing guests directly)
*   `Status` (Single Select: Pending, Processing, Completed, Failed)
*   `CreatedAt` (Created Time)

### 2. Guests Table

*   `GuestID` (Primary Key, Autonumber or UUID)
*   `EventID_FK` (Link to Events Table)
*   `GuestName` (Text)
*   `PhoneNumber` (Phone Number)
*   `CallStatus` (Single Select: Pending, Called, Answered, No Answer, Failed)
*   `InvitationSentAt` (Timestamp)
*   `CreatedAt` (Created Time)

### 3. RSVPs Table

*   `RSVP_ID` (Primary Key, Autonumber or UUID)
*   `GuestID_FK` (Link to Guests Table)
*   `EventID_FK` (Link to Events Table)
*   `RSVP_Status` (Single Select: Yes, No, Maybe, No Response)
*   `RSVP_Timestamp` (Timestamp)
*   `Notes` (Long Text, for any additional voice input or context)
*   `CreatedAt` (Created Time)

## Implementation Steps

1.  **Project Setup & Basic Flask App**: Initialize Git, create folder structure, set up Flask.
2.  **Airtable Setup**: Create Base and Tables as per schema.
3.  **Airtable Integration (`src/airtable_integration/client.py`)**: Functions to read/write to Airtable.
4.  **Web Form (`templates/index.html`, `app.py`)**: Create HTML form for event details. Implement Flask routes to handle form submission and save data to Airtable (Events table).
5.  **CSV Upload (`app.py`, `src/utils/csv_parser.py`)**: Add functionality to upload guest list CSV. Parse CSV and store guest data in Airtable (Guests table), linking to the event.
6.  **Voice Cloning (`src/voice_cloning/eleven_labs_handler.py`)**: Integrate ElevenLabs API. Create a simple interface (could be a separate page or CLI initially) for users to record/upload a 30-second voice sample. Store the cloned voice ID.
7.  **Script Generation (LLM Integration - e.g., Grok)**: Function to generate a personalized invitation script using event details and guest name.
8.  **Outbound Calls (`src/call_handling/vapi_handler.py`)**: Integrate Vapi API. Trigger outbound calls to guests using the cloned voice and generated script.
9.  **RSVP Collection (Vapi & Airtable)**: Configure Vapi to capture voice responses (Yes/No/Maybe). Update Airtable (RSVPs table) with the responses.
10. **Testing**: Unit tests for CSV parsing, Airtable client, Flask routes. Integration tests for the end-to-end flow.
11. **Deployment**: Consider options like Heroku, PythonAnywhere, or Docker on a cloud provider (AWS, GCP, Azure).

## Testing and Deployment

*   **Testing**:
    *   **Unit Tests**: Use `pytest` for testing individual functions (e.g., CSV parsing, Airtable interactions, form validation).
    *   **Integration Tests**: Test the flow of creating an event, uploading guests, and simulating call/RSVP logging.
    *   **Manual Testing**: Thoroughly test the web interface, voice cloning, call quality, and RSVP accuracy.
*   **Deployment**:
    *   **Development**: Use Flask's built-in server.
    *   **Production**: Use a production-grade WSGI server like Gunicorn or uWSGI behind a reverse proxy like Nginx.
    *   **Platform**: Heroku, AWS Elastic Beanstalk, Google App Engine, or Docker + Kubernetes for more complex setups.

## Scalability Considerations

*   **Task Queues**: For handling outbound calls and voice processing asynchronously (e.g., Celery with Redis/RabbitMQ). This prevents the web server from being blocked.
*   **Database Optimization**: Ensure Airtable base is structured efficiently. For very high volumes, consider a more scalable database solution (e.g., PostgreSQL, MySQL) and use Airtable as a reporting/management layer.
*   **Rate Limiting**: Be mindful of API rate limits for Vapi, ElevenLabs, and Airtable. Implement retry mechanisms and potentially distribute calls over time.
*   **Stateless Application**: Design the Flask app to be stateless if possible, to allow for horizontal scaling (running multiple instances).
*   **Voice Cloning Management**: Efficiently manage and store voice samples and cloned voice IDs.
*   **Cost Management**: Monitor API usage costs for all third-party services.

## Future Enhancements

*   User authentication and accounts.
*   More sophisticated voice training and quality checks.
*   Support for different languages and accents.
*   Interactive voice responses (e.g., allowing guests to ask questions).
*   Dashboard for users to track RSVP status.
*   Calendar integrations for guests.