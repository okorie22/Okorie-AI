import sys
import os
import math
import importlib.util
from pathlib import Path
from datetime import datetime, timedelta
import json
import random

from PySide6.QtWidgets import (QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QSlider, QComboBox, 
                             QLineEdit, QTextEdit, QProgressBar, QFrame, QGridLayout,
                             QSplitter, QGroupBox, QCheckBox, QSpacerItem, QSizePolicy,
                             QFileDialog, QMessageBox, QDialog, QDialogButtonBox)
from PySide6.QtCore import Qt, QTimer, Signal, Slot, QSize, QThread, QObject
from PySide6.QtGui import QColor, QFont, QPalette, QLinearGradient, QGradient, QPainter, QPen, QBrush

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

class PortfolioVisualization(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(300)
        self.tokens = []
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(50)  # Update every 50ms for animation
        self.animation_offset = 0
        
    def set_portfolio_data(self, tokens):
        """
        Set portfolio data for visualization
        tokens: list of dicts with keys: name, allocation, performance, volatility
        """
        self.tokens = tokens
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw background
        painter.fillRect(self.rect(), QColor(CyberpunkColors.BACKGROUND))
        
        # Draw grid lines
        pen = QPen(QColor(CyberpunkColors.PRIMARY).darker(300))
        pen.setWidth(1)
        painter.setPen(pen)
        
        # Draw horizontal grid lines
        for i in range(0, self.height(), 20):
            painter.drawLine(0, i, self.width(), i)
            
        # Draw vertical grid lines
        for i in range(0, self.width(), 20):
            painter.drawLine(i, 0, i, self.height())
            
        # Draw tokens if we have data
        if not self.tokens:
            # Draw placeholder text
            painter.setPen(QColor(CyberpunkColors.TEXT_LIGHT))
            painter.setFont(QFont("Rajdhani", 14))
            painter.drawText(self.rect(), Qt.AlignCenter, "Portfolio Visualization\n(No data available)")
            return
            
        center_x = self.width() / 2
        center_y = self.height() / 2
        radius = min(center_x, center_y) * 0.8
        
        # Update animation offset
        self.animation_offset = (self.animation_offset + 1) % 360
        
        # Draw central hub
        hub_radius = 30
        # Draw hub glow
        for i in range(3):
            glow_size = hub_radius + (3-i)*4
            painter.setPen(Qt.NoPen)
            glow_color = QColor(CyberpunkColors.PRIMARY)
            glow_color.setAlpha(50 - i*15)
            painter.setBrush(QBrush(glow_color))
            painter.drawEllipse(int(center_x - glow_size/2), int(center_y - glow_size/2), 
                               int(glow_size), int(glow_size))
        
        # Draw hub
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(CyberpunkColors.PRIMARY)))
        painter.drawEllipse(int(center_x - hub_radius/2), int(center_y - hub_radius/2), 
                           int(hub_radius), int(hub_radius))
        
        # Draw tokens in a circular pattern
        angle_step = 360 / len(self.tokens)
        current_angle = self.animation_offset * 0.1  # Slow rotation
        
        for token in self.tokens:
            # Calculate position
            x = center_x + radius * 0.8 * math.cos(math.radians(current_angle))
            y = center_y + radius * 0.8 * math.sin(math.radians(current_angle))
            
            # Determine color based on performance
            if token.get('performance', 0) > 0:
                color = QColor(CyberpunkColors.SUCCESS)
            elif token.get('performance', 0) < 0:
                color = QColor(CyberpunkColors.DANGER)
            else:
                color = QColor(CyberpunkColors.PRIMARY)
                
            # Determine size based on allocation
            size = 10 + (token.get('allocation', 1) * 40)
            
            # Add pulsing effect based on volatility
            volatility = token.get('volatility', 0.05)
            pulse = math.sin(math.radians(self.animation_offset * 4 * volatility)) * 5
            size += pulse
            
            # Draw connection line to center
            pen = QPen(color.darker(200))
            pen.setWidth(1)
            painter.setPen(pen)
            painter.drawLine(int(center_x), int(center_y), int(x), int(y))
            
            # Draw token circle with glow effect
            # First draw glow
            for i in range(3):
                glow_size = size + (3-i)*4
                painter.setPen(Qt.NoPen)
                glow_color = QColor(color)
                glow_color.setAlpha(50 - i*15)
                painter.setBrush(QBrush(glow_color))
                painter.drawEllipse(int(x - glow_size/2), int(y - glow_size/2), 
                                   int(glow_size), int(glow_size))
            
            # Then draw main circle
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(color))
            painter.drawEllipse(int(x - size/2), int(y - size/2), int(size), int(size))
            
            # Draw token name
            painter.setPen(QColor(CyberpunkColors.TEXT_WHITE))
            painter.setFont(QFont("Rajdhani", 8, QFont.Bold))
            text_rect = painter.boundingRect(int(x - 50), int(y + size/2 + 5), 
                                           100, 20, Qt.AlignCenter, token.get('name', ''))
            painter.drawText(text_rect, Qt.AlignCenter, token.get('name', ''))
            
            # Draw allocation percentage
            allocation_text = f"{token.get('allocation', 0)*100:.1f}%"
            perf_text = f"{token.get('performance', 0)*100:+.1f}%"
            combined_text = f"{allocation_text} ({perf_text})"
            
            text_rect = painter.boundingRect(int(x - 50), int(y + size/2 + 25), 
                                           100, 20, Qt.AlignCenter, combined_text)
            painter.drawText(text_rect, Qt.AlignCenter, combined_text)
            
            current_angle += angle_step

class AgentStatusCard(NeonFrame):
    def __init__(self, agent_name, color, parent=None):
        super().__init__(color, parent)
        self.agent_name = agent_name
        self.color = QColor(color)
        self.status = "Inactive"
        self.last_run = "Never"
        self.next_run = "Not scheduled"
        
        # Create layout
        layout = QVBoxLayout(self)
        
        # Agent name header
        self.name_label = QLabel(agent_name)
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
        self.status_label = QLabel(self.status)
        self.status_label.setStyleSheet(f"color: {CyberpunkColors.DANGER};")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        layout.addLayout(status_layout)
        
        # Last run
        last_run_layout = QHBoxLayout()
        last_run_layout.addWidget(QLabel("Last Run:"))
        self.last_run_label = QLabel(self.last_run)
        last_run_layout.addWidget(self.last_run_label)
        last_run_layout.addStretch()
        layout.addLayout(last_run_layout)
        
        # Next run
        next_run_layout = QHBoxLayout()
        next_run_layout.addWidget(QLabel("Next Run:"))
        self.next_run_label = QLabel(self.next_run)
        next_run_layout.addWidget(self.next_run_label)
        next_run_layout.addStretch()
        layout.addLayout(next_run_layout)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {CyberpunkColors.BACKGROUND};
                border: 1px solid {color};
                border-radius: 2px;
                height: 6px;
            }}
            QProgressBar::chunk {{
                background-color: {color};
            }}
        """)
        layout.addWidget(self.progress_bar)
        
        # Control buttons
        button_layout = QHBoxLayout()
        self.start_button = NeonButton("Start", CyberpunkColors.SUCCESS)
        self.stop_button = NeonButton("Stop", CyberpunkColors.DANGER)
        self.stop_button.setEnabled(False)
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        layout.addLayout(button_layout)
        
        # Connect signals
        self.start_button.clicked.connect(self.start_agent)
        self.stop_button.clicked.connect(self.stop_agent)
        
        # Set default styling
        self.setStyleSheet(f"""
            QLabel {{
                color: {CyberpunkColors.TEXT_LIGHT};
                font-family: 'Rajdhani', sans-serif;
            }}
        """)
        
    def start_agent(self):
        self.status = "Active"
        self.status_label.setText(self.status)
        self.status_label.setStyleSheet(f"color: {CyberpunkColors.SUCCESS};")
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        
        # Update last run time
        self.last_run = datetime.now().strftime("%H:%M:%S")
        self.last_run_label.setText(self.last_run)
        
        # Update next run time (example: 30 minutes from now)
        next_run_time = datetime.now() + timedelta(minutes=30)
        self.next_run = next_run_time.strftime("%H:%M:%S")
        self.next_run_label.setText(self.next_run)
        
        # Simulate progress
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_progress)
        self.timer.start(100)
        
    def stop_agent(self):
        self.status = "Inactive"
        self.status_label.setText(self.status)
        self.status_label.setStyleSheet(f"color: {CyberpunkColors.DANGER};")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        
        # Stop progress timer
        if hasattr(self, 'timer'):
            self.timer.stop()
        self.progress_bar.setValue(0)
        
    def update_progress(self):
        current_value = self.progress_bar.value()
        if current_value >= 100:
            self.progress_bar.setValue(0)
        else:
            self.progress_bar.setValue(current_value + 1)
            
    def update_status(self, status_data):
        """Update card with real agent status data"""
        if 'status' in status_data:
            self.status = status_data['status']
            self.status_label.setText(self.status)
            if self.status == "Active":
                self.status_label.setStyleSheet(f"color: {CyberpunkColors.SUCCESS};")
                self.start_button.setEnabled(False)
                self.stop_button.setEnabled(True)
            else:
                self.status_label.setStyleSheet(f"color: {CyberpunkColors.DANGER};")
                self.start_button.setEnabled(True)
                self.stop_button.setEnabled(False)
                
        if 'last_run' in status_data:
            self.last_run = status_data['last_run']
            self.last_run_label.setText(self.last_run)
            
        if 'next_run' in status_data:
            self.next_run = status_data['next_run']
            self.next_run_label.setText(self.next_run)
            
        if 'progress' in status_data:
            self.progress_bar.setValue(status_data['progress'])

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
        self.copybot_card = AgentStatusCard("Copybot Agent", CyberpunkColors.PRIMARY)
        self.risk_card = AgentStatusCard("Risk Agent", CyberpunkColors.DANGER)
        self.dca_card = AgentStatusCard("DCA/Staking Agent", CyberpunkColors.SUCCESS)
        self.chart_card = AgentStatusCard("Chart Analysis Agent", CyberpunkColors.SECONDARY)
        
        agent_cards_layout.addWidget(self.copybot_card)
        agent_cards_layout.addWidget(self.risk_card)
        agent_cards_layout.addWidget(self.dca_card)
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
        
        # Simulate portfolio changes
        if hasattr(self, 'portfolio_viz') and self.portfolio_viz.tokens:
            tokens = self.portfolio_viz.tokens
            for token in tokens:
                # Randomly adjust performance within a small range
                perf_change = (random.random() - 0.5) * 0.05
                token['performance'] = max(-0.5, min(0.5, token['performance'] + perf_change))
            
            self.portfolio_viz.set_portfolio_data(tokens)
    
    def connect_agent_signals(self):
        """Connect signals for agent cards"""
        # Copybot agent
        self.copybot_card.start_button.clicked.connect(lambda: self.start_agent("copybot"))
        self.copybot_card.stop_button.clicked.connect(lambda: self.stop_agent("copybot"))
        
        # Risk agent
        self.risk_card.start_button.clicked.connect(lambda: self.start_agent("risk"))
        self.risk_card.stop_button.clicked.connect(lambda: self.stop_agent("risk"))
        
        # DCA agent
        self.dca_card.start_button.clicked.connect(lambda: self.start_agent("dca_staking"))
        self.dca_card.stop_button.clicked.connect(lambda: self.stop_agent("dca_staking"))
        
        # Chart analysis agent
        self.chart_card.start_button.clicked.connect(lambda: self.start_agent("chart_analysis"))
        self.chart_card.stop_button.clicked.connect(lambda: self.stop_agent("chart_analysis"))
    
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
        card = None
        if agent_name == "copybot":
            card = self.copybot_card
        elif agent_name == "risk":
            card = self.risk_card
        elif agent_name == "dca_staking":
            card = self.dca_card
        elif agent_name == "chart_analysis":
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
