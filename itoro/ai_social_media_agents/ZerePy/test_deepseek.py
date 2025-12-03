#!/usr/bin/env python3
"""
Test script for DeepSeek connection in ZerePy
"""
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# Load environment variables
import os
os.environ['DEEPSEEK_KEY'] = 'sk-8954c2a2ed664a43ba110ece54595444'

from connections.deepseek_connection import DeepSeekConnection

def test_deepseek_connection():
    """Test the DeepSeek connection"""
    print("🧪 Testing DeepSeek Connection for ZerePy")
    print("=" * 50)

    # Check environment
    deepseek_key = os.getenv('DEEPSEEK_KEY')
    if deepseek_key:
        print(f"✅ DEEPSEEK_KEY found: {deepseek_key[:10]}...")
    else:
        print("❌ DEEPSEEK_KEY not found in environment")
        return False

    # Create connection
    try:
        config = {'model': 'deepseek-chat'}
        conn = DeepSeekConnection(config)
        print("✅ DeepSeek connection created")
    except Exception as e:
        print(f"❌ Failed to create connection: {e}")
        return False

    # Test configuration
    try:
        is_configured = conn.is_configured(verbose=True)
        if is_configured:
            print("✅ DeepSeek API is configured and accessible")
        else:
            print("❌ DeepSeek API configuration failed")
            return False
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False

    # Test text generation
    try:
        print("\n🧠 Testing text generation...")
        test_prompt = "Hello! Can you confirm you're working with ZerePy?"
        response = conn.generate_text(test_prompt, max_tokens=100)
        print(f"✅ Generated response: {response[:100]}...")
        print("✅ DeepSeek text generation working!")
    except Exception as e:
        print(f"❌ Text generation failed: {e}")
        return False

    print("\n🎉 All DeepSeek tests passed! Ready for ZerePy integration.")
    return True

if __name__ == "__main__":
    success = test_deepseek_connection()
    sys.exit(0 if success else 1)
