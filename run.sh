#!/bin/bash
# Run script for AI Workflow Automation System

set -e

echo "🤖 AI Workflow Automation System"
echo "================================="

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip > /dev/null 2>&1

# Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt > /dev/null 2>&1

# Check for .env file
if [ ! -f ".env" ]; then
    echo "⚠️  No .env file found. Creating from template..."
    cp .env.example .env
    echo ""
    echo "📝 Please edit .env with your credentials:"
    echo "   - LLM_PROVIDER (nvidia or openai)"
    if grep -q "LLM_PROVIDER=nvidia" .env.example; then
        echo "   - NVIDIA_API_KEY (required for NVIDIA provider)"
    fi
    echo "   - EMAIL_ADDRESS and EMAIL_PASSWORD (for email features)"
    echo ""
    echo "Then run this script again."
    exit 1
fi

# Check for required environment variables
source .env
LLM_PROVIDER=${LLM_PROVIDER:-nvidia}
LLM_PROVIDER=$(echo "$LLM_PROVIDER" | tr '[:upper:]' '[:lower:]')

if [ "$LLM_PROVIDER" = "nvidia" ]; then
    API_KEY_VAR="NVIDIA_API_KEY"
    API_KEY_VALUE="${NVIDIA_API_KEY}"
elif [ "$LLM_PROVIDER" = "openai" ]; then
    API_KEY_VAR="OPENAI_API_KEY"
    API_KEY_VALUE="${OPENAI_API_KEY}"
else
    echo "❌ Unsupported LLM_PROVIDER: $LLM_PROVIDER"
    echo "   Supported providers: nvidia, openai"
    exit 1
fi

if [ -z "$API_KEY_VALUE" ] || [ "$API_KEY_VALUE" = "nvapi-your_nvidia_api_key_here" ] || [ "$API_KEY_VALUE" = "your_openai_api_key_here" ]; then
    echo "❌ $API_KEY_VAR not set in .env"
    echo "   Please edit .env and add your $API_KEY_VAR"
    exit 1
fi

echo "✅ Environment configured (Provider: $LLM_PROVIDER)"
echo "🚀 Starting Streamlit on http://localhost:8501"
echo "   Press Ctrl+C to stop"
echo ""

# Run Streamlit
streamlit run app.py