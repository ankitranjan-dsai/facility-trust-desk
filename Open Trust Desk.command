#!/bin/bash
# Double-click this file in Finder to launch the Facility Trust Desk.
# It starts the local server and opens the app in your browser.

# Always run from this script's own folder (works no matter where it's launched).
cd "$(dirname "$0")" || exit 1

PORT=8501
URL="http://localhost:$PORT"

echo "──────────────────────────────────────────────"
echo "  Facility Trust Desk"
echo "  Opening $URL in your browser…"
echo "  (Press Ctrl-C in this window to stop the app.)"
echo "──────────────────────────────────────────────"

# If something is already serving on the port, just open the browser and exit.
if curl -s -o /dev/null "$URL" 2>/dev/null; then
  open "$URL"
  exit 0
fi

# Open the browser a few seconds after the server comes up.
( sleep 4; open "$URL" ) &

# Run Streamlit from the project's virtual environment (foreground; Ctrl-C stops it).
exec ./.venv/bin/streamlit run app.py \
  --server.headless=true \
  --server.port="$PORT" \
  --browser.gatherUsageStats=false
