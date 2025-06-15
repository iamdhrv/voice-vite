"""
Handler for Google's Gemini AI integration for generating dynamic scripts.
"""
import os
from google import genai
from google.genai import types
from typing import Dict, Optional, Union
import logging
from config import config

# Configure logging
logger = logging.getLogger(__name__)

# Initialize the client
client = genai.Client(api_key=config.GEMINI_API_KEY)

class GeminiHandler:
    def __init__(self, voice_gender: str = 'female', host_name: str = None):
        """Initialize the Gemini handler with API key from config, voice gender, and host name.
        
        Args:
            voice_gender (str): 'male', 'female', or 'custom' to determine assistant name
            host_name (str, optional): Host name to use as assistant name for custom voice
        """
        self.voice_gender = voice_gender.lower()
        
        # Set assistant name based on voice selection
        if self.voice_gender == 'male':
            self.assistant_name = 'Rohan'
        elif self.voice_gender == 'custom' and host_name:
            self.assistant_name = host_name.strip()
        else:  # Default to female if no custom name or if custom without host_name
            self.assistant_name = 'Eva'
        
        if not config.GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY not found in config. Gemini integration will be disabled.")
            self.enabled = False
            return
            
        try:
            self.enabled = True
            logger.info(f"Gemini AI initialized successfully with assistant name '{self.assistant_name}'")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini: {str(e)}")
            self.enabled = False
    
    def generate_script(self, event_data: Dict, guest_name: str = "Guest") -> Optional[str]:
        """
        Generate a personalized invitation script using Gemini AI.
        
        Args:
            event_data: Dictionary containing event details
            guest_name: Name of the guest to personalize the script
            
        Returns:
            str: Generated script or None if generation fails
        """
        if not self.enabled:
            logger.warning("Gemini integration is disabled")
            return None
            
        try:
            # Prepare the prompt for Gemini
            prompt = self._build_prompt(event_data, guest_name)
            
            # Generate content using the chat model
            response = client.models.generate_content(
                model='gemini-2.5-flash-preview-04-17',
                contents=prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=1000,
                    temperature=0.7,
                )
            )
            
            return response.text
            
        except Exception as e:
            logger.error(f"Error generating script with Gemini: {str(e)}")
            return None
    
    def _build_prompt(self, event_data: Dict, guest_name: str) -> str:
        """Build the prompt for an AI to generate a 'Voice Assistant Invitation Protocol'
        based on event data, focusing on conciseness and clarity."""

        # Use the instance's assistant name and service name
        assistant_name = self.assistant_name
        service_name = "VoiceVite"

        # Get event details with fallbacks
        event_type = event_data.get('event_type', 'an event')
        host_name = event_data.get('host_name', 'the host')
        event_date = event_data.get('event_date', 'an upcoming date')
        event_time = event_data.get('event_time', 'a convenient time')
        location = event_data.get('location', 'the venue')
        duration = event_data.get('duration', 'a few hours')
        special_instructions_raw = event_data.get('special_instructions', 'None')
        cultural_preferences_raw = event_data.get('cultural_preferences', 'None')
        rsvp_deadline = event_data.get('rsvp_deadline', 'as soon as possible')

        # Prepare conditional text for special instructions and cultural preferences
        special_instructions_text = ""
        if special_instructions_raw and special_instructions_raw.lower() != 'none' and special_instructions_raw.strip():
            special_instructions_text = f"Quick note: {special_instructions_raw}."

        cultural_preferences_text = ""
        if cultural_preferences_raw and cultural_preferences_raw.lower() != 'none' and cultural_preferences_raw.strip():
            cultural_preferences_text = f"And it will have a {cultural_preferences_raw} touch."

        # Construct the detailed prompt
        prompt = f"""You are an AI Prompt Engineer specializing in creating comprehensive persona and interaction guides for voice assistants. Your task is to generate such a guide, which will be used to instruct a voice assistant on how to handle event invitations efficiently and pleasantly.

        Given the following core event details, generate a complete 'Voice Assistant Invitation Protocol'. This protocol should be structured robustly, but with a strong, explicit emphasis on making the voice assistant's interactions concise, efficient, and engaging ("short yet sweet"). The goal is to eliminate unnecessary conversational filler while ensuring all critical information is exchanged and collected clearly.

        The generated protocol must be personalized using the provided event details where appropriate (e.g., in example dialogue for the voice assistant).

        Input Event Details:
        *   Event Type: {event_type}
        *   Host Name: {host_name}
        *   Target Guest Name (for example scripting): {guest_name}
        *   Event Date: {event_date}
        *   Event Time: {event_time}
        *   Location: {location}
        *   Duration: {duration}
        *   Special Instructions: {special_instructions_raw if special_instructions_raw.strip() else 'None'}
        *   Cultural Preferences/Notes (if any): {cultural_preferences_raw if cultural_preferences_raw.strip() else 'None'}
        *   RSVP Deadline: {rsvp_deadline}
        *   Voice Assistant Name: {assistant_name}
        *   Service Name: {service_name}

        Output: 'Voice Assistant Invitation Protocol'

        Your generated protocol should include the following sections, all designed to embody the "short yet sweet" philosophy:

        1.  Identity & Purpose:
            *   Assistant: {assistant_name} from {service_name}.
            *   Purpose: To efficiently invite {guest_name} to {host_name}'s {event_type}, provide key details, and collect their RSVP.

        2.  Voice & Persona:
            *   Personality: Friendly, efficient, clear, helpful, respectful of the guest's time.
            *   Speech Characteristics: Clear and direct language, natural contractions, polite but not overly verbose. Measured pace for key details, otherwise brisk and focused.

        3.  Streamlined Conversation Flow (with concise example dialogue):
            *   A. Introduction:
                *   "Hello, this is {assistant_name} from {service_name}, calling on behalf of {host_name}. May I speak with {guest_name}, please?"
                *   *(If confirmed guest):* "Great, {guest_name}. {host_name} would love to invite you to their {event_type}!"
            *   B. Core Event Details (Immediate & Clear):
                *   "It's on {event_date} at {event_time}, at {location}. It’s planned for about {duration}."
                *   {special_instructions_text}
                *   {cultural_preferences_text}
            *   C. Availability Check & Initial RSVP Probe:
                *   "Does that sound like something you might be able to attend?"
            *   D. RSVP Collection (Direct & Simple):
                *   *(If positive or unsure):* "Wonderful! To help {host_name} plan, could you let me know if that’s a 'Yes,' 'No,' or 'Maybe' for now? The RSVP deadline is {rsvp_deadline}."
                *   *(If negative):* "Okay, thank you for letting us know."
            *   E. Confirmation of RSVP:
                *   "Thanks! I've recorded your RSVP as [Yes/No/Maybe] for {host_name}'s {event_type} on {event_date}. Is that correct?"
            *   F. Reminder Option (if Yes/Maybe):
                *   "Would you like a quick reminder a few days before the event?"
            *   G. Wrap-up (Brief & Polite):
                *   "Excellent. Thank you so much, {guest_name}! We [hope to see you there / appreciate you letting us know]. Have a great day!"

        4.  Response Guidelines (Focus on Brevity & Clarity):
            *   Keep assistant responses highly focused and to the point.
            *   Use explicit, brief confirmations.
            *   Ask one direct question at a time.
            *   Avoid jargon or overly formal language.

        5.  Concise Scenario Handling:
            *   If Guest is Busy/Wants to Call Back: "Understood! When would be a better time for a quick 1-minute call, or can I send these details via text?"
            *   If Guest Asks Detail Questions Beyond Scope: "That's a great question for {host_name} directly. My main role is to share the core details and get your RSVP. Can I help with those?"
            *   If Voicemail: "Hello {guest_name}, this is {assistant_name} from {service_name} calling for {host_name} with an invitation to their {event_type} on {event_date} at {event_time} at {location}. {('Key info: ' + special_instructions_raw + '. ') if special_instructions_raw and special_instructions_raw.lower() != 'none' and special_instructions_raw.strip() else ''}Please RSVP by {rsvp_deadline} if you can. Thanks!"

        6.  Knowledge Base (Core Data for this Specific Event):
            *   Event: {host_name}'s {event_type}
            *   Date & Time: {event_date}, {event_time}
            *   Location: {location}
            *   Duration: {duration}
            *   Special Instructions: {special_instructions_raw if special_instructions_raw.strip() else 'None'}
            *   Cultural Notes: {cultural_preferences_raw if cultural_preferences_raw.strip() else 'None'}
            *   RSVP By: {rsvp_deadline}

        7.  Call Management Notes (Efficiency Focused):
            *   If Checking Details: "One moment, please."
            *   Technical Issues: "Apologies, a slight delay. I'm back."
            *   Goal: Complete the call efficiently while ensuring the guest feels informed and valued, not rushed. Aim for an average call length of 60-90 seconds for a standard RSVP.
        """
        return prompt

# Create a default instance (will be updated with actual values when needed)
gemini_handler = GeminiHandler(voice_gender='female')
