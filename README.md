# Hellum Campus Tour Bot

An intelligent AI-powered physical robot tour guide for campus visitors, built with Streamlit and integrated with OpenAI's language models.

## Overview

The Hellum Campus Tour Bot serves as an interactive physical tour guide for visitors and new students, providing information about campus facilities, directions, services, and answering questions in real-time through a conversational interface. This robot navigates the campus autonomously while offering detailed descriptions and information about important campus locations and landmarks.

## Features

- **Interactive Conversational Interface**: Easy-to-use chat interface for natural interactions
- **Campus Information**: Details about buildings, departments, facilities, and services
- **Autonomous Navigation**: Hardware-integrated robot that physically guides visitors around campus
- **Location-Aware Descriptions**: Automatically detects and describes important locations as it navigates
- **Navigation Assistance**: Physical guidance and directions for moving around campus
- **Event Information**: Updates on campus events, schedules, and activities
- **Personalized Responses**: AI-powered responses tailored to specific user queries
- **Knowledge Base**: Comprehensive information about campus history, rules, and resources

## Technology Stack

- **Python**: Core programming language
- **Streamlit**: Web application framework for the user interface
- **OpenAI API**: Powers the natural language understanding and response generation
- **Langchain**: For managing conversation context and knowledge base integration
- **dotenv**: For secure environment variable management
- **Hardware Integration**: Custom robotics platform with navigation capabilities
- **Computer Vision**: Location recognition and mapping systems

## Installation

1. Clone the repository:
   ```bash
   git clone -b Final-beta https://github.com/Digvijay6/Hellum-campus_tour_bot.git
   cd Hellum-campus_tour_bot
   ```

2. Create and activate a virtual environment (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file in the root directory with your API key:
   ```
   OPENAI_API_KEY=your_openai_api_key_here
   ```

5. Hardware Setup:
   - Connect to the robot's onboard computer
   - Configure the navigation parameters in `config/robot_config.yml`
   - Calibrate sensors using the provided calibration script

## Usage

1. Start the application:
   ```bash
   streamlit run app.py
   ```

2. Power on the robot hardware and ensure connectivity

3. Open your web browser and go to http://localhost:8501 (or the URL displayed in your terminal)

4. Select a tour route or specific locations to visit

5. The robot will navigate to each location while providing detailed information about important campus landmarks

6. Interact with the tour bot by typing your questions in the chat interface as you go

## Robot Navigation Features

The Hellum Campus Tour Bot is integrated with custom hardware that enables physical navigation around campus. Key features include:

- **Autonomous Navigation**: Robot can move between buildings and points of interest without human guidance
- **Location Recognition**: Uses computer vision and mapping to identify current location
- **Interactive Tours**: Stops at important locations to provide detailed descriptions and historical information
- **Custom Tour Routes**: Pre-programmed routes highlighting different aspects of campus (academic buildings, recreational facilities, etc.)
- **Dynamic Obstacle Avoidance**: Safely navigates around people and unexpected obstacles
- **Voice Announcements**: Verbal descriptions of landmarks synchronized with physical location

## Customizing the Bot

### Adding Campus Information

1. Update the data files in the `data/` directory with specific campus information
2. The bot automatically incorporates this information into its responses

### Modifying Response Behavior

1. Adjust prompt templates in `chat_handler.py` to change how the bot responds
2. Modify the system message to give the bot different personality traits or knowledge focus

### Configuring Navigation

1. Edit waypoints and routes in the navigation configuration files
2. Add new points of interest with corresponding descriptions in the landmarks database

## Deployment

The application can be deployed using:

1. **Robot Hardware**: Install on the robot's onboard computer
2. **Streamlit Cloud**: For remote monitoring and control
3. **Custom Mobile App**: Companion app for users to interact with the robot

Remember to set up environment variables securely on your chosen platform.

## Contributing

Contributions to improve the Hellum Campus Tour Bot are welcome! To contribute:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-addition`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-addition`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contact

Digvijay - [GitHub Profile](https://github.com/Digvijay6)

Project Link: [https://github.com/Digvijay6/Hellum-campus_tour_bot](https://github.com/Digvijay6/Hellum-campus_tour_bot)
