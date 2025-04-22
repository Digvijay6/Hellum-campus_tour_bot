import threading
import pyaudio
from deepgram import DeepgramClient, DeepgramClientOptions, SpeakWSOptions, SpeakWebSocketEvents
from app.utils import DEEPGRAM_API_KEY

class TextToSpeechStreamer:
    def __init__(self, stop_event=None):
        self.stop_event = stop_event or threading.Event()
        # Configure client to disable automatic playback
        config = DeepgramClientOptions(options={"speaker_playback": "false"})
        self.deepgram_client = DeepgramClient(DEEPGRAM_API_KEY, config)
        self.voice = "aura"
        self.p = pyaudio.PyAudio()
        self.stream = None

    def stream_text(self, text):
        if self.stop_event.is_set():
            return
        dg_conn = self.deepgram_client.speak.websocket.v("1")
        options = SpeakWSOptions(model="aura-asteria-en", encoding="linear16", sample_rate=24000)

        def on_audio(data, **kwargs):
            if self.stop_event.is_set():
                dg_conn.finish()
                return
            if self.stream is None:
                self.stream = self.p.open(format=self.p.get_format_from_width(2), channels=1, rate=24000, output=True)
            try:
                self.stream.write(data)
            except Exception as e:
                print(f"TTS playback error: {e}")
                dg_conn.finish()

        dg_conn.on(SpeakWebSocketEvents.AudioData, on_audio)
        dg_conn.on(SpeakWebSocketEvents.Error, lambda err, **kw: print(f"TTS Error: {err}"))

        dg_conn.start(options)
        dg_conn.send_text(text)
        dg_conn.flush()
        try:
            dg_conn.wait_for_complete()
        except Exception:
            pass
        dg_conn.finish()

        # Clean up
        self.stop_speech()

    def stop_speech(self):
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception as e:
                print(f"Error stopping TTS stream: {e}")
            finally:
                self.stream = None