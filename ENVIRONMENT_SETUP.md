# Environment Configuration for AI Scrum Master

## Required Environment Variables

### 1. Google Gemini API Key
```bash
export GEMINI_API_KEY="your-gemini-api-key-here"
```

**How to get:**
1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create a new API key
3. Copy the key and set it as environment variable

### 2. Telegram Bot Configuration
```bash
export TELEGRAM_BOT_TOKEN="your-telegram-bot-token"
```

**How to get:**
1. Message @BotFather on Telegram
2. Create a new bot with `/newbot`
3. Copy the bot token
4. Add the bot to your target chat
5. Send a message and get chat ID from: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`

**Note:** The target chat ID `2036883627` is hardcoded in the service. 
Modify `TELEGRAM_CHAT_ID` in `main.py` if needed.

### 3. Optional Configuration
```bash
# Service configuration
export HOST="0.0.0.0"
export PORT="8001"
export LOG_LEVEL="INFO"

# Meeting bot settings
export BOT_NAME="AI-Agent"
export HEADLESS="false"
```

## Windows PowerShell Setup
```powershell
$env:GEMINI_API_KEY = "your-gemini-api-key-here"
$env:TELEGRAM_BOT_TOKEN = "your-telegram-bot-token"
```

## Windows Command Prompt Setup
```cmd
set GEMINI_API_KEY=your-gemini-api-key-here
set TELEGRAM_BOT_TOKEN=your-telegram-bot-token
```

## .env File (Alternative)
Create a `.env` file in the project root:
```
GEMINI_API_KEY=your-gemini-api-key-here
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
TELEGRAM_CHAT_ID=2036883627
HOST=0.0.0.0
PORT=8001
LOG_LEVEL=INFO
```

Then load it with:
```python
from dotenv import load_dotenv
load_dotenv()
```

## Testing Configuration
Run the health check to verify configuration:
```bash
curl http://localhost:8001/
```

Expected response:
```json
{
  "message": "AI Scrum Master Agent Service is running",
  "active_sessions": 0,
  "gemini_configured": true,
  "telegram_configured": true
}
```

## Production Deployment

### Docker Environment Variables
```dockerfile
ENV GEMINI_API_KEY=your-key
ENV TELEGRAM_BOT_TOKEN=your-token
ENV TELEGRAM_CHAT_ID=2036883627
```

### Kubernetes Secret
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: ai-scrum-master-secrets
type: Opaque
data:
  gemini-api-key: <base64-encoded-key>
  telegram-bot-token: <base64-encoded-token>
```