import os
import platform
from dotenv import load_dotenv

load_dotenv()

# Load environment variables
PV_ACCESS_KEY = os.getenv("PV_ACCESS_KEY")

AZURE_SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY")
AZURE_SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION")

AZURE_OPENAI_ENDPOINT = os.getenv("ENDPOINT_URL")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
DEPLOYMENT_NAME = os.getenv("DEPLOYMENT_NAME")
DEEPGRAM_API_KEY = "3aa9424c62c32d7f23955b66250bcfc746afc1ca"

STT_TIMEOUT = 10  # seconds for speech recognition
TTS_TIMEOUT = 60   # seconds for speech synthesis
AUDIO_RECORD_TIMEOUT = 5  # seconds for audio recording
WAKE_INTERRUPT_TIMEOUT = 0.7  # seconds for thread joining


def get_wakeword_path():
    """Choose wakeword .ppn file based on platform."""
    system = platform.system().lower()
    if system == "linux":
        return "assets/hellum_pi.ppn"
    else:
        return "assets/hellum_win.ppn"
