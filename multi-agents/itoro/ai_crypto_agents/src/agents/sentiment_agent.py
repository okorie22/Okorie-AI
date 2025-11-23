'''
🌙 Anarcho Capital's Enhanced Sentiment Agent
Built with love by Anarcho Capital 🚀

This agent monitors Twitter sentiment for cryptocurrency tokens using Apify Twitter scraper.
It provides both short-term and long-term sentiment analysis with BULLISH/BEARISH/NEUTRAL classifications.

Features:
- Apify Twitter scraper integration
- Data cleaning and processing
- SQLite database storage with 30-day retention
- AI-powered sentiment analysis with engagement metrics
- Short-term and long-term analysis modes
- Production-ready error handling
- Multiple AI model support (Claude, DeepSeek)

Required:
1. Set APIFY_API_TOKEN in your .env file
2. Configure your desired tokens in config.py
'''

import os
import sys
import time
import pathlib
import sqlite3
import logging
import statistics
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import numpy as np
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import openai
import anthropic
from dotenv import load_dotenv
from termcolor import cprint
from apify_client import ApifyClient

# Import configuration
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import src.config as config

# Cloud database import
try:
    from src.scripts.database.cloud_database import get_cloud_database_manager
    CLOUD_DB_AVAILABLE = True
except ImportError:
    CLOUD_DB_AVAILABLE = False

# Load environment variables
load_dotenv()

# Create data directories if they don't exist
pathlib.Path(config.SENTIMENT_DATA_FOLDER).mkdir(parents=True, exist_ok=True)
pathlib.Path("src/data/logs").mkdir(parents=True, exist_ok=True)
pathlib.Path(os.path.dirname(config.SENTIMENT_SQLITE_DB_FILE)).mkdir(parents=True, exist_ok=True)

# Get API keys
openai.api_key = os.getenv("OPENAI_KEY")
apify_api_token = os.getenv("APIFY_API_TOKEN")

if not apify_api_token:
    cprint("❌ APIFY_API_TOKEN not found in .env file!", "red")
    sys.exit(1)

# Setup logging
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - %(levelname)s - %(message)s',
#     handlers=[
#         logging.FileHandler('src/data/logs/sentiment_agent.log'),
#         logging.StreamHandler()
#     ]
# )  # Removed - main logger configured in src/scripts/shared_services/logger.py
logger = logging.getLogger(__name__)

# Initialize Apify client
apify_client = ApifyClient(apify_api_token)

class SentimentAgent:
    def __init__(self, analysis_mode: str = config.SENTIMENT_DEFAULT_ANALYSIS_MODE):
        """Initialize the Enhanced Sentiment Agent"""
        self.apify_client = apify_client
        self.tokenizer = None
        self.model = None
        self.analysis_mode = analysis_mode
        self.audio_dir = Path("src/audio")
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize AI clients
        self._init_ai_clients()
        
        # Initialize database and files
        self.init_database()
        self.init_sentiment_history_file()
        
        # Load the sentiment model at initialization
        cprint("🤖 Loading sentiment model...", "cyan")
        self.init_sentiment_model()
            
        cprint(f"🌙 Anarcho Capital's Enhanced Sentiment Agent initialized in {analysis_mode} mode!", "green")
        
    def _init_ai_clients(self):
        """Initialize AI clients for enhanced sentiment analysis"""
        try:
            # Set AI parameters from config
            self.ai_model = config.SENTIMENT_MODEL_OVERRIDE
            self.ai_temperature = config.SENTIMENT_AI_TEMPERATURE
            self.ai_max_tokens = config.SENTIMENT_AI_MAX_TOKENS
            
            cprint(f"Using AI Model: {self.ai_model}", "cyan")
            
            # Get API keys
            anthropic_key = os.getenv("ANTHROPIC_KEY")
            deepseek_key = os.getenv("DEEPSEEK_KEY")
            
            # Initialize AI clients based on model selection
            if self.ai_model.lower() in ["deepseek-chat", "deepseek-reasoner"]:
                if not deepseek_key:
                    cprint("❌ DEEPSEEK_KEY not found for DeepSeek model!", "red")
                    raise ValueError("DEEPSEEK_KEY required for DeepSeek models")
                
                self.ai_client = openai.OpenAI(
                    api_key=deepseek_key,
                    base_url=config.SENTIMENT_DEEPSEEK_BASE_URL
                )
                self.ai_provider = "deepseek"
                cprint(f"✅ DeepSeek client initialized with {self.ai_model}!", "green")
                
            elif self.ai_model.startswith("claude"):
                if not anthropic_key:
                    cprint("❌ ANTHROPIC_KEY not found for Claude model!", "red")
                    raise ValueError("ANTHROPIC_KEY required for Claude models")
                
                self.ai_client = anthropic.Anthropic(api_key=anthropic_key)
                self.ai_provider = "anthropic"
                cprint(f"✅ Claude client initialized with {self.ai_model}!", "green")
                
            else:
                cprint(f"⚠️ Unknown AI model: {self.ai_model}, falling back to BERT only", "yellow")
                self.ai_client = None
                self.ai_provider = None
                
        except Exception as e:
            cprint(f"❌ Error initializing AI clients: {str(e)}", "red")
            logger.error(f"AI client initialization error: {str(e)}")
            self.ai_client = None
            self.ai_provider = None
    
    def init_database(self):
        """Initialize SQLite database for sentiment data storage"""
        try:
            conn = sqlite3.connect(config.SENTIMENT_SQLITE_DB_FILE)
            cursor = conn.cursor()
            
            # Create tweets table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tweets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tweet_id TEXT UNIQUE,
                    text TEXT NOT NULL,
                    likes INTEGER DEFAULT 0,
                    replies INTEGER DEFAULT 0,
                    retweets INTEGER DEFAULT 0,
                    quotes INTEGER DEFAULT 0,
                    timestamp TEXT NOT NULL,
                    search_query TEXT NOT NULL,
                    url TEXT,
                    sentiment_score REAL,
                    engagement_score REAL,
                    classification TEXT,
                    ai_enhanced_score REAL,
                    ai_analysis TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create sentiment_history table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sentiment_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    analysis_mode TEXT NOT NULL,
                    sentiment_score REAL NOT NULL,
                    classification TEXT NOT NULL,
                    num_tweets INTEGER NOT NULL,
                    tokens_analyzed TEXT NOT NULL,
                    engagement_avg REAL DEFAULT 0,
                    ai_enhanced_score REAL,
                    ai_model_used TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create indexes for better performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_tweets_timestamp ON tweets(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_tweets_search_query ON tweets(search_query)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sentiment_timestamp ON sentiment_history(timestamp)')
            
            conn.commit()
            conn.close()
            
            cprint("✅ Database initialized successfully", "green")
            
        except Exception as e:
            cprint(f"❌ Error initializing database: {str(e)}", "red")
            logger.error(f"Database initialization error: {str(e)}")
    
    def init_sentiment_history_file(self):
        """Initialize sentiment history CSV file for backward compatibility"""
        if not os.path.exists(config.SENTIMENT_HISTORY_FILE):
            pd.DataFrame(columns=[
                'timestamp', 'analysis_mode', 'sentiment_score', 'classification', 
                'num_tweets', 'tokens_analyzed', 'engagement_avg', 'ai_enhanced_score', 'ai_model_used'
            ]).to_csv(config.SENTIMENT_HISTORY_FILE, index=False)
    
    def init_sentiment_model(self):
        """Initialize the BERT model for sentiment analysis"""
        if self.model is None:
            try:
                self.tokenizer = AutoTokenizer.from_pretrained(config.SENTIMENT_BERT_MODEL)
                self.model = AutoModelForSequenceClassification.from_pretrained(config.SENTIMENT_BERT_MODEL)
                cprint("✨ BERT sentiment model loaded!", "green")
                logger.info("BERT sentiment model loaded successfully")
            except Exception as e:
                cprint(f"❌ Error loading BERT sentiment model: {str(e)}", "red")
                logger.error(f"BERT sentiment model loading error: {str(e)}")
                raise

    def analyze_sentiment(self, texts: List[str]) -> float:
        """Analyze sentiment of a batch of texts using BERT"""
        self.init_sentiment_model()
        
        if not texts:
            return 0.0
        
        try:
            sentiments = []
            batch_size = config.SENTIMENT_BERT_BATCH_SIZE
            
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i + batch_size]
                inputs = self.tokenizer(batch_texts, padding=True, truncation=True, max_length=128, return_tensors="pt")
                
                with torch.no_grad():
                    outputs = self.model(**inputs)
                    predictions = torch.nn.functional.softmax(outputs.logits, dim=-1)
                    sentiments.extend(predictions.tolist())
            
            # Convert to sentiment scores (-1 to 1)
            scores = []
            for sentiment in sentiments:
                # NEG, NEU, POS
                neg, neu, pos = sentiment
                # Convert to -1 to 1 scale
                score = pos - neg  # Will be between -1 and 1
                scores.append(score)
                
            return float(np.mean(scores))
            
        except Exception as e:
            logger.error(f"BERT sentiment analysis error: {str(e)}")
            cprint(f"❌ Error in BERT sentiment analysis: {str(e)}", "red")
            return 0.0
    
    def ai_enhance_sentiment(self, texts: List[str], base_sentiment: float, engagement_data: List[Dict]) -> Tuple[float, str]:
        """Use AI to enhance sentiment analysis with context and nuance"""
        if not self.ai_client or not texts:
            return base_sentiment, "No AI enhancement available"
        
        try:
            # Sample tweets for AI analysis (max 10 for efficiency)
            sample_texts = texts[:10] if len(texts) > 10 else texts
            sample_engagement = engagement_data[:10] if len(engagement_data) > 10 else engagement_data
            
            # Prepare context for AI
            context = f"""
            Analyze the sentiment of these cryptocurrency-related tweets and provide an enhanced sentiment score.
            
            Base BERT sentiment score: {base_sentiment:.3f} (scale: -1 to 1)
            
            Sample tweets with engagement:
            """
            
            for i, (text, engagement) in enumerate(zip(sample_texts, sample_engagement)):
                context += f"\n{i+1}. \"{text}\"\n   Likes: {engagement.get('likes', 0)}, Retweets: {engagement.get('retweets', 0)}, Replies: {engagement.get('replies', 0)}\n"
            
            context += """
            
            Consider:
            1. Crypto-specific sentiment nuances (HODL, moon, diamond hands, etc.)
            2. Sarcasm and irony detection
            3. Market context and timing
            4. Engagement patterns (high engagement on negative news might indicate concern)
            5. Influence of high-engagement tweets
            
            Provide:
            1. Enhanced sentiment score (-1 to 1 scale)
            2. Brief analysis explaining your reasoning
            
            Format your response as:
            SCORE: [your enhanced score]
            ANALYSIS: [your reasoning]
            """
            
            if self.ai_provider == "deepseek":
                response = self.ai_client.chat.completions.create(
                    model=self.ai_model,
                    messages=[{"role": "user", "content": context}],
                    temperature=self.ai_temperature,
                    max_tokens=self.ai_max_tokens
                )
                ai_response = response.choices[0].message.content
                
            elif self.ai_provider == "anthropic":
                response = self.ai_client.messages.create(
                    model=self.ai_model,
                    max_tokens=self.ai_max_tokens,
                    temperature=self.ai_temperature,
                    messages=[{"role": "user", "content": context}]
                )
                ai_response = response.content[0].text
            
            # Parse AI response
            lines = ai_response.strip().split('\n')
            enhanced_score = base_sentiment  # Default fallback
            analysis = "AI analysis failed to parse"
            
            for line in lines:
                if line.startswith('SCORE:'):
                    try:
                        enhanced_score = float(line.split('SCORE:')[1].strip())
                        enhanced_score = max(-1.0, min(1.0, enhanced_score))  # Clamp to valid range
                    except (ValueError, IndexError):
                        pass
                elif line.startswith('ANALYSIS:'):
                    analysis = line.split('ANALYSIS:')[1].strip()
            
            return enhanced_score, analysis
            
        except Exception as e:
            logger.error("AI sentiment enhancement error: %s", str(e))
            cprint(f"❌ Error in AI sentiment enhancement: {str(e)}", "red")
            return base_sentiment, f"AI enhancement failed: {str(e)}"
    
    def calculate_engagement_score(self, tweet_data: Dict) -> float:
        """Calculate engagement score based on likes, retweets, replies, and quotes"""
        try:
            likes = int(tweet_data.get('likes', 0))
            retweets = int(tweet_data.get('retweets', 0))
            replies = int(tweet_data.get('replies', 0))
            quotes = int(tweet_data.get('quotes', 0))
            
            # Calculate weighted engagement score
            engagement_score = (
                likes * config.SENTIMENT_LIKES_WEIGHT +
                retweets * config.SENTIMENT_RETWEETS_WEIGHT +
                replies * config.SENTIMENT_REPLIES_WEIGHT +
                quotes * config.SENTIMENT_QUOTES_WEIGHT
            )
            
            # Normalize to 0-1 scale using log transformation to handle outliers
            normalized_score = min(1.0, np.log1p(engagement_score) / 10.0)
            
            return float(normalized_score)
            
        except Exception as e:
            logger.error(f"Engagement score calculation error: {str(e)}")
            return 0.0
    
    def classify_sentiment(self, sentiment_score: float) -> str:
        """Classify sentiment score into BULLISH, BEARISH, or NEUTRAL"""
        if sentiment_score > config.SENTIMENT_BULLISH_THRESHOLD:
            return "BULLISH"
        elif sentiment_score < config.SENTIMENT_BEARISH_THRESHOLD:
            return "BEARISH"
        else:
            return "NEUTRAL"

    def _announce(self, message: str, is_important: bool = False):
        """Announce a message using text-to-speech"""
        try:
            print(f"\n🗣️ {message}")
            logger.info(f"Announcement: {message}")
            
            # Check if voice is enabled and conditions are met
            if not config.SENTIMENT_VOICE_ENABLED or not is_important or not openai.api_key:
                return
                
            # Generate unique filename based on timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            speech_file = self.audio_dir / f"sentiment_audio_{timestamp}.mp3"
            
            # Generate speech using OpenAI
            response = openai.audio.speech.create(
                model=config.SENTIMENT_VOICE_MODEL,
                voice=config.SENTIMENT_VOICE_NAME,
                speed=config.SENTIMENT_VOICE_SPEED,
                input=message
            )
            
            # Save and play the audio
            with open(speech_file, 'wb') as f:
                for chunk in response.iter_bytes():
                    f.write(chunk)
            
            # Play the audio
            if os.name == 'posix':  # macOS/Linux
                os.system(f"afplay {speech_file}")
            else:  # Windows
                os.system(f"start {speech_file}")
                time.sleep(5)
            
            # Clean up
            try:
                speech_file.unlink()
            except Exception as e:
                print(f"⚠️ Couldn't delete audio file: {e}")
                
        except Exception as e:
            # Only show TTS errors if voice is enabled
            if config.SENTIMENT_VOICE_ENABLED:
                print(f"❌ Error in text-to-speech: {str(e)}")
                logger.error(f"Text-to-speech error: {str(e)}")

    def save_sentiment_score(self, sentiment_score: float, classification: str, num_tweets: int, 
                           tokens_analyzed: List[str], engagement_avg: float = 0.0, 
                           ai_enhanced_score: float = None, ai_model_used: str = None):
        """Save sentiment score to local storage first, then sync to cloud database"""
        try:
            timestamp = datetime.now().isoformat()
            tokens_str = ','.join(tokens_analyzed)
            
            # PRIMARY: Save to local storage first
            self._save_sentiment_to_local_storage(timestamp, sentiment_score, classification, 
                                               num_tweets, tokens_str, engagement_avg, 
                                               ai_enhanced_score, ai_model_used)
            
            # SECONDARY: Try to sync to cloud database
            if CLOUD_DB_AVAILABLE:
                try:
                    db_manager = get_cloud_database_manager()
                    if db_manager is not None:
                        # Save to cloud database
                        query = '''
                            INSERT INTO sentiment_data (
                                sentiment_type, overall_sentiment, sentiment_score, confidence,
                                num_tokens_analyzed, num_tweets, engagement_avg, ai_enhanced_score,
                                ai_model_used, tokens_analyzed, metadata
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        '''
                        
                        params = (
                            'twitter',  # sentiment_type
                            classification,  # overall_sentiment
                            sentiment_score,  # sentiment_score
                            50.0,  # confidence (default)
                            len(tokens_analyzed),  # num_tokens_analyzed
                            num_tweets,  # num_tweets
                            engagement_avg,  # engagement_avg
                            ai_enhanced_score,  # ai_enhanced_score
                            ai_model_used,  # ai_model_used
                            tokens_str,  # tokens_analyzed
                            json.dumps({'analysis_mode': self.analysis_mode})  # metadata
                        )
                        
                        db_manager.execute_query(query, params, fetch=False)
                        logger.info(f"✅ Sentiment data synced to cloud database: {sentiment_score} ({classification})")
                        
                except Exception as cloud_error:
                    logger.warning(f"⚠️ Cloud database sync failed (local data saved): {cloud_error}")
            
        except Exception as e:
            cprint(f"❌ Error saving sentiment history: {str(e)}", "red")
            logger.error(f"Save sentiment error: {str(e)}")
    
    def _save_sentiment_to_local_storage(self, timestamp: str, sentiment_score: float, classification: str, 
                                       num_tweets: int, tokens_str: str, engagement_avg: float, 
                                       ai_enhanced_score: float = None, ai_model_used: str = None):
        """Fallback method to save sentiment to local storage"""
        try:
            # Save to SQLite database
            conn = sqlite3.connect(config.SENTIMENT_SQLITE_DB_FILE)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO sentiment_history 
                (timestamp, analysis_mode, sentiment_score, classification, num_tweets, tokens_analyzed, 
                 engagement_avg, ai_enhanced_score, ai_model_used)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (timestamp, self.analysis_mode, sentiment_score, classification, num_tweets, 
                  tokens_str, engagement_avg, ai_enhanced_score, ai_model_used))
            
            # Clean up old data (keep only last 30 days)
            cutoff_time = (datetime.now() - timedelta(days=config.SENTIMENT_DATA_RETENTION_DAYS)).isoformat()
            cursor.execute('DELETE FROM sentiment_history WHERE timestamp < ?', (cutoff_time,))
            
            conn.commit()
            conn.close()
            
            # Save to CSV for backward compatibility
            new_data = pd.DataFrame([{
                'timestamp': timestamp,
                'analysis_mode': self.analysis_mode,
                'sentiment_score': sentiment_score,
                'classification': classification,
                'num_tweets': num_tweets,
                'tokens_analyzed': tokens_str,
                'engagement_avg': engagement_avg,
                'ai_enhanced_score': ai_enhanced_score,
                'ai_model_used': ai_model_used
            }])
            
            # Load existing CSV data
            if os.path.exists(config.SENTIMENT_HISTORY_FILE):
                history_df = pd.read_csv(config.SENTIMENT_HISTORY_FILE)
                # Convert timestamps to datetime for comparison
                history_df['timestamp'] = pd.to_datetime(history_df['timestamp'], errors='coerce')
                # Keep only last 30 days of data
                cutoff_time = datetime.now() - timedelta(days=config.SENTIMENT_DATA_RETENTION_DAYS)
                history_df = history_df[history_df['timestamp'] > cutoff_time]
                # Convert back to ISO format for consistent storage
                history_df['timestamp'] = history_df['timestamp'].dt.strftime('%Y-%m-%dT%H:%M:%S.%f')
                # Append new data
                history_df = pd.concat([history_df, new_data], ignore_index=True)
            else:
                history_df = new_data
                
            history_df.to_csv(config.SENTIMENT_HISTORY_FILE, index=False)
            logger.info(f"📁 Sentiment data saved to local storage: {sentiment_score} ({classification})")
            
        except Exception as e:
            cprint(f"❌ Error saving sentiment to local storage: {str(e)}", "red")
            logger.error(f"Local storage save error: {str(e)}")

    def get_sentiment_change(self) -> Tuple[Optional[float], Optional[float], Optional[str], Optional[str]]:
        """Calculate sentiment change from last run"""
        try:
            conn = sqlite3.connect(config.SENTIMENT_SQLITE_DB_FILE)
            cursor = conn.cursor()
            
            # Get last two sentiment records for the current analysis mode
            cursor.execute('''
                SELECT sentiment_score, classification, timestamp 
                FROM sentiment_history 
                WHERE analysis_mode = ?
                ORDER BY timestamp DESC 
                LIMIT 2
            ''', (self.analysis_mode,))
            
            results = cursor.fetchall()
            conn.close()
            
            if len(results) < 2:
                return None, None, None, None
                
            current_score, current_class, current_time = results[0]
            previous_score, previous_class, previous_time = results[1]
            
            # Calculate time difference in minutes
            current_dt = datetime.fromisoformat(current_time)
            previous_dt = datetime.fromisoformat(previous_time)
            time_diff = (current_dt - previous_dt).total_seconds() / 60
            
            # Calculate percentage change relative to the scale (-1 to 1)
            # Convert to 0-100 scale for easier understanding
            current_percent = (current_score + 1) * 50
            previous_percent = (previous_score + 1) * 50
            percent_change = current_percent - previous_percent
            
            return percent_change, time_diff, previous_class, current_class
            
        except Exception as e:
            cprint(f"❌ Error calculating sentiment change: {str(e)}", "red")
            logger.error(f"Sentiment change calculation error: {str(e)}")
            return None, None, None, None

    def analyze_and_announce_sentiment(self, tweets_data: List[Dict], tokens_analyzed: List[str]):
        """Analyze sentiment of tweets and announce results"""
        if not tweets_data:
            cprint("⚠️ No tweets to analyze", "yellow")
            return
            
        try:
            # Extract text from tweets
            texts = [tweet['text'] for tweet in tweets_data if tweet.get('text')]
            
            if not texts:
                cprint("⚠️ No valid tweet texts found", "yellow")
                return
            
            # Get base BERT sentiment score
            base_sentiment_score = self.analyze_sentiment(texts)
            
            # Calculate engagement scores and weighted sentiment
            engagement_scores = []
            weighted_sentiments = []
            
            for i, tweet in enumerate(tweets_data):
                if i < len(texts):
                    engagement_score = self.calculate_engagement_score(tweet)
                    engagement_scores.append(engagement_score)
                    
                    # Weight sentiment by engagement (higher engagement = more influence)
                    individual_sentiment = self.analyze_sentiment([texts[i]])
                    weighted_sentiment = individual_sentiment * (1 + engagement_score)
                    weighted_sentiments.append(weighted_sentiment)
            
            # Calculate engagement-weighted sentiment score
            if weighted_sentiments:
                engagement_weighted_score = np.mean(weighted_sentiments)
                # Blend base sentiment with engagement-weighted sentiment
                bert_final_score = (base_sentiment_score * 0.6) + (engagement_weighted_score * 0.4)
                # Ensure it stays within -1 to 1 range
                bert_final_score = max(-1.0, min(1.0, bert_final_score))
            else:
                bert_final_score = base_sentiment_score
            
            # AI Enhancement (if available)
            ai_enhanced_score = None
            ai_analysis = None
            ai_model_used = None
            
            if self.ai_client:
                cprint("🤖 Enhancing sentiment with AI analysis...", "cyan")
                ai_enhanced_score, ai_analysis = self.ai_enhance_sentiment(texts, bert_final_score, tweets_data)
                ai_model_used = self.ai_model
                cprint(f"✨ AI Enhancement: {bert_final_score:.3f} → {ai_enhanced_score:.3f}", "green")
            
            # Use AI-enhanced score if available, otherwise use BERT score
            final_sentiment_score = ai_enhanced_score if ai_enhanced_score is not None else bert_final_score
            
            # Calculate average engagement score
            avg_engagement = np.mean(engagement_scores) if engagement_scores else 0.0
            
            # Classify sentiment
            classification = self.classify_sentiment(final_sentiment_score)
            
            # Save score to history
            self.save_sentiment_score(final_sentiment_score, classification, len(texts), tokens_analyzed, 
                                    avg_engagement, ai_enhanced_score, ai_model_used)
            
            # Get change since last run
            percent_change, time_diff, prev_class, curr_class = self.get_sentiment_change()
            
            # Convert score to human readable format
            if final_sentiment_score > 0.3:
                sentiment_desc = "very positive"
            elif final_sentiment_score > 0:
                sentiment_desc = "slightly positive"
            elif final_sentiment_score > -0.3:
                sentiment_desc = "slightly negative"
            else:
                sentiment_desc = "very negative"
                
            # Format the score as a percentage for easier understanding
            score_percent = (final_sentiment_score + 1) * 50  # Convert -1 to 1 into 0 to 100
                
            # Prepare announcement
            tokens_str = ', '.join(tokens_analyzed)
            message = f"Anarcho Capital's {self.analysis_mode.replace('_', ' ').title()} Sentiment Analysis: "
            message += f"After analyzing {len(texts)} tweets about {tokens_str}, "
            message += f"the crypto sentiment is {classification} ({sentiment_desc}) "
            message += f"with a score of {score_percent:.1f} out of 100"
            
            if ai_enhanced_score is not None:
                message += f" (AI-enhanced using {ai_model_used})"
            
            if avg_engagement > 0:
                message += f" (avg engagement: {avg_engagement:.2f})"
            
            # Add change information if available
            if percent_change is not None and time_diff is not None:
                direction = "up" if percent_change > 0 else "down"
                message += f". Sentiment has moved {direction} {abs(percent_change):.1f} points "
                message += f"over the past {int(time_diff)} minutes"
                
                # Add classification change if it occurred
                if prev_class and curr_class and prev_class != curr_class:
                    message += f" (changed from {prev_class} to {curr_class})"
                
                # Add percentage interpretation
                if abs(percent_change) > 15:
                    message += f" - this is a major {abs(percent_change):.1f}% change!"
                elif abs(percent_change) > 10:
                    message += f" - this is a significant {abs(percent_change):.1f}% change!"
                elif abs(percent_change) > 5:
                    message += f" - a moderate {abs(percent_change):.1f}% shift"
                else:
                    message += f" - a small {abs(percent_change):.1f}% change"
            
            message += "."
            
            # Announce with voice if sentiment is significant, classification changed, or if there's a big change
            classification_changed = prev_class and curr_class and prev_class != curr_class
            is_important = (
                abs(final_sentiment_score) > config.SENTIMENT_ANNOUNCE_THRESHOLD or 
                (percent_change is not None and abs(percent_change) > 10) or
                classification_changed
            )
            
            self._announce(message, is_important)
            
            # Print detailed info for debugging
            cprint("📊 Detailed Analysis:", "cyan")
            cprint(f"   Base BERT sentiment: {base_sentiment_score:.3f}", "cyan")
            cprint(f"   Engagement-weighted: {bert_final_score:.3f}", "cyan")
            if ai_enhanced_score is not None:
                cprint(f"   AI-enhanced score: {ai_enhanced_score:.3f}", "cyan")
                cprint(f"   AI model used: {ai_model_used}", "cyan")
                if ai_analysis:
                    cprint(f"   AI analysis: {ai_analysis[:100]}...", "cyan")
            cprint(f"   Final classification: {classification}", "cyan")
            cprint(f"   Average engagement: {avg_engagement:.3f}", "cyan")
            
        except Exception as e:
            cprint(f"❌ Error in sentiment analysis: {str(e)}", "red")
            logger.error(f"Sentiment analysis error: {str(e)}")

    def clean_tweet_data(self, raw_tweets: List[Dict]) -> List[Dict]:
        """Clean tweet data by removing Avatar, ID, and Images fields"""
        cleaned_tweets = []
        
        for tweet in raw_tweets:
            try:
                # Remove unwanted fields and keep only necessary data
                cleaned_tweet = {
                    'text': tweet.get('text', ''),
                    'likes': int(tweet.get('likes', 0)),
                    'replies': int(tweet.get('replies', 0)),
                    'retweets': int(tweet.get('retweets', 0)),
                    'quotes': int(tweet.get('quotes', 0)),
                    'timestamp': tweet.get('timestamp', ''),
                    'search_query': tweet.get('searchQuery', ''),
                    'url': tweet.get('url', '')
                }
                
                # Only include tweets with valid text
                if cleaned_tweet['text'] and len(cleaned_tweet['text'].strip()) > 0:
                    # Filter out tweets with ignore words
                    if not any(word.lower() in cleaned_tweet['text'].lower() for word in config.SENTIMENT_IGNORE_LIST):
                        cleaned_tweets.append(cleaned_tweet)
                        
            except Exception as e:
                logger.error(f"Error cleaning tweet data: {str(e)}")
                continue
        
        cprint(f"✅ Cleaned {len(cleaned_tweets)} tweets from {len(raw_tweets)} raw tweets", "green")
        return cleaned_tweets

    def scrape_tweets_with_apify(self, search_queries: List[str]) -> List[Dict]:
        """Scrape tweets using Apify Twitter scraper with robust error handling"""
        import threading
        import sys
        
        all_tweets = []
        
        for attempt in range(config.SENTIMENT_MAX_RETRIES):
            try:
                cprint(f'🕒 Time is {datetime.now()} - Anarcho Capital scraping tweets with Apify! 🌟', "cyan")
                
                # Configure Apify actor parameters
                actor_input = {
                    "excludeImages": True,  # We don't want images
                    "excludeLinks": True,
                    "excludeMedia": True,
                    "excludeNativeRetweets": False,
                    "excludeNativeVideo": True,
                    "excludeNews": False,
                    "excludeProVideo": True,
                    "excludeQuote": False,
                    "excludeReplies": False,
                    "excludeSafe": False,
                    "excludeVerified": False,
                    "excludeVideos": True,
                    "images": False,
                    "includeUserInfo": False,  # We don't need user info to avoid ID fields
                    "language": "en",
                    "links": False,
                    "media": False,
                    "minLikes": 1,
                    "minReplies": 0,
                    "nativeRetweets": False,
                    "nativeVideo": False,
                    "news": False,
                    "proVideo": False,
                    "proxyConfig": {
                        "useApifyProxy": True,
                        "apifyProxyGroups": ["RESIDENTIAL"]
                    },
                    "quote": False,
                    "replies": True,
                    "safe": False,
                    "searchQueries": search_queries,
                    "tweetsDesired": config.SENTIMENT_TWEETS_PER_RUN,
                    "verified": False,
                    "videos": False
                }
                
                # Start the actor
                cprint(f"🚀 Starting Apify actor for queries: {', '.join(search_queries)}", "cyan")
                
                # Progress bar setup
                progress_chars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
                progress_index = 0
                stop_progress = False
                
                def show_progress():
                    nonlocal progress_index, stop_progress
                    while not stop_progress:
                        sys.stdout.write(f'\r🔄 Scraping tweets {progress_chars[progress_index]} Please wait...')
                        sys.stdout.flush()
                        progress_index = (progress_index + 1) % len(progress_chars)
                        time.sleep(0.1)
                    sys.stdout.write('\r' + ' ' * 50 + '\r')  # Clear the line
                    sys.stdout.flush()
                
                # Start progress animation in background
                progress_thread = threading.Thread(target=show_progress, daemon=True)
                progress_thread.start()
                
                # Suppress Apify client logging temporarily
                import logging
                apify_logger = logging.getLogger('apify_client')
                original_level = apify_logger.level
                apify_logger.setLevel(logging.CRITICAL)
                
                try:
                    # Start the actor and wait for completion
                    run = self.apify_client.actor(config.SENTIMENT_APIFY_ACTOR_ID).call(run_input=actor_input)
                    
                    # Get the results
                    results = list(self.apify_client.dataset(run["defaultDatasetId"]).iterate_items())
                    
                finally:
                    # Stop progress bar and restore logging
                    stop_progress = True
                    progress_thread.join(timeout=0.5)
                    apify_logger.setLevel(original_level)
                
                if results:
                    cprint(f"✅ Successfully scraped {len(results)} tweets from Apify", "green")
                    all_tweets.extend(results)
                    logger.info(f"Scraped {len(results)} tweets successfully")
                    break
                else:
                    cprint("⚠️ No results from Apify scraper", "yellow")
                    if attempt < config.SENTIMENT_MAX_RETRIES - 1:
                        cprint(f"🔄 Retrying in {config.SENTIMENT_RETRY_DELAY} seconds... (attempt {attempt + 1}/{config.SENTIMENT_MAX_RETRIES})", "yellow")
                        time.sleep(config.SENTIMENT_RETRY_DELAY)
                        continue
                        
            except Exception as e:
                # Ensure progress bar is stopped on error
                stop_progress = True
                error_msg = f"Apify scraping error (attempt {attempt + 1}/{config.SENTIMENT_MAX_RETRIES}): {str(e)}"
                cprint(f"❌ {error_msg}", "red")
                logger.error(error_msg)
                
                if attempt < config.SENTIMENT_MAX_RETRIES - 1:
                    cprint(f"🔄 Retrying in {config.SENTIMENT_RETRY_DELAY} seconds...", "yellow")
                    time.sleep(config.SENTIMENT_RETRY_DELAY)
                else:
                    cprint("❌ Max retries reached, giving up", "red")
                    break
        
        return all_tweets

    def save_tweets(self, tweets_data: List[Dict], tokens: List[str]):
        """Save tweets to both SQLite database and CSV files with deduplication"""
        if not tweets_data:
            cprint("ℹ️ No tweets to save", "yellow")
            return
        
        try:
            # Save to SQLite database
            conn = sqlite3.connect(config.SENTIMENT_SQLITE_DB_FILE)
            cursor = conn.cursor()
            
            saved_count = 0
            duplicate_count = 0
            
            for tweet in tweets_data:
                try:
                    # Generate a unique tweet_id from URL if available, otherwise use text hash
                    tweet_url = tweet.get('url', '')
                    if tweet_url:
                        tweet_id = tweet_url.split('/')[-1] if '/' in tweet_url else str(hash(tweet.get('text', '')))
                    else:
                        tweet_id = str(hash(tweet.get('text', '')))
                    
                    # Calculate sentiment and engagement scores for this tweet
                    sentiment_score = self.analyze_sentiment([tweet['text']]) if tweet.get('text') else 0.0
                    engagement_score = self.calculate_engagement_score(tweet)
                    classification = self.classify_sentiment(sentiment_score)
                    
                    # Try to insert the tweet
                    cursor.execute('''
                        INSERT OR IGNORE INTO tweets 
                        (tweet_id, text, likes, replies, retweets, quotes, timestamp, search_query, url, 
                         sentiment_score, engagement_score, classification)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        tweet_id,
                        tweet['text'],
                        tweet['likes'],
                        tweet['replies'],
                        tweet['retweets'],
                        tweet['quotes'],
                        tweet['timestamp'],
                        tweet['search_query'],
                        tweet['url'],
                        sentiment_score,
                        engagement_score,
                        classification
                    ))
                    
                    if cursor.rowcount > 0:
                        saved_count += 1
                    else:
                        duplicate_count += 1
                        
                except Exception as e:
                    logger.error(f"Error saving individual tweet: {str(e)}")
                    continue
            
            # Clean up old tweets (keep only last 30 days)
            cutoff_time = (datetime.now() - timedelta(days=config.SENTIMENT_DATA_RETENTION_DAYS)).isoformat()
            cursor.execute('DELETE FROM tweets WHERE timestamp < ?', (cutoff_time,))
            
            conn.commit()
            conn.close()
            
            # Also save to CSV files for each token (backward compatibility)
            for token in tokens:
                self.save_tweets_to_csv(tweets_data, token)
            
            cprint(f"📝 Saved {saved_count} new tweets to database ({duplicate_count} duplicates skipped)", "green")
            logger.info(f"Saved {saved_count} tweets, skipped {duplicate_count} duplicates")
            
        except Exception as e:
            cprint(f"❌ Error saving tweets: {str(e)}", "red")
            logger.error(f"Tweet saving error: {str(e)}")
    
    def save_tweets_to_csv(self, tweets_data: List[Dict], token: str):
        """Save tweets to CSV file for a specific token"""
        filename = f"{config.SENTIMENT_DATA_FOLDER}/{token.lower()}_tweets.csv"
        
        # Filter tweets for this specific token
        token_tweets = [tweet for tweet in tweets_data 
                       if token.lower() in tweet.get('search_query', '').lower() or 
                          token.lower() in tweet.get('text', '').lower()]
        
        if not token_tweets:
            return
        
        # Prepare new tweets data
        new_tweets_data = []
        for tweet in token_tweets:
            try:
                tweet_data = {
                    "collection_time": datetime.now().isoformat(),
                    "tweet_id": tweet.get('url', '').split('/')[-1] if tweet.get('url') else str(hash(tweet.get('text', ''))),
                    "text": tweet['text'],
                    "likes": tweet['likes'],
                    "replies": tweet['replies'],
                    "retweets": tweet['retweets'],
                    "quotes": tweet['quotes'],
                    "timestamp": tweet['timestamp'],
                    "search_query": tweet['search_query'],
                    "url": tweet['url'],
                    "sentiment_score": self.analyze_sentiment([tweet['text']]) if tweet.get('text') else 0.0,
                    "engagement_score": self.calculate_engagement_score(tweet)
                }
                new_tweets_data.append(tweet_data)
            except Exception as e:
                logger.error(f"Error processing tweet for CSV: {str(e)}")
                continue
        
        if not new_tweets_data:
            return
            
        # Convert to DataFrame
        new_df = pd.DataFrame(new_tweets_data)
        
        try:
            # Load existing data if file exists
            if os.path.exists(filename):
                existing_df = pd.read_csv(filename)
                # Remove duplicates based on tweet_id
                new_df = new_df[~new_df['tweet_id'].isin(existing_df['tweet_id'])]
                # Append new data
                if not new_df.empty:
                    pd.concat([existing_df, new_df], ignore_index=True).to_csv(filename, index=False)
            else:
                # Save new file
                new_df.to_csv(filename, index=False)
            
            if not new_df.empty:
                cprint(f"📝 Added {len(new_df)} new tweets to {token.lower()}_tweets.csv", "green")
                
        except Exception as e:
            cprint(f"❌ Error saving CSV for {token}: {str(e)}", "red")
            logger.error(f"CSV saving error for {token}: {str(e)}")

    def get_historical_data_for_long_term_analysis(self) -> List[Dict]:
        """Get historical tweet data for long-term analysis"""
        try:
            conn = sqlite3.connect(config.SENTIMENT_SQLITE_DB_FILE)
            cursor = conn.cursor()
            
            # Get tweets from the last 30 days
            cutoff_time = (datetime.now() - timedelta(days=config.SENTIMENT_DATA_RETENTION_DAYS)).isoformat()
            cursor.execute('''
                SELECT text, likes, replies, retweets, quotes, timestamp, search_query, url,
                       sentiment_score, engagement_score, classification
                FROM tweets 
                WHERE timestamp > ?
                ORDER BY timestamp DESC
            ''', (cutoff_time,))
            
            rows = cursor.fetchall()
            conn.close()
            
            # Convert to list of dictionaries
            historical_tweets = []
            for row in rows:
                tweet_data = {
                    'text': row[0],
                    'likes': row[1],
                    'replies': row[2],
                    'retweets': row[3],
                    'quotes': row[4],
                    'timestamp': row[5],
                    'search_query': row[6],
                    'url': row[7],
                    'sentiment_score': row[8],
                    'engagement_score': row[9],
                    'classification': row[10]
                }
                historical_tweets.append(tweet_data)
            
            cprint(f"📊 Retrieved {len(historical_tweets)} historical tweets for long-term analysis", "cyan")
            return historical_tweets
            
        except Exception as e:
            cprint(f"❌ Error retrieving historical data: {str(e)}", "red")
            logger.error(f"Historical data retrieval error: {str(e)}")
            return []
    
    def run_analysis(self):
        """Main function to run sentiment analysis based on current mode"""
        try:
            cprint(f"🤖 Anarcho Capital's {self.analysis_mode.replace('_', ' ').title()} Sentiment Analysis running...", "cyan")
            
            if self.analysis_mode == config.SENTIMENT_ANALYSIS_MODE_SHORT_TERM:
                # Short-term: Scrape fresh tweets and analyze immediately
                cprint("📡 Running short-term analysis with fresh data...", "cyan")
                
                # Scrape fresh tweets using Apify
                raw_tweets = self.scrape_tweets_with_apify(config.SENTIMENT_TOKENS_TO_TRACK)
                
                if raw_tweets:
                    # Clean the scraped data
                    cleaned_tweets = self.clean_tweet_data(raw_tweets)
                    
                    if cleaned_tweets:
                        # Save tweets to database and CSV
                        self.save_tweets(cleaned_tweets, config.SENTIMENT_TOKENS_TO_TRACK)
                        
                        # Analyze and announce sentiment
                        self.analyze_and_announce_sentiment(cleaned_tweets, config.SENTIMENT_TOKENS_TO_TRACK)
                    else:
                        cprint("⚠️ No valid tweets after cleaning", "yellow")
                else:
                    cprint("⚠️ No tweets scraped from Apify", "yellow")
                    
            elif self.analysis_mode == config.SENTIMENT_ANALYSIS_MODE_LONG_TERM:
                # Long-term: Analyze historical data from the last 30 days
                cprint("📈 Running long-term analysis with 30-day historical data...", "cyan")
                
                historical_tweets = self.get_historical_data_for_long_term_analysis()
                
                if historical_tweets:
                    # Analyze and announce sentiment for historical data
                    self.analyze_and_announce_sentiment(historical_tweets, config.SENTIMENT_TOKENS_TO_TRACK)
                else:
                    cprint("⚠️ No historical data available for long-term analysis", "yellow")
            
            cprint(f"🌙 Anarcho Capital's {self.analysis_mode.replace('_', ' ').title()} Sentiment Analysis complete! 🚀", "green")
            
        except Exception as e:
            cprint(f"❌ Error in sentiment analysis: {str(e)}", "red")
            logger.error(f"Analysis error: {str(e)}")
    
    def set_analysis_mode(self, mode: str):
        """Switch between short-term and long-term analysis modes"""
        if mode in [config.SENTIMENT_ANALYSIS_MODE_SHORT_TERM, config.SENTIMENT_ANALYSIS_MODE_LONG_TERM]:
            self.analysis_mode = mode
            cprint(f"🔄 Switched to {mode.replace('_', ' ')} analysis mode", "green")
            logger.info(f"Analysis mode changed to: {mode}")
        else:
            cprint(f"❌ Invalid analysis mode: {mode}", "red")
            cprint(f"Valid modes: {config.SENTIMENT_ANALYSIS_MODE_SHORT_TERM}, {config.SENTIMENT_ANALYSIS_MODE_LONG_TERM}", "yellow")

    def run(self):
        """Main function to run sentiment analysis"""
        self.run_analysis()
    
    def get_sentiment_summary(self) -> Dict:
        """Get a summary of recent sentiment analysis results"""
        try:
            conn = sqlite3.connect(config.SENTIMENT_SQLITE_DB_FILE)
            cursor = conn.cursor()
            
            # Get recent sentiment history
            cursor.execute('''
                SELECT sentiment_score, classification, num_tweets, timestamp, analysis_mode, 
                       engagement_avg, ai_enhanced_score, ai_model_used
                FROM sentiment_history 
                ORDER BY timestamp DESC 
                LIMIT 10
            ''', )
            
            results = cursor.fetchall()
            conn.close()
            
            if not results:
                return {"message": "No sentiment data available"}
            
            # Calculate summary statistics
            recent_scores = [float(row[0]) for row in results]
            recent_classifications = [row[1] for row in results]
            
            summary = {
                "latest_sentiment_score": recent_scores[0],
                "latest_classification": recent_classifications[0],
                "average_sentiment_score": statistics.mean(recent_scores),
                "sentiment_trend": "IMPROVING" if len(recent_scores) > 1 and recent_scores[0] > recent_scores[1] else "DECLINING" if len(recent_scores) > 1 and recent_scores[0] < recent_scores[1] else "STABLE",
                "classification_distribution": dict(pd.Series(recent_classifications).value_counts()),
                "total_analyses": len(results),
                "analysis_mode": results[0][4] if results else self.analysis_mode,
                "latest_timestamp": results[0][3] if results else None,
                "ai_enhanced": results[0][6] is not None if results else False,
                "ai_model_used": results[0][7] if results and results[0][7] else "None"
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Error getting sentiment summary: {str(e)}")
            return {"error": str(e)}

def main():
    """Main function with command line argument support"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Anarcho Capital's Enhanced Sentiment Agent")
    parser.add_argument('--mode', choices=[config.SENTIMENT_ANALYSIS_MODE_SHORT_TERM, config.SENTIMENT_ANALYSIS_MODE_LONG_TERM], 
                       default=config.SENTIMENT_DEFAULT_ANALYSIS_MODE, help='Analysis mode')
    parser.add_argument('--single-run', action='store_true', help='Run once and exit')
    parser.add_argument('--summary', action='store_true', help='Show sentiment summary and exit')
    
    args = parser.parse_args()
    
    try:
        agent = SentimentAgent(analysis_mode=args.mode)
        
        if args.summary:
            summary = agent.get_sentiment_summary()
            cprint("\n📊 Sentiment Analysis Summary:", "cyan")
            for key, value in summary.items():
                cprint(f"   {key}: {value}", "white")
            return
        
        if args.single_run:
            cprint(f"\n🌙 Anarcho Capital's Sentiment Agent running once in {args.mode.replace('_', ' ')} mode...", "cyan")
            agent.run()
            cprint("\n✅ Single run complete!", "green")
            return
        
        # Continuous mode
        cprint(f"\n🌙 Anarcho Capital's Enhanced Sentiment Agent starting in {args.mode.replace('_', ' ')} mode", "cyan")
        cprint(f"   (checking every {config.SENTIMENT_CHECK_INTERVAL_MINUTES} minutes)...", "cyan")
        
        while True:
            try:
                agent.run()
                next_run = datetime.now() + timedelta(minutes=config.SENTIMENT_CHECK_INTERVAL_MINUTES)
                cprint(f"\n😴 Next sentiment check at {next_run.strftime('%H:%M:%S')}", "cyan")
                time.sleep(60 * config.SENTIMENT_CHECK_INTERVAL_MINUTES)
            except KeyboardInterrupt:
                raise
            except Exception as e:
                cprint(f"\n❌ Error in run loop: {str(e)}", "red")
                logger.error(f"Run loop error: {str(e)}")
                time.sleep(60)  # Wait a minute before retrying
                
    except KeyboardInterrupt:
        cprint("\n👋 Anarcho Capital's Enhanced Sentiment Agent shutting down gracefully...", "yellow")
    except Exception as e:
        cprint(f"\n❌ Fatal error: {str(e)}", "red")
        logger.error(f"Fatal error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()