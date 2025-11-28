"""
FastAPI Controller for AI Scrum Master Meeting Agent
Entry point for the Agent Service that handles meeting join requests
Extended with Gemini AI and Telegram integration for meeting analysis
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
import asyncio
import logging
from typing import Dict, Optional, List
import uuid
import os
from datetime import datetime
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# AI and messaging imports
import httpx

from bot_service import MeetingAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configure AI logging for detailed request/response tracking
ai_logger = logging.getLogger('ai_requests')
ai_handler = logging.FileHandler('ai.log', encoding='utf-8')  # Fix Unicode encoding
ai_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
ai_logger.addHandler(ai_handler)
ai_logger.setLevel(logging.INFO)
# Prevent propagation to root logger to avoid console encoding issues
ai_logger.propagate = False

# Configure OpenRouter AI
OPENROUTER_TOKEN = os.getenv("OPENROUTER_TOKEN")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = "2036883627"  # Specific chat ID for notifications

# OpenRouter API configuration
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "tngtech/deepseek-r1t-chimera:free"

if OPENROUTER_TOKEN:
    logger.info("OpenRouter AI configured successfully")
    ai_configured = True
else:
    logger.warning("OPENROUTER_TOKEN not set - AI features will be disabled")
    ai_configured = False

app = FastAPI(
    title="AI Scrum Master Agent Service",
    description="Production-ready service with AI analysis and Telegram notifications",
    version="2.0.0"
)

# Store active agent sessions and session history
active_sessions: Dict[str, MeetingAgent] = {}
session_history: Dict[str, Dict] = {}  # session_id -> {chunks: [], questions_asked: int, participants: set}

class StartAgentRequest(BaseModel):
    meeting_url: str
    participants_info: Optional[Dict] = None
    backend_api_url: Optional[str] = "http://localhost:8001"
    lemonfox_api_key: Optional[str] = None

class AgentResponse(BaseModel):
    session_id: str
    status: str
    message: str

# New models for transcript processing
class ChunkProcessRequest(BaseModel):
    session_id: str
    text_chunk: str
    timestamp: str

class ChunkProcessResponse(BaseModel):
    action: str = Field(..., description="Either 'ask_question' or 'continue'")
    question_text: Optional[str] = Field(None, description="Question to ask if action is 'ask_question'")
    cleaned_text: Optional[str] = Field(None, description="Cleaned version of the input text")

class FinalTranscriptRequest(BaseModel):
    session_id: str
    full_raw_transcript: str

class MeetingSummary(BaseModel):
    participants: List[str]
    key_decisions: List[str]
    action_items: List[str]
    questions_asked: List[str]
    meeting_duration: str
    summary_text: str

class FinalTranscriptResponse(BaseModel):
    success: bool
    summary: Optional[MeetingSummary] = None
    telegram_sent: bool = False
    message: str

# Utility functions for AI and messaging

async def clean_text_with_openrouter(text: str) -> str:
    """Clean and fix spelling/grammar errors in Russian text using OpenRouter AI"""
    if not ai_configured:
        logger.warning("OpenRouter not configured, returning original text")
        return text
    
    try:
        prompt = f"""
        Исправьте орфографические и грамматические ошибки в следующем русском тексте, который был получен через speech-to-text.
        Сохраните смысл и структуру текста, исправьте только очевидные ошибки распознавания речи.
        
        Текст: {text}
        
        Верните только исправленный текст без дополнительных комментариев.
        """
        
        # Log the request
        ai_logger.info(f"🔄 OPENROUTER REQUEST - clean_text")
        ai_logger.info(f"📝 Model: {OPENROUTER_MODEL}")
        ai_logger.info(f"📄 Prompt: {prompt[:200]}...")
        
        headers = {
            "Authorization": f"Bearer {OPENROUTER_TOKEN}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://meetagent.ai",
            "X-Title": "AI Scrum Master"
        }
        
        payload = {
            "model": OPENROUTER_MODEL,
            "messages": [{"role": "user", "content": prompt}]
        }
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            ai_logger.info(f"⏳ Sending request to OpenRouter...")
            response = await client.post(OPENROUTER_API_URL, headers=headers, json=payload)
            
            ai_logger.info(f"✅ Response Status: {response.status_code}")
            
            if response.status_code == 200:
                response_data = response.json()
                ai_logger.info(f"📥 Response Data: {json.dumps(response_data, indent=2, ensure_ascii=False)}")
                
                cleaned_text = response_data['choices'][0]['message']['content'].strip()
                logger.info("Text cleaned successfully with OpenRouter")
                ai_logger.info(f"✨ Cleaned Text: {cleaned_text}")
                return cleaned_text
            else:
                ai_logger.error(f"❌ OpenRouter API Error: {response.status_code} - {response.text}")
                return text
    
    except Exception as e:
        ai_logger.error(f"💥 Error cleaning text with OpenRouter: {str(e)}")
        logger.error(f"Error cleaning text with OpenRouter: {str(e)}")
        return text

async def analyze_context_with_openrouter(current_chunk: str, session_history: List[str], questions_asked: int) -> tuple[bool, str]:
    """Analyze if a clarifying question should be asked based on context"""
    if not ai_configured:
        return False, ""
    
    if questions_asked >= 2:  # Limit to 2 questions per meeting
        return False, ""
    
    try:
        context = "\n".join(session_history[-3:])  # Last 3 chunks for context
        
        prompt = f"""
        Вы - AI Scrum Master на совещании. Проанализируйте текущий фрагмент разговора и контекст предыдущих сообщений.
        
        Предыдущий контекст:
        {context}
        
        Текущий фрагмент:
        {current_chunk}
        
        Вопросов уже задано: {questions_asked}/2
        
        Определите, есть ли что-то неясное или требующее уточнения. Задавайте вопрос ТОЛЬКО если:
        1. Есть явная неопределенность в принятии решения
        2. Обсуждается важная техническая деталь без конкретики
        3. Назначаются ответственные, но неясно кто именно
        
        Ответьте в формате:
        НУЖЕН_ВОПРОС: Да/Нет
        ВОПРОС: [если да, то краткий вопрос на русском языке]
        """
        
        # Log the request
        ai_logger.info(f"🔄 OPENROUTER REQUEST - analyze_context")
        ai_logger.info(f"📝 Model: {OPENROUTER_MODEL}")
        ai_logger.info(f"📄 Prompt: {prompt[:300]}...")
        
        headers = {
            "Authorization": f"Bearer {OPENROUTER_TOKEN}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://meetagent.ai",
            "X-Title": "AI Scrum Master"
        }
        
        payload = {
            "model": OPENROUTER_MODEL,
            "messages": [{"role": "user", "content": prompt}]
        }
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            ai_logger.info(f"⏳ Sending context analysis request to OpenRouter...")
            response = await client.post(OPENROUTER_API_URL, headers=headers, json=payload)
            
            ai_logger.info(f"✅ Response Status: {response.status_code}")
            
            if response.status_code == 200:
                response_data = response.json()
                ai_logger.info(f"📥 Context Analysis Response: {json.dumps(response_data, indent=2, ensure_ascii=False)}")
                
                result = response_data['choices'][0]['message']['content'].strip()
                ai_logger.info(f"🤖 Context Analysis Result: {result}")
                
                lines = result.split('\n')
                needs_question = False
                question_text = ""
                
                for line in lines:
                    if line.startswith('НУЖЕН_ВОПРОС:'):
                        needs_question = 'Да' in line
                    elif line.startswith('ВОПРОС:'):
                        question_text = line.replace('ВОПРОС:', '').strip()
                
                logger.info(f"Context analysis: needs_question={needs_question}, question='{question_text}'")
                return needs_question, question_text
            else:
                ai_logger.error(f"❌ OpenRouter API Error: {response.status_code} - {response.text}")
                return False, ""
    
    except Exception as e:
        ai_logger.error(f"💥 Error analyzing context with OpenRouter: {str(e)}")
        logger.error(f"Error analyzing context with OpenRouter: {str(e)}")
        return False, ""

async def generate_meeting_summary(full_transcript: str, session_data: dict) -> MeetingSummary:
    """Generate structured meeting summary using OpenRouter AI"""
    if not ai_configured:
        raise HTTPException(status_code=500, detail="OpenRouter AI not configured")
    
    try:
        participants = list(session_data.get('participants', set()))
        
        prompt = f"""Проанализируй транскрипт совещания и верни ТОЛЬКО структурированную сводку в точном формате ниже. НЕ добавляй рассуждения, объяснения или дополнительный текст.

Транскрипт:
{full_transcript}

ВЕРНИ ОТВЕТ СТРОГО В ЭТОМ ФОРМАТЕ:

УЧАСТНИКИ: [имена участников через запятую, извлеченные из транскрипта]

КЛЮЧЕВЫЕ_РЕШЕНИЯ:
- [решение 1]
- [решение 2]

ЗАДАЧИ_И_ДЕЙСТВИЯ:
- [задача 1 - ответственный]
- [задача 2 - ответственный]

ВОПРОСЫ_ОБСУЖДЕННЫЕ:
- [вопрос 1]
- [вопрос 2]

ОБЩАЯ_СВОДКА:
[краткая сводка совещания в 2-3 предложениях]

ВАЖНО: Начни свой ответ сразу с "УЧАСТНИКИ:" без предисловия."""
        
        # Log the request  
        ai_logger.info(f"🔄 OPENROUTER REQUEST - generate_meeting_summary")
        ai_logger.info(f"📝 Model: {OPENROUTER_MODEL}")
        ai_logger.info(f"📄 Transcript Length: {len(full_transcript)} chars")
        ai_logger.info(f"📄 Full Prompt: {prompt}")
        
        headers = {
            "Authorization": f"Bearer {OPENROUTER_TOKEN}",
            "Content-Type": "application/json", 
            "HTTP-Referer": "https://meetagent.ai",
            "X-Title": "AI Scrum Master"
        }
        
        payload = {
            "model": OPENROUTER_MODEL,
            "messages": [{"role": "user", "content": prompt}]
        }
        
        async with httpx.AsyncClient(timeout=150.0) as client:  # Extended timeout for reasoning
            ai_logger.info(f"⏳ Sending meeting summary request to OpenRouter (may take 1-1.5 minutes for reasoning)...")
            response = await client.post(OPENROUTER_API_URL, headers=headers, json=payload)
            
            ai_logger.info(f"✅ Response Status: {response.status_code}")
            
            if response.status_code == 200:
                response_data = response.json()
                ai_logger.info(f"📥 Meeting Summary Response: {json.dumps(response_data, indent=2, ensure_ascii=False)}")
                
                raw_response = response_data['choices'][0]['message']['content'].strip()
                ai_logger.info(f"📋 Raw AI Response: {raw_response}")
                
                # Extract structured content (skip reasoning if present)
                # Look for the start of structured format
                summary_text = raw_response
                if '**УЧАСТНИКИ:**' in raw_response:
                    # Model used markdown formatting
                    summary_start = raw_response.find('**УЧАСТНИКИ:**')
                    summary_text = raw_response[summary_start:]
                    # Remove markdown formatting
                    summary_text = summary_text.replace('**', '')
                elif 'УЧАСТНИКИ:' in raw_response:
                    # Find where structured content actually starts
                    summary_start = raw_response.find('УЧАСТНИКИ:')
                    summary_text = raw_response[summary_start:]
                
                ai_logger.info(f"📋 Extracted Summary Text: {summary_text}")
            else:
                ai_logger.error(f"❌ OpenRouter API Error: {response.status_code} - {response.text}")
                raise HTTPException(status_code=500, detail=f"OpenRouter API Error: {response.status_code}")
        
        # Parse the structured response
        summary_parts = {
            'participants': [],
            'key_decisions': [],
            'action_items': [],
            'questions_asked': [],
            'summary_text': ''
        }
        
        current_section = None
        lines = summary_text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Handle both regular and markdown-formatted headers
            line_upper = line.upper().replace('**', '').replace('*', '')
            
            if line_upper.startswith('УЧАСТНИКИ:') or line.startswith('УЧАСТНИКИ:'):
                current_section = 'participants'
                # Extract participant text after the colon
                participants_text = line.split(':', 1)[1].strip() if ':' in line else ''
                # Remove markdown formatting
                participants_text = participants_text.replace('**', '').replace('*', '')
                # Remove brackets if present
                participants_text = participants_text.replace('[', '').replace(']', '')
                if participants_text and participants_text.lower() not in ['', 'нет', 'отсутствуют']:
                    # Split by comma, semicolon, or newline
                    parts = [p.strip() for p in participants_text.replace(';', ',').split(',')]
                    summary_parts['participants'] = [p for p in parts if p and len(p) > 1]
                    
            elif line_upper.startswith('КЛЮЧЕВЫЕ_РЕШЕНИЯ:') or line_upper.startswith('КЛЮЧЕВЫЕ РЕШЕНИЯ:'):
                current_section = 'key_decisions'
                
            elif line_upper.startswith('ЗАДАЧИ_И_ДЕЙСТВИЯ:') or line_upper.startswith('ЗАДАЧИ И ДЕЙСТВИЯ:'):
                current_section = 'action_items'
                
            elif line_upper.startswith('ВОПРОСЫ_ОБСУЖДЕННЫЕ:') or line_upper.startswith('ВОПРОСЫ ОБСУЖДЕННЫЕ:'):
                current_section = 'questions_asked'
                
            elif line_upper.startswith('ОБЩАЯ_СВОДКА:') or line_upper.startswith('ОБЩАЯ СВОДКА:'):
                current_section = 'summary'
                summary_content = line.split(':', 1)[1].strip() if ':' in line else ''
                summary_parts['summary_text'] = summary_content.replace('**', '').replace('*', '')
                
            elif line.startswith('- ') or line.startswith('• '):
                # Extract item (remove bullet point)
                item = line[2:].strip() if line.startswith('- ') else line[1:].strip()
                item = item.replace('**', '').replace('*', '')  # Remove markdown
                
                if current_section and current_section in summary_parts and isinstance(summary_parts[current_section], list):
                    if item and len(item) > 2:  # Avoid empty or very short items
                        summary_parts[current_section].append(item)
                        
            elif current_section == 'summary' and line and not line.startswith('УЧАСТНИКИ') and not line.startswith('КЛЮЧЕВЫЕ') and not line.startswith('ЗАДАЧИ') and not line.startswith('ВОПРОСЫ'):
                summary_parts['summary_text'] += ' ' + line
        
        # Calculate meeting duration (rough estimate)
        duration = f"~{len(session_data.get('chunks', [])) * 5} минут"
        
        # Log parsed results for debugging
        ai_logger.info(f"📊 Parsed Summary Parts:")
        ai_logger.info(f"  👥 Participants: {summary_parts['participants']}")
        ai_logger.info(f"  ✅ Key Decisions: {len(summary_parts['key_decisions'])} items")
        ai_logger.info(f"  📋 Action Items: {len(summary_parts['action_items'])} items")
        ai_logger.info(f"  ❓ Questions: {len(summary_parts['questions_asked'])} items")
        ai_logger.info(f"  📝 Summary: {summary_parts['summary_text'][:100]}...")
        
        return MeetingSummary(
            participants=summary_parts['participants'] or participants,
            key_decisions=summary_parts['key_decisions'],
            action_items=summary_parts['action_items'],
            questions_asked=summary_parts['questions_asked'],
            meeting_duration=duration,
            summary_text=summary_parts['summary_text'].strip()
        )
        
    except Exception as e:
        ai_logger.error(f"💥 Error generating summary with OpenRouter: {str(e)}")
        logger.error(f"Error generating summary with OpenRouter: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate summary: {str(e)}")

async def send_telegram_notification(summary: MeetingSummary, session_id: str) -> bool:
    """Send meeting summary to Telegram"""
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("Telegram bot token not configured")
        return False
    
    try:
        # Format message
        message = f"""🤖 *AI Scrum Master - Сводка Совещания*

📅 Сессия: `{session_id[:8]}`
⏱ Длительность: {summary.meeting_duration}

👥 *Участники:*
{chr(10).join([f"• {p}" for p in summary.participants])}

🎯 *Ключевые Решения:*
{chr(10).join([f"• {d}" for d in summary.key_decisions]) if summary.key_decisions else "• Нет принятых решений"}

✅ *Задачи и Действия:*
{chr(10).join([f"• {a}" for a in summary.action_items]) if summary.action_items else "• Задачи не назначены"}

❓ *Обсуждённые Вопросы:*
{chr(10).join([f"• {q}" for q in summary.questions_asked]) if summary.questions_asked else "• Вопросы не обсуждались"}

📝 *Сводка:*
{summary.summary_text or "Сводка не сгенерирована"}"""

        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "Markdown"
            })
        
        if response.status_code == 200:
            logger.info(f"Telegram notification sent successfully for session {session_id}")
            return True
        else:
            logger.error(f"Failed to send Telegram notification: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error sending Telegram notification: {str(e)}")
        return False

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "AI Scrum Master Agent Service is running", 
        "active_sessions": len(active_sessions),
        "openrouter_configured": ai_configured,
        "telegram_configured": TELEGRAM_BOT_TOKEN is not None
    }

@app.get("/sessions")
async def get_active_sessions():
    """Get information about active agent sessions"""
    sessions = {}
    for session_id, agent in active_sessions.items():
        sessions[session_id] = {
            "meeting_url": agent.meeting_url,
            "status": agent.status,
            "created_at": agent.created_at.isoformat() if agent.created_at else None
        }
    return {"active_sessions": sessions, "count": len(sessions)}

@app.post("/start_agent", response_model=AgentResponse)
async def start_agent(request: StartAgentRequest, background_tasks: BackgroundTasks):
    """
    Start the AI agent to join a Google Meet call
    
    Args:
        request: Contains meeting_url and optional participants_info
        background_tasks: FastAPI background tasks handler
        
    Returns:
        AgentResponse with session_id and status
    """
    try:
        # Generate unique session ID
        session_id = str(uuid.uuid4())
        
        # Validate meeting URL
        if not request.meeting_url or not request.meeting_url.startswith('https://meet.google.com/'):
            raise HTTPException(
                status_code=400, 
                detail="Invalid meeting URL. Must be a valid Google Meet URL."
            )
        
        # Create new agent instance
        agent = MeetingAgent(
            meeting_url=request.meeting_url,
            session_id=session_id,
            backend_api_url=request.backend_api_url,
            lemonfox_api_key=request.lemonfox_api_key,
            participants_info=request.participants_info
        )
        
        # Store in active sessions
        active_sessions[session_id] = agent
        
        # Initialize session history
        session_history[session_id] = {
            'chunks': [],
            'questions_asked': 0,
            'participants': set(),
            'created_at': datetime.now(),
            'status': 'active'
        }
        
        # Start agent in background task
        background_tasks.add_task(run_agent_session, session_id, agent)
        
        logger.info(f"Started new agent session {session_id} for meeting: {request.meeting_url}")
        
        return AgentResponse(
            session_id=session_id,
            status="started",
            message=f"Agent session {session_id} started successfully"
        )
        
    except Exception as e:
        logger.error(f"Error starting agent: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to start agent: {str(e)}")

@app.post("/stop_agent/{session_id}")
async def stop_agent(session_id: str):
    """Stop a specific agent session"""
    try:
        if session_id not in active_sessions:
            raise HTTPException(status_code=404, detail="Session not found")
        
        agent = active_sessions[session_id]
        await agent.stop()
        
        # Remove from active sessions
        del active_sessions[session_id]
        
        logger.info(f"Stopped agent session {session_id}")
        
        return {"session_id": session_id, "status": "stopped", "message": "Agent session stopped successfully"}
        
    except Exception as e:
        logger.error(f"Error stopping agent {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to stop agent: {str(e)}")

@app.get("/agent_status/{session_id}")
async def get_agent_status(session_id: str):
    """Get status of a specific agent session"""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    agent = active_sessions[session_id]
    return {
        "session_id": session_id,
        "status": agent.status,
        "meeting_url": agent.meeting_url,
        "created_at": agent.created_at.isoformat() if agent.created_at else None,
        "last_activity": agent.last_activity.isoformat() if agent.last_activity else None,
        "captions_enabled": agent.captions_enabled,
        "audio_recording": agent.audio_recording
    }

# New transcript processing endpoints

@app.post("/api/transcript/chunk", response_model=ChunkProcessResponse)
async def process_transcript_chunk(request: ChunkProcessRequest):
    """
    Process a 5-minute text chunk in real-time
    Cleans text with Gemini and analyzes if clarifying questions are needed
    """
    try:
        session_id = request.session_id
        
        # Initialize session history if not exists
        if session_id not in session_history:
            session_history[session_id] = {
                'chunks': [],
                'questions_asked': 0,
                'participants': set(),
                'created_at': datetime.now()
            }
        
        session_data = session_history[session_id]
        
        # Clean the text with Gemini
        cleaned_text = await clean_text_with_openrouter(request.text_chunk)
        
        # Store the cleaned chunk
        session_data['chunks'].append({
            'timestamp': request.timestamp,
            'original': request.text_chunk,
            'cleaned': cleaned_text
        })
        
        # Extract participant names (simple heuristic)
        import re
        speakers = re.findall(r'(\w+):\s', cleaned_text)
        session_data['participants'].update(speakers)
        
        # Analyze if we need to ask a clarifying question
        history_texts = [chunk['cleaned'] for chunk in session_data['chunks']]
        needs_question, question_text = await analyze_context_with_openrouter(
            cleaned_text, 
            history_texts, 
            session_data['questions_asked']
        )
        
        if needs_question and question_text:
            session_data['questions_asked'] += 1
            logger.info(f"Session {session_id}: Asking question #{session_data['questions_asked']}: {question_text}")
            return ChunkProcessResponse(
                action="ask_question",
                question_text=question_text,
                cleaned_text=cleaned_text
            )
        else:
            return ChunkProcessResponse(
                action="continue",
                cleaned_text=cleaned_text
            )
            
    except Exception as e:
        logger.error(f"Error processing chunk for session {request.session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process chunk: {str(e)}")

@app.post("/api/transcript/final", response_model=FinalTranscriptResponse)
async def process_final_transcript(request: FinalTranscriptRequest):
    """
    Process the final meeting transcript
    Generates summary and sends Telegram notification
    """
    try:
        session_id = request.session_id
        
        # Get session data
        session_data = session_history.get(session_id, {
            'chunks': [],
            'questions_asked': 0,
            'participants': set(),
            'created_at': datetime.now()
        })
        
        logger.info(f"Processing final transcript for session {session_id}")
        
        # Clean the final transcript
        cleaned_transcript = await clean_text_with_openrouter(request.full_raw_transcript)
        
        # Generate meeting summary
        summary = await generate_meeting_summary(cleaned_transcript, session_data)
        
        # Send Telegram notification
        telegram_sent = await send_telegram_notification(summary, session_id)
        
        # Mark session as completed and clean up
        if session_id in session_history:
            session_history[session_id]['status'] = 'completed'
            session_history[session_id]['completed_at'] = datetime.now()
        
        logger.info(f"Final transcript processed for session {session_id}, Telegram sent: {telegram_sent}")
        
        return FinalTranscriptResponse(
            success=True,
            summary=summary,
            telegram_sent=telegram_sent,
            message="Meeting summary generated and notification sent successfully"
        )
        
    except Exception as e:
        logger.error(f"Error processing final transcript for session {request.session_id}: {str(e)}")
        return FinalTranscriptResponse(
            success=False,
            message=f"Failed to process final transcript: {str(e)}"
        )

# Session management endpoints

@app.get("/api/session/{session_id}/history")
async def get_session_history(session_id: str):
    """Get the conversation history for a session"""
    if session_id not in session_history:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session_data = session_history[session_id]
    return {
        "session_id": session_id,
        "chunks_count": len(session_data['chunks']),
        "questions_asked": session_data['questions_asked'],
        "participants": list(session_data['participants']),
        "created_at": session_data['created_at'].isoformat(),
        "chunks": session_data['chunks'][-5:]  # Return last 5 chunks
    }

@app.delete("/api/session/{session_id}")
async def cleanup_session(session_id: str):
    """Manually cleanup a session"""
    if session_id in session_history:
        del session_history[session_id]
        logger.info(f"Cleaned up session {session_id}")
        return {"message": f"Session {session_id} cleaned up successfully"}
    else:
        raise HTTPException(status_code=404, detail="Session not found")

async def run_agent_session(session_id: str, agent: MeetingAgent):
    """
    Background task to run the agent session
    Handles both visual parsing and audio recording
    """
    try:
        logger.info(f"Starting agent session {session_id}")
        
        # Start the agent (this will run in background)
        await agent.start()
        
        logger.info(f"Agent session {session_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Agent session {session_id} failed: {str(e)}")
        agent.status = "error"
        agent.error_message = str(e)
    
    finally:
        # Clean up session after completion or error
        if session_id in active_sessions:
            # Keep session for a while to allow status checking
            # In production, you might want to implement a cleanup task
            pass

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up all active sessions on shutdown"""
    logger.info("Shutting down agent service, cleaning up active sessions...")
    
    for session_id, agent in active_sessions.items():
        try:
            await agent.stop()
            logger.info(f"Cleaned up session {session_id}")
        except Exception as e:
            logger.error(f"Error cleaning up session {session_id}: {str(e)}")
    
    active_sessions.clear()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)