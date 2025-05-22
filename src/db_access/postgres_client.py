from src.database import db
from src.models import Event, Guest, RSVP
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func # Add this import
import logging

logger = logging.getLogger(__name__)

def create_event(event_data: dict) -> Event | None:
    """Creates a new event in the database."""
    try:
        new_event = Event(**event_data)
        db.session.add(new_event)
        db.session.commit()
        logger.info(f"Event created successfully with ID: {new_event.id}")
        return new_event
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Error creating event in PostgreSQL: {e}")
        return None
    except Exception as e: # Catch any other unexpected errors
        db.session.rollback()
        logger.error(f"Unexpected error creating event: {e}")
        return None

def get_event_by_id(event_id: int) -> Event | None:
    """Retrieves an event by its ID."""
    try:
        # Using db.session.get for primary key lookup as it's slightly more optimized.
        # For SQLAlchemy versions < 2.0, it was event = Event.query.get(event_id).
        # Assuming Flask-SQLAlchemy uses SQLAlchemy 2.0+ style sessions.
        event = db.session.get(Event, event_id)
        if event:
            logger.info(f"Event with ID {event_id} retrieved successfully.")
        else:
            logger.info(f"No event found with ID {event_id}.")
        return event
    except SQLAlchemyError as e:
        logger.error(f"Error retrieving event {event_id} from PostgreSQL: {e}")
        return None
    except Exception as e: # Catch any other unexpected errors
        logger.error(f"Unexpected error retrieving event {event_id}: {e}")
        return None

def update_event_status(event_id: int, status: str) -> Event | None:
    """Updates the status of an existing event."""
    try:
        event = db.session.get(Event, event_id)
        if event:
            event.status = status
            db.session.commit()
            logger.info(f"Status updated for event ID {event_id} to {status}.")
            return event
        else:
            logger.warning(f"Event with ID {event_id} not found for status update.")
            return None
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Error updating status for event {event_id} in PostgreSQL: {e}")
        return None
    except Exception as e:
        db.session.rollback()
        logger.error(f"Unexpected error updating event status for event {event_id}: {e}")
        return None

def update_event_fields(event_id: int, update_data: dict) -> Event | None:
    """
    Updates specified fields of an existing event.
    
    Args:
        event_id: The ID of the event to update.
        update_data: A dictionary where keys are event model attribute names
                     (e.g., 'status', 'final_invitation_script') and values are
                     the new values for these attributes.
                     
    Returns:
        The updated Event object if successful, None otherwise.
    """
    try:
        event = db.session.get(Event, event_id)
        if event:
            for key, value in update_data.items():
                if hasattr(event, key):
                    setattr(event, key, value)
                else:
                    logger.warning(f"Attempted to update non-existent attribute '{key}' for event {event_id}.")
            db.session.commit()
            logger.info(f"Event ID {event_id} updated successfully with data: {update_data}.")
            return event
        else:
            logger.warning(f"Event with ID {event_id} not found for update.")
            return None
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"SQLAlchemyError updating event {event_id} in PostgreSQL: {e}")
        return None
    except Exception as e:
        db.session.rollback()
        logger.error(f"Unexpected error updating event {event_id}: {e}")
        return None

def create_guest(event_id: int, guest_data: dict) -> Guest | None:
    """Creates a new guest linked to an event."""
    try:
        # Ensure event_id from path/argument is used, not from guest_data if present
        guest_data['event_id'] = event_id
        new_guest = Guest(**guest_data)
        db.session.add(new_guest)
        db.session.commit()
        logger.info(f"Guest created successfully with ID {new_guest.id} for Event ID {event_id}.")
        return new_guest
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Error creating guest for event {event_id} in PostgreSQL: {e}")
        return None
    except Exception as e:
        db.session.rollback()
        logger.error(f"Unexpected error creating guest for event {event_id}: {e}")
        return None

def add_guests_batch(event_id: int, guests_data: list[dict]) -> list[Guest]:
    """Adds multiple guests to an event in a batch."""
    created_guests = []
    try:
        for guest_data_item in guests_data:
            # Ensure event_id from path/argument is used
            guest_data_item['event_id'] = event_id
            guest = Guest(**guest_data_item)
            db.session.add(guest)
            created_guests.append(guest)
        
        if not created_guests:
            logger.info(f"No guest data provided for batch add to event {event_id}.")
            return []

        db.session.commit()
        guest_ids = [guest.id for guest in created_guests]
        logger.info(f"{len(created_guests)} guests added successfully for Event ID {event_id}. Guest IDs: {guest_ids}")
        return created_guests
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Error batch adding guests for event {event_id} in PostgreSQL: {e}")
        return [] # Return empty list on error
    except Exception as e:
        db.session.rollback()
        logger.error(f"Unexpected error batch adding guests for event {event_id}: {e}")
        return []

def get_guest_by_id(guest_id: int) -> Guest | None:
    """Retrieves a guest by their ID."""
    try:
        guest = db.session.get(Guest, guest_id)
        if guest:
            logger.info(f"Guest with ID {guest_id} retrieved successfully.")
        else:
            logger.info(f"No guest found with ID {guest_id}.")
        return guest
    except SQLAlchemyError as e:
        logger.error(f"Error retrieving guest {guest_id} from PostgreSQL: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error retrieving guest {guest_id}: {e}")
        return None

def update_guest_call_status(guest_id: int, status: str) -> Guest | None:
    """Updates the call status of an existing guest."""
    try:
        guest = db.session.get(Guest, guest_id)
        if guest:
            guest.call_status = status
            db.session.commit()
            logger.info(f"Call status updated for guest ID {guest_id} to {status}.")
            return guest
        else:
            logger.warning(f"Guest with ID {guest_id} not found for call status update.")
            return None
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Error updating call status for guest {guest_id} in PostgreSQL: {e}")
        return None
    except Exception as e:
        db.session.rollback()
        logger.error(f"Unexpected error updating guest call status for guest {guest_id}: {e}")
        return None

def create_rsvp(guest_id: int, event_id: int, rsvp_data: dict) -> RSVP | None:
    """Creates a new RSVP linked to a guest and an event."""
    try:
        # Ensure foreign keys from path/arguments are used
        rsvp_data['guest_id'] = guest_id
        rsvp_data['event_id'] = event_id 
        
        # Check if guest and event exist (optional, but good practice)
        guest = db.session.get(Guest, guest_id)
        if not guest:
            logger.error(f"Cannot create RSVP. Guest with ID {guest_id} not found.")
            return None
        event = db.session.get(Event, event_id)
        if not event:
            logger.error(f"Cannot create RSVP. Event with ID {event_id} not found.")
            return None

        new_rsvp = RSVP(**rsvp_data)
        db.session.add(new_rsvp)
        db.session.commit()
        logger.info(f"RSVP created successfully with ID {new_rsvp.id} for Guest ID {guest_id} and Event ID {event_id}.")
        return new_rsvp
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Error creating RSVP for guest {guest_id}, event {event_id} in PostgreSQL: {e}")
        return None
    except Exception as e:
        db.session.rollback()
        logger.error(f"Unexpected error creating RSVP for guest {guest_id}, event {event_id}: {e}")
        return None

def get_guests_for_event(event_id: int) -> list[Guest]:
    """Retrieves all guests associated with a specific event ID."""
    try:
        # Using Model.query.filter_by().all() as requested
        guests = Guest.query.filter_by(event_id=event_id).all()
        logger.info(f"Retrieved {len(guests)} guests for Event ID {event_id}.")
        return guests
    except SQLAlchemyError as e:
        logger.error(f"Error retrieving guests for event {event_id} from PostgreSQL: {e}")
        return [] # Return empty list on error
    except Exception as e:
        logger.error(f"Unexpected error retrieving guests for event {event_id}: {e}")
        return []

def get_rsvps_for_event(event_id: int) -> list[RSVP]:
    """Retrieves all RSVPs associated with a specific event ID."""
    try:
        # Using Model.query.filter_by().all() as requested
        rsvps = RSVP.query.filter_by(event_id=event_id).all()
        logger.info(f"Retrieved {len(rsvps)} RSVPs for Event ID {event_id}.")
        return rsvps
    except SQLAlchemyError as e:
        logger.error(f"Error retrieving RSVPs for event {event_id} from PostgreSQL: {e}")
        return [] # Return empty list on error
    except Exception as e:
        logger.error(f"Unexpected error retrieving RSVPs for event {event_id}: {e}")
        return []

def get_events_for_user(user_email: str) -> list[Event]:
    """Retrieves all events for a given user, ordered by creation descending."""
    try:
        events = Event.query.filter_by(user_email=user_email).order_by(Event.id.desc()).all()
        logger.info(f"Retrieved {len(events)} events for user {user_email}.")
        return events
    except SQLAlchemyError as e:
        logger.error(f"Error retrieving events for user {user_email} from PostgreSQL: {e}")
        return [] # Return empty list on error
    except Exception as e:
        logger.error(f"Unexpected error retrieving events for user {user_email}: {e}")
        return []

def get_rsvp_summary_for_event(event_id: int) -> dict:
    """
    Calculates RSVP summary (yes, no, maybe, pending) for an event.
    Pending = Total Guests - (Yes + No + Maybe responses).
    """
    summary = {'yes': 0, 'no': 0, 'maybe': 0, 'pending': 0}
    total_guests = 0 # Initialize to ensure it's in scope for exception blocks
    try:
        # Get total number of guests for the event
        total_guests = Guest.query.filter_by(event_id=event_id).count()

        if total_guests == 0:
            logger.info(f"No guests found for event {event_id}, RSVP summary is all zeros.")
            return summary

        # Get RSVP counts grouped by response
        # Vapi webhook saves response as "Yes", "No", "Maybe", "No Response", "Call Failed"
        # We are interested in "Yes", "No", "Maybe"
        rsvp_counts_query_result = db.session.query(
            RSVP.response, func.count(RSVP.id)
        ).filter(RSVP.event_id == event_id).group_by(RSVP.response).all()

        responded_count = 0
        for response_status, count in rsvp_counts_query_result:
            if response_status: # Make sure response_status is not None
                status_lower = response_status.lower()
                if status_lower in ['yes', 'no', 'maybe']:
                    summary[status_lower] = count
                    responded_count += count
        
        summary['pending'] = total_guests - responded_count
        if summary['pending'] < 0: 
            summary['pending'] = 0 
            logger.warning(f"Pending count for event {event_id} was negative, adjusted to 0. Total: {total_guests}, Responded: {responded_count}")

        logger.info(f"RSVP summary for event {event_id}: {summary}")
        return summary
    except SQLAlchemyError as e:
        logger.error(f"SQLAlchemyError calculating RSVP summary for event {event_id}: {e}")
        # Fallback: if total_guests was fetched, pending is total_guests, else 0
        return {'yes': 0, 'no': 0, 'maybe': 0, 'pending': total_guests}
    except Exception as e:
        logger.error(f"Unexpected error calculating RSVP summary for event {event_id}: {e}")
        # Fallback
        return {'yes': 0, 'no': 0, 'maybe': 0, 'pending': total_guests}
