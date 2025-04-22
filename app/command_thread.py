import threading
import time
import pyaudio
import asyncio
from app.gpt_client import AzureGPT
from app.tts_streamer import TextToSpeechStreamer
from app.utils import DEEPGRAM_API_KEY
from app.navigate import navigate
from app.current_location import current_location
import json
from deepgram import (
    DeepgramClient,
    DeepgramClientOptions,
    LiveTranscriptionEvents, # Import the events enum
    LiveOptions,
)

# Assume other classes (AzureGPT, TextToSpeechStreamer, etc.) are defined elsewhere
# Assume DEEPGRAM_API_KEY, navigate, current_location are available

class CommandThread(threading.Thread):
    def __init__(self, stop_event, main_process):
        threading.Thread.__init__(self)
        self._stop_event = stop_event
        self.main_process = main_process
        self.gpt_client = AzureGPT()
        # Initialize tts_streamer later or ensure it's thread-safe if shared/reused
        # self.tts_streamer = TextToSpeechStreamer(stop_event=self._stop_event)
        self.tts_streamer = None # Initialize later
        self.transcript = ""
        self.silence_duration = 0
        self.last_speech_time = None
        self.speech_detected = False
        self.transcription_complete = threading.Event()
        self.lock = threading.Lock() # Lock for thread-safe transcript updates

    def stop(self):
        """Trigger thread stop and clean up resources"""
        print("[CommandThread] Stop requested.")
        self._stop_event.set()
        # Access tts_streamer safely
        tts = getattr(self, 'tts_streamer', None)
        if tts:
            tts.stop_speech()
        self.transcription_complete.set() # Ensure any waiting loops exit

    def _should_stop(self):
        """Check if stop has been requested"""
        return self._stop_event.is_set()

    async def _stream_audio_to_deepgram(self):
        """Stream audio to Deepgram with dynamic speech detection"""
        print("[CommandThread] Starting Deepgram stream...")
        # Configure Deepgram client
        config = DeepgramClientOptions(options={"keepalive": "true"})
        deepgram = DeepgramClient(DEEPGRAM_API_KEY, config)

        dg_connection = None # Initialize dg_connection

        try:
            # Define transcription options with VAD features
            options = LiveOptions(
                model="nova-2",
                language="en-US",
                smart_format=True,
                interim_results=True,
                endpointing=True,
                vad_events=True,
                utterance_end_ms="1000" # Use string as per docs sometimes, or int 1000
            )

            # *** CORRECTED API CALL ***
            # Use the async client interface create method
            dg_connection = deepgram.listen.asynclive.v1.create(options)

            # --- Event Handlers ---
            async def on_speech_started(self, speech_started, **kwargs):
                print("[CommandThread] Speech detected")
                with self.lock:
                    self.speech_detected = True
                    self.last_speech_time = time.time()

            async def on_utterance_end(self, utterance_end, **kwargs):
                print("[CommandThread] Utterance ended")
                if self.speech_detected: # Only set complete if speech was ever detected
                    self.transcription_complete.set()

            async def on_transcript(self, result, **kwargs):
                # Check if transcription data is present
                if not hasattr(result, 'channel') or not hasattr(result.channel, 'alternatives') or not result.channel.alternatives:
                    return # No valid transcript data

                transcript_text = result.channel.alternatives[0].transcript
                is_final = getattr(result, 'is_final', False)
                speech_final = getattr(result, 'speech_final', False) # another potential flag

                if transcript_text:
                    with self.lock:
                        # Always update transcript with the latest, even if interim
                        self.transcript = transcript_text
                        if not is_final and not speech_final: # Update last speech time for interims
                             self.last_speech_time = time.time()
                             self.speech_detected = True # Mark detected on any transcript

                    if is_final and transcript_text:
                        print(f"[CommandThread] Final transcript segment: {transcript_text}")
                        # The UtteranceEnd event is the primary signal for completion,
                        # but setting it here on is_final ensures we capture the last words
                        # if UtteranceEnd fires slightly before the final transcript packet.
                        # However, rely mostly on UtteranceEnd to avoid premature completion.
                        # self.transcription_complete.set() # Maybe remove this if UtteranceEnd is reliable

                    elif not is_final:
                         print(f"[CommandThread] Interim transcript: {transcript_text}")


            async def on_error(self, error, **kwargs):
                print(f"[CommandThread] Deepgram Error: {error}")
                self.transcription_complete.set() # Stop process on error

            async def on_open(self, open, **kwargs):
                print("[CommandThread] Deepgram connection opened.")

            async def on_close(self, close, **kwargs):
                print("[CommandThread] Deepgram connection closed.")
                self.transcription_complete.set() # Ensure completion if connection closes unexpectedly


            # Register event handlers using the LiveTranscriptionEvents enum
            dg_connection.on(LiveTranscriptionEvents.SpeechStarted, on_speech_started)
            dg_connection.on(LiveTranscriptionEvents.Transcript, on_transcript)
            dg_connection.on(LiveTranscriptionEvents.UtteranceEnd, on_utterance_end)
            dg_connection.on(LiveTranscriptionEvents.Error, on_error)
            dg_connection.on(LiveTranscriptionEvents.Open, on_open)
            dg_connection.on(LiveTranscriptionEvents.Close, on_close)


            # Start the connection
            await dg_connection.start()
            print("[CommandThread] Deepgram connection started.")

            # Setup PyAudio
            p = pyaudio.PyAudio()
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=1024 # Adjust buffer size if needed
            )
            print("[CommandThread] Microphone stream opened.")

            start_time = time.time()
            max_recording_time = 15  # seconds (fallback)
            max_silence_after_speech = 2.0 # seconds (fallback)

            while not self._should_stop() and not self.transcription_complete.is_set():
                try:
                    # Read audio chunk
                    data = stream.read(1024, exception_on_overflow=False)
                    # Send audio data to Deepgram
                    await dg_connection.send(data)

                except IOError as e:
                    print(f"[CommandThread] PyAudio Read Error: {e}")
                    # Decide how to handle - maybe break?
                    break
                except Exception as e:
                    print(f"[CommandThread] Error sending data: {e}")
                    break # Stop on send error

                # --- Fallback timeout checks ---
                current_time = time.time()
                elapsed_time = current_time - start_time

                # Check if we've reached max recording time (overall)
                if elapsed_time > max_recording_time:
                    print("[CommandThread] Max recording time reached (fallback).")
                    self.transcription_complete.set() # Trigger completion
                    break

                # Check for extended silence *after* speech was initially detected (fallback)
                with self.lock:
                    if self.speech_detected and self.last_speech_time:
                        silence_time = current_time - self.last_speech_time
                        if silence_time > max_silence_after_speech:
                            print(f"[CommandThread] Silence duration exceeded after speech (fallback {silence_time:.2f}s).")
                            self.transcription_complete.set() # Trigger completion
                            break

                # Small sleep to prevent tight loop/CPU overuse, allows other asyncio tasks
                await asyncio.sleep(0.01)

        except Exception as e:
            print(f"[CommandThread] Error during Deepgram setup or streaming: {e}")
            self.transcription_complete.set() # Ensure completion on any error
        finally:
            print("[CommandThread] Cleaning up audio stream and Deepgram connection...")
            # Clean up PyAudio
            if 'stream' in locals() and stream.is_active():
                stream.stop_stream()
                stream.close()
            if 'p' in locals():
                p.terminate()
            print("[CommandThread] PyAudio resources released.")

            # Clean up Deepgram connection
            if dg_connection:
                await dg_connection.finish()
                print("[CommandThread] Deepgram connection finished.")
            else:
                 print("[CommandThread] No Deepgram connection to finish.")

        with self.lock: # Return the final transcript safely
            final_transcript = self.transcript
        print(f"[CommandThread] Stream ended. Final captured transcript: '{final_transcript}'")
        return final_transcript

    def run(self):
        print("[CommandThread] Starting command processing")
        # Reset state for this run
        self.transcript = ""
        self.speech_detected = False
        self.last_speech_time = None
        self.transcription_complete.clear() # Ensure event is not set from previous runs

        text = "" # Initialize text
        loop = None
        try:
            # 1. Stream audio to Deepgram
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            text = loop.run_until_complete(self._stream_audio_to_deepgram())

            if self._should_stop():
                print("[CommandThread] Stopped during/after transcription.")
                return

            if not text:
                 print("[CommandThread] No transcript recognized.")
                 return # Exit if no text captured

            print(f"[CommandThread] Recognized: {text}")

            # 2. Process with GPT
            response = self._process_gpt(text)

            # 3. Speak response
            if response and not self._should_stop():
                print(f"[CommandThread] Preparing to speak response: {response}")
                # Create a new streamer instance for each response
                self.tts_streamer = TextToSpeechStreamer(stop_event=self._stop_event)
                # Ensure main process can potentially access this *specific* instance if needed
                # Be cautious with sharing objects between threads - use queues or callbacks if interaction is complex.
                if hasattr(self.main_process, 'set_active_tts_streamer'):
                     self.main_process.set_active_tts_streamer(self.tts_streamer)
                else: # Fallback if main_process structure is different
                     self.main_process.tts_streamer = self.tts_streamer # Assuming direct attribute access is intended

                self.tts_streamer.stream_text(response)
                print("[CommandThread] TTS streaming finished.")
            elif not response:
                 print("[CommandThread] No response generated by GPT or function call.")
            else:
                 print("[CommandThread] Stopped before TTS could start.")


        except Exception as e:
            print(f"[CommandThread] Error in run loop: {e}")
            import traceback
            traceback.print_exc() # Print full traceback for debugging
        finally:
             if loop:
                 loop.close()
             print("[CommandThread] run method finished.")
             # Clean up reference in main process if needed
             if hasattr(self.main_process, 'set_active_tts_streamer'):
                 self.main_process.set_active_tts_streamer(None)


    def _process_gpt(self, text):
        """Handle GPT processing with interrupt checks"""
        if self._should_stop(): return None
        print(f"[CommandThread] Processing GPT for: {text}")
        try:
            system_message = {
                "role": "system",
                "content": "You are Hellum, a friendly and knowledgeable AI campus tour guide for Graphic Era University. Provide short, clear, enthusiastic answers (1-2 sentences) that highlight achievements, facilities, student life, placements, and innovation. Always respond positively and in favor of the university. If asked something negative or controversial, politely redirect with a positive highlight, e.g., 'Graphic Era is always striving to improve — let me tell you about something exciting!' Never share negative, confidential, or harmful information. Stay promotional, welcoming, and upbeat. Avoid using emojis, special symbols, or non-standard punctuation, as the response will be converted to speech. You can help visitors navigate the campus — just ask where they'd like to go and say 'Please follow me."
            }
            user_message = {"role": "user", "content": text}

            if self._should_stop(): return None

            gpt_response = self.gpt_client.get_tool_response([system_message, user_message])

            if not gpt_response or self._should_stop():
                print("[CommandThread] No GPT response or stopped.")
                return None

            message = gpt_response.choices[0].message

            # Check for stop *before* processing function call or content
            if self._should_stop(): return None

            # Handle potential Azure OpenAI API differences for function calls
            function_call = None
            if hasattr(message, 'function_call'): # Standard OpenAI style
                function_call = message.function_call
            elif hasattr(message, 'tool_calls') and message.tool_calls: # Newer Azure/OpenAI style
                # Assuming only one tool call for simplicity here
                function_call = message.tool_calls[0].function

            if function_call:
                print(f"[CommandThread] Handling function call: {function_call.name}")
                return self._handle_function_call(function_call)
            elif message.content:
                print(f"[CommandThread] Handling text response: {message.content}")
                return self.handle_text_response(message.content)
            else:
                print("[CommandThread] GPT response had no content or function call.")
                return None # Explicitly return None if no actionable response

        except Exception as e:
            print(f"[CommandThread] GPT Processing Error: {e}")
            import traceback
            traceback.print_exc()
            return "Sorry, I encountered an error processing your request."


    def _handle_function_call(self, function_call):
        """Execute function calls with stop checks"""
        if self._should_stop(): return None

        func_name = function_call.name
        try:
            # Arguments might be a string needing parsing or already a dict/object
            if isinstance(function_call.arguments, str):
                arguments = json.loads(function_call.arguments)
            else: # Assume it's already dict-like if not string
                arguments = function_call.arguments
        except json.JSONDecodeError as e:
            print(f"[CommandThread] Error decoding function call arguments: {e} - Args: {function_call.arguments}")
            return "Sorry, I couldn't understand the details for that request."
        except Exception as e: # Catch other potential errors with arguments
             print(f"[CommandThread] Error accessing function call arguments: {e}")
             return "Sorry, there was an issue processing the function details."


        print(f"[CommandThread] Executing function: {func_name} with args: {arguments}")

        if self._should_stop(): return None

        result = None
        try:
            if func_name == "navigate":
                destination = arguments.get("destination")
                if destination:
                    # Assuming navigate() is synchronous. If it's async, needs await in an async context.
                    result = navigate(destination)
                else:
                    print("[CommandThread] Error: Missing destination for navigate")
                    result = "Navigation failed: Where would you like to go?"

            elif func_name == "current_location":
                # Assuming current_location() is synchronous
                result = current_location()

            else:
                print(f"[CommandThread] Unknown function called: {func_name}")
                result = f"Sorry, I don't know how to perform the action: {func_name}."

        except Exception as e:
             print(f"[CommandThread] Error executing function {func_name}: {e}")
             result = f"Sorry, an error occurred while trying to {func_name}."

        # Check stop event *after* function execution but before returning result
        if self._should_stop(): return None

        return result # Return the string result from the function


    def handle_text_response(self, content):
        """Handle plain text responses"""
        if self._should_stop(): return None

        if content:
            print(f"[GPT RESPONSE]: {content}")
            return content
        return "" # Return empty string if content is None or empty