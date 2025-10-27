#!/bin/bash

# Launch Demo Script
# Quick start for the microphone demo

set -e

echo "========================================================================"
echo "🎤 AI SUPPORT ASSISTANT - MICROPHONE DEMO"
echo "========================================================================"
echo ""

# Check Python
if ! command -v python &> /dev/null; then
    echo "❌ Python not found. Please install Python 3.9+"
    exit 1
fi

echo "✓ Python found: $(python --version)"
echo ""

# Check dependencies
echo "Checking dependencies..."
python -c "import flask, openai, qdrant_client" 2>/dev/null || {
    echo "⚠️  Installing dependencies..."
    pip install -q -r requirements.txt
    echo "✓ Dependencies installed"
}

echo ""
echo "Starting server..."
echo "========================================================================"
echo ""
echo "📍 Demo will be available at:"
echo "   http://localhost:8080/demo"
echo ""
echo "🎯 Instructions:"
echo "   1. Open http://localhost:8080/demo in your browser"
echo "   2. Click the microphone button"
echo "   3. Speak clearly about a technical problem"
echo "   4. Watch AI suggestions appear in real-time!"
echo ""
echo "💡 Example phrases to try:"
echo "   - 'I'm getting error 401 when trying to log in'"
echo "   - 'My payment failed with error declined'"
echo "   - 'The app is very slow to load'"
echo ""
echo "Press Ctrl+C to stop the server"
echo "========================================================================"
echo ""

# Start server
python main.py
