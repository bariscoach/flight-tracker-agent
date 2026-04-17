#!/bin/bash
# Open the Flight Tracker Settings UI in your browser.
# Double-click this file or run: bash open_settings.sh

cd "$(dirname "$0")"

# Start the web UI in the background
/usr/local/bin/python3.11 web_ui/app.py &
SERVER_PID=$!

# Give Flask a moment to start, then open the browser
sleep 1.2
open http://localhost:5050

echo "Settings UI running at http://localhost:5050"
echo "Press Ctrl+C to stop."

# Wait for the server process
wait $SERVER_PID
