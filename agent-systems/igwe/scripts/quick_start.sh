#!/bin/bash
# Quick Start Script for Linux/Mac
# Starts Redis and the IUL Appointment Setter System

echo "========================================"
echo "IUL Appointment Setter - Quick Start"
echo "========================================"
echo ""

# Check if Redis is installed
if ! command -v redis-server &> /dev/null
then
    echo "[WARNING] redis-server not found"
    echo "Please install Redis:"
    echo "  Ubuntu/Debian: sudo apt-get install redis-server"
    echo "  macOS: brew install redis"
    echo ""
    read -p "Press Enter to continue anyway..."
else
    # Check if Redis is already running
    if pgrep -x "redis-server" > /dev/null
    then
        echo "✅ Redis is already running"
    else
        echo "Starting Redis server..."
        redis-server --daemonize yes
        sleep 2
        echo "✅ Redis started"
    fi
fi

echo ""
echo "Starting IUL Appointment Setter System..."
echo ""

# Navigate to project root
cd "$(dirname "$0")/.."

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run the main system
python main.py
