# AI Scrum Master - Complete Meeting Management System

🤖 **Comprehensive AI-powered meeting management system with Telegram Bot interface, Selenium automation, and intelligent analysis.**

## Features

- **FastAPI Service**: RESTful API to control the agent
- **Guest Login Flow**: Automatically joins meetings as "AI-Agent" 
- **Russian Caption Support**: Automatically switches caption language to Russian
- **Dual Transcription**: 
  - Visual parsing of Google Meet captions
  - Audio recording with Whisper API integration
- **Background Processing**: Non-blocking meeting participation
- **Session Management**: Multiple concurrent meeting sessions

## Requirements

- Python 3.8+
- Chrome browser installed
- Audio drivers (for audio recording features)

## Installation

1. **Clone and navigate to project:**
```bash
cd MeetAgent
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **For audio features (optional):**
```bash
pip install soundcard soundfile numpy
```

## Configuration

Set environment variables or use defaults:

```bash
# Service configuration
export HOST="0.0.0.0"
export PORT="8001"
export BACKEND_API_URL="http://localhost:8000"

# Lemonfox.ai Whisper API (for audio transcription)
export LEMONFOX_API_KEY="your-api-key-here"

# Agent behavior
export BOT_NAME="AI-Agent"
export HEADLESS="false"  # Set to "true" for headless mode
```

## Usage

### 1. Start the Service

```bash
python main.py
```

The service will start on `http://localhost:8001`

### 2. Start an Agent Session

**POST** `/start_agent`

```json
{
    "meeting_url": "https://meet.google.com/abc-defg-hij",
    "participants_info": {
        "expected_participants": ["John Doe", "Jane Smith"]
    },
    "backend_api_url": "http://localhost:8000",
    "lemonfox_api_key": "your-api-key"
}
```

**Response:**
```json
{
    "session_id": "uuid-here",
    "status": "started", 
    "message": "Agent session started successfully"
}
```

### 3. Monitor Session Status

**GET** `/agent_status/{session_id}`

```json
{
    "session_id": "uuid-here",
    "status": "active",
    "meeting_url": "https://meet.google.com/abc-defg-hij",
    "created_at": "2025-11-27T10:00:00",
    "captions_enabled": true,
    "audio_recording": true
}
```

### 4. Stop an Agent Session

**POST** `/stop_agent/{session_id}`

### 5. List Active Sessions

**GET** `/sessions`

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Health check |
| `/start_agent` | POST | Start new agent session |
| `/stop_agent/{session_id}` | POST | Stop specific session |
| `/agent_status/{session_id}` | GET | Get session status |
| `/sessions` | GET | List all active sessions |

## Meeting Join Flow

The agent follows this exact sequence:

1. **Navigate** to the Google Meet URL
2. **Enter Name** using exact XPath: `/html/body/div[1]/c-wiz/div/div/div[67]/div[3]/div/div[4]/div[4]/div/div/div[2]/div[1]/div[1]/div[3]/div[1]/span[2]/input`
3. **Wait** for admission to the meeting
4. **Enable Captions** by pressing 'c' key or clicking caption button
5. **Switch Language** to Russian using DOM class `rHGeGc-uusGie-fmcmS`

## Data Flow

### Visual Transcription
1. Parses Google Meet captions every 2 seconds
2. Buffers captions for 5 minutes or until 50 entries
3. Sends to backend: `POST {BACKEND_API_URL}/api/transcript/visual`

### Audio Transcription  
1. Records system audio in 5-minute chunks
2. Sends to Lemonfox.ai Whisper API
3. Forwards results to backend: `POST {BACKEND_API_URL}/api/transcript/whisper`

## Payload Formats

### Visual Transcript Payload
```json
{
    "session_id": "uuid",
    "captions": [
        {
            "timestamp": "2025-11-27T10:00:00",
            "speaker": "John Doe",
            "text": "Hello everyone",
            "source": "visual"
        }
    ],
    "timestamp": "2025-11-27T10:00:00"
}
```

### Whisper Transcript Payload
```json
{
    "session_id": "uuid", 
    "whisper_data": {
        "text": "Complete transcription...",
        "segments": [...],
        "language": "ru"
    },
    "timestamp": "2025-11-27T10:00:00",
    "chunk_number": 1
}
```

## Error Handling

- Automatic retries for transient failures
- Graceful degradation if audio features unavailable
- Comprehensive logging at all levels
- Session cleanup on service shutdown

## Troubleshooting

### Audio Recording Issues
If audio recording fails:
1. Check that `soundcard` and `soundfile` are installed
2. Verify system audio permissions
3. Ensure Chrome has microphone access

### Caption Parsing Issues
If captions aren't detected:
1. Verify captions are enabled in Google Meet
2. Check if meeting language is supported
3. Review browser console for JavaScript errors

### Chrome Driver Issues
If Chrome fails to start:
1. Ensure Chrome browser is installed and updated
2. Check that no other Chrome instances are running
3. Try running in headless mode: `HEADLESS=true`

## Development

### Running Tests
```bash
python -m pytest tests/
```

### Debug Mode
```bash
LOG_LEVEL=DEBUG python main.py
```

## Docker Support

See `Dockerfile` and `docker-compose.yml` for containerized deployment.

## License

This project is part of the AI Scrum Master suite.