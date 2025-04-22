import threading
import io
import time
import asyncio
from pydub import AudioSegment
import simpleaudio as sa
from deepgram import DeepgramClient, DeepgramClientOptions, PrerecordedOptions
from app.utils import DEEPGRAM_API_KEY


class TextToSpeechStreamer:
    def __init__(self, stop_event):
        self.stop_event = stop_event
        self.play_obj = None

    def stream_text(self, text):
        """Stream TTS using Deepgram SDK"""

        def tts_worker():
            try:
                # Set up async event loop for the thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self._stream_tts_async(text))
            except Exception as e:
                print(f"[TTSStreamer] Error in TTS streaming: {e}")

        threading.Thread(target=tts_worker).start()

    async def _stream_tts_async(self, text):
        """Async method to handle TTS using Deepgram SDK"""
        try:
            # Configure Deepgram client
            config = DeepgramClientOptions(options={"keepalive": "true"})
            deepgram = DeepgramClient(DEEPGRAM_API_KEY, config)

            # Set TTS parameters
            options = {
                "model": "aura-asteria-en",
                "encoding": "linear16",
                "sample_rate": 24000
            }

            # Get audio data as bytes
            response = await deepgram.speak.v("1").stream_request(text, options)

            if self.stop_event.is_set():
                print("[TTSStreamer] Stopping before playback.")
                return

            # Convert to audio and play
            buffer = response

            if buffer:
                audio = AudioSegment(
                    data=buffer,
                    sample_width=2,
                    frame_rate=24000,
                    channels=1
                )

                if self.stop_event.is_set():
                    print("[TTSStreamer] Stopping before playback.")
                    return

                self.play_obj = sa.play_buffer(
                    audio.raw_data,
                    num_channels=1,
                    bytes_per_sample=2,
                    sample_rate=24000
                )

                # Wait for playback completion unless interrupted
                while self.play_obj.is_playing() and not self.stop_event.is_set():
                    await asyncio.sleep(0.1)

                if self.stop_event.is_set() and self.play_obj.is_playing():
                    self.play_obj.stop()

        except Exception as e:
            print(f"[TTSStreamer] Error in TTS streaming: {e}")

    def stop_speech(self):
        pass