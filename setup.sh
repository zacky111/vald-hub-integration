#!/bin/bash
# Vald Hub Dashboard Setup for macOS & Linux

echo ""
echo "========================================"
echo " Vald Hub Dashboard Setup (Mac/Linux)"
echo "========================================"
echo ""

# Check if Python3 is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python3 is not installed"
    echo "Please install Python from https://www.python.org/downloads/"
    exit 1
fi

# Check Python version
python3 --version

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "Error creating virtual environment"
        exit 1
    fi
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
python -m pip install --upgrade pip

# Install dependencies
echo "Installing dependencies from requirements.txt..."
pip install -r requirements.txt

# Create .env if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env file..."
    cat > .env << EOF
VALD_HUB_API_KEY=your_api_key_here
VALD_HUB_BASE_URL=https://api.vald-hub.com
EOF
    echo "Created .env file - UPDATE WITH YOUR CREDENTIALS"
fi

echo ""
echo "========================================"
echo " Setup Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "   1. Edit .env with your Vald Hub API key"
echo "   2. Run: streamlit run app.py"
echo ""
echo "The app will open at: http://localhost:8501"
echo ""
