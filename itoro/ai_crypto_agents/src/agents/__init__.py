"""
Anarcho Capital's Trading Agents
Built with love by Anarcho Capital 🚀
"""

from src.agents.copybot_agent import CopyBotAgent
from src.agents.risk_agent import RiskAgent
from src.agents.harvesting_agent import HarvestingAgent
from src.agents.staking_agent import StakingAgent

# Singleton instances
_copybot_agent_instance = None
_risk_agent_instance = None
_harvesting_agent_instance = None
_staking_agent_instance = None

def get_copybot_agent():
    global _copybot_agent_instance
    if _copybot_agent_instance is None:
        _copybot_agent_instance = CopybotAgent()
    return _copybot_agent_instance

def get_risk_agent():
    global _risk_agent_instance
    if _risk_agent_instance is None:
        _risk_agent_instance = RiskAgent()
    return _risk_agent_instance

def get_harvesting_agent():
    global _harvesting_agent_instance
    if _harvesting_agent_instance is None:
        _harvesting_agent_instance = HarvestingAgent(enable_ai=True)
    return _harvesting_agent_instance

def get_staking_agent():
    global _staking_agent_instance
    if _staking_agent_instance is None:
        _staking_agent_instance = StakingAgent()
    return _staking_agent_instance

