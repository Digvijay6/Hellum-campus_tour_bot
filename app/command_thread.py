import threading
import time
import pyaudio
import wave
from io import BytesIO
from deepgram import (
    DeepgramClient,
    DeepgramClientOptions,
    LiveOptions,
    LiveTranscriptionEvents,
    PrerecordedOptions,
    FileSource
)
from app.gpt_client import AzureGPT
from app.tts_streamer import TextToSpeechStreamer
from app.utils import DEEPGRAM_API_KEY
from app.navigate import navigate
from app.current_location import current_location
import json
import asyncio

class CommandThread(threading.Thread):
    def __init__(self):
        super().__init__()
        self._stop_event = threading.Event()
        self.gpt_client = AzureGPT()
        self.tts_streamer = TextToSpeechStreamer(stop_event=self._stop_event)
        config = DeepgramClientOptions(options={
            "keep_alive": True,
            "auto_flush_reply_delta": 5000
        })
        self.deepgram_client = DeepgramClient(DEEPGRAM_API_KEY, config)

    def stop(self):
        """Trigger thread stop and clean up resources"""
        self._stop_event.set()
        self.tts_streamer.stop_speech()

    def _should_stop(self):
        return self._stop_event.is_set()

    def _stream_transcribe(self):
        """Stream mic to Deepgram, return final transcript on silence/end or after max duration, with fallback."""
        transcript = ""
        done = threading.Event()

        # Prepare buffer for fallback
        pcm_buffer = BytesIO()
        pa = pyaudio.PyAudio()
        # Wave writer for fallback WAV file
        wf = wave.open(pcm_buffer, 'wb')
        wf.setnchannels(1)
        wf.setsampwidth(pa.get_sample_size(pyaudio.paInt16))
        wf.setframerate(16000)

        # Deepgram websocket
        dg_conn = self.deepgram_client.listen.websocket.v("1")
        options = LiveOptions(
            model="nova-2",
            interim_results=True,
            language="en-US"
        )

        def handle_transcript(result, **kwargs):
            nonlocal transcript
            alt = result.channel.alternatives[0]
            text = alt.transcript.strip()
            if not text:
                return
            if alt.is_final:
                transcript = text
                dg_conn.finish()
                done.set()
            else:
                print(f"Interim: {text}")

        def handle_error(error, **kwargs):
            print(f"Deepgram streaming error: {error}")
            dg_conn.finish()
            done.set()

        dg_conn.on(LiveTranscriptionEvents.Transcript, handle_transcript)
        dg_conn.on(LiveTranscriptionEvents.Error, handle_error)
        dg_conn.start(options)

        # Open mic
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=1024
        )

        start_time = time.time()
        max_duration = 8.0

        # Stream and buffer
        while not done.is_set() and not self._should_stop():
            if time.time() - start_time >= max_duration:
                print("Max recording duration reached; finalizing stream")
                try:
                    dg_conn.finish()
                except Exception:
                    pass
                done.set()
                break
            try:
                data = stream.read(1024, exception_on_overflow=False)
                if data:
                    dg_conn.send(data)
                    wf.writeframes(data)
                pcm_buffer.write(data)
            except Exception as e:
                print(f"Streaming send error: {e}")
                break

        # Clean up mic
        stream.stop_stream()
        stream.close()
        pa.terminate()
        wf.close()

        # Wait for websocket finish
        try:
            dg_conn.finish()
        except Exception:
            pass
        done.wait()

        # Fallback if empty
        if not transcript:
            try:
                buffer_bytes = pcm_buffer.getvalue()
                pre_opts = PrerecordedOptions(
                    model="nova-2",
                    smart_format=True,
                    language="en-US"
                )
                resp = asyncio.run(
                    self.deepgram_client.listen.prerecorded.v("1").transcribe_file(
                        FileSource(buffer=buffer_bytes, mimetype="audio/wav"),
                        pre_opts
                    )
                )
                ch = resp.results.channels[0]
                transcript = ch.alternatives[0].transcript
                print(f"Fallback transcript: {transcript}")
            except Exception as e:
                print(f"Fallback STT error: {e}")

        return transcript

    def run(self):
        print("[CommandThread] Starting command processing")
        try:
            text = self._stream_transcribe()
            if self._should_stop():
                return
            print(f"Recognized: {text}")

            response = self._process_gpt(text)
            if response and not self._should_stop():
                self.tts_streamer.stream_text(response)
        except Exception as e:
            print(f"CommandThread error: {e}")

    def _process_gpt(self, text):
        try:
            system_message = {"role": "system", "content": "You are Hellum..."}
            user_message = {"role": "user", "content": text}
            if self._should_stop(): return
            gpt_response = self.gpt_client.get_tool_response([system_message, user_message])
            if not gpt_response or self._should_stop(): return
            message = gpt_response.choices[0].message
            if message.function_call:
                return self._handle_function_call(message.function_call)
            else:
                return self._handle_text_response(message.content)
        except Exception as e:
            print(f"[CommandThread] GPT Error: {e}")
            return "Sorry, I encountered an error processing your request."

    def _handle_function_call(self, function_call):
        func_name = function_call.name
        args = json.loads(function_call.arguments)
        if self._should_stop(): return
        if func_name == "navigate":
            return navigate(args.get("destination")) if args.get("destination") else "Navigation failed: No destination specified"
        if func_name == "current_location":
            return current_location()
        return ""

    def _handle_text_response(self, content):
        return content or ""