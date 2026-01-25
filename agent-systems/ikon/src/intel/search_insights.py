"""
Search Insights for IKON IUL Pipeline
Uses Google Trends and YouTube autocomplete for keyword research
"""

import json
import logging
import time
from pathlib import Path
from typing import Dict, Any, List
import requests

logger = logging.getLogger("search_insights")


class SearchInsights:
    """Gathers search insights using Google Trends and YouTube autocomplete"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize search insights
        
        Args:
            config: IUL_INTEL_CONFIG from config.py
        """
        self.config = config
        self.keywords = config["search_keywords"]
        
        # Cache settings
        self.cache_ttl = config["gather_cadence"]["search"]  # 12 hours
        
        # Data storage
        project_root = Path(__file__).parent.parent.parent
        self.data_dir = project_root / "data" / "intel"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.trends_file = self.data_dir / "search_trends.json"
        
        logger.info(f"Search insights initialized ({len(self.keywords)} seed keywords)")
    
    def gather(self) -> Dict[str, Any]:
        """
        Gather search insights
        
        Returns:
            Dictionary with google_trends, youtube_autocomplete, insights
        """
        logger.info("Gathering search insights...")
        
        google_trends = self._get_google_trends()
        youtube_autocomplete = self._get_youtube_autocomplete()
        
        # Generate insights
        insights = self._generate_insights(google_trends, youtube_autocomplete)
        
        result = {
            "timestamp": time.time(),
            "google_trends": google_trends,
            "youtube_autocomplete": youtube_autocomplete,
            "insights": insights
        }
        
        # Save to file
        self._save_trends(result)
        
        logger.info(f"✅ Search insights gathered")
        return result
    
    def _get_google_trends(self) -> Dict[str, Any]:
        """Get Google Trends data using pytrends"""
        try:
            from pytrends.request import TrendReq
            
            pytrends = TrendReq(hl='en-US', tz=360, timeout=(10, 25))
            
            trends_data = {}
            
            for keyword in self.keywords[:5]:  # Limit to 5 to avoid rate limits
                try:
                    # Build payload
                    pytrends.build_payload([keyword], timeframe='today 3-m')
                    
                    # Get interest over time
                    interest_df = pytrends.interest_over_time()
                    
                    if not interest_df.empty:
                        avg_interest = interest_df[keyword].mean()
                        trends_data[keyword] = {
                            "avg_interest": round(float(avg_interest), 2),
                            "trend": "rising" if interest_df[keyword].iloc[-1] > avg_interest else "stable"
                        }
                    
                    # Get related queries
                    related_queries = pytrends.related_queries()
                    if keyword in related_queries and related_queries[keyword]['rising'] is not None:
                        rising = related_queries[keyword]['rising']
                        trends_data[keyword]["rising_queries"] = rising['query'].tolist()[:5] if not rising.empty else []
                    
                    time.sleep(2)  # Rate limit
                    
                except Exception as e:
                    logger.warning(f"Failed to get trends for '{keyword}': {e}")
            
            return trends_data
            
        except Exception as e:
            logger.error(f"Google Trends failed: {e}")
            return {}
    
    def _get_youtube_autocomplete(self) -> List[Dict[str, Any]]:
        """Get YouTube autocomplete suggestions (unofficial)"""
        suggestions_list = []
        
        for keyword in self.keywords[:5]:  # Limit to 5
            try:
                suggestions = self._fetch_youtube_suggestions(keyword)
                if suggestions:
                    suggestions_list.append({
                        "seed_keyword": keyword,
                        "suggestions": suggestions[:10]  # Top 10
                    })
                time.sleep(1)  # Rate limit
            except Exception as e:
                logger.warning(f"Failed to get suggestions for '{keyword}': {e}")
        
        return suggestions_list
    
    def _fetch_youtube_suggestions(self, query: str) -> List[str]:
        """Fetch YouTube autocomplete suggestions"""
        try:
            # YouTube autocomplete endpoint (unofficial)
            url = "https://suggestqueries.google.com/complete/search"
            params = {
                "client": "youtube",
                "ds": "yt",
                "q": query
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            # Parse response (JSONP format)
            data = response.json()
            
            if data and len(data) > 1:
                suggestions = [item[0] for item in data[1]]
                return suggestions
            
            return []
            
        except Exception as e:
            logger.warning(f"YouTube autocomplete request failed: {e}")
            return []
    
    def _generate_insights(self, google_trends: Dict[str, Any], 
                          youtube_autocomplete: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate actionable insights"""
        insights = {}
        
        # Rising keywords from Google Trends
        rising_keywords = []
        for keyword, data in google_trends.items():
            if data.get("trend") == "rising":
                rising_keywords.append(keyword)
            if "rising_queries" in data:
                rising_keywords.extend(data["rising_queries"][:3])
        
        insights["rising_keywords"] = list(set(rising_keywords))[:10]  # Top 10 unique
        
        # Most common autocomplete patterns
        all_suggestions = []
        for item in youtube_autocomplete:
            all_suggestions.extend(item["suggestions"])
        
        # Extract common patterns (e.g., "how to", "what is", "vs")
        patterns = {"how_to": 0, "what_is": 0, "vs": 0, "explained": 0, "pros_and_cons": 0}
        
        for suggestion in all_suggestions:
            suggestion_lower = suggestion.lower()
            if "how to" in suggestion_lower:
                patterns["how_to"] += 1
            if "what is" in suggestion_lower or "what are" in suggestion_lower:
                patterns["what_is"] += 1
            if " vs " in suggestion_lower:
                patterns["vs"] += 1
            if "explained" in suggestion_lower:
                patterns["explained"] += 1
            if "pros and cons" in suggestion_lower:
                patterns["pros_and_cons"] += 1
        
        insights["popular_query_patterns"] = {k: v for k, v in patterns.items() if v > 0}
        
        # Top trending topic
        if rising_keywords:
            insights["hottest_search_term"] = rising_keywords[0]
        
        return insights
    
    def _save_trends(self, data: Dict[str, Any]):
        """Save trends data to file"""
        try:
            with open(self.trends_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save trends: {e}")
    
    def load_latest_trends(self) -> Optional[Dict[str, Any]]:
        """Load latest trends data"""
        if not self.trends_file.exists():
            return None
        
        try:
            with open(self.trends_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load trends: {e}")
            return None
