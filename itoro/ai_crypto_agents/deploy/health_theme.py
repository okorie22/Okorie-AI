#!/usr/bin/env python3
"""
🧠 Anarcho Capital's AI/Neural Network Health Check Theme
Advanced terminal styling with circuit patterns and neural network aesthetics
Built with love by Anarcho Capital 🚀
"""

import os
import sys
import time
import threading
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

# Color codes for AI/Neural Network theme
class Colors:
    """AI/Neural Network color palette"""
    # Primary colors
    NEURAL_BLUE = '\033[38;2;0;191;255m'      # Bright cyan blue
    NEURAL_PURPLE = '\033[38;2;138;43;226m'   # Blue violet
    NEURAL_CYAN = '\033[38;2;0;255;255m'      # Pure cyan
    NEURAL_MAGENTA = '\033[38;2;255;0;255m'   # Bright magenta
    
    # Secondary colors
    CIRCUIT_GREEN = '\033[38;2;0;255;127m'    # Spring green
    MATRIX_GREEN = '\033[38;2;0;255;0m'       # Lime green
    ELECTRIC_BLUE = '\033[38;2;0;100;255m'    # Electric blue
    PLASMA_PINK = '\033[38;2;255;20;147m'     # Deep pink
    
    # Status colors
    HEALTHY = '\033[38;2;0;255;127m'          # Spring green
    WARNING = '\033[38;2;255;165;0m'          # Orange
    CRITICAL = '\033[38;2;255;0;0m'           # Red
    CHECKING = '\033[38;2;0;191;255m'         # Bright cyan
    
    # Background colors
    BG_DARK = '\033[48;2;0;0;20m'             # Very dark blue
    BG_NEURAL = '\033[48;2;10;10;40m'         # Dark neural blue
    
    # Reset
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    UNDERLINE = '\033[4m'
    BLINK = '\033[5m'

class StatusIcon:
    """Status indicators with AI theme"""
    HEALTHY = '⚡'      # Lightning bolt
    WARNING = '⚠️'      # Warning triangle
    CRITICAL = '❌'     # X mark
    CHECKING = '🔄'     # Refresh
    LOADING = '⏳'      # Hourglass
    SUCCESS = '✅'      # Check mark
    FAILED = '💥'       # Explosion
    NEURAL = '🧠'       # Brain
    CIRCUIT = '⚡'      # Circuit
    DATA = '📊'         # Chart
    NETWORK = '🌐'      # Globe
    SECURITY = '🔒'     # Lock
    PERFORMANCE = '🚀'  # Rocket

@dataclass
class ThemeConfig:
    """Theme configuration"""
    show_animations: bool = True
    show_banner: bool = True
    show_progress_bars: bool = True
    show_circuit_lines: bool = True
    animation_speed: float = 0.1
    banner_style: str = "neural_network"  # neural_network, circuit_board, matrix

class NeuralTheme:
    """AI/Neural Network themed terminal interface"""
    
    def __init__(self, config: Optional[ThemeConfig] = None):
        self.config = config or ThemeConfig()
        self.animation_thread = None
        self.animation_running = False
        self.current_frame = 0
        
    def clear_screen(self):
        """Clear terminal screen with neural effect"""
        os.system('cls' if os.name == 'nt' else 'clear')
        
    def print_banner(self, title: str = "ANARCHO CAPITAL HEALTH MONITOR"):
        """Print AI/Neural Network themed banner"""
        if not self.config.show_banner:
            return
            
        banner = self._get_banner(title)
        print(f"{Colors.BG_DARK}{Colors.NEURAL_CYAN}{banner}{Colors.RESET}")
        print()
        
    def _get_banner(self, title: str) -> str:
        """Generate banner based on style"""
        if self.config.banner_style == "neural_network":
            return self._neural_network_banner(title)
        elif self.config.banner_style == "circuit_board":
            return self._circuit_board_banner(title)
        else:
            return self._matrix_banner(title)
    
    def _neural_network_banner(self, title: str) -> str:
        """Neural network style banner"""
        return f"""
    {Colors.NEURAL_BLUE}╔══════════════════════════════════════════════════════════════════════════════╗{Colors.RESET}
    {Colors.NEURAL_BLUE}║{Colors.RESET}  {Colors.NEURAL_CYAN}🧠 NEURAL NETWORK HEALTH MONITORING SYSTEM 🧠{Colors.RESET}  {Colors.NEURAL_BLUE}║{Colors.RESET}
    {Colors.NEURAL_BLUE}║{Colors.RESET}                                                                      {Colors.NEURAL_BLUE}║{Colors.RESET}
    {Colors.NEURAL_BLUE}║{Colors.RESET}  {Colors.CIRCUIT_GREEN}┌─┐┌─┐┌┬┐┌─┐┌─┐┌─┐┌─┐  ┌─┐┌─┐┌─┐┌─┐┌─┐┌─┐┌─┐┌─┐{Colors.RESET}  {Colors.NEURAL_BLUE}║{Colors.RESET}
    {Colors.NEURAL_BLUE}║{Colors.RESET}  {Colors.CIRCUIT_GREEN}│  │ │ ││││ ││  ││  ││  │  │  ││  ││  ││  ││  ││  ││  ││  │{Colors.RESET}  {Colors.NEURAL_BLUE}║{Colors.RESET}
    {Colors.NEURAL_BLUE}║{Colors.RESET}  {Colors.CIRCUIT_GREEN}└─┘└─┘└─┘└─┘└─┘└─┘└─┘  └─┘└─┘└─┘└─┘└─┘└─┘└─┘└─┘{Colors.RESET}  {Colors.NEURAL_BLUE}║{Colors.RESET}
    {Colors.NEURAL_BLUE}║{Colors.RESET}                                                                      {Colors.NEURAL_BLUE}║{Colors.RESET}
    {Colors.NEURAL_BLUE}║{Colors.RESET}  {Colors.NEURAL_PURPLE}⚡ Real-time System Diagnostics & Performance Monitoring ⚡{Colors.RESET}  {Colors.NEURAL_BLUE}║{Colors.RESET}
    {Colors.NEURAL_BLUE}╚══════════════════════════════════════════════════════════════════════════════╝{Colors.RESET}
    """
    
    def _circuit_board_banner(self, title: str) -> str:
        """Circuit board style banner"""
        return f"""
    {Colors.ELECTRIC_BLUE}┌─────────────────────────────────────────────────────────────────────────────┐{Colors.RESET}
    {Colors.ELECTRIC_BLUE}│{Colors.RESET}  {Colors.CIRCUIT_GREEN}⚡ CIRCUIT BOARD HEALTH MONITOR ⚡{Colors.RESET}  {Colors.ELECTRIC_BLUE}│{Colors.RESET}
    {Colors.ELECTRIC_BLUE}├─────────────────────────────────────────────────────────────────────────────┤{Colors.RESET}
    {Colors.ELECTRIC_BLUE}│{Colors.RESET}  {Colors.NEURAL_CYAN}┌─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┐{Colors.RESET}  {Colors.ELECTRIC_BLUE}│{Colors.RESET}
    {Colors.ELECTRIC_BLUE}│{Colors.RESET}  {Colors.NEURAL_CYAN}│ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │{Colors.RESET}  {Colors.ELECTRIC_BLUE}│{Colors.RESET}
    {Colors.ELECTRIC_BLUE}│{Colors.RESET}  {Colors.NEURAL_CYAN}└─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┘{Colors.RESET}  {Colors.ELECTRIC_BLUE}│{Colors.RESET}
    {Colors.ELECTRIC_BLUE}└─────────────────────────────────────────────────────────────────────────────┘{Colors.RESET}
    """
    
    def _matrix_banner(self, title: str) -> str:
        """Matrix style banner"""
        return f"""
    {Colors.MATRIX_GREEN}╔══════════════════════════════════════════════════════════════════════════════╗{Colors.RESET}
    {Colors.MATRIX_GREEN}║{Colors.RESET}  {Colors.CIRCUIT_GREEN}🔮 MATRIX HEALTH MONITOR 🔮{Colors.RESET}  {Colors.MATRIX_GREEN}║{Colors.RESET}
    {Colors.MATRIX_GREEN}║{Colors.RESET}                                                                      {Colors.MATRIX_GREEN}║{Colors.RESET}
    {Colors.MATRIX_GREEN}║{Colors.RESET}  {Colors.NEURAL_CYAN}01001000 01100101 01100001 01101100 01110100 01101000{Colors.RESET}  {Colors.MATRIX_GREEN}║{Colors.RESET}
    {Colors.MATRIX_GREEN}║{Colors.RESET}  {Colors.NEURAL_CYAN}01001101 01101111 01101110 01101001 01110100 01101111 01110010{Colors.RESET}  {Colors.MATRIX_GREEN}║{Colors.RESET}
    {Colors.MATRIX_GREEN}╚══════════════════════════════════════════════════════════════════════════════╝{Colors.RESET}
    """
    
    def print_header(self, title: str, subtitle: str = ""):
        """Print section header with circuit line decoration"""
        if self.config.show_circuit_lines:
            line = "─" * 80
            print(f"{Colors.NEURAL_BLUE}┌{line}┐{Colors.RESET}")
            print(f"{Colors.NEURAL_BLUE}│{Colors.RESET} {Colors.BOLD}{Colors.NEURAL_CYAN}{title}{Colors.RESET}")
            if subtitle:
                print(f"{Colors.NEURAL_BLUE}│{Colors.RESET} {Colors.DIM}{Colors.NEURAL_PURPLE}{subtitle}{Colors.RESET}")
            print(f"{Colors.NEURAL_BLUE}└{line}┘{Colors.RESET}")
        else:
            print(f"{Colors.BOLD}{Colors.NEURAL_CYAN}{title}{Colors.RESET}")
            if subtitle:
                print(f"{Colors.DIM}{Colors.NEURAL_PURPLE}{subtitle}{Colors.RESET}")
        print()
    
    def print_status(self, status: str, message: str, details: str = ""):
        """Print status with appropriate icon and color"""
        icon = self._get_status_icon(status)
        color = self._get_status_color(status)
        
        status_line = f"{color}{icon} {message}{Colors.RESET}"
        if details:
            status_line += f" {Colors.DIM}({details}){Colors.RESET}"
        
        print(status_line)
    
    def _get_status_icon(self, status: str) -> str:
        """Get icon for status"""
        status_lower = status.lower()
        if 'healthy' in status_lower or 'pass' in status_lower or 'success' in status_lower:
            return StatusIcon.HEALTHY
        elif 'warning' in status_lower or 'degraded' in status_lower:
            return StatusIcon.WARNING
        elif 'critical' in status_lower or 'fail' in status_lower or 'error' in status_lower:
            return StatusIcon.CRITICAL
        elif 'checking' in status_lower or 'loading' in status_lower:
            return StatusIcon.CHECKING
        else:
            return StatusIcon.NEURAL
    
    def _get_status_color(self, status: str) -> str:
        """Get color for status"""
        status_lower = status.lower()
        if 'healthy' in status_lower or 'pass' in status_lower or 'success' in status_lower:
            return Colors.HEALTHY
        elif 'warning' in status_lower or 'degraded' in status_lower:
            return Colors.WARNING
        elif 'critical' in status_lower or 'fail' in status_lower or 'error' in status_lower:
            return Colors.CRITICAL
        elif 'checking' in status_lower or 'loading' in status_lower:
            return Colors.CHECKING
        else:
            return Colors.NEURAL_CYAN
    
    def print_progress_bar(self, current: int, total: int, label: str = "", width: int = 50):
        """Print animated progress bar"""
        if not self.config.show_progress_bars:
            return
            
        percentage = (current / total) * 100 if total > 0 else 0
        filled = int((current / total) * width) if total > 0 else 0
        bar = "█" * filled + "░" * (width - filled)
        
        # Gradient effect
        if percentage < 33:
            color = Colors.CRITICAL
        elif percentage < 66:
            color = Colors.WARNING
        else:
            color = Colors.HEALTHY
        
        progress_line = f"{color}│{bar}│ {percentage:.1f}%{Colors.RESET}"
        if label:
            progress_line = f"{Colors.NEURAL_CYAN}{label}:{Colors.RESET} {progress_line}"
        
        print(progress_line)
    
    def print_metric(self, name: str, value: str, unit: str = "", status: str = "healthy"):
        """Print metric with neural styling"""
        icon = self._get_status_icon(status)
        color = self._get_status_color(status)
        
        metric_line = f"  {color}{icon} {name}:{Colors.RESET} {Colors.BOLD}{value}{Colors.RESET}"
        if unit:
            metric_line += f" {Colors.DIM}{unit}{Colors.RESET}"
        
        print(metric_line)
    
    def print_summary_stats(self, stats: Dict[str, int]):
        """Print summary statistics"""
        total = stats.get('total', 0)
        passed = stats.get('passed', 0)
        warnings = stats.get('warnings', 0)
        critical = stats.get('critical', 0)
        
        print(f"{Colors.BOLD}{Colors.NEURAL_CYAN}📊 SYSTEM HEALTH SUMMARY{Colors.RESET}")
        print(f"{Colors.NEURAL_BLUE}┌─────────────────────────────────────────────────────────┐{Colors.RESET}")
        print(f"{Colors.NEURAL_BLUE}│{Colors.RESET} Total Checks: {Colors.BOLD}{total}{Colors.RESET}")
        print(f"{Colors.NEURAL_BLUE}│{Colors.RESET} {StatusIcon.HEALTHY} Passed: {Colors.HEALTHY}{passed}{Colors.RESET}")
        print(f"{Colors.NEURAL_BLUE}│{Colors.RESET} {StatusIcon.WARNING} Warnings: {Colors.WARNING}{warnings}{Colors.RESET}")
        print(f"{Colors.NEURAL_BLUE}│{Colors.RESET} {StatusIcon.CRITICAL} Critical: {Colors.CRITICAL}{critical}{Colors.RESET}")
        
        if total > 0:
            pass_rate = (passed / total) * 100
            print(f"{Colors.NEURAL_BLUE}│{Colors.RESET} Pass Rate: {Colors.BOLD}{pass_rate:.1f}%{Colors.RESET}")
        
        print(f"{Colors.NEURAL_BLUE}└─────────────────────────────────────────────────────────┘{Colors.RESET}")
        print()
    
    def start_loading_animation(self, message: str = "Initializing"):
        """Start loading animation"""
        if not self.config.show_animations:
            print(f"{Colors.CHECKING}{StatusIcon.CHECKING} {message}...{Colors.RESET}")
            return
            
        self.animation_running = True
        self.animation_thread = threading.Thread(
            target=self._loading_animation_worker,
            args=(message,),
            daemon=True
        )
        self.animation_thread.start()
    
    def stop_loading_animation(self):
        """Stop loading animation"""
        self.animation_running = False
        if self.animation_thread:
            self.animation_thread.join(timeout=1)
        print()  # New line after animation
    
    def _loading_animation_worker(self, message: str):
        """Loading animation worker thread"""
        frames = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        frame_index = 0
        
        while self.animation_running:
            frame = frames[frame_index % len(frames)]
            print(f"\r{Colors.CHECKING}{frame} {message}...{Colors.RESET}", end='', flush=True)
            time.sleep(self.config.animation_speed)
            frame_index += 1
    
    def print_circuit_line(self, length: int = 80):
        """Print decorative circuit line"""
        if not self.config.show_circuit_lines:
            return
            
        line = "─" * length
        print(f"{Colors.NEURAL_BLUE}┌{line}┐{Colors.RESET}")
    
    def print_footer(self, message: str = "Press 'q' to quit, 'v' for verbose, 'r' to refresh"):
        """Print footer with instructions"""
        print(f"{Colors.DIM}{Colors.NEURAL_PURPLE}{message}{Colors.RESET}")
    
    def cleanup(self):
        """Cleanup resources"""
        self.stop_loading_animation()

# Global theme instance
theme = NeuralTheme()

def get_theme() -> NeuralTheme:
    """Get global theme instance"""
    return theme

def print_banner(title: str = "ANARCHO CAPITAL HEALTH MONITOR"):
    """Convenience function to print banner"""
    theme.print_banner(title)

def print_header(title: str, subtitle: str = ""):
    """Convenience function to print header"""
    theme.print_header(title, subtitle)

def print_status(status: str, message: str, details: str = ""):
    """Convenience function to print status"""
    theme.print_status(status, message, details)

def print_metric(name: str, value: str, unit: str = "", status: str = "healthy"):
    """Convenience function to print metric"""
    theme.print_metric(name, value, unit, status)

def print_progress_bar(current: int, total: int, label: str = "", width: int = 50):
    """Convenience function to print progress bar"""
    theme.print_progress_bar(current, total, label, width)

def print_summary_stats(stats: Dict[str, int]):
    """Convenience function to print summary stats"""
    theme.print_summary_stats(stats)

if __name__ == "__main__":
    # Test the theme
    theme = NeuralTheme()
    theme.print_banner()
    theme.print_header("Test Section", "Testing neural theme")
    theme.print_status("healthy", "System operational", "All checks passed")
    theme.print_status("warning", "High memory usage", "85% utilized")
    theme.print_status("critical", "Database connection failed", "Retrying...")
    theme.print_metric("CPU Usage", "45.2", "%", "healthy")
    theme.print_metric("Memory", "8.5", "GB", "warning")
    theme.print_progress_bar(75, 100, "Health Check Progress")
    theme.print_summary_stats({"total": 25, "passed": 20, "warnings": 4, "critical": 1})
    theme.print_footer()
