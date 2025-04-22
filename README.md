# Hellum: Campus Tour Voice Assistant 🚗🎤

This is a fully autonomous voice bot for campus navigation using:
- Wake Word Detection (Porcupine)
- Azure Speech-to-Text
- Azure OpenAI Function Calling (GPT-4o)
- Text-to-Speech Streaming
- Always listening for wake word "Hellum"

---

## Setup

1. Clone the repo.
2. Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3. Set environment variables:
    - Copy `.env.example` ➔ `.env`
    - Fill your keys.
4. Add wake word models:
    - `hellum_win.ppn` for Windows
    - `hellum_pi.ppn` for Raspberry Pi
5. Run:
    ```bash
    python main.py
    ```

---

## Folder Structure

