#!/bin/bash

# Check if backend/config directory exists
if [ -d "backend/config" ]; then
    echo "backend/config directory exists"
else
    echo "backend/config directory does NOT exist"
fi

# Check if requirements.txt file exists
if [ -f "backend/config/requirements.txt" ]; then
    echo "backend/config/requirements.txt file exists"
    echo "Contents (first few lines):"
    head -5 backend/config/requirements.txt
else
    echo "backend/config/requirements.txt file does NOT exist"
fi

# Check if .env.example file exists
if [ -f "backend/config/.env.example" ]; then
    echo "backend/config/.env.example file exists"
else
    echo "backend/config/.env.example file does NOT exist"
fi

# List all files in backend/config
echo "Files in backend/config directory:"
ls -la backend/config/ 