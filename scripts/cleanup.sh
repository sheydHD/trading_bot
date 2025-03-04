#!/bin/bash
# Cleanup script to remove redundant files after restructuring

# Change to project root directory
cd "$(dirname "$0")/.." || exit 1

# Print colored messages
print_green() {
    echo -e "\e[32m$1\e[0m"
}

print_yellow() {
    echo -e "\e[33m$1\e[0m"
}

print_red() {
    echo -e "\e[31m$1\e[0m"
}

print_blue() {
    echo -e "\e[34m$1\e[0m"
}

# Safety check function to verify files exist in new location
check_file_exists() {
    original_file="$1"
    new_file="$2"
    
    if [ ! -f "$new_file" ]; then
        print_red "ERROR: $new_file does not exist. Not removing $original_file for safety."
        return 1
    fi
    
    return 0
}

# Check directory exists
check_dir_exists() {
    dir="$1"
    if [ ! -d "$dir" ]; then
        print_red "ERROR: Directory $dir does not exist. Aborting for safety."
        exit 1
    fi
}

# Main safety checks
print_blue "Performing safety checks..."

# Check that the new directories exist
check_dir_exists "backend/core"
check_dir_exists "backend/utils"
check_dir_exists "backend/api"
check_dir_exists "backend/config"
check_dir_exists "backend/data/cache"
check_dir_exists "backend/logs"
check_dir_exists "frontend/src"
check_dir_exists "frontend/public"

print_green "Safety checks passed. All new directories exist."

# Ask for confirmation
print_yellow "This script will remove redundant files that have been moved to the new structure."
print_yellow "The following files will be removed:"
echo "- main.py"
echo "- utils/ directory"
echo "- api/ directory"
echo "- telegram_messages.json"
echo "- analysis_cache.json"
echo "- api_cache.json"
echo "- trading_bot.log"
echo "- .env"
echo "- .env.production"
echo "- requirements.txt"
echo "- Requirements.in"
echo "- src/ directory"
echo "- public/ directory"

echo
read -p "Are you sure you want to continue? (y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_yellow "Cleanup cancelled."
    exit 0
fi

# Start cleanup process
print_blue "Starting cleanup process..."

# Core Python file
if [ -f "main.py" ] && [ -f "backend/core/main.py" ]; then
    rm main.py
    print_green "Removed main.py"
fi

# Data files
if [ -f "telegram_messages.json" ]; then
    rm telegram_messages.json
    print_green "Removed telegram_messages.json"
fi

if [ -f "analysis_cache.json" ]; then
    rm analysis_cache.json
    print_green "Removed analysis_cache.json"
fi

if [ -f "api_cache.json" ]; then
    rm api_cache.json
    print_green "Removed api_cache.json"
fi

if [ -f "trading_bot.log" ]; then
    rm trading_bot.log
    print_green "Removed trading_bot.log"
fi

# Configuration files
if [ -f ".env" ] && [ -f "backend/config/.env" ]; then
    rm .env
    print_green "Removed .env"
fi

if [ -f ".env.production" ] && [ -f "backend/config/.env.production" ]; then
    rm .env.production
    print_green "Removed .env.production"
fi

if [ -f "requirements.txt" ] && [ -f "backend/config/requirements.txt" ]; then
    rm requirements.txt
    print_green "Removed requirements.txt"
fi

if [ -f "Requirements.in" ] && [ -f "backend/config/Requirements.in" ]; then
    rm Requirements.in
    print_green "Removed Requirements.in"
fi

# Directories - using rm -rf with caution - only if they exist and have been moved
if [ -d "utils" ]; then
    # Check if some critical files have been moved to confirm we can delete safely
    if [ -f "backend/utils/config.py" ] && [ -f "backend/utils/telegram.py" ]; then
        rm -rf utils
        print_green "Removed utils/ directory"
    else
        print_red "Safety check failed: Essential utils files not found in new location. Not removing utils/ directory."
    fi
fi

if [ -d "api" ]; then
    # Check if some critical files have been moved
    if [ -f "backend/api/app.py" ]; then
        rm -rf api
        print_green "Removed api/ directory"
    else
        print_red "Safety check failed: Essential api files not found in new location. Not removing api/ directory."
    fi
fi

if [ -d "src" ]; then
    # Check if the directory has been moved
    if [ -d "frontend/src/components" ] || [ -f "frontend/src/App.js" ]; then
        rm -rf src
        print_green "Removed src/ directory"
    else
        print_red "Safety check failed: Essential frontend files not found in new location. Not removing src/ directory."
    fi
fi

if [ -d "public" ]; then
    # Check if the directory exists in the new location
    if [ -d "frontend/public" ]; then
        rm -rf public
        print_green "Removed public/ directory"
    else
        print_red "Safety check failed: Public directory not found in new location. Not removing public/ directory."
    fi
fi

print_green "Cleanup complete! Your directory structure is now cleaner and more organized."
print_blue "Your project can now be run using './run.py' or 'python run.py'" 