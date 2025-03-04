#!/bin/bash

# Script to start the Docker Compose setup for the Trading Bot

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

print_blue "Starting Trading Bot Docker containers..."

# Get the real path of the project root
PROJECT_ROOT="$(dirname "$0")"

# Navigate to docker directory and start containers
cd "$PROJECT_ROOT/docker" || exit 1

print_blue "Working directory: $(pwd)"

# Check if we want to rebuild
if [ "$1" == "--rebuild" ]; then
    print_yellow "Rebuilding containers..."
    docker-compose up --build
else
    docker-compose up
fi

# Note: Ctrl+C will stop the containers 