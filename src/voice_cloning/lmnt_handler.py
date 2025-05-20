import requests
import json
import os
import logging

logger = logging.getLogger(__name__)

def create_custom_voice(file_path, host_name, api_key):
    """
    Create a custom voice using LMNT API.
    
    Args:
        file_path (str): Path to the audio file.
        host_name (str): Name of the host for naming the voice.
        api_key (str): LMNT API key.
    
    Returns:
        str: Voice ID if successful, None otherwise.
    """
    url = "https://api.lmnt.com/v1/ai/voice"
    headers = {
        "X-API-Key": api_key
    }
    metadata = {
        "name": f"{host_name}_voice",
        "type": "instant",
        "enhance": False,
        "gender": "unknown",
        "description": f"Custom voice for {host_name}'s event"
    }
    
    try:
        with open(file_path, 'rb') as f:
            files = [
                ('metadata', (None, json.dumps(metadata), 'application/json')),
                ('files', (os.path.basename(file_path), f, 'audio/wav'))
            ]
            response = requests.post(url, headers=headers, files=files)
        
        if response.status_code == 200:
            voice_data = response.json()
            logger.debug(f"Voice created successfully: {voice_data}")
            return voice_data['id']
        else:
            logger.error(f"Failed to create voice: {response.text}")
            return None
    except Exception as e:
        logger.error(f"Error creating voice: {str(e)}")
        return None