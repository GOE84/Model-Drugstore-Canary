#!/bin/bash

# Drugstore Canary - Quick Start Script
# This script sets up and runs the complete system

echo "======================================"
echo "Drugstore Canary - Quick Start"
echo "======================================"
echo ""

# Step 1: Generate synthetic data
echo "Step 1: Generating synthetic data..."
python3 data/data_generator.py

if [ $? -ne 0 ]; then
    echo "❌ Error generating data. Please install dependencies first:"
    echo "   pip3 install -r requirements.txt"
    exit 1
fi

echo ""
echo "✅ Data generated successfully!"
echo ""

# Step 2: Start API server in background
echo "Step 2: Starting API server..."
python3 api/main.py &
API_PID=$!

echo "✅ API server started (PID: $API_PID)"
echo "   API URL: http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo ""

# Wait for API to start
sleep 3

# Step 3: Start dashboard server
echo "Step 3: Starting dashboard..."
cd dashboard
python3 -m http.server 8080 &
DASHBOARD_PID=$!
cd ..

echo "✅ Dashboard started (PID: $DASHBOARD_PID)"
echo "   Dashboard URL: http://localhost:8080"
echo ""

echo "======================================"
echo "🎉 Drugstore Canary is now running!"
echo "======================================"
echo ""
echo "Access the system:"
echo "  📊 Dashboard: http://localhost:8080"
echo "  🔌 API: http://localhost:8000"
echo "  📖 API Docs: http://localhost:8000/docs"
echo ""
echo "To stop the system:"
echo "  kill $API_PID $DASHBOARD_PID"
echo ""
echo "Press Ctrl+C to stop all services..."

# Wait for user interrupt
trap "kill $API_PID $DASHBOARD_PID; echo 'Services stopped.'; exit" INT
wait
