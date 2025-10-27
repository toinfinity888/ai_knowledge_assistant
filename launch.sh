#!/bin/bash

# Real-time Support Assistant - Launch Script
# This script starts the Flask server with all real-time endpoints

set -e

echo "========================================================================"
echo "LAUNCHING REAL-TIME SUPPORT ASSISTANT SERVER"
echo "========================================================================"

# Check if in virtual environment
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo ""
    echo "⚠️  Virtual environment not activated!"
    echo "Activating .venv..."
    source /Users/saraevsviatoslav/Documents/.venv/bin/activate || {
        echo "Failed to activate virtual environment"
        exit 1
    }
fi

echo ""
echo "✓ Virtual environment: $VIRTUAL_ENV"
echo ""

# Check if dependencies are installed
echo "Checking dependencies..."
python -c "import flask, openai, qdrant_client, sqlalchemy" 2>/dev/null || {
    echo ""
    echo "⚠️  Missing dependencies. Installing..."
    pip install -q -r requirements.txt
    echo "✓ Dependencies installed"
}

echo ""
echo "Starting Flask server..."
echo "========================================================================"
echo ""
echo "🌐 Server will be available at:"
echo "   http://localhost:8080"
echo ""
echo "📡 API Endpoints:"
echo "   POST   http://localhost:8080/api/realtime/call/start"
echo "   POST   http://localhost:8080/api/realtime/transcription"
echo "   POST   http://localhost:8080/api/realtime/call/end"
echo "   GET    http://localhost:8080/api/realtime/suggestions/<session_id>"
echo "   WS     ws://localhost:8080/api/realtime/ws/<session_id>"
echo "   SSE    http://localhost:8080/api/realtime/stream/<session_id>"
echo ""
echo "Press Ctrl+C to stop the server"
echo "========================================================================"
echo ""

# Start the server
python main.py
