"""
🌙 Anarcho Capital's Sentiment Data Extractor
Utility module for extracting chart analysis and Twitter sentiment data
Built with love by Anarcho Capital 🚀
"""

import os
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass
# Local imports with fallback for relative imports
try:
    from src.scripts.shared_services.logger import debug, info, warning, error
except ImportError:
    # Try relative imports when running from test directory
    from src.scripts.shared_services.logger import debug, info, warning, error

# Cloud database import
try:
    from src.scripts.database.cloud_database import get_cloud_database_manager
    CLOUD_DB_AVAILABLE = True
except ImportError:
    CLOUD_DB_AVAILABLE = False

@dataclass
class SentimentData:
    """Data class to hold combined sentiment analysis results"""
    chart_sentiment: str = "NEUTRAL"
    chart_confidence: float = 50.0
    chart_timestamp: float = 0.0
    chart_bullish_tokens: int = 0
    chart_bearish_tokens: int = 0
    chart_neutral_tokens: int = 0
    chart_total_tokens: int = 0
    
    twitter_classification: str = "NEUTRAL"
    twitter_sentiment_score: float = 0.0
    twitter_confidence: float = 50.0
    twitter_timestamp: str = ""
    twitter_num_tweets: int = 0
    twitter_tokens_analyzed: str = ""
    
    data_freshness_minutes: float = 0.0
    has_fresh_data: bool = False

class SentimentDataExtractor:
    """Utility class for extracting sentiment and chart analysis data"""
    
    def __init__(self):
        """Initialize the sentiment data extractor"""
        self.chart_sentiment_file = "src/data/charts/aggregated_market_sentiment.csv"
        self.twitter_sentiment_file = "src/data/sentiment_history.csv"
        self.twitter_sentiment_db = "src/data/sentiment_analysis.db"
        
        # Data freshness thresholds (in minutes)
        self.max_chart_data_age_minutes = 180  # 3 hours
        self.max_twitter_data_age_minutes = 120  # 2 hours
        
        debug("📊 Sentiment Data Extractor initialized")
    
    def get_latest_chart_sentiment(self) -> Tuple[Optional[Dict], str]:
        """
        Extract the most recent chart sentiment data from aggregated_market_sentiment.csv
        
        Returns:
            Tuple of (sentiment_data_dict, status_message)
        """
        try:
            if not os.path.exists(self.chart_sentiment_file):
                return None, "Chart sentiment file not found"
            
            # Read the CSV file
            df = pd.read_csv(self.chart_sentiment_file)
            
            if df.empty:
                return None, "Chart sentiment file is empty"
            
            # Get the most recent entry (highest timestamp)
            latest_row = df.loc[df['timestamp'].idxmax()]
            
            # Convert timestamp to datetime for age calculation
            chart_timestamp = float(latest_row['timestamp'])
            chart_datetime = datetime.fromtimestamp(chart_timestamp)
            current_time = datetime.now()
            age_minutes = (current_time - chart_datetime).total_seconds() / 60
            
            # Check data freshness
            is_fresh = age_minutes <= self.max_chart_data_age_minutes
            
            chart_data = {
                'overall_sentiment': latest_row.get('overall_sentiment', 'NEUTRAL'),
                'sentiment_score': float(latest_row.get('sentiment_score', 0.0)),
                'confidence': float(latest_row.get('confidence', 50.0)),
                'timestamp': chart_timestamp,
                'bullish_tokens': int(latest_row.get('bullish_tokens', 0)),
                'bearish_tokens': int(latest_row.get('bearish_tokens', 0)),
                'neutral_tokens': int(latest_row.get('neutral_tokens', 0)),
                'total_tokens_analyzed': int(latest_row.get('total_tokens_analyzed', 0)),
                'age_minutes': age_minutes,
                'is_fresh': is_fresh
            }
            
            status = f"Chart data extracted - Age: {age_minutes:.1f} minutes ({'fresh' if is_fresh else 'stale'})"
            debug(f"📈 {status}")
            
            return chart_data, status
            
        except Exception as e:
            error_msg = f"Error extracting chart sentiment: {str(e)}"
            error(error_msg)
            return None, error_msg
    
    def get_latest_twitter_sentiment(self) -> Tuple[Optional[Dict], str]:
        """
        Extract the most recent Twitter sentiment data from cloud database, local database, or CSV
        
        Returns:
            Tuple of (sentiment_data_dict, status_message)
        """
        # Try cloud database first
        if CLOUD_DB_AVAILABLE:
            cloud_data, cloud_status = self._get_twitter_sentiment_from_cloud()
            if cloud_data is not None:
                return cloud_data, cloud_status
        
        # Try local database second
        db_data, db_status = self._get_twitter_sentiment_from_db()
        if db_data is not None:
            return db_data, db_status
        
        # Fallback to CSV
        return self._get_twitter_sentiment_from_csv()
    
    def _get_twitter_sentiment_from_cloud(self) -> Tuple[Optional[Dict], str]:
        """Extract Twitter sentiment from cloud database"""
        try:
            db_manager = get_cloud_database_manager()
            if db_manager is None:
                # Cloud database not configured, fallback to local
                return self._get_twitter_sentiment_from_db()
            
            # Get the most recent sentiment entry
            query = '''
                SELECT timestamp, sentiment_score, overall_sentiment, num_tweets, 
                       tokens_analyzed, engagement_avg, ai_enhanced_score, ai_model_used
                FROM sentiment_data 
                WHERE sentiment_type = 'twitter'
                ORDER BY timestamp DESC 
                LIMIT 1
            '''
            
            results = db_manager.execute_query(query)
            
            if not results:
                return None, "No Twitter sentiment data found in cloud database"
            
            row = results[0]
            
            # Parse timestamp and calculate age
            timestamp_str = row['timestamp']
            try:
                # Handle PostgreSQL timestamp
                if isinstance(timestamp_str, str):
                    twitter_datetime = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                else:
                    twitter_datetime = timestamp_str
            except:
                # Fallback for other timestamp formats
                twitter_datetime = datetime.now() - timedelta(hours=24)  # Assume old data
            
            current_time = datetime.now()
            age_minutes = (current_time - twitter_datetime).total_seconds() / 60
            is_fresh = age_minutes <= self.max_twitter_data_age_minutes
            
            twitter_data = {
                'classification': row['overall_sentiment'],
                'sentiment_score': float(row['sentiment_score']),
                'timestamp': str(timestamp_str),
                'num_tweets': int(row['num_tweets']),
                'tokens_analyzed': row['tokens_analyzed'] or '',
                'engagement_avg': float(row['engagement_avg']) if row['engagement_avg'] else 0.0,
                'ai_enhanced_score': float(row['ai_enhanced_score']) if row['ai_enhanced_score'] else None,
                'ai_model_used': row['ai_model_used'] or 'unknown',
                'age_minutes': age_minutes,
                'is_fresh': is_fresh
            }
            
            status = f"Twitter data from cloud database - Age: {age_minutes:.1f} minutes ({'fresh' if is_fresh else 'stale'})"
            debug(f"☁️ {status}")
            
            return twitter_data, status
            
        except Exception as e:
            error_msg = f"Error extracting Twitter sentiment from cloud database: {str(e)}"
            warning(error_msg)
            return None, error_msg
    
    def _get_twitter_sentiment_from_db(self) -> Tuple[Optional[Dict], str]:
        """Extract Twitter sentiment from SQLite database"""
        try:
            if not os.path.exists(self.twitter_sentiment_db):
                return None, "Twitter sentiment database not found"
            
            conn = sqlite3.connect(self.twitter_sentiment_db)
            cursor = conn.cursor()
            
            # Get the most recent sentiment entry
            cursor.execute('''
                SELECT timestamp, sentiment_score, classification, num_tweets, 
                       tokens_analyzed, engagement_avg, ai_enhanced_score, ai_model_used
                FROM sentiment_history 
                ORDER BY timestamp DESC 
                LIMIT 1
            ''')
            
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                return None, "No Twitter sentiment data found in database"
            
            # Parse timestamp and calculate age
            timestamp_str = row[0]
            try:
                # Handle ISO format timestamp
                if 'T' in timestamp_str:
                    twitter_datetime = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                else:
                    twitter_datetime = datetime.fromisoformat(timestamp_str)
            except:
                # Fallback for other timestamp formats
                twitter_datetime = datetime.now() - timedelta(hours=24)  # Assume old data
            
            current_time = datetime.now()
            age_minutes = (current_time - twitter_datetime).total_seconds() / 60
            is_fresh = age_minutes <= self.max_twitter_data_age_minutes
            
            twitter_data = {
                'classification': row[2] or 'NEUTRAL',
                'sentiment_score': float(row[1]) if row[1] is not None else 0.0,
                'timestamp': timestamp_str,
                'num_tweets': int(row[3]) if row[3] is not None else 0,
                'tokens_analyzed': row[4] or '',
                'engagement_avg': float(row[5]) if row[5] is not None else 0.0,
                'ai_enhanced_score': float(row[6]) if row[6] is not None else None,
                'ai_model_used': row[7] or 'unknown',
                'age_minutes': age_minutes,
                'is_fresh': is_fresh
            }
            
            status = f"Twitter data from DB - Age: {age_minutes:.1f} minutes ({'fresh' if is_fresh else 'stale'})"
            debug(f"🐦 {status}")
            
            return twitter_data, status
            
        except Exception as e:
            error_msg = f"Error extracting Twitter sentiment from database: {str(e)}"
            warning(error_msg)
            return None, error_msg
    
    def _get_twitter_sentiment_from_csv(self) -> Tuple[Optional[Dict], str]:
        """Extract Twitter sentiment from CSV file as fallback"""
        try:
            if not os.path.exists(self.twitter_sentiment_file):
                return None, "Twitter sentiment CSV file not found"
            
            # Read the CSV file
            df = pd.read_csv(self.twitter_sentiment_file)
            
            if df.empty:
                return None, "Twitter sentiment CSV file is empty"
            
            # Get the most recent entry (last row, assuming chronological order)
            latest_row = df.iloc[-1]
            
            # Parse timestamp and calculate age
            timestamp_str = latest_row.get('timestamp', '')
            try:
                if 'T' in timestamp_str:
                    twitter_datetime = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                else:
                    twitter_datetime = datetime.fromisoformat(timestamp_str)
            except:
                twitter_datetime = datetime.now() - timedelta(hours=24)  # Assume old data
            
            current_time = datetime.now()
            age_minutes = (current_time - twitter_datetime).total_seconds() / 60
            is_fresh = age_minutes <= self.max_twitter_data_age_minutes
            
            twitter_data = {
                'classification': latest_row.get('classification', 'NEUTRAL'),
                'sentiment_score': float(latest_row.get('sentiment_score', 0.0)),
                'timestamp': timestamp_str,
                'num_tweets': int(latest_row.get('num_tweets', 0)),
                'tokens_analyzed': latest_row.get('tokens_analyzed', ''),
                'engagement_avg': float(latest_row.get('engagement_avg', 0.0)),
                'ai_enhanced_score': float(latest_row.get('ai_enhanced_score', 0.0)) if pd.notna(latest_row.get('ai_enhanced_score')) else None,
                'ai_model_used': latest_row.get('ai_model_used', 'unknown'),
                'age_minutes': age_minutes,
                'is_fresh': is_fresh
            }
            
            status = f"Twitter data from CSV - Age: {age_minutes:.1f} minutes ({'fresh' if is_fresh else 'stale'})"
            debug(f"🐦 {status}")
            
            return twitter_data, status
            
        except Exception as e:
            error_msg = f"Error extracting Twitter sentiment from CSV: {str(e)}"
            error(error_msg)
            return None, error_msg
    
    def get_combined_sentiment_data(self) -> SentimentData:
        """
        Get combined sentiment data from both chart analysis and Twitter sentiment
        
        Returns:
            SentimentData object with all available sentiment information
        """
        sentiment_data = SentimentData()
        
        # Get chart sentiment data
        chart_data, chart_status = self.get_latest_chart_sentiment()
        if chart_data:
            sentiment_data.chart_sentiment = chart_data.get('overall_sentiment', 'NEUTRAL')
            sentiment_data.chart_confidence = chart_data.get('confidence', 50.0)
            sentiment_data.chart_timestamp = chart_data.get('timestamp', 0.0)
            sentiment_data.chart_bullish_tokens = chart_data.get('bullish_tokens', 0)
            sentiment_data.chart_bearish_tokens = chart_data.get('bearish_tokens', 0)
            sentiment_data.chart_neutral_tokens = chart_data.get('neutral_tokens', 0)
            sentiment_data.chart_total_tokens = chart_data.get('total_tokens_analyzed', 0)
            
            chart_fresh = chart_data.get('is_fresh', False)
        else:
            chart_fresh = False
            warning(f"Chart sentiment unavailable: {chart_status}")
        
        # Get Twitter sentiment data
        twitter_data, twitter_status = self.get_latest_twitter_sentiment()
        if twitter_data:
            sentiment_data.twitter_classification = twitter_data.get('classification', 'NEUTRAL')
            sentiment_data.twitter_sentiment_score = twitter_data.get('sentiment_score', 0.0)
            sentiment_data.twitter_timestamp = twitter_data.get('timestamp', '')
            sentiment_data.twitter_num_tweets = twitter_data.get('num_tweets', 0)
            sentiment_data.twitter_tokens_analyzed = twitter_data.get('tokens_analyzed', '')
            
            # Calculate confidence based on number of tweets and engagement
            base_confidence = 30.0  # Base confidence
            tweet_confidence = min(50.0, sentiment_data.twitter_num_tweets * 0.2)  # Up to 50% from tweet count
            engagement_confidence = min(20.0, twitter_data.get('engagement_avg', 0.0) * 400)  # Up to 20% from engagement
            sentiment_data.twitter_confidence = base_confidence + tweet_confidence + engagement_confidence
            
            twitter_fresh = twitter_data.get('is_fresh', False)
        else:
            twitter_fresh = False
            warning(f"Twitter sentiment unavailable: {twitter_status}")
        
        # Calculate overall data freshness
        if chart_data and twitter_data:
            sentiment_data.data_freshness_minutes = min(
                chart_data.get('age_minutes', float('inf')),
                twitter_data.get('age_minutes', float('inf'))
            )
        elif chart_data:
            sentiment_data.data_freshness_minutes = chart_data.get('age_minutes', float('inf'))
        elif twitter_data:
            sentiment_data.data_freshness_minutes = twitter_data.get('age_minutes', float('inf'))
        else:
            sentiment_data.data_freshness_minutes = float('inf')
        
        sentiment_data.has_fresh_data = chart_fresh or twitter_fresh
        
        # Suppress logging to avoid display overlap
        # info(f"📊 Combined sentiment data extracted - Chart: {sentiment_data.chart_sentiment} ({sentiment_data.chart_confidence:.1f}%), Twitter: {sentiment_data.twitter_classification} ({sentiment_data.twitter_confidence:.1f}%)")
        
        return sentiment_data
    
    def format_sentiment_for_ai_prompt(self, sentiment_data: SentimentData) -> str:
        """
        Format sentiment data for inclusion in AI prompts
        
        Args:
            sentiment_data: SentimentData object with sentiment information
            
        Returns:
            Formatted string for AI prompt inclusion
        """
        if not sentiment_data.has_fresh_data:
            return """
Market Sentiment Analysis:
- Status: No fresh sentiment data available
- Recommendation: Proceed with caution due to lack of current market sentiment insights
"""
        
        # Format chart sentiment section
        chart_section = f"""
Technical Chart Sentiment:
- Overall Market Sentiment: {sentiment_data.chart_sentiment}
- Technical Confidence: {sentiment_data.chart_confidence:.1f}%
- Tokens Analyzed: {sentiment_data.chart_total_tokens} (Bullish: {sentiment_data.chart_bullish_tokens}, Bearish: {sentiment_data.chart_bearish_tokens}, Neutral: {sentiment_data.chart_neutral_tokens})
- Data Age: {sentiment_data.data_freshness_minutes:.1f} minutes"""
        
        # Format Twitter sentiment section
        twitter_section = f"""
Social Media Sentiment:
- Twitter Classification: {sentiment_data.twitter_classification}
- Social Confidence: {sentiment_data.twitter_confidence:.1f}%
- Tweets Analyzed: {sentiment_data.twitter_num_tweets}
- Tokens Tracked: {sentiment_data.twitter_tokens_analyzed}"""
        
        # Add sentiment alignment analysis
        alignment_analysis = self._analyze_sentiment_alignment(sentiment_data)
        
        return f"""
Market Sentiment Analysis:
{chart_section}

{twitter_section}

Sentiment Alignment:
{alignment_analysis}
"""
    
    def _analyze_sentiment_alignment(self, sentiment_data: SentimentData) -> str:
        """Analyze alignment between chart and Twitter sentiment"""
        chart_sentiment = sentiment_data.chart_sentiment
        twitter_sentiment = sentiment_data.twitter_classification
        
        # Map sentiments to scores for comparison
        sentiment_scores = {
            'STRONG_BULLISH': 2,
            'BULLISH': 1,
            'NEUTRAL': 0,
            'BEARISH': -1,
            'STRONG_BEARISH': -2
        }
        
        chart_score = sentiment_scores.get(chart_sentiment, 0)
        twitter_score = sentiment_scores.get(twitter_sentiment, 0)
        
        # Calculate alignment
        if chart_score == twitter_score:
            if chart_score > 0:
                return f"- Strong BULLISH alignment between technical and social sentiment (High conviction signal)"
            elif chart_score < 0:
                return f"- Strong BEARISH alignment between technical and social sentiment (High conviction signal)"
            else:
                return f"- Both technical and social sentiment are NEUTRAL (Low conviction environment)"
        elif abs(chart_score - twitter_score) == 1:
            return f"- Moderate sentiment divergence (Technical: {chart_sentiment}, Social: {twitter_sentiment}) - Mixed signals"
        else:
            return f"- Strong sentiment divergence (Technical: {chart_sentiment}, Social: {twitter_sentiment}) - Conflicting signals, proceed with caution"

# Global instance for easy access
_sentiment_extractor = None

def get_sentiment_data_extractor() -> SentimentDataExtractor:
    """Get the global sentiment data extractor instance"""
    global _sentiment_extractor
    if _sentiment_extractor is None:
        _sentiment_extractor = SentimentDataExtractor()
    return _sentiment_extractor
