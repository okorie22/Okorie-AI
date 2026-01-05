import sys
import os
import math
import re
import importlib.util
from pathlib import Path
from datetime import datetime, timedelta
import json
import random
import time
import atexit
import signal
import psutil
import shutil
import subprocess

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
        self.setMinimumHeight(32)
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
                font-size: 12px;
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
        self.setMinimumHeight(200)
        self.setStyleSheet(f"""
            QTextEdit {{
                background-color: #0A0A0A;
                color: {CyberpunkColors.TEXT_LIGHT};
                border: 2px solid {CyberpunkColors.TERTIARY};
                font-family: 'Share Tech Mono', monospace;
                padding: 10px;
                font-size: 11px;
            }}
        """)

        # Track if we're waiting for the first pattern
        self.waiting_for_patterns = False

        # Don't automatically show welcome message - let initialization decide

    def initialize_display(self, has_persistent_data=False):
        """Initialize console display based on whether persistent data exists"""
        if has_persistent_data:
            # Show title only for returning users with data
            html = f"""
            <div style="color: {CyberpunkColors.TERTIARY}; text-align: center; padding: 10px;">
                <h2 style="color: {CyberpunkColors.PRIMARY};">AI Analysis Console</h2>
            </div>
            """
            self.setHtml(html)
        else:
            # Show full welcome message for new users
            self.append_welcome_message()
    
    def append_welcome_message(self):
        """Display welcome message"""
        html = f"""
        <div style="color: {CyberpunkColors.TERTIARY}; text-align: center; padding: 20px;">
            <h2 style="color: {CyberpunkColors.PRIMARY};">AI Analysis Console</h2>
            <p>Waiting for strategy to start...</p>
            <p style="color: {CyberpunkColors.TERTIARY}; font-size: 11px;">
                Use Menu → Strategy → Run Strategy to begin
            </p>
        </div>
        """
        self.setHtml(html)
    
    def show_running_message(self, symbols, scan_interval, timeframe):
        """Display message when pattern detection is running"""
        # Check if we already have patterns displayed (returning user)
        current_html = self.toHtml()
        has_patterns = 'PATTERN DETECTED:' in current_html
        
        # If patterns are already displayed, don't overwrite - just update the flag
        if has_patterns:
            self.waiting_for_patterns = False
            return  # Don't overwrite existing patterns
        
        # Only show running message for new users without patterns
        timestamp = datetime.now().strftime("%H:%M:%S")
        symbols_str = ", ".join(symbols)
        interval_min = scan_interval // 60
        interval_sec = scan_interval % 60
        interval_str = f"{interval_min}m {interval_sec}s" if interval_min > 0 else f"{interval_sec}s"
        
        html = f"""
        <div style="color: {CyberpunkColors.SUCCESS}; text-align: center; padding: 15px;">
            <h2 style="color: {CyberpunkColors.PRIMARY}; font-size: 16px;">AI Analysis Console</h2>
            <p style="color: {CyberpunkColors.SUCCESS}; font-size: 12px; font-weight: bold;">
                ✅ Pattern Detection Active
            </p>
            <p style="color: {CyberpunkColors.TEXT_LIGHT}; margin-top: 8px; font-size: 10px;">
                Monitoring: <strong style="color: {CyberpunkColors.PRIMARY};">{symbols_str}</strong>
            </p>
            <p style="color: {CyberpunkColors.TEXT_LIGHT}; font-size: 10px;">
                Scan Interval: <strong style="color: {CyberpunkColors.PRIMARY};">{interval_str}</strong> | 
                Timeframe: <strong style="color: {CyberpunkColors.PRIMARY};">{timeframe}</strong>
            </p>
            <p style="color: {CyberpunkColors.TERTIARY}; font-size: 9px; margin-top: 10px;">
                Waiting for patterns to be detected...
            </p>
        </div>
        """
        self.setHtml(html)
        # Set flag to indicate we're waiting for the first pattern
        self.waiting_for_patterns = True
        
    def display_pattern_analysis(self, pattern_data):
        """Display a detected pattern with AI analysis"""
        # If this is the first pattern, clear the waiting message
        if self.waiting_for_patterns:
            self.clear()
            self.waiting_for_patterns = False
        
        # Use timestamp from pattern_data if available, otherwise use current time
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Default to current time with date
        
        if 'timestamp' in pattern_data and pattern_data['timestamp']:
            # Parse the timestamp - it might be a string or datetime
            timestamp_str = pattern_data['timestamp']
            try:
                if isinstance(timestamp_str, str):
                    # Try parsing ISO format first (most common from database)
                    if 'T' in timestamp_str:
                        # ISO format: "2024-01-01T20:38:21" or "2024-01-01T20:38:21.123456"
                        try:
                            # Handle with or without microseconds
                            if '.' in timestamp_str:
                                dt = datetime.strptime(timestamp_str.split('.')[0], "%Y-%m-%dT%H:%M:%S")
                            else:
                                dt = datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S")
                            timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
                        except ValueError:
                            # Try fromisoformat as fallback (Python 3.7+)
                            try:
                                dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00').split('.')[0])
                                timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
                            except:
                                print(f"[DEBUG] Failed to parse ISO timestamp: {timestamp_str}")
                    else:
                        # Try other formats like "YYYY-MM-DD HH:MM:SS"
                        try:
                            dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                            timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
                        except ValueError:
                            print(f"[DEBUG] Failed to parse timestamp format: {timestamp_str}")
                elif isinstance(timestamp_str, datetime):
                    timestamp = timestamp_str.strftime("%Y-%m-%d %H:%M:%S")
            except Exception as e:
                print(f"[DEBUG] Error parsing timestamp {timestamp_str}: {e}")
                # Keep default current time
        
        html = f"""
        <div style="border-left: 3px solid {CyberpunkColors.SUCCESS}; padding-left: 10px; margin: 10px 0;">
            <div style="color: {CyberpunkColors.SUCCESS}; font-weight: bold; font-size: 12px;">
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
        # Insert at the beginning (after title) instead of appending to show newest first
        current_html = self.toHtml()
        if 'AI Analysis Console' in current_html:
            # Find where to insert (after the title div)
            title_end = current_html.find('</div>', current_html.find('AI Analysis Console'))
            if title_end != -1:
                insert_pos = current_html.find('>', title_end) + 1
                new_html = current_html[:insert_pos] + html + current_html[insert_pos:]
                self.setHtml(new_html)
            else:
                self.append(html)
        else:
            self.append(html)
        
        # Auto-scroll to top to show newest pattern
        self.verticalScrollBar().setValue(0)
        
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
                        
        except (IOError, OSError) as e:
            # Handle "I/O operation on closed file" gracefully
            if self.running:
                print(f"[DATA WORKER] Redis connection closed: {e}")
            # If we're stopping, this is expected
        except Exception as e:
            print(f"[DATA WORKER] Error in subscriber loop: {e}")
        finally:
            if self.pubsub:
                try:
                    self.pubsub.close()
                except:
                    pass  # Already closed
    
    def stop(self):
        """Stop the worker"""
        self.running = False
        if self.pubsub:
            try:
                # Unsubscribe from all channels first to stop the listen loop
                self.pubsub.unsubscribe()
                # Give it a moment to process the unsubscribe
                time.sleep(0.1)
            except Exception as e:
                print(f"[DATA WORKER] Error unsubscribing: {e}")
            finally:
                try:
                    self.pubsub.close()
                except Exception as e:
                    print(f"[DATA WORKER] Error closing pubsub: {e}")
        
        if self.redis_client:
            try:
                self.redis_client.close()
            except Exception as e:
                print(f"[DATA WORKER] Error closing redis client: {e}")

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
        
        # Key metrics display
        metrics_layout = QVBoxLayout()
        metrics_layout.addWidget(QLabel("Alerts:"))
        self.metrics_label = QLabel("--")
        self.metrics_label.setWordWrap(True)
        self.metrics_label.setStyleSheet(f"""
            QLabel {{
                color: {CyberpunkColors.PRIMARY};
                font-family: 'Share Tech Mono', monospace;
                font-size: 10px;
                padding: 3px;
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
        # Update status based on data
        status = data.get('status', 'active')
        if status == 'active':
            self.status_label.setText("Active")
            self.status_label.setStyleSheet(f"color: {CyberpunkColors.SUCCESS};")
        elif status == 'error':
            self.status_label.setText("Error")
            self.status_label.setStyleSheet(f"color: {CyberpunkColors.DANGER};")
        else:
            self.status_label.setText("Collecting")
            self.status_label.setStyleSheet(f"color: {CyberpunkColors.SUCCESS};")
        
        # Update metrics based on data type
        if self.data_type == "Open Interest":
            alerts = data.get('alerts', '')
            if alerts and alerts != "No alerts" and alerts.strip():
                # Parse alerts and find the one with highest absolute change
                alert_lines = alerts.split('\n')
                parsed_alerts = []
                
                for alert in alert_lines:
                    if alert.strip():  # Only process non-empty lines
                        # Format: "ADA: -15.4%" or "DOGE: 78.5%"
                        if ':' in alert:
                            parts = alert.split(':')
                            if len(parts) == 2:
                                symbol = parts[0].strip()
                                percentage_str = parts[1].strip()
                                # Extract percentage value (remove % sign)
                                try:
                                    percentage = float(percentage_str.replace('%', '').strip())
                                    parsed_alerts.append({
                                        'symbol': symbol,
                                        'percentage': percentage,
                                        'original': alert.strip()
                                    })
                                except ValueError:
                                    continue
                
                # Find alert with highest absolute percentage change
                if parsed_alerts:
                    max_alert = max(parsed_alerts, key=lambda x: abs(x['percentage']))
                    # Format as "SYMBOL X.XX%"
                    metrics_text = f"{max_alert['symbol']} {max_alert['percentage']:+.2f}%"
                else:
                    metrics_text = "NO ALERTS"
            else:
                metrics_text = "NO ALERTS"
            self.metrics_label.setText(metrics_text)
        elif self.data_type == "Funding Rates":
            alerts = data.get('alerts', '')
            if alerts and alerts != "No alerts" and alerts.strip():
                # Parse alerts - format is "MID-RANGE: SUSHI (-2.93%)" or "EXTREME: BTC (5.0%)"
                # Find the one with highest absolute change
                alert_lines = alerts.split('\n')
                parsed_alerts = []
                
                for alert in alert_lines:
                    if alert.strip():  # Only process non-empty lines
                        # Format: "MID-RANGE: SUSHI (-2.93%)" or "EXTREME: BTC (5.0%)"
                        # Remove category prefix (MID-RANGE: or EXTREME:)
                        alert_clean = alert.strip()
                        if ':' in alert_clean:
                            # Split on first colon to remove category
                            parts = alert_clean.split(':', 1)
                            if len(parts) == 2:
                                # parts[1] should be " SUSHI (-2.93%)" or " BTC (5.0%)"
                                rest = parts[1].strip()
                                # Extract symbol and percentage
                                # Look for pattern: "SYMBOL (X.XX%)"
                                match = re.match(r'([A-Z0-9]+)\s*\(([-+]?\d+\.?\d*)%\)', rest)
                                if match:
                                    symbol = match.group(1)
                                    percentage = float(match.group(2))
                                    parsed_alerts.append({
                                        'symbol': symbol,
                                        'percentage': percentage,
                                        'original': alert.strip()
                                    })
                
                # Find alert with highest absolute percentage change
                if parsed_alerts:
                    max_alert = max(parsed_alerts, key=lambda x: abs(x['percentage']))
                    # Format as "SYMBOL X.XX%" (no category prefix, no parentheses)
                    metrics_text = f"{max_alert['symbol']} {max_alert['percentage']:+.2f}%"
                else:
                    metrics_text = "NO ALERTS"
            else:
                metrics_text = "NO ALERTS"
            self.metrics_label.setText(metrics_text)
        elif self.data_type == "Market Sentiment":
            # Only update if sentiment key exists in data (prevents wrong data type from overwriting)
            if 'sentiment' in data:
                sentiment = data.get('sentiment', '--')
                if sentiment and sentiment != '--' and sentiment != "Analyzing..." and sentiment is not None:
                    # Show only the sentiment value (BULLISH, BEARISH, NEUTRAL, etc.)
                    metrics_text = sentiment.upper()
                elif sentiment == "Analyzing...":
                    metrics_text = "Analyzing..."
                else:
                    metrics_text = "No data"
                self.metrics_label.setText(metrics_text)
            # If 'sentiment' key doesn't exist, don't update metrics (preserve existing)
            # Status and timestamp are already updated above, so just skip metrics update
            else:
                return  # Skip metrics update, preserve existing metrics
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

        # Add System Autorun Settings Group
        autorun_group = QGroupBox("System Autorun")
        autorun_layout = QVBoxLayout()

        autorun_layout.addWidget(QLabel("Automatically start the complete trading system on application launch:"))

        # Single autorun checkbox for entire system
        self.autorun_system_cb = QCheckBox("Auto-start Trading System")
        self.autorun_system_cb.setChecked(False)
        self.autorun_system_cb.setToolTip("Automatically start both data collection and pattern detection when app launches")

        autorun_layout.addWidget(self.autorun_system_cb)

        # Apply button for autorun settings
        apply_autorun_btn = NeonButton("Apply Autorun Settings", CyberpunkColors.SUCCESS)
        apply_autorun_btn.clicked.connect(self.save_autorun_settings)
        autorun_layout.addWidget(apply_autorun_btn)

        autorun_group.setLayout(autorun_layout)
        layout.addWidget(autorun_group)
        
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

    def save_autorun_settings(self):
        """Save autorun settings"""
        settings = {
            'autorun_system': self.autorun_system_cb.isChecked()
        }

        # Update parent window attributes
        self.parent().autorun_system = settings['autorun_system']

        # Save to config if available
        if hasattr(self.parent(), 'config_data'):
            self.parent().config_data.update(settings)

        # Immediately save to persistence file
        self.parent().persistence_manager.save_state()
        
        # Debug: Verify it was saved
        saved_state = self.parent().persistence_manager.load_state()
        if saved_state and "autorun_settings" in saved_state:
            print(f"[AUTORUN] ConfigEditor: Verified saved: {saved_state['autorun_settings']}")
        else:
            print(f"[AUTORUN] ConfigEditor: WARNING: Autorun setting not found in saved state!")

        self.parent().console.append_message("System autorun settings saved", "success")


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
            if self.agent_name == "chart_analysis":
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


class AppPersistenceManager:
    """Manages saving and loading application state between sessions"""

    def __init__(self, app_dir, parent=None):
        self.app_dir = Path(app_dir)
        self.parent = parent
        self.state_file = self.app_dir / "app_state.json"
        self.backup_file = self.app_dir / "app_state.backup.json"
        self.auto_save_timer = None

        # Ensure directory exists
        self.app_dir.mkdir(exist_ok=True)

        # Setup periodic auto-save
        self.setup_auto_save()

    def setup_auto_save(self):
        """Setup periodic auto-save functionality"""
        self.auto_save_timer = QTimer()
        self.auto_save_timer.timeout.connect(self.save_state)
        self.auto_save_timer.start(30000)  # Auto-save every 30 seconds

    def save_state(self):
        """Save current application state"""
        try:
            state = {
                "timestamp": datetime.now().isoformat(),
                "ui_state": self.get_ui_state(),
                "settings": self.get_settings_state(),
                "data_alerts": self.get_data_alerts_state(),
                "autorun_settings": self.get_autorun_settings()
            }

            # Create backup of existing state
            if self.state_file.exists():
                shutil.copy2(self.state_file, self.backup_file)

            # Save new state
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2, default=str)

        except Exception as e:
            print(f"[PERSISTENCE] Error saving state: {e}")

    def load_state(self):
        """Load saved application state"""
        if not self.state_file.exists():
            print(f"[PERSISTENCE] State file does not exist: {self.state_file}")
            return {}

        try:
            with open(self.state_file, 'r') as f:
                state = json.load(f)
                # Debug: Show autorun settings if present
                if "autorun_settings" in state:
                    pass
                else:
                    pass
                return state
        except Exception as e:
            print(f"[PERSISTENCE] Error loading state: {e}")
            # Try loading backup
            if self.backup_file.exists():
                try:
                    with open(self.backup_file, 'r') as f:
                        return json.load(f)
                except:
                    pass
            return {}

    def get_ui_state(self):
        """Get current UI state"""
        if not self.parent:
            return {}

        state = {
            "window_geometry": {
                "x": self.parent.x(),
                "y": self.parent.y(),
                "width": self.parent.width(),
                "height": self.parent.height()
            }
        }

        # Safely get splitter sizes
        if hasattr(self.parent, 'content_splitter'):
            state["splitter_sizes"] = self.parent.content_splitter.sizes()

        # Safely get selected tab
        if hasattr(self.parent, 'tab_widget'):
            state["selected_tab"] = self.parent.tab_widget.currentIndex()

        # Safely get console visibility
        if hasattr(self.parent, 'console_group'):
            state["console_visible"] = not self.parent.console_group.isHidden()

        return state

    def get_settings_state(self):
        """Get current settings state"""
        if not self.parent:
            return {}

        return {
            "oi_enabled": self.parent.oi_enabled_checkbox.isChecked(),
            "funding_enabled": self.parent.funding_enabled_checkbox.isChecked(),
            "chart_enabled": self.parent.chart_enabled_checkbox.isChecked(),
            "trading_symbols": getattr(self.parent.config_data, 'TRADING_SYMBOLS', 'BTCUSDT,ETHUSDT,SOLUSDT'),
            "scan_interval": getattr(self.parent.config_data, 'SCAN_INTERVAL', 300),
            "timeframe": getattr(self.parent.config_data, 'TIMEFRAME', '1d')
        }

    def get_data_alerts_state(self):
        """Get current data alerts state"""
        if not self.parent:
            return {}

        return {
            "oi_alerts": self.parent.oi_card.metrics_label.text(),
            "funding_alerts": self.parent.funding_card.metrics_label.text(),
            "sentiment_data": self.parent.chart_card.metrics_label.text(),
            "oi_status": self.parent.oi_card.status_label.text(),
            "funding_status": self.parent.funding_card.status_label.text(),
            "sentiment_status": self.parent.chart_card.status_label.text()
        }

    def get_autorun_settings(self):
        """Get autorun settings"""
        if not self.parent:
            return {}

        return {
            "autorun_system": getattr(self.parent, 'autorun_system', False)
        }

    def restore_ui_state(self, state):
        """Restore UI state"""
        if not self.parent or "ui_state" not in state:
            return

        ui_state = state["ui_state"]

        # Restore window geometry
        if "window_geometry" in ui_state:
            geom = ui_state["window_geometry"]
            self.parent.setGeometry(geom["x"], geom["y"], geom["width"], geom["height"])

        # Restore splitter sizes
        if "splitter_sizes" in ui_state and hasattr(self.parent, 'content_splitter'):
            self.parent.content_splitter.setSizes(ui_state["splitter_sizes"])

        # Restore selected tab
        if "selected_tab" in ui_state and hasattr(self.parent, 'tab_widget'):
            self.parent.tab_widget.setCurrentIndex(ui_state["selected_tab"])

    def restore_settings_state(self, state):
        """Restore settings state"""
        if not self.parent or "settings" not in state:
            return

        settings = state["settings"]

        # Restore checkboxes (only if they exist)
        if "oi_enabled" in settings and hasattr(self.parent, 'oi_enabled_checkbox'):
            self.parent.oi_enabled_checkbox.setChecked(settings["oi_enabled"])
        if "funding_enabled" in settings and hasattr(self.parent, 'funding_enabled_checkbox'):
            self.parent.funding_enabled_checkbox.setChecked(settings["funding_enabled"])
        if "chart_enabled" in settings and hasattr(self.parent, 'chart_enabled_checkbox'):
            self.parent.chart_enabled_checkbox.setChecked(settings["chart_enabled"])

    def restore_data_alerts_state(self, state):
        """Restore data alerts state"""
        if not self.parent or "data_alerts" not in state:
            return

        alerts = state["data_alerts"]

        # Restore metrics (only if no real data is available and cards exist)
        if alerts.get("oi_alerts") and hasattr(self.parent, 'oi_card'):
            if self.parent.oi_card.status_label.text() == "Idle":
                self.parent.oi_card.metrics_label.setText(alerts["oi_alerts"])
        if alerts.get("funding_alerts") and hasattr(self.parent, 'funding_card'):
            if self.parent.funding_card.status_label.text() == "Idle":
                self.parent.funding_card.metrics_label.setText(alerts["funding_alerts"])
        if alerts.get("sentiment_data") and hasattr(self.parent, 'chart_card'):
            if self.parent.chart_card.status_label.text() == "Idle":
                self.parent.chart_card.metrics_label.setText(alerts["sentiment_data"])

    def load_recent_patterns(self, limit=50):
        """Load recent patterns for display"""
        try:
            # Import pattern storage
            pattern_detector_path = Path(__file__).parent / "pattern-detector"
            sys.path.insert(0, str(pattern_detector_path))
            
            from pattern_storage import PatternStorage

            storage = PatternStorage()
            print(f"[PERSISTENCE] PatternStorage initialized, database path: {storage.db_path}")
            
            recent_patterns = storage.get_recent_patterns(limit=limit)
            
            print(f"[PERSISTENCE] Retrieved {len(recent_patterns) if recent_patterns else 0} patterns from database")

            # Display patterns in console
            if recent_patterns and len(recent_patterns) > 0:
                print(f"[PERSISTENCE] Displaying {len(recent_patterns)} patterns in console")
                # Clear console and show title for returning users
                html = f"""
                <div style="color: {CyberpunkColors.TERTIARY}; text-align: center; padding: 10px;">
                    <h2 style="color: {CyberpunkColors.PRIMARY};">AI Analysis Console</h2>
                </div>
                """
                self.parent.portfolio_viz.setHtml(html)

                # Display patterns (most recent first)
                for pattern in recent_patterns[:10]:  # Get first 10 (newest), iterate in order
                    # Prefer created_at if timestamp has no time info (00:00:00)
                    timestamp_value = pattern.get('timestamp')
                    created_at_value = pattern.get('created_at')
                    
                    # If timestamp has no meaningful time (00:00:00), use created_at instead
                    if timestamp_value and isinstance(timestamp_value, str):
                        if timestamp_value.endswith('T00:00:00') or 'T00:00:00' in timestamp_value:
                            # Timestamp has no time info, use created_at
                            timestamp_value = created_at_value
                    
                    # Fallback to created_at if timestamp is not available
                    if not timestamp_value:
                        timestamp_value = created_at_value
                    
                    pattern_data = {
                        'pattern_type': pattern['pattern'],
                        'symbol': pattern['symbol'],
                        'timeframe': getattr(self.parent.config_data, 'TIMEFRAME', '1d'),
                        'ai_analysis': pattern.get('ai_analysis', 'Analysis not available'),
                        'recommendation': f"Pattern: {pattern['pattern']} (Confidence: {pattern['confidence']:.2f})",
                        'timestamp': timestamp_value  # Use created_at if timestamp has no time info
                    }
                    self.parent.portfolio_viz.display_pattern_analysis(pattern_data)

                # Only append console message if console exists (it may not be initialized yet)
                if hasattr(self.parent, 'console'):
                    self.parent.console.append_message(f"Loaded {len(recent_patterns)} recent patterns from previous session", "info")
                return True  # Indicate patterns were loaded
            else:
                print(f"[PERSISTENCE] No patterns found in database (returned empty list or None)")

        except ImportError as e:
            print(f"[PERSISTENCE] Import error loading recent patterns: {e}")
            print(f"[PERSISTENCE] Pattern detector path: {Path(__file__).parent / 'pattern-detector'}")
            import traceback
            traceback.print_exc()
            return False
        except Exception as e:
            print(f"[PERSISTENCE] Error loading recent patterns: {e}")
            import traceback
            traceback.print_exc()
            return False  # Indicate no patterns loaded

        return False  # No patterns found


class ProcessManager:
    """Manages subprocess lifecycle and cleanup"""

    def __init__(self):
        self.processes = {}
        self.log_files = {}
        self.cleanup_registered = False

    def register_process(self, name, process, stdout_file=None, stderr_file=None):
        """Register a subprocess for management"""
        self.processes[name] = {
            'process': process,
            'pid': process.pid,
            'start_time': datetime.now(),
            'stdout_file': stdout_file,
            'stderr_file': stderr_file
        }

        self.log_files[name] = {
            'stdout': stdout_file,
            'stderr': stderr_file
        }

        # Register cleanup if not already done
        if not self.cleanup_registered:
            atexit.register(self.cleanup_all_processes)
            signal.signal(signal.SIGTERM, self.signal_handler)
            signal.signal(signal.SIGINT, self.signal_handler)
            self.cleanup_registered = True

        print(f"[PROCESS MANAGER] Registered process '{name}' with PID {process.pid}")

    def cleanup_process(self, name):
        """Clean up a specific process"""
        if name not in self.processes:
            return

        proc_info = self.processes[name]
        process = proc_info['process']

        try:
            # Check if process is still running
            if process.poll() is None:  # Process is still running
                print(f"[PROCESS MANAGER] Terminating process '{name}' (PID: {process.pid})")

                # Try graceful termination first
                process.terminate()

                # Wait up to 5 seconds for graceful shutdown
                try:
                    process.wait(timeout=5)
                    print(f"[PROCESS MANAGER] Process '{name}' terminated gracefully")
                except subprocess.TimeoutExpired:
                    # Force kill if graceful termination failed
                    print(f"[PROCESS MANAGER] Force killing process '{name}'")
                    process.kill()
                    process.wait()

            # Close log files
            self.close_log_files(name)

            # Clean up process tree (child processes)
            self.cleanup_child_processes(process.pid)

        except Exception as e:
            print(f"[PROCESS MANAGER] Error cleaning up process '{name}': {e}")

        # Remove from tracking
        del self.processes[name]

    def cleanup_child_processes(self, parent_pid):
        """Clean up child processes of a parent PID"""
        try:
            parent = psutil.Process(parent_pid)
            children = parent.children(recursive=True)

            for child in children:
                try:
                    if child.is_running():
                        print(f"[PROCESS MANAGER] Terminating child process PID {child.pid}")
                        child.terminate()

                        # Wait briefly for termination
                        try:
                            child.wait(timeout=2)
                        except psutil.TimeoutExpired:
                            child.kill()

                except psutil.NoSuchProcess:
                    pass  # Process already terminated

        except psutil.NoSuchProcess:
            pass  # Parent process already gone
        except Exception as e:
            print(f"[PROCESS MANAGER] Error cleaning up child processes: {e}")

    def close_log_files(self, name):
        """Close log files for a process"""
        if name not in self.log_files:
            return

        log_info = self.log_files[name]

        # Close stdout file
        if log_info.get('stdout'):
            try:
                log_info['stdout'].close()
                print(f"[PROCESS MANAGER] Closed stdout log for '{name}'")
            except Exception as e:
                print(f"[PROCESS MANAGER] Error closing stdout log for '{name}': {e}")

        # Close stderr file
        if log_info.get('stderr'):
            try:
                log_info['stderr'].close()
                print(f"[PROCESS MANAGER] Closed stderr log for '{name}'")
            except Exception as e:
                print(f"[PROCESS MANAGER] Error closing stderr log for '{name}': {e}")

    def cleanup_all_processes(self):
        """Clean up all registered processes"""
        print("[PROCESS MANAGER] Cleaning up all processes...")

        for name in list(self.processes.keys()):
            self.cleanup_process(name)

        print("[PROCESS MANAGER] Process cleanup completed")

    def signal_handler(self, signum, frame):
        """Handle system signals for cleanup"""
        print(f"[PROCESS MANAGER] Received signal {signum}, cleaning up...")
        self.cleanup_all_processes()
        sys.exit(0)


class MainWindow(QMainWindow):
    def __init__(self, config_path=None, src_path=None):
        super().__init__()
        
        # Store paths
        self.config_path = config_path
        self.src_path = src_path
        
        # Load configuration
        self.config_data = self.load_config()

        # Initialize managers
        self.persistence_manager = AppPersistenceManager(self.src_path or Path(__file__).parent, parent=self)
        self.process_manager = ProcessManager()
        
        # Debug: Check state file location
        state_file = self.persistence_manager.state_file

        # Initialize autorun setting
        self.autorun_system = False

        # Load saved state
        saved_state = self.persistence_manager.load_state()
        if saved_state:
            self.persistence_manager.restore_ui_state(saved_state)
            # Defer settings and data alerts restoration until after UI is created
            self._saved_settings_state = saved_state.get("settings", {})
            self._saved_data_alerts_state = saved_state.get("data_alerts", {})

            # Load recent patterns (will be called after console is initialized)
            self._saved_state_loaded = True

        # Load autorun settings
        if saved_state and "autorun_settings" in saved_state:
            autorun = saved_state["autorun_settings"]
            self.autorun_system = autorun.get("autorun_system", False)
        else:
            # If no saved state or no autorun_settings, default to False
            self.autorun_system = False
        
        # Debug: Log autorun state
        print(f"[AUTORUN] Loaded autorun setting: {self.autorun_system}")

        # Set window properties
        self.setWindowTitle("Anarcho Capital")
        # Set window dimensions to start in compact format (user can still resize)
        # Dimensions: 480px width x 600px height
        self.resize(500, 635)

        # Create menu bar
        self.setup_menu_bar()

        # Update menu action with loaded setting
        if hasattr(self, 'autorun_system_action'):
            self.autorun_system_action.setChecked(self.autorun_system)
        
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
        self.header_frame = NeonFrame(CyberpunkColors.PRIMARY)
        header_frame = self.header_frame
        header_layout = QHBoxLayout(header_frame)
        
        # Logo and title
        logo_label = QLabel("🌙")
        logo_label.setStyleSheet("font-size: 24px;")
        title_label = QLabel("AI ASSISTANT")
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
        self.content_splitter = QSplitter(Qt.Vertical)
        self.content_splitter.setChildrenCollapsible(False)  # Prevent console from being collapsed
        content_splitter = self.content_splitter
        
        # Main content area
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create tab widget for different sections
        self.tab_widget = QTabWidget()
        tab_widget = self.tab_widget  # Keep for backward compatibility
        
        # Dashboard tab
        dashboard_widget = QWidget()
        dashboard_layout = QVBoxLayout(dashboard_widget)
        
        # Portfolio visualization
        portfolio_group = QGroupBox("Console")
        portfolio_layout = QVBoxLayout(portfolio_group)
        self.portfolio_viz = PortfolioVisualization()

        # Check if we have persistent pattern data and initialize accordingly
        has_patterns = self.persistence_manager.load_recent_patterns()
        if not has_patterns:
            # Only show welcome message if no patterns were loaded
            self.portfolio_viz.initialize_display(has_persistent_data=False)

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
        
        self.chart_card = DataStatusCard("Market Sentiment", CyberpunkColors.TERTIARY)
        self.chart_card.setToolTip("Technical analysis and trend detection - identifies chart patterns")
        
        agent_cards_layout.addWidget(self.chart_card)
        agent_cards_layout.addWidget(self.funding_card)
        agent_cards_layout.addWidget(self.oi_card)
        
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
        
        self.chart_enabled_checkbox = QCheckBox("Market Sentiment")
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
        
        
        # Add tabs for data visualization
        tab_widget.addTab(QWidget(), "History")
        tab_widget.addTab(QWidget(), "Statistics")
        tab_widget.addTab(QWidget(), "Data")
        tab_widget.addTab(QWidget(), "AI Brain")
        # Add configuration tab
        tab_widget.addTab(config_widget, "Settings")
        # Add enviroment keys tab
        tab_widget.addTab(QWidget(), "Keys")
        
        # Add tab widget to content layout
        content_layout.addWidget(tab_widget)
        
        # Add content widget to splitter
        content_splitter.addWidget(content_widget)
        # Set minimum size for content area to prevent it from taking all space
        content_widget.setMinimumHeight(200)
        
        # Console output
        console_group = QGroupBox("System Log")
        console_layout = QVBoxLayout(console_group)
        console_layout.setContentsMargins(5, 5, 5, 5)  # Add margins for better spacing
        self.console = ConsoleOutput()
        console_layout.addWidget(self.console)
        
        # Add console to splitter
        content_splitter.addWidget(console_group)
        # Set minimum and maximum sizes for console to keep it visible but compact
        console_group.setMinimumHeight(120)  # Reduced minimum height for more compact console
        console_group.setMaximumHeight(180)  # Reduced maximum height to prevent it from taking too much space
        
        # Set initial splitter sizes with proper proportions (console should be smaller)
        content_splitter.setSizes([700, 120])  # Reduced console initial size from 200 to 120
        # Set stretch factors: content area gets more space (1), console gets less (0)
        content_splitter.setStretchFactor(0, 1)  # Content area can grow
        content_splitter.setStretchFactor(1, 0)  # Console maintains its size better
        
        # Add splitter to main layout
        main_layout.addWidget(content_splitter)
        # Set stretch factor so splitter takes remaining space but respects status bar
        main_layout.setStretchFactor(content_splitter, 1)
        
        # Initialize with sample data
        self.initialize_sample_data()
        
        # Clean up old log files on startup (after console is initialized)
        self.cleanup_old_logs()
        
        # Restore settings state now that UI is fully initialized
        if hasattr(self, '_saved_settings_state') and self._saved_settings_state:
            self.persistence_manager.restore_settings_state({"settings": self._saved_settings_state})
        
        # Also update config editor autorun checkbox if it exists
        if hasattr(self, 'config_editor') and hasattr(self.config_editor, 'autorun_system_cb'):
            self.config_editor.autorun_system_cb.setChecked(self.autorun_system)
        
        # Restore data alerts state now that UI is fully initialized
        if hasattr(self, '_saved_data_alerts_state') and self._saved_data_alerts_state:
            self.persistence_manager.restore_data_alerts_state({"data_alerts": self._saved_data_alerts_state})
        
        # Application state restored message (patterns loaded earlier in initialization)
        if hasattr(self, '_saved_state_loaded') and self._saved_state_loaded:
            self.console.append_message("Application state restored from previous session", "success")
        
        # Add initial console messages
        self.console.append_message("🌙 Moon Dev AI Agent Trading System Starting...", "system")
        self.console.append_message("📊 Active Agents and their Intervals:", "system")
        # Removed: Detailed agent interval list - now only shows header
        self.console.append_message("Data monitoring initialized (connects when data collection starts)", "info")
        self.console.append_message("Strategy runner initialized", "info")
        
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

    def cleanup_old_logs(self):
        """Clean up old data collection log files on startup"""
        try:
            log_dir = Path(__file__).parent
            log_patterns = ['data_collection_stdout_*.log', 'data_collection_stderr_*.log']

            deleted_count = 0
            for pattern in log_patterns:
                for log_file in log_dir.glob(pattern):
                    try:
                        log_file.unlink()
                        deleted_count += 1
                        print(f"[LOG CLEANUP] Deleted old log: {log_file.name}")
                    except Exception as e:
                        print(f"[LOG CLEANUP] Error deleting {log_file.name}: {e}")

            if deleted_count > 0:
                if hasattr(self, 'console'):
                    self.console.append_message(f"Cleaned up {deleted_count} old log files", "info")
        except Exception as e:
            print(f"[LOG CLEANUP] Error during log cleanup: {e}")

    def center_window(self):
        """Center the window horizontally and position it higher on the screen"""
        from PySide6.QtGui import QScreen
        from PySide6.QtCore import QPoint
        screen = QApplication.primaryScreen()
        screen_geometry = screen.geometry()
        window_geometry = self.frameGeometry()
        
        # Center horizontally
        center_x = screen_geometry.center().x()
        
        # Position higher vertically (about 15% from top instead of center)
        # This moves the window up so the bottom isn't cut off by the taskbar
        window_height = window_geometry.height()
        top_margin = int(screen_geometry.height() * 0.00)  # 15% from top
        center_y = top_margin + (window_height // 2)
        
        # Move window to calculated position
        window_geometry.moveCenter(QPoint(center_x, center_y))
        self.move(window_geometry.topLeft())
    
    def resizeEvent(self, event):
        """Handle window resize to maintain proper layout"""
        super().resizeEvent(event)
        # Ensure console remains visible by adjusting splitter if needed
        if hasattr(self, 'console') and hasattr(self, 'content_splitter'):
            # Get current sizes
            sizes = self.content_splitter.sizes()
            if len(sizes) >= 2:
                # Calculate available height (window height - header - status bar - margins)
                available_height = self.height() - self.header_frame.height() - self.statusBar().height() - 50
                # Ensure console has at least minimum height
                min_console_height = 100  # Match the new minimum height
                max_content_height = available_height - min_console_height
                # Adjust if content area is too large
                if sizes[0] > max_content_height and max_content_height > 0:
                    self.content_splitter.setSizes([max_content_height, min_console_height])
        
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
        
        # Execute autorun after UI is fully initialized
        QTimer.singleShot(1000, self.execute_system_autorun)
        
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
        # Map data type to card with validation
        card = None
        if data_type == "oi":
            card = self.oi_card
            # OI data can have 'alerts' or just 'status' (for status-only updates)
            # The update_data method will handle missing alerts gracefully
        elif data_type == "funding":
            card = self.funding_card
            # Funding data can have 'alerts' or just 'status' (for status-only updates)
            # The update_data method will handle missing alerts gracefully
        elif data_type == "chart" or data_type == "chartanalysis":
            card = self.chart_card
            # Validate: Chart data MUST have 'sentiment' field (not just 'status')
            # This prevents funding/oi data from overwriting chart metrics
            if 'sentiment' not in data:
                return  # Don't update if data doesn't have sentiment field
        
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
        
        # NEW: System menu for complete system control
        system_menu = menubar.addMenu('System')
        self.start_system_action = system_menu.addAction('Start Trading System')
        self.stop_system_action = system_menu.addAction('Stop Trading System')
        self.start_system_action.triggered.connect(self.start_trading_system)
        self.stop_system_action.triggered.connect(self.stop_trading_system)
        self.stop_system_action.setEnabled(False)

        # Strategy menu
        strategy_menu = menubar.addMenu('Strategy')
        self.run_pattern_action = strategy_menu.addAction('Run Strategy')
        self.stop_strategy_action = strategy_menu.addAction('Stop Strategy')
        self.run_pattern_action.triggered.connect(self.run_pattern_strategy)
        self.stop_strategy_action.triggered.connect(self.stop_strategy)
        self.stop_strategy_action.setEnabled(False)
        
        # Data Collection menu
        data_menu = menubar.addMenu('Data Collection')
        self.start_data_action = data_menu.addAction('Start Data Collection')
        self.stop_data_action = data_menu.addAction('Stop Data Collection')
        self.start_data_action.triggered.connect(self.start_data_collection)
        self.stop_data_action.triggered.connect(self.stop_data_collection)
        self.stop_data_action.setEnabled(False)

        # Add separator
        system_menu.addSeparator()

        # Autorun toggle in system menu
        self.autorun_system_action = system_menu.addAction('Auto-start System')
        self.autorun_system_action.setCheckable(True)
        self.autorun_system_action.setChecked(False)
        self.autorun_system_action.triggered.connect(self.toggle_autorun_system)
    
    def start_data_collection(self):
        """Start data collection service and monitoring"""
        self.console.append_message("Starting data collection service...", "system")
        
        # Start data.py as subprocess
        data_script = Path(__file__).parent / "data.py"
        
        if not data_script.exists():
            self.console.append_message(f"Error: data.py not found at {data_script}", "error")
            return
        
        try:
            # Create log files for subprocess output
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            stdout_log = Path(__file__).parent / f"data_collection_stdout_{timestamp}.log"
            stderr_log = Path(__file__).parent / f"data_collection_stderr_{timestamp}.log"

            with open(stdout_log, 'w') as stdout_file, open(stderr_log, 'w') as stderr_file:
                self.data_process = subprocess.Popen(
                    [sys.executable, str(data_script)],
                    stdout=stdout_file,
                    stderr=stderr_file,
                    cwd=Path(__file__).parent,  # Set working directory to src/
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )

            # Register process with manager
            self.process_manager.register_process(
                'data_collection',
                self.data_process,
                stdout_file,
                stderr_file
            )

            self.console.append_message(f"Data collection service started (PID: {self.data_process.pid})", "success")
            self.console.append_message(f"Logs: stdout={stdout_log.name}, stderr={stderr_log.name}", "info")
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
        
        # Use process manager for cleanup
        if hasattr(self, 'data_process') and self.data_process:
            self.process_manager.cleanup_process('data_collection')
            self.console.append_message("Data collection service stopped", "info")
        
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
            self.strategy_status_label.setText("Strategy: Running")
            self.strategy_status_label.setStyleSheet(f"color: {CyberpunkColors.SUCCESS}; padding: 5px;")
            
            # Update AI Analysis Console to show running status
            self.portfolio_viz.show_running_message(
                symbols, 
                config['scan_interval'], 
                config['timeframe']
            )
            
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

    def start_trading_system(self):
        """Start the complete trading system (both data collection and strategy)"""
        self.console.append_message("Starting complete trading system...", "system")

        # Start data collection first
        if self.start_data_action.isEnabled():
            self.start_data_collection()

            # Wait a moment for data collection to initialize, then start strategy
            QTimer.singleShot(2000, self.start_strategy_after_data)
        else:
            # Data collection already running, just start strategy
            self.start_strategy_after_data()

    def start_strategy_after_data(self):
        """Start strategy after ensuring data collection is running"""
        if self.run_pattern_action.isEnabled():
            self.run_pattern_strategy()

        # Update system menu state
        self.start_system_action.setEnabled(False)
        self.stop_system_action.setEnabled(True)

        # Check if both services are now running
        both_running = (not self.start_data_action.isEnabled() and
                       not self.run_pattern_action.isEnabled())

        if both_running:
            self.console.append_message("Complete trading system started successfully", "success")
        else:
            self.console.append_message("Warning: Not all system components started", "warning")

    def stop_trading_system(self):
        """Stop the complete trading system (both data collection and strategy)"""
        self.console.append_message("Stopping complete trading system...", "warning")

        # Stop both services
        stopped_count = 0

        if self.stop_data_action.isEnabled():
            self.stop_data_collection()
            stopped_count += 1

        if self.stop_strategy_action.isEnabled():
            self.stop_strategy()
            stopped_count += 1

        # Update system menu state
        self.start_system_action.setEnabled(True)
        self.stop_system_action.setEnabled(False)

        if stopped_count > 0:
            self.console.append_message(f"Trading system stopped ({stopped_count} services)", "info")
        else:
            self.console.append_message("No running services to stop", "info")

    def toggle_autorun_system(self):
        """Toggle autorun system setting"""
        enabled = self.autorun_system_action.isChecked()
        self.autorun_system = enabled

        # Update config editor checkbox if it exists
        if hasattr(self, 'config_editor') and hasattr(self.config_editor, 'autorun_system_cb'):
            self.config_editor.autorun_system_cb.setChecked(enabled)

        # Save setting
        if hasattr(self, 'config_data'):
            self.config_data['autorun_system'] = enabled

        # Immediately save to persistence file
        self.persistence_manager.save_state()
        
        # Debug: Verify it was saved
        saved_state = self.persistence_manager.load_state()
        if saved_state and "autorun_settings" in saved_state:
            print(f"[AUTORUN] Verified saved: {saved_state['autorun_settings']}")
        else:
            print(f"[AUTORUN] WARNING: Autorun setting not found in saved state!")

        status = "enabled" if enabled else "disabled"
        self.console.append_message(f"System autorun {status}", "success")

    def execute_system_autorun(self):
        """Execute system autorun functionality"""
        # Debug: Check autorun state
        autorun_enabled = getattr(self, 'autorun_system', False)
        
        # Always log for debugging
        print(f"[AUTORUN] execute_system_autorun called, autorun_enabled: {autorun_enabled}")
        self.console.append_message(f"System autorun check: {'Enabled' if autorun_enabled else 'Disabled'}", "info")
        
        if not autorun_enabled:
            return

        try:
            self.console.append_message("System autorun: Starting complete trading system...", "system")
            self.start_trading_system()

        except Exception as e:
            self.console.append_message(f"System autorun error: {e}", "error")
            import traceback
            traceback.print_exc()

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
        # REMOVED: No longer initializing portfolio data - this is now the AI Analysis Console
        # The portfolio visualization has been repurposed for pattern analysis
        pass
    
    def simulate_updates(self):
        """Simulate real-time updates"""
        # Removed simulated trading messages - now only real data collection and pattern detection messages appear
        # The portfolio visualization area is now used for displaying AI pattern analysis

        # Portfolio simulation removed - now using AI analysis console instead
        # The portfolio visualization area is now used for displaying AI pattern analysis
        pass
    
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
        # Save state before closing
        self.persistence_manager.save_state()

        # Stop auto-save timer
        if self.persistence_manager.auto_save_timer:
            self.persistence_manager.auto_save_timer.stop()

        # Ensure all processes are cleaned up
        self.process_manager.cleanup_all_processes()

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
    window.center_window()  # Center window on screen
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
