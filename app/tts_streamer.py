import threading
import subprocess
from gtts import gTTS
from io import BytesIO

class TextToSpeechStreamer:
    def __init__(self, stop_event=None):
        self.stop_event = stop_event or threading.Event()
        self.play_proc = None

    def stream_text(self, text):
        if self.stop_event.is_set():
            return
        # Generate speech
        tts = gTTS(text=text, lang='en')
        buf = BytesIO()
        tts.write_to_fp(buf)
        buf.seek(0)

        # Play via mpg123 subprocess (stdin)
        try:
            self.play_proc = subprocess.Popen([
                'mpg123', '-q', '-'
            ], stdin=subprocess.PIPE)
            self.play_proc.stdin.write(buf.read())
            self.play_proc.stdin.close()
            self.play_proc.wait()
        except Exception as e:
            print(f"TTS playback error: {e}")
        finally:
            self.play_proc = None

    def stop_speech(self):
        # Terminate playback if running
        if self.play_proc:
            try:
                self.play_proc.terminate()
            except Exception:
                pass
            finally:
                self.play_proc = None