"""
🌙 Anarcho Capital's AI Trading System - Local Coordinator
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🤖 INTELLIGENT TRADING COORDINATOR
   Advanced webhook-driven agent coordination system
   
📡 ARCHITECTURE:
   • Receives webhook events from Render server via HTTP
   • Coordinates all trading agents locally with event-driven architecture
   • Implements sophisticated agent coordination and conflict resolution
   • Runs background monitoring for risk management and rebalancing

🖥️  SYSTEM LAYOUT:
   Terminal 1: This main.py (CopyBot, Risk, Harvesting)
   Terminal 2: Data Collection (data.py - Whale, Sentiment, Chart Analysis)
   Terminal 3: DeFi Operations (defi.py)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import sys
import time
import threading
import json
import traceback
import subprocess
import signal
from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import requests
import logging
from termcolor import cprint, colored

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Global ngrok process
ngrok_process = None

def start_ngrok():
    """Force start ngrok tunnel (kill existing and start fresh)"""
    global ngrok_process
    
    try:
        # Force kill any existing ngrok processes
        cprint("🔄 Force restarting ngrok tunnel...", "yellow")
        
        # Kill any existing ngrok process
        if ngrok_process:
            try:
                ngrok_process.terminate()
                ngrok_process.wait(timeout=5)
            except:
                pass
        
        # Kill any ngrok processes by name (Windows)
        try:
            subprocess.run(["taskkill", "/F", "/IM", "ngrok.exe"], 
                         capture_output=True, timeout=5)
        except:
            pass
        
        # Wait a moment for processes to fully terminate
        time.sleep(2)
        
        cprint("🚀 Starting fresh ngrok tunnel...", "yellow")
        
        # Start new ngrok process
        ngrok_process = subprocess.Popen(
            ["./ngrok.exe", "http", "8080"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=project_root
        )
        
        # Wait longer for ngrok to fully start
        time.sleep(5)
        
        if ngrok_process.poll() is None:
            cprint("✅ ngrok tunnel started successfully", "green")
            return True
        else:
            cprint("❌ Failed to start ngrok tunnel", "red")
            return False
            
    except Exception as e:
        cprint(f"❌ Error starting ngrok: {e}", "red")
        return False

def is_ngrok_running():
    """Check if ngrok is already running"""
    try:
        # Try to get ngrok status via API
        response = requests.get("http://localhost:4040/api/tunnels", timeout=2)
        if response.status_code == 200:
            tunnels = response.json()
            return len(tunnels.get('tunnels', [])) > 0
    except:
        pass
    return False

def stop_ngrok():
    """Stop ngrok tunnel"""
    global ngrok_process
    
    if ngrok_process:
        try:
            ngrok_process.terminate()
            ngrok_process.wait(timeout=5)
            cprint("🛑 ngrok tunnel stopped", "yellow")
        except:
            try:
                ngrok_process.kill()
            except:
                pass
        ngrok_process = None

def get_ngrok_url():
    """Get the current ngrok URL"""
    try:
        response = requests.get("http://localhost:4040/api/tunnels", timeout=2)
        if response.status_code == 200:
            tunnels = response.json()
            for tunnel in tunnels.get('tunnels', []):
                if tunnel.get('proto') == 'https':
                    return tunnel.get('public_url')
    except:
        pass
    return None

# Import configuration and utilities
from src.config import *
from src.scripts.shared_services.logger import info, warning, error, debug

# Import agents for local coordination
from src.agents.copybot_agent import CopyBotAgent
from src.agents.risk_agent import RiskAgent
from src.agents.harvesting_agent import HarvestingAgent
from src.agents.master_agent import get_master_agent

# Simple coordination - handled by SimpleAgentCoordinator

# Agent instances
copybot_agent = None
risk_agent = None
harvesting_agent = None
master_agent = None

# Flask app for receiving webhook events from Render server
app = Flask(__name__)
app.logger.setLevel(logging.WARNING)  # Reduce Flask noise

# ============================================================================
# 🎨 VISUAL DESIGN FUNCTIONS
# ============================================================================

def print_startup_banner():
    """Print epic gaming-style startup banner with skull and African designs"""
    banner = """
    ╔══════════════════════════════════════════════════════════════════════════════╗
    ║  💀 ██╗████████╗ ██████╗ ██████╗  ██████╗  💀 ║
    ║  💀 ██║╚══██╔══╝██╔═══██╗██╔══██╗██╔═══██╗ 💀 ║
    ║  💀 ██║   ██║   ██║   ██║██████╔╝██║   ██║ 💀 ║
    ║  💀 ██║   ██║   ██║   ██║██╔══██╗██║   ██║ 💀 ║
    ║  💀 ██║   ██║   ╚██████╔╝██║  ██║╚██████╔╝ 💀 ║
    ║  💀 ╚═╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝ ╚═════╝  💀 ║
    ║                                                                              ║
    ║  🌙 ANARCHO CAPITAL AI TRADING SYSTEM 🌙                                    ║
    ║  ═══════════════════════════════════════════════════════════════════════════  ║
    ║                                                                              ║
    ║  ╭─────────────────────────────────────────────────────────────────────────╮  ║
    ║  │  🤖 INTELLIGENT TRADING & OPERATIONS ROBOT by OKEM                                    │  ║
    ║  │  Advanced webhook-driven agent coordination system                     │  ║
    ║  │  🎮 DEMI-GOD MODE ACTIVATED - DARK THEME ENABLED                        │  ║
    ║  ╰─────────────────────────────────────────────────────────────────────────╯  ║
    ║                                                                              ║
    ║  🚀 PHASE 3 NIMROD - LOCAL COORDINATOR                                    ║
    ║  📡 Event-driven architecture with sophisticated agent coordination         ║
    ║  🎯 African Warrior SPIRIT @ MAXIMUM EFFICIENCY                              ║
    ║                                                                              ║
    ╚══════════════════════════════════════════════════════════════════════════════╝
    """
    cprint(banner, "red", attrs=["bold"])

def print_system_info():
    """Print system information with gaming colors and African Warrior theme"""
    cprint("\n💀 SYSTEM CONFIGURATION 💀", "red", attrs=["bold"])
    cprint("🔥" + "═" * 48 + "🔥", "red")
    
    # Show webhook mode status
    webhook_mode = "🌐 WEBHOOK MODE" if WEBHOOK_MODE else "⏱️  POLLING MODE"
    cprint(f"🎮 Operating Mode: {webhook_mode}", "yellow")
    
    # Show paper trading status
    paper_status = "📈 ENABLED" if PAPER_TRADING_ENABLED else "💰 LIVE TRADING"
    cprint(f"⚔️ Trading Mode: {paper_status}", "yellow")
    
    # Show webhook server info
    webhook_url = os.getenv('WEBHOOK_SERVER_URL', 'http://localhost:8080')
    cprint(f"🌍 Webhook Server: {webhook_url}", "yellow")
    
    # Add African Warrior status
    cprint(f"🦁 African Warrior Spirit @ MAXIMUM EFFICIENCY", "yellow")
    cprint(f"💀 Ancestral Blessings: RECEIVED", "red")
    
    cprint("🔥" + "═" * 48 + "🔥", "red")

def print_agent_dashboard():
    """Print epic gaming-style agent status dashboard with skull designs"""
    cprint("\n💀 AGENT DASHBOARD 💀", "red", attrs=["bold"])
    cprint("🔥" + "═" * 58 + "🔥", "red")
    
    # Agent configurations from config
    agents = {
        'copybot': {
            'name': 'CopyBot Agent',
            'emoji': '🤖',
            'status': '🟢 ACTIVE' if WEBHOOK_ACTIVE_AGENTS.get('copybot', False) else '🔴 DISABLED',
            'description': 'Primary trading agent - executes all trading decisions with precision',
            'color': 'green' if WEBHOOK_ACTIVE_AGENTS.get('copybot', False) else 'red',
            'african_emoji': '🦁'
        },
        'risk': {
            'name': 'Risk Agent',
            'emoji': '🛡️',
            'status': '🟢 ACTIVE' if WEBHOOK_ACTIVE_AGENTS.get('risk', False) else '🔴 DISABLED',
            'description': 'Emergency guardian - losses, drawdown, SOL/USDC balance protection',
            'color': 'green' if WEBHOOK_ACTIVE_AGENTS.get('risk', False) else 'red',
            'african_emoji': '🐆'
        },
        'harvesting': {
            'name': 'Harvesting Agent',
            'emoji': '🌾',
            'status': '🟢 ACTIVE' if WEBHOOK_ACTIVE_AGENTS.get('harvesting', False) else '🔴 DISABLED',
            'description': 'Portfolio management - SOL/USDC rebalancing and realized gains reallocation',
            'color': 'green' if WEBHOOK_ACTIVE_AGENTS.get('harvesting', False) else 'red',
            'african_emoji': '🦒'
        },
        'master': {
            'name': 'Master Agent',
            'emoji': '👑',
            'status': '🟢 ACTIVE',
            'description': 'Supreme orchestrator - monitors system, adapts configs, achieves PnL goals',
            'color': 'green',
            'african_emoji': '🦅'
        }
    }
    
    for agent_id, agent_info in agents.items():
        cprint(f"\n{agent_info['african_emoji']} {agent_info['emoji']} {agent_info['name']}", "yellow", attrs=["bold"])
        cprint(f"   💀 Status: {agent_info['status']}", "yellow")
        cprint(f"   ⚔️ Role: {agent_info['description']}", "yellow")
    
    cprint("\n🔥" + "═" * 58 + "🔥", "red")

def print_initialization_progress(step, total_steps, message):
    """Print epic gaming-style progress with agent-specific colors"""
    progress_bar = "█" * int((step / total_steps) * 25)
    progress_empty = "░" * (25 - int((step / total_steps) * 25))
    percentage = int((step / total_steps) * 100)
    
    # Agent-specific colors and emojis
    if step == 1:  # CopyBot Agent
        color = "yellow"
        emoji = "🦁"
    elif step == 2:  # Risk Agent
        color = "red"
        emoji = "🐆"
    elif step == 3:  # Harvesting Agent
        color = "green"
        emoji = "🦒"
    elif step == 4:  # Final step
        color = "blue"
        emoji = "🦏"
    else:
        color = "white"
        emoji = "💀"
    
    # Print the progress bar on its own line
    cprint(f"{emoji} [{progress_bar}{progress_empty}] {percentage:3d}% - {message}", color, attrs=["bold"])
    
    # Add completion emoji for final step
    if step == total_steps:
        cprint("💀✅🦁", "green")

def print_webhook_event(event_type, count=1, details=""):
    """Print epic gaming-style webhook event notifications with skull theme"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    
    if event_type == "received":
        cprint(f"\n💀 [{timestamp}] WEBHOOK AGENT ACTIVATED", "red", attrs=["bold"])
        cprint(f"   🔥 Processing {count} parsed events...", "yellow")
        if details:
            cprint(f"   ⚔️ Details: {details}", "yellow")
    
    elif event_type == "processed":
        cprint(f"   🦁 Successfully processed {count} events", "yellow")
    
    elif event_type == "blocked":
        cprint(f"   💀 Events blocked: {details}", "red")
    
    elif event_type == "deferred":
        cprint(f"   🔥 Events deferred: {details}", "yellow")

def print_agent_activation(agent_name, agent_type, count=1, details=""):
    """Print agent activation in CopyBot's exact format"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    
    # Agent-specific configurations
    agent_configs = {
        'risk': {
            'african_emoji': '🐆',
            'title': 'RISK AGENT ACTIVATED',
            'color': 'red'
        },
        'harvesting': {
            'african_emoji': '🦒', 
            'title': 'HARVESTING AGENT ACTIVATED',
            'color': 'green'
        },
        'copybot': {
            'african_emoji': '🦁',
            'title': 'WEBHOOK AGENT ACTIVATED',
            'color': 'yellow'
        },
        'staking': {
            'african_emoji': '🦅',
            'title': 'STAKING AGENT ACTIVATED',
            'color': 'magenta'
        },
        'defi': {
            'african_emoji': '🐘',
            'title': 'DEFI AGENT ACTIVATED',
            'color': 'cyan'
        }
    }
    
    config = agent_configs.get(agent_type, {
        'african_emoji': '💀',
        'title': 'AGENT ACTIVATED',
        'color': 'white'
    })
    
    # Print in CopyBot's exact format
    cprint(f"\n💀 [{timestamp}] {config['title']}", "red", attrs=["bold"])
    cprint(f"   🔥 Processing {count} parsed events...", config['color'])
    if details:
        cprint(f"   ⚔️ Details: {details}", config['color'])
    cprint(f"   🔥 Processing events with {agent_name}...", config['color'])

def print_agent_event_processing(event_num, total_events, message="Processing transaction...", agent_type="copybot"):
    """Print event processing in CopyBot's exact format"""
    agent_configs = {
        'risk': {'color': 'red'},
        'harvesting': {'color': 'green'},
        'copybot': {'color': 'yellow'},
        'staking': {'color': 'magenta'},
        'defi': {'color': 'cyan'}
    }
    config = agent_configs.get(agent_type, {'color': 'white'})
    cprint(f"   💀 Event {event_num}/{total_events}: {message}", config['color'])

def print_agent_event_result(event_num, result_type, message="", agent_type="copybot"):
    """Print event result in CopyBot's exact format"""
    agent_configs = {
        'risk': {'color': 'red'},
        'harvesting': {'color': 'green'},
        'copybot': {'color': 'yellow'},
        'staking': {'color': 'magenta'},
        'defi': {'color': 'cyan'}
    }
    config = agent_configs.get(agent_type, {'color': 'white'})
    
    if result_type == "success":
        cprint(f"   🦁 Event {event_num}: Successfully processed", config['color'])
    elif result_type == "no_action":
        cprint(f"   ⚔️ Event {event_num}: No action taken", config['color'])
    elif result_type == "failed":
        cprint(f"   💀 Event {event_num}: Processing failed - {message}", "red")

def print_agent_completion(agent_type, processed_count, total_events):
    """Print agent completion in CopyBot's exact format"""
    agent_configs = {
        'risk': {'african_emoji': '🐆', 'color': 'red'},
        'harvesting': {'african_emoji': '🦒', 'color': 'green'},
        'copybot': {'african_emoji': '🦁', 'color': 'yellow'},
        'staking': {'african_emoji': '🦅', 'color': 'magenta'},
        'defi': {'african_emoji': '🐘', 'color': 'cyan'}
    }
    
    config = agent_configs.get(agent_type, {'african_emoji': '💀', 'color': 'white'})
    
    # Print completion logs
    cprint(f"   {config['african_emoji']} Successfully processed {processed_count} events", config['color'])

def print_system_status():
    """Print epic gaming-style system status with skull and African Warrior theme"""
    cprint("\n💀 LIVE AGENT STATUS 💀", "red", attrs=["bold"])
    cprint("🔥" + "═" * 38 + "🔥", "red")
    
    # Webhook server status
    cprint(f"🌍 Webhook Server: 🟢 RUNNING", "yellow")
    
    # Agent coordination status (simplified)
    from src.scripts.shared_services.simple_agent_coordinator import get_simple_agent_coordinator
    coordinator = get_simple_agent_coordinator()
    current_agent = coordinator.get_status()['current_agent']
    
    if current_agent:
        cprint(f"🤖 Current Agent: {current_agent.upper()}", "yellow")
    else:
        cprint(f"🤖 Current Agent: IDLE", "yellow")
    
    # Add African Warrior status
    cprint(f"🦁 African Warrior Spirit @ MAXIMUM EFFICIENCY", "yellow")
    cprint(f"💀 Ancestral Blessings: RECEIVED", "red")
    
    cprint("🔥" + "═" * 38 + "🔥", "red")


def initialize_agents():
    """Initialize all trading agents with epic gaming-style progress and African Warrior theme"""
    global copybot_agent, risk_agent, harvesting_agent, master_agent
    
    try:
        cprint("\n💀 INITIALIZING AGENT AGENTS 💀", "red", attrs=["bold"])
        cprint("🔥" + "═" * 48 + "🔥", "red")
        
        # Step 1: Initialize CopyBot Agent
        print_initialization_progress(1, 5, "Initializing CopyBot Agent...")
        time.sleep(0.5)  # Visual delay for effect
        copybot_agent = CopyBotAgent()
        print()  # Ensure clean line break
        cprint(f"   🦁 CopyBot Agent initialized successfully", "yellow")
        cprint(f"   🤖 Primary trading agent ready for execution", "yellow")
        
        # Step 2: Initialize Risk Agent
        print_initialization_progress(2, 5, "Initializing Risk Agent...")
        time.sleep(0.5)  # Visual delay for effect
        from src.agents.risk_agent import get_risk_agent
        risk_agent = get_risk_agent()
        if risk_agent:
            risk_agent.start()  # Start hybrid monitoring
            print()  # Ensure clean line break
            cprint(f"   🐆 Risk Agent initialized successfully", "yellow")
            cprint(f"   🛡️ Emergency stop system ready", "yellow")
            cprint(f"   ⚡ Hybrid monitoring active", "yellow")
        else:
            cprint(f"   ❌ Risk Agent initialization failed", "red")
        
        # Step 3: Initialize Harvesting Agent
        print_initialization_progress(3, 5, "Initializing Harvesting Agent...")
        time.sleep(0.5)  # Visual delay for effect
        
        harvesting_agent = HarvestingAgent(enable_ai=True)
        print()  # Ensure clean line break
        cprint(f"   🌾 Harvesting Agent initialized successfully", "yellow")
        cprint(f"   🔄 Portfolio management system ready", "yellow")
        cprint(f"   ⚡ Hybrid monitoring active", "yellow")
        
        # Step 4: Initialize Master Agent
        print_initialization_progress(4, 5, "Initializing Master Agent...")
        time.sleep(0.5)  # Visual delay for effect
        
        master_agent = get_master_agent()
        master_agent.start()  # Start monitoring loop
        print()  # Ensure clean line break
        cprint(f"   👑 Master Agent initialized successfully", "yellow")
        cprint(f"   📊 System optimization and monitoring active", "yellow")
        cprint(f"   🎯 Monthly PnL goal: {master_agent.monthly_pnl_goal_percent}%", "yellow")
        
        # Step 5: Final coordination check
        print_initialization_progress(5, 5, "Checking for startup rebalancing...")
        time.sleep(0.5)  # Visual delay for effect
        print()  # Ensure clean line break
        
        # Startup rebalancing is handled by the harvesting agent during initialization
        # No need to call it again here to avoid double execution
        
        cprint(f"\n   🦏 Agent coordination system ready", "yellow")
        
        cprint("\n💀 ALL AGENTS INITIALIZED SUCCESSFULLY! 💀", "green", attrs=["bold"])
        cprint("🔥" + "═" * 48 + "🔥", "red")
        
        
        # Register local IP for webhook forwarding
        try:
            from src.scripts.shared_services.ip_registration_service import get_ip_registration_service
            ip_service = get_ip_registration_service()
            
            # Register IP on startup
            if ip_service.register_local_ip(port=8080):
                info("🌍 Local IP registered for webhook forwarding", file_only=True)
            else:
                warning("⚠️ IP registration failed - webhook forwarding may not work", file_only=True)
            
            # Start background registration
            ip_service.start_background_registration(port=8080)
            
        except Exception as e:
            warning(f"⚠️ IP registration service error: {e}", file_only=True)
        
        return True
        
    except Exception as e:
        cprint(f"\n💀 AGENT INITIALIZATION FAILED: {e} 💀", "red", attrs=["bold"])
        cprint("🔥" + "═" * 48 + "🔥", "red")
        traceback.print_exc()
        return False

@app.route('/webhook', methods=['POST'])
def receive_webhook():
    """Receive parsed webhook events from Render with beautiful display"""
    # Simple coordination - handled by SimpleAgentCoordinator
    
    try:
        data = request.get_json()
        events = data.get('events', [])
        
        if not events:
            print_webhook_event("blocked", 0, "No events in webhook payload")
            return jsonify({"status": "error", "message": "No events"}), 400
        
        
        print_webhook_event("received", len(events), f"From Render server")
        
        # Check if CopyBot can execute (simple priority check)
        from src.scripts.shared_services.simple_agent_coordinator import get_simple_agent_coordinator
        coordinator = get_simple_agent_coordinator()
        
        if not coordinator.start_execution('copybot'):
            print_webhook_event("deferred", len(events), "Higher priority agent running")
            return jsonify({"status": "deferred", "reason": "higher_priority_agent"}), 200
        processed_count = 0
        
        cprint(f"   🔥 Processing events with CopyBot Agent...", "yellow")
        
        # Process each parsed event with CopyBot
        for i, event in enumerate(events, 1):
            try:
                cprint(f"   💀 Event {i}/{len(events)}: Processing transaction...", "yellow")
                
                # CopyBot processes the fully parsed transaction
                result = copybot_agent.process_parsed_transaction(event)
                if result:
                    processed_count += 1
                    cprint(f"   🦁 Event {i}: Successfully processed", "yellow")
                else:
                    cprint(f"   ⚔️ Event {i}: No action taken", "yellow")
                    
            except Exception as e:
                cprint(f"   💀 Event {i}: Processing failed - {e}", "red")
        
        # Mark CopyBot execution complete
        coordinator.finish_execution('copybot')
        
        print_webhook_event("processed", processed_count, f"Out of {len(events)} total events")
        
        return jsonify({
            "status": "processed",
            "count": processed_count
        }), 200
        
    except Exception as e:
        cprint(f"\n❌ WEBHOOK RECEIVER ERROR: {e}", "red", attrs=["bold"])
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/webhook/hyperliquid', methods=['POST'])
def receive_webhook_hyperliquid():
    """Receive Hyperliquid fill events from WebSocket listener; forward to copybot process_hyperliquid_fill."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "No data"}), 400
        events = data.get("events", [])
        if not events:
            return jsonify({"status": "ok", "message": "No events"}), 200
        from src.scripts.shared_services.simple_agent_coordinator import get_simple_agent_coordinator
        coordinator = get_simple_agent_coordinator()
        if not coordinator.start_execution("copybot"):
            return jsonify({"status": "deferred", "reason": "higher_priority_agent"}), 200
        processed_count = 0
        for event in events:
            try:
                if copybot_agent and hasattr(copybot_agent, "process_hyperliquid_fill"):
                    if copybot_agent.process_hyperliquid_fill(event):
                        processed_count += 1
            except Exception as e:
                cprint(f"   Hyperliquid event error: {e}", "red")
        coordinator.finish_execution("copybot")
        return jsonify({"status": "processed", "count": processed_count}), 200
    except Exception as e:
        cprint(f"\n❌ HYPERLIQUID WEBHOOK ERROR: {e}", "red", attrs=["bold"])
        return jsonify({"status": "error", "message": str(e)}), 500


# Coordination functions removed - now handled by Portfolio Tracker trigger system

def status_endpoint():
    """Health check and status endpoint"""
    master_status = master_agent.get_status() if master_agent else {}
    
    return jsonify({
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "agents": {
            "copybot": copybot_agent is not None,
            "risk": risk_agent is not None,
            "harvesting": harvesting_agent is not None,
            "master": master_agent is not None
        },
        "coordinator": {
            "current_agent": "idle"  # Simplified status
        },
        "master_agent": master_status
    })

@app.route('/master/status', methods=['GET'])
def master_status_endpoint():
    """Get detailed Master Agent status"""
    if not master_agent:
        return jsonify({"error": "Master Agent not initialized"}), 503
    
    return jsonify(master_agent.get_status())

@app.route('/master/suggestions', methods=['GET'])
def master_suggestions_endpoint():
    """Get pending trading config suggestions"""
    if not master_agent:
        return jsonify({"error": "Master Agent not initialized"}), 503
    
    from src.scripts.shared_services.config_manager import get_config_manager
    config_manager = get_config_manager()
    
    suggestions = config_manager.get_pending_suggestions()
    
    return jsonify({
        "suggestions": [
            {
                "parameter": s.parameter,
                "current_value": s.old_value,
                "suggested_value": s.new_value,
                "reason": s.reason,
                "confidence": s.confidence,
                "timestamp": s.timestamp
            }
            for s in suggestions
        ]
    })

@app.route('/master/approve/<parameter>', methods=['POST'])
def master_approve_endpoint(parameter):
    """Approve a pending trading config suggestion"""
    if not master_agent:
        return jsonify({"error": "Master Agent not initialized"}), 503
    
    success = master_agent.approve_trading_config(parameter)
    
    if success:
        return jsonify({"status": "approved", "parameter": parameter})
    else:
        return jsonify({"status": "failed", "parameter": parameter}), 400

@app.route('/master/decisions', methods=['GET'])
def master_decisions_endpoint():
    """Get recent Master Agent decisions"""
    if not master_agent:
        return jsonify({"error": "Master Agent not initialized"}), 503
    
    limit = request.args.get('limit', 10, type=int)
    decisions = master_agent.get_recent_decisions(limit=limit)
    
    return jsonify({"decisions": decisions})

app.add_url_rule('/status', 'status', status_endpoint, methods=['GET'])

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    cprint("\n\n💀 RECEIVED SHUTDOWN SIGNAL 💀", "yellow", attrs=["bold"])
    stop_ngrok()
    sys.exit(0)

def trigger_initial_harvesting_check():
    """Trigger harvesting agent for initial portfolio check after Flask server starts"""
    try:
        # Small delay to ensure Flask server is fully started
        time.sleep(1)
        
        cprint("\n🌾 TRIGGERING INITIAL PORTFOLIO CHECK 💀", "yellow", attrs=["bold"])
        cprint("🔥" + "═" * 38 + "🔥", "red")
        
        # Disable initialization mode
        from src.scripts.trading.portfolio_tracker import get_portfolio_tracker
        portfolio_tracker = get_portfolio_tracker()
        portfolio_tracker.initialization_mode = False
        portfolio_tracker.initialization_complete_time = time.time()
        
        # Trigger harvesting agent for initial check
        from src.agents.harvesting_agent import get_harvesting_agent
        harvesting_agent = get_harvesting_agent()
        
        # Get current snapshot
        current_snapshot = portfolio_tracker.current_snapshot
        if current_snapshot:
            cprint("🔍 Checking portfolio for rebalancing needs...", "cyan")
            harvesting_agent._execute_interval_based_checks()
            cprint("✅ Initial portfolio check completed", "green")
        else:
            cprint("⚠️ No portfolio snapshot available for initial check", "yellow")
        
        cprint("🔥" + "═" * 38 + "🔥", "red")
        
    except Exception as e:
        cprint(f"❌ Error in initial harvesting check: {e}", "red")

def main():
    """Main coordinator function with beautiful startup sequence"""
    try:
        # Set up signal handlers for clean shutdown
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        # Clear screen and show startup banner
        os.system('cls' if os.name == 'nt' else 'clear')
        print_startup_banner()
        
        # Show system configuration
        print_system_info()
        
        # Show agent dashboard
        print_agent_dashboard()
        
        cprint("\n💀 STARTING AGENT TRADING COORDINATOR 💀", "red", attrs=["bold"])
        cprint("🔥" + "═" * 48 + "🔥", "red")
        cprint("🌍 Receiving webhook events from Render server", "cyan")
        cprint("🤖 Coordinating local trading AGENTs", "cyan")
        cprint("🔥" + "═" * 48 + "🔥", "red")
        
        # Initialize all trading agents
        if not initialize_agents():
            cprint("\n💀 FAILED TO INITIALIZE AGENTS - CANNOT CONTINUE 💀", "red", attrs=["bold"])
            cprint("🔥" + "═" * 48 + "🔥", "red")
            return
        
        # Show agent responsibilities
        cprint("\n💀 AGENT RESPONSIBILITIES 💀", "red", attrs=["bold"])
        cprint("🔥" + "═" * 38 + "🔥", "red")
        cprint("🤖 CopyBot Agent:", "yellow", attrs=["bold"])
        cprint("   ⚔️ All trading decisions and execution", "yellow")
        cprint("   🦁 Primary trading AGENT for webhook events", "yellow")
        cprint("")
        cprint("🛡️ Risk Agent:", "yellow", attrs=["bold"])
        cprint("   ⚔️ Emergency stops only", "yellow")
        cprint("   🐆 consecutive losses, drawdown, SOL/USDC balance", "yellow")
        cprint("")
        cprint("🌾 Harvesting Agent:", "yellow", attrs=["bold"])
        cprint("   ⚔️ SOL/USDC rebalancing and realized gains reallocation", "yellow")
        cprint("   🦒 Portfolio tracker triggered executions", "yellow")
        cprint("")
        cprint("🔥" + "═" * 38 + "🔥", "red")
        
        # Start background risk monitoring
        cprint("\n💀 STARTING BACKGROUND MONITORING 💀", "red", attrs=["bold"])
        cprint("🔥" + "═" * 38 + "🔥", "red")
        cprint("🛡️ Portfolio Tracker will handle agent triggering...", "yellow")
        cprint("🦁 Background monitoring active", "yellow")
        cprint("🔥" + "═" * 38 + "🔥", "red")
        
        # Start ngrok tunnel
        cprint("\n💀 STARTING NGROK TUNNEL 💀", "red", attrs=["bold"])
        cprint("🔥" + "═" * 38 + "🔥", "red")
        
        if start_ngrok():
            # Wait a bit more for ngrok to fully initialize
            time.sleep(3)
            
            ngrok_url = get_ngrok_url()
            if ngrok_url:
                cprint(f"🌐 ngrok URL: {ngrok_url}", "green")
                cprint("🔗 Webhook will be accessible from Render server", "green")
                
                # Verify ngrok is actually working
                cprint("🔍 Verifying ngrok connection...", "yellow")
                if is_ngrok_running():
                    cprint("✅ ngrok tunnel verified and working", "green")
                    
                    # Detect the actual port from ngrok
                    detected_port = 8080  # default
                    try:
                        import requests
                        response = requests.get("http://localhost:4040/api/tunnels", timeout=2)
                        if response.status_code == 200:
                            tunnels = response.json()
                            for tunnel in tunnels.get('tunnels', []):
                                if tunnel.get('proto') == 'https':
                                    config = tunnel.get('config', {})
                                    addr = config.get('addr', '')
                                    if ':' in addr:
                                        detected_port = int(addr.split(':')[-1])
                                        cprint(f"🔍 Detected ngrok port: {detected_port}", "yellow")
                                    break
                    except Exception as e:
                        cprint(f"⚠️ Could not detect ngrok port, using default 8080: {e}", "yellow")
                    
                    # Register ngrok URL with IP registration service
                    try:
                        from src.scripts.shared_services.ip_registration_service import get_ip_registration_service
                        ip_service = get_ip_registration_service()
                        
                        # Re-register with ngrok URL and detected port
                        if ip_service.register_local_ip(port=detected_port, ngrok_url=ngrok_url):
                            cprint(f"🌐 ngrok URL registered for webhook forwarding: {ngrok_url} (port: {detected_port})", "green")
                        else:
                            cprint("⚠️ Failed to register ngrok URL - webhook forwarding may not work", "yellow")
                            
                    except Exception as e:
                        cprint(f"⚠️ Error registering ngrok URL: {e}", "yellow")
                else:
                    cprint("⚠️ ngrok started but connection verification failed", "yellow")
            else:
                cprint("⚠️ ngrok started but URL not detected", "yellow")
                cprint("💡 Trying to get URL again in 3 seconds...", "yellow")
                time.sleep(3)
                ngrok_url = get_ngrok_url()
                if ngrok_url:
                    cprint(f"🌐 ngrok URL (retry): {ngrok_url}", "green")
                    
                    # Detect the actual port from ngrok
                    detected_port = 8080  # default
                    try:
                        import requests
                        response = requests.get("http://localhost:4040/api/tunnels", timeout=2)
                        if response.status_code == 200:
                            tunnels = response.json()
                            for tunnel in tunnels.get('tunnels', []):
                                if tunnel.get('proto') == 'https':
                                    config = tunnel.get('config', {})
                                    addr = config.get('addr', '')
                                    if ':' in addr:
                                        detected_port = int(addr.split(':')[-1])
                                        cprint(f"🔍 Detected ngrok port: {detected_port}", "yellow")
                                    break
                    except Exception as e:
                        cprint(f"⚠️ Could not detect ngrok port, using default 8080: {e}", "yellow")
                    
                    # Register ngrok URL with IP registration service
                    try:
                        from src.scripts.shared_services.ip_registration_service import get_ip_registration_service
                        ip_service = get_ip_registration_service()
                        
                        # Re-register with ngrok URL and detected port
                        if ip_service.register_local_ip(port=detected_port, ngrok_url=ngrok_url):
                            cprint(f"🌐 ngrok URL registered for webhook forwarding: {ngrok_url} (port: {detected_port})", "green")
                        else:
                            cprint("⚠️ Failed to register ngrok URL - webhook forwarding may not work", "yellow")
                            
                    except Exception as e:
                        cprint(f"⚠️ Error registering ngrok URL: {e}", "yellow")
                else:
                    cprint("❌ Still unable to detect ngrok URL", "red")
        else:
            cprint("❌ Failed to start ngrok - webhook forwarding may not work", "red")
            cprint("💡 Make sure ngrok.exe is in the project root directory", "yellow")
        
        cprint("🔥" + "═" * 38 + "🔥", "red")
        
        # Start webhook server
        cprint("\n💀 STARTING WEBHOOK SERVER 💀", "red", attrs=["bold"])
        cprint("🔥" + "═" * 38 + "🔥", "red")
        cprint("🎯 Webhook endpoint: http://localhost:8080/webhook", "green")
        cprint("📊 Status endpoint: http://localhost:8080/status", "green")
        cprint("🔗 Health check: http://localhost:8080/status", "green")
        cprint("🔥" + "═" * 38 + "🔥", "red")
        
        # Show final status
        cprint("\n💀 AGENT TRADING COORDINATOR IS READY! 💀", "yellow", attrs=["bold"])
        cprint("🔥" + "═" * 48 + "🔥", "red")
        cprint("🌍 Waiting for webhook events from Render server...", "cyan")
        cprint("⌨️  Press Ctrl+C to stop the coordinator", "yellow")
        cprint("🔥" + "═" * 48 + "🔥", "red")
        
        # Show system status
        print_system_status()
        
        # Start harvesting check in background thread after Flask server starts
        import threading
        harvesting_thread = threading.Thread(target=trigger_initial_harvesting_check, daemon=True)
        harvesting_thread.start()
        
        # Start Flask server to receive webhook events
        app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)
        
    except KeyboardInterrupt:
        cprint("\n\n💀 SHUTTING DOWN AGENT TRADING COORDINATOR 💀", "yellow", attrs=["bold"])
        cprint("🔥" + "═" * 48 + "🔥", "red")
        cprint("🛑 Stopping webhook server...", "red")
        cprint("🛑 Stopping background monitoring...", "red")
        cprint("🛑 Stopping ngrok tunnel...", "red")
        stop_ngrok()
        cprint("🦁 Shutdown complete", "yellow")
        cprint("🔥" + "═" * 48 + "🔥", "red")
    except Exception as e:
        cprint(f"\n💀 FATAL ERROR IN AGENT TRADING COORDINATOR: {e} 💀", "red", attrs=["bold"])
        cprint("🔥" + "═" * 48 + "🔥", "red")
        traceback.print_exc()

if __name__ == "__main__":
    main()
