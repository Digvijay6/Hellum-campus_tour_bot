# Hellum Campus Tour Bot

A conversational AI-powered tour guide for campus visitors, built with OpenAI API integration and Streamlit.

## Overview

Hellum Campus Tour Bot provides an interactive and informative virtual tour experience for visitors to our campus. Using natural language processing and AI, it answers questions, provides directions, and shares information about campus facilities, history, events, and more.

## Features

- **Natural conversation**: Engage with the tour bot through a chat interface
- **Campus information**: Get details about buildings, departments, facilities, and services
- **Wayfinding**: Receive directions to navigate around campus
- **Event information**: Learn about upcoming events and activities
- **History and facts**: Discover interesting facts and historical information about the campus

## Technology Stack

- Python
- Streamlit (for web interface)
- OpenAI API (for natural language processing)
- Langchain (for conversational context management)

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/Digvijay6/Hellum-campus_tour_bot.git
   cd Hellum-campus_tour_bot
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up environment variables:
   - Create a `.env` file in the root directory
   - Add your OpenAI API key:
     ```
     OPENAI_API_KEY=your_api_key_here
     ```

## Usage

1. Start the application:
   ```bash
   streamlit run app.py
   ```

2. Open your browser and navigate to the URL displayed in the terminal (typically http://localhost:8501)

3. Begin chatting with the campus tour bot!

## Project Structure

```
Hellum-campus_tour_bot/
├── app.py                  # Main Streamlit application
├── chat_engine.py          # Core conversational logic
├── campus_data/            # Campus information database
├── utils/                  # Utility functions
├── requirements.txt        # Project dependencies
└── README.md               # Project documentation
```

## Customization

### Adding Campus Information

To add or update campus information, edit the files in the `campus_data/` directory. The information is organized by category (buildings, services, events, etc.).

### Modifying the Chat Interface

The UI components can be customized in `app.py` using Streamlit's widgets and styling options.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

Distributed under the MIT License. See `LICENSE` for more information.

## Contact

Digvijay - [GitHub Profile](https://github.com/Digvijay6)

Project Link: [https://github.com/Digvijay6/Hellum-campus_tour_bot](https://github.com/Digvijay6/Hellum-campus_tour_bot)
