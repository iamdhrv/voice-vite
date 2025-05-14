"""
ElevenLabs Handler for VoiceVite.

Handles interactions with the ElevenLabs API for voice cloning and TTS.
"""
import requests
import os
from elevenlabs import set_api_key, Voice, VoiceSettings, generate, play, save
from elevenlabs.api import Voices, VoiceClone, Samples

from config import config # Assuming your config.py is in the root

class ElevenLabsHandler:
    """A client to interact with the ElevenLabs API for voice cloning and synthesis."""

    def __init__(self, api_key: str):
        """
        Initializes the ElevenLabsHandler with the API key.

        Args:
            api_key (str): The ElevenLabs API key.
        """
        if not api_key:
            raise ValueError("ElevenLabs API key is required.")
        self.api_key = api_key
        set_api_key(api_key)

    def list_available_voices(self) -> list:
        """
        Lists all available pre-made and cloned voices in your ElevenLabs account.

        Returns:
            list: A list of Voice objects.
        """
        try:
            voices = Voices.from_api()
            return voices
        except Exception as e:
            print(f"Error listing ElevenLabs voices: {e}")
            return []

    def clone_voice(self, voice_name: str, description: str, audio_file_paths: list[str]) -> str | None:
        """
        Clones a new voice using provided audio samples.

        Args:
            voice_name (str): The name for the new cloned voice.
            description (str): A description for the voice.
            audio_file_paths (list[str]): A list of paths to audio files (e.g., .mp3, .wav)
                                          for cloning. At least 1MB of audio is recommended.

        Returns:
            str | None: The ID of the newly cloned voice, or None if cloning failed.
        """
        if not audio_file_paths:
            print("Error: No audio files provided for voice cloning.")
            return None

        try:
            # Ensure files exist
            for f_path in audio_file_paths:
                if not os.path.exists(f_path):
                    print(f"Error: Audio file not found at {f_path}")
                    return None
            
            cloned_voice: VoiceClone = VoiceClone.create(
                name=voice_name,
                description=description,
                files=audio_file_paths
            )
            return cloned_voice.voice_id
        except Exception as e:
            print(f"Error cloning voice '{voice_name}' with ElevenLabs: {e}")
            return None

    def generate_audio_from_text(self, text: str, voice_id: str, output_path: str | None = None) -> bytes | None:
        """
        Generates audio from text using a specified voice ID.

        Args:
            text (str): The text to synthesize.
            voice_id (str): The ID of the voice to use (cloned or pre-made).
            output_path (str, optional): If provided, saves the audio to this file path (e.g., 'audio.mp3').
                                         Otherwise, returns the audio bytes.

        Returns:
            bytes | None: The audio data as bytes if output_path is None, or None if generation failed.
                          If output_path is provided, returns None on success (file is saved).
        """
        try:
            # You might want to customize VoiceSettings
            audio_bytes = generate(
                text=text,
                voice=Voice(
                    voice_id=voice_id,
                    # settings=VoiceSettings(stability=0.71, similarity_boost=0.5, style=0.0, use_speaker_boost=True)
                )
                # model="eleven_multilingual_v2" # or other models
            )
            
            if output_path:
                save(audio_bytes, output_path)
                print(f"Audio saved to {output_path}")
                return None # Indicate success by saving file
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

# Example Usage (for testing purposes)
if __name__ == '__main__':
    if not config.ELEVENLABS_API_KEY:
        print("ElevenLabs API Key not found in config. Please set it.")
    else:
        handler = ElevenLabsHandler(api_key=config.ELEVENLABS_API_KEY)
        print("ElevenLabsHandler initialized.")

        # --- Test Listing Voices ---
        # print("\n--- Listing Available Voices ---")
        # available_voices = handler.list_available_voices()
        # if available_voices:
        #     print(f"Found {len(available_voices)} voices:")
        #     for v in available_voices:
        #         print(f"  - Name: {v.name}, ID: {v.voice_id}, Category: {v.category}")
        # else:
        #     print("No voices found or error listing them.")

        # --- Test Voice Cloning (Requires audio files) ---
        # print("\n--- Testing Voice Cloning (Commented out by default) ---")
        # # Create dummy audio files for testing if you don't have any.
        # # IMPORTANT: Voice cloning requires significant audio data (ideally > 1 min, >1MB total).
        # # Using very short or poor quality audio will result in bad clones.
        # # This example assumes you have 'sample1.mp3' and 'sample2.mp3' in the current directory.
        # # dummy_audio_files = ["sample1.mp3", "sample2.mp3"] 
        # # for f in dummy_audio_files:
        # #    if not os.path.exists(f):
        # #        with open(f, 'wb') as audio_file: # Create tiny dummy files if they don't exist
        # #            audio_file.write(os.urandom(1024*50)) # 50KB dummy data, NOT SUITABLE FOR REAL CLONING
        # #        print(f"Created dummy audio file: {f}. REPLACE WITH REAL AUDIO FOR CLONING.")
        
        # # cloned_voice_id = handler.clone_voice(
        # #     voice_name="MyClonedVoiceTest", 
        # #     description="A test clone for VoiceVite.", 
        # #     audio_file_paths=dummy_audio_files # Replace with actual paths to good audio samples
        # # )
        # # if cloned_voice_id:
        # #     print(f"Voice cloned successfully! Voice ID: {cloned_voice_id}")
        # # else:
        # #     print("Voice cloning failed.")
        cloned_voice_id = None # Set this if you have a cloned voice ID

        # --- Test Text-to-Speech Generation ---
        print("\n--- Testing TTS Generation ---")
        # Use a pre-existing voice ID or one you cloned.
        # Find a voice ID from your ElevenLabs account (e.g., a pre-made one like Rachel's: '21m00Tcm4TlvDq8ikWAM')
        test_voice_id = cloned_voice_id if cloned_voice_id else "21m00Tcm4TlvDq8ikWAM" # Default to Rachel if no clone
        
        if not test_voice_id:
            print("No voice ID available for TTS test. Please clone a voice or use a pre-made one.")
        else:
            print(f"Using Voice ID for TTS: {test_voice_id}")
            sample_text = "Hello, this is a test of the ElevenLabs integration for VoiceVite!"
            output_audio_file = "test_elevenlabs_output.mp3"
            
            # Generate and save to file
            print(f"Generating audio and saving to '{output_audio_file}'...")
            handler.generate_audio_from_text(sample_text, test_voice_id, output_path=output_audio_file)
            if os.path.exists(output_audio_file):
                print(f"Audio file '{output_audio_file}' created successfully.")
                # To play it (optional, ensure ffplay or similar is installed and in PATH for `play`)
                # print("Attempting to play the generated audio...")
                # audio_bytes_for_play = handler.generate_audio_from_text(sample_text, test_voice_id)
                # if audio_bytes_for_play:
                #    handler.play_audio(audio_bytes_for_play)
            else:
                print(f"Failed to create audio file '{output_audio_file}'.")
        pass