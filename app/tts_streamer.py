import requests
import pyaudio
import time
import wave
import threading
from io import BytesIO
from app.utils import AZURE_SPEECH_KEY, AZURE_SPEECH_REGION

class TextToSpeechStreamer:
    def __init__(self, stop_event=None):
        self.stop_event = stop_event or threading.Event()
        self.audio_queue = []
        self.p = pyaudio.PyAudio()
        self.stream = None
        self.voice_name = "en-US-AriaNeural"
        self.tts_url = f"https://{AZURE_SPEECH_REGION}.tts.speech.microsoft.com/cognitiveservices/v1"
        self.headers = {
            "Ocp-Apim-Subscription-Key": AZURE_SPEECH_KEY,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "riff-24khz-16bit-mono-pcm"
        }

    def _synthesize(self, text):
        ssml = f"""<speak version='1.0' xml:lang='en-US'>
            <voice name='{self.voice_name}'>{text}</voice>
        </speak>"""
        response = requests.post(self.tts_url, headers=self.headers, data=ssml.encode("utf-8"))
        return response.content if response.status_code == 200 else None

    def stream_text(self, text, stop_event=None):
        if self.stop_event.is_set() or (stop_event and stop_event.is_set()):
            return

        audio_data = self._synthesize(text)
        if not audio_data:
            return

        wav_file = BytesIO(audio_data)
        with wave.open(wav_file, 'rb') as wf:
            def callback(in_data, frame_count, time_info, status):
                data = wf.readframes(frame_count)
                return (data, pyaudio.paContinue)

            self.stream = self.p.open(
                format=self.p.get_format_from_width(wf.getsampwidth()),
                channels=wf.getnchannels(),
                rate=wf.getframerate(),
                output=True,
                stream_callback=callback
            )

            self.stream.start_stream()
            while self.stream.is_active():
                if self.stop_event.is_set() or (stop_event and stop_event.is_set()):
                    self.stream.stop_stream()
                    break
                time.sleep(0.1)

            self.stream.close()

    def stop_speech(self):
        if self.stream and self.stream.is_active():
            self.stream.stop_stream()
            self.stream.close()