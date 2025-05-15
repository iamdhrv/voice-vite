"""
ElevenLabs Handler for VoiceVite.

Handles interactions with the ElevenLabs API for voice synthesis.
"""
import os
from elevenlabs.client import ElevenLabs
from elevenlabs import play, save

from config import config

class ElevenLabsHandler:
    """A client to interact with the ElevenLabs API for voice synthesis."""

    def __init__(self, api_key: str):
        """
        Initializes the ElevenLabsHandler with the API key.

        Args:
            api_key (str): The ElevenLabs API key.
        """
        if not api_key:
            raise ValueError("ElevenLabs API key is required.")
        self.client = ElevenLabs(api_key=api_key)
        self.default_voice_id = "21m00Tcm4TlvDq8ikWAM"  # Pre-made voice "Rachel"

    def list_available_voices(self) -> list:
        """
        Lists all available pre-made and cloned voices in your ElevenLabs account.

        Returns:
            list: A list of Voice objects.
        """
        try:
            voices = self.client.voices.get_all()
            return voices.voices
        except Exception as e:
            print(f"Error listing ElevenLabs voices: {e}")
            return []

    def get_default_voice_id(self) -> str:
        """
        Returns the default pre-made voice ID.

        Returns:
            str: The default voice ID.
        """
        return self.default_voice_id

    def generate_audio_from_text(self, text: str, voice_id: str, output_path: str | None = None) -> bytes | None:
        """
        Generates audio from text using a specified voice ID.

        Args:
            text (str): The text to synthesize.
            voice_id (str): The ID of the voice to use (pre-made or cloned).
            output_path (str, optional): If provided, saves the audio to this file path.

        Returns:
            bytes | None: The audio data as bytes if output_path is None, or None if generation failed.
        """
        try:
            audio_stream = self.client.generate(
                text=text,
                voice=voice_id,
                model="eleven_multilingual_v2"
            )
            audio_bytes = b"".join(audio_stream)

            if output_path:
                save(audio_bytes, output_path)
                print(f"Audio saved to {output_path}")
                return None
            return audio_bytes
        except Exception as e:
            print(f"Error generating audio with ElevenLabs for voice ID '{voice_id}': {e}")
            return None

    def play_audio(self, audio_bytes: bytes):
        """
        Plays audio bytes using the default audio output.

        Args:
            audio_bytes (bytes): The audio data to play.
        """
        try:
            play(audio_bytes)
        except Exception as e:
            print(f"Error playing audio with ElevenLabs: {e}")

if __name__ == '__main__':
    if not config.ELEVENLABS_API_KEY:
        print("ElevenLabs API Key not found in config. Please set it.")
    else:
        handler = ElevenLabsHandler(api_key=config.ELEVENLABS_API_KEY)
        print("ElevenLabsHandler initialized.")

        print("\n--- Testing TTS Generation ---")
        test_voice_id = handler.get_default_voice_id()
        print(f"Using Voice ID for TTS: {test_voice_id}")
        sample_text = "Hello, this is a test of the ElevenLabs integration for VoiceVite!"
        output_audio_file = "test_elevenlabs_output.mp3"

        print(f"Generating audio and saving to '{output_audio_file}'...")
        handler.generate_audio_from_text(sample_text, test_voice_id, output_path=output_audio_file)
        if os.path.exists(output_audio_file):
            print(f"Audio file '{output_audio_file}' created successfully.")
        else:
            print(f"Failed to create audio file '{output_audio_file}'.")