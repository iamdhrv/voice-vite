from src.database import db
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship
import datetime

class Event(db.Model):
    __tablename__ = 'events'
    id = db.Column(db.Integer, primary_key=True)
    host_name = db.Column(db.String(150), nullable=True) # Made nullable based on Airtable schema inspection (not all fields were mandatory there)
    event_type = db.Column(db.String(100), nullable=True)
    event_date = db.Column(db.Date, nullable=True)
    event_time = db.Column(db.Time, nullable=True)
    duration = db.Column(db.String(50), nullable=True)
    location = db.Column(db.String(200), nullable=True)
    cultural_preferences = db.Column(db.Text, nullable=True)
    special_instructions = db.Column(db.Text, nullable=True)
    rsvp_deadline = db.Column(db.Date, nullable=True)
    user_email = db.Column(db.String(120), nullable=True)
    voice_sample_id = db.Column(db.String(100), nullable=True) # Assuming this is an ID from a voice service
    status = db.Column(db.String(50), default='draft') # e.g., "Pending", "Completed", "Failed"
    guest_list_csv_path = db.Column(db.String(255), nullable=True)
    background_music_url = db.Column(db.String(512), nullable=True) # New field
    final_invitation_script = db.Column(db.Text, nullable=True) # New field

    # Relationships
    guests = db.relationship('Guest', backref='event', lazy=True, cascade="all, delete-orphan")
    rsvps = db.relationship('RSVP', backref='event', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Event {self.id}: {self.event_type} hosted by {self.host_name}>'

class Guest(db.Model):
    __tablename__ = 'guests'
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    guest_name = db.Column(db.String(150), nullable=False)
    phone_number = db.Column(db.String(20), nullable=False) # E.164 format can be up to 15 digits + '+'
    call_status = db.Column(db.String(50), default='Not Called') # e.g., "Not Called", "Called - Initiated", "Called - RSVP Received", "Failed - API Error"

    # Relationships
    rsvps = db.relationship('RSVP', backref='guest', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Guest {self.id}: {self.guest_name} for Event {self.event_id}>'

class RSVP(db.Model):
    __tablename__ = 'rsvps'
    id = db.Column(db.Integer, primary_key=True)
    guest_id = db.Column(db.Integer, db.ForeignKey('guests.id'), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False) # Direct link to event for easier querying if needed
    response = db.Column(db.String(50), nullable=True) # e.g., "Yes", "No", "Maybe", "No Response"
    summary = db.Column(db.Text, nullable=True) # From Vapi analysis
    special_request = db.Column(db.Text, nullable=True) # From Vapi analysis
    reminder_request = db.Column(db.String(100), nullable=True) # From Vapi analysis, could be date/time or boolean

    def __repr__(self):
        return f'<RSVP {self.id}: Guest {self.guest_id} for Event {self.event_id} - {self.response}>'
