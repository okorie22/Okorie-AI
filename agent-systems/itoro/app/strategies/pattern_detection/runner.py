#!/usr/bin/env python
"""
SolPattern Detector Launcher
Run this from the main project directory to launch the pattern detector service
"""

import sys
import os

def main():
    """Launch the pattern detector service"""

    # Get the absolute path to the pattern-detector directory
    # This script is in src/, so we need to go up one level to find pattern-detector
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)  # Go up from src/ to project root
    pattern_detector_path = os.path.join(current_dir, 'pattern-detector')

    # Add pattern-detector directory to Python path for imports
    sys.path.insert(0, pattern_detector_path)

    print("SolPattern Detector Launcher")
    print("=" * 50)
    print(f"Project root: {project_root}")
    print(f"Pattern detector path: {pattern_detector_path}")
    print(f"Python executable: {sys.executable}")
    print(f"Python version: {sys.version}")
    print("=" * 50)

    try:
        # Test imports
        print("\n[TEST] Testing imports...")
        from pattern_detector import PatternDetector
        from data_fetcher import BinanceDataFetcher
        from alert_system import AlertSystem
        from pattern_storage import PatternStorage
        from pattern_service import PatternService
        print("[OK] All imports successful")

        # Test TA-Lib availability
        try:
            import talib
            print("[OK] TA-Lib available")
        except ImportError:
            print("[WARN] TA-Lib not available - some features may be limited")

        # Test other dependencies
        try:
            import pandas as pd
            import numpy as np
            print("[OK] Pandas and NumPy available")
        except ImportError:
            print("[ERROR] Pandas/NumPy missing - critical error")
            return

        try:
            from openai import OpenAI
            print("[OK] OpenAI available")
        except ImportError:
            print("[WARN] OpenAI not available - AI analysis disabled")

        try:
            from plyer import notification
            print("[OK] Plyer available - desktop notifications enabled")
        except ImportError:
            print("[WARN] Plyer not available - desktop notifications disabled")

        print("\n[LAUNCH] Launching Pattern Detector Service...")

        # Import and run the main function
        from pattern_service import main as service_main
        service_main()

    except ImportError as e:
        print(f"\n[ERROR] Import Error: {e}")
        print("\n[TROUBLESHOOT] Troubleshooting:")
        print("1. Check if you're in the correct directory")
        print("2. Verify Python environment has required packages")
        print("3. Try: pip install TA-Lib openai plyer python-dotenv pandas numpy")
        print("4. Check if src/pattern-detector/ directory exists")

        # List available files in pattern detector directory
        if os.path.exists(pattern_detector_path):
            print(f"\n[INFO] Pattern detector directory contents:")
            for item in os.listdir(pattern_detector_path):
                if item.endswith('.py'):
                    print(f"  - {item}")
        else:
            print(f"\n[ERROR] Pattern detector directory not found: {pattern_detector_path}")

        sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n[STOP] Service stopped by user")
        print("Thank you for using SolPattern Detector!")

    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
