#!/bin/bash
set -e

# Create necessary directories
mkdir -p /app/backend/data/cache /app/backend/logs

# Ensure environment variables are set in Flask environment
export FLASK_ENV=${FLASK_ENV:-development}
export API_KEY=${API_KEY:-your-secret-api-key}
export REACT_APP_API_KEY=${REACT_APP_API_KEY:-your-secret-api-key}

# Load all environment variables from .env file if it exists
if [ -f backend/config/.env ]; then
  export $(cat backend/config/.env | grep -v '#' | xargs)
  echo "Loaded environment variables from backend/config/.env file"
elif [ -f backend/config/.env.production ]; then
  export $(cat backend/config/.env.production | grep -v '#' | xargs)
  echo "Loaded environment variables from backend/config/.env.production file"
fi

# Print debug info
echo "API URLs and environment:"
echo "FLASK_ENV: $FLASK_ENV"
echo "API_KEY: ${API_KEY:0:4}... (truncated)"

# Print telegram configuration (partially obscured for security)
if [ ! -z "$TELEGRAM_BOT_TOKEN" ]; then
  echo "TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN:0:8}... (configured)"
  echo "TELEGRAM_CHAT_ID: $TELEGRAM_CHAT_ID (configured)"
else
  echo "WARNING: TELEGRAM_BOT_TOKEN is not set"
fi

# Print email configuration
if [ "$EMAIL_ENABLED" = "true" ]; then
  echo "Email notifications: ENABLED"
  echo "EMAIL_RECIPIENT: $EMAIL_RECIPIENT"
else
  echo "Email notifications: DISABLED"
fi

# Execute the given command (typically the main application)
exec "$@" 