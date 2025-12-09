"""
🧠 ITORO Master Agent AI - Intelligent Config Optimization
AI-powered analysis and recommendations for system optimization
"""

import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from src.scripts.shared_services.logger import info, warning, error, debug
from src.models.model_factory import create_model

class MasterAgentAI:
    """
    AI-powered analysis engine for the Master Agent
    Uses DeepSeek to analyze system performance and generate optimization recommendations
    """
    
    def __init__(self):
        """Initialize the AI analysis module"""
        self.ai_model = create_model("deepseek")
        info("🧠 Master Agent AI initialized with DeepSeek")
    
    def analyze_system_health(self, health_summary: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze overall system health and provide insights
        Returns dict with analysis, concerns, and recommendations
        """
        try:
            prompt = self._build_system_health_prompt(health_summary)

            response = self.ai_model.generate_response(
                system_prompt="You are ITORO's Master Asset Manager. Analyze the system health and provide insights.",
                user_content=prompt,
                temperature=0.3,  # Lower temperature for more focused analysis
                max_tokens=1500
            )

            # Parse the response
            analysis = self._parse_analysis_response(response.content)

            return analysis

        except Exception as e:
            error(f"Error in system health analysis: {e}")
            return None
    
    def recommend_personality_mode(self, performance_data: Dict[str, Any], 
                                  market_sentiment: str) -> Tuple[str, str, float]:
        """
        Recommend personality mode based on performance and market conditions
        Returns: (mode, reasoning, confidence)
        """
        try:
            prompt = f"""You are ITORO's Master Agent. Analyze the current system performance and market conditions to recommend the optimal personality mode.

AVAILABLE MODES:
- AGGRESSIVE: For bull markets and strong performance (increase position sizes, reduce cooldowns)
- BALANCED: For neutral markets and steady performance (maintain standard parameters)
- CONSERVATIVE: For bear markets or underperformance (reduce position sizes, increase safety margins)

CURRENT PERFORMANCE:
{json.dumps(performance_data, indent=2)}

MARKET SENTIMENT: {market_sentiment}

Based on this data, recommend the optimal personality mode.

Respond in this EXACT format:
MODE: [AGGRESSIVE/BALANCED/CONSERVATIVE]
CONFIDENCE: [0.0-1.0]
REASONING: [Your detailed reasoning]
"""
            
            response = self.ai_model.generate_response(
                system_prompt="You are ITORO's Master Agent. Recommend optimal personality mode based on performance data.",
                user_content=prompt,
                temperature=0.2,
                max_tokens=500
            )

            # Parse response
            mode = "BALANCED"  # Default
            confidence = 0.5
            reasoning = ""

            lines = response.content.strip().split('\n')
            for line in lines:
                if line.startswith("MODE:"):
                    mode = line.replace("MODE:", "").strip()
                elif line.startswith("CONFIDENCE:"):
                    try:
                        confidence = float(line.replace("CONFIDENCE:", "").strip())
                    except:
                        confidence = 0.5
                elif line.startswith("REASONING:"):
                    reasoning = line.replace("REASONING:", "").strip()
            
            return mode, reasoning, confidence
        
        except Exception as e:
            error(f"Error recommending personality mode: {e}")
            return "BALANCED", "Error in analysis", 0.5
    
    def recommend_config_adjustments(self, health_summary: Dict[str, Any], 
                                    personality_mode: str) -> List[Dict[str, Any]]:
        """
        Recommend specific config adjustments based on system health and personality
        Returns list of recommendations with parameter, value, reasoning, confidence
        """
        try:
            # Get available parameters from config manager
            from src.scripts.shared_services.config_manager import get_config_manager
            config_manager = get_config_manager()
            
            # Get all whitelisted parameters with their info
            all_params = config_manager.list_parameters()
            param_info = {}
            for param_name in all_params:
                info = config_manager.get_parameter_info(param_name)
                if info:
                    param_info[param_name] = {
                        'category': info.category,
                        'description': info.description,
                        'min': info.min_value,
                        'max': info.max_value,
                        'allowed_values': info.allowed_values
                    }
            
            prompt = self._build_config_recommendation_prompt(health_summary, personality_mode, param_info)
            
            response = self.ai_model.generate_response(
                system_prompt="You are ITORO's Master Agent. Recommend specific configuration adjustments from the available parameters only.",
                user_content=prompt,
                temperature=0.3,
                max_tokens=2000
            )
            
            # Parse recommendations
            recommendations = self._parse_config_recommendations(response.content)
            
            # Filter to only include whitelisted parameters
            valid_recommendations = []
            for rec in recommendations:
                if rec.get('parameter') in all_params:
                    valid_recommendations.append(rec)
                else:
                    debug(f"⚠️ Master Agent AI suggested non-whitelisted parameter: {rec.get('parameter')} - ignored")
            
            return valid_recommendations
        
        except Exception as e:
            error(f"Error generating config recommendations: {e}")
            return []
    
    def analyze_goal_gap(self, goal_progress: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze the gap between current performance and PnL goal
        Identify what's preventing goal achievement
        """
        try:
            # Check if we have sufficient data for analysis
            if not goal_progress or not goal_progress.get('has_data', False):
                return {
                    "on_track": True,  # Can't be off-track if no data yet
                    "gap_severity": "none",
                    "main_blockers": ["Insufficient trading history - System just started"],
                    "recommended_actions": [
                        {
                            "action": "Begin live trading to establish baseline performance metrics",
                            "expected_impact_percent": 0.0,
                            "priority": "high"
                        }
                    ],
                    "confidence": 1.0
                }
            
            prompt = f"""You are ITORO's Master Agent analyzing why the system isn't meeting its PnL goals.

GOAL PROGRESS DATA:
{json.dumps(goal_progress, indent=2)}

Analyze:
1. Is the system on track to meet the goal?
2. What are the main factors preventing goal achievement?
3. What specific changes would help close the gap?
4. What's the estimated impact of each recommended change?

Provide a detailed analysis with actionable insights.

Respond in JSON format:
{{
  "on_track": true/false,
  "gap_severity": "low/medium/high/critical",
  "main_blockers": ["blocker1", "blocker2"],
  "recommended_actions": [
    {{"action": "description", "expected_impact_percent": 5.0, "priority": "high/medium/low"}}
  ],
  "confidence": 0.0-1.0
}}
"""
            
            response = self.ai_model.generate_response(
                system_prompt="You are ITORO's Master Agent. Analyze the gap between current performance and goals.",
                user_content=prompt,
                temperature=0.3,
                max_tokens=1000
            )

            # Try to parse as JSON
            try:
                analysis = json.loads(response.content)
                return analysis
            except:
                # Fallback parsing
                return {
                    "on_track": goal_progress.get('on_track', False),
                    "gap_severity": "unknown",
                    "main_blockers": ["AI response parsing failed - Check data quality"],
                    "recommended_actions": [],
                    "confidence": 0.3
                }
        
        except Exception as e:
            error(f"Error analyzing goal gap: {e}")
            return None
    
    def evaluate_data_quality_issues(self, data_quality: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate data quality and recommend adjustments to collection parameters
        """
        try:
            prompt = f"""You are ITORO's Master Agent evaluating data collection quality.

DATA QUALITY METRICS:
{json.dumps(data_quality, indent=2)}

Analyze the data quality and recommend specific adjustments to improve it.

Consider:
- Is data stale? (update intervals too long)
- Is data quality affecting trading decisions?
- Should we adjust timeframes, lookback periods, or scoring weights?

Respond in JSON format:
{{
  "overall_quality": "excellent/good/fair/poor",
  "critical_issues": ["issue1", "issue2"],
  "recommended_adjustments": [
    {{
      "parameter": "PARAM_NAME",
      "current_issue": "description",
      "recommended_value": "value",
      "reasoning": "why this helps",
      "confidence": 0.0-1.0
    }}
  ]
}}
"""
            
            response = self.ai_model.generate_response(
                system_prompt="You are ITORO's Master Agent. Evaluate data quality and recommend adjustments.",
                user_content=prompt,
                temperature=0.3,
                max_tokens=1500
            )

            # Try to parse as JSON
            try:
                evaluation = json.loads(response.content)
                return evaluation
            except:
                return {
                    "overall_quality": "unknown",
                    "critical_issues": [],
                    "recommended_adjustments": []
                }
        
        except Exception as e:
            error(f"Error evaluating data quality: {e}")
            return None
    
    def assess_config_change_impact(self, change_history: List[Dict[str, Any]], 
                                   performance_before: Dict[str, Any],
                                   performance_after: Dict[str, Any]) -> Dict[str, Any]:
        """
        Assess the impact of recent config changes on performance
        Determine if changes were beneficial and should be kept or rolled back
        """
        try:
            prompt = f"""You are ITORO's Master Agent evaluating the impact of recent configuration changes.

RECENT CONFIG CHANGES:
{json.dumps(change_history, indent=2)}

PERFORMANCE BEFORE CHANGES:
{json.dumps(performance_before, indent=2)}

PERFORMANCE AFTER CHANGES:
{json.dumps(performance_after, indent=2)}

Evaluate:
1. Did the changes improve or harm performance?
2. Which specific changes had the most impact?
3. Should any changes be rolled back?
4. What's the confidence level in this assessment?

Respond in JSON format:
{{
  "overall_impact": "positive/negative/neutral",
  "performance_change_percent": 0.0,
  "change_assessments": [
    {{
      "parameter": "PARAM_NAME",
      "impact": "positive/negative/neutral",
      "should_keep": true/false,
      "reasoning": "explanation"
    }}
  ],
  "rollback_recommended": true/false,
  "confidence": 0.0-1.0
}}
"""
            
            response = self.ai_model.generate_response(
                system_prompt="You are ITORO's Master Agent. Assess the impact of recent config changes.",
                user_content=prompt,
                temperature=0.2,
                max_tokens=1500
            )

            # Try to parse as JSON
            try:
                assessment = json.loads(response.content)
                return assessment
            except:
                return {
                    "overall_impact": "neutral",
                    "performance_change_percent": 0.0,
                    "change_assessments": [],
                    "rollback_recommended": False,
                    "confidence": 0.3
                }
        
        except Exception as e:
            error(f"Error assessing config change impact: {e}")
            return None
    
    def _build_system_health_prompt(self, health_summary: Dict[str, Any]) -> str:
        """Build prompt for system health analysis"""
        return f"""You are ITORO's Master Agent analyzing the overall system health.

SYSTEM HEALTH SUMMARY:
{json.dumps(health_summary, indent=2)}

Provide a comprehensive analysis including:
1. Overall system health assessment (excellent/good/fair/poor/critical)
2. Key strengths of the current system
3. Critical concerns or weaknesses
4. Immediate actions needed (if any)
5. Long-term optimization opportunities

Be specific and actionable in your recommendations.
"""
    
    def _build_config_recommendation_prompt(self, health_summary: Dict[str, Any], 
                                          personality_mode: str,
                                          available_params: Dict[str, Dict[str, Any]]) -> str:
        """Build prompt for config recommendations"""
        
        # Build parameter list grouped by category
        trading_params = []
        data_params = []
        
        for param_name, info in available_params.items():
            param_desc = f"  • {param_name}: {info['description']}"
            if info.get('min') is not None and info.get('max') is not None:
                param_desc += f" (range: {info['min']}-{info['max']})"
            elif info.get('allowed_values'):
                param_desc += f" (options: {', '.join(map(str, info['allowed_values']))})"
            
            if info['category'] == 'trading':
                trading_params.append(param_desc)
            else:
                data_params.append(param_desc)
        
        return f"""You are ITORO's Master Agent operating in {personality_mode} MODE.

SYSTEM HEALTH:
{json.dumps(health_summary, indent=2)}

PERSONALITY MODE GUIDELINES:
- AGGRESSIVE: Increase position sizes, reduce cooldowns, focus on opportunities
- BALANCED: Maintain standard parameters, optimize for consistency
- CONSERVATIVE: Reduce position sizes, increase safety margins, prioritize capital preservation

AVAILABLE PARAMETERS TO ADJUST:

TRADING PARAMETERS (require human approval):
{chr(10).join(trading_params[:20])}
{'... and ' + str(len(trading_params) - 20) + ' more' if len(trading_params) > 20 else ''}

DATA COLLECTION PARAMETERS (auto-adjustable):
{chr(10).join(data_params)}

**IMPORTANT**: You can ONLY recommend parameters from the list above. Do not invent new parameter names.

Recommend specific configuration adjustments that align with the current personality mode.
Select the most impactful 2-5 parameters to adjust based on system health.

For each recommendation, provide:
- Parameter name (must be from the list above)
- Recommended value (within valid range/options)
- Detailed reasoning
- Expected impact
- Confidence level (0.0-1.0)

Format each recommendation as:
PARAMETER: [exact parameter name from list above]
VALUE: [recommended value]
CATEGORY: [data/trading]
REASONING: [detailed explanation]
EXPECTED_IMPACT: [description]
CONFIDENCE: [0.0-1.0]
---
"""
    
    def _parse_analysis_response(self, response: str) -> Dict[str, Any]:
        """Parse AI response for system health analysis"""
        # Simple parsing - extract key insights
        return {
            'analysis': response,
            'timestamp': datetime.now().isoformat()
        }
    
    def _parse_config_recommendations(self, response: str) -> List[Dict[str, Any]]:
        """Parse AI response for config recommendations"""
        recommendations = []
        
        try:
            # Split by separator
            sections = response.split('---')
            
            for section in sections:
                if not section.strip():
                    continue
                
                rec = {}
                lines = section.strip().split('\n')
                
                for line in lines:
                    line = line.strip()
                    if line.startswith('PARAMETER:'):
                        rec['parameter'] = line.replace('PARAMETER:', '').strip()
                    elif line.startswith('VALUE:'):
                        value_str = line.replace('VALUE:', '').strip()
                        # Try to parse value
                        try:
                            rec['value'] = json.loads(value_str)
                        except:
                            rec['value'] = value_str
                    elif line.startswith('CATEGORY:'):
                        rec['category'] = line.replace('CATEGORY:', '').strip()
                    elif line.startswith('REASONING:'):
                        rec['reasoning'] = line.replace('REASONING:', '').strip()
                    elif line.startswith('EXPECTED_IMPACT:'):
                        rec['expected_impact'] = line.replace('EXPECTED_IMPACT:', '').strip()
                    elif line.startswith('CONFIDENCE:'):
                        try:
                            rec['confidence'] = float(line.replace('CONFIDENCE:', '').strip())
                        except:
                            rec['confidence'] = 0.5
                
                # Only add if we have essential fields
                if 'parameter' in rec and 'value' in rec:
                    recommendations.append(rec)
        
        except Exception as e:
            error(f"Error parsing recommendations: {e}")
        
        return recommendations

# Singleton accessor
_master_agent_ai = None

def get_master_agent_ai() -> MasterAgentAI:
    """Get the global MasterAgentAI instance"""
    global _master_agent_ai
    if _master_agent_ai is None:
        _master_agent_ai = MasterAgentAI()
    return _master_agent_ai

