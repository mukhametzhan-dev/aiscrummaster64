# AI Scrum Master Telegram Bot

## Overview
This Telegram bot serves as a frontend interface to control an AI Scrum Master agent that can join Google Meet sessions, monitor conversations, and generate meeting summaries.

## Features
- 🤖 **Agent Management**: Start and stop AI agents for Google Meet sessions
- 📊 **Real-time Status**: Live updates on agent status during meetings  
- ❓ **Agent Questions**: Forward questions from the AI agent to users
- 📝 **Meeting Summaries**: Generate AI-powered meeting summaries with action items
- 🎯 **Jira Integration**: Mock Jira task creation from meeting outcomes
- 📂 **Session History**: View past meeting sessions

## Setup

### 1. Environment Configuration
Create a `.env` file with your tokens:
```
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
BACKEND_URL=http://localhost:8001
```

### 2. Install Dependencies
```bash
pip install aiogram aiohttp python-dotenv
```

### 3. Start Backend Server
Ensure your FastAPI backend is running:
```bash
python main.py
```

### 4. Start Bot
```bash
python bot.py
```

## Bot Usage Flow

### 1. Start the Bot
Send `/start` to the bot to see the main menu with options:
- 📞 **Начать созвон** - Start a new meeting session
- 📂 **Мои созвоны** - View meeting history

### 2. Starting a Meeting
1. Click "Начать созвон"
2. Send a Google Meet link (must contain `meet.google.com`)
3. Bot will start the AI agent and show real-time status updates:
   - 🟡 Агент запускает браузер...
   - 🟠 Агент ждет разрешения на вход...
   - 🟢 Агент успешно присоединился к звонку!

### 3. During the Meeting
- Bot polls agent status every 3 seconds
- Agent questions are forwarded to you in real-time
- Once agent joins, you get a "🛑 Завершить созвон" button

### 4. Ending a Meeting
1. Click "🛑 Завершить созвон" or send `/stop`
2. Bot generates meeting summary using AI
3. Summary is sent with Jira integration options:
   - 🚀 **Создать задачи в Jira** - Create tasks from meeting
   - ❌ **Отмена** - Cancel

### 5. Jira Integration (Mock)
- Clicking "Создать задачи в Jira" extracts action items from the summary
- Creates inline buttons for each task
- Tasks are parsed from bullet points in the summary

## Technical Architecture

### State Management
Uses aiogram FSM with two main states:
- `WaitingForLink`: Waiting for Google Meet URL
- `MeetingInProgress`: Agent is active in meeting

### Backend Communication
The bot communicates with FastAPI backend via these endpoints:
- `POST /start_agent` - Start new meeting agent
- `GET /agent_status/{session_id}` - Poll agent status
- `POST /stop_agent/{session_id}` - Stop agent and get summary
- `GET /sessions?user_id={user_id}` - Get meeting history

### Session Management
- In-memory session storage per user
- Background asyncio tasks for status polling
- Automatic cleanup when meetings end

## Error Handling
- Backend connectivity issues are handled gracefully
- Agent failures are reported to users
- Polling tasks are properly cancelled on bot shutdown
- Invalid Google Meet URLs are rejected

## Testing
Run the backend connectivity test:
```bash
python test_bot_backend.py
```

This will verify that the backend is running and endpoints are accessible.

## Supported Backend Response Formats

### Start Agent Response
```json
{
  "session_id": "uuid-string",
  "status": "starting"
}
```

### Agent Status Response  
```json
{
  "status": "joined|waiting|starting|error|finished",
  "last_question": "Optional question from agent"
}
```

### Stop Agent Response
```json
{
  "summary": "Meeting summary text...",
  "action_items": ["Task 1", "Task 2", "Task 3"]
}
```

## Logging
The bot logs important events:
- Bot startup with token info
- Backend communication errors  
- Status polling events
- Session management actions

All logs use structured format with timestamps and levels.