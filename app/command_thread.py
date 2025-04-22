import threading
import time
import pyaudio
from google.cloud import speech
from google.oauth2 import service_account
from app.gpt_client import AzureGPT
from app.tts_streamer import TextToSpeechStreamer
from app.navigate import navigate
from app.current_location import current_location
import json

class CommandThread(threading.Thread):
    def __init__(self):
        super().__init__()
        self._stop_event = threading.Event()
        self.gpt_client = AzureGPT()
        self.tts_streamer = TextToSpeechStreamer(stop_event=self._stop_event)
        # Initialize Google Cloud Speech-to-Text client
        creds = service_account.Credentials.from_service_account_file(
            'gen-lang-client.json'
        )
        self.speech_client = speech.SpeechClient(credentials=creds)

    def stop(self):
        """Trigger thread stop and clean up resources"""
        self._stop_event.set()
        self.tts_streamer.stop_speech()

    def _should_stop(self):
        return self._stop_event.is_set()

    def _record_audio(self):
        """Record up to 8 seconds or until 0.3s of silence"""
        pa = pyaudio.PyAudio()
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=1024
        )
        frames = []
        start = time.time()
        silence_threshold = 500  # adjust as needed
        silent_chunks = 0
        max_duration = 8.0

        while time.time() - start < max_duration and not self._should_stop():
            data = stream.read(1024, exception_on_overflow=False)
            frames.append(data)
            # simple silence detection
            if max(data) < silence_threshold:
                silent_chunks += 1
                if silent_chunks > 3:  # ~0.3s of silence
                    break
            else:
                silent_chunks = 0

        stream.stop_stream()
        stream.close()
        pa.terminate()
        return b''.join(frames)

    def _transcribe(self, audio_data):
        """Synchronous recognition of recorded audio"""
        audio = speech.RecognitionAudio(content=audio_data)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code='en-US'
        )
        try:
            response = self.speech_client.recognize(config=config, audio=audio)
            if response.results:
                return response.results[0].alternatives[0].transcript
        except Exception as e:
            print(f"Google STT error: {e}")
        return ""

    def run(self):
        print("[CommandThread] Starting command processing")
        # 1. Record audio
        audio_data = self._record_audio()
        if self._should_stop() or not audio_data:
            return

        # 2. Transcribe
        text = self._transcribe(audio_data)
        print(f"Recognized: {text}")
        if not text:
            return

        # 3. Process with GPT
        response = self._process_gpt(text)

        # 4. Speak response
        if response and not self._should_stop():
            self.tts_streamer.stream_text(response)

    def _process_gpt(self, text):
        try:
            system_message = {"role": "system", "content": "You are Hellum, a friendly and knowledgeable AI campus tour guide..."}
            user_message = {"role": "user", "content": text}
            if self._should_stop():
                return
            gpt_response = self.gpt_client.get_tool_response([system_message, user_message])
            if not gpt_response or self._should_stop():
                return
            msg = gpt_response.choices[0].message
            if msg.function_call:
                return self._handle_function_call(msg.function_call)
            return msg.content
        except Exception as e:
            print(f"[CommandThread] GPT Error: {e}")
            return "Sorry, an error occurred."

    def _handle_function_call(self, function_call):
        name = function_call.name
        args = json.loads(function_call.arguments)
        if self._should_stop():
            return
        if name == "navigate":
            dest = args.get("destination")
            return navigate(dest) if dest else "Navigation failed: No destination."
        if name == "current_location":
            return current_location()
        return ""