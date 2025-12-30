import sys
import os
import math
import importlib.util
from pathlib import Path
from datetime import datetime, timedelta
import json
import random
import time

from PySide6.QtWidgets import (QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QSlider, QComboBox, 
                             QLineEdit, QTextEdit, QProgressBar, QFrame, QGridLayout,
                             QSplitter, QGroupBox, QCheckBox, QSpacerItem, QSizePolicy,
                             QFileDialog, QMessageBox, QDialog, QDialogButtonBox, QScrollArea)
from PySide6.QtCore import Qt, QTimer, Signal, Slot, QSize, QThread, QObject
from PySide6.QtGui import QColor, QFont, QPalette, QLinearGradient, QGradient, QPainter, QPen, QBrush

# Redis import (optional - graceful degradation if not available)
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

# Import strategy runner
from strategy_runner import StrategyRunner

# Define cyberpunk color scheme
class CyberpunkColors:
    BACKGROUND = "#0D0D14"
    PRIMARY = "#00FFFF"    # Neon Blue
    SECONDARY = "#FF00FF"  # Neon Purple
    TERTIARY = "#00FF00"   # Neon Green
    WARNING = "#FF6600"    # Neon Orange
    DANGER = "#FF0033"     # Neon Red
    SUCCESS = "#33FF33"    # Neon Green
    TEXT_LIGHT = "#E0E0E0"
    TEXT_WHITE = "#FFFFFF"

# Custom styled widgets
class NeonButton(QPushButton):
    def __init__(self, text, color=CyberpunkColors.PRIMARY, parent=None):
        super().__init__(text, parent)
        self.color = QColor(color)
        self.setMinimumHeight(40)
        self.setCursor(Qt.PointingHandCursor)
        
        # Set stylesheet
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {color};
                border: 2px solid {color};
                border-radius: 5px;
                padding: 5px 15px;
                font-family: 'Rajdhani', sans-serif;
                font-weight: bold;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: {color};
                color: {CyberpunkColors.BACKGROUND};
            }}
            QPushButton:pressed {{
                background-color: {CyberpunkColors.BACKGROUND};
                color: {color};
            }}
        """)

class NeonFrame(QFrame):
    def __init__(self, color=CyberpunkColors.PRIMARY, parent=None):
        super().__init__(parent)
        self.color = QColor(color)
        self.setFrameShape(QFrame.StyledPanel)
        self.setLineWidth(2)
        self.setStyleSheet(f"""
            NeonFrame {{
                background-color: {CyberpunkColors.BACKGROUND};
                border: 2px solid {color};
                border-radius: 5px;
            }}
        """)

class ConsoleOutput(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setStyleSheet(f"""
            QTextEdit {{
                background-color: #0A0A0A;
                color: {CyberpunkColors.TEXT_LIGHT};
                border: 1px solid {CyberpunkColors.PRIMARY};
                font-family: 'Share Tech Mono', monospace;
                padding: 10px;
            }}
        """)
        
    def append_message(self, message, message_type="info"):
        color_map = {
            "info": CyberpunkColors.TEXT_LIGHT,
            "success": CyberpunkColors.SUCCESS,
            "warning": CyberpunkColors.WARNING,
            "error": CyberpunkColors.DANGER,
            "system": CyberpunkColors.PRIMARY
        }
        color = color_map.get(message_type, CyberpunkColors.TEXT_LIGHT)
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.append(f'<span style="color:{color};">[{timestamp}] {message}</span>')

class AIAnalysisConsole(QTextEdit):
    """Console for displaying AI pattern analysis and recommendations"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMinimumHeight(300)
        self.setStyleSheet(f"""
            QTextEdit {{
                background-color: #0A0A0A;
                color: {CyberpunkColors.TEXT_LIGHT};
                border: 2px solid {CyberpunkColors.TERTIARY};
                font-family: 'Share Tech Mono', monospace;
                padding: 15px;
                font-size: 13px;
            }}
        """)
        
        # Add welcome message
        self.append_welcome_message()
    
    def append_welcome_message(self):
        """Display welcome message"""
        html = f"""
        <div style="color: {CyberpunkColors.TERTIARY}; text-align: center; padding: 20px;">
            <h2 style="color: {CyberpunkColors.PRIMARY};">AI Pattern Analysis Console</h2>
            <p>Waiting for pattern detection to start...</p>
            <p style="color: {CyberpunkColors.TERTIARY}; font-size: 11px;">
                Use Menu → Strategy → Run Pattern Detection to begin
            </p>
        </div>
        """
        self.setHtml(html)
    
    def display_pattern_analysis(self, pattern_data):
        """Display a detected pattern with AI analysis"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        html = f"""
        <div style="border-left: 3px solid {CyberpunkColors.SUCCESS}; padding-left: 10px; margin: 10px 0;">
            <div style="color: {CyberpunkColors.SUCCESS}; font-weight: bold; font-size: 14px;">
                [{timestamp}] PATTERN DETECTED: {pattern_data.get('pattern_type', 'Unknown')}
            </div>
            <div style="color: {CyberpunkColors.PRIMARY}; margin-top: 5px;">
                Symbol: {pattern_data.get('symbol', 'N/A')} | Timeframe: {pattern_data.get('timeframe', 'N/A')}
            </div>
            <div style="color: {CyberpunkColors.TEXT_LIGHT}; margin-top: 10px;">
                <strong>AI Analysis:</strong><br/>
                {pattern_data.get('ai_analysis', 'No analysis available')}
            </div>
            <div style="color: {CyberpunkColors.TERTIARY}; margin-top: 10px;">
                <strong>Recommendation:</strong><br/>
                {pattern_data.get('recommendation', 'No recommendation available')}
            </div>
        </div>
        """
        self.append(html)
        
        # Auto-scroll to bottom
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())
        
        # Limit to last 50 patterns
        self.limit_content()
    
    def limit_content(self, max_patterns=50):
        """Keep only the last max_patterns patterns"""
        # This is a simple implementation - counts divs
        html = self.toHtml()
        pattern_count = html.count('PATTERN DETECTED:')
        if pattern_count > max_patterns:
            # Keep only recent patterns by clearing and showing welcome
            self.append_welcome_message()
    
    def append_message(self, message, message_type="info"):
        """Add a simple message (compatible with console interface)"""
        color_map = {
            "info": CyberpunkColors.TEXT_LIGHT,
            "success": CyberpunkColors.SUCCESS,
            "warning": CyberpunkColors.WARNING,
            "error": CyberpunkColors.DANGER,
        }
        color = color_map.get(message_type, CyberpunkColors.TEXT_LIGHT)
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        html = f'<div style="color:{color};">[{timestamp}] {message}</div>'
        self.append(html)

# Legacy compatibility - keep PortfolioVisualization as alias
class PortfolioVisualization(AIAnalysisConsole):
    """Legacy compatibility - redirects to AIAnalysisConsole"""
    def __init__(self, parent=None):
        super().__init__(parent)
        
    def set_portfolio_data(self, tokens):
        """Legacy method for compatibility - converts portfolio data to message"""
        message = f"Portfolio update: {len(tokens)} tokens"
        self.append_message(message, "info")

class DataUpdateWorker(QObject):
    """Worker thread for monitoring data updates from Redis"""
    data_updated = Signal(str, dict)  # data_type, data
    
    def __init__(self):
        super().__init__()
        self.running = False
        self.redis_client = None
        self.pubsub = None
        # Redis connection moved to run() method to avoid startup errors
        
    def run(self):
        """Run the Redis subscriber loop"""
        # Try to connect to Redis when data collection is started
        if REDIS_AVAILABLE:
            # Retry connecting to Redis up to 5 times with delays
            max_retries = 5
            for attempt in range(max_retries):
                try:
                    self.redis_client = redis.Redis(
                        host='localhost',
                        port=6379,
                        decode_responses=True,
                        socket_connect_timeout=3
                    )
                    # Test connection
                    self.redis_client.ping()
                    self.pubsub = self.redis_client.pubsub()
                    print("[DATA WORKER] Connected to Redis for real-time updates")
                    break  # Success, exit retry loop
                except Exception as e:
                    if attempt < max_retries - 1:
                        print(f"[DATA WORKER] Redis not ready yet (attempt {attempt + 1}/{max_retries}), waiting...")
                        time.sleep(2)  # Wait 2 seconds before retry
                    else:
                        print(f"[DATA WORKER] Failed to connect to Redis after {max_retries} attempts: {e}")
                        print("[DATA WORKER] Data collection may not have started properly")
                        self.redis_client = None
                        return
        else:
            print("[DATA WORKER] Redis library not available")
            return

        if not self.redis_client or not self.pubsub:
            print("[DATA WORKER] Redis not available - data updates disabled")
            return
        
        try:
            # Subscribe to data collection channels
            self.pubsub.subscribe('oi:updates', 'funding:updates', 'chart:updates')
            self.running = True
            print("[DATA WORKER] Listening for data updates...")
            
            for message in self.pubsub.listen():
                if not self.running:
                    break
                    
                if message['type'] == 'message':
                    try:
                        channel = message['channel']
                        data = json.loads(message['data'])
                        data_type = channel.split(':')[0]  # Extract 'oi', 'funding', or 'chart'
                        self.data_updated.emit(data_type, data)
                    except Exception as e:
                        print(f"[DATA WORKER] Error processing message: {e}")
                        
        except Exception as e:
            print(f"[DATA WORKER] Error in subscriber loop: {e}")
        finally:
            if self.pubsub:
                self.pubsub.close()
    
    def stop(self):
        """Stop the worker"""
        self.running = False
        if self.pubsub:
            self.pubsub.close()

class DataStatusCard(NeonFrame):
    """Status card for displaying data collection metrics"""
    def __init__(self, data_type, color, parent=None):
        super().__init__(color, parent)
        self.data_type = data_type
        self.color = QColor(color)
        
        # Create layout
        layout = QVBoxLayout(self)
        
        # Data type header
        self.name_label = QLabel(data_type)
        self.name_label.setStyleSheet(f"""
            QLabel {{
                color: {color};
                font-family: 'Orbitron', sans-serif;
                font-size: 16px;
                font-weight: bold;
            }}
        """)
        layout.addWidget(self.name_label)
        
        # Status indicator
        status_layout = QHBoxLayout()
        status_layout.addWidget(QLabel("Status:"))
        self.status_label = QLabel("Idle")
        self.status_label.setStyleSheet(f"color: {CyberpunkColors.TERTIARY};")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        layout.addLayout(status_layout)
        
        # Last update timestamp
        update_layout = QHBoxLayout()
        update_layout.addWidget(QLabel("Last Update:"))
        self.last_update_label = QLabel("Never")
        update_layout.addWidget(self.last_update_label)
        update_layout.addStretch()
        layout.addLayout(update_layout)
        
        # Key metrics display
        metrics_layout = QVBoxLayout()
        metrics_layout.addWidget(QLabel("Metrics:"))
        self.metrics_label = QLabel("--")
        self.metrics_label.setWordWrap(True)
        self.metrics_label.setStyleSheet(f"""
            QLabel {{
                color: {CyberpunkColors.PRIMARY};
                font-family: 'Share Tech Mono', monospace;
                font-size: 11px;
                padding: 5px;
            }}
        """)
        metrics_layout.addWidget(self.metrics_label)
        layout.addLayout(metrics_layout)
        
        # Set default styling
        self.setStyleSheet(f"""
            QLabel {{
                color: {CyberpunkColors.TEXT_LIGHT};
                font-family: 'Rajdhani', sans-serif;
            }}
        """)
        
    def update_data(self, data: dict):
        """Update card with new data"""
        # Update status
        self.status_label.setText("Collecting")
        self.status_label.setStyleSheet(f"color: {CyberpunkColors.SUCCESS};")
        
        # Update last update time
        self.last_update_label.setText(datetime.now().strftime("%H:%M:%S"))
        
        # Update metrics based on data type
        if self.data_type == "Open Interest":
            metrics_text = f"OI: {data.get('oi', '--')}\nChange: {data.get('oi_change', '--')}%"
        elif self.data_type == "Funding Rates":
            metrics_text = f"Rate: {data.get('funding_rate', '--')}%\nNext: {data.get('next_funding', '--')}"
        elif self.data_type == "Chart Analysis":
            metrics_text = f"Trend: {data.get('trend', '--')}\nStrength: {data.get('strength', '--')}"
        else:
            metrics_text = str(data)
        
        self.metrics_label.setText(metrics_text)
    
    def set_idle(self):
        """Set card to idle state"""
        self.status_label.setText("Idle")
        self.status_label.setStyleSheet(f"color: {CyberpunkColors.TERTIARY};")
    
    def set_error(self, error_msg: str = "Error"):
        """Set card to error state"""
        self.status_label.setText(error_msg)
        self.status_label.setStyleSheet(f"color: {CyberpunkColors.DANGER};")

class AgentStatusCard(DataStatusCard):
    """Legacy compatibility - redirects to DataStatusCard"""
    def __init__(self, agent_name, color, parent=None):
        super().__init__(agent_name, color, parent)
        self.agent_name = agent_name
        
    def start_agent(self):
        """Legacy method for compatibility"""
        self.status_label.setText("Active")
        self.status_label.setStyleSheet(f"color: {CyberpunkColors.SUCCESS};")
        
    def stop_agent(self):
        """Legacy method for compatibility"""
        self.set_idle()
        
    def update_status(self, status_data):
        """Update card with real agent status data"""
        if 'status' in status_data:
            status = status_data['status']
            self.status_label.setText(status)
            if status == "Active" or status == "Collecting":
                self.status_label.setStyleSheet(f"color: {CyberpunkColors.SUCCESS};")
            else:
                self.status_label.setStyleSheet(f"color: {CyberpunkColors.DANGER};")
        
        # Update with data if available
        if 'data' in status_data:
            self.update_data(status_data['data'])

class ConfigEditor(QWidget):
    """Widget for editing configuration values"""
    config_saved = Signal(dict)
    
    def __init__(self, config_data=None, parent=None):
        super().__init__(parent)
        self.config_data = config_data or {}
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Create scrollable form
        form_layout = QGridLayout()
        row = 0
        
        # Create widgets for each config item
        self.widgets = {}
        
        # Group similar settings
        groups = {
            "AI Settings": ["AI_MODEL", "AI_MAX_TOKENS", "AI_TEMPERATURE"],
            "Risk Management": ["CASH_PERCENTAGE", "MAX_POSITION_PERCENTAGE", "MINIMUM_BALANCE_USD", "USE_AI_CONFIRMATION"],
            "DCA & Staking": ["STAKING_ALLOCATION_PERCENTAGE", "DCA_INTERVAL_MINUTES", "TAKE_PROFIT_PERCENTAGE", "FIXED_DCA_AMOUNT"],
            "Agent Intervals": ["SLEEP_BETWEEN_RUNS_MINUTES", "CHART_CHECK_INTERVAL_MINUTES"],
            "Wallet Settings": ["address", "symbol"]
        }
        
        for group_name, keys in groups.items():
            # Add group header
            group_label = QLabel(group_name)
            group_label.setStyleSheet(f"""
                font-family: 'Orbitron', sans-serif;
                font-size: 16px;
                font-weight: bold;
                color: {CyberpunkColors.PRIMARY};
                padding-top: 10px;
            """)
            form_layout.addWidget(group_label, row, 0, 1, 2)
            row += 1
            
            # Add settings in this group
            for key in keys:
                if key in self.config_data:
                    value = self.config_data[key]
                    label = QLabel(key.replace("_", " ").title() + ":")
                    
                    # Create appropriate widget based on value type
                    if isinstance(value, bool):
                        widget = QCheckBox()
                        widget.setChecked(value)
                    elif isinstance(value, int):
                        if key in ["AI_TEMPERATURE", "CASH_PERCENTAGE", "MAX_POSITION_PERCENTAGE", 
                                  "STAKING_ALLOCATION_PERCENTAGE", "TAKE_PROFIT_PERCENTAGE"]:
                            widget = QSlider(Qt.Horizontal)
                            widget.setRange(0, 100)
                            widget.setValue(value)
                        else:
                            widget = QLineEdit(str(value))
                    elif isinstance(value, float):
                        widget = QLineEdit(str(value))
                    elif isinstance(value, str):
                        if key == "AI_MODEL":
                            widget = QComboBox()
                            models = ["claude-3-haiku-20240307", "claude-3-sonnet-20240229", "claude-3-opus-20240229"]
                            widget.addItems(models)
                            current_index = widget.findText(value)
                            if current_index >= 0:
                                widget.setCurrentIndex(current_index)
                        else:
                            widget = QLineEdit(value)
                    else:
                        widget = QLineEdit(str(value))
                    
                    form_layout.addWidget(label, row, 0)
                    form_layout.addWidget(widget, row, 1)
                    self.widgets[key] = widget
                    row += 1
            
            # Add separator
            separator = QFrame()
            separator.setFrameShape(QFrame.HLine)
            separator.setFrameShadow(QFrame.Sunken)
            separator.setStyleSheet(f"background-color: {CyberpunkColors.PRIMARY}; max-height: 1px;")
            form_layout.addWidget(separator, row, 0, 1, 2)
            row += 1
        
        # Add form to layout
        form_widget = QWidget()
        form_widget.setLayout(form_layout)
        
        # Add scrollable area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(form_widget)
        layout.addWidget(scroll_area)
        
        # Add save button
        save_button = NeonButton("Save Configuration", CyberpunkColors.SUCCESS)
        save_button.clicked.connect(self.save_config)
        layout.addWidget(save_button)
        
    def save_config(self):
        """Save configuration values from widgets"""
        updated_config = {}
        
        for key, widget in self.widgets.items():
            if isinstance(widget, QCheckBox):
                updated_config[key] = widget.isChecked()
            elif isinstance(widget, QSlider):
                updated_config[key] = widget.value()
            elif isinstance(widget, QComboBox):
                updated_config[key] = widget.currentText()
            elif isinstance(widget, QLineEdit):
                # Try to convert to appropriate type
                value = widget.text()
                original_value = self.config_data.get(key)
                
                if isinstance(original_value, int):
                    try:
                        updated_config[key] = int(value)
                    except ValueError:
                        updated_config[key] = original_value
                elif isinstance(original_value, float):
                    try:
                        updated_config[key] = float(value)
                    except ValueError:
                        updated_config[key] = original_value
                else:
                    updated_config[key] = value
        
        # Emit signal with updated config
        self.config_saved.emit(updated_config)
        
        # Show confirmation
        QMessageBox.information(self, "Configuration Saved", 
                               "Configuration has been saved successfully.")

class AgentWorker(QObject):
    """Worker thread for running agents"""
    status_update = Signal(str, dict)  # agent_name, status_data
    console_message = Signal(str, str)  # message, message_type
    portfolio_update = Signal(list)  # token_data
    
    def __init__(self, agent_name, agent_module_path, parent=None):
        super().__init__(parent)
        self.agent_name = agent_name
        self.agent_module_path = agent_module_path
        self.running = False
        self.agent = None
        
    def run(self):
        """Run the agent in a separate thread"""
        self.running = True
        self.console_message.emit(f"Starting {self.agent_name}...", "system")
        
        try:
            # Import agent module
            spec = importlib.util.spec_from_file_location("agent_module", self.agent_module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Initialize agent
            if self.agent_name == "copybot":
                self.agent = module.CopyBotAgent()
            elif self.agent_name == "risk":
                self.agent = module.RiskAgent()
            elif self.agent_name == "dca_staking":
                self.agent = module.DCAStakingAgent()
            elif self.agent_name == "chart_analysis":
                self.agent = module.ChartAnalysisAgent()
            
            # Run agent
            if self.agent:
                # Update status
                status_data = {
                    "status": "Active",
                    "last_run": datetime.now().strftime("%H:%M:%S"),
                    "next_run": (datetime.now() + timedelta(minutes=30)).strftime("%H:%M:%S"),
                    "progress": 0
                }
                self.status_update.emit(self.agent_name, status_data)
                
                # Simulate agent running
                for i in range(100):
                    if not self.running:
                        break
                    
                    # Update progress
                    status_data["progress"] = i + 1
                    self.status_update.emit(self.agent_name, status_data)
                    
                    # Emit console messages
                    if i % 10 == 0:
                        self.console_message.emit(f"{self.agent_name} processing step {i+1}/100", "info")
                    
                    # Sleep
                    QThread.msleep(100)
                
                # Emit completion message
                self.console_message.emit(f"{self.agent_name} completed successfully", "success")
                
                # Update status
                status_data = {
                    "status": "Active",
                    "last_run": datetime.now().strftime("%H:%M:%S"),
                    "next_run": (datetime.now() + timedelta(minutes=30)).strftime("%H:%M:%S"),
                    "progress": 0
                }
                self.status_update.emit(self.agent_name, status_data)
                
                # Update portfolio data (simulated)
                if self.agent_name == "risk":
                    self.update_portfolio_data()
        
        except Exception as e:
            self.console_message.emit(f"Error in {self.agent_name}: {str(e)}", "error")
            
            # Update status
            status_data = {
                "status": "Error",
                "last_run": datetime.now().strftime("%H:%M:%S"),
                "next_run": "Not scheduled",
                "progress": 0
            }
            self.status_update.emit(self.agent_name, status_data)
        
        self.running = False
    
    def stop(self):
        """Stop the agent"""
        self.running = False
        self.console_message.emit(f"Stopping {self.agent_name}...", "warning")
    
    def update_portfolio_data(self):
        """Simulate portfolio data update"""
        # This would normally come from the risk agent
        sample_tokens = [
            {"name": "SOL", "allocation": 0.35, "performance": 0.12, "volatility": 0.08},
            {"name": "BONK", "allocation": 0.15, "performance": 0.25, "volatility": 0.15},
            {"name": "JTO", "allocation": 0.20, "performance": -0.05, "volatility": 0.10},
            {"name": "PYTH", "allocation": 0.10, "performance": 0.08, "volatility": 0.05},
            {"name": "USDC", "allocation": 0.20, "performance": 0.0, "volatility": 0.01}
        ]
        
        # Add some randomness to simulate changes
        for token in sample_tokens:
            perf_change = (random.random() - 0.5) * 0.05
            token['performance'] = max(-0.5, min(0.5, token['performance'] + perf_change))
            
            alloc_change = (random.random() - 0.5) * 0.02
            token['allocation'] = max(0.01, min(0.5, token['allocation'] + alloc_change))
        
        self.portfolio_update.emit(sample_tokens)

class MainWindow(QMainWindow):
    def __init__(self, config_path=None, src_path=None):
        super().__init__()
        
        # Store paths
        self.config_path = config_path
        self.src_path = src_path
        
        # Load configuration
        self.config_data = self.load_config()
        
        # Set window properties
        self.setWindowTitle("AI Crypto Trading System")
        self.resize(1200, 800)
        
        # Create menu bar
        self.setup_menu_bar()
        
        # Set application style
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {CyberpunkColors.BACKGROUND};
            }}
            QTabWidget::pane {{
                border: 1px solid {CyberpunkColors.PRIMARY};
                background-color: {CyberpunkColors.BACKGROUND};
            }}
            QTabBar::tab {{
                background-color: {CyberpunkColors.BACKGROUND};
                color: {CyberpunkColors.TEXT_LIGHT};
                border: 1px solid {CyberpunkColors.PRIMARY};
                padding: 8px 16px;
                margin-right: 2px;
                font-family: 'Rajdhani', sans-serif;
            }}
            QTabBar::tab:selected {{
                background-color: {CyberpunkColors.PRIMARY};
                color: {CyberpunkColors.BACKGROUND};
                font-weight: bold;
            }}
            QLabel {{
                color: {CyberpunkColors.TEXT_LIGHT};
                font-family: 'Rajdhani', sans-serif;
            }}
            QGroupBox {{
                border: 1px solid {CyberpunkColors.PRIMARY};
                border-radius: 5px;
                margin-top: 1ex;
                font-family: 'Rajdhani', sans-serif;
                color: {CyberpunkColors.PRIMARY};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 3px;
            }}
            QScrollArea {{
                border: none;
                background-color: {CyberpunkColors.BACKGROUND};
            }}
            QScrollBar:vertical {{
                background-color: {CyberpunkColors.BACKGROUND};
                width: 12px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {CyberpunkColors.PRIMARY};
                min-height: 20px;
                border-radius: 6px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QLineEdit, QComboBox {{
                background-color: {CyberpunkColors.BACKGROUND};
                color: {CyberpunkColors.TEXT_LIGHT};
                border: 1px solid {CyberpunkColors.PRIMARY};
                border-radius: 3px;
                padding: 5px;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border: none;
            }}
            QComboBox QAbstractItemView {{
                background-color: {CyberpunkColors.BACKGROUND};
                color: {CyberpunkColors.TEXT_LIGHT};
                selection-background-color: {CyberpunkColors.PRIMARY};
                selection-color: {CyberpunkColors.BACKGROUND};
            }}
            QSlider::groove:horizontal {{
                border: 1px solid {CyberpunkColors.PRIMARY};
                height: 4px;
                background: {CyberpunkColors.BACKGROUND};
                margin: 0px;
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: {CyberpunkColors.PRIMARY};
                border: none;
                width: 16px;
                height: 16px;
                margin: -6px 0;
                border-radius: 8px;
            }}
            QCheckBox {{
                color: {CyberpunkColors.TEXT_LIGHT};
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 1px solid {CyberpunkColors.PRIMARY};
                border-radius: 3px;
            }}
            QCheckBox::indicator:checked {{
                background-color: {CyberpunkColors.PRIMARY};
            }}
        """)
        
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Create header
        header_frame = NeonFrame(CyberpunkColors.PRIMARY)
        header_layout = QHBoxLayout(header_frame)
        
        # Logo and title
        logo_label = QLabel("🌙")
        logo_label.setStyleSheet("font-size: 24px;")
        title_label = QLabel("AI CRYPTO TRADING SYSTEM")
        title_label.setStyleSheet(f"""
            color: {CyberpunkColors.PRIMARY};
            font-family: 'Orbitron', sans-serif;
            font-size: 24px;
            font-weight: bold;
        """)
        header_layout.addWidget(logo_label)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        # System status
        self.status_label = QLabel("● SYSTEM ONLINE")
        self.status_label.setStyleSheet(f"""
            color: {CyberpunkColors.SUCCESS};
            font-family: 'Share Tech Mono', monospace;
            font-weight: bold;
        """)
        header_layout.addWidget(self.status_label)
        
        # Add header to main layout
        main_layout.addWidget(header_frame)
        
        # Create content splitter (main content and console)
        content_splitter = QSplitter(Qt.Vertical)
        
        # Main content area
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create tab widget for different sections
        tab_widget = QTabWidget()
        
        # Dashboard tab
        dashboard_widget = QWidget()
        dashboard_layout = QVBoxLayout(dashboard_widget)
        
        # Portfolio visualization
        portfolio_group = QGroupBox("Portfolio Visualization")
        portfolio_layout = QVBoxLayout(portfolio_group)
        self.portfolio_viz = PortfolioVisualization()
        portfolio_layout.addWidget(self.portfolio_viz)
        dashboard_layout.addWidget(portfolio_group)
        
        # Agent status cards
        agent_cards_layout = QHBoxLayout()
        
        # Create agent cards with different colors
        # Create data collection status cards
        self.oi_card = DataStatusCard("Open Interest", CyberpunkColors.PRIMARY)
        self.oi_card.setToolTip("Monitor Open Interest changes across exchanges - indicates market positioning")
        
        self.funding_card = DataStatusCard("Funding Rates", CyberpunkColors.SECONDARY)
        self.funding_card.setToolTip("Track perpetual futures funding rates - indicates market sentiment")
        
        self.chart_card = DataStatusCard("Chart Analysis", CyberpunkColors.TERTIARY)
        self.chart_card.setToolTip("Technical analysis and trend detection - identifies chart patterns")
        
        agent_cards_layout.addWidget(self.oi_card)
        agent_cards_layout.addWidget(self.funding_card)
        agent_cards_layout.addWidget(self.chart_card)
        
        dashboard_layout.addLayout(agent_cards_layout)
        
        # Add dashboard tab
        tab_widget.addTab(dashboard_widget, "Dashboard")
        
        # Configuration tab
        config_widget = QWidget()
        config_layout = QVBoxLayout(config_widget)
        
        # Create configuration editor
        self.config_editor = ConfigEditor(self.config_data)
        self.config_editor.config_saved.connect(self.save_config)
        config_layout.addWidget(self.config_editor)
        
        # Add Data Sources Configuration Group
        data_sources_group = QGroupBox("Data Collection Sources")
        data_sources_layout = QVBoxLayout()
        
        data_sources_layout.addWidget(QLabel("Select which data sources to monitor:"))
        
        self.oi_enabled_checkbox = QCheckBox("Open Interest Data")
        self.oi_enabled_checkbox.setChecked(True)
        self.oi_enabled_checkbox.setToolTip("Monitor Open Interest changes across exchanges")
        
        self.funding_enabled_checkbox = QCheckBox("Funding Rates")
        self.funding_enabled_checkbox.setChecked(True)
        self.funding_enabled_checkbox.setToolTip("Monitor perpetual futures funding rates")
        
        self.chart_enabled_checkbox = QCheckBox("Chart Analysis")
        self.chart_enabled_checkbox.setChecked(True)
        self.chart_enabled_checkbox.setToolTip("Technical analysis and trend detection")
        
        data_sources_layout.addWidget(self.oi_enabled_checkbox)
        data_sources_layout.addWidget(self.funding_enabled_checkbox)
        data_sources_layout.addWidget(self.chart_enabled_checkbox)
        
        # Add save button for data sources
        save_data_sources_btn = NeonButton("Apply Data Sources", CyberpunkColors.SUCCESS)
        save_data_sources_btn.clicked.connect(self.save_data_source_settings)
        data_sources_layout.addWidget(save_data_sources_btn)
        
        data_sources_group.setLayout(data_sources_layout)
        config_layout.addWidget(data_sources_group)
        
        config_layout.addStretch()
        
        # Add configuration tab
        tab_widget.addTab(config_widget, "Configuration")
        
        # Add tabs for each agent
        tab_widget.addTab(QWidget(), "Copybot")
        tab_widget.addTab(QWidget(), "Risk Management")
        tab_widget.addTab(QWidget(), "DCA & Staking")
        tab_widget.addTab(QWidget(), "Chart Analysis")
        
        # Add tab widget to content layout
        content_layout.addWidget(tab_widget)
        
        # Add content widget to splitter
        content_splitter.addWidget(content_widget)
        
        # Console output
        console_group = QGroupBox("System Console")
        console_layout = QVBoxLayout(console_group)
        self.console = ConsoleOutput()
        console_layout.addWidget(self.console)
        
        # Add console to splitter
        content_splitter.addWidget(console_group)
        
        # Set initial splitter sizes
        content_splitter.setSizes([600, 200])
        
        # Add splitter to main layout
        main_layout.addWidget(content_splitter)
        
        # Initialize with sample data
        self.initialize_sample_data()
        
        # Add initial console messages
        self.console.append_message("🌙 Moon Dev AI Agent Trading System Starting...", "system")
        self.console.append_message("📊 Active Agents and their Intervals:", "system")
        self.console.append_message("  • Copybot: ✅ ON (Every 30 minutes)", "info")
        self.console.append_message("  • Risk Management: ✅ ON (Every 10 minutes)", "info")
        self.console.append_message("  • DCA & Staking: ✅ ON (Every 12 hours)", "info")
        self.console.append_message("  • Chart Analysis: ✅ ON (Every 4 hours)", "info")
        self.console.append_message("💓 System heartbeat - All agents running on schedule", "success")
        
        # Setup timer for simulating real-time updates
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.simulate_updates)
        self.update_timer.start(5000)  # Update every 5 seconds
        
        # Connect agent card signals
        self.connect_agent_signals()
        
        # Setup agent threads
        self.setup_agent_threads()
        
        # Setup data update worker for real-time market data
        self.setup_data_worker()
        
        # Initialize strategy runner
        self.strategy_runner = StrategyRunner()
        self.console.append_message("Strategy runner initialized", "info")
        
        # Setup status bar
        self.setup_status_bar()
        
    def setup_status_bar(self):
        """Setup status bar for service states"""
        self.status_bar = self.statusBar()
        self.status_bar.setStyleSheet(f"""
            QStatusBar {{
                background-color: {CyberpunkColors.BACKGROUND};
                color: {CyberpunkColors.TEXT_LIGHT};
                border-top: 1px solid {CyberpunkColors.PRIMARY};
            }}
        """)
        
        self.data_status_label = QLabel("Data Collection: Idle")
        self.data_status_label.setStyleSheet(f"color: {CyberpunkColors.TERTIARY}; padding: 5px;")
        
        self.strategy_status_label = QLabel("Strategy: Idle")
        self.strategy_status_label.setStyleSheet(f"color: {CyberpunkColors.TERTIARY}; padding: 5px;")
        
        self.status_bar.addPermanentWidget(self.data_status_label)
        self.status_bar.addPermanentWidget(self.strategy_status_label)
        
    def setup_data_worker(self):
        """Setup worker thread for monitoring data collection updates"""
        self.data_worker = DataUpdateWorker()
        self.data_thread = QThread()
        self.data_worker.moveToThread(self.data_thread)
        
        # Connect signals
        self.data_worker.data_updated.connect(self.update_data_card)
        self.data_thread.started.connect(self.data_worker.run)
        
        # Don't start automatically - will connect to Redis when data collection is started
        self.console.append_message("Data monitoring initialized (connects when data collection starts)", "info")
    
    def update_data_card(self, data_type: str, data: dict):
        """Update data status card with new data from Redis"""
        # Map data type to card
        card = None
        if data_type == "oi":
            card = self.oi_card
        elif data_type == "funding":
            card = self.funding_card
        elif data_type == "chart" or data_type == "chartanalysis":
            card = self.chart_card
        
        if card:
            card.update_data(data)
    
    def save_data_source_settings(self):
        """Save data source configuration"""
        settings = {
            'oi_enabled': self.oi_enabled_checkbox.isChecked(),
            'funding_enabled': self.funding_enabled_checkbox.isChecked(),
            'chart_enabled': self.chart_enabled_checkbox.isChecked()
        }
        
        # Update card visibility based on settings
        if not settings['oi_enabled']:
            self.oi_card.set_idle()
            self.oi_card.setVisible(False)
        else:
            self.oi_card.setVisible(True)
            
        if not settings['funding_enabled']:
            self.funding_card.set_idle()
            self.funding_card.setVisible(False)
        else:
            self.funding_card.setVisible(True)
            
        if not settings['chart_enabled']:
            self.chart_card.set_idle()
            self.chart_card.setVisible(False)
        else:
            self.chart_card.setVisible(True)
        
        # Save to config file if available
        self.config_data.update(settings)
        
        enabled_sources = [k.replace('_enabled', '').upper() for k, v in settings.items() if v]
        self.console.append_message(f"Data sources updated: {', '.join(enabled_sources)}", "success")
        
    def load_config(self):
        """Load configuration from file"""
        if not self.config_path:
            # Return default config
            return {
                "AI_MODEL": "claude-3-haiku-20240307",
                "AI_MAX_TOKENS": 1024,
                "AI_TEMPERATURE": 70,
                "CASH_PERCENTAGE": 20,
                "MAX_POSITION_PERCENTAGE": 10,
                "MINIMUM_BALANCE_USD": 100,
                "USE_AI_CONFIRMATION": True,
                "STAKING_ALLOCATION_PERCENTAGE": 30,
                "DCA_INTERVAL_MINUTES": 720,
                "TAKE_PROFIT_PERCENTAGE": 200,
                "FIXED_DCA_AMOUNT": 10,
                "SLEEP_BETWEEN_RUNS_MINUTES": 15,
                "CHART_CHECK_INTERVAL_MINUTES": 10,
                "address": "4wgfCBf2WwLSRKLef9iW7JXZ2AfkxUxGM4XcKpHm3Sin",
                "symbol": "9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump"
            }
        
        try:
            # Try to import config module
            spec = importlib.util.spec_from_file_location("config", self.config_path)
            config_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(config_module)
            
            # Extract configuration variables
            config = {}
            for key in dir(config_module):
                if not key.startswith("__") and not key.startswith("_"):
                    config[key] = getattr(config_module, key)
            
            return config
        except Exception as e:
            self.console.append_message(f"Error loading configuration: {str(e)}", "error")
            return {}
    
    def setup_menu_bar(self):
        """Setup application menu bar"""
        menubar = self.menuBar()
        menubar.setStyleSheet(f"""
            QMenuBar {{
                background-color: {CyberpunkColors.BACKGROUND};
                color: {CyberpunkColors.TEXT_LIGHT};
                border-bottom: 1px solid {CyberpunkColors.PRIMARY};
            }}
            QMenuBar::item {{
                background-color: transparent;
                padding: 5px 10px;
            }}
            QMenuBar::item:selected {{
                background-color: {CyberpunkColors.PRIMARY};
                color: {CyberpunkColors.BACKGROUND};
            }}
            QMenu {{
                background-color: {CyberpunkColors.BACKGROUND};
                color: {CyberpunkColors.TEXT_LIGHT};
                border: 1px solid {CyberpunkColors.PRIMARY};
            }}
            QMenu::item:selected {{
                background-color: {CyberpunkColors.PRIMARY};
                color: {CyberpunkColors.BACKGROUND};
            }}
        """)
        
        # File menu
        file_menu = menubar.addMenu('File')
        exit_action = file_menu.addAction('Exit')
        exit_action.triggered.connect(self.close)
        
        # Data Collection menu
        data_menu = menubar.addMenu('Data Collection')
        self.start_data_action = data_menu.addAction('Start Data Collection')
        self.stop_data_action = data_menu.addAction('Stop Data Collection')
        self.start_data_action.triggered.connect(self.start_data_collection)
        self.stop_data_action.triggered.connect(self.stop_data_collection)
        self.stop_data_action.setEnabled(False)
        
        # Strategy menu
        strategy_menu = menubar.addMenu('Strategy')
        self.run_pattern_action = strategy_menu.addAction('Run Pattern Detection')
        self.stop_strategy_action = strategy_menu.addAction('Stop Strategy')
        self.run_pattern_action.triggered.connect(self.run_pattern_strategy)
        self.stop_strategy_action.triggered.connect(self.stop_strategy)
        self.stop_strategy_action.setEnabled(False)
    
    def start_data_collection(self):
        """Start data collection service and monitoring"""
        import subprocess
        
        self.console.append_message("Starting data collection service...", "system")
        
        # Start data.py as subprocess
        data_script = Path(__file__).parent / "data.py"
        
        if not data_script.exists():
            self.console.append_message(f"Error: data.py not found at {data_script}", "error")
            return
        
        try:
            self.data_process = subprocess.Popen(
                [sys.executable, str(data_script)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            self.console.append_message(f"Data collection service started (PID: {self.data_process.pid})", "success")
        except Exception as e:
            self.console.append_message(f"Failed to start data.py: {e}", "error")
            return
        
        # Start the data worker thread if not already running
        if not self.data_thread.isRunning():
            self.data_thread.start()
            self.console.append_message("Data monitoring thread started - connecting to Redis", "success")

        # Update menu states
        self.start_data_action.setEnabled(False)
        self.stop_data_action.setEnabled(True)

        # Update data cards to show they're ready
        self.oi_card.set_idle()
        self.funding_card.set_idle()
        self.chart_card.set_idle()

        # Update status bar
        self.data_status_label.setText("Data Collection: Running")
        self.data_status_label.setStyleSheet(f"color: {CyberpunkColors.SUCCESS}; padding: 5px;")

        self.console.append_message("Data collection active - monitoring for updates", "info")
    
    def stop_data_collection(self):
        """Stop data collection service"""
        self.console.append_message("Stopping data collection service...", "warning")
        
        # Stop the data.py subprocess
        if hasattr(self, 'data_process') and self.data_process:
            try:
                self.data_process.terminate()
                self.data_process.wait(timeout=5)
                self.console.append_message("Data collection service stopped", "info")
            except Exception as e:
                self.console.append_message(f"Error stopping data.py: {e}", "error")
        
        # Stop the data worker
        if hasattr(self, 'data_worker'):
            self.data_worker.stop()
        
        # Update menu states
        self.start_data_action.setEnabled(True)
        self.stop_data_action.setEnabled(False)
        
        # Update status bar
        self.data_status_label.setText("Data Collection: Idle")
        self.data_status_label.setStyleSheet(f"color: {CyberpunkColors.TERTIARY}; padding: 5px;")
        
        self.console.append_message("Data monitoring stopped", "info")
    
    def run_pattern_strategy(self):
        """Run pattern detection strategy"""
        self.console.append_message("Starting Pattern Detection strategy...", "system")
        
        # Build configuration from settings
        symbols_str = self.config_data.get('TRADING_SYMBOLS', 'BTCUSDT,ETHUSDT,SOLUSDT')
        symbols = [s.strip() for s in symbols_str.split(',')]
        
        config = {
            'symbols': symbols,
            'scan_interval': int(self.config_data.get('SCAN_INTERVAL', 300)),
            'timeframe': self.config_data.get('TIMEFRAME', '1d')
        }
        
        # Start strategy
        success, message = self.strategy_runner.start_pattern_detection(config)
        
        if success:
            self.console.append_message(message, "success")
            self.run_pattern_action.setEnabled(False)
            self.stop_strategy_action.setEnabled(True)
            
            # Update status bar
            self.strategy_status_label.setText("Strategy: Pattern Detection Running")
            self.strategy_status_label.setStyleSheet(f"color: {CyberpunkColors.SUCCESS}; padding: 5px;")
            
            # Connect pattern detection signal to AI analysis console
            active_strategy = self.strategy_runner.get_active_strategy()
            if active_strategy and hasattr(active_strategy, 'pattern_detected'):
                active_strategy.pattern_detected.connect(self.portfolio_viz.display_pattern_analysis)
                self.console.append_message("AI Analysis routing connected", "info")
        else:
            self.console.append_message(message, "error")
    
    def stop_strategy(self):
        """Stop active strategy"""
        self.console.append_message("Stopping strategy...", "warning")
        
        success, message = self.strategy_runner.stop_strategy()
        
        msg_type = "success" if success else "warning"
        self.console.append_message(message, msg_type)
        
        # Update status bar
        self.strategy_status_label.setText("Strategy: Idle")
        self.strategy_status_label.setStyleSheet(f"color: {CyberpunkColors.TERTIARY}; padding: 5px;")
        
        # Update menu states
        self.run_pattern_action.setEnabled(True)
        self.stop_strategy_action.setEnabled(False)
    
    def save_config(self, config_data):
        """Save configuration to file"""
        if not self.config_path:
            self.console.append_message("No configuration file specified", "warning")
            return
        
        try:
            # Create backup of original config
            backup_path = self.config_path + ".bak"
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as src, open(backup_path, 'w') as dst:
                    dst.write(src.read())
            
            # Write new config
            with open(self.config_path, 'w') as f:
                f.write("# AI Trading System Configuration\n")
                f.write("# Generated by Cyberpunk UI\n\n")
                
                for key, value in config_data.items():
                    if isinstance(value, str):
                        f.write(f'{key} = "{value}"\n')
                    else:
                        f.write(f'{key} = {value}\n')
            
            self.console.append_message("Configuration saved successfully", "success")
            
            # Update local config data
            self.config_data = config_data
            
        except Exception as e:
            self.console.append_message(f"Error saving configuration: {str(e)}", "error")
    
    def initialize_sample_data(self):
        """Initialize with sample data"""
        # Sample portfolio data
        sample_tokens = [
            {"name": "SOL", "allocation": 0.35, "performance": 0.12, "volatility": 0.08},
            {"name": "BONK", "allocation": 0.15, "performance": 0.25, "volatility": 0.15},
            {"name": "JTO", "allocation": 0.20, "performance": -0.05, "volatility": 0.10},
            {"name": "PYTH", "allocation": 0.10, "performance": 0.08, "volatility": 0.05},
            {"name": "USDC", "allocation": 0.20, "performance": 0.0, "volatility": 0.01}
        ]
        self.portfolio_viz.set_portfolio_data(sample_tokens)
    
    def simulate_updates(self):
        """Simulate real-time updates"""
        # Simulate console updates
        messages = [
            ("💓 System heartbeat - All agents running on schedule", "success"),
            ("📊 Checking market conditions...", "info"),
            ("💰 Current portfolio balance: $1,245.67", "info"),
            ("🤖 CopyBot analyzing wallet 0x123...456", "info"),
            ("⚠️ Risk threshold approaching for JTO position", "warning"),
            ("✅ DCA purchase complete: Bought 0.25 SOL", "success")
        ]
        
        # Add a random message to console
        message, msg_type = random.choice(messages)
        self.console.append_message(message, msg_type)
        
        # Portfolio simulation removed - now using AI analysis console instead
        # The portfolio visualization area is now used for displaying AI pattern analysis
    
    def connect_agent_signals(self):
        """Connect signals for agent cards"""
        # Data collection cards don't need button connections
        # They are controlled via menu actions
    
    def setup_agent_threads(self):
        """Setup threads for running agents"""
        self.agent_threads = {}
        self.agent_workers = {}
        
        if self.src_path:
            agent_paths = {
                "copybot": os.path.join(self.src_path, "agents", "copybot_agent.py"),
                "risk": os.path.join(self.src_path, "agents", "risk_agent.py"),
                "dca_staking": os.path.join(self.src_path, "agents", "dca_staking_agent.py"),
                "chart_analysis": os.path.join(self.src_path, "agents", "chartanalysis_agent.py")
            }
            
            for agent_name, agent_path in agent_paths.items():
                if os.path.exists(agent_path):
                    # Create worker
                    worker = AgentWorker(agent_name, agent_path)
                    
                    # Create thread
                    thread = QThread()
                    worker.moveToThread(thread)
                    
                    # Connect signals
                    thread.started.connect(worker.run)
                    worker.status_update.connect(self.update_agent_status)
                    worker.console_message.connect(self.console.append_message)
                    worker.portfolio_update.connect(self.portfolio_viz.set_portfolio_data)
                    
                    # Store worker and thread
                    self.agent_workers[agent_name] = worker
                    self.agent_threads[agent_name] = thread
    
    def start_agent(self, agent_name):
        """Start an agent"""
        if agent_name in self.agent_threads:
            thread = self.agent_threads[agent_name]
            if not thread.isRunning():
                thread.start()
        else:
            # Fallback to simulated agent
            self.console.append_message(f"Starting {agent_name} (simulated)...", "system")
            
            # Update agent card
            card = getattr(self, f"{agent_name.lower().replace('_', '')}_card", None)
            if card:
                card.start_agent()
    
    def stop_agent(self, agent_name):
        """Stop an agent"""
        if agent_name in self.agent_workers:
            worker = self.agent_workers[agent_name]
            worker.stop()
            
            # Wait for thread to finish
            thread = self.agent_threads[agent_name]
            if thread.isRunning():
                thread.quit()
                thread.wait()
        else:
            # Fallback to simulated agent
            self.console.append_message(f"Stopping {agent_name} (simulated)...", "warning")
            
            # Update agent card
            card = getattr(self, f"{agent_name.lower().replace('_', '')}_card", None)
            if card:
                card.stop_agent()
    
    def update_agent_status(self, agent_name, status_data):
        """Update agent status card"""
        # Map data collection agent names to cards
        card = None
        if agent_name == "oi":
            card = self.oi_card
        elif agent_name == "funding":
            card = self.funding_card
        elif agent_name == "chartanalysis" or agent_name == "chart_analysis":
            card = self.chart_card
        
        if card:
            card.update_status(status_data)
    
    def closeEvent(self, event):
        """Handle window close event"""
        # Stop all agent threads
        for agent_name in self.agent_threads:
            self.stop_agent(agent_name)
        
        # Accept the close event
        event.accept()

def main():
    app = QApplication(sys.argv)
    
    # Parse command line arguments
    config_path = None
    src_path = None
    
    if len(sys.argv) > 1:
        for i, arg in enumerate(sys.argv[1:]):
            if arg == "--config" and i+1 < len(sys.argv)-1:
                config_path = sys.argv[i+2]
            elif arg == "--src" and i+1 < len(sys.argv)-1:
                src_path = sys.argv[i+2]
    
    # Try to find config.py and src directory if not specified
    if not config_path or not src_path:
        # Look in current directory
        if os.path.exists("config.py"):
            config_path = os.path.abspath("config.py")
        
        if os.path.exists("src"):
            src_path = os.path.abspath("src")
        
        # Look in parent directory
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if not config_path and os.path.exists(os.path.join(parent_dir, "config.py")):
            config_path = os.path.join(parent_dir, "config.py")
        
        if not src_path and os.path.exists(os.path.join(parent_dir, "src")):
            src_path = os.path.join(parent_dir, "src")
    
    # Load fonts if available
    try:
        import matplotlib.font_manager as fm
        # Try to find and load cyberpunk-style fonts
        for font_file in ["Rajdhani-Regular.ttf", "ShareTechMono-Regular.ttf", "Orbitron-Regular.ttf"]:
            try:
                font_path = fm.findfont(font_file)
                if font_path:
                    QFont(font_path).family()
            except:
                pass
    except ImportError:
        pass
    
    window = MainWindow(config_path, src_path)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
