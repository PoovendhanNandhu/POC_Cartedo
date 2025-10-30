#!/bin/bash

# Railway Deployment Script for FastAPI LangGraph Application
# This script helps deploy your application to Railway

set -e  # Exit on error

echo "🚂 Railway Deployment Script"
echo "============================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if Railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo -e "${RED}❌ Railway CLI is not installed${NC}"
    echo ""
    echo "To install Railway CLI:"
    echo "  npm install -g @railway/cli"
    echo "  or"
    echo "  brew install railway"
    echo ""
    exit 1
fi

echo -e "${GREEN}✅ Railway CLI is installed${NC}"

# Check if user is logged in
if ! railway whoami &> /dev/null; then
    echo -e "${YELLOW}⚠️  Not logged in to Railway${NC}"
    echo "Running: railway login"
    railway login
fi

echo -e "${GREEN}✅ Logged in to Railway${NC}"

# Check for required files
echo ""
echo "📋 Checking required files..."

REQUIRED_FILES=("requirements.txt" "Procfile" "railway.toml" "src/main.py")
for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        echo -e "${RED}❌ Missing required file: $file${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ Found: $file${NC}"
done

# Check environment variables
echo ""
echo "🔐 Checking environment variables..."

if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  No .env file found${NC}"
    echo "You'll need to set environment variables in Railway dashboard"
else
    echo -e "${GREEN}✅ .env file found${NC}"
fi

# Menu
echo ""
echo "What would you like to do?"
echo "1) Initialize new Railway project"
echo "2) Link to existing Railway project"
echo "3) Deploy to Railway"
echo "4) Set environment variables"
echo "5) View deployment logs"
echo "6) Open Railway dashboard"
echo "7) Check deployment status"
echo "8) Full deployment (init + deploy + set env)"
echo "9) Exit"
echo ""
read -p "Select option (1-9): " option

case $option in
    1)
        echo ""
        echo "🆕 Initializing new Railway project..."
        railway init
        echo -e "${GREEN}✅ Project initialized${NC}"
        echo "Next: Set environment variables using option 4"
        ;;

    2)
        echo ""
        echo "🔗 Linking to existing Railway project..."
        railway link
        echo -e "${GREEN}✅ Project linked${NC}"
        ;;

    3)
        echo ""
        echo "🚀 Deploying to Railway..."
        railway up
        echo ""
        echo -e "${GREEN}✅ Deployment initiated${NC}"
        echo "Check status with option 7"
        ;;

    4)
        echo ""
        echo "🔐 Setting environment variables..."
        echo ""
        echo "Required environment variables:"
        echo "  - OPENAI_API_KEY"
        echo "  - OPENAI_MODEL (default: gpt-4o-mini)"
        echo "  - OPENAI_TEMPERATURE (default: 0)"
        echo "  - OPENAI_SEED (default: 42)"
        echo ""

        if [ -f ".env" ]; then
            echo "Found .env file. Do you want to set variables from .env? (y/n)"
            read -p "> " use_env

            if [ "$use_env" = "y" ]; then
                # Read and set each variable from .env
                while IFS='=' read -r key value; do
                    # Skip comments and empty lines
                    [[ $key =~ ^#.*$ ]] && continue
                    [[ -z $key ]] && continue

                    # Remove quotes and whitespace
                    value=$(echo "$value" | sed -e 's/^"//' -e 's/"$//' -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')

                    echo "Setting $key..."
                    railway variables --set "$key=$value"
                done < .env

                echo -e "${GREEN}✅ Environment variables set from .env${NC}"
            fi
        else
            echo "Enter OPENAI_API_KEY:"
            read -p "> " openai_key

            railway variables --set "OPENAI_API_KEY=$openai_key"
            railway variables --set "OPENAI_MODEL=gpt-4o-mini"
            railway variables --set "OPENAI_TEMPERATURE=0"
            railway variables --set "OPENAI_SEED=42"

            echo -e "${GREEN}✅ Environment variables set${NC}"
        fi

        echo ""
        echo "View all variables:"
        railway variables
        ;;

    5)
        echo ""
        echo "📋 Viewing deployment logs..."
        railway logs
        ;;

    6)
        echo ""
        echo "🌐 Opening Railway dashboard..."
        railway open
        ;;

    7)
        echo ""
        echo "📊 Checking deployment status..."
        railway status
        ;;

    8)
        echo ""
        echo "🚀 Full deployment process starting..."
        echo ""

        # Check if already linked
        if railway status &> /dev/null; then
            echo -e "${GREEN}✅ Already linked to Railway project${NC}"
        else
            echo "Do you want to (1) Create new project or (2) Link existing? (1/2)"
            read -p "> " project_option

            if [ "$project_option" = "1" ]; then
                railway init
            else
                railway link
            fi
        fi

        echo ""
        echo "Setting environment variables..."

        if [ -f ".env" ]; then
            echo "Setting variables from .env file..."
            while IFS='=' read -r key value; do
                [[ $key =~ ^#.*$ ]] && continue
                [[ -z $key ]] && continue
                value=$(echo "$value" | sed -e 's/^"//' -e 's/"$//' -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')
                echo "Setting $key..."
                railway variables --set "$key=$value" || true
            done < .env
        else
            echo -e "${YELLOW}⚠️  No .env file found. You'll need to set variables manually.${NC}"
            echo "Enter OPENAI_API_KEY (or press Enter to skip):"
            read -p "> " openai_key

            if [ ! -z "$openai_key" ]; then
                railway variables --set "OPENAI_API_KEY=$openai_key"
            fi
        fi

        echo ""
        echo "🚀 Deploying to Railway..."
        railway up

        echo ""
        echo -e "${GREEN}✅ Deployment complete!${NC}"
        echo ""
        echo "Your API should be available at the Railway-provided URL"
        echo "Check the dashboard for the URL: railway open"
        ;;

    9)
        echo "Exiting..."
        exit 0
        ;;

    *)
        echo -e "${RED}❌ Invalid option${NC}"
        exit 1
        ;;
esac

echo ""
echo "🎉 Done!"
