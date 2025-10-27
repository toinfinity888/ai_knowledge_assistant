#!/bin/bash

# Installation and Test Script for Real-time Support Assistant
# This script installs dependencies and runs the test suite

set -e  # Exit on error

echo "========================================================================"
echo "REAL-TIME SUPPORT ASSISTANT - INSTALLATION & TEST"
echo "========================================================================"

# Check if we're in virtual environment
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo ""
    echo "⚠️  Virtual environment not activated!"
    echo ""
    echo "Please activate it first:"
    echo "  source /Users/saraevsviatoslav/Documents/.venv/bin/activate"
    echo ""
    exit 1
fi

echo ""
echo "✓ Virtual environment: $VIRTUAL_ENV"
echo ""

# Step 1: Install dependencies
echo "[1/4] Installing dependencies..."
echo "--------------------------------------------------------------------"
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo "✓ Dependencies installed"

# Step 2: Check setup
echo ""
echo "[2/4] Checking system setup..."
echo "--------------------------------------------------------------------"
python check_setup.py | tail -20

# Step 3: Initialize database
echo ""
echo "[3/4] Initializing database tables..."
echo "--------------------------------------------------------------------"
python app/database/init_call_tracking.py

# Step 4: Run tests
echo ""
echo "[4/4] Running integration tests..."
echo "--------------------------------------------------------------------"
echo ""
python examples/test_realtime_flow.py

echo ""
echo "========================================================================"
echo "✅ INSTALLATION AND TESTS COMPLETE!"
echo "========================================================================"
echo ""
echo "Your system is ready! You can now:"
echo "  1. Start the server: python main.py"
echo "  2. Configure ACD webhooks"
echo "  3. Connect support agent UI"
echo ""
