#!/bin/bash
# Databricks Apps launcher: bind Streamlit to the injected app port.
set -euo pipefail
exec streamlit run app.py \
  --server.port="${DATABRICKS_APP_PORT:-8000}" \
  --server.address=0.0.0.0 \
  --server.headless=true \
  --browser.gatherUsageStats=false
