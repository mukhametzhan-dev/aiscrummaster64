"""
Bot Service for AI Scrum Master Meeting Agent
Handles Selenium automation, audio capture, and API integrations
"""

import asyncio
import threading
import time
import datetime
import logging
import requests
import tempfile
import os
from typing import Dict, Optional, Set
import json
import httpx

# Audio recording imports
try:
    import soundcard as sc
    import soundfile as sf
    import numpy as np
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False
    logging.warning("Audio recording not available. Install soundcard and soundfile for audio features.")

# Selenium imports
# Fix for distutils compatibility with Python 3.12+
import distutils_fix

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException

logger = logging.getLogger(__name__)

class MeetingAgent:
    """
    AI Scrum Master Agent for Google Meet
    Handles both visual parsing (subtitles) and audio recording with Whisper integration
    """
    
    def __init__(self, meeting_url: str, session_id: str, backend_api_url: str = "http://localhost:8001", 
                 lemonfox_api_key: str = None, participants_info: Dict = None, headless: bool = False):
        self.meeting_url = meeting_url
        self.session_id = session_id
        self.backend_api_url = backend_api_url
        self.lemonfox_api_key = lemonfox_api_key  # Not used, kept for compatibility
        self.participants_info = participants_info or {}
        self.headless = headless
        
        # Status tracking
        self.status = "initializing"
        self.created_at = datetime.datetime.now()
        self.last_activity = None
        self.error_message = None
        self.captions_enabled = False
        self.audio_recording = False  # Always False - audio disabled
        
        # Selenium setup
        self.driver = None
        self.wait = None
        self.seen_captions: Set[str] = set()
        
        # Control flags
        self.should_stop = False
        self.visual_parsing_active = False
        
        logger.info(f"Initialized MeetingAgent {session_id} for meeting: {meeting_url} (captions-only mode)")
    
    async def start(self):
        """Start the agent - both visual parsing and audio recording"""
        try:
            self.status = "starting"
            
            # Initialize Chrome driver
            await self._initialize_driver()
            
            # Join the meeting with enhanced flow
            await self._join_meeting_enhanced()
            
            # Start visual parsing in background thread
            visual_thread = threading.Thread(target=self._run_visual_parsing, daemon=True)
            visual_thread.start()
            
            # Audio recording disabled - using only visual captions
            logger.info("Audio recording disabled - using only visual caption parsing")
            
            self.status = "active"
            self.last_activity = datetime.datetime.now()
            
            # Keep the session alive
            await self._monitor_session()
            
        except Exception as e:
            logger.error(f"Error starting agent {self.session_id}: {str(e)}")
            self.status = "error"
            self.error_message = str(e)
            raise
    
    async def stop(self):
        """Stop the agent and clean up resources"""
        logger.info(f"Stopping agent {self.session_id}")
        
        self.should_stop = True
        self.status = "stopping"
        
        # Send final transcript for processing
        try:
            self._send_final_transcript()
        except Exception as e:
            logger.error(f"Error sending final transcript: {str(e)}")
        
        # Close browser
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                logger.error(f"Error closing driver: {str(e)}")
        
        self.status = "stopped"
        logger.info(f"Agent {self.session_id} stopped successfully")
    
    async def _initialize_driver(self):
        """Initialize Chrome driver with appropriate options"""
        logger.info("Initializing Chrome driver...")
        
        options = uc.ChromeOptions()
        if self.headless:
            options.add_argument('--headless')
        
        # Enhanced Chrome options for better stability
        options.add_argument("--disable-infobars")
        options.add_argument("--start-maximized")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--use-fake-ui-for-media-stream")
        options.add_argument("--disable-web-security")
        options.add_argument("--allow-running-insecure-content")
        options.add_argument("--disable-features=VizDisplayCompositor")
        
        # Grant microphone and camera permissions
        prefs = {
            "profile.default_content_setting_values": {
                "media_stream_mic": 1,
                "media_stream_camera": 1,
                "notifications": 1
            }
        }
        options.add_experimental_option("prefs", prefs)
        
        self.driver = uc.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, 20)
        
        logger.info("Chrome driver initialized successfully")
    
    async def _join_meeting_enhanced(self):
        """Enhanced meeting join flow with exact specifications"""
        logger.info("Starting enhanced meeting join flow...")
        
        try:
            # Step A: Go to the URL
            logger.info(f"Navigating to meeting URL: {self.meeting_url}")
            self.driver.get(self.meeting_url)
            await asyncio.sleep(3)
            
            # Step B: Input name "AI-Agent"
            logger.info("Looking for name input field...")
            name_input_xpath = "/html/body/div[1]/c-wiz/div/div/div[67]/div[3]/div/div[4]/div[4]/div/div/div[2]/div[1]/div[1]/div[3]/div[1]/span[2]/input"
            
            try:
                name_input = self.wait.until(EC.element_to_be_clickable((By.XPATH, name_input_xpath)))
                name_input.clear()
                name_input.send_keys("AI-Agent")
                name_input.send_keys(Keys.ENTER)
                logger.info("Name 'AI-Agent' entered successfully")
                await asyncio.sleep(2)
            except TimeoutException:
                # Fallback: try alternative selectors for name input
                logger.warning("Primary name input not found, trying alternative selectors...")
                alternative_selectors = [
                    "input[placeholder*='name']",
                    "input[aria-label*='name']",
                    "input[type='text'][jsname]",
                ]
                
                for selector in alternative_selectors:
                    try:
                        name_input = self.driver.find_element(By.CSS_SELECTOR, selector)
                        name_input.clear()
                        name_input.send_keys("AI-Agent")
                        name_input.send_keys(Keys.ENTER)
                        logger.info(f"Name entered using fallback selector: {selector}")
                        break
                    except NoSuchElementException:
                        continue
                else:
                    logger.error("Could not find name input field with any selector")
            
            # Step C: Wait for admission to meeting
            logger.info("Waiting for admission to meeting...")
            await asyncio.sleep(5)
            
            # Look for indicators that we're in the meeting
            meeting_indicators = [
                "//div[contains(@aria-label, 'meeting')]",
                "//div[contains(@class, 'uGOf1d')]",  # Common Meet UI class
                "//button[contains(@aria-label, 'camera')]",
                "//button[contains(@aria-label, 'microphone')]"
            ]
            
            for indicator in meeting_indicators:
                try:
                    self.wait.until(EC.presence_of_element_located((By.XPATH, indicator)))
                    logger.info("Successfully admitted to meeting")
                    break
                except TimeoutException:
                    continue
            else:
                logger.warning("Could not confirm meeting admission")
            
            # Step D: Enable Captions
            await self._enable_captions()
            
            # Skip language switching as requested
            logger.info("Skipping language switching as requested")
            
            logger.info("Enhanced meeting join flow completed successfully")
            
        except Exception as e:
            logger.error(f"Error in enhanced meeting join flow: {str(e)}")
            raise
    
    async def _enable_captions(self):
        """Enable captions using keyboard shortcut and button click"""
        logger.info("Enabling captions...")
        
        try:
            # Method 1: Try keyboard shortcut 'c'
            body = self.driver.find_element(By.TAG_NAME, "body")
            body.send_keys("c")
            await asyncio.sleep(2)
            logger.info("Pressed 'c' key for captions")
            
            # Method 2: Try clicking caption button
            caption_selectors = [
                "//button[contains(translate(@aria-label, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'turn on captions')]",
                "//button[contains(@aria-label, 'تفعيل')]",
                "//button[contains(@data-tooltip, 'caption')]",
                "//div[contains(@aria-label, 'caption')]//button"
            ]
            
            for selector in caption_selectors:
                try:
                    caption_button = self.wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                    caption_button.click()
                    logger.info(f"Clicked caption button using selector: {selector}")
                    self.captions_enabled = True
                    await asyncio.sleep(2)
                    break
                except TimeoutException:
                    continue
            
            if not self.captions_enabled:
                logger.warning("Could not find caption button, assuming captions enabled via keyboard")
                self.captions_enabled = True
            
            # Verify captions are actually working
            await asyncio.sleep(3)  # Wait for captions to appear
            await self._verify_captions_working()
            
        except Exception as e:
            logger.error(f"Error enabling captions: {str(e)}")
    
    async def _verify_captions_working(self):
        """Verify that captions are actually appearing on the page"""
        logger.info("Verifying captions are working...")
        
        try:
            # Look for caption indicators
            caption_indicators = [
                "*[aria-live='polite']",
                "[jsname='YSxPC']",
                ".a4cQT",
                "[data-caption-text]",
                ".captions-text",
                ".zs7s8d.jxFHg",
                ".iTTPOb"
            ]
            
            found_caption_elements = False
            for indicator in caption_indicators:
                elements = self.driver.find_elements(By.CSS_SELECTOR, indicator)
                if elements:
                    logger.info(f"✅ Found {len(elements)} potential caption elements with selector: {indicator}")
                    found_caption_elements = True
                    
                    # Log some sample text
                    for i, elem in enumerate(elements[:3]):  # Check first 3 elements
                        text = elem.text.strip()
                        if text:
                            logger.info(f"   Element {i+1}: '{text[:100]}...'")
                
            if not found_caption_elements:
                logger.warning("❌ No caption elements found! Captions may not be enabled.")
                # Try to enable captions again
                logger.info("Trying to enable captions again...")
                body = self.driver.find_element(By.TAG_NAME, "body")
                body.send_keys("c")
            else:
                logger.info("✅ Caption elements detected - parsing should work")
                
        except Exception as e:
            logger.error(f"Error verifying captions: {str(e)}")
    
    async def _switch_language_to_russian(self):
        """Switch caption language to Russian using exact DOM elements"""
        logger.info("Switching caption language to Russian...")
        
        try:
            # Look for the language dropdown trigger
            dropdown_selector = "//span[contains(@class, 'rHGeGc-uusGie-fmcmS')]"
            
            try:
                dropdown_trigger = self.wait.until(EC.element_to_be_clickable((By.XPATH, dropdown_selector)))
                dropdown_trigger.click()
                logger.info("Clicked language dropdown trigger")
                await asyncio.sleep(2)
                
                # Look for Russian option
                russian_selectors = [
                    "//span[@aria-label='Русский']",
                    "//span[contains(text(), 'Русский')]",
                    "//div[contains(text(), 'Русский')]",
                    "//li[contains(text(), 'Русский')]"
                ]
                
                for selector in russian_selectors:
                    try:
                        russian_option = self.driver.find_element(By.XPATH, selector)
                        russian_option.click()
                        logger.info("Selected Russian language option")
                        await asyncio.sleep(2)
                        return
                    except NoSuchElementException:
                        continue
                
                logger.warning("Could not find Russian language option")
                
            except TimeoutException:
                logger.warning("Could not find language dropdown trigger")
        
        except Exception as e:
            logger.error(f"Error switching language to Russian: {str(e)}")
    
    def _run_visual_parsing(self):
        """Run visual parsing loop in background thread"""
        logger.info("Starting visual parsing loop...")
        self.visual_parsing_active = True
        
        last_send_time = time.time()
        last_debug_log = time.time()
        caption_buffer = []
        parsing_attempts = 0
        
        while not self.should_stop:
            try:
                current_time = time.time()
                parsing_attempts += 1
                
                # Parse current captions
                new_captions = self._parse_current_captions()
                
                if new_captions:
                    logger.info(f"🎯 Found {len(new_captions)} new captions!")
                    caption_buffer.extend(new_captions)
                
                # Debug logging every 30 seconds
                if current_time - last_debug_log >= 30:
                    logger.info(f"📊 Parsing status: {parsing_attempts} attempts, {len(caption_buffer)} captions buffered, {len(self.seen_captions)} total seen")
                    last_debug_log = current_time
                    parsing_attempts = 0
                
                # Send captions every 5 minutes or when buffer reaches certain size
                if (current_time - last_send_time >= 300) or len(caption_buffer) >= 10:  # Reduced from 50 to 10 for testing
                    if caption_buffer:
                        logger.info(f"📤 Sending {len(caption_buffer)} captions to backend...")
                        # Use asyncio to run the async method in the thread
                        asyncio.run(self._send_captions_to_backend(caption_buffer))
                        caption_buffer = []
                        last_send_time = current_time
                        self.last_activity = datetime.datetime.now()
                
                time.sleep(2)  # Check every 2 seconds
                
            except Exception as e:
                logger.error(f"Error in visual parsing loop: {str(e)}")
                import traceback
                logger.error(f"Full traceback: {traceback.format_exc()}")
                time.sleep(5)  # Wait before retrying
        
        # Send any remaining captions before stopping
        if caption_buffer:
            logger.info(f"📤 Sending final {len(caption_buffer)} captions before stopping...")
            asyncio.run(self._send_captions_to_backend(caption_buffer))
        
        self.visual_parsing_active = False
        logger.info("Visual parsing loop stopped")
    
    def _send_final_transcript(self):
        """Send final transcript to backend for summary generation"""
        try:
            # Reconstruct full transcript from seen captions
            full_transcript = "\n".join(list(self.seen_captions))
            
            if not full_transcript.strip():
                logger.warning("No transcript data to send for final processing")
                return
            
            url = f"{self.backend_api_url}/api/transcript/final"
            payload = {
                "session_id": self.session_id,
                "full_raw_transcript": full_transcript
            }
            
            response = requests.post(url, json=payload, timeout=30)
            
            if response.status_code == 200:
                response_data = response.json()
                logger.info(f"Final transcript processed successfully. Telegram sent: {response_data.get('telegram_sent', False)}")
            else:
                logger.error(f"Failed to process final transcript: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"Error sending final transcript: {str(e)}")
    
    def _parse_current_captions(self):
        """Parse current captions from the page with improved selectors and debugging"""
        new_captions = []
        
        try:
            # Updated selectors based on Google Meet structure
            caption_selectors = [
                # Google Meet caption containers
                "[jsname='YSxPC']",  # Primary caption selector
                ".a4cQT",             # Alternative caption class
                "[data-caption-text]", # Data attribute selector
                ".captions-text",     # Generic caption class
                ".zs7s8d.jxFHg",      # New Meet UI selector
                "[jscontroller='B1jPud']", # Caption controller
                ".iTTPOb",            # Caption text container
                ".nMcdL",             # Caption block (from original bot)
                "[data-is-caption='true']", # Caption flag
                # More generic selectors
                "*[aria-live='polite']", # Live region for captions
                "*[role='log']",      # ARIA log role for captions
            ]
            
            logger.debug(f"Checking {len(caption_selectors)} caption selectors...")
            
            for i, selector in enumerate(caption_selectors):
                try:
                    caption_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    logger.debug(f"Selector {i+1} '{selector}': found {len(caption_elements)} elements")
                    
                    for element in caption_elements:
                        text = element.text.strip()
                        if text:
                            logger.debug(f"Found text from selector {i+1}: '{text[:50]}...'")
                            
                            if text not in self.seen_captions:
                                # Try to extract speaker info using multiple methods
                                speaker = "Unknown"
                                
                                # Method 1: Look for speaker in parent elements
                                try:
                                    parent = element.find_element(By.XPATH, "./..")
                                    speaker_selectors = [
                                        "[data-sender-name]",
                                        ".speaker-name", 
                                        ".NWpY1d",  # From original bot
                                        "[jsname='r4nke']", # Speaker name container
                                        ".participant-name"
                                    ]
                                    
                                    for speaker_sel in speaker_selectors:
                                        try:
                                            speaker_element = parent.find_element(By.CSS_SELECTOR, speaker_sel)
                                            if speaker_element.text.strip():
                                                speaker = speaker_element.text.strip()
                                                break
                                        except NoSuchElementException:
                                            continue
                                except:
                                    pass
                                
                                # Method 2: Parse speaker from text if format is "Speaker: message"  
                                if ":" in text and speaker == "Unknown":
                                    parts = text.split(":", 1)
                                    if len(parts) == 2 and len(parts[0]) < 50:  # Reasonable speaker name length
                                        potential_speaker = parts[0].strip()
                                        if not any(char.isdigit() for char in potential_speaker):  # Avoid timestamps
                                            speaker = potential_speaker
                                            text = parts[1].strip()
                                
                                # Method 3: Look for usernames in the text content (Google Meet pattern)
                                if speaker == "Unknown":
                                    # Look for patterns like "mukhametzhan-dev" or "username -dev" in text
                                    import re
                                    # Pattern to match usernames (letters, numbers, hyphens, underscores)
                                    username_patterns = [
                                        r'\b([a-zA-Z0-9_-]+(?:\s*-\s*dev))\b',  # Match "username-dev" patterns
                                        r'\b([a-zA-Z][a-zA-Z0-9_-]{2,})\b',     # Match general username patterns
                                    ]
                                    
                                    for pattern in username_patterns:
                                        matches = re.findall(pattern, text, re.IGNORECASE)
                                        if matches:
                                            # Filter out common words that aren't usernames
                                            excluded = ['language', 'русский', 'format_size', 'circle', 'settings', 'также', 'нужно', 'задача', 'следующая']
                                            for match in matches:
                                                if match.lower() not in excluded and len(match) > 2:
                                                    speaker = match
                                                    break
                                            if speaker != "Unknown":
                                                break
                                
                                caption_data = {
                                    "timestamp": datetime.datetime.now().isoformat(),
                                    "speaker": speaker,
                                    "text": text,
                                    "source": "visual"
                                }
                                
                                new_captions.append(caption_data)
                                self.seen_captions.add(text)
                                
                                # Log the caption immediately (as requested)
                                timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                                logger.info(f"📝 [{timestamp}] {speaker}: {text}")
                    
                    if new_captions:
                        logger.debug(f"Found {len(new_captions)} new captions with selector {i+1}")
                        break  # Found captions with this selector
                        
                except Exception as selector_error:
                    logger.debug(f"Selector {i+1} failed: {str(selector_error)}")
                    continue
            
            # If no captions found, do additional debugging
            if not new_captions:
                logger.debug("No captions found, checking page state...")
                try:
                    # Check if we're still in the meeting
                    page_text = self.driver.find_element(By.TAG_NAME, "body").text
                    if "captions" in page_text.lower():
                        logger.debug("Page contains 'captions' text - captions might be available")
                    else:
                        logger.debug("Page does not mention captions")
                    
                    # Look for any elements that might contain live text
                    all_elements = self.driver.find_elements(By.CSS_SELECTOR, "*")
                    text_elements = [el for el in all_elements if el.text and len(el.text.strip()) > 10]
                    logger.debug(f"Found {len(text_elements)} elements with substantial text")
                    
                except Exception as debug_error:
                    logger.debug(f"Debug check failed: {str(debug_error)}")
            
        except Exception as e:
            logger.error(f"Error parsing captions: {str(e)}")
        
        return new_captions
    
    async def _send_captions_to_backend(self, captions):
        """Send parsed captions to backend API using the new chunk endpoint"""
        try:
            # Convert captions list to text chunk format
            text_chunk = ""
            for caption in captions:
                speaker = caption.get('speaker', 'Unknown')
                text = caption.get('text', '')
                timestamp = caption.get('timestamp', '')
                # Format timestamp properly (just time part)
                if 'T' in timestamp:
                    time_part = timestamp.split('T')[1].split('.')[0]  # Extract HH:MM:SS
                else:
                    time_part = timestamp
                text_chunk += f"[{time_part}] {speaker}: {text}\n"
            
            if not text_chunk.strip():
                logger.warning("No caption text to send")
                return
            
            # Use the new chunk processing endpoint
            url = f"{self.backend_api_url}/api/transcript/chunk"
            payload = {
                "session_id": self.session_id,
                "text_chunk": text_chunk.strip(),
                "timestamp": datetime.datetime.now().isoformat()
            }
            
            # Use async HTTP client with proper timeout handling
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload)
            
            if response.status_code == 200:
                response_data = response.json()
                logger.info(f"Successfully sent {len(captions)} captions to backend")
                
                # Check if AI wants to ask a question
                if response_data.get('action') == 'ask_question':
                    question = response_data.get('question_text')
                    logger.info(f"AI Scrum Master wants to ask: {question}")
                    # Here you could implement voice synthesis or chat message
                    # For now, just log it
                    
            else:
                logger.error(f"Failed to send captions to backend: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"Error sending captions to backend: {str(e)}")
    
    # Audio recording methods removed - using captions-only mode
    

    
    async def _monitor_session(self):
        """Monitor the session and keep it alive"""
        logger.info("Starting session monitor...")
        
        while not self.should_stop:
            try:
                # Check if browser is still alive
                if not self.driver or not self._is_browser_alive():
                    logger.error("Browser connection lost")
                    break
                
                # Update last activity
                self.last_activity = datetime.datetime.now()
                
                # Sleep for monitoring interval
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in session monitor: {str(e)}")
                break
        
        logger.info("Session monitor stopped")
    
    def _is_browser_alive(self):
        """Check if browser is still responsive"""
        try:
            self.driver.current_url
            return True
        except WebDriverException:
            return False
    
    # Public methods for API endpoints
    def start_visual_parsing(self):
        """Start visual parsing loop (public method)"""
        if not self.visual_parsing_active and not self.should_stop:
            visual_thread = threading.Thread(target=self._run_visual_parsing, daemon=True)
            visual_thread.start()