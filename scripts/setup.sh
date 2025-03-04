#!/bin/bash
# Setup script for the Trading Bot

# Change to project root directory
cd "$(dirname "$0")/.." || exit 1

# Print colored messages
print_green() {
    echo -e "\e[32m$1\e[0m"
}

print_yellow() {
    echo -e "\e[33m$1\e[0m"
}

print_blue() {
    echo -e "\e[34m$1\e[0m"
}

print_green "Starting Trading Bot setup..."

# Ensure directories exist
print_blue "Creating directory structure..."
mkdir -p backend/data/cache backend/logs

# Copy environment file if it doesn't exist
if [ ! -f backend/config/.env ]; then
    print_blue "Setting up environment configuration..."
    if [ -f backend/config/.env.example ]; then
        cp backend/config/.env.example backend/config/.env
        print_green "Created .env file from example. Please edit backend/config/.env with your actual values."
    else
        print_yellow "Warning: .env.example not found. You'll need to create backend/config/.env manually."
    fi
else
    print_blue "Environment file already exists."
fi

# Install Python dependencies
print_blue "Installing Python dependencies..."
pip install -r backend/config/requirements.txt

# Check if frontend exists and set it up if needed
if [ -d frontend ]; then
    print_blue "Setting up frontend..."
    cd frontend || exit 1
    if [ -f config/package.json ]; then
        # Copy package.json to frontend root for npm install
        cp config/package.json .
        npm install
        print_green "Frontend dependencies installed."
    else
        print_yellow "Warning: package.json not found in frontend/config directory."
    fi
    cd ..
fi

print_green "Setup complete! You can now run the bot with: python run.py"
print_yellow "Don't forget to edit backend/config/.env with your actual API keys and settings." 