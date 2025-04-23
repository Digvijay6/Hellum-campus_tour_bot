import os
import threading
import time
from app.command_thread import CommandThread
from app.utils import get_wakeword_path, PV_ACCESS_KEY
import pvporcupine
from pvrecorder import PvRecorder
import platform
from dotenv import load_dotenv
from app.send_command import send_command_to_arduino


load_dotenv()


class MainProcess:
    def __init__(self):
        self._stop_event = threading.Event()
        self.current_command_thread = None
        self.porcupine = None
        self.recorder = None

    def get_wakeword_path(self):
        system = platform.system().lower()
        return "assets/hellum_pi.ppn" if system == "linux" else "assets/hellum_win.ppn"

    def _initialize_audio(self):
        """Initialize wake word detection resources"""
        try:
            if not PV_ACCESS_KEY:
                raise ValueError("Missing Porcupine access key")

            # Use the provided util function to obtain the wake word asset path.
            wakeword_path = get_wakeword_path()
            self.porcupine = pvporcupine.create(
                access_key=PV_ACCESS_KEY,
                keyword_paths=[wakeword_path],
                sensitivities=[0.7]
            )
            self.recorder = PvRecorder(
                frame_length=self.porcupine.frame_length,
                device_index=-1
            )
            self.recorder.start()
        except Exception as e:
            print(f"Audio initialization failed: {e}")
            self.cleanup()
            raise

    def start_wakeword_detection(self):
        """Main loop for continuous wake word detection"""
        try:
            self._initialize_audio()
            print("Listening for wake word 'Hellum'...")

            while not self._stop_event.is_set():
                try:
                    pcm = self.recorder.read()
                    result = self.porcupine.process(pcm)

                    if result >= 0:
                        print("\nWake word detected!")
                        self._handle_wakeword()

                    time.sleep(0.01)  # Prevent CPU overuse

                except Exception as e:
                    print(f"Detection error: {e}")
                    break  # Break only on critical errors

        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            self.cleanup()

    def _handle_wakeword(self):
        """Handle wake word detection event"""
        # Stop current command thread if it is already running.
        if self.current_command_thread and self.current_command_thread.is_alive():
            print("Interrupting previous command")
            self.current_command_thread.stop()
            self.current_command_thread.join(timeout=0.5)

        # Start the command thread (for processing voice commands, etc.).
        self.current_command_thread = CommandThread()
        self.current_command_thread.start()

        # Start a new thread to send LED commands.
        led_thread = threading.Thread(target=self.send_led_command)
        led_thread.start()

    def send_led_command(self):
        """Send LED_ON then after a delay send LED_OFF to the Arduino."""
        try:
            print("Sending LED_ON command to Arduino")
            send_command_to_arduino("LED_ON")
            time.sleep(2)
            print("Sending LED_OFF command to Arduino")
            send_command_to_arduino("LED_OFF")
        except Exception as e:
            print(f"Error sending LED command: {e}")

    def cleanup(self):
        """Clean up all resources"""
        print("Cleaning up resources...")
        self._stop_event.set()

        if self.recorder:
            try:
                self.recorder.stop()
                self.recorder.delete()
            except Exception as e:
                print(f"Error stopping recorder: {e}")

        if self.porcupine:
            try:
                self.porcupine.delete()
            except Exception as e:
                print(f"Error cleaning up porcupine: {e}")


if __name__ == "__main__":
    main_process = MainProcess()
    try:
        main_process.start_wakeword_detection()
    except Exception as e:
        print(f"Fatal error: {e}")
        main_process.cleanup()
