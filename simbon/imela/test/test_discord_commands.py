#!/usr/bin/env python3
"""
Comprehensive Discord Commands Test Suite
Tests all 25 Discord actions to ensure they work correctly.
"""

import sys
import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add parent directory (ai_social_media_agents) to path
# Structure: ai_social_media_agents/ZerePy/test_discord_commands.py
#            ai_social_media_agents/src/agent.py
current_dir = Path(__file__).parent
parent_dir = current_dir.parent  # This is ai_social_media_agents/
sys.path.insert(0, str(parent_dir))

# Also change to parent directory so relative paths work
os.chdir(parent_dir)

# Load environment variables from ITORO root .env file
def load_env_from_root():
    """Load .env from ITORO root directory"""
    try:
        # Path: ITORO/itoro/ai_social_media_agents/test/test_discord_commands.py
        # Need: ITORO/.env
        current = Path(__file__).parent  # test directory
        itoro_root = current.parent.parent.parent / '.env'  # ITORO/.env
        
        if itoro_root.exists():
            # Read .env file manually to avoid null character issues
            with open(itoro_root, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                # Remove null characters
                content = content.replace('\x00', '')
                # Split by lines
                for line in content.split('\n'):
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        try:
                            key, value = line.split('=', 1)
                            key = key.strip()
                            value = value.strip().strip('"').strip("'")
                            # Only set ZerePy-relevant keys if not already set
                            zerepy_keys = ['DEEPSEEK_KEY', 'DISCORD_BOT_TOKEN', 'YOUTUBE_CLIENT_ID', 
                                          'YOUTUBE_CLIENT_SECRET', 'TWITTER_CONSUMER_KEY', 
                                          'TWITTER_CONSUMER_SECRET', 'TWITTER_ACCESS_TOKEN',
                                          'TWITTER_ACCESS_TOKEN_SECRET', 'TWITTER_USER_ID']
                            if key in zerepy_keys and key and value and not os.getenv(key):
                                os.environ[key] = value
                        except Exception:
                            continue
    except Exception:
        pass

# Load environment variables before importing agent
load_env_from_root()

from src.agent import ZerePyAgent

# Test configuration - UPDATE THESE VALUES WITH YOUR ACTUAL IDs
TEST_CONFIG = {
    "guild_id": "1445575379321360527",  # Your guild ID
    "channel_id": None,  # Will be dynamically discovered
    "user_id": "701114427415724053",  # Your user ID (for member operations)
    "voice_channel_id": None,  # Will be created during testing
    "test_role_id": None,  # Will be created during testing
    "test_message_id": None,  # Will be stored after sending test message
}

def get_test_channel_id():
    """Dynamically get a valid text channel ID from the server"""
    try:
        # Load agent temporarily to get server info
        agent = ZerePyAgent("example")
        result = agent.connection_manager.perform_action("discord", "get-server-info", [])

        if result and "channels" in result:
            # Find first text channel
            for channel in result["channels"]:
                if channel.get("type") == "text":
                    print(f"Found valid text channel: {channel['name']} ({channel['id']})")
                    return channel["id"]
        else:
            print("Warning: get-server-info did not return channel information")
    except Exception as e:
        print(f"Warning: Could not get test channel ID: {e}")

    # Fallback to hardcoded ID if dynamic discovery fails
    fallback_id = "1445575380336513138"
    print(f"Warning: Using fallback channel ID: {fallback_id}")
    return fallback_id

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_header(text: str):
    """Print a formatted header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text.center(70)}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.RESET}\n")

def print_test(test_name: str, status: str, details: str = ""):
    """Print test result"""
    status_colors = {
        "PASSED": Colors.GREEN,
        "FAILED": Colors.RED,
        "SKIPPED": Colors.YELLOW
    }
    color = status_colors.get(status, Colors.RESET)
    symbol = "✅" if status == "PASSED" else "❌" if status == "FAILED" else "⏭️"
    print(f"{symbol} {color}{status}{Colors.RESET} - {test_name}")
    if details:
        print(f"   {details}")

def format_params(params: Dict[str, Any]) -> List[str]:
    """Convert params dict to list of key=value strings for agent.perform_action"""
    result = []
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, str) and ' ' in value:
            result.append(f'{key}="{value}"')
        elif isinstance(value, bool):
            result.append(f'{key}={str(value).lower()}')
        elif isinstance(value, (list, dict)):
            # For complex types, convert to JSON string
            result.append(f'{key}={json.dumps(value)}')
        else:
            result.append(f'{key}={value}')
    return result

def test_discord_actions():
    """Test all Discord actions"""
    
    # Check for --safe flag
    safe_mode = "--safe" in sys.argv or "-s" in sys.argv
    
    print_header("DISCORD COMMANDS TEST SUITE")
    
    if safe_mode:
        print(f"{Colors.YELLOW}⚠️  SAFE MODE ENABLED - Only read-only tests will run{Colors.RESET}\n")
    
    # Load agent
    try:
        print(f"{Colors.BLUE}Loading agent...{Colors.RESET}")
        agent = ZerePyAgent("example")
        print(f"{Colors.GREEN}✅ Agent loaded: {agent.name}{Colors.RESET}\n")
    except Exception as e:
        print(f"{Colors.RED}❌ Failed to load agent: {e}{Colors.RESET}")
        return None
    
    # Verify Discord connection
    if "discord" not in agent.connection_manager.connections:
        print(f"{Colors.RED}❌ Discord connection not found in agent config{Colors.RESET}")
        return None
    
    discord_conn = agent.connection_manager.connections["discord"]
    if not discord_conn.is_configured():
        print(f"{Colors.RED}❌ Discord connection is not configured{Colors.RESET}")
        print(f"{Colors.YELLOW}Checking environment variables...{Colors.RESET}")
        token = os.getenv('DISCORD_BOT_TOKEN')
        if token:
            print(f"{Colors.GREEN}✅ DISCORD_BOT_TOKEN found in environment{Colors.RESET}")
            print(f"{Colors.YELLOW}Token preview: {token[:20]}...{Colors.RESET}")
            print(f"{Colors.YELLOW}The connection may need to be configured through the CLI first.{Colors.RESET}")
        else:
            print(f"{Colors.RED}❌ DISCORD_BOT_TOKEN not found in environment{Colors.RESET}")
            print(f"{Colors.YELLOW}Make sure your .env file is in ITORO root and contains DISCORD_BOT_TOKEN{Colors.RESET}")
        return None
    
    print(f"{Colors.GREEN}✅ Discord connection configured{Colors.RESET}\n")

    # Get a valid channel ID for testing
    print(f"{Colors.BLUE}Getting test channel ID...{Colors.RESET}")
    TEST_CONFIG["channel_id"] = get_test_channel_id()
    print(f"{Colors.GREEN}✅ Using channel ID: {TEST_CONFIG['channel_id']}{Colors.RESET}\n")

    # Define all test cases
    test_cases = [
        # === READ-ONLY TESTS (Safe) ===
        {
            "name": "get-server-info",
            "action": "get-server-info",
            "params": {},
            "safe": True,
            "description": "Get detailed information about the Discord server"
        },
        {
            "name": "get-channel-activity (specific channel)",
            "action": "get-channel-activity",
            "params": {
                "channel_id": TEST_CONFIG["channel_id"],
                "hours_back": 24
            },
            "safe": True,
            "description": "Get activity statistics for a specific channel"
        },
        {
            "name": "get-channel-activity (all channels)",
            "action": "get-channel-activity",
            "params": {
                "hours_back": 24
            },
            "safe": True,
            "description": "Get activity statistics for all channels"
        },
        {
            "name": "get-member-info",
            "action": "get-member-info",
            "params": {
                "user_id": TEST_CONFIG["user_id"]
            },
            "safe": True,
            "description": "Get detailed information about a server member"
        },
        
        # === MESSAGE TESTS ===
        {
            "name": "send-message (simple)",
            "action": "send-message",
            "params": {
                "channel_id": TEST_CONFIG["channel_id"],
                "content": "🧪 Test message from automated test suite - Simple"
            },
            "safe": False,
            "description": "Send a simple text message",
            "store_result": "message_id"
        },
        {
            "name": "send-message (with embed)",
            "action": "send-message",
            "params": {
                "channel_id": TEST_CONFIG["channel_id"],
                "content": "Test embed message",
                "embed_title": "Test Embed",
                "embed_description": "This is a test embed created by the automated test suite",
                "embed_color": "#FF0000"
            },
            "safe": False,
            "description": "Send a message with embed"
        },
        {
            "name": "delete-message",
            "action": "delete-message",
            "params": {
                "channel_id": TEST_CONFIG["channel_id"],
                "message_id": None  # Will be set from previous test
            },
            "safe": False,
            "description": "Delete a specific message",
            "depends_on": "send-message (simple)"
        },
        
        # === CHANNEL TESTS ===
        {
            "name": "create-channel (text)",
            "action": "create-channel",
            "params": {
                "name": "test-channel-auto",
                "channel_type": "text",
                "topic": "Automated test channel - will be deleted"
            },
            "safe": False,
            "description": "Create a new text channel",
            "store_result": "channel_id",
            "cleanup": "delete-channel"
        },
        {
            "name": "create-channel (voice)",
            "action": "create-channel",
            "params": {
                "name": "test-voice-auto",
                "channel_type": "voice",
                "user_limit": 5
            },
            "safe": False,
            "description": "Create a new voice channel",
            "store_result": "voice_channel_id",
            "cleanup": "delete-channel"
        },
        {
            "name": "create-channel (category)",
            "action": "create-channel",
            "params": {
                "name": "test-category-auto",
                "channel_type": "category"
            },
            "safe": False,
            "description": "Create a new category channel",
            "store_result": "category_id",
            "cleanup": "delete-channel"
        },
        
        # === ROLE TESTS ===
        {
            "name": "create-role",
            "action": "create-role",
            "params": {
                "name": "TestRole-Auto",
                "color": "#00FF00"
            },
            "safe": False,
            "description": "Create a new role",
            "store_result": "role_id"
        },
        {
            "name": "assign-role",
            "action": "assign-role",
            "params": {
                "user_id": TEST_CONFIG["user_id"],
                "role_id": None  # Will be set from create-role
            },
            "safe": False,
            "description": "Assign a role to a member",
            "depends_on": "create-role"
        },
        {
            "name": "remove-role",
            "action": "remove-role",
            "params": {
                "user_id": TEST_CONFIG["user_id"],
                "role_id": None  # Will be set from create-role
            },
            "safe": False,
            "description": "Remove a role from a member",
            "depends_on": "create-role"
        },
        
        # === VOICE CHANNEL TESTS ===
        {
            "name": "create-voice-channel",
            "action": "create-voice-channel",
            "params": {
                "name": "test-voice-direct",
                "user_limit": 10
            },
            "safe": False,
            "description": "Create a voice channel using dedicated action",
            "store_result": "voice_channel_id_2",
            "cleanup": "delete-channel"
        },
        {
            "name": "move-member",
            "action": "move-member",
            "params": {
                "user_id": TEST_CONFIG["user_id"],
                "channel_id": None  # Will be set from create-voice-channel
            },
            "safe": False,
            "description": "Move a member to a voice channel",
            "depends_on": "create-voice-channel",
            "skip_by_default": True  # Skip unless explicitly testing (requires user to be in voice)
        },
        
        # === MODERATION TESTS (Use with caution!) ===
        {
            "name": "timeout-member (1 minute)",
            "action": "timeout-member",
            "params": {
                "user_id": TEST_CONFIG["user_id"],
                "duration_seconds": 60,  # 1 minute timeout
                "reason": "Automated test - will be removed immediately"
            },
            "safe": False,
            "description": "Timeout a member for 1 minute",
            "skip_by_default": True  # Skip unless --moderation flag is used
        },
        {
            "name": "remove-timeout",
            "action": "remove-timeout",
            "params": {
                "user_id": TEST_CONFIG["user_id"]
            },
            "safe": False,
            "description": "Remove timeout from a member",
            "depends_on": "timeout-member (1 minute)",
            "skip_by_default": True
        },
        
        # === BULK OPERATIONS ===
        {
            "name": "bulk-delete-messages",
            "action": "bulk-delete-messages",
            "params": {
                "channel_id": TEST_CONFIG["channel_id"],
                "count": 5,
                "reason": "Automated test cleanup"
            },
            "safe": False,
            "description": "Bulk delete messages (last 5)",
            "skip_by_default": True  # Skip unless explicitly testing
        },
        
        # === WELCOME/AUTO-MOD TESTS ===
        {
            "name": "set-welcome-message",
            "action": "set-welcome-message",
            "params": {
                "channel_id": TEST_CONFIG["channel_id"],
                "message": "Welcome to the server! 🎉",
                "enabled": True
            },
            "safe": False,
            "description": "Configure welcome messages"
        },
        {
            "name": "enable-auto-mod",
            "action": "enable-auto-mod",
            "params": {
                "enabled": True,
                "spam_threshold": 5,
                "blocked_words": ["spam", "test"]
            },
            "safe": False,
            "description": "Enable auto-moderation"
        },
        
        # === SCHEDULED EVENTS ===
        {
            "name": "create-scheduled-event",
            "action": "create-scheduled-event",
            "params": {
                "name": "Test Event - Auto",
                "description": "This is a test event created by automated test suite",
                "start_time": "2025-12-10T12:00:00Z",
                "end_time": "2025-12-10T14:00:00Z"
            },
            "safe": False,
            "description": "Create a scheduled event",
            "skip_by_default": True  # Events can't be easily deleted
        },
    ]
    
    # Track results
    results = {
        "passed": [],
        "failed": [],
        "skipped": []
    }
    
    # Track created resources for cleanup
    created_resources = {
        "channels": [],
        "roles": [],
        "messages": []
    }
    
    # Check for moderation flag
    test_moderation = "--moderation" in sys.argv or "-m" in sys.argv
    
    print(f"{Colors.BOLD}Testing {len(test_cases)} Discord actions...{Colors.RESET}\n")
    
    # Execute tests
    for i, test in enumerate(test_cases, 1):
        test_num = f"[{i}/{len(test_cases)}]"
        
        # Skip if safe mode and not safe
        if safe_mode and not test.get("safe", False):
            print_test(f"{test_num} {test['name']}", "SKIPPED", "Safe mode enabled")
            results["skipped"].append(test["name"])
            continue
        
        # Skip if skip_by_default and flag not set
        if test.get("skip_by_default", False) and not test_moderation:
            print_test(f"{test_num} {test['name']}", "SKIPPED", "Use --moderation to test")
            results["skipped"].append(test["name"])
            continue
        
        # Handle dependencies
        if "depends_on" in test:
            dep_name = test["depends_on"]
            if dep_name not in [r["name"] for r in results["passed"]]:
                print_test(f"{test_num} {test['name']}", "SKIPPED", f"Depends on: {dep_name}")
                results["skipped"].append(test["name"])
                continue
        
        # Update params with stored values
        params = test["params"].copy()
        if "message_id" in params and params["message_id"] is None:
            if created_resources["messages"]:
                params["message_id"] = created_resources["messages"][-1]
            else:
                print_test(f"{test_num} {test['name']}", "SKIPPED", "No message ID available")
                results["skipped"].append(test["name"])
                continue
        
        if "role_id" in params and params["role_id"] is None:
            if created_resources["roles"]:
                params["role_id"] = created_resources["roles"][-1]
            else:
                print_test(f"{test_num} {test['name']}", "SKIPPED", "No role ID available")
                results["skipped"].append(test["name"])
                continue
        
        if "channel_id" in params and params["channel_id"] is None and test.get("depends_on") == "create-voice-channel":
            # Find the voice channel from created resources
            if created_resources["channels"]:
                # Use the last created channel (should be the voice channel)
                params["channel_id"] = created_resources["channels"][-1]
            else:
                print_test(f"{test_num} {test['name']}", "SKIPPED", "No voice channel ID available")
                results["skipped"].append(test["name"])
                continue
        
        # Execute test
        try:
            print(f"{test_num} {Colors.BLUE}Testing: {test['name']}{Colors.RESET}")
            print(f"   {Colors.YELLOW}{test['description']}{Colors.RESET}")
            
            # Format params for agent
            param_list = format_params(params)
            
            # Execute
            result = agent.connection_manager.perform_action(
                connection_name="discord",
                action_name=test["action"],
                params=param_list
            )
            
            # Check if result is None (indicates failure)
            if result is None:
                print_test(f"{test_num} {test['name']}", "FAILED", "Action returned None (likely an error occurred)")
                results["failed"].append({
                    "name": test["name"],
                    "error": "Action returned None - check logs for details"
                })
                print()  # Blank line between tests
                continue
            
            # Store results for dependent tests
            if "store_result" in test:
                store_key = test["store_result"]
                if isinstance(result, dict):
                    if "channel_id" in result:
                        created_resources["channels"].append(result["channel_id"])
                    if "role_id" in result:
                        created_resources["roles"].append(result["role_id"])
                    if "message_id" in result:
                        created_resources["messages"].append(result["message_id"])
            
            print_test(f"{test_num} {test['name']}", "PASSED", f"Result: {str(result)[:80]}...")
            results["passed"].append({
                "name": test["name"],
                "result": result
            })
            
        except Exception as e:
            error_msg = str(e)[:100]
            print_test(f"{test_num} {test['name']}", "FAILED", error_msg)
            results["failed"].append({
                "name": test["name"],
                "error": str(e)
            })
        
        print()  # Blank line between tests
    
    # Cleanup created resources
    if created_resources["channels"] or created_resources["roles"]:
        print_header("CLEANUP")
        
        # Delete channels
        for channel_id in created_resources["channels"]:
            try:
                print(f"{Colors.YELLOW}Deleting channel: {channel_id}{Colors.RESET}")
                param_list = format_params({"channel_id": channel_id})
                agent.connection_manager.perform_action("discord", "delete-channel", param_list)
                print(f"  {Colors.GREEN}✅ Deleted{Colors.RESET}")
            except Exception as e:
                print(f"  {Colors.RED}❌ Failed: {e}{Colors.RESET}")
        
        # Note: Roles can't be easily deleted via API
        if created_resources["roles"]:
            print(f"\n{Colors.YELLOW}⚠️  Note: {len(created_resources['roles'])} role(s) were created.{Colors.RESET}")
            print(f"{Colors.YELLOW}   Manual cleanup may be required in Discord.{Colors.RESET}")
    
    # Print summary
    print_header("TEST SUMMARY")
    
    print(f"{Colors.GREEN}✅ Passed: {len(results['passed'])}{Colors.RESET}")
    print(f"{Colors.RED}❌ Failed: {len(results['failed'])}{Colors.RESET}")
    print(f"{Colors.YELLOW}⏭️  Skipped: {len(results['skipped'])}{Colors.RESET}")
    
    if results["failed"]:
        print(f"\n{Colors.RED}{Colors.BOLD}Failed Tests:{Colors.RESET}")
        for failure in results["failed"]:
            print(f"  {Colors.RED}• {failure['name']}{Colors.RESET}")
            print(f"    {failure['error'][:100]}")
    
    if results["passed"]:
        print(f"\n{Colors.GREEN}{Colors.BOLD}Passed Tests:{Colors.RESET}")
        for passed in results["passed"][:10]:  # Show first 10
            print(f"  {Colors.GREEN}• {passed['name']}{Colors.RESET}")
        if len(results["passed"]) > 10:
            print(f"  ... and {len(results['passed']) - 10} more")
    
    return results

if __name__ == "__main__":
    print(f"""
{Colors.BOLD}{Colors.BLUE}
╔══════════════════════════════════════════════════════════════════╗
║         ZerePy Discord Commands Test Suite                      ║
╚══════════════════════════════════════════════════════════════════╝
{Colors.RESET}

{Colors.YELLOW}Usage:{Colors.RESET}
  python test_discord_commands.py              # Run all tests
  python test_discord_commands.py --safe       # Run only read-only tests
  python test_discord_commands.py --moderation # Include moderation tests

{Colors.YELLOW}Before running:{Colors.RESET}
  1. Update TEST_CONFIG in this file with your actual IDs
  2. Ensure Discord bot is configured and has proper permissions
  3. Start with --safe flag to test read-only operations first

{Colors.BOLD}Press Enter to continue or Ctrl+C to cancel...{Colors.RESET}
    """)
    
    try:
        input()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Cancelled.{Colors.RESET}")
        sys.exit(0)
    
    try:
        results = test_discord_actions()
        if results:
            exit_code = 0 if len(results["failed"]) == 0 else 1
            sys.exit(exit_code)
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Test interrupted by user{Colors.RESET}")
        sys.exit(130)
    except Exception as e:
        print(f"\n{Colors.RED}❌ Fatal error: {e}{Colors.RESET}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

