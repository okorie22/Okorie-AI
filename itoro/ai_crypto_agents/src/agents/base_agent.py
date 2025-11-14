"""
🌙 Anarcho Capital's Base Agent
Parent class for all trading agents
"""

import os
import sys
from datetime import datetime
from pathlib import Path
import pandas as pd

class BaseAgent:
    def __init__(self, agent_type):
        """Initialize base agent with type"""
        self.type = agent_type
        self.start_time = datetime.now()
        self.running = True  # Add missing running attribute
        
    def run(self):
        """Default run method - should be overridden by child classes"""
        raise NotImplementedError("Each agent must implement its own run method")
        
    def stop(self):
        """Stop the agent gracefully"""
        self.running = False 