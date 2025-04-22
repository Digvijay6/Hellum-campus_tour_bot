import threading
import time
import requests
import pyaudio
import wave
from io import BytesIO
from app.gpt_client import AzureGPT
from app.tts_streamer import TextToSpeechStreamer
from app.utils import AZURE_SPEECH_KEY, AZURE_SPEECH_REGION
from app.navigate import navigate
from app.current_location import current_location
import json


class CommandThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self._stop_event = threading.Event()
        self.gpt_client = AzureGPT()
        self.tts_streamer = TextToSpeechStreamer(stop_event=self._stop_event)

    def stop(self):
        """Trigger thread stop and clean up resources"""
        self._stop_event.set()
        self.tts_streamer.stop_speech()

    def _should_stop(self):
        """Check if stop has been requested"""
        return self._stop_event.is_set()

    def _record_audio(self):
        """Record audio using PyAudio with stop checks"""
        p = pyaudio.PyAudio()
        stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=1024
        )

        frames = []
        for _ in range(0, int(16000 / 1024 * 5)):  # 5 seconds
            if self._should_stop():
                break
            frames.append(stream.read(1024))

        stream.stop_stream()
        stream.close()
        p.terminate()
        return b''.join(frames)

    def _transcribe(self, audio_data):
        """Send audio to Azure STT REST API"""
        if self._should_stop():
            return ""

        url = f"https://{AZURE_SPEECH_REGION}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1"
        headers = {
            "Ocp-Apim-Subscription-Key": AZURE_SPEECH_KEY,
            "Content-Type": "audio/wav; codec=audio/pcm; samplerate=16000"
        }
        params = {"language": "en-US", "format": "simple"}

        try:
            response = requests.post(url, headers=headers, params=params, data=audio_data)
            return response.json().get("DisplayText", "") if response.status_code == 200 else ""
        except Exception as e:
            print(f"STT Error: {e}")
            return ""

    def run(self):
        print("[CommandThread] Starting command processing")
        try:
            # 1. Record audio
            audio_data = self._record_audio()
            if self._should_stop():
                return

            # 2. Transcribe using REST API
            text = self._transcribe(audio_data)
            print(f"Recognized: {text}")

            # 3. Process with GPT
            response = self._process_gpt(text)

            # 4. Speak response
            if response and not self._should_stop():
                self.tts_streamer.stream_text(response)

        except Exception as e:
            print(f"CommandThread error: {e}")

    def _process_gpt(self, text):
        """Handle GPT processing with interrupt checks"""
        try:
            system_message = {
                "role": "system",
                "content": "system_message = {
    "role": "system",
    "content": """
    You are Hellum, a knowledgeable AI campus tour guide at Graphic Era University (GEU). Your primary role is to provide firm and clear responses to questions, especially regarding university policies, student life, and academic expectations. Always maintain a professional and strict tone when discussing issues like dedication to academics, university standards, and behavior. 

    When answering questions, think step-by-step (Chain of Thought) to ensure logical clarity. For negative or critical questions, provide firm but constructive responses. If someone asks why they shouldn’t join Graphic Era or challenges the university’s quality, reply with a direct statement about the university’s standards and the type of students it attracts. For example: "Students who do not want to put in the effort or are not serious about their education may not thrive here, as Graphic Era demands focus and hard work from its students."

    Do not use emojis, special symbols, or non-standard punctuation as the response will be converted to speech. The tone should always be serious, firm, and reflective of the university's high standards.

    Here are a few examples to guide your behavior:

    Example 1:
    Q: Why should I join Graphic Era University?
    A: Graphic Era University offers a top-tier education with strong industry connections, high placements, and cutting-edge infrastructure. If you are committed to your education and eager to succeed, this is the right place for you.

    Example 2:
    Q: Why should I not join Graphic Era?
    A: If you are not serious about your academic growth or unwilling to put in the required effort, Graphic Era is not the place for you. This university is for students who are focused, hardworking, and dedicated to achieving excellence.

    Example 3:
    Q: What happens if I fail an exam?
    A: Failing an exam at **GEU** is not something that should be taken lightly. You’ll need to assess why you failed, seek help from professors, and prepare thoroughly for any supplementary exams. The university expects students to take responsibility for their learning.

    Example 4:
    Q: I heard the campus is not well-maintained.
    A: While no campus is perfect, Graphic Era strives for excellence in all areas, including maintenance. If you see an issue, it’s important to report it to campus services. We maintain high standards here, and your feedback helps us improve.

    Example 5:
    Q: How do I get to the Library from the Main Gate?
    A: The **Central Library** is located behind **Block A**. From the Main Gate, walk straight past the administration building, take a left, and you will see the Library ahead. Please follow me, and I will guide you there.

    """


            }
            user_message = {"role": "user", "content": text}

            if self._should_stop():
                return

            gpt_response = self.gpt_client.get_tool_response([system_message, user_message])

            if not gpt_response or self._should_stop():
                return

            message = gpt_response.choices[0].message
            function_call = message.function_call

            if function_call:
                return self._handle_function_call(function_call)
            else:
                return self._handle_text_response(message.content)

        except Exception as e:
            print(f"[CommandThread] GPT Error: {e}")
            return "Sorry, I encountered an error processing your request."

    def _handle_function_call(self, function_call):
        """Execute function calls with stop checks"""
        func_name = function_call.name
        arguments = json.loads(function_call.arguments) if isinstance(function_call.arguments,
                                                                      str) else function_call.arguments

        if self._should_stop():
            return

        if func_name == "navigate":
            destination = arguments.get("destination")
            if destination:
                result = navigate(destination)
                return result
            print("[CommandThread] Error: Missing destination")
            return "Navigation failed: No destination specified"

        elif func_name == "current_location":
            result = current_location()
            return result

        print(f"[CommandThread] Unknown function: {func_name}")
        return ""

    def _handle_text_response(self, content):
        """Handle plain text responses"""
        if content:
            print(f"[GPT RESPONSE]: {content}")
            return content
        return ""